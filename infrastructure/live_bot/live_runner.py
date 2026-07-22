#!/usr/bin/env python3
"""BWE Live Top-3 Runner — production trading on Binance USDT-M futures.

Strategy mix: Top 3 from 2-run intersection backtest (both runs positive)
  A_MULTI_CONFIRM — 5-filter strict short
  B_ASIA_AM_STRICT — hours 5-9 UTC + time_decay exit
  C_PULLBACK_VOL — pullback from high + volume z-score

Data sources:
  - 1m klines: fetched directly from Binance REST (local DB stale due to WAL)
  - Top 50 movers: /fapi/v1/ticker/24hr
  - BWE events: /Volumes/T9/BWE/30_DATA/bwe_logs/bwe_matrix_posts.jsonl

Safety guards (7):
  1. Per-symbol cross-strategy lock (one position per symbol total)
  2. Blacklist + 10d uptrend filter (auto-skip pumping coins)
  3. Slippage protection (abort entry if fill > 0.5% off)
  4. Daily loss limit + total drawdown limit (auto-halt)
  5. Kill switch file (/Users/ye/.bwe/EMERGENCY_HALT_LIVE)
  6. Liquidation safety monitor (close at 10% before liq price)
  7. State persistence + clean restart recovery
"""
from __future__ import annotations

import argparse
import dataclasses
import fcntl  # FIX BLOCKING (audit 3 — process lock): prevent double-instance race
import hashlib
import hmac
import html  # FIX SECURITY: escape user-controlled strings before HTML telegram
import json
import math
import os
import signal
import sys
import time
import traceback
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

# Paths: env vars override; defaults work for cloud (EC2 layout) and local (Mac layout via symlink).
# CLI args also override (--config, --state-dir, --secrets).
DEFAULT_CONFIG = Path(os.getenv("BWE_LIVE_CONFIG",
    "/home/ubuntu/bwe-live/config/strategies_live_top3.json"))
DEFAULT_STATE_DIR = Path(os.getenv("BWE_LIVE_STATE_DIR",
    "/home/ubuntu/bwe-live/runtime"))
DEFAULT_SECRETS = Path(os.getenv("BWE_LIVE_SECRETS",
    "/home/ubuntu/bwe-live/secrets.env"))
# BWE log is optional — on cloud it doesn't exist, runner falls back to top-movers only.
BWE_LOG = Path(os.getenv("BWE_LIVE_BWE_LOG",
    "/home/ubuntu/bwe-live/bwe_matrix_posts.jsonl"))
FAPI_BASE = "https://fapi.binance.com"

SECONDS_PER_MIN = 60
MS_PER_MIN = 60_000
MS_PER_DAY = 86_400_000

RUNNING = True
SHUTDOWN_REASON = ""


# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────

def utc_now_ms() -> int:
    return int(time.time() * 1000)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


_log_file_handle = None


def init_logging(log_path: Path) -> None:
    global _log_file_handle
    log_path.parent.mkdir(parents=True, exist_ok=True)
    _log_file_handle = open(log_path, "a", buffering=1)  # line-buffered


def log(level: str, msg: str) -> None:
    line = f"[{utc_now_iso()}] [{level}] {msg}"
    print(line, flush=True)
    if _log_file_handle is not None:
        try:
            _log_file_handle.write(line + "\n")
        except Exception:
            pass


def log_event(payload: dict[str, Any], events_path: Path) -> None:
    """Append a structured event to the events.jsonl audit trail."""
    payload = {"ts_ms": utc_now_ms(), "ts_iso": utc_now_iso(), **payload}
    try:
        events_path.parent.mkdir(parents=True, exist_ok=True)
        with open(events_path, "a") as f:
            f.write(json.dumps(payload, default=str) + "\n")
    except Exception as e:
        log("WARN", f"failed to write event: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Dataclasses
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class StrategyDef:
    strategy_id: str
    label: str
    side: str  # "short" or "long"
    entry: dict[str, Any]
    exit: dict[str, Any]
    rank_in_backtest: int = 0
    expected_signals_per_day: float = 0
    backtest_avg_sum_pct: float = 0
    backtest_avg_wr_pct: float = 0
    # FIX PER-STRAT-NOTIONAL (2026-05-21): optional per-strategy notional override.
    # 0 = use portfolio.notional_per_trade_usdt default. Set in config to size a
    # specific strategy bigger (e.g. B_US_PM at $300 while D/C stay at $100).
    notional_usdt: float = 0


@dataclass
class Position:
    symbol: str
    strategy_id: str
    side: str  # "short" or "long"
    qty: float
    notional_usdt: float
    leverage: int
    entry_price: float
    entry_ts_ms: int
    atr_at_entry: float  # absolute price, not pct
    sl_price: float
    tp_init_price: float  # initial TP price
    tp_final_price: float  # final TP price (for time_decay)
    exit_type: str  # "single" or "time_decay"
    time_stop_min: float
    tp_confirm_bars: int
    confirm_counter: int = 0  # consecutive 1m bars at TP target
    last_confirm_bar_ot: int = 0  # open_time of bar last counted (prevents same-bar double-count)
    binance_order_id: int | None = None
    # FIX LIVE-EXCHANGE-SL (2026-05-17): exchange-side STOP_MARKET safety net.
    # If bot crashes / network dies between poll cycles, this order auto-fires at SL price.
    # Bot's poll-based SL still primary (faster, allows confirm_bars on TP); this is backup.
    exchange_sl_order_id: int | None = None

    def current_tp_price(self, now_ms: int) -> float:
        if self.exit_type == "single":
            return self.tp_init_price
        elapsed_min = (now_ms - self.entry_ts_ms) / SECONDS_PER_MIN / 1000
        progress = min(1.0, elapsed_min / self.time_stop_min)
        # linear decay from tp_init to tp_final
        if self.side == "short":
            # short TP is lower price; tp_init_price > tp_final_price (closer to entry)
            return self.tp_init_price + (self.tp_final_price - self.tp_init_price) * progress
        else:
            return self.tp_init_price + (self.tp_final_price - self.tp_init_price) * progress

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RiskState:
    daily_pnl_usdt: float = 0.0
    daily_pnl_date_utc: str = ""  # YYYY-MM-DD
    total_pnl_usdt: float = 0.0
    halted: bool = False
    halt_reason: str = ""
    # FIX LIVE-BLOCK-COUNTERS (2026-05-16): track which safety filters blocked would-be trades
    block_counters: dict[str, int] = field(default_factory=dict)

    def bump(self, key: str) -> None:
        self.block_counters[key] = self.block_counters.get(key, 0) + 1

    def reset_daily_if_needed(self) -> bool:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self.daily_pnl_date_utc != today:
            old = self.daily_pnl_usdt
            self.daily_pnl_usdt = 0.0
            self.daily_pnl_date_utc = today
            # FIX TG-COUNTER-RESET (2026-05-19): clear block_counters daily so heartbeat
            # shows TODAY's stats not cumulative-since-startup. Previously "FAILED open 5"
            # from L11/L13 era stayed visible for weeks and confused operators.
            self.block_counters.clear()
            # FIX: clear daily_loss_limit halt at rollover (total_drawdown halt stays as protection)
            if "daily_loss_limit" in self.halt_reason:
                self.halted = False
                self.halt_reason = ""
            # Always return True on rollover so caller can fire daily report
            return True
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Secrets loader
# ─────────────────────────────────────────────────────────────────────────────


def load_secrets(secrets_path: Path) -> None:
    if not secrets_path.exists():
        log("FATAL", f"secrets file not found: {secrets_path}")
        sys.exit(2)
    for line in secrets_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ[k.strip()] = v.strip()


# ─────────────────────────────────────────────────────────────────────────────
# HTTP + signed request
# ─────────────────────────────────────────────────────────────────────────────


def request_json(url: str, *, method: str = "GET", body: bytes | None = None,
                 headers: dict[str, str] | None = None, timeout: float = 10.0) -> Any:
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        # FIX: extract Binance error code/msg from response body for better diagnostics
        try:
            err_body = e.read().decode()
            try:
                err_json = json.loads(err_body)
                code = err_json.get("code", "")
                msg = err_json.get("msg", err_body)
                raise RuntimeError(f"Binance HTTP {e.code} code={code}: {msg}")
            except (ValueError, AttributeError):
                raise RuntimeError(f"HTTP {e.code}: {err_body[:300]}")
        except (AttributeError, OSError):
            raise RuntimeError(f"HTTP {e.code}")


def credentials() -> tuple[str, str]:
    api_key = os.getenv("BINANCE_LIVE_API_KEY", "")
    secret = os.getenv("BINANCE_LIVE_API_SECRET", "")
    if not api_key or not secret:
        raise RuntimeError("BINANCE_LIVE_API_KEY / SECRET missing in environment")
    return api_key, secret


def signed_request(method: str, path: str, params: dict[str, Any] | None = None,
                   timeout: float = 10.0) -> Any:
    api_key, secret = credentials()
    payload = dict(params or {})
    payload["timestamp"] = utc_now_ms()
    payload["recvWindow"] = 5000
    query = urllib.parse.urlencode(payload)
    sig = hmac.new(secret.encode(), query.encode(), hashlib.sha256).hexdigest()
    full = f"{query}&signature={sig}"
    headers = {
        "X-MBX-APIKEY": api_key,
        "User-Agent": "BWE-Live-Top3/1.0",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    url = f"{FAPI_BASE.rstrip('/')}{path}"
    if method == "GET":
        return request_json(f"{url}?{full}", headers=headers, timeout=timeout)
    return request_json(url, method=method, body=full.encode(), headers=headers, timeout=timeout)


# ─────────────────────────────────────────────────────────────────────────────
# Binance REST wrappers
# ─────────────────────────────────────────────────────────────────────────────

_exchange_filters_cache: dict[str, dict[str, Any]] = {}
_EXCHANGE_TTL_MS = 60 * 60 * 1000  # 1h — was 24h, but bulk fetch is cheap (one req for all)
_exchange_bulk_fetched_ms: int = 0


def _parse_symbol_filters(raw: dict[str, Any]) -> dict[str, Any]:
    """Parse a single symbol's exchangeInfo dict into our normalized filter shape."""
    filters = {f["filterType"]: f for f in raw.get("filters", [])}
    lot = filters.get("LOT_SIZE", {})
    market_lot = filters.get("MARKET_LOT_SIZE", {})
    min_notional = filters.get("MIN_NOTIONAL", {})
    percent = filters.get("PERCENT_PRICE", {})
    price_filter = filters.get("PRICE_FILTER", {})
    return {
        "stepSize": float(lot.get("stepSize", "0.001")),
        "minQty": float(lot.get("minQty", "0")),
        "lotMaxQty": float(lot.get("maxQty", "1e18")),
        "marketMaxQty": float(market_lot.get("maxQty", "1e18")),
        "marketMinQty": float(market_lot.get("minQty", "0")),
        "marketStepSize": float(market_lot.get("stepSize", "0.001")),
        "quantityPrecision": int(raw.get("quantityPrecision", 3)),
        "pricePrecision": int(raw.get("pricePrecision", 4)),
        "minNotional": float(min_notional.get("notional", "5")),
        "percentMultiplierUp": float(percent.get("multiplierUp", "5")),
        "percentMultiplierDown": float(percent.get("multiplierDown", "0.2")),
        "tickSize": float(price_filter.get("tickSize", "0")),
        "minPrice": float(price_filter.get("minPrice", "0")),
        "maxPrice": float(price_filter.get("maxPrice", "1e18")),
        "status": raw.get("status", ""),
        "contractType": raw.get("contractType", ""),
        "_fetched_ms": utc_now_ms(),
    }


def _refresh_exchange_filters_bulk() -> bool:
    """FIX LIVE-EXINFO-BULK (2026-05-18): Binance fapi /exchangeInfo?symbol=X returns
    WRONG default (BTC-class) filters for many small-cap perps. Verified on HANAUSDT,
    STARUSDT, RONINUSDT, AINUSDT — all reported pricePrecision=2/tickSize=0.10/maxQty=120
    via the per-symbol endpoint, but pricePrecision=7/tickSize=0.00001/maxQty=4M via the
    full-table endpoint. This bug caused L11/L13 (every signal -1111). The full-table
    endpoint returns correct data — fetch once and cache all symbols at once.
    """
    global _exchange_bulk_fetched_ms
    try:
        data = request_json(f"{FAPI_BASE}/fapi/v1/exchangeInfo", timeout=15.0)
    except Exception as e:
        log("WARN", f"bulk exchangeInfo refresh failed: {e}")
        return False
    syms = data.get("symbols") or []
    if not syms:
        log("WARN", "bulk exchangeInfo returned 0 symbols")
        return False
    count = 0
    for raw in syms:
        sym = raw.get("symbol")
        if not sym:
            continue
        _exchange_filters_cache[sym] = _parse_symbol_filters(raw)
        count += 1
    _exchange_bulk_fetched_ms = utc_now_ms()
    log("INFO", f"  ✓ bulk exchangeInfo refreshed: {count} symbols cached")
    return True


def get_exchange_filters(symbol: str) -> dict[str, Any] | None:
    """Returns cached normalized filters for `symbol`. Refreshes bulk cache hourly.
    DO NOT use /fapi/v1/exchangeInfo?symbol= — it returns BTC default filters for
    many small-cap symbols (Binance API quirk). Always go through bulk fetch.
    """
    now_ms = utc_now_ms()
    needs_refresh = (
        _exchange_bulk_fetched_ms == 0
        or (now_ms - _exchange_bulk_fetched_ms) > _EXCHANGE_TTL_MS
    )
    if needs_refresh:
        _refresh_exchange_filters_bulk()
    cached = _exchange_filters_cache.get(symbol)
    if cached:
        return cached
    # Symbol not in cache — try one targeted bulk refresh (in case it was newly listed)
    if not needs_refresh:
        _refresh_exchange_filters_bulk()
        cached = _exchange_filters_cache.get(symbol)
    if cached:
        return cached
    log("WARN", f"get_exchange_filters({symbol!r}): symbol not found in bulk exchangeInfo")
    return None


def _LEGACY_get_exchange_filters_per_symbol_DO_NOT_USE(symbol: str) -> dict[str, Any] | None:
    """KEPT FOR REFERENCE: this is the old broken path. Binance returned BTC defaults
    for small-cap symbols through this endpoint. Never call this — use get_exchange_filters."""
    cached = _exchange_filters_cache.get(symbol)
    if cached and (utc_now_ms() - cached.get("_fetched_ms", 0)) < _EXCHANGE_TTL_MS:
        return cached
    try:
        sym_enc = urllib.parse.quote(symbol, safe="")
        data = request_json(f"{FAPI_BASE}/fapi/v1/exchangeInfo?symbol={sym_enc}")
    except Exception as e:
        log("WARN", f"exchangeInfo({symbol!r}) failed: {e}")
        return cached
    syms = data.get("symbols") or []
    if not syms:
        return cached
    raw = syms[0]
    filters = {f["filterType"]: f for f in raw.get("filters", [])}
    lot = filters.get("LOT_SIZE", {})
    market_lot = filters.get("MARKET_LOT_SIZE", {})
    min_notional = filters.get("MIN_NOTIONAL", {})
    percent = filters.get("PERCENT_PRICE", {})
    price_filter = filters.get("PRICE_FILTER", {})
    out = {
        "stepSize": float(lot.get("stepSize", "0.001")),
        "minQty": float(lot.get("minQty", "0")),
        "marketMaxQty": float(market_lot.get("maxQty", "1e18")),
        "quantityPrecision": int(raw.get("quantityPrecision", 3)),
        "pricePrecision": int(raw.get("pricePrecision", 4)),
        "minNotional": float(min_notional.get("notional", "5")),
        "percentMultiplierUp": float(percent.get("multiplierUp", "5")),
        "percentMultiplierDown": float(percent.get("multiplierDown", "0.2")),
        "tickSize": float(price_filter.get("tickSize", "0")),
        "_fetched_ms": utc_now_ms(),
    }
    _exchange_filters_cache[symbol] = out
    return out


def round_qty(qty: float, step: float, min_qty: float, precision: int) -> float | None:
    if qty <= 0:
        return None
    rounded = math.floor(qty / step) * step
    rounded = round(rounded, precision)
    if rounded < min_qty:
        return None
    return rounded


def qty_for_notional(symbol: str, price: float, notional: float) -> float | None:
    """Returns the qty to trade for a given notional, respecting:
      - LOT_SIZE.stepSize (qty must be a multiple)
      - LOT_SIZE.minQty (qty floor)
      - MIN_NOTIONAL (price × qty floor)
      - LOT_SIZE.maxQty (max for LIMIT — typically huge, rarely hit)

    Does NOT reject on MARKET_LOT_SIZE.maxQty — place_market_order auto-routes to LIMIT IOC
    when the MARKET cap is exceeded (FIX LIVE-LIMIT-FALLBACK 2026-05-17).
    """
    if price <= 0:
        return None
    f = get_exchange_filters(symbol)
    if not f:
        return None
    qty = round_qty(notional / price, f["stepSize"], f["minQty"], f["quantityPrecision"])
    if qty is None or qty * price < f["minNotional"]:
        return None
    return qty


def fetch_klines_1m(symbol: str, limit: int = 200) -> list[dict[str, float]]:
    """Returns list of dicts {ot, o, h, l, c, v, ct, taker_buy_vol} for last `limit` 1m bars."""
    try:
        # FIX LIVE-URLENCODE (2026-05-16): URL-encode symbol for non-ASCII safety
        sym_enc = urllib.parse.quote(symbol, safe="")
        url = f"{FAPI_BASE}/fapi/v1/klines?symbol={sym_enc}&interval=1m&limit={limit}"
        data = request_json(url, timeout=8.0)
    except Exception as e:
        log("WARN", f"klines({symbol!r}) failed: {e}")
        return []
    out = []
    for r in data:
        # [open_time, open, high, low, close, volume, close_time, quote_volume, count, taker_buy_volume, taker_buy_quote_volume, ignore]
        out.append({
            "ot": int(r[0]),
            "o": float(r[1]),
            "h": float(r[2]),
            "l": float(r[3]),
            "c": float(r[4]),
            "v": float(r[5]),
            "ct": int(r[6]),
            "taker_buy_vol": float(r[9]),
        })
    return out


def fetch_top_movers(top_n: int = 50) -> list[dict[str, Any]]:
    try:
        data = request_json(f"{FAPI_BASE}/fapi/v1/ticker/24hr", timeout=15.0)
    except Exception as e:
        log("WARN", f"top_movers fetch failed: {e}")
        return []
    rows = [x for x in data if isinstance(x, dict) and x.get("symbol", "").endswith("USDT")]
    rows.sort(key=lambda x: abs(float(x.get("priceChangePercent", 0))), reverse=True)
    return [{"symbol": x["symbol"], "pct_24h": float(x["priceChangePercent"])} for x in rows[:top_n]]


def fetch_account_balance() -> float:
    """Returns USDT AVAILABLE balance (wallet - locked margin). Use for capital-floor
    safety checks (what's free to open new positions)."""
    try:
        data = signed_request("GET", "/fapi/v2/balance")
    except Exception as e:
        log("WARN", f"balance fetch failed: {e}")
        return 0.0
    for asset in data:
        if asset.get("asset") == "USDT":
            return float(asset.get("availableBalance", "0"))
    return 0.0


def fetch_account_equity() -> float:
    """FIX TG-EQUITY (2026-05-21): Returns USDT total EQUITY = walletBalance + unrealizedPnL.
    Use for 累计 PnL display so it stays accurate while a position is open.

    fetch_account_balance() returns availableBalance which drops by locked margin when a
    position opens, making heartbeat 累计 PnL look falsely negative (saw -$30 / -5.78%
    during TSTUSDT trade that was actually never in real loss). Equity = wallet + unrealized
    is the true mark-to-market account value.
    """
    try:
        data = signed_request("GET", "/fapi/v2/balance")
    except Exception as e:
        log("WARN", f"equity fetch failed: {e}")
        return 0.0
    for asset in data:
        if asset.get("asset") == "USDT":
            wallet = float(asset.get("balance", "0"))
            unpnl = float(asset.get("crossUnPnl", "0"))
            return wallet + unpnl
    return 0.0


def fetch_positions() -> list[dict[str, Any]]:
    """Returns list of open positions (positionAmt != 0)."""
    try:
        data = signed_request("GET", "/fapi/v2/positionRisk")
    except Exception as e:
        log("WARN", f"positionRisk fetch failed: {e}")
        return []
    out = []
    for p in data:
        amt = float(p.get("positionAmt", "0"))
        if abs(amt) < 1e-9:
            continue
        out.append({
            "symbol": p["symbol"],
            "positionAmt": amt,
            "entryPrice": float(p.get("entryPrice", "0")),
            "markPrice": float(p.get("markPrice", "0")),
            "liquidationPrice": float(p.get("liquidationPrice", "0")),
            "unRealizedProfit": float(p.get("unRealizedProfit", "0")),
            "leverage": int(p.get("leverage", "1")),
        })
    return out


def set_leverage(symbol: str, leverage: int) -> bool:
    try:
        signed_request("POST", "/fapi/v1/leverage", {"symbol": symbol, "leverage": leverage})
        return True
    except Exception as e:
        msg = str(e)
        # Already set is fine
        if "No need to change" in msg:
            return True
        log("WARN", f"set_leverage({symbol}, {leverage}) failed: {e}")
        return False


def set_margin_type(symbol: str, margin_type: str) -> bool:
    try:
        signed_request("POST", "/fapi/v1/marginType", {"symbol": symbol, "marginType": margin_type})
        return True
    except Exception as e:
        msg = str(e)
        # "No need to change margin type" returned when already set
        if "No need to change" in msg or "-4046" in msg:
            return True
        log("WARN", f"set_margin_type({symbol}, {margin_type}) failed: {e}")
        return False


def ensure_one_way_position_mode() -> bool:
    """FIX: Force One-way position mode at startup. If user is in Hedge mode,
    SELL orders without positionSide will fail with -4061.

    Returns True if set or already in One-way."""
    try:
        # GET current mode
        cur = signed_request("GET", "/fapi/v1/positionSide/dual")
        is_hedge = bool(cur.get("dualSidePosition", False))
        if not is_hedge:
            log("INFO", "position mode already One-way ✓")
            return True
        # Try to switch to One-way (requires no open positions)
        log("INFO", "switching position mode from Hedge to One-way")
        signed_request("POST", "/fapi/v1/positionSide/dual", {"dualSidePosition": "false"})
        log("INFO", "position mode set to One-way ✓")
        return True
    except Exception as e:
        msg = str(e)
        if "No need to change" in msg or "-4059" in msg:
            return True
        log("ERROR", f"failed to set One-way mode: {e}")
        return False


# FIX LIVE-LIMIT-FALLBACK (2026-05-17): Binance perp small-caps have MARKET_LOT_SIZE.maxQty=120
# (launch liquidity protection), making $100 notional unfillable as MARKET for 44/49 of our
# universe. LIMIT orders use LOT_SIZE (much higher cap, typically 9M+). We use LIMIT IOC
# (immediate-or-cancel) at an aggressive offset so behavior is "marketable limit" — fills
# instantly at the limit price or better, cancels the rest. Net: effectively MARKET execution
# with a worst-case price bound.
#
# Offset (2.0%) is generous to maximize fill probability. The existing post-fill slippage
# check in open_position enforces the tighter max_slippage_pct (default 0.3%) and emergency-
# closes if real slip exceeds — so a too-loose LIMIT can't sneak through a bad fill.
LIMIT_IOC_OFFSET_PCT = 2.0


def fetch_mark_price(symbol: str) -> float | None:
    try:
        sym_enc = urllib.parse.quote(symbol, safe="")
        data = request_json(f"{FAPI_BASE}/fapi/v1/premiumIndex?symbol={sym_enc}", timeout=5.0)
        return float(data.get("markPrice", "0")) or None
    except Exception as e:
        log("WARN", f"mark price fetch failed for {symbol}: {e}")
        return None


# FIX CHAMPION-E (2026-05-22): live OI feed for Champion_E's oi_chg_60m filter.
# Cache per symbol for 5 min (OI only updates every 5m on Binance anyway).
_oi_cache: dict[str, tuple[float, int]] = {}  # symbol -> (oi_chg_pct, fetched_ms)
_OI_TTL_MS = 5 * 60 * 1000


def fetch_oi_chg_60m(symbol: str) -> float | None:
    """% change in open interest over the last 60 min (12 × 5m bars), as-of latest.
    Uses Binance /futures/data/openInterestHist (period=5m). Returns None on failure.

    Positive = OI rising (new leveraged positions); negative = OI falling (de-leveraging).
    Champion_E shorts only when oi_chg >= -1% (OI not collapsing → not a short squeeze).
    """
    cached = _oi_cache.get(symbol)
    if cached and (utc_now_ms() - cached[1]) < _OI_TTL_MS:
        return cached[0]
    try:
        sym_enc = urllib.parse.quote(symbol, safe="")
        # limit=13 → 13 points over 5m = 60 min span (point[-1] vs point[0])
        url = f"{FAPI_BASE}/futures/data/openInterestHist?symbol={sym_enc}&period=5m&limit=13"
        data = request_json(url, timeout=6.0)
    except Exception as e:
        log("WARN", f"OI fetch failed for {symbol}: {e}")
        return None
    if not isinstance(data, list) or len(data) < 2:
        return None
    try:
        oi_now = float(data[-1]["sumOpenInterest"])
        oi_60ago = float(data[0]["sumOpenInterest"])
    except (KeyError, ValueError, TypeError):
        return None
    if oi_60ago <= 0:
        return None
    chg = (oi_now - oi_60ago) / oi_60ago * 100.0
    _oi_cache[symbol] = (chg, utc_now_ms())
    return chg


def round_price(price: float, tick_size: float, precision: int) -> float:
    """Round price down to tickSize (Binance rejects unaligned prices)."""
    if tick_size <= 0:
        return round(price, precision)
    return round(math.floor(price / tick_size) * tick_size, precision)


def _place_limit_ioc(symbol: str, side: str, qty: float, ref_price: float,
                     reduce_only: bool = False) -> dict[str, Any]:
    """LIMIT IOC at an aggressive offset (acts as marketable limit).

    For SELL (open short / close long): price = ref_price * (1 - offset) — willing to sell DOWN to here
    For BUY  (open long  / close short): price = ref_price * (1 + offset) — willing to buy UP to here

    IOC = fills what's immediately available at price or better, cancels rest.
    Caller MUST check executedQty (may be < requested qty on thin books).
    """
    f = get_exchange_filters(symbol)
    if not f:
        raise RuntimeError(f"_place_limit_ioc: no filters for {symbol}")
    qty_str = f"{qty:.{int(f['quantityPrecision'])}f}"
    if side == "SELL":
        limit_price = ref_price * (1 - LIMIT_IOC_OFFSET_PCT / 100)
    else:
        limit_price = ref_price * (1 + LIMIT_IOC_OFFSET_PCT / 100)
    limit_price = round_price(limit_price, f["tickSize"], int(f["pricePrecision"]))
    price_str = f"{limit_price:.{int(f['pricePrecision'])}f}"
    params = {
        "symbol": symbol,
        "side": side,
        "type": "LIMIT",
        "quantity": qty_str,
        "price": price_str,
        "timeInForce": "IOC",
        "newOrderRespType": "RESULT",
    }
    if reduce_only:
        params["reduceOnly"] = "true"
    log("INFO", f"  → LIMIT IOC fallback {symbol} {side} qty={qty_str} @ {price_str} (ref={ref_price:.6f}, offset={LIMIT_IOC_OFFSET_PCT}%)")
    resp = signed_request("POST", "/fapi/v1/order", params)
    status = resp.get("status", "")
    executed = float(resp.get("executedQty", "0"))
    if executed <= 0:
        raise RuntimeError(f"LIMIT IOC unfilled (status={status} qty={qty} ref={ref_price}): book too thin or price moved away — {resp}")
    if status not in ("FILLED", "PARTIALLY_FILLED"):
        raise RuntimeError(f"LIMIT IOC unexpected status={status} resp={resp}")
    return resp


def _extract_algo_id(resp: dict[str, Any]) -> int | None:
    """Pull algoId from a /fapi/v1/algoOrder response, tolerant of a {"data": {...}} envelope
    (FIX LIVE-ALGO-MIGRATION 2026-05-25 — codex review nit #1)."""
    aid = resp.get("algoId")
    if aid is None and isinstance(resp.get("data"), dict):
        aid = resp["data"].get("algoId")
    try:
        return int(aid) or None
    except (TypeError, ValueError):
        return None


def place_stop_market_safety(symbol: str, side: str, stop_price: float, qty: float = 0.0) -> int | None:
    """FIX LIVE-EXCHANGE-SL (2026-05-17 / 2026-05-19): place exchange-side STOP_MARKET that
    closes the position if mark price hits stop_price. Acts as safety net if bot crashes.

    Two-attempt strategy (FIX LIVE-SL-FALLBACK 2026-05-19):
      Attempt 1: closePosition=true (simplest, no qty math required)
      Attempt 2 (if -4120 / not supported): use quantity + reduceOnly=true instead
                Some symbols (e.g. GTCUSDT seen 2026-05-19) reject closePosition=true on
                /fapi/v1/order with -4120 "Order type not supported for this endpoint".
                Quantity + reduceOnly is the universal fallback.

    workingType=MARK_PRICE to avoid wick-based false triggers.
    Returns algoId on success, None on failure (best-effort — never blocks main flow).
    """
    f = get_exchange_filters(symbol)
    if not f:
        log("WARN", f"exchange-side SL skipped for {symbol}: no filters available")
        return None
    price_precision = int(f["pricePrecision"])
    tick_size = float(f.get("tickSize", 0) or 0)
    # Round stop_price to tickSize first (binance rejects unaligned prices with -1111)
    if tick_size > 0:
        stop_price_rounded = round(math.floor(stop_price / tick_size) * tick_size, price_precision)
    else:
        stop_price_rounded = round(stop_price, price_precision)
    stop_str = f"{stop_price_rounded:.{price_precision}f}"

    # FIX LIVE-ALGO-MIGRATION (2026-05-25): Binance moved conditional orders (STOP_MARKET /
    # TAKE_PROFIT_MARKET / etc.) to the Algo Service on 2025-12-09. They must be sent to
    # POST /fapi/v1/algoOrder with algoType=CONDITIONAL and triggerPrice (NOT stopPrice).
    # The old /fapi/v1/order path returns -4120 "use the Algo Order API endpoints instead".
    # GTE_GTC / newOrderRespType are not accepted on the algo endpoint.
    # Attempt 1: closePosition=true
    base_params = {
        "algoType": "CONDITIONAL",
        "symbol": symbol,
        "side": side,
        "type": "STOP_MARKET",
        "triggerPrice": stop_str,
        "workingType": "MARK_PRICE",
    }
    params1 = dict(base_params, closePosition="true")
    try:
        resp = signed_request("POST", "/fapi/v1/algoOrder", params1)
        oid = _extract_algo_id(resp)
        if oid:
            log("INFO", f"  ✓ exchange-side SL placed for {symbol} via closePosition: stop={stop_str} algoId={oid}")
        return oid
    except Exception as e1:
        emsg = str(e1)
        # If error is NOT -4120 (Order type not supported), it's a real error — abort
        if "-4120" not in emsg and "Order type not supported" not in emsg:
            log("WARN", f"exchange-side SL closePosition failed for {symbol}: {e1}")
            return None
        log("INFO", f"  closePosition not supported for {symbol}, trying qty+reduceOnly fallback")

    # Attempt 2: quantity + reduceOnly (no closePosition flag)
    if qty <= 0:
        log("WARN", f"exchange-side SL fallback skipped for {symbol}: qty not provided")
        return None
    qty_precision = int(f["quantityPrecision"])
    qty_str = f"{qty:.{qty_precision}f}"
    params2 = dict(base_params, quantity=qty_str, reduceOnly="true")
    try:
        resp = signed_request("POST", "/fapi/v1/algoOrder", params2)
        oid = _extract_algo_id(resp)
        if oid:
            log("INFO", f"  ✓ exchange-side SL placed for {symbol} via qty+reduceOnly: stop={stop_str} qty={qty_str} algoId={oid}")
        return oid
    except Exception as e2:
        log("WARN", f"exchange-side SL fallback also failed for {symbol} (non-fatal): {e2}")
        return None


def cancel_order_safe(symbol: str, order_id: int) -> bool:
    """Best-effort cancel. Returns True if cancelled or already gone, False on hard error."""
    try:
        signed_request("DELETE", "/fapi/v1/order", {"symbol": symbol, "orderId": order_id})
        return True
    except Exception as e:
        emsg = str(e)
        # -2011 = "Unknown order sent" (already filled/cancelled — fine)
        if "-2011" in emsg or "Unknown order" in emsg:
            return True
        log("WARN", f"cancel_order({symbol}, {order_id}) failed: {e}")
        return False


def cancel_algo_order_safe(symbol: str, algo_id: int) -> bool:
    """Best-effort cancel of an exchange-side conditional (Algo) order via
    DELETE /fapi/v1/algoOrder. FIX LIVE-ALGO-MIGRATION (2026-05-25): the exchange-side SL is
    now an Algo order (algoId), so it must be cancelled on the algo endpoint, not the old
    /fapi/v1/order. Returns True if cancelled or already gone, False on hard error."""
    try:
        signed_request("DELETE", "/fapi/v1/algoOrder", {"symbol": symbol, "algoId": algo_id})
        return True
    except Exception as e:
        emsg = str(e)
        # already filled / cancelled / not found → treat as success
        if "-2011" in emsg or "Unknown order" in emsg or "does not exist" in emsg.lower():
            return True
        log("WARN", f"cancel_algo_order({symbol}, {algo_id}) failed: {e}")
        return False


def place_market_order(symbol: str, side: str, qty: float, reduce_only: bool = False) -> dict[str, Any]:
    """side: 'BUY' or 'SELL'.

    FIX: Validates order status == FILLED or PARTIALLY_FILLED. Raises if rejected/expired.

    FIX LIVE-PRECISION-1111 (2026-05-16): format qty as string with EXACT decimal precision
    matching the symbol's quantityPrecision.

    FIX LIVE-LIMIT-FALLBACK (2026-05-17): if qty > MARKET_LOT_SIZE.maxQty, the MARKET path
    would fail with -1111. Auto-route to LIMIT IOC instead (uses LOT_SIZE, much higher cap).
    Net effect: caller sees a single "execute now at market quality" function regardless of
    symbol's small-cap restrictions.
    """
    f = get_exchange_filters(symbol)
    precision = int(f["quantityPrecision"]) if f else 3
    market_max = f.get("marketMaxQty", 1e18) if f else 1e18

    if qty > market_max:
        ref = fetch_mark_price(symbol)
        if ref is None or ref <= 0:
            raise RuntimeError(f"MARKET fallback to LIMIT failed: cannot fetch mark price for {symbol}")
        return _place_limit_ioc(symbol, side, qty, ref, reduce_only=reduce_only)

    qty_str = f"{qty:.{precision}f}"
    # Strip trailing zeros AFTER decimal point (but keep integer part), then strip dangling "."
    # e.g., "2218.0" → "2218" (when precision=0 the value is integer-valued)
    # but "0.123000" with precision=6 stays "0.123000" because we used f-string with exact width
    # Actually keep f-string output as-is — it's already exactly `precision` decimals which is
    # what Binance expects. Don't strip — strip can break precision=2 "0.10" → "0.1".
    params = {
        "symbol": symbol,
        "side": side,
        "type": "MARKET",
        "quantity": qty_str,  # str, not float
        "newOrderRespType": "RESULT",
    }
    if reduce_only:
        params["reduceOnly"] = "true"
    resp = signed_request("POST", "/fapi/v1/order", params)
    status = resp.get("status", "")
    if status not in ("FILLED", "PARTIALLY_FILLED"):
        raise RuntimeError(f"order not filled: status={status} resp={resp}")
    executed = float(resp.get("executedQty", "0"))
    if executed <= 0:
        raise RuntimeError(f"order executedQty=0 resp={resp}")
    return resp


# ─────────────────────────────────────────────────────────────────────────────
# Feature computation (from 1m klines)
# ─────────────────────────────────────────────────────────────────────────────


def compute_atr_pct(bars: list[dict[str, float]], period: int = 14) -> float:
    """Returns ATR as pct of last close."""
    if len(bars) < period + 1:
        return 0.0
    trs = []
    for i in range(1, len(bars)):
        h = bars[i]["h"]
        l = bars[i]["l"]
        prev_c = bars[i-1]["c"]
        tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
        trs.append(tr)
    if len(trs) < period:
        return 0.0
    atr_abs = sum(trs[-period:]) / period
    last_close = bars[-1]["c"]
    return (atr_abs / last_close * 100) if last_close > 0 else 0.0


def compute_rsi(bars: list[dict[str, float]], period: int = 14) -> float:
    if len(bars) < period + 1:
        return 50.0
    closes = [b["c"] for b in bars[-(period+1):]]
    gains = []
    losses = []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i-1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def compute_ret_60m(bars: list[dict[str, float]]) -> float:
    """Last close vs close 60 bars ago, in pct."""
    if len(bars) < 61:
        return 0.0
    c_now = bars[-1]["c"]
    c_60ago = bars[-61]["c"]
    return (c_now - c_60ago) / c_60ago * 100 if c_60ago > 0 else 0.0


def compute_ret_5m(bars: list[dict[str, float]]) -> float:
    if len(bars) < 6:
        return 0.0
    c_now = bars[-1]["c"]
    c_5ago = bars[-6]["c"]
    return (c_now - c_5ago) / c_5ago * 100 if c_5ago > 0 else 0.0


def compute_pullback_from_high_60m(bars: list[dict[str, float]]) -> float:
    """Pct distance from last close to highest high in last 60 bars (negative if below)."""
    if len(bars) < 60:
        return 0.0
    highs = [b["h"] for b in bars[-60:]]
    max_h = max(highs)
    c = bars[-1]["c"]
    return (c - max_h) / max_h * 100 if max_h > 0 else 0.0


def compute_vol_zscore_30(bars: list[dict[str, float]]) -> float:
    if len(bars) < 31:
        return 0.0
    vols = [b["v"] for b in bars[-31:-1]]  # last 30 excluding current
    cur_v = bars[-1]["v"]
    mean = sum(vols) / 30
    var = sum((v - mean) ** 2 for v in vols) / 30
    sd = math.sqrt(var) if var > 0 else 1.0
    return (cur_v - mean) / sd if sd > 0 else 0.0


def compute_upper_wick_pct(bar: dict[str, float]) -> float:
    """Upper wick / range. Returns 0 if no range."""
    h, l, o, c = bar["h"], bar["l"], bar["o"], bar["c"]
    body_top = max(o, c)
    wick = h - body_top
    rng = h - l
    return (wick / c) if c > 0 else 0.0  # pct of close


def compute_body_ret(bar: dict[str, float]) -> float:
    """Body close-open / open. Pct."""
    o = bar["o"]
    c = bar["c"]
    return (c - o) / o if o > 0 else 0.0


def compute_taker_buy_ratio(bars: list[dict[str, float]], window: int = 5) -> float:
    """Taker buy volume / total volume over last `window` bars."""
    if len(bars) < window:
        return 0.5
    total_buy = sum(b["taker_buy_vol"] for b in bars[-window:])
    total_vol = sum(b["v"] for b in bars[-window:])
    return total_buy / total_vol if total_vol > 0 else 0.5


# ─────────────────────────────────────────────────────────────────────────────
# Strategy evaluation
# ─────────────────────────────────────────────────────────────────────────────


def evaluate_strategy(strat: StrategyDef, bars: list[dict[str, float]], symbol: str = "") -> dict[str, Any] | None:
    """Returns signal-data dict on match, None otherwise.

    Output keys: ret60_atr, rsi, taker, uw, body, vol_zs, pullback_pct, ret5_atr, atr_pct, last_close, oi_chg

    `symbol` is needed only for strategies with an oi_chg filter (Champion_E) — the OI feed
    is fetched lazily (only after all cheap filters pass) to avoid hammering the OI API.
    """
    if len(bars) < 65:
        return None

    cur = bars[-1]
    atr_pct = compute_atr_pct(bars, 14)
    # FIX BLOCKING (audit 3 — NaN guard): catch both 0 and NaN/Inf
    if not math.isfinite(atr_pct) or atr_pct <= 0:
        return None
    # FIX BLOCKING (audit 3 — ATR cap): reject entries with extreme ATR
    # to keep SL ≥ 20% buffer from liquidation at 3x leverage
    if atr_pct > MAX_ENTRY_ATR_PCT:
        return None

    ret60_pct = compute_ret_60m(bars)
    ret60_atr = ret60_pct / atr_pct
    ret5_pct = compute_ret_5m(bars)
    ret5_atr = ret5_pct / atr_pct
    rsi = compute_rsi(bars, 14)
    taker = compute_taker_buy_ratio(bars, 5)
    uw = compute_upper_wick_pct(cur)
    body = compute_body_ret(cur)
    vol_zs = compute_vol_zscore_30(bars)
    pullback_pct = compute_pullback_from_high_60m(bars)
    pullback_frac = pullback_pct / 100  # config uses fractional (-0.03 = -3%)

    e = strat.entry
    # Check hours filter (UTC)
    if "hours_utc" in e:
        cur_hour = datetime.now(timezone.utc).hour
        if cur_hour not in e["hours_utc"]:
            return None

    # Numeric checks (short only — adapt sign for long if added later)
    if "ret60_atr_min" in e and ret60_atr < e["ret60_atr_min"]:
        return None
    # FIX CHAMPION-E (2026-05-22): ret60_atr_max upper bound — avoid the most extreme pumps
    # (those are squeeze-prone; Champion_E caps at 10). atr_pct is PERCENT in live.
    if "ret60_atr_max" in e and ret60_atr > e["ret60_atr_max"]:
        return None
    if "ret60_atr_neg_max" in e and ret60_atr > e["ret60_atr_neg_max"]:
        return None
    if "ret5_atr_neg_max" in e and ret5_atr > e["ret5_atr_neg_max"]:
        return None
    if "rsi_min" in e and rsi < e["rsi_min"]:
        return None
    if "rsi_max" in e and rsi > e["rsi_max"]:
        return None
    if "taker_max" in e and taker > e["taker_max"]:
        return None
    if "upper_wick_min" in e and uw < e["upper_wick_min"]:
        return None
    if "body_neg_max" in e and body > e["body_neg_max"]:
        return None
    if "vol_zscore_30_min" in e and vol_zs < e["vol_zscore_30_min"]:
        return None
    # FIX CHAMPION-E: vol_zs upper bound — avoid extreme volume spikes (also squeeze-prone)
    if "vol_zscore_30_max" in e and vol_zs > e["vol_zscore_30_max"]:
        return None
    # FIX CHAMPION-E: atr_pct floor (PERCENT units; e.g. 0.3 = 0.3%) — exclude dead/illiquid coins
    if "atr_pct_min" in e and atr_pct < e["atr_pct_min"]:
        return None
    if "pullback_from_high_60m_max" in e and pullback_frac > e["pullback_from_high_60m_max"]:
        return None

    # FIX CHAMPION-E: OI filter — LAST (network fetch, lazy). Only short when OI is NOT
    # falling more than the threshold (oi_chg_min, e.g. -1.0 = OI not down >1% over 60min).
    # OI rising = fresh leveraged longs crowding in → fragile crowded long to fade.
    # OI falling = shorts covering → squeeze risk → avoid.
    oi_chg = None
    if "oi_chg_min" in e:
        oi_chg = fetch_oi_chg_60m(symbol) if symbol else None
        if oi_chg is None:
            # No OI data → fail safe (don't take the trade we can't validate)
            return None
        if oi_chg < e["oi_chg_min"]:
            return None

    return {
        "ret60_atr": ret60_atr,
        "rsi": rsi,
        "taker": taker,
        "uw": uw,
        "body": body,
        "vol_zs": vol_zs,
        "pullback_pct": pullback_pct,
        "ret5_atr": ret5_atr,
        "atr_pct": atr_pct,
        "oi_chg": oi_chg,
        "last_close": cur["c"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Universe builder
# ─────────────────────────────────────────────────────────────────────────────


def load_recent_bwe_symbols(window_min: int = 30) -> set[str]:
    """Symbols mentioned in BWE jsonl in last `window_min` minutes."""
    if not BWE_LOG.exists():
        return set()
    threshold_ms = utc_now_ms() - window_min * SECONDS_PER_MIN * 1000
    syms: set[str] = set()
    try:
        # Tail-read last 5 MB max for speed
        size = BWE_LOG.stat().st_size
        with open(BWE_LOG, "rb") as f:
            if size > 5_000_000:
                f.seek(size - 5_000_000)
                f.readline()  # discard partial
            for line in f:
                try:
                    d = json.loads(line)
                    t = int(d.get("ts_ms", 0))
                    if t < threshold_ms:
                        continue
                    s = d.get("symbol", "")
                    if s and s.endswith("USDT"):
                        syms.add(s)
                except Exception:
                    continue
    except Exception as e:
        log("WARN", f"BWE log read failed: {e}")
    return syms


def build_universe(config: dict, blacklist: set[str], mainstream: set[str]) -> list[str]:
    movers = fetch_top_movers(config["universe"].get("include_top_movers_24h", 50))
    bwe_syms = load_recent_bwe_symbols(config["universe"].get("include_bwe_event_window_min", 30))
    candidates = set([m["symbol"] for m in movers]) | bwe_syms
    candidates -= mainstream
    candidates -= blacklist
    # FIX LIVE-NONASCII (2026-05-16): filter non-ASCII symbols (e.g. "我踏马来了USDT" — Chinese meme coin).
    # Non-ASCII symbol names break urllib unless URL-encoded, AND they typically signal joke/scam coins
    # that we don't want to trade anyway.
    candidates = {s for s in candidates if s.endswith("USDT") and s.isascii()}
    return sorted(candidates)


# ─────────────────────────────────────────────────────────────────────────────
# 10d uptrend filter (skip coins that pumped a lot)
# ─────────────────────────────────────────────────────────────────────────────


def compute_10d_return_pct(symbol: str) -> float:
    """Returns 10-day close-to-close return %. Uses 1h klines (cheap)."""
    try:
        # FIX LIVE-URLENCODE (2026-05-16): URL-encode symbol
        sym_enc = urllib.parse.quote(symbol, safe="")
        url = f"{FAPI_BASE}/fapi/v1/klines?symbol={sym_enc}&interval=1h&limit=240"
        data = request_json(url, timeout=8.0)
    except Exception:
        return 0.0
    if len(data) < 10:
        return 0.0
    first_close = float(data[0][4])
    last_close = float(data[-1][4])
    return (last_close - first_close) / first_close * 100 if first_close > 0 else 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Telegram notifier
# ─────────────────────────────────────────────────────────────────────────────


def telegram_send(msg: str) -> None:
    token = os.getenv("BWE_LIVE_TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("BWE_LIVE_TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        body = urllib.parse.urlencode({"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}).encode()
        req = urllib.request.Request(url, data=body)
        urllib.request.urlopen(req, timeout=10.0)
    except Exception as e:
        log("WARN", f"telegram send failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Chinese Telegram message formatters (FIX TG-ZH 2026-05-19)
# ─────────────────────────────────────────────────────────────────────────────


def tg_balance_block(misc: dict, risk: RiskState, current_balance: float | None = None) -> str:
    """Returns a 4-line block: 当前余额 / 累计 PnL / 今日 PnL / 起始资金."""
    init_bal = float(misc.get("initial_balance_usdt", 0) or 0)
    deploy_date = misc.get("deploy_date_utc", "?")
    cur_bal = float(current_balance if current_balance is not None
                    else misc.get("current_balance_cached_usdt", 0) or 0)
    cum_pnl = cur_bal - init_bal if init_bal > 0 else risk.total_pnl_usdt
    cum_pct = (cum_pnl / init_bal * 100) if init_bal > 0 else 0.0
    return (
        f"💰 <b>账户</b>\n"
        f"   当前余额: ${cur_bal:.2f}\n"
        f"   累计 PnL: {cum_pnl:+.2f} USDT  ({cum_pct:+.2f}%)\n"
        f"   今日 PnL: {risk.daily_pnl_usdt:+.2f} USDT\n"
        f"   起始资金: ${init_bal:.2f}  ({deploy_date} 部署)"
    )


def tg_strategy_stats_block(misc: dict, strategies: list) -> str:
    """Returns per-strategy W/L/PnL block."""
    stats = misc.get("strat_stats", {}) or {}
    lines = ["🎯 <b>策略累计</b> (since 部署)"]
    for s in strategies:
        sid = s.strategy_id
        st = stats.get(sid, {})
        wins = int(st.get("wins", 0))
        losses = int(st.get("losses", 0))
        pnl = float(st.get("total_pnl", 0) or 0)
        if wins + losses == 0:
            lines.append(f"   {sid}: 未触发")
        else:
            lines.append(f"   {sid}: {wins}胜 {losses}负  ·  {pnl:+.2f} USDT")
    return "\n".join(lines)


def tg_risk_remaining_block(risk: RiskState, config: dict, current_balance: float | None = None) -> str:
    """Returns the 3-line risk-limits-remaining block."""
    r = config["risk_limits"]
    daily_lim = float(r["daily_loss_limit_usdt"])
    total_lim = float(r["total_drawdown_limit_usdt"])
    min_cap = float(r["min_remaining_capital_usdt"])
    daily_safety = risk.daily_pnl_usdt - daily_lim  # daily_pnl is negative when losing
    total_safety = risk.total_pnl_usdt - total_lim
    cur_bal = float(current_balance) if current_balance is not None else 0.0
    bal_safety = cur_bal - min_cap if cur_bal > 0 else 0.0
    return (
        f"🛡️ <b>风险护栏</b>\n"
        f"   日亏限: ${daily_lim:.0f}     ·  安全余量 ${daily_safety:+.2f}\n"
        f"   总回撤限: ${total_lim:.0f}  ·  安全余量 ${total_safety:+.2f}\n"
        f"   最小余额: ${min_cap:.0f}    ·  余量 ${bal_safety:+.2f}"
    )


def tg_today_activity_block(misc: dict) -> str:
    """Returns 'today's activity' block — counters reset on daily rollover."""
    opens = int(misc.get("daily_open_count", 0))
    closes = int(misc.get("daily_close_count", 0))
    wins = int(misc.get("daily_win_count", 0))
    losses = int(misc.get("daily_loss_count", 0))
    return (
        f"📈 <b>今日活动</b>\n"
        f"   信号匹配: {misc.get('daily_signal_count', 0)}\n"
        f"   成功开仓: {opens}\n"
        f"   已平仓: {closes} (盈 {wins} / 亏 {losses})"
    )


def tg_update_strat_stats(misc: dict, strategy_id: str, realized_usdt: float) -> None:
    """Update strat_stats after a position closes. Also update daily counters."""
    stats = misc.setdefault("strat_stats", {})
    s = stats.setdefault(strategy_id, {"wins": 0, "losses": 0, "total_pnl": 0.0})
    if realized_usdt > 0:
        s["wins"] = int(s.get("wins", 0)) + 1
        misc["daily_win_count"] = int(misc.get("daily_win_count", 0)) + 1
    else:
        s["losses"] = int(s.get("losses", 0)) + 1
        misc["daily_loss_count"] = int(misc.get("daily_loss_count", 0)) + 1
    s["total_pnl"] = float(s.get("total_pnl", 0.0)) + float(realized_usdt)
    misc["daily_close_count"] = int(misc.get("daily_close_count", 0)) + 1


def tg_reset_daily_counters(misc: dict) -> None:
    """Called at UTC date rollover, after sending daily report."""
    for k in ("daily_signal_count", "daily_open_count", "daily_close_count",
              "daily_win_count", "daily_loss_count"):
        misc[k] = 0


# Hour-window descriptors for each strategy (for daily report's "下次窗口" hint)
_STRAT_LABEL_ZH = {
    "B_US_PM_PULLBACK": "美东 PM pullback (UTC 15-19, 主力)",
    "D_ASIA_LATE_CONFIRM": "晚亚洲 5重确认 (UTC 0-4)",
    "C_PULLBACK_STRICT": "深 pullback 严筛 (全天)",
}


# ─────────────────────────────────────────────────────────────────────────────
# State persistence
# ─────────────────────────────────────────────────────────────────────────────


def save_state(state_path: Path, positions: dict[str, Position], risk: RiskState,
               cooldowns: dict[tuple[str, str], int], misc: dict[str, Any]) -> None:
    payload = {
        "ts_ms": utc_now_ms(),
        "positions": {k: v.to_dict() for k, v in positions.items()},
        "risk": asdict(risk),
        "cooldowns": [{"strategy_id": s, "symbol": sym, "expires_ms": ts}
                      for (s, sym), ts in cooldowns.items()],
        "misc": misc,
    }
    tmp = state_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str))
    tmp.rename(state_path)  # atomic


def load_state(state_path: Path) -> tuple[dict[str, Position], RiskState, dict[tuple[str, str], int], dict[str, Any]]:
    if not state_path.exists():
        return {}, RiskState(), {}, {}
    try:
        data = json.loads(state_path.read_text())
    except Exception as e:
        log("WARN", f"state load failed, starting fresh: {e}")
        return {}, RiskState(), {}, {}
    positions = {}
    for sym, p in (data.get("positions") or {}).items():
        try:
            positions[sym] = Position(**p)
        except Exception as e:
            log("WARN", f"skipping malformed position {sym}: {e}")
    risk = RiskState(**(data.get("risk") or {}))
    cooldowns = {(c["strategy_id"], c["symbol"]): int(c["expires_ms"])
                 for c in (data.get("cooldowns") or [])}
    return positions, risk, cooldowns, data.get("misc") or {}


# ─────────────────────────────────────────────────────────────────────────────
# Position open / close
# ─────────────────────────────────────────────────────────────────────────────


def open_position(symbol: str, strat: StrategyDef, sig_data: dict[str, Any], config: dict,
                  events_path: Path) -> Position | None:
    # FIX PER-STRAT-NOTIONAL (2026-05-21): strategy-level notional overrides portfolio default
    notional = float(strat.notional_usdt) if getattr(strat, "notional_usdt", 0) else \
        float(config["portfolio"]["notional_per_trade_usdt"])
    leverage = int(config["portfolio"]["leverage"])
    margin_mode = config["portfolio"]["margin_mode"]
    max_slip_pct = float(config["risk_limits"]["max_slippage_pct"])

    # 1. Set leverage + margin mode (idempotent — Binance returns "No need to change" if already set)
    if not set_margin_type(symbol, margin_mode):
        log("ERROR", f"set_margin_type failed for {symbol}, aborting open")
        return None
    if not set_leverage(symbol, leverage):
        log("ERROR", f"set_leverage failed for {symbol}, aborting open")
        return None

    # 2. Compute qty
    last_close = sig_data["last_close"]
    qty = qty_for_notional(symbol, last_close, notional)
    if qty is None or qty <= 0:
        log("WARN", f"qty_for_notional({symbol}) returned None — skipping")
        return None

    # 3. Place market order (short = SELL)
    binance_side = "SELL" if strat.side == "short" else "BUY"
    retries = int(config["risk_limits"]["max_order_retries"])
    delay = float(config["risk_limits"]["order_retry_delay_sec"])
    resp = None
    for attempt in range(retries):
        try:
            resp = place_market_order(symbol, binance_side, qty, reduce_only=False)
            break
        except Exception as e:
            log("WARN", f"place_market_order attempt {attempt+1} failed for {symbol}: {e}")
            if attempt < retries - 1:
                time.sleep(delay)
    if resp is None:
        log("ERROR", f"all order retries exhausted for {symbol}")
        return None

    # 4. Verify fill + check slippage
    fill_price = float(resp.get("avgPrice", "0")) or float(resp.get("price", "0"))
    if fill_price <= 0:
        log("ERROR", f"order {symbol} returned no fill price, response: {resp}")
        return None
    slip_pct = abs(fill_price - last_close) / last_close * 100
    if slip_pct > max_slip_pct:
        log("WARN", f"{symbol} slippage {slip_pct:.2f}% > {max_slip_pct}% — closing immediately")
        # FIX: try emergency close; if close fails, we MUST track the orphan position
        # rather than return None (which would leave it untracked on the exchange).
        close_side = "BUY" if strat.side == "short" else "SELL"
        close_succeeded = False
        try:
            place_market_order(symbol, close_side, qty, reduce_only=True)
            close_succeeded = True
            log("INFO", f"slippage close OK for {symbol}")
        except Exception as e:
            log("CRITICAL", f"slippage close FAILED for {symbol}: {e} — will track as live position")
            telegram_send(
                f"⚠️ <b>{symbol} SLIPPAGE CLOSE FAILED</b>\n"
                f"slip={slip_pct:.2f}%  fill={fill_price:.6f}\n"
                f"Position is open on Binance — bot will manage it.\n"
                f"Manually verify if bot misbehaves."
            )
        log_event({
            "event": "entry_slippage" if close_succeeded else "entry_slippage_close_failed",
            "symbol": symbol,
            "strategy_id": strat.strategy_id,
            "expected_price": last_close,
            "fill_price": fill_price,
            "slip_pct": slip_pct,
            "close_succeeded": close_succeeded,
        }, events_path)
        if close_succeeded:
            return None
        # close failed — fall through to create Position object so bot tracks it

    # FIX MEDIUM-3: use actual executedQty (may differ from requested on partial fills)
    executed_qty = float(resp.get("executedQty", "0"))
    if executed_qty <= 0:
        # Defensive — place_market_order already requires executedQty > 0 to return,
        # but guard against future changes.
        executed_qty = qty
    actual_notional = executed_qty * fill_price

    # 5. Compute SL/TP prices from ATR
    atr_pct = sig_data["atr_pct"]
    atr_abs = fill_price * atr_pct / 100  # ATR in price units
    exit_cfg = strat.exit

    if strat.side == "short":
        sl_price = fill_price + exit_cfg["sl_atr"] * atr_abs  # SL higher (loss)
        if exit_cfg["type"] == "time_decay":
            tp_init = fill_price - exit_cfg["tp_init_atr"] * atr_abs  # TP lower (profit)
            tp_final = fill_price - exit_cfg["tp_final_atr"] * atr_abs
        else:
            tp_init = fill_price - exit_cfg["tp_atr"] * atr_abs
            tp_final = tp_init
    else:  # long
        sl_price = fill_price - exit_cfg["sl_atr"] * atr_abs
        if exit_cfg["type"] == "time_decay":
            tp_init = fill_price + exit_cfg["tp_init_atr"] * atr_abs
            tp_final = fill_price + exit_cfg["tp_final_atr"] * atr_abs
        else:
            tp_init = fill_price + exit_cfg["tp_atr"] * atr_abs
            tp_final = tp_init

    # FIX LIVE-EXCHANGE-SL (2026-05-17): place exchange-side STOP_MARKET safety net.
    # If bot dies / network hangs between polls, this fires at sl_price (MARK_PRICE basis).
    # Bot's own poll-based SL still primary (faster reaction + uses bar high not mark).
    close_side = "BUY" if strat.side == "short" else "SELL"
    exchange_sl_id = place_stop_market_safety(symbol, close_side, sl_price, qty=executed_qty)

    pos = Position(
        symbol=symbol,
        strategy_id=strat.strategy_id,
        side=strat.side,
        qty=executed_qty,            # FIX MEDIUM-3: use actual fill qty
        notional_usdt=actual_notional,  # FIX MEDIUM-3: use actual notional from fill
        leverage=leverage,
        entry_price=fill_price,
        entry_ts_ms=utc_now_ms(),
        atr_at_entry=atr_abs,
        sl_price=sl_price,
        tp_init_price=tp_init,
        tp_final_price=tp_final,
        exit_type=exit_cfg["type"],
        time_stop_min=float(exit_cfg["time_stop_min"]),
        tp_confirm_bars=int(exit_cfg.get("tp_confirm_bars", 1)),
        binance_order_id=int(resp.get("orderId", 0)) or None,
        exchange_sl_order_id=exchange_sl_id,
    )

    log("INFO", f"OPEN {symbol} {strat.side.upper()} qty={executed_qty} entry={fill_price:.6f} "
                f"SL={sl_price:.6f} TP_init={tp_init:.6f} TP_final={tp_final:.6f} "
                f"notional={actual_notional:.2f} strategy={strat.strategy_id} "
                f"exchange_sl_oid={exchange_sl_id}")
    log_event({
        "event": "position_opened",
        "symbol": symbol,
        "strategy_id": strat.strategy_id,
        "requested_qty": qty,
        "executed_qty": executed_qty,
        "notional_actual": actual_notional,
        "entry_price": fill_price,
        "sl_price": sl_price,
        "tp_init_price": tp_init,
        "tp_final_price": tp_final,
        "atr_pct": atr_pct,
        "signal": sig_data,
        "binance_response": resp,
    }, events_path)
    # FIX TG-ZH (2026-05-19): Chinese entry message with 4-filter check
    side_zh = "做空" if strat.side == "short" else "做多"
    leverage_used = int(config["portfolio"]["leverage"])
    notional_actual_str = f"${actual_notional:.2f}"
    # Compute pct distances for SL/TP relative to entry
    if strat.side == "short":
        sl_pct = (sl_price - fill_price) / fill_price * 100  # positive (反向)
        tp_pct = (tp_init - fill_price) / fill_price * 100  # negative (顺向)
    else:
        sl_pct = (fill_price - sl_price) / fill_price * 100
        tp_pct = (tp_init - fill_price) / fill_price * 100
    # Filter check box — show the 4 strict filters with actual vs threshold
    entry_cfg = strat.entry
    sig_lines = []
    if "ret60_atr_min" in entry_cfg:
        ok = "✓" if sig_data.get("ret60_atr", 0) >= float(entry_cfg["ret60_atr_min"]) else "✗"
        sig_lines.append(f"   60分钟涨幅: {sig_data.get('ret60_atr', 0):.1f} ATR  ≥ {entry_cfg['ret60_atr_min']}  {ok}")
    if "rsi_min" in entry_cfg:
        ok = "✓" if sig_data.get("rsi", 0) >= float(entry_cfg["rsi_min"]) else "✗"
        sig_lines.append(f"   RSI: {sig_data.get('rsi', 0):.1f}           ≥ {entry_cfg['rsi_min']}   {ok}")
    if "vol_zscore_30_min" in entry_cfg:
        ok = "✓" if sig_data.get("vol_zs", 0) >= float(entry_cfg["vol_zscore_30_min"]) else "✗"
        sig_lines.append(f"   成交量异常: {sig_data.get('vol_zs', 0):.1f}σ      ≥ {entry_cfg['vol_zscore_30_min']}  {ok}")
    if "pullback_from_high_60m_max" in entry_cfg:
        thresh = float(entry_cfg["pullback_from_high_60m_max"]) * 100  # convert -0.02 → -2.0
        actual = sig_data.get("pullback_pct", 0)
        ok = "✓" if actual <= thresh else "✗"
        sig_lines.append(f"   回撤: {actual:.1f}%         ≤ {thresh:.1f}  {ok}")
    time_stop_min = int(exit_cfg.get("time_stop_min", 240))
    actual_margin = actual_notional / leverage_used

    telegram_send(
        f"🔴 <b>BWE 实盘 · 开仓</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📍 <b>{html.escape(symbol)}</b>  {side_zh}\n"
        f"   策略: {html.escape(strat.strategy_id)}\n"
        f"   仓位: {notional_actual_str}  ·  {leverage_used}x 杠杆 (实际押 ${actual_margin:.2f})\n"
        f"   入场: ${fill_price:.6f}\n"
        f"\n"
        f"🎯 <b>止损/止盈</b>\n"
        f"   止损: ${sl_price:.6f}  ({sl_pct:+.2f}%)\n"
        f"   止盈: ${tp_init:.6f}  ({tp_pct:+.2f}%)\n"
        f"   最长持仓: {time_stop_min} 分钟\n"
        f"\n"
        f"📊 <b>触发信号</b>\n"
        + "\n".join(sig_lines)
        + f"\n\n⏰ {utc_now_iso()}"
    )
    return pos


BINANCE_TAKER_FEE_RATE = 0.0004  # 0.04% per side for futures taker — applied both entry+exit

# FIX BLOCKING (audit 3 — ATR cap): reject entries when 1m ATR is extreme.
# At 3x leverage, liquidation ≈ 33% adverse. If ATR=5% then SL=2.5×5%=12.5% adverse.
# FIX RISK-SCALE (2026-05-21): with B at $300 notional, lower default cap to 3% so the
# worst-case single SL = 2.5 × 3% × $300 = $22.5 (was $37.5 at 5%). Overridable via
# config risk_limits.max_entry_atr_pct (set at startup in main()).
MAX_ENTRY_ATR_PCT = 3.0


def position_is_flat(symbol: str) -> bool | None:
    """Authoritative: True if Binance reports zero NET position for `symbol`, False if any
    non-zero exposure, None if unknown (API error / malformed / symbol absent — caller must
    stay conservative and NOT reconcile). Aggregates ALL rows (handles one-way BOTH and any
    hedge LONG/SHORT split) so a leading zero row can't mask live exposure.
    FIX LIVE-RECONCILE (2026-05-26)."""
    try:
        data = signed_request("GET", "/fapi/v2/positionRisk", {"symbol": symbol})
        rows = [p for p in data if isinstance(p, dict) and p.get("symbol") == symbol]
        if not rows:
            return None  # symbol absent from response → unknown, do not reconcile
        total = sum(abs(float(p.get("positionAmt", "0") or 0)) for p in rows)
        return total < 1e-9
    except Exception as e:
        log("WARN", f"positionRisk({symbol}) check failed: {e}")
        return None


def fetch_exit_fill_price(symbol: str, since_ms: int, close_side: str) -> float | None:
    """Qty-weighted avg fill price of close-side userTrades since entry — used to reconcile a
    position closed on the exchange (e.g. by the Algo SL) when our reduceOnly close hits -2022.
    Returns None if unavailable. FIX LIVE-RECONCILE (2026-05-26)."""
    try:
        trades = signed_request("GET", "/fapi/v1/userTrades",
                                {"symbol": symbol, "startTime": int(since_ms), "limit": 1000})
    except Exception as e:
        log("WARN", f"userTrades({symbol}) fetch failed: {e}")
        return None
    tot_qty = 0.0
    tot_quote = 0.0
    for t in trades or []:
        try:
            if str(t.get("side", "")).upper() != close_side:
                continue
            q = float(t.get("qty", 0) or 0)
            px = float(t.get("price", 0) or 0)
        except (TypeError, ValueError):
            continue
        tot_qty += q
        tot_quote += q * px
    return (tot_quote / tot_qty) if tot_qty > 0 else None


def close_position(pos: Position, reason: str, current_price: float, events_path: Path,
                   risk: RiskState, misc: dict | None = None) -> bool:
    """Close a position via market order. Returns True iff close confirmed FILLED.

    CRITICAL: caller MUST check return value before removing position from state.
    If returns False, position is still open on Binance — leave it in state for retry.
    """
    # FIX LIVE-SL-WINDOW (2026-05-26): do NOT cancel the exchange-side Algo stop here. Cancelling
    # before the close is confirmed would leave the position unprotected if the close fails.
    # The stop is now cancelled only AFTER a confirmed FULL close (see below); on a failed or
    # partial close the stop stays in place. closePosition stops also auto-cancel on full close,
    # so a brief overlap is harmless (both sides are reduce/close-only — cannot flip the position).
    close_side = "BUY" if pos.side == "short" else "SELL"
    resp = None
    reconciled_external = False
    for attempt in range(3):
        try:
            resp = place_market_order(pos.symbol, close_side, pos.qty, reduce_only=True)
            break
        except Exception as e:
            emsg = str(e)
            # FIX LIVE-RECONCILE (2026-05-26): -2022 ReduceOnly-rejected can mean the position
            # was ALREADY closed on the exchange (e.g. the exchange-side Algo SL triggered
            # between our polls). Verify the real position; if confirmed flat, reconcile with a
            # synthetic fill (so the normal PnL/event/stats path runs) and stop retrying. Only
            # reconcile on a DEFINITIVE flat — None (API error) falls through to normal retry.
            if ("-2022" in emsg or "ReduceOnly Order is rejected" in emsg) \
                    and position_is_flat(pos.symbol) is True:
                exit_px = fetch_exit_fill_price(pos.symbol, pos.entry_ts_ms, close_side) or pos.sl_price
                log("INFO", f"  {pos.symbol} already flat on exchange (-2022) → reconciling "
                            f"external close @ {exit_px:.6f}")
                resp = {"avgPrice": f"{exit_px}", "executedQty": f"{pos.qty}",
                        "status": "FILLED", "symbol": pos.symbol, "side": close_side,
                        "type": "RECONCILED", "origType": "EXTERNAL_CLOSE",
                        "_reconciled_external": True}
                reconciled_external = True
                break
            log("WARN", f"close attempt {attempt+1} failed for {pos.symbol}: {e}")
            time.sleep(2)
    if resp is None:
        log("ERROR", f"FAILED TO CLOSE {pos.symbol} — bot will retry next poll cycle")
        telegram_send(
            f"⚠️ <b>FAILED TO CLOSE</b> {html.escape(pos.symbol)} after 3 retries\n"
            f"Bot will retry next poll. If urgent, run emergency_halt manually.")
        return False
    if reconciled_external:
        reason = f"{reason}/exchange_close_reconciled"

    fill_price = float(resp.get("avgPrice", "0")) or current_price
    # FIX BLOCKING (audit 3 — partial close): use ACTUAL filled qty, not pos.qty.
    # If Binance PARTIALLY_FILLED on close, only part is closed; remainder still open.
    filled_qty = float(resp.get("executedQty", "0"))
    if filled_qty <= 0:
        # Defensive: shouldn't happen (place_market_order requires executedQty > 0)
        log("CRITICAL", f"close {pos.symbol}: response reports 0 filled — keeping in state")
        return False
    PARTIAL_TOL = 0.999  # 0.1% tolerance for floating-point dust
    is_partial = filled_qty < pos.qty * PARTIAL_TOL

    # PnL on the filled portion ONLY
    if pos.side == "short":
        ret_pct = (pos.entry_price - fill_price) / pos.entry_price
    else:
        ret_pct = (fill_price - pos.entry_price) / pos.entry_price
    filled_notional = filled_qty * pos.entry_price  # face value of the closed portion
    gross_usdt = ret_pct * filled_notional
    # Fees: entry fee pro-rata + exit fee on filled portion
    fee_entry_prorata = BINANCE_TAKER_FEE_RATE * filled_notional
    fee_exit = BINANCE_TAKER_FEE_RATE * filled_qty * fill_price
    fees_usdt = fee_entry_prorata + fee_exit
    realized_usdt = gross_usdt - fees_usdt
    duration_min = (utc_now_ms() - pos.entry_ts_ms) / 1000 / 60

    risk.daily_pnl_usdt += realized_usdt
    risk.total_pnl_usdt += realized_usdt

    emoji = "✅" if realized_usdt > 0 else "❌"
    partial_tag = " [PARTIAL]" if is_partial else ""
    log("INFO", f"CLOSE{partial_tag} {pos.symbol} reason={reason} fill={fill_price:.6f} "
                f"filled={filled_qty}/{pos.qty} ret={ret_pct*100:+.2f}% "
                f"gross={gross_usdt:+.2f} fee={fees_usdt:.2f} net={realized_usdt:+.2f}USDT "
                f"duration={duration_min:.1f}min")
    log_event({
        "event": "position_partial_close" if is_partial else "position_closed",
        "symbol": pos.symbol,
        "strategy_id": pos.strategy_id,
        "reason": reason,
        "entry_price": pos.entry_price,
        "exit_price": fill_price,
        "requested_qty": pos.qty,
        "filled_qty": filled_qty,
        "is_partial": is_partial,
        "ret_pct": ret_pct * 100,
        "gross_usdt": gross_usdt,
        "fees_usdt": fees_usdt,
        "realized_usdt": realized_usdt,
        "duration_min": duration_min,
        "binance_response": resp,
    }, events_path)

    if is_partial:
        # Partial close → record realized PnL on filled portion, update pos for remainder,
        # KEEP in state so monitor retries next poll cycle.
        remainder = pos.qty - filled_qty
        log("CRITICAL",
            f"{pos.symbol} PARTIAL CLOSE: only {filled_qty}/{pos.qty} filled "
            f"({100*filled_qty/pos.qty:.1f}%); residual {remainder} REMAINS — retrying next poll")
        telegram_send(
            f"⚠️ <b>PARTIAL CLOSE</b> {html.escape(pos.symbol)}\n"
            f"filled {filled_qty}/{pos.qty} ({100*filled_qty/pos.qty:.1f}%)\n"
            f"PnL on filled portion: {realized_usdt:+.2f} USDT\n"
            f"residual {remainder} open — bot retries automatically next poll"
        )
        pos.qty = remainder
        pos.notional_usdt = remainder * pos.entry_price
        return False  # KEEP IN STATE — caller MUST NOT pop

    # FIX LIVE-SL-WINDOW (2026-05-26): full close confirmed → now safe to cancel the exchange-side
    # Algo stop (kept until now so a failed/partial close stayed protected). Always attempt it:
    # cancel_algo_order_safe is idempotent (no-op if the stop already fired/closed us), and if the
    # flat state came from any OTHER external/manual close the stored stop must not be orphaned.
    if pos.exchange_sl_order_id:
        cancel_algo_order_safe(pos.symbol, pos.exchange_sl_order_id)

    # FIX TG-ZH (2026-05-19): Full close — Chinese formatted message with balance change.
    # Update strat_stats + daily counters before composing the message so balance line
    # reflects post-close state.
    if misc is not None:
        tg_update_strat_stats(misc, pos.strategy_id, realized_usdt)
    # Compute slippage vs exit target (TP price)
    if pos.side == "short":
        slip_vs_tp_pct = (pos.tp_init_price - fill_price) / pos.entry_price * 100
    else:
        slip_vs_tp_pct = (fill_price - pos.tp_init_price) / pos.entry_price * 100
    slip_direction = "有利" if slip_vs_tp_pct > 0 else ("不利" if slip_vs_tp_pct < 0 else "无")
    # Map reason to Chinese
    reason_zh_map = {
        "take_profit": "止盈 (take_profit)",
        "stop_loss": "止损 (stop_loss)",
        "time_stop": "时间停止 (time_stop)",
        "liquidation_safety": "强平防护",
        "kill_switch": "紧急停止 (kill switch)",
    }
    reason_zh = reason_zh_map.get(reason, reason)
    title_emoji = "✅" if realized_usdt > 0 else "❌"
    title_status = "盈利" if realized_usdt > 0 else "亏损"
    side_zh = "做空" if pos.side == "short" else "做多"

    # Balance — use latest fetched if available, else compute from init + total_pnl
    init_bal = float((misc or {}).get("initial_balance_usdt", 0) or 0)
    new_bal = init_bal + risk.total_pnl_usdt if init_bal > 0 else 0.0
    old_bal = new_bal - realized_usdt
    cum_pct = (risk.total_pnl_usdt / init_bal * 100) if init_bal > 0 else 0.0

    telegram_send(
        f"{title_emoji} <b>BWE 实盘 · 平仓 ({title_status})</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📍 <b>{html.escape(pos.symbol)}</b>  {side_zh} ➜ 已平\n"
        f"   策略: {html.escape(pos.strategy_id)}\n"
        f"   平仓原因: {reason_zh}\n"
        f"\n"
        f"💵 <b>本笔收益</b>\n"
        f"   毛利: {gross_usdt:+.2f} USDT\n"
        f"   手续费: -{fees_usdt:.2f} USDT\n"
        f"   净利: {realized_usdt:+.2f} USDT  ({ret_pct*100:+.2f}%)\n"
        f"   持仓: {duration_min:.1f} 分钟\n"
        f"\n"
        f"📊 <b>价格</b>\n"
        f"   入场: ${pos.entry_price:.6f}\n"
        f"   平仓: ${fill_price:.6f}\n"
        f"   滑点: {abs(slip_vs_tp_pct):.2f}%  {slip_direction}\n"
        f"\n"
        f"💰 <b>账户余额</b>\n"
        f"   ${old_bal:.2f}  ➜  ${new_bal:.2f}\n"
        f"   累计 PnL: {risk.total_pnl_usdt:+.2f} USDT  ({cum_pct:+.2f}%)\n"
        f"\n"
        f"⏰ {utc_now_iso()}"
    )
    return True


def force_close_all(positions: dict[str, Position], reason: str, events_path: Path,
                    risk: RiskState, misc: dict | None = None) -> None:
    if not positions:
        return
    log("CRITICAL", f"force-closing {len(positions)} positions: {reason}")
    telegram_send(f"🚨 <b>FORCE CLOSE ALL</b>\nreason: {html.escape(reason)}\npositions: {len(positions)}")
    failed = []
    for sym, pos in list(positions.items()):
        # Use last known mark price as estimate
        try:
            bars = fetch_klines_1m(sym, limit=2)
            cur_price = bars[-1]["c"] if bars else pos.entry_price
        except Exception:
            cur_price = pos.entry_price
        # FIX: only pop on confirmed close success — never drop unclosed position from state
        if close_position(pos, f"force_close:{reason}", cur_price, events_path, risk, misc):
            positions.pop(sym, None)
        else:
            failed.append(sym)
    if failed:
        log("CRITICAL", f"force_close failed for: {failed} — staying in state for retry")
        telegram_send(
            f"🚨 <b>FORCE CLOSE FAILED</b>\n"
            f"These positions could NOT be closed: {failed}\n"
            f"They remain in state.json; bot will retry next poll.")


# ─────────────────────────────────────────────────────────────────────────────
# Position state machine (monitor SL/TP/time_stop)
# ─────────────────────────────────────────────────────────────────────────────


def monitor_position(pos: Position, bars: list[dict[str, float]], events_path: Path,
                     risk: RiskState) -> str | None:
    """Returns close reason if position should exit, else None.
    Also mutates pos.confirm_counter."""
    if not bars:
        return None
    cur = bars[-1]
    cur_close = cur["c"]
    now_ms = utc_now_ms()

    # 1. SL check (use bar high for shorts — worst case)
    if pos.side == "short":
        if cur["h"] >= pos.sl_price:
            return "stop_loss"
    else:
        if cur["l"] <= pos.sl_price:
            return "stop_loss"

    # 2. Time stop
    elapsed_min = (now_ms - pos.entry_ts_ms) / 1000 / 60
    if elapsed_min >= pos.time_stop_min:
        return "time_stop"

    # 3. TP check with confirm_bars
    tp = pos.current_tp_price(now_ms)
    if pos.side == "short":
        at_tp = cur_close <= tp
    else:
        at_tp = cur_close >= tp

    if at_tp:
        # FIX: only count if this is a NEW 1m bar (not just a new poll within same bar)
        cur_ot = int(cur["ot"])
        if cur_ot != pos.last_confirm_bar_ot:
            pos.confirm_counter += 1
            pos.last_confirm_bar_ot = cur_ot
        if pos.confirm_counter >= pos.tp_confirm_bars:
            return "take_profit"
    else:
        pos.confirm_counter = 0
        pos.last_confirm_bar_ot = 0

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Risk checks
# ─────────────────────────────────────────────────────────────────────────────


def check_kill_switch(config: dict) -> bool:
    path = Path(config["kill_switch"]["file_path"])
    return path.exists()


def check_circuit_breakers(risk: RiskState, config: dict) -> str | None:
    daily_limit = config["risk_limits"]["daily_loss_limit_usdt"]
    total_limit = config["risk_limits"]["total_drawdown_limit_usdt"]
    if risk.daily_pnl_usdt <= daily_limit:
        return f"daily_loss_limit ({risk.daily_pnl_usdt:.2f} <= {daily_limit})"
    if risk.total_pnl_usdt <= total_limit:
        return f"total_drawdown_limit ({risk.total_pnl_usdt:.2f} <= {total_limit})"
    return None


def check_liquidation_safety(pos: Position, mark_price: float, liq_price: float,
                              safety_pct: float) -> bool:
    """Returns True if dangerously close to liquidation."""
    if liq_price <= 0:
        return False
    if pos.side == "short":
        # short liquidates when price RISES to liq_price
        distance_pct = (liq_price - mark_price) / mark_price * 100
    else:
        distance_pct = (mark_price - liq_price) / mark_price * 100
    return distance_pct < safety_pct


# ─────────────────────────────────────────────────────────────────────────────
# Signal handlers
# ─────────────────────────────────────────────────────────────────────────────


def handle_signal(signum: int, frame) -> None:
    global RUNNING, SHUTDOWN_REASON
    RUNNING = False
    SHUTDOWN_REASON = f"signal_{signum}"
    log("INFO", f"received signal {signum}, will shutdown cleanly")


# ─────────────────────────────────────────────────────────────────────────────
# Preflight (FIX LIVE-PREFLIGHT 2026-05-17)
# Audit gap: 3 code-review passes never exercised real exchange API against real
# universe → L6/L7/L11 all surfaced post-deploy. Preflight closes the gap by
# fetching exchangeInfo for the current universe and validating tradability
# BEFORE the scanner runs, so structurally unfillable symbols are skipped on
# startup rather than at signal time.
# ─────────────────────────────────────────────────────────────────────────────


def fetch_server_time_ms() -> int | None:
    """Returns Binance fapi server time in ms, or None on failure."""
    try:
        data = request_json(f"{FAPI_BASE}/fapi/v1/time", timeout=5.0)
        return int(data.get("serverTime", 0)) or None
    except Exception as e:
        log("WARN", f"server time fetch failed: {e}")
        return None


def run_preflight(config: dict, state_dir: Path) -> dict[str, Any]:
    """Pre-deploy / pre-startup smoke test against the real Binance API.

    Checks:
      1. Server time drift vs local (>2000ms = fail)
      2. API key signed call (/fapi/v2/balance returns)
      3. Position mode = One-way
      4. For each top-50 universe symbol: fetch exchangeInfo,
         check if notional_per_trade is tradable given LOT_SIZE, MARKET_LOT_SIZE,
         MIN_NOTIONAL, PERCENT_PRICE. Mark unitradable symbols.

    Writes report to state_dir/universe_tradability.json.
    Returns dict with {ok: bool, unitradable: set[str], fatal: str|None, ...}
    """
    report: dict[str, Any] = {
        "ts_utc": utc_now_iso(),
        "ok": True,
        "fatal": None,
        "checks": {},
        "unitradable": [],
        "per_symbol": {},
    }
    # FIX PER-STRAT-NOTIONAL (2026-05-21): check tradability at the MAX notional any strategy
    # uses, so a $300 strategy doesn't get a symbol falsely marked tradable based on $100.
    portfolio_notional = float(config["portfolio"]["notional_per_trade_usdt"])
    strat_notionals = [float(s.get("notional_usdt", 0) or 0) for s in config.get("strategies", [])]
    notional = max([portfolio_notional] + strat_notionals)

    # 1. Server time sync
    log("INFO", "[preflight] checking server time sync...")
    srv_ms = fetch_server_time_ms()
    local_ms = utc_now_ms()
    if srv_ms is None:
        report["fatal"] = "cannot fetch server time"
        report["ok"] = False
        report["checks"]["server_time"] = "FAIL: no response"
    else:
        drift = abs(srv_ms - local_ms)
        report["checks"]["server_time"] = {"drift_ms": drift, "ok": drift <= 2000}
        if drift > 2000:
            report["fatal"] = f"server time drift {drift}ms > 2000ms (would break signed requests)"
            report["ok"] = False
        log("INFO", f"[preflight] server time drift: {drift}ms (ok if ≤2000)")

    if not report["ok"]:
        return report

    # 2. Signed call (/fapi/v2/balance) — verifies API key + secret + IP whitelist
    log("INFO", "[preflight] verifying signed API access...")
    try:
        bal = fetch_account_balance()
        report["checks"]["signed_balance"] = {"usdt": bal, "ok": bal > 0}
        log("INFO", f"[preflight] signed balance OK: {bal:.2f} USDT")
    except Exception as e:
        report["fatal"] = f"signed balance failed: {e}"
        report["ok"] = False
        return report

    # 3. Position mode
    log("INFO", "[preflight] verifying One-way position mode...")
    if not ensure_one_way_position_mode():
        report["fatal"] = "could not set One-way position mode"
        report["ok"] = False
        return report
    report["checks"]["position_mode"] = "One-way ✓"

    # 4. Build universe + per-symbol tradability scan
    log("INFO", "[preflight] scanning universe tradability...")
    mainstream = set(config["universe"]["exclude_mainstream"])
    blacklist = set(config["universe"]["explicit_blacklist"])
    universe = build_universe(config, blacklist, mainstream)
    log("INFO", f"[preflight] universe size: {len(universe)} symbols")

    unitradable: list[str] = []
    for sym in universe:
        try:
            f = get_exchange_filters(sym)
            if not f:
                unitradable.append(sym)
                report["per_symbol"][sym] = {"ok": False, "reason": "no exchangeInfo"}
                continue
            # Use last_close estimate from a 1-bar fetch
            bars = fetch_klines_1m(sym, limit=2)
            if not bars:
                report["per_symbol"][sym] = {"ok": True, "reason": "skipped (no klines)"}
                continue
            price = bars[-1]["c"]
            qty_target = notional / price
            step = f["stepSize"]
            min_qty = f["minQty"]
            market_max = f.get("marketMaxQty", 1e18)
            min_notional_fil = f["minNotional"]
            # Calculate min_tradable_notional (qty=max(min_qty, ceil(min_notional/price/step)*step) * price)
            min_qty_by_notional = math.ceil(min_notional_fil / price / step) * step if step > 0 else min_qty
            effective_min_qty = max(min_qty, min_qty_by_notional)
            min_tradable_notional = effective_min_qty * price
            max_tradable_notional = market_max * price
            entry = {
                "price": price,
                "qty_target": round(qty_target, 6),
                "step": step,
                "min_qty": min_qty,
                "market_max_qty": market_max,
                "min_notional_filter": min_notional_fil,
                "min_tradable_notional": round(min_tradable_notional, 4),
                "max_tradable_notional_market": round(max_tradable_notional, 4),
                "notional_target": notional,
                "percent_mult_up": f.get("percentMultiplierUp", 5),
                "percent_mult_down": f.get("percentMultiplierDown", 0.2),
                "tick_size": f.get("tickSize", 0),
                "price_precision": f.get("pricePrecision", 4),
                "ok": True,
                "via": "MARKET",
                "reason": "",
            }
            # FIX LIVE-LIMIT-FALLBACK (2026-05-17): if MARKET cap exceeded, mark via=LIMIT
            # — order will route through LIMIT IOC which uses LOT_SIZE (no marketMaxQty cap).
            if notional < min_tradable_notional:
                entry["ok"] = False
                entry["reason"] = f"notional ${notional} < min tradable ${min_tradable_notional:.2f}"
                unitradable.append(sym)
            elif notional > max_tradable_notional:
                # LIMIT path will handle this — still tradable, just routed differently
                entry["via"] = "LIMIT_IOC"
                entry["reason"] = (f"MARKET cap exceeded (${max_tradable_notional:.2f}), "
                                   f"will route via LIMIT IOC")
            report["per_symbol"][sym] = entry
        except Exception as e:
            report["per_symbol"][sym] = {"ok": False, "reason": f"exception: {e}"}
            unitradable.append(sym)

    report["unitradable"] = sorted(set(unitradable))
    report["universe_size"] = len(universe)
    report["tradable_count"] = len(universe) - len(set(unitradable))
    report["unitradable_count"] = len(set(unitradable))

    # Write report
    report_path = state_dir / "universe_tradability.json"
    report_path.write_text(json.dumps(report, indent=2, default=str))
    log("INFO", f"[preflight] report written: {report_path}")
    log("INFO", f"[preflight] tradable: {report['tradable_count']}/{len(universe)}, "
                f"unitradable: {report['unitradable_count']}")
    if unitradable:
        log("WARN", f"[preflight] unitradable symbols: {sorted(set(unitradable))[:20]}"
                    f"{' …' if len(set(unitradable)) > 20 else ''}")

    return report


# ─────────────────────────────────────────────────────────────────────────────
# Main loop
# ─────────────────────────────────────────────────────────────────────────────


def main(args: argparse.Namespace) -> int:
    # Load config
    config = json.loads(args.config.read_text())
    state_dir: Path = args.state_dir
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / "state.json"
    events_path = state_dir / "events.jsonl"
    log_path = state_dir / "live_runner.log"

    init_logging(log_path)
    log("INFO", f"=== BWE Live Top-3 starting (config={args.config}, state={state_dir}) ===")
    log("INFO", f"  dry_run={args.dry_run}, telegram={args.telegram}")

    # Load secrets
    load_secrets(args.secrets)

    # Validate config
    portfolio = config["portfolio"]
    risk_limits = config["risk_limits"]
    # FIX RISK-SCALE (2026-05-21): allow config to override the ATR cap module global
    global MAX_ENTRY_ATR_PCT
    if "max_entry_atr_pct" in risk_limits:
        MAX_ENTRY_ATR_PCT = float(risk_limits["max_entry_atr_pct"])
        log("INFO", f"  MAX_ENTRY_ATR_PCT set from config: {MAX_ENTRY_ATR_PCT}%")
    # FIX LIVE-DATACLASS (2026-05-16): config may contain audit_* metadata fields that
    # StrategyDef doesn't accept. Filter to known dataclass fields to silently ignore extras.
    _strat_fields = {f.name for f in dataclasses.fields(StrategyDef)}
    strategies = [
        StrategyDef(**{k: v for k, v in s.items() if k in _strat_fields})
        for s in config["strategies"]
    ]
    mainstream = set(config["universe"]["exclude_mainstream"])
    blacklist = set(config["universe"]["explicit_blacklist"])
    log("INFO", f"  strategies: {[s.strategy_id for s in strategies]}")
    log("INFO", f"  blacklist: {sorted(blacklist)}")

    # Signal handlers
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    # FIX BLOCKING (audit 3 — process lock): exclusive lock prevents double-instance race
    # where two runners both load empty state and both open positions on the same symbol.
    lock_path = state_dir / "live_runner.lock"
    lock_file = open(lock_path, "w")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log("FATAL", f"another live_runner instance already holds {lock_path} — exiting")
        return 2
    lock_file.write(f"{os.getpid()}\n")
    lock_file.flush()
    # Keep lock_file open for lifetime of process — lock released on exit

    # Load state
    positions, risk, cooldowns, misc = load_state(state_path)
    if positions:
        log("INFO", f"  restored {len(positions)} positions from state: {list(positions.keys())}")
    else:
        log("INFO", f"  no prior positions to restore")

    # Connect & verify account
    if not args.dry_run:
        try:
            balance = fetch_account_balance()
            log("INFO", f"  account USDT balance: {balance:.2f}")
            min_cap = risk_limits["min_remaining_capital_usdt"]
            if balance < min_cap:
                log("FATAL", f"balance {balance:.2f} < min_remaining_capital {min_cap}, aborting")
                return 2
        except Exception as e:
            log("FATAL", f"can't fetch balance: {e}")
            return 2

        # FIX: ensure One-way position mode (Hedge mode would break SELL orders)
        if not ensure_one_way_position_mode():
            log("FATAL", "could not set One-way position mode, aborting")
            return 2

        # Sync open positions with account (in case state.json drifted from reality)
        try:
            real_positions = fetch_positions()
            real_syms = {p["symbol"] for p in real_positions}
            state_syms = set(positions.keys())
            missing_in_account = state_syms - real_syms
            extra_in_account = real_syms - state_syms
            if missing_in_account:
                # FIX LIVE-RECONCILE (2026-05-26): fetch_positions() returns [] on API error,
                # which would otherwise mark ALL state positions "missing" and drop real ones on
                # a transient fetch failure. Confirm each is REALLY flat via an authoritative
                # per-symbol check before removing; keep it on an inconclusive/None result.
                for s in sorted(missing_in_account):
                    if position_is_flat(s) is True:
                        log("WARN", f"state position {s} confirmed flat on account — removing from state")
                        positions.pop(s, None)
                    else:
                        log("WARN", f"state position {s} absent from bulk fetch but flat-check inconclusive — KEEPING (live reconcile will handle)")
            if extra_in_account:
                # FIX MANUAL-TRADE-SAFETY (2026-06-06): the bot must NEVER touch positions the
                # user opened manually (e.g. a manual BTC long on the same account). Only
                # auto-close orphans that are symbols THIS BOT could have opened — i.e. in its
                # tradeable universe (not mainstream-excluded, not blacklisted). Any orphan on a
                # mainstream/blacklisted symbol is assumed to be a user's manual trade and is
                # ALERT-ONLY, never auto-closed. (FIX HIGH-1's crash-orphan cleanup is preserved
                # for real yaobi coins the bot trades.)
                bot_tradeable_orphans = {s for s in extra_in_account
                                         if s not in mainstream and s not in blacklist}
                user_manual_orphans = extra_in_account - bot_tradeable_orphans
                if user_manual_orphans:
                    umsg = (f"Positions on Binance NOT in state.json and NOT bot-tradeable "
                            f"(mainstream/blacklist) — assuming USER MANUAL trades, leaving UNTOUCHED: "
                            f"{sorted(user_manual_orphans)}")
                    log("WARN", umsg)
                    telegram_send(f"ℹ️ <b>Manual positions detected (left untouched)</b>\n{html.escape(umsg)}")
                if bot_tradeable_orphans:
                    # FIX HIGH-1: orphan positions on exchange (e.g., from crash mid-open) MUST be
                    # auto-closed for safety, not left unmonitored at 3x leverage on yaobi coins.
                    # (Scoped to bot-tradeable symbols only — user manual trades handled above.)
                    msg = (f"ORPHAN bot-tradeable positions on Binance not in state.json: {sorted(bot_tradeable_orphans)}. "
                           f"Auto-closing for safety (no SL/TP without state).")
                    log("CRITICAL", msg)
                    telegram_send(f"🚨 <b>ORPHAN POSITIONS</b>\n{html.escape(msg)}")
                    orphan_close_failures = []
                    for p in real_positions:
                        sym = p["symbol"]
                        if sym not in bot_tradeable_orphans:
                            continue
                        amt = float(p["positionAmt"])
                        # short position has negative amt → close with BUY; long has positive → SELL
                        close_side = "BUY" if amt < 0 else "SELL"
                        abs_qty = abs(amt)
                        # FIX BLOCKING (audit 3): retry orphan close 3× before failure
                        closed_ok = False
                        last_err = None
                        for attempt in range(3):
                            try:
                                resp = place_market_order(sym, close_side, abs_qty, reduce_only=True)
                                log("INFO", f"  ✓ orphan {sym} closed ({close_side} {abs_qty}): {resp.get('avgPrice')}")
                                log_event({"event": "orphan_closed", "symbol": sym, "qty": abs_qty,
                                           "side": close_side, "binance_response": resp}, events_path)
                                # 1h cooldown on this symbol for all strategies after orphan close
                                now_ms = utc_now_ms()
                                for s in strategies:
                                    cooldowns[(s.strategy_id, sym)] = now_ms + 60 * 60 * 1000
                                closed_ok = True
                                break
                            except Exception as e:
                                last_err = e
                                log("WARN", f"  orphan close attempt {attempt+1}/3 failed for {sym}: {e}")
                                time.sleep(2)
                        if not closed_ok:
                            log("CRITICAL", f"  ✗ orphan close FAILED for {sym} after 3 retries: {last_err}")
                            orphan_close_failures.append(sym)
                    # FIX BLOCKING (audit 3): if ANY orphan close failed, ABORT startup
                    # — running with unmanaged positions at 3x leverage is unacceptable.
                    if orphan_close_failures:
                        msg = (f"ABORTING STARTUP — orphan close failed for: {orphan_close_failures}. "
                               f"Manually close these positions on Binance, then restart bot.")
                        log("FATAL", msg)
                        telegram_send(f"🚨 <b>BOT STARTUP ABORTED</b>\n{html.escape(msg)}")
                        return 2
        except Exception as e:
            log("ERROR", f"position sync failed: {e}")

    # FIX LIVE-PREFLIGHT (2026-05-17): run preflight before scanner to populate
    # the unitradable set. Symbols in this set are skipped by the scanner so we
    # never burn API retries on structurally unfillable symbols (L11 root cause).
    unitradable_symbols: set[str] = set()
    if not args.dry_run:
        try:
            preflight_report = run_preflight(config, state_dir)
            if not preflight_report["ok"]:
                msg = f"PREFLIGHT FAILED: {preflight_report['fatal']}"
                log("FATAL", msg)
                if args.telegram:
                    telegram_send(f"🚨 <b>BOT STARTUP ABORTED</b>\n{html.escape(msg)}")
                return 2
            unitradable_symbols = set(preflight_report.get("unitradable") or [])
            if unitradable_symbols and args.telegram:
                top = sorted(unitradable_symbols)[:10]
                telegram_send(
                    f"🔍 <b>PREFLIGHT OK</b>\n"
                    f"tradable: {preflight_report['tradable_count']}/{preflight_report['universe_size']}\n"
                    f"unitradable: {preflight_report['unitradable_count']}\n"
                    f"first 10: {', '.join(top)}"
                )
            elif args.telegram:
                telegram_send(
                    f"🔍 <b>PREFLIGHT OK</b>\n"
                    f"tradable: {preflight_report['tradable_count']}/{preflight_report['universe_size']} (all)"
                )
        except Exception as e:
            log("ERROR", f"preflight crashed (non-fatal, continuing without filter): {e}")

    # FIX TG-INIT (2026-05-19): Track initial balance + deploy date in misc so累计 PnL
    # can be computed precisely (current_balance - initial_balance), not approximated by
    # risk.total_pnl_usdt which resets if state.json is wiped.
    if not args.dry_run and balance > 0:
        if not misc.get("initial_balance_usdt"):
            misc["initial_balance_usdt"] = float(balance)
            misc["deploy_date_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            log("INFO", f"  recorded initial_balance=${balance:.2f} deploy_date={misc['deploy_date_utc']}")
        misc["current_balance_cached_usdt"] = float(balance)
        misc["current_balance_cached_at_ms"] = utc_now_ms()

    # Telegram startup ping (中文)
    if args.telegram:
        init_bal_disp = float(misc.get("initial_balance_usdt", balance if not args.dry_run else 0))
        deploy_disp = misc.get("deploy_date_utc", "?")
        bal_safe = balance if not args.dry_run else 0
        cum_pnl_calc = bal_safe - init_bal_disp if init_bal_disp > 0 else 0.0
        telegram_send(
            f"🟢 <b>BWE 实盘 · 启动</b>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"📦 <b>配置</b>\n"
            f"   策略数: {len(strategies)}\n"
            f"   每仓 notional: ${portfolio['notional_per_trade_usdt']}\n"
            f"   杠杆: {portfolio['leverage']}x  ({portfolio['margin_mode']})\n"
            f"   最大并发: {portfolio['max_concurrent_positions']}\n"
            f"   日亏限额: ${risk_limits['daily_loss_limit_usdt']}\n"
            f"\n"
            f"💰 <b>账户</b>\n"
            f"   当前余额: ${bal_safe:.2f}\n"
            f"   起始资金: ${init_bal_disp:.2f}  ({deploy_disp})\n"
            f"   累计 PnL: {cum_pnl_calc:+.2f} USDT\n"
            f"\n"
            f"🌐 <b>Universe (preflight)</b>\n"
            f"   不可交易: {len(unitradable_symbols)}\n"
            f"\n"
            f"🚀 监控启动... 等待信号"
        )

    # ─────────── Main loop ───────────
    last_universe_update_ms = 0
    universe: list[str] = []
    last_heartbeat_ms = utc_now_ms()
    last_uptrend_check_ms: dict[str, int] = {}
    uptrend_cache: dict[str, float] = {}  # sym → last 10d return %
    poll_sec = float(portfolio.get("position_poll_sec", 15))
    scan_sec = float(portfolio.get("scanner_interval_sec", 60))
    skip_uptrend_pct = float(config["universe"].get("skip_if_10d_return_pct_above", 10.0))
    last_scan_ms = 0

    while RUNNING:
        try:
            now_ms = utc_now_ms()

            # 0. Kill switch
            if check_kill_switch(config):
                log("CRITICAL", "KILL SWITCH detected — closing all positions and halting")
                telegram_send("🚨 <b>KILL SWITCH triggered</b> — closing all positions")
                if not args.dry_run:
                    force_close_all(positions, "kill_switch", events_path, risk, misc)
                save_state(state_path, positions, risk, cooldowns, misc)
                return 0

            # 0.5 Daily reset + daily report (FIX TG-ZH 2026-05-19)
            # Capture today's snapshot BEFORE reset so daily report has accurate data
            prev_daily_pnl = risk.daily_pnl_usdt
            prev_daily_date = risk.daily_pnl_date_utc
            prev_daily_signals = int(misc.get("daily_signal_count", 0))
            prev_daily_opens = int(misc.get("daily_open_count", 0))
            prev_daily_closes = int(misc.get("daily_close_count", 0))
            prev_daily_wins = int(misc.get("daily_win_count", 0))
            prev_daily_losses = int(misc.get("daily_loss_count", 0))
            if risk.reset_daily_if_needed():
                log("INFO", f"daily PnL reset (new UTC day)")
                # Send daily report with PREVIOUS day's stats (if there was activity)
                if args.telegram and (prev_daily_signals > 0 or prev_daily_opens > 0 or prev_daily_pnl != 0 or prev_daily_date):
                    # Refresh balance
                    try:
                        fresh = fetch_account_equity()
                        if fresh > 0:
                            misc["current_balance_cached_usdt"] = float(fresh)
                    except Exception:
                        pass
                    cur_bal_dr = float(misc.get("current_balance_cached_usdt", 0) or 0)
                    init_bal_dr = float(misc.get("initial_balance_usdt", 0) or 0)
                    day_open_bal = cur_bal_dr - prev_daily_pnl  # estimate of yesterday's open balance
                    cum_pnl_dr = cur_bal_dr - init_bal_dr if init_bal_dr > 0 else risk.total_pnl_usdt
                    cum_pct_dr = (cum_pnl_dr / init_bal_dr * 100) if init_bal_dr > 0 else 0.0
                    win_rate = (prev_daily_wins / max(prev_daily_closes, 1)) * 100 if prev_daily_closes else 0.0
                    avg_per_trade = prev_daily_pnl / max(prev_daily_closes, 1) if prev_daily_closes else 0.0
                    strat_dr_lines = []
                    strat_stats_dr = misc.get("strat_stats", {}) or {}
                    for s in strategies:
                        st = strat_stats_dr.get(s.strategy_id, {})
                        w = int(st.get("wins", 0))
                        l = int(st.get("losses", 0))
                        p = float(st.get("total_pnl", 0) or 0)
                        if w + l == 0:
                            strat_dr_lines.append(f"   {s.strategy_id}: 未触发")
                        else:
                            strat_dr_lines.append(f"   {s.strategy_id}: {w}胜 {l}负  ·  {p:+.2f} USDT")
                    bc = risk.block_counters
                    blk_strat = sum(v for k, v in bc.items() if k.startswith("blocked_strategy_filter_"))
                    blk_10d = bc.get("blocked_10d_uptrend", 0)
                    blk_atr = bc.get("blocked_atr_cap", 0)
                    daily_pct = (prev_daily_pnl / day_open_bal * 100) if day_open_bal > 0 else 0.0
                    telegram_send(
                        f"🌅 <b>BWE 实盘日报</b>  ·  {prev_daily_date}\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"💰 <b>资金</b>\n"
                        f"   日初余额: ${day_open_bal:.2f}\n"
                        f"   日终余额: ${cur_bal_dr:.2f}\n"
                        f"   ━━━━━━━━━━━━━━━\n"
                        f"   日净盈亏: {prev_daily_pnl:+.2f} USDT  ({daily_pct:+.2f}%)\n"
                        f"   累计盈亏: {cum_pnl_dr:+.2f} USDT  ({cum_pct_dr:+.2f}%)\n"
                        f"\n"
                        f"📈 <b>交易统计</b>\n"
                        f"   信号匹配: {prev_daily_signals}\n"
                        f"   开仓: {prev_daily_opens}\n"
                        f"   平仓: {prev_daily_closes}\n"
                        f"   胜 / 负: {prev_daily_wins} / {prev_daily_losses}  ·  胜率 {win_rate:.0f}%\n"
                        f"   平均每单: {avg_per_trade:+.2f} USDT\n"
                        f"\n"
                        f"🎯 <b>策略累计</b>\n"
                        + "\n".join(strat_dr_lines) + "\n"
                        f"\n"
                        f"📊 <b>市场扫描</b>\n"
                        f"   被过滤 (top 累计):\n"
                        f"     · 策略过滤器: {blk_strat:,}\n"
                        f"     · 10日已涨过 5%: {blk_10d:,}\n"
                        f"     · ATR > 5%: {blk_atr:,}\n"
                        f"\n"
                        f"🚦 <b>系统</b>\n"
                        f"   持仓: {len(positions)} / {portfolio['max_concurrent_positions']}\n"
                        f"   断路器: {'⚠ 已触发' if risk.halted else '✓ 正常'}\n"
                        f"\n"
                        f"━━━━━━━━━━━━━━━━\n"
                        f"明日策略时段 (UTC):\n"
                        f"  🌙 00-04   D_ASIA_LATE\n"
                        f"  🌅 全天    C_PULLBACK\n"
                        f"  ☀ 15-19   B_US_PM (主力)"
                    )
                # Now reset misc daily counters
                tg_reset_daily_counters(misc)
                telegram_send(f"📅 新交易日 {risk.daily_pnl_date_utc} 开始 · 计数器已重置")

            # 1. Circuit breakers
            cb_reason = check_circuit_breakers(risk, config)
            if cb_reason and not risk.halted:
                log("CRITICAL", f"circuit breaker: {cb_reason}")
                risk.halted = True
                risk.halt_reason = cb_reason
                telegram_send(f"🚨 <b>CIRCUIT BREAKER</b>: {cb_reason}\nClosing positions, no new entries.")
                if not args.dry_run:
                    force_close_all(positions, cb_reason, events_path, risk, misc)

            # 2. Monitor existing positions
            # FIX MEDIUM-2: fetch all positions ONCE per cycle (not per position)
            # — avoid N×positionRisk API calls and rate limit waste
            positions_map: dict[str, dict[str, Any]] | None = None
            if not args.dry_run and positions:
                try:
                    rps = fetch_positions()
                    positions_map = {r["symbol"]: r for r in rps}
                except Exception as e:
                    log("WARN", f"positionRisk batch fetch failed: {e}")
                    positions_map = {}

            for sym in list(positions.keys()):
                pos = positions[sym]
                try:
                    bars = fetch_klines_1m(sym, limit=3)
                except Exception as e:
                    log("WARN", f"monitor {sym} klines failed: {e}")
                    bars = []

                # FIX BLOCKING (audit 3 — monitor SL fallback): if klines fail, use markPrice
                # from positions_map as a SL fallback. Otherwise SL never triggers and position
                # is unprotected against liquidation.
                if not bars:
                    rp = positions_map.get(sym) if positions_map else None
                    if rp and rp.get("markPrice", 0) > 0:
                        mark = float(rp["markPrice"])
                        # SL check via mark price (no high/low — use mark as both)
                        sl_hit = (pos.side == "short" and mark >= pos.sl_price) or \
                                 (pos.side == "long" and mark <= pos.sl_price)
                        if sl_hit:
                            log("CRITICAL", f"{sym} klines down, SL via markPrice={mark:.6f} TRIGGERED")
                            if not args.dry_run:
                                closed = close_position(pos, "stop_loss_via_mark", mark, events_path, risk, misc)
                                if closed:
                                    positions.pop(sym, None)
                                    cooldowns[(pos.strategy_id, sym)] = now_ms + int(60 * 60 * 1000)
                    # Either SL not hit, or close succeeded/failed → skip rest for this sym this cycle
                    continue

                # Liquidation safety check — FIX MEDIUM-2: use cached positions_map (fetched once per cycle)
                if not args.dry_run and positions_map is not None:
                    rp = positions_map.get(sym)
                    if rp and check_liquidation_safety(
                        pos, rp["markPrice"], rp["liquidationPrice"],
                        risk_limits["liquidation_safety_pct"],
                    ):
                        log("CRITICAL", f"{sym} near liquidation, closing")
                        # FIX CRITICAL-3: only pop on confirmed close success
                        if close_position(pos, "liquidation_safety", rp["markPrice"], events_path, risk, misc):
                            positions.pop(sym, None)
                            cooldowns[(pos.strategy_id, sym)] = now_ms + 60 * 60 * 1000
                        continue

                reason = monitor_position(pos, bars, events_path, risk)
                if reason:
                    # FIX CRITICAL-3: only pop position on confirmed close
                    if not args.dry_run:
                        closed = close_position(pos, reason, bars[-1]["c"], events_path, risk, misc)
                    else:
                        log("INFO", f"[DRY] would close {sym} reason={reason} price={bars[-1]['c']}")
                        closed = True
                    if closed:
                        positions.pop(sym, None)
                        cooldown_min = float(portfolio["same_strategy_symbol_cooldown_min"])
                        cooldowns[(pos.strategy_id, sym)] = now_ms + int(cooldown_min * 60 * 1000)
                    # If close FAILED, leave position in state — next poll will retry monitor + close

            # 3. Universe refresh (every 5 min)
            if now_ms - last_universe_update_ms > 5 * 60 * 1000:
                try:
                    universe = build_universe(config, blacklist, mainstream)
                    last_universe_update_ms = now_ms
                    log("INFO", f"universe refreshed: {len(universe)} symbols")
                except Exception as e:
                    log("WARN", f"universe refresh failed: {e}")

            # 4. Scan for new entries (every scan_sec)
            if not risk.halted and now_ms - last_scan_ms >= scan_sec * 1000:
                last_scan_ms = now_ms
                max_concurrent = int(portfolio["max_concurrent_positions"])
                # FIX LIVE-BLOCK-COUNTERS: track concurrent_cap separately (different reason than per-sym)
                if len(positions) >= max_concurrent:
                    # would-be scan blocked because portfolio already full
                    risk.bump("blocked_portfolio_full_outer")
                if len(positions) < max_concurrent:
                    for sym in universe:
                        if not RUNNING:
                            break
                        risk.bump("scanned_sym")
                        if len(positions) >= max_concurrent:
                            risk.bump("blocked_portfolio_full")
                            break
                        # FIX LIVE-PREFLIGHT (2026-05-17): skip structurally unfillable
                        # symbols flagged at startup (no point burning CPU on signal evaluation
                        # + API retries when the exchange will reject the order).
                        if sym in unitradable_symbols:
                            risk.bump("blocked_unitradable")
                            continue
                        # Per-symbol lock (cross-strategy)
                        if portfolio.get("one_position_per_symbol_across_strategies", True):
                            if sym in positions:
                                risk.bump("blocked_same_symbol")
                                continue
                        # 10d uptrend filter (cache 1h per sym)
                        uptrend = uptrend_cache.get(sym)
                        if uptrend is None or now_ms - last_uptrend_check_ms.get(sym, 0) > 3600 * 1000:
                            try:
                                uptrend = compute_10d_return_pct(sym)
                                uptrend_cache[sym] = uptrend
                                last_uptrend_check_ms[sym] = now_ms
                            except Exception:
                                uptrend = 0.0
                        if uptrend > skip_uptrend_pct:
                            risk.bump("blocked_10d_uptrend")
                            continue
                        # Fetch fresh 1m bars (limit 81 → keep 80 closed after dropping forming bar)
                        try:
                            bars = fetch_klines_1m(sym, limit=81)
                        except Exception as e:
                            log("WARN", f"klines failed for {sym}: {e}")
                            risk.bump("blocked_klines_fail")
                            continue
                        # FIX SIGNAL-CLOSED-BAR (2026-05-21): Binance returns the in-progress
                        # (forming) bar as the last element. Evaluating it makes candle-shape
                        # filters (upper_wick, body_neg → D_ASIA) and vol z-score (B + C) unreliable
                        # — the forming bar's shape/volume aren't final, vol is under-counted.
                        # Drop it so evaluate_strategy sees the last CLOSED bar as "current".
                        # This aligns live signal eval with the closed-bar backtest/audit, and is
                        # why D_ASIA's 2 valid closed-bar signals were missed live (replay caught them).
                        if bars and bars[-1].get("ct", 0) > now_ms:
                            bars = bars[:-1]
                        if len(bars) < 65:
                            risk.bump("blocked_insufficient_bars")
                            continue
                        # FIX LIVE-BLOCK-COUNTERS: ATR cap pre-check (for explicit counter)
                        # evaluate_strategy also enforces this internally as defense-in-depth.
                        atr_pre = compute_atr_pct(bars, 14)
                        if atr_pre > MAX_ENTRY_ATR_PCT:
                            risk.bump("blocked_atr_cap")
                            continue
                        # FIX HIGH-3: per-strategy concurrency cap — count active per strategy_id
                        max_per_strat = int(portfolio.get("max_concurrent_per_strategy", 1))
                        active_per_strat: dict[str, int] = {}
                        for p in positions.values():
                            active_per_strat[p.strategy_id] = active_per_strat.get(p.strategy_id, 0) + 1

                        # Evaluate each strategy (FCFS: first to match wins)
                        for strat in strategies:
                            # FIX HIGH-3: skip strategies that already have max_per_strat open
                            if active_per_strat.get(strat.strategy_id, 0) >= max_per_strat:
                                risk.bump(f"blocked_per_strat_cap_{strat.strategy_id}")
                                continue
                            cd_expiry = cooldowns.get((strat.strategy_id, sym), 0)
                            if cd_expiry > now_ms:
                                risk.bump(f"blocked_cooldown_{strat.strategy_id}")
                                continue
                            sig_data = evaluate_strategy(strat, bars, symbol=sym)  # FIX: pass symbol for OI fetch (Champion_E)
                            if sig_data is None:
                                risk.bump(f"blocked_strategy_filter_{strat.strategy_id}")
                                continue
                            risk.bump(f"signal_matched_{strat.strategy_id}")
                            misc["daily_signal_count"] = int(misc.get("daily_signal_count", 0)) + 1
                            log("INFO", f"SIGNAL {sym} {strat.strategy_id}: {sig_data}")
                            if args.dry_run:
                                log("INFO", f"[DRY] would open {sym} via {strat.strategy_id}")
                                # Set fake cooldown to avoid log spam
                                cooldowns[(strat.strategy_id, sym)] = now_ms + 60 * 60 * 1000
                                break
                            pos = open_position(sym, strat, sig_data, config, events_path)
                            if pos:
                                positions[sym] = pos
                                risk.bump(f"opened_{strat.strategy_id}")
                                misc["daily_open_count"] = int(misc.get("daily_open_count", 0)) + 1
                                # Cross-strategy cooldown — block ALL strategies on this sym briefly
                                for s in strategies:
                                    cooldowns[(s.strategy_id, sym)] = now_ms + 5 * 60 * 1000
                            else:
                                # FIX LIVE-FAIL-COOLDOWN (2026-05-17): on failure, lock this (strategy, symbol)
                                # for 60min so we don't burn API retries every minute on a structurally
                                # bad symbol (e.g. MARKET_LOT_SIZE.maxQty exceeded). Lock all strategies
                                # on this symbol for 15min (other strategies may still face same exchange limit).
                                risk.bump(f"failed_open_{strat.strategy_id}")
                                cooldowns[(strat.strategy_id, sym)] = now_ms + 60 * 60 * 1000
                                for s in strategies:
                                    if s.strategy_id != strat.strategy_id:
                                        cd_prev = cooldowns.get((s.strategy_id, sym), 0)
                                        cooldowns[(s.strategy_id, sym)] = max(cd_prev, now_ms + 15 * 60 * 1000)
                                # Instant telegram alert (de-duped: 1 alert per (sym, strat) per hour)
                                fail_key = f"fail_alert_{strat.strategy_id}_{sym}"
                                last_alert_ms = int(misc.get(fail_key, 0))
                                if now_ms - last_alert_ms > 60 * 60 * 1000:
                                    misc[fail_key] = now_ms
                                    telegram_send(
                                        f"⚠️ <b>OPEN FAILED</b>\n"
                                        f"symbol: {html.escape(sym)}\n"
                                        f"strategy: {html.escape(strat.strategy_id)}\n"
                                        f"side: {strat.side}\n"
                                        f"cooldown: 60min (this strat) / 15min (others)\n"
                                        f"check live_runner.log for exchange error"
                                    )
                            break

            # 5. Heartbeat
            if now_ms - last_heartbeat_ms > config["telegram"]["heartbeat_interval_sec"] * 1000:
                last_heartbeat_ms = now_ms
                # FIX LIVE-BLOCK-COUNTERS: summarize block counters
                bc = risk.block_counters
                scanned = bc.get("scanned_sym", 0)
                signal_matches = sum(v for k, v in bc.items() if k.startswith("signal_matched_"))
                opens = sum(v for k, v in bc.items() if k.startswith("opened_"))
                # group block reasons
                blk_atr = bc.get("blocked_atr_cap", 0)
                blk_10d = bc.get("blocked_10d_uptrend", 0)
                blk_full = bc.get("blocked_portfolio_full", 0) + bc.get("blocked_portfolio_full_outer", 0)
                blk_samesym = bc.get("blocked_same_symbol", 0)
                blk_strat_filter = sum(v for k, v in bc.items() if k.startswith("blocked_strategy_filter_"))
                blk_per_strat = sum(v for k, v in bc.items() if k.startswith("blocked_per_strat_cap_"))
                blk_cooldown = sum(v for k, v in bc.items() if k.startswith("blocked_cooldown_"))
                blk_klines = bc.get("blocked_klines_fail", 0)
                blk_unitradable = bc.get("blocked_unitradable", 0)
                failed_opens = sum(v for k, v in bc.items() if k.startswith("failed_open_"))
                # FIX TG-EQUITY (2026-05-21): use EQUITY (wallet+unrealized) not availableBalance,
                # so 累计 PnL stays accurate during open positions (was showing false -$30 when
                # margin locked). Append " (含浮盈)" hint if a position is open.
                try:
                    fresh_eq = fetch_account_equity()
                    if fresh_eq > 0:
                        misc["current_balance_cached_usdt"] = float(fresh_eq)
                        misc["current_balance_cached_at_ms"] = now_ms
                except Exception:
                    pass
                cur_bal = float(misc.get("current_balance_cached_usdt", 0) or 0)
                init_bal = float(misc.get("initial_balance_usdt", 0) or 0)
                cum_pnl = cur_bal - init_bal if init_bal > 0 else risk.total_pnl_usdt
                cum_pct = (cum_pnl / init_bal * 100) if init_bal > 0 else 0.0
                # Daily safety distances (限额 + 当前位置)
                daily_lim = float(config["risk_limits"]["daily_loss_limit_usdt"])
                total_lim = float(config["risk_limits"]["total_drawdown_limit_usdt"])
                min_cap = float(config["risk_limits"]["min_remaining_capital_usdt"])
                # Strategy stats lines
                strat_lines = []
                strat_stats = misc.get("strat_stats", {}) or {}
                for s in strategies:
                    st = strat_stats.get(s.strategy_id, {})
                    w = int(st.get("wins", 0))
                    l = int(st.get("losses", 0))
                    p = float(st.get("total_pnl", 0) or 0)
                    if w + l == 0:
                        strat_lines.append(f"   {s.strategy_id}: 未触发")
                    else:
                        strat_lines.append(f"   {s.strategy_id}: {w}胜 {l}负  ·  {p:+.2f} USDT")
                # Service uptime
                proc_uptime_sec = (now_ms / 1000) - (utc_now_ms() / 1000 - (now_ms - last_heartbeat_ms + 2 * 3600 * 1000) / 1000)  # rough
                msg = (
                    f"📊 <b>BWE 实盘心跳</b>  ·  {datetime.now(timezone.utc).strftime('%d %b %H:%M UTC')}\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"💰 <b>账户</b>\n"
                    f"   当前余额: ${cur_bal:.2f}\n"
                    f"   累计 PnL: {cum_pnl:+.2f} USDT  ({cum_pct:+.2f}%)\n"
                    f"   今日 PnL: {risk.daily_pnl_usdt:+.2f} USDT\n"
                    f"   起始资金: ${init_bal:.2f}  ({misc.get('deploy_date_utc', '?')} 部署)\n"
                    f"\n"
                    f"📦 <b>持仓</b>: {len(positions)} / {portfolio['max_concurrent_positions']}\n"
                    f"\n"
                    f"📈 <b>今日活动</b> (UTC {risk.daily_pnl_date_utc})\n"
                    f"   信号匹配: {int(misc.get('daily_signal_count', 0))}\n"
                    f"   成功开仓: {int(misc.get('daily_open_count', 0))}\n"
                    f"   已平仓: {int(misc.get('daily_close_count', 0))} "
                    f"(盈 {int(misc.get('daily_win_count', 0))} / 亏 {int(misc.get('daily_loss_count', 0))})\n"
                    f"\n"
                    f"🎯 <b>策略累计</b> (since 部署)\n"
                    + "\n".join(strat_lines) + "\n"
                    f"\n"
                    f"🛡️ <b>风险护栏</b> (剩余距离)\n"
                    f"   日亏限: ${daily_lim:.0f}     ·  剩余 ${risk.daily_pnl_usdt - daily_lim:+.2f}\n"
                    f"   总回撤限: ${total_lim:.0f}  ·  剩余 ${risk.total_pnl_usdt - total_lim:+.2f}\n"
                    f"   最小余额: ${min_cap:.0f}    ·  余量 ${cur_bal - min_cap:+.2f}\n"
                    f"\n"
                    f"🚦 <b>系统</b>\n"
                    f"   universe: {len(universe)} 币种 ({len(unitradable_symbols)} 不可交易)\n"
                    f"   断路器: {'⚠ 已触发' if risk.halted else '✓ 正常'}\n"
                    f"   今日扫描: {scanned}\n"
                    f"   开仓失败 (累计): {failed_opens}"
                )
                if args.telegram:
                    telegram_send(msg)
                log("INFO", msg.replace("\n", " | "))

            # 6. Prune expired cooldowns (unbounded dict otherwise)
            cooldowns = {k: v for k, v in cooldowns.items() if v > now_ms}

            # 7. Persist state every loop
            save_state(state_path, positions, risk, cooldowns, misc)

        except Exception as e:
            log("ERROR", f"main loop exception: {e}\n{traceback.format_exc()}")
            # Don't crash, sleep + continue
            time.sleep(5)

        # Sleep, respecting RUNNING
        for _ in range(int(poll_sec)):
            if not RUNNING:
                break
            time.sleep(1)

    # Shutdown
    log("INFO", f"main loop exited, reason={SHUTDOWN_REASON}")
    save_state(state_path, positions, risk, cooldowns, misc)
    if args.telegram:
        telegram_send(
            f"🟡 <b>LIVE STOPPED</b>\n"
            f"reason: {SHUTDOWN_REASON}\n"
            f"open positions: {len(positions)} (NOT auto-closed on graceful stop)\n"
            f"daily PnL: {risk.daily_pnl_usdt:+.2f}\n"
            f"total PnL: {risk.total_pnl_usdt:+.2f}"
        )
    return 0


def cli() -> int:
    p = argparse.ArgumentParser(description="BWE Live Top-3 Runner")
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    p.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    p.add_argument("--secrets", type=Path, default=DEFAULT_SECRETS)
    p.add_argument("--dry-run", action="store_true",
                   help="Scan + evaluate but never send orders. Useful for first test.")
    p.add_argument("--telegram", action="store_true", help="Enable Telegram alerts.")
    p.add_argument("--preflight", action="store_true",
                   help="Run preflight (server-time + universe tradability) and exit. "
                        "Writes runtime/universe_tradability.json. Exit 0 ok, 2 fail.")
    args = p.parse_args()
    if args.preflight:
        config = json.loads(args.config.read_text())
        state_dir: Path = args.state_dir
        state_dir.mkdir(parents=True, exist_ok=True)
        init_logging(state_dir / "preflight.log")
        load_secrets(args.secrets)
        report = run_preflight(config, state_dir)
        if not report["ok"]:
            log("FATAL", f"[preflight] FAILED: {report['fatal']}")
            return 2
        log("INFO", f"[preflight] OK — tradable {report['tradable_count']}/{report['universe_size']}, "
                    f"unitradable {report['unitradable_count']}")
        return 0
    return main(args)


if __name__ == "__main__":
    sys.exit(cli())
