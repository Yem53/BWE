from __future__ import annotations

import json
import threading
import time
from collections import defaultdict, deque

import requests


def parse_markprice_array(msg: str) -> list[tuple[str, int, float]]:
    """Parse a !markPrice@arr payload → [(symbol, ts_ms, mark_price)] for USDT perps only."""
    try:
        arr = json.loads(msg)
    except Exception:
        return []
    if not isinstance(arr, list):
        return []
    out = []
    for x in arr:
        try:
            sym = x["s"]
            if not sym.endswith("USDT"):
                continue
            out.append((sym, int(x["E"]), float(x["p"])))
        except (KeyError, TypeError, ValueError):
            continue
    return out


class PriceBuffers:
    """Per-symbol rolling price samples.

    Two rings per symbol: a full-resolution short ring (last `short_max_sec`, ~1s steps)
    for fast windows, and a downsampled long ring (1 sample / `long_step_sec`, up to
    `long_max_sec`) for the 1h window. `samples()` merges them ascending.
    """

    def __init__(self, short_max_sec: int = 200, long_step_sec: int = 10, long_max_sec: int = 3600):
        self._short_max_ms = short_max_sec * 1000
        self._long_step_ms = long_step_sec * 1000
        self._long_max_ms = long_max_sec * 1000
        self._short: dict[str, deque] = defaultdict(deque)
        self._long: dict[str, deque] = defaultdict(deque)
        self._last_long_ts: dict[str, int] = {}

    def add(self, symbol: str, ts_ms: int, price: float) -> None:
        s = self._short[symbol]
        s.append((ts_ms, price))
        while s and ts_ms - s[0][0] > self._short_max_ms:
            s.popleft()
        last = self._last_long_ts.get(symbol)
        if last is None or ts_ms - last >= self._long_step_ms:
            lg = self._long[symbol]
            lg.append((ts_ms, price))
            self._last_long_ts[symbol] = ts_ms
            while lg and ts_ms - lg[0][0] > self._long_max_ms:
                lg.popleft()

    def short_samples(self, symbol: str) -> list[tuple[int, float]]:
        return list(self._short.get(symbol, ()))

    def samples(self, symbol: str) -> list[tuple[int, float]]:
        """Merged ascending samples (long + short), deduped by ts."""
        merged = dict(self._long.get(symbol, ()))
        merged.update(self._short.get(symbol, ()))
        return sorted(merged.items())

    def symbols(self) -> list[str]:
        return list(self._short.keys())


def oi_chg_from_hist(rows: list[dict]) -> tuple[float | None, float | None]:
    """From openInterestHist rows (oldest→newest) → (1h % change of contracts, latest USD OI)."""
    if len(rows) < 2:
        return None, None
    try:
        first = float(rows[0]["sumOpenInterest"])
        last = float(rows[-1]["sumOpenInterest"])
        oi_usd = float(rows[-1]["sumOpenInterestValue"])
    except (KeyError, ValueError):
        return None, None
    if first == 0:
        return None, None
    return (last / first - 1.0) * 100.0, oi_usd


def parse_ticker_price_array(rows: list[dict], now_ms: int) -> list[tuple[str, int, float]]:
    """Parse /fapi/v1/ticker/price response → [(symbol, ts_ms, price)] for USDT perps.

    Uses each row's exchange `time` if present, else the supplied poll `now_ms`."""
    out = []
    for x in rows:
        try:
            sym = x["symbol"]
            if not sym.endswith("USDT"):
                continue
            ts = int(x.get("time") or now_ms)
            out.append((sym, ts, float(x["price"])))
        except (KeyError, TypeError, ValueError):
            continue
    return out


class WSFeed:
    """Subscribes !markPrice@arr@1s; pushes (symbol, ts, price) into PriceBuffers.
    Auto-reconnect with exponential backoff. Runs its own thread via start()."""

    def __init__(self, ws_url: str, buffers: PriceBuffers, on_tick=None):
        self._url = ws_url
        self._buffers = buffers
        self._on_tick = on_tick
        self._stop = threading.Event()
        self.last_msg_ms = 0

    def _on_message(self, ws, message: str) -> None:
        rows = parse_markprice_array(message)
        if not rows:
            return
        now_ms = rows[0][1]
        for sym, ts, price in rows:
            self._buffers.add(sym, ts, price)
        self.last_msg_ms = int(time.time() * 1000)
        if self._on_tick:
            self._on_tick(now_ms)

    def _run_forever(self) -> None:
        import websocket  # lazy: only needed at runtime, not for unit tests
        backoff = 1
        while not self._stop.is_set():
            try:
                ws = websocket.WebSocketApp(self._url, on_message=self._on_message)
                ws.run_forever(ping_interval=15, ping_timeout=8)
            except Exception:
                pass
            if self._stop.is_set():
                break
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)

    def start(self) -> threading.Thread:
        t = threading.Thread(target=self._run_forever, daemon=True)
        t.start()
        return t

    def stop(self) -> None:
        self._stop.set()


class OIPoller:
    """Polls openInterestHist (period=5m, limit=13 → ~1h) for a set of symbols.
    Exposes {symbol: (oi_chg_1h_pct, oi_usd)}; refreshes round-robin under a throttle."""

    def __init__(self, fapi_base: str, poll_sec: int = 300):
        self._base = fapi_base
        self._poll_sec = poll_sec
        self._data: dict[str, tuple[float | None, float | None]] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._symbols: list[str] = []

    def set_universe(self, symbols: list[str]) -> None:
        with self._lock:
            self._symbols = list(symbols)

    def get(self, symbol: str) -> tuple[float | None, float | None]:
        return self._data.get(symbol, (None, None))

    def _poll_symbol(self, sym: str) -> None:
        try:
            r = requests.get(f"{self._base}/futures/data/openInterestHist",
                             params={"symbol": sym, "period": "5m", "limit": 13}, timeout=10)
            chg, usd = oi_chg_from_hist(r.json())
            self._data[sym] = (chg, usd)
        except Exception:
            pass

    def _run(self) -> None:
        while not self._stop.is_set():
            with self._lock:
                syms = list(self._symbols)
            t0 = time.time()
            for sym in syms:
                if self._stop.is_set():
                    break
                self._poll_symbol(sym)
                time.sleep(0.3)
            elapsed = time.time() - t0
            self._stop.wait(max(1.0, self._poll_sec - elapsed))

    def start(self) -> threading.Thread:
        t = threading.Thread(target=self._run, daemon=True)
        t.start()
        return t

    def stop(self) -> None:
        self._stop.set()


class RestPriceFeed:
    """Polls /fapi/v1/ticker/price every poll_sec; pushes (symbol, ts, price) into
    PriceBuffers. Drop-in alternative to WSFeed (same start/stop/last_msg_ms interface)
    for environments where the futures websocket won't deliver data frames (e.g. this EC2)."""

    def __init__(self, fapi_base: str, buffers: PriceBuffers, poll_sec: float = 1.0, on_tick=None):
        self._base = fapi_base
        self._buffers = buffers
        self._poll_sec = poll_sec
        self._on_tick = on_tick
        self._stop = threading.Event()
        self.last_msg_ms = 0

    def _poll_once(self) -> None:
        r = requests.get(f"{self._base}/fapi/v1/ticker/price", timeout=10)
        now_ms = int(time.time() * 1000)
        rows = parse_ticker_price_array(r.json(), now_ms)
        for sym, ts, price in rows:
            self._buffers.add(sym, ts, price)
        if rows:
            self.last_msg_ms = int(time.time() * 1000)
            if self._on_tick:
                self._on_tick(now_ms)

    def _run(self) -> None:
        while not self._stop.is_set():
            t0 = time.time()
            try:
                self._poll_once()
            except Exception:
                pass
            self._stop.wait(max(0.1, self._poll_sec - (time.time() - t0)))

    def start(self) -> threading.Thread:
        t = threading.Thread(target=self._run, daemon=True)
        t.start()
        return t

    def stop(self) -> None:
        self._stop.set()
