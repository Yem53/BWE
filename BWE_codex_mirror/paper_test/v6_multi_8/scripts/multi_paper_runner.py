#!/usr/bin/env python3
"""Eight-strategy BWE paper/demo runner.

Design guardrails:
- BWE entries use due-time mark price, never 1m close.
- BWE entries expire if they cannot be processed close to their due time.
- Scanner entries use latest completed 1m bar only as a signal; fill uses
  current mark price.
- Indicators use data at or before decision time.
- State is persisted after every loop so pending/open positions survive crash.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import hmac
import json
import math
import os
import re
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


CODEX_ROOT = Path("/Volumes/T9/BWE_codex")
RUN_ROOT = CODEX_ROOT / "paper_test/v6_multi_8"
DEFAULT_CONFIG = RUN_ROOT / "config/strategies_9.json"
DEFAULT_STATE_DIR = RUN_ROOT / "runtime"
DEFAULT_SECRET_ENV = RUN_ROOT / "secrets.env"
DEFAULT_BWE_LOG = Path("/Volumes/T9/BWE/30_DATA/bwe_logs/bwe_matrix_posts.jsonl")
DEFAULT_DB = Path("/Volumes/T9_HOT/binance_collectors_runtime/binance_futures_1m.sqlite3")
DEFAULT_PRICE_BASE_URL = "https://fapi.binance.com"
DEFAULT_DEMO_BASE_URL = "https://testnet.binancefuture.com"


@dataclass(frozen=True)
class StrategySpec:
    strategy_id: str
    label: str
    side: str
    trigger: str
    entry_delay_s: int
    conditions: list[dict[str, Any]]
    exit: dict[str, Any]
    event_type: str = "ANY"
    components: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class BweEvent:
    ts_ms: int
    source: str
    post_id: str
    text: str
    symbol: str
    event_type: str
    move_pct: float | None
    marketcap: float | None


@dataclass
class FeatureSnapshot:
    top_ratio: float | None = None
    top_ratio_age_ms: int | None = None
    global_ratio: float | None = None
    global_ratio_age_ms: int | None = None
    top_position_ratio: float | None = None
    taker_ratio: float | None = None
    oi_chg_60m: float | None = None
    quote_volume_24h: float | None = None
    quote_volume_24h_age_ms: int | None = None
    listing_age_days: float | None = None
    mark_1m_age_ms: int | None = None


@dataclass
class Bar:
    open_time_ms: int
    open: float
    high: float
    low: float
    close: float
    quote_volume: float = 0.0


@dataclass
class OpenPosition:
    strategy_id: str
    label: str
    symbol: str
    side: str
    event_ts_ms: int
    due_ts_ms: int
    entry_ts_ms: int
    entry_price: float
    qty: float
    mode: str
    exit: dict[str, Any]
    notional_usdt: float = 0.0
    component: str | None = None
    order_id: str | None = None
    demo_entry_price: float | None = None
    close_attempts: int = 0


@dataclass
class ClosedPosition:
    strategy_id: str
    label: str
    symbol: str
    side: str
    event_ts_ms: int
    entry_ts_ms: int
    exit_ts_ms: int
    entry_price: float
    exit_price: float
    pnl_pct: float
    reason: str
    mode: str
    qty: float
    notional_usdt: float = 0.0
    component: str | None = None
    order_id: str | None = None
    close_order_id: str | None = None
    demo_entry_price: float | None = None
    demo_exit_price: float | None = None
    demo_pnl_pct: float | None = None


@dataclass
class RunnerState:
    started_ts_ms: int
    cursor_byte: int = 0
    total_posts_seen: int = 0
    total_events_parsed: int = 0
    api_failures: int = 0
    api_fallback_count: int = 0
    demo_orders_placed: int = 0
    demo_orders_failed: int = 0
    demo_close_orders_placed: int = 0
    demo_close_orders_failed: int = 0
    demo_total_pnl_usdt: float = 0.0
    notifications_sent: int = 0
    pending_entries: list[dict[str, Any]] = field(default_factory=list)
    open_positions: list[OpenPosition] = field(default_factory=list)
    closed_positions: list[ClosedPosition] = field(default_factory=list)
    by_strategy: dict[str, dict[str, Any]] = field(default_factory=dict)
    skip_reasons: dict[str, int] = field(default_factory=dict)
    scanner_cursor: dict[str, int] = field(default_factory=dict)
    scanner_last_run_ms: int = 0
    recent_bwe_events: list[dict[str, Any]] = field(default_factory=list)


_SYMBOL_RE = re.compile(r"\b([A-Z0-9]{2,30}USDT)\b")
_MOVE_RE = re.compile(r"([+-])\s*([0-9]+(?:\.[0-9]+)?)\s*%")
_MC_RE = re.compile(r"MarketCap:\s*\$?\s*([0-9]+(?:\.[0-9]+)?)\s*([KMBT]?)", re.I)
_MC_MULT = {"": 1.0, "K": 1_000.0, "M": 1_000_000.0, "B": 1_000_000_000.0, "T": 1_000_000_000_000.0}
FALLBACK_FIELDS = {"top_ratio", "global_ratio", "top_position_ratio", "quote_volume_24h", "mark_1m_age_ms"}


def now_ms() -> int:
    return int(time.time() * 1000)


def iso_ms(ts_ms: int) -> str:
    return dt.datetime.fromtimestamp(ts_ms / 1000, tz=dt.timezone.utc).isoformat()


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'").strip('"'))


def load_strategy_specs(path: Path) -> list[StrategySpec]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [
        StrategySpec(
            strategy_id=s["strategy_id"],
            label=s["label"],
            side=s["side"],
            trigger=s["trigger"],
            entry_delay_s=int(s.get("entry_delay_s", 0)),
            conditions=list(s.get("conditions") or []),
            exit=dict(s.get("exit") or {}),
            event_type=str(s.get("event_type") or "ANY"),
            components=list(s.get("components") or []),
        )
        for s in raw["strategies"]
    ]


def load_portfolio(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")).get("portfolio", {})


def parse_marketcap(text: str) -> float | None:
    match = _MC_RE.search(text)
    if not match:
        return None
    return float(match.group(1)) * _MC_MULT.get(match.group(2).upper(), 1.0)


def parse_move_pct(text: str) -> tuple[str, float] | None:
    match = _MOVE_RE.search(text)
    if match:
        val = float(match.group(2))
        return ("pump" if match.group(1) == "+" else "dump", val)
    if "上涨" in text:
        return "pump", 0.0
    if "下跌" in text:
        return "dump", 0.0
    return None


def parse_bwe_post(raw: dict[str, Any]) -> BweEvent | None:
    text = str(raw.get("text") or "")
    symbol_match = _SYMBOL_RE.search(text)
    move = parse_move_pct(text)
    if not symbol_match or move is None:
        return None
    event_type, move_pct = move
    return BweEvent(
        ts_ms=int(raw.get("ts_ms") or 0),
        source=str(raw.get("source") or ""),
        post_id=str(raw.get("post_id") or ""),
        text=text,
        symbol=symbol_match.group(1),
        event_type=event_type,
        move_pct=move_pct,
        marketcap=parse_marketcap(text),
    )


def compare_value(value: float | None, cond: dict[str, Any]) -> tuple[bool, str]:
    field = str(cond["field"])
    if value is None or not math.isfinite(float(value)):
        return False, f"skip_{field}_missing"
    op = cond["op"]
    threshold = float(cond["threshold"])
    if op == ">=":
        return float(value) >= threshold, f"skip_{field}_below"
    if op == "<=":
        return float(value) <= threshold, f"skip_{field}_above"
    raise ValueError(f"unsupported op {op}")


def feature_value(event: BweEvent | None, features: FeatureSnapshot | dict[str, Any], field: str) -> float | None:
    if field == "marketcap":
        return event.marketcap if event else None
    if field == "move_pct":
        return event.move_pct if event else None
    if isinstance(features, FeatureSnapshot):
        return getattr(features, field, None)
    value = features.get(field)
    return float(value) if value is not None else None


def evaluate_long_strategy(event: BweEvent, features: FeatureSnapshot, spec: StrategySpec, active_symbols: set[str]) -> tuple[bool, str]:
    if event.symbol not in active_symbols:
        return False, "skip_not_active_usdt_perp"
    if spec.event_type != "ANY" and event.event_type != spec.event_type:
        return False, "skip_event_type"
    for cond in spec.conditions:
        age_field = None
        if cond.get("field") == "top_ratio":
            age_field = features.top_ratio_age_ms
        elif cond.get("field") == "global_ratio":
            age_field = features.global_ratio_age_ms
        if age_field is not None and "max_age_ms" in cond and age_field > int(cond["max_age_ms"]):
            return False, f"skip_{cond['field']}_stale"
        ok, reason = compare_value(feature_value(event, features, cond["field"]), cond)
        if not ok:
            return False, reason
    return True, "entry_pass"


def evaluate_scanner_conditions(values: dict[str, Any], conditions: list[dict[str, Any]]) -> tuple[bool, str]:
    for cond in conditions:
        ok, reason = compare_value(feature_value(None, values, cond["field"]), cond)
        if not ok:
            return False, reason
    return True, "entry_pass"


def ensure_stats(state: RunnerState, spec: StrategySpec) -> dict[str, Any]:
    return state.by_strategy.setdefault(spec.strategy_id, {"label": spec.label, "pass": 0, "open": 0, "closed": 0, "wins": 0, "sum_pct": 0.0, "reject": 0})


def inc_reason(state: RunnerState, reason: str) -> None:
    state.skip_reasons[reason] = state.skip_reasons.get(reason, 0) + 1


def long_pnl(entry: float, price: float) -> float:
    return (price / entry - 1.0) * 100.0


def short_pnl(entry: float, price: float) -> float:
    return ((entry - price) / entry) * 100.0


def make_closed(pos: OpenPosition, exit_ts_ms: int, exit_price: float, reason: str) -> ClosedPosition:
    pnl = long_pnl(pos.entry_price, exit_price) if pos.side == "long" else short_pnl(pos.entry_price, exit_price)
    return ClosedPosition(
        strategy_id=pos.strategy_id,
        label=pos.label,
        symbol=pos.symbol,
        side=pos.side,
        event_ts_ms=pos.event_ts_ms,
        entry_ts_ms=pos.entry_ts_ms,
        exit_ts_ms=exit_ts_ms,
        entry_price=pos.entry_price,
        exit_price=exit_price,
        pnl_pct=pnl,
        reason=reason,
        mode=pos.mode,
        qty=pos.qty,
        notional_usdt=pos.notional_usdt,
        component=pos.component,
        order_id=pos.order_id,
        demo_entry_price=pos.demo_entry_price,
    )


def simulate_exit(pos: OpenPosition, bars: list[Bar], spec: StrategySpec) -> ClosedPosition | None:
    if not bars:
        return None
    entry = pos.entry_price
    ex = pos.exit or spec.exit
    kind = ex.get("kind")
    horizon = int(ex.get("horizon", 240))
    bars = bars[:horizon]

    if kind == "failed_continuation":
        sl = float(ex.get("sl_pct", 0.05))
        failed_check = int(ex.get("failed_check_min", 10))
        failed_frac = float(ex.get("failed_threshold_fraction_of_sl", 0.35))
        if pos.side == "long":
            stop = entry * (1.0 - sl)
            for idx, bar in enumerate(bars, start=1):
                if bar.low <= stop:
                    return make_closed(pos, bar.open_time_ms, stop, "initial_stop")
                if idx >= failed_check and long_pnl(entry, bar.close) < -sl * failed_frac * 100.0:
                    return make_closed(pos, bar.open_time_ms, bar.close, "failed_continuation_exit")
        else:
            stop = entry * (1.0 + sl)
            for idx, bar in enumerate(bars, start=1):
                if bar.high >= stop:
                    return make_closed(pos, bar.open_time_ms, stop, "initial_stop")
                if idx >= failed_check and short_pnl(entry, bar.close) < -sl * failed_frac * 100.0:
                    return make_closed(pos, bar.open_time_ms, bar.close, "failed_continuation_exit")
        if len(bars) >= horizon:
            return make_closed(pos, bars[-1].open_time_ms, bars[-1].close, "time_exit")
        return None

    if kind == "adaptive_trail":
        arm = float(ex.get("arm", 8))
        trail = float(ex.get("trail", 3))
        lock = float(ex.get("lock", 0))
        sl = float(ex.get("sl", 0))
        best = -999.0
        armed = False
        for bar in bars:
            if pos.side != "short":
                raise ValueError("adaptive_trail currently configured only for short")
            if armed:
                stop_profit = max(lock, best - trail)
                stop_price = entry * (1.0 - stop_profit / 100.0)
                if bar.high >= stop_price:
                    return make_closed(pos, bar.open_time_ms, stop_price, "adaptive_trail")
            elif sl > 0 and bar.high >= entry * (1.0 + sl / 100.0):
                return make_closed(pos, bar.open_time_ms, entry * (1.0 + sl / 100.0), "initial_stop")
            low_profit = short_pnl(entry, bar.low)
            best = max(best, low_profit)
            if best >= arm:
                armed = True
        if len(bars) >= horizon:
            return make_closed(pos, bars[-1].open_time_ms, bars[-1].close, "time_exit")
        return None

    if kind == "tp_close_stop":
        tp = float(ex["tp"])
        close_stop = float(ex["close_stop"])
        grace = int(ex["grace"])
        for idx, bar in enumerate(bars, start=1):
            if pos.side != "short":
                raise ValueError("tp_close_stop currently configured only for short")
            if bar.low <= entry * (1.0 - tp / 100.0):
                return make_closed(pos, bar.open_time_ms, entry * (1.0 - tp / 100.0), "take_profit")
            if idx >= grace and bar.close >= entry * (1.0 + close_stop / 100.0):
                return make_closed(pos, bar.open_time_ms, entry * (1.0 + close_stop / 100.0), "close_stop")
        if len(bars) >= horizon:
            return make_closed(pos, bars[-1].open_time_ms, bars[-1].close, "time_exit")
        return None

    raise ValueError(f"unsupported exit kind {kind}")


def open_db(db_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=30)


def load_active_symbols(db: sqlite3.Connection) -> set[str]:
    return {str(r[0]) for r in db.execute("SELECT symbol FROM symbol_meta WHERE status='TRADING' AND quote_asset='USDT' AND contract_type='PERPETUAL'")}


def one_row(db: sqlite3.Connection, sql: str, params: tuple[Any, ...]) -> sqlite3.Row | tuple[Any, ...] | None:
    return db.execute(sql, params).fetchone()


def ratio_at(db: sqlite3.Connection, table: str, symbol: str, ts_ms: int) -> tuple[float | None, int | None]:
    row = one_row(db, f"SELECT ts_ms, long_short_ratio FROM {table} WHERE symbol=? AND ts_ms<=? ORDER BY ts_ms DESC LIMIT 1", (symbol, ts_ms))
    if not row:
        return None, None
    return float(row[1]), max(0, ts_ms - int(row[0]))


def point_feature_snapshot(db: sqlite3.Connection, symbol: str, ts_ms: int) -> FeatureSnapshot:
    top, top_age = ratio_at(db, "top_trader_long_short_account_ratio_5m", symbol, ts_ms)
    glob, glob_age = ratio_at(db, "global_long_short_account_ratio_5m", symbol, ts_ms)
    pos, _ = ratio_at(db, "top_trader_long_short_position_ratio_5m", symbol, ts_ms)
    qv_row = one_row(db, "SELECT ts_ms, quote_volume FROM ticker_24h WHERE symbol=? AND ts_ms<=? ORDER BY ts_ms DESC LIMIT 1", (symbol, ts_ms))
    meta = one_row(db, "SELECT listing_ts_ms FROM symbol_meta WHERE symbol=? LIMIT 1", (symbol,))
    mark = one_row(db, "SELECT ts_ms FROM mark_price_1m WHERE symbol=? AND ts_ms<=? ORDER BY ts_ms DESC LIMIT 1", (symbol, ts_ms))
    return FeatureSnapshot(
        top_ratio=top,
        top_ratio_age_ms=top_age,
        global_ratio=glob,
        global_ratio_age_ms=glob_age,
        top_position_ratio=pos,
        quote_volume_24h=float(qv_row[1]) if qv_row and qv_row[1] is not None else None,
        quote_volume_24h_age_ms=max(0, ts_ms - int(qv_row[0])) if qv_row and qv_row[0] is not None else None,
        listing_age_days=(ts_ms - int(meta[0])) / 86_400_000.0 if meta and meta[0] else None,
        mark_1m_age_ms=max(0, ts_ms - int(mark[0])) if mark else None,
    )


def bars_after_entry(db: sqlite3.Connection, symbol: str, entry_ts_ms: int, current_ts_ms: int, limit: int) -> list[Bar]:
    rows = db.execute(
        "SELECT open_time_ms, open, high, low, close, quote_volume FROM klines_1m "
        "WHERE interval='1m' AND symbol=? AND open_time_ms>? AND close_time_ms<=? ORDER BY open_time_ms LIMIT ?",
        (symbol, entry_ts_ms, current_ts_ms - 5_000, limit),
    ).fetchall()
    return [Bar(int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])) for r in rows]


def latest_bars(db: sqlite3.Connection, symbol: str, current_ts_ms: int, limit: int = 1505) -> list[Bar]:
    rows = db.execute(
        "SELECT open_time_ms, open, high, low, close, quote_volume FROM klines_1m "
        "WHERE interval='1m' AND symbol=? AND close_time_ms<=? ORDER BY open_time_ms DESC LIMIT ?",
        (symbol, current_ts_ms - 5_000, limit),
    ).fetchall()
    rows = list(reversed(rows))
    return [Bar(int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])) for r in rows]


def scanner_values(db: sqlite3.Connection, symbol: str, bars: list[Bar], recent_events: list[dict[str, Any]]) -> dict[str, Any] | None:
    if len(bars) < 65:
        return None
    cur = bars[-1]
    prev_qv = [b.quote_volume for b in bars[-1441:-1]]
    if len(prev_qv) < 120:
        return None
    qv_avg = sum(prev_qv) / len(prev_qv)
    qv_5m = sum(b.quote_volume for b in bars[-5:])
    highs60 = [b.high for b in bars[-60:]]
    ts5 = (cur.open_time_ms // 300_000) * 300_000
    top_pos, _ = ratio_at(db, "top_trader_long_short_position_ratio_5m", symbol, ts5)
    taker_row = one_row(db, "SELECT buy_sell_ratio FROM taker_buy_sell_volume_5m WHERE symbol=? AND ts_ms<=? ORDER BY ts_ms DESC LIMIT 1", (symbol, ts5))
    oi_now = one_row(db, "SELECT sum_open_interest FROM open_interest_5m WHERE symbol=? AND ts_ms<=? ORDER BY ts_ms DESC LIMIT 1", (symbol, ts5))
    oi_prev = one_row(db, "SELECT sum_open_interest FROM open_interest_5m WHERE symbol=? AND ts_ms<=? ORDER BY ts_ms DESC LIMIT 1", (symbol, ts5 - 3_600_000))
    oi_chg = None
    if oi_now and oi_prev and oi_prev[0]:
        oi_chg = (float(oi_now[0]) / float(oi_prev[0]) - 1.0) * 100.0
    bwe_60 = sum(1 for e in recent_events if e.get("symbol") == symbol and cur.open_time_ms - 3_600_000 <= int(e["ts_ms"]) <= cur.open_time_ms)
    return {
        "open_time_ms": cur.open_time_ms,
        "ret_3m": (cur.close / bars[-4].close - 1.0) * 100.0,
        "ret_15m": (cur.close / bars[-16].close - 1.0) * 100.0,
        "ret_60m": (cur.close / bars[-61].close - 1.0) * 100.0,
        "pullback_from_high_60m": (cur.close / max(highs60) - 1.0) * 100.0,
        "body_ret_1m": (cur.close / cur.open - 1.0) * 100.0,
        "upper_wick_pct": (cur.high / max(cur.open, cur.close) - 1.0) * 100.0,
        "qv_5m_ratio": qv_5m / (qv_avg * 5.0) if qv_avg > 0 else None,
        "top_position_ratio": top_pos,
        "taker_ratio": float(taker_row[0]) if taker_row and taker_row[0] is not None else None,
        "oi_chg_60m": oi_chg,
        "bwe_60m": bwe_60,
    }


def read_new_lines(path: Path, cursor_byte: int) -> tuple[list[str], int]:
    try:
        size = path.stat().st_size
    except FileNotFoundError:
        return [], cursor_byte
    if size < cursor_byte:
        cursor_byte = 0
    if size == cursor_byte:
        return [], cursor_byte
    with path.open("rb") as f:
        f.seek(cursor_byte)
        chunk = f.read(size - cursor_byte)
    last = chunk.rfind(b"\n")
    if last < 0:
        return [], cursor_byte
    complete = chunk[: last + 1]
    return [ln for ln in complete.decode("utf-8", errors="replace").splitlines() if ln.strip()], cursor_byte + len(complete)


def request_json(url: str, *, method: str = "GET", body: bytes | None = None, headers: dict[str, str] | None = None, timeout: float = 10.0) -> Any:
    req = urllib.request.Request(url, data=body, headers=headers or {"User-Agent": "BWE-Codex-MultiPaper/1.0"}, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _mark_price_from_sqlite(symbol: str, db_path: Path = DEFAULT_DB, max_age_ms: int = 180_000) -> float | None:
    """Read latest mark_price from collector's mark_price_1m table.

    The mark_price_1m schema stores 1m bars (open/high/low/close); `close` is the
    bar's final mark price. Returns None if no row, value too stale, or DB issue.
    Uses read-only URI to never block collector writes.
    """
    if not db_path.exists():
        return None
    try:
        uri = f"file:{db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=5)
        try:
            row = conn.execute(
                "SELECT ts_ms, close FROM mark_price_1m WHERE symbol=? ORDER BY ts_ms DESC LIMIT 1",
                (symbol,),
            ).fetchone()
        finally:
            conn.close()
        if not row or row[1] is None:
            return None
        ts_ms, close = int(row[0]), float(row[1])
        age = max(0, int(time.time() * 1000) - ts_ms)
        if age > max_age_ms:
            return None
        return close
    except sqlite3.Error:
        return None


def get_mark_price(symbol: str, base_url: str, db_path: Path = DEFAULT_DB) -> float:
    """Resolve mark price for a symbol.

    Prefer collector's mark_price_1m SQLite (≤3min stale) so the runner stays
    aligned with collector state and avoids hammering /fapi/v1/premiumIndex.
    Falls back to REST premiumIndex if SQLite is empty/stale or read fails.
    """
    cached = _mark_price_from_sqlite(symbol, db_path=db_path)
    if cached is not None:
        return cached
    data = request_json(f"{base_url.rstrip('/')}/fapi/v1/premiumIndex?{urllib.parse.urlencode({'symbol': symbol})}")
    return float(data["markPrice"])


def _age_ms(current_ts_ms: int, source_ts_ms: int | None) -> int | None:
    if source_ts_ms is None:
        return None
    return max(0, current_ts_ms - int(source_ts_ms))


def _ratio_from_rest(symbol: str, base_url: str, endpoint: str, current_ts_ms: int, timeout: float) -> tuple[float | None, int | None]:
    params = urllib.parse.urlencode({"symbol": symbol, "period": "5m", "limit": 1})
    data = request_json(f"{base_url.rstrip('/')}/futures/data/{endpoint}?{params}", timeout=timeout)
    if not isinstance(data, list) or not data:
        return None, None
    row = data[-1]
    ratio = row.get("longShortRatio")
    ts = row.get("timestamp")
    return (float(ratio) if ratio is not None else None, _age_ms(current_ts_ms, int(ts) if ts is not None else None))


def fetch_binance_public_feature_snapshot(symbol: str, base_url: str, current_ts_ms: int, needed_fields: set[str], timeout: float) -> FeatureSnapshot:
    snap = FeatureSnapshot()
    if "top_ratio" in needed_fields:
        snap.top_ratio, snap.top_ratio_age_ms = _ratio_from_rest(symbol, base_url, "topLongShortAccountRatio", current_ts_ms, timeout)
    if "global_ratio" in needed_fields:
        snap.global_ratio, snap.global_ratio_age_ms = _ratio_from_rest(symbol, base_url, "globalLongShortAccountRatio", current_ts_ms, timeout)
    if "top_position_ratio" in needed_fields:
        snap.top_position_ratio, _ = _ratio_from_rest(symbol, base_url, "topLongShortPositionRatio", current_ts_ms, timeout)
    if "quote_volume_24h" in needed_fields:
        data = request_json(f"{base_url.rstrip('/')}/fapi/v1/ticker/24hr?{urllib.parse.urlencode({'symbol': symbol})}", timeout=timeout)
        snap.quote_volume_24h = float(data["quoteVolume"]) if isinstance(data, dict) and data.get("quoteVolume") is not None else None
        close_time = data.get("closeTime") if isinstance(data, dict) else None
        snap.quote_volume_24h_age_ms = _age_ms(current_ts_ms, int(close_time) if close_time is not None else None)
    if "mark_1m_age_ms" in needed_fields:
        data = request_json(f"{base_url.rstrip('/')}/fapi/v1/premiumIndex?{urllib.parse.urlencode({'symbol': symbol})}", timeout=timeout)
        mark_time = data.get("time") if isinstance(data, dict) else None
        snap.mark_1m_age_ms = _age_ms(current_ts_ms, int(mark_time) if mark_time is not None else current_ts_ms)
    return snap


def fallback_needed_fields(event: BweEvent, features: FeatureSnapshot, spec: StrategySpec, ticker_max_age_ms: int) -> list[str]:
    needed: list[str] = []
    for cond in spec.conditions:
        field = str(cond["field"])
        if field not in FALLBACK_FIELDS:
            continue
        value = feature_value(event, features, field)
        if value is None:
            needed.append(field)
            continue
        if field in {"top_ratio", "global_ratio"}:
            age = features.top_ratio_age_ms if field == "top_ratio" else features.global_ratio_age_ms
            if age is not None and "max_age_ms" in cond and age > int(cond["max_age_ms"]):
                needed.append(field)
        elif field == "quote_volume_24h":
            age = features.quote_volume_24h_age_ms
            if age is not None and age > ticker_max_age_ms:
                needed.append(field)
        elif field == "mark_1m_age_ms" and cond.get("op") == "<=" and value > float(cond["threshold"]):
            needed.append(field)
    return list(dict.fromkeys(needed))


def _merge_fallback_value(features: FeatureSnapshot, fallback: FeatureSnapshot, field: str) -> bool:
    value = getattr(fallback, field, None)
    if value is None:
        return False
    setattr(features, field, value)
    if field == "top_ratio":
        features.top_ratio_age_ms = fallback.top_ratio_age_ms
    elif field == "global_ratio":
        features.global_ratio_age_ms = fallback.global_ratio_age_ms
    elif field == "quote_volume_24h":
        features.quote_volume_24h_age_ms = fallback.quote_volume_24h_age_ms
    return True


# 5m short-term cache keyed by (symbol, field) so concurrent strategies on the
# same BWE event share fallback REST work instead of N×duplicate calls.
_FALLBACK_CACHE_TTL_MS = 5 * 60 * 1000
_fallback_cache: dict[tuple[str, str], tuple[int, Any, int | None]] = {}


def _read_fallback_cache(symbol: str, fields: set[str], current_ts_ms: int) -> tuple[FeatureSnapshot, set[str]]:
    """Return (cached_snap, fields_still_needed). Removes expired entries."""
    snap = FeatureSnapshot()
    still: set[str] = set()
    for field in fields:
        entry = _fallback_cache.get((symbol, field))
        if entry is None:
            still.add(field); continue
        cached_at, value, age_ms = entry
        if (current_ts_ms - cached_at) > _FALLBACK_CACHE_TTL_MS:
            still.add(field); continue
        # Re-base the age relative to "now" so consumers see realistic staleness
        rebased_age = (age_ms or 0) + (current_ts_ms - cached_at)
        if field == "top_ratio":
            snap.top_ratio = value; snap.top_ratio_age_ms = rebased_age
        elif field == "global_ratio":
            snap.global_ratio = value; snap.global_ratio_age_ms = rebased_age
        elif field == "top_position_ratio":
            snap.top_position_ratio = value
        elif field == "quote_volume_24h":
            snap.quote_volume_24h = value; snap.quote_volume_24h_age_ms = rebased_age
        elif field == "mark_1m_age_ms":
            snap.mark_1m_age_ms = rebased_age
    return snap, still


def _write_fallback_cache(symbol: str, snap: FeatureSnapshot, fields: set[str], current_ts_ms: int) -> None:
    for field in fields:
        if field == "top_ratio" and snap.top_ratio is not None:
            _fallback_cache[(symbol, field)] = (current_ts_ms, snap.top_ratio, snap.top_ratio_age_ms)
        elif field == "global_ratio" and snap.global_ratio is not None:
            _fallback_cache[(symbol, field)] = (current_ts_ms, snap.global_ratio, snap.global_ratio_age_ms)
        elif field == "top_position_ratio" and snap.top_position_ratio is not None:
            _fallback_cache[(symbol, field)] = (current_ts_ms, snap.top_position_ratio, None)
        elif field == "quote_volume_24h" and snap.quote_volume_24h is not None:
            _fallback_cache[(symbol, field)] = (current_ts_ms, snap.quote_volume_24h, snap.quote_volume_24h_age_ms)
        elif field == "mark_1m_age_ms" and snap.mark_1m_age_ms is not None:
            _fallback_cache[(symbol, field)] = (current_ts_ms, snap.mark_1m_age_ms, snap.mark_1m_age_ms)


def maybe_apply_binance_fallback(event: BweEvent, features: FeatureSnapshot, spec: StrategySpec, args: argparse.Namespace, current_ts_ms: int, fetcher: Any = fetch_binance_public_feature_snapshot) -> tuple[FeatureSnapshot, list[str]]:
    if not getattr(args, "enable_binance_fallback", True):
        return features, []
    needed = fallback_needed_fields(event, features, spec, int(getattr(args, "ticker_max_age_ms", 600_000)))
    if not needed:
        return features, []
    needed_set = set(needed)
    cached_snap, still_needed = _read_fallback_cache(event.symbol, needed_set, current_ts_ms)
    used: list[str] = []
    for field in needed:
        if field not in still_needed and _merge_fallback_value(features, cached_snap, field):
            used.append(field)
    if still_needed:
        fallback = fetcher(event.symbol, args.price_base_url, current_ts_ms, still_needed, float(getattr(args, "fallback_timeout_seconds", 5.0)))
        _write_fallback_cache(event.symbol, fallback, still_needed, current_ts_ms)
        for field in needed:
            if field in still_needed and _merge_fallback_value(features, fallback, field):
                used.append(field)
    return features, used


def credentials() -> tuple[str, str]:
    api_key = os.getenv("BINANCE_DEMO_API_KEY") or os.getenv("BINANCE_TESTNET_API_KEY")
    secret = os.getenv("BINANCE_DEMO_API_SECRET") or os.getenv("BINANCE_TESTNET_SECRET")
    if not api_key or not secret:
        raise RuntimeError("Binance demo/testnet credentials are not set")
    return api_key, secret


def signed_request(base_url: str, method: str, path: str, params: dict[str, Any] | None = None) -> Any:
    api_key, secret = credentials()
    payload = dict(params or {})
    payload["timestamp"] = now_ms()
    payload["recvWindow"] = 5000
    query = urllib.parse.urlencode(payload)
    sig = hmac.new(secret.encode(), query.encode(), hashlib.sha256).hexdigest()
    full = f"{query}&signature={sig}"
    headers = {"X-MBX-APIKEY": api_key, "User-Agent": "BWE-Codex-MultiPaper/1.0", "Content-Type": "application/x-www-form-urlencoded"}
    if method == "GET":
        return request_json(f"{base_url.rstrip('/')}{path}?{full}", headers=headers)
    return request_json(f"{base_url.rstrip('/')}{path}", method=method, body=full.encode(), headers=headers)


_exchange_cache: dict[str, dict[str, Any]] = {}
_EXCHANGE_CACHE_TTL_MS = 24 * 60 * 60 * 1000  # refresh exchange filters once per day


def exchange_filters(symbol: str, base_url: str) -> dict[str, Any] | None:
    cached = _exchange_cache.get(symbol)
    if cached is not None:
        fetched_at = int(cached.get("_fetched_ms") or 0)
        if (now_ms() - fetched_at) <= _EXCHANGE_CACHE_TTL_MS:
            return cached
    try:
        data = request_json(f"{base_url.rstrip('/')}/fapi/v1/exchangeInfo?{urllib.parse.urlencode({'symbol': symbol})}")
    except Exception:
        return cached  # serve stale-but-known if refresh fails
    syms = data.get("symbols") or []
    if not syms:
        return cached
    raw = syms[0]
    filters = {f["filterType"]: f for f in raw.get("filters", [])}
    lot = filters.get("LOT_SIZE", {})
    min_notional = filters.get("MIN_NOTIONAL", {})
    # Default minNotional 50 USDT (binance USDM perp standard); avoid letting under-minimum orders slip through if exchangeInfo data is incomplete.
    out = {
        "stepSize": float(lot.get("stepSize", "0.001")),
        "minQty": float(lot.get("minQty", "0")),
        "quantityPrecision": int(raw.get("quantityPrecision", 3)),
        "minNotional": float(min_notional.get("notional", "50")),
        "_fetched_ms": now_ms(),
    }
    _exchange_cache[symbol] = out
    return out


def round_step(qty: float, step: float, min_qty: float, precision: int) -> float | None:
    rounded = math.floor(qty / step) * step
    rounded = round(rounded, precision)
    return rounded if rounded >= min_qty else None


def qty_for_notional(symbol: str, price: float, notional: float, base_url: str) -> float | None:
    f = exchange_filters(symbol, base_url)
    if not f or price <= 0:
        return None
    qty = round_step(notional / price, f["stepSize"], f["minQty"], f["quantityPrecision"])
    if qty is None or qty * price < f["minNotional"]:
        return None
    return qty


def place_demo_market_order(symbol: str, side: str, qty: float, base_url: str, reduce_only: bool) -> dict[str, Any]:
    params: dict[str, Any] = {"symbol": symbol, "side": side, "type": "MARKET", "quantity": qty, "newOrderRespType": "RESULT"}
    if reduce_only:
        params["reduceOnly"] = "true"
    data = signed_request(base_url, "POST", "/fapi/v1/order", params)
    if not isinstance(data, dict):
        raise RuntimeError("order response was not object")
    return data


def send_telegram(text: str) -> bool:
    token = os.getenv("BWE_TRADE_TEST_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("BWE_TRADE_TEST_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False
    body = json.dumps({"chat_id": chat_id, "text": text, "disable_web_page_preview": True}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.status == 200


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def state_to_dict(state: RunnerState) -> dict[str, Any]:
    raw = asdict(state)
    raw["open_positions"] = [asdict(p) for p in state.open_positions]
    raw["closed_positions"] = [asdict(p) for p in state.closed_positions[-500:]]
    return raw


def state_from_dict(raw: dict[str, Any]) -> RunnerState:
    state = RunnerState(started_ts_ms=int(raw.get("started_ts_ms") or now_ms()))
    for key in ["cursor_byte", "total_posts_seen", "total_events_parsed", "api_failures", "api_fallback_count", "demo_orders_placed", "demo_orders_failed", "demo_close_orders_placed", "demo_close_orders_failed", "notifications_sent"]:
        setattr(state, key, int(raw.get(key) or 0))
    state.demo_total_pnl_usdt = float(raw.get("demo_total_pnl_usdt") or 0.0)
    state.pending_entries = list(raw.get("pending_entries") or [])
    state.open_positions = [OpenPosition(**p) for p in raw.get("open_positions") or []]
    state.closed_positions = [ClosedPosition(**p) for p in raw.get("closed_positions") or []]
    state.by_strategy = dict(raw.get("by_strategy") or {})
    state.skip_reasons = dict(raw.get("skip_reasons") or {})
    state.scanner_cursor = {str(k): int(v) for k, v in (raw.get("scanner_cursor") or {}).items()}
    state.scanner_last_run_ms = int(raw.get("scanner_last_run_ms") or 0)
    state.recent_bwe_events = list(raw.get("recent_bwe_events") or [])
    return state


def load_state(path: Path) -> RunnerState:
    if not path.exists():
        return RunnerState(started_ts_ms=now_ms())
    return state_from_dict(json.loads(path.read_text(encoding="utf-8")))


def save_state(path: Path, state: RunnerState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state_to_dict(state), ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def recover_from_order_journal(state_dir: Path, state: RunnerState, specs: list[StrategySpec]) -> bool:
    journal = state_dir / "order_journal.jsonl"
    if not journal.exists():
        return False
    specs_by_id = {s.strategy_id: s for s in specs}
    changed = False
    open_order_ids = {p.order_id for p in state.open_positions if p.order_id}
    closed_entry_order_ids = {p.order_id for p in state.closed_positions if p.order_id}
    close_order_ids = {p.close_order_id for p in state.closed_positions if p.close_order_id}
    for line in journal.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind = row.get("kind")
        if kind == "open_ack":
            payload = row.get("position") or {}
            order_id = str(payload.get("order_id") or "")
            if not order_id or order_id in open_order_ids or order_id in closed_entry_order_ids:
                continue
            pos = OpenPosition(**payload)
            state.open_positions.append(pos)
            open_order_ids.add(order_id)
            spec = specs_by_id.get(pos.strategy_id)
            if spec:
                stats = ensure_stats(state, spec)
                stats["pass"] = int(stats.get("pass", 0)) + 1
                stats["open"] = int(stats.get("open", 0)) + 1
            inc_reason(state, "recovered_open_from_order_journal")
            changed = True
        elif kind == "close_ack":
            payload = row.get("closed_position") or {}
            close_order_id = str(payload.get("close_order_id") or "")
            if not close_order_id or close_order_id in close_order_ids:
                continue
            closed = ClosedPosition(**payload)
            state.open_positions = [p for p in state.open_positions if p.order_id != closed.order_id]
            state.closed_positions.append(closed)
            close_order_ids.add(close_order_id)
            closed_entry_order_ids.add(str(closed.order_id or ""))
            spec = specs_by_id.get(closed.strategy_id)
            if spec:
                stats = ensure_stats(state, spec)
                stats["open"] = max(0, int(stats.get("open", 0)) - 1)
                stats["closed"] = int(stats.get("closed", 0)) + 1
                stats["wins"] = int(stats.get("wins", 0)) + (1 if closed.pnl_pct > 0 else 0)
                stats["sum_pct"] = float(stats.get("sum_pct", 0.0)) + closed.pnl_pct
            inc_reason(state, "recovered_close_from_order_journal")
            changed = True
    return changed


def has_conflicting_demo_position(state: RunnerState, symbol: str, side: str) -> bool:
    return any(p.symbol == symbol and p.side != side and p.mode == "demo_order" for p in state.open_positions)


def _position_last_ts_ms(position: Any) -> int:
    return int(getattr(position, "exit_ts_ms", 0) or getattr(position, "entry_ts_ms", 0) or 0)


def portfolio_block_reason(state: RunnerState, spec: StrategySpec, symbol: str, args: argparse.Namespace, current_ts_ms: int) -> str | None:
    if count_open_strategy(state, spec.strategy_id) >= args.max_concurrent_per_strategy or len(state.open_positions) >= args.max_concurrent_total:
        return "skip_concurrency_cap"
    if getattr(args, "one_position_per_symbol", False) and any(p.symbol == symbol for p in state.open_positions):
        return "skip_symbol_already_open"
    if getattr(args, "demo_orders", False) and has_conflicting_demo_position(state, symbol, spec.side):
        return "skip_demo_opposite_side_conflict"
    cooldown_min = float(getattr(args, "same_strategy_symbol_cooldown_min", 0) or 0)
    if cooldown_min > 0:
        cutoff_ms = current_ts_ms - int(cooldown_min * 60_000)
        recent_positions = list(state.open_positions) + list(state.closed_positions)
        for pos in recent_positions:
            if pos.strategy_id == spec.strategy_id and pos.symbol == symbol and _position_last_ts_ms(pos) >= cutoff_ms:
                return "skip_same_strategy_symbol_cooldown"
    return None


def open_position(args: argparse.Namespace, state: RunnerState, spec: StrategySpec, symbol: str, side: str, event_ts_ms: int, due_ts_ms: int, exit_cfg: dict[str, Any], component: str | None = None) -> None:
    stats = ensure_stats(state, spec)
    if args.demo_orders and has_conflicting_demo_position(state, symbol, side):
        inc_reason(state, "skip_demo_opposite_side_conflict")
        return
    try:
        entry_price = get_mark_price(symbol, args.price_base_url, db_path=args.db)
    except Exception as exc:
        state.api_failures += 1
        inc_reason(state, "skip_mark_price_unavailable")
        append_jsonl(args.state_dir / "errors.jsonl", {"ts_ms": now_ms(), "component": "mark_price", "symbol": symbol, "error": str(exc)})
        return
    qty = args.notional_usdt / entry_price
    mode = "signal_only"
    order_id = None
    demo_entry_price = None
    if args.demo_orders and not has_conflicting_demo_position(state, symbol, side):
        mode = "demo_order"
        demo_qty = qty_for_notional(symbol, entry_price, args.notional_usdt, args.demo_base_url)
        if demo_qty is None:
            state.demo_orders_failed += 1
            inc_reason(state, "skip_demo_qty_or_symbol_unavailable")
            return
        side_order = "BUY" if side == "long" else "SELL"
        try:
            order = place_demo_market_order(symbol, side_order, demo_qty, args.demo_base_url, reduce_only=False)
            qty = float(order.get("executedQty") or demo_qty) or demo_qty
            fill = float(order.get("avgPrice") or 0.0)
            if fill > 0:
                entry_price = fill
                demo_entry_price = fill
            order_id = str(order.get("orderId") or "")
            state.demo_orders_placed += 1
        except Exception as exc:
            state.demo_orders_failed += 1
            inc_reason(state, "skip_demo_order_failed")
            append_jsonl(args.state_dir / "errors.jsonl", {"ts_ms": now_ms(), "component": "demo_open_order", "symbol": symbol, "error": str(exc)})
            return
    pos = OpenPosition(spec.strategy_id, spec.label, symbol, side, event_ts_ms, due_ts_ms, now_ms(), entry_price, qty, mode, dict(exit_cfg), qty * entry_price, component, order_id, demo_entry_price)
    if mode == "demo_order":
        append_jsonl(args.state_dir / "order_journal.jsonl", {"ts_ms": now_ms(), "kind": "open_ack", "position": asdict(pos)})
    state.open_positions.append(pos)
    stats["pass"] = int(stats.get("pass", 0)) + 1
    stats["open"] = int(stats.get("open", 0)) + 1
    append_jsonl(args.state_dir / "trades.jsonl", {"ts_ms": now_ms(), "action": "open", "position": asdict(pos)})
    save_state(args.state_dir / "state.json", state)
    # Telegram push on open (best-effort, never blocks the trade path)
    try:
        delay = int((pos.entry_ts_ms - pos.event_ts_ms) // 1000)
        notify(args, state, build_open_text(pos, entry_delay_s=delay), "open")
    except Exception:
        pass


def close_demo_position(args: argparse.Namespace, pos: OpenPosition) -> tuple[str | None, float | None]:
    side_order = "SELL" if pos.side == "long" else "BUY"
    order = place_demo_market_order(pos.symbol, side_order, pos.qty, args.demo_base_url, reduce_only=not args.allow_non_reduce_close)
    return str(order.get("orderId") or ""), float(order.get("avgPrice") or 0.0) or None


def process_bwe_posts(args: argparse.Namespace, state: RunnerState, specs: list[StrategySpec]) -> None:
    lines, cursor = read_new_lines(args.bwe_log, state.cursor_byte)
    state.cursor_byte = cursor
    long_specs = [s for s in specs if s.side == "long" and s.trigger == "bwe"]
    for line in lines:
        state.total_posts_seen += 1
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            inc_reason(state, "skip_bad_json")
            continue
        event = parse_bwe_post(raw)
        if not event:
            inc_reason(state, "skip_not_bwe_price_event")
            continue
        state.total_events_parsed += 1
        state.recent_bwe_events.append(asdict(event))
        append_jsonl(args.state_dir / "events.jsonl", {"ts_ms": now_ms(), "event": asdict(event)})
        for spec in long_specs:
            if spec.event_type != "ANY" and event.event_type != spec.event_type:
                continue
            state.pending_entries.append({"strategy_id": spec.strategy_id, "event": asdict(event), "due_ts_ms": event.ts_ms + spec.entry_delay_s * 1000})
    cutoff = now_ms() - 2 * 3_600_000
    state.recent_bwe_events = [e for e in state.recent_bwe_events if int(e.get("ts_ms") or 0) >= cutoff]


def process_pending(args: argparse.Namespace, state: RunnerState, specs_by_id: dict[str, StrategySpec], db: sqlite3.Connection, active: set[str]) -> None:
    current = now_ms()
    keep: list[dict[str, Any]] = []
    for item in state.pending_entries:
        due_ts_ms = int(item["due_ts_ms"])
        if due_ts_ms > current:
            keep.append(item)
            continue
        if current - due_ts_ms > int(args.max_entry_lag_seconds * 1000):
            spec = specs_by_id[item["strategy_id"]]
            event = BweEvent(**item["event"])
            ensure_stats(state, spec)["reject"] += 1
            inc_reason(state, "skip_pending_entry_expired")
            append_jsonl(args.state_dir / "decisions.jsonl", {"ts_ms": current, "strategy": spec.strategy_id, "symbol": event.symbol, "decision": "skip", "reason": "skip_pending_entry_expired", "due_ts_ms": due_ts_ms, "lag_ms": current - due_ts_ms})
            continue
        spec = specs_by_id[item["strategy_id"]]
        event = BweEvent(**item["event"])
        features = point_feature_snapshot(db, event.symbol, due_ts_ms)
        try:
            features, fallback_used = maybe_apply_binance_fallback(event, features, spec, args, current)
        except Exception as exc:
            ensure_stats(state, spec)["reject"] += 1
            state.api_failures += 1
            inc_reason(state, "skip_binance_fallback_failed")
            append_jsonl(args.state_dir / "errors.jsonl", {"ts_ms": current, "component": "binance_feature_fallback", "symbol": event.symbol, "strategy": spec.strategy_id, "error": str(exc)})
            continue
        if fallback_used:
            state.api_fallback_count += 1
            inc_reason(state, "binance_fallback_used")
            append_jsonl(args.state_dir / "decisions.jsonl", {"ts_ms": current, "strategy": spec.strategy_id, "symbol": event.symbol, "decision": "fallback", "fields": fallback_used, "features": asdict(features)})
        ok, reason = evaluate_long_strategy(event, features, spec, active)
        if not ok:
            ensure_stats(state, spec)["reject"] += 1
            inc_reason(state, reason)
            append_jsonl(args.state_dir / "decisions.jsonl", {"ts_ms": current, "strategy": spec.strategy_id, "symbol": event.symbol, "decision": "skip", "reason": reason, "features": asdict(features)})
            continue
        block_reason = portfolio_block_reason(state, spec, event.symbol, args, current)
        if block_reason:
            ensure_stats(state, spec)["reject"] += 1
            inc_reason(state, block_reason)
            continue
        open_position(args, state, spec, event.symbol, spec.side, event.ts_ms, due_ts_ms, spec.exit)
    state.pending_entries = keep


def count_open_strategy(state: RunnerState, strategy_id: str) -> int:
    return sum(1 for p in state.open_positions if p.strategy_id == strategy_id)


def component_pass(values: dict[str, Any], component: dict[str, Any]) -> tuple[bool, str]:
    entry = dict(component.get("entry") or {})
    trigger = entry.pop("trigger", "market")
    if trigger == "bwe60" and float(values.get("bwe_60m") or 0) < 1:
        return False, "skip_bwe60_missing"
    conditions = []
    field_map = {
        "vol_min": "qv_5m_ratio",
        "ret60_min": "ret_60m",
        "ret15_min": "ret_15m",
        "ret3_max": "ret_3m",
        "pullback60_max": "pullback_from_high_60m",
        "upper_wick_min": "upper_wick_pct",
        "body_ret_max": "body_ret_1m",
        "oi60_min": "oi_chg_60m",
        "top_position_min": "top_position_ratio",
        "taker_max": "taker_ratio",
    }
    for key, field_name in field_map.items():
        if key not in entry:
            continue
        op = ">=" if key.endswith("_min") else "<="
        conditions.append({"field": field_name, "op": op, "threshold": entry[key]})
    return evaluate_scanner_conditions(values, conditions)


def process_scanner(args: argparse.Namespace, state: RunnerState, specs: list[StrategySpec], db: sqlite3.Connection, active: set[str]) -> None:
    scanner_specs = [s for s in specs if s.trigger == "scanner"]
    if not scanner_specs:
        return
    current = now_ms()
    if state.scanner_last_run_ms and current - state.scanner_last_run_ms < int(args.scanner_seconds * 1000):
        return
    state.scanner_last_run_ms = current
    for symbol in sorted(active):
        bars = latest_bars(db, symbol, current)
        values = scanner_values(db, symbol, bars, state.recent_bwe_events)
        if not values:
            continue
        scan_ts = int(values["open_time_ms"])
        scan_bar_close_ts = scan_ts + 60_000
        if current - scan_bar_close_ts > int(args.scanner_max_bar_age_seconds * 1000):
            inc_reason(state, "skip_scanner_stale_bar")
            continue
        for spec in scanner_specs:
            key = f"{spec.strategy_id}:{symbol}"
            if state.scanner_cursor.get(key, 0) >= scan_ts:
                continue
            state.scanner_cursor[key] = scan_ts
            block_reason = portfolio_block_reason(state, spec, symbol, args, current)
            if block_reason:
                ensure_stats(state, spec)["reject"] += 1
                inc_reason(state, block_reason)
                continue
            if spec.components:
                chosen = None
                reason = "skip_no_component_pass"
                for component in spec.components:
                    ok, reason = component_pass(values, component)
                    if ok:
                        chosen = component
                        break
                if not chosen:
                    ensure_stats(state, spec)["reject"] += 1
                    inc_reason(state, reason)
                    continue
                open_position(args, state, spec, symbol, "short", scan_ts, scan_ts, chosen["exit"], component=str(chosen.get("label") or "component"))
                continue
            ok, reason = evaluate_scanner_conditions(values, spec.conditions)
            if not ok:
                ensure_stats(state, spec)["reject"] += 1
                inc_reason(state, reason)
                continue
            open_position(args, state, spec, symbol, "short", scan_ts, scan_ts, spec.exit)


def process_exits(args: argparse.Namespace, state: RunnerState, specs_by_id: dict[str, StrategySpec], db: sqlite3.Connection) -> None:
    current = now_ms()
    still: list[OpenPosition] = []
    for pos in state.open_positions:
        spec = specs_by_id[pos.strategy_id]
        bars = bars_after_entry(db, pos.symbol, pos.entry_ts_ms, current, int(pos.exit.get("horizon", spec.exit.get("horizon", 240))))
        closed = simulate_exit(pos, bars, spec)
        if closed is None:
            still.append(pos)
            continue
        if pos.mode == "demo_order":
            try:
                close_id, demo_px = close_demo_position(args, pos)
                closed.close_order_id = close_id
                closed.demo_exit_price = demo_px
                state.demo_close_orders_placed += 1
                if demo_px and pos.demo_entry_price:
                    closed.demo_pnl_pct = long_pnl(pos.demo_entry_price, demo_px) if pos.side == "long" else short_pnl(pos.demo_entry_price, demo_px)
                    state.demo_total_pnl_usdt += pos.notional_usdt * closed.demo_pnl_pct / 100.0
                append_jsonl(args.state_dir / "order_journal.jsonl", {"ts_ms": current, "kind": "close_ack", "closed_position": asdict(closed)})
            except Exception as exc:
                pos.close_attempts += 1
                state.demo_close_orders_failed += 1
                still.append(pos)
                append_jsonl(args.state_dir / "errors.jsonl", {"ts_ms": current, "component": "demo_close_order", "symbol": pos.symbol, "error": str(exc)})
                save_state(args.state_dir / "state.json", state)
                continue
        stats = ensure_stats(state, spec)
        stats["open"] = max(0, int(stats.get("open", 0)) - 1)
        stats["closed"] = int(stats.get("closed", 0)) + 1
        stats["wins"] = int(stats.get("wins", 0)) + (1 if closed.pnl_pct > 0 else 0)
        stats["sum_pct"] = float(stats.get("sum_pct", 0.0)) + closed.pnl_pct
        state.closed_positions.append(closed)
        append_jsonl(args.state_dir / "trades.jsonl", {"ts_ms": current, "action": "close", "position": asdict(closed)})
        save_state(args.state_dir / "state.json", state)
        # Telegram push on close
        try:
            notify(args, state, build_close_text(closed), "close")
        except Exception:
            pass
    state.open_positions = still


def _fmt_price(p: float) -> str:
    if p >= 100: return f"{p:.2f}"
    if p >= 1: return f"{p:.4f}"
    if p >= 0.01: return f"{p:.6f}"
    return f"{p:.8g}"


def build_open_text(pos: "OpenPosition", entry_delay_s: int = 0) -> str:
    """Telegram message when a position opens."""
    side_emoji = "🟢" if pos.side == "long" else "🔴"
    arrow = "↗︎ LONG" if pos.side == "long" else "↘︎ SHORT"
    delay_note = f" (event +{entry_delay_s}s)" if entry_delay_s else ""
    component_note = f"\n   ⚙️ component: {pos.component}" if pos.component else ""
    real_note = "🧪 demo_order" if pos.mode == "demo_order" else "📡 signal_only"
    return (
        f"{side_emoji} OPEN {pos.label} {arrow}\n"
        f"   💎 {pos.symbol}  @{_fmt_price(pos.entry_price)}\n"
        f"   📦 qty={pos.qty:.6g}  notional=${pos.notional_usdt:.2f}\n"
        f"   {real_note}{component_note}\n"
        f"   🕒 BWE {time.strftime('%H:%M:%S', time.localtime(pos.event_ts_ms/1000))}{delay_note}"
    )


def build_close_text(closed: "ClosedPosition") -> str:
    """Telegram message when a position closes."""
    pct = closed.pnl_pct
    pnl_usdt = closed.notional_usdt * pct / 100.0
    win_emoji = "✅" if pct > 0 else "❌" if pct < 0 else "➖"
    pnl_color = "🟢" if pct > 0 else "🔴" if pct < 0 else "⚪️"
    held_min = max(0, (closed.exit_ts_ms - closed.entry_ts_ms) // 60_000)
    component_note = f" ({closed.component})" if closed.component else ""
    return (
        f"{win_emoji} CLOSE {closed.label}{component_note}\n"
        f"   💎 {closed.symbol} {closed.side.upper()}\n"
        f"   📈 entry {_fmt_price(closed.entry_price)} → exit {_fmt_price(closed.exit_price)}\n"
        f"   {pnl_color} PnL {pct:+.2f}% (${pnl_usdt:+.2f})\n"
        f"   🚪 reason: {closed.reason}  ⏱️ held {held_min}min"
    )


def build_heartbeat(state: RunnerState, specs: list[StrategySpec], now_ms: int | None = None) -> str:
    ts = now_ms if now_ms is not None else globals()["now_ms"]()
    elapsed = max(0, ts - state.started_ts_ms)
    hours = elapsed // 3_600_000
    minutes = (elapsed % 3_600_000) // 60_000

    # Aggregate: total trades / WR / PnL across strategies
    total_pass = sum(int(s.get("pass", 0)) for s in state.by_strategy.values())
    total_closed = sum(int(s.get("closed", 0)) for s in state.by_strategy.values())
    total_wins = sum(int(s.get("wins", 0)) for s in state.by_strategy.values())
    total_sum_pct = sum(float(s.get("sum_pct", 0.0)) for s in state.by_strategy.values())
    overall_wr = (100 * total_wins / total_closed) if total_closed else 0.0
    mean_pct = (total_sum_pct / total_closed) if total_closed else 0.0

    # Top performer/loser by sum_pct
    perf = sorted(
        ((spec.label, float(state.by_strategy.get(spec.strategy_id, {}).get("sum_pct", 0.0)),
          int(state.by_strategy.get(spec.strategy_id, {}).get("closed", 0))) for spec in specs),
        key=lambda x: -x[1],
    )
    top_perf = next((p for p in perf if p[2] > 0), None)
    bot_perf = next((p for p in reversed(perf) if p[2] > 0), None)

    lines = [
        "📊 BWE Paper Heartbeat",
        f"⏱  uptime {hours}h{minutes:02d}m   📨 events {state.total_events_parsed}   ⏳ pending {len(state.pending_entries)}",
        f"📈 trades {total_closed}closed/{total_pass}pass | WR {overall_wr:.0f}% | mean {mean_pct:+.2f}% | sum {total_sum_pct:+.1f}%",
        f"💼 testnet ok {state.demo_orders_placed}+{state.demo_close_orders_placed}  fail {state.demo_orders_failed}+{state.demo_close_orders_failed}  💰 ${state.demo_total_pnl_usdt:+.2f}",
        f"🔌 API fails {state.api_failures}  fallback {state.api_fallback_count}  stale {state.skip_reasons.get('skip_scanner_stale_bar', 0)}",
    ]
    if top_perf:
        lines.append(f"🏆 best: {top_perf[0]} {top_perf[1]:+.2f}% ({top_perf[2]} trades)")
    if bot_perf and bot_perf != top_perf:
        lines.append(f"🥶 worst: {bot_perf[0]} {bot_perf[1]:+.2f}% ({bot_perf[2]} trades)")

    # Per-strategy table
    name_w = 22
    lines.append("")
    lines.append(f"{'strategy':<{name_w}} {'P':>4} {'O':>3} {'C':>4} {'WR':>4} {'sum%':>8}")
    lines.append("─" * (name_w + 26))
    for spec in specs:
        st = state.by_strategy.get(spec.strategy_id, {})
        closed = int(st.get("closed", 0))
        wins = int(st.get("wins", 0))
        wr = int(round(wins / closed * 100)) if closed else 0
        label = spec.label[:name_w]
        lines.append(
            f"{label:<{name_w}} "
            f"{int(st.get('pass', 0)):>4} "
            f"{int(st.get('open', 0)):>3} "
            f"{closed:>4} "
            f"{wr:>3}% "
            f"{float(st.get('sum_pct', 0.0)):>+8.1f}"
        )

    # Open positions (compact)
    if state.open_positions:
        lines.append("")
        lines.append(f"📦 Open ({len(state.open_positions)}):")
        for pos in state.open_positions[:15]:
            age_m = max(0, (ts - pos.entry_ts_ms) // 60_000)
            side_arrow = "↗" if pos.side == "long" else "↘"
            comp = f"·{pos.component}" if pos.component else ""
            lines.append(f"  {side_arrow} {pos.symbol:<14} {pos.label}{comp} @{_fmt_price(pos.entry_price)} ({age_m}m)")
        if len(state.open_positions) > 15:
            lines.append(f"  … and {len(state.open_positions) - 15} more")
    return "\n".join(lines)


def notify(args: argparse.Namespace, state: RunnerState, text: str, kind: str) -> None:
    append_jsonl(args.state_dir / "notifications.jsonl", {"ts_ms": now_ms(), "kind": kind, "text": text})
    if not args.telegram:
        return
    try:
        if send_telegram(text):
            state.notifications_sent += 1
    except Exception as exc:
        append_jsonl(args.state_dir / "errors.jsonl", {"ts_ms": now_ms(), "component": "telegram", "error": str(exc)})


def run_once(args: argparse.Namespace, state: RunnerState, specs: list[StrategySpec]) -> RunnerState:
    if args.start_at_end and state.cursor_byte == 0 and args.bwe_log.exists():
        state.cursor_byte = args.bwe_log.stat().st_size
    specs_by_id = {s.strategy_id: s for s in specs}
    with open_db(args.db) as db:
        active = load_active_symbols(db)
        process_bwe_posts(args, state, specs)
        process_pending(args, state, specs_by_id, db, active)
        if not args.disable_scanner:
            process_scanner(args, state, specs, db, active)
        process_exits(args, state, specs_by_id, db)
    save_state(args.state_dir / "state.json", state)
    return state


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["once", "loop"], default="once")
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    p.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    p.add_argument("--secret-env", type=Path, default=DEFAULT_SECRET_ENV)
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--bwe-log", type=Path, default=DEFAULT_BWE_LOG)
    p.add_argument("--price-base-url", default=DEFAULT_PRICE_BASE_URL)
    p.add_argument("--demo-base-url", default=DEFAULT_DEMO_BASE_URL)
    p.add_argument("--notional-usdt", type=float, default=None)
    p.add_argument("--max-concurrent-total", type=int, default=None)
    p.add_argument("--max-concurrent-per-strategy", type=int, default=None)
    p.add_argument("--one-position-per-symbol", action=argparse.BooleanOptionalAction, default=None)
    p.add_argument("--same-strategy-symbol-cooldown-min", type=float, default=None)
    p.add_argument("--poll-seconds", type=float, default=10.0)
    p.add_argument("--scanner-seconds", type=float, default=60.0)
    p.add_argument("--scanner-max-bar-age-seconds", type=float, default=180.0)
    p.add_argument("--max-entry-lag-seconds", type=float, default=45.0)
    p.add_argument("--enable-binance-fallback", action=argparse.BooleanOptionalAction, default=None)
    p.add_argument("--fallback-timeout-seconds", type=float, default=None)
    p.add_argument("--ticker-max-age-ms", type=int, default=None)
    p.add_argument("--heartbeat-seconds", type=float, default=3600.0)
    p.add_argument("--heartbeat-now", action="store_true")
    p.add_argument("--start-at-end", action="store_true")
    p.add_argument("--demo-orders", action="store_true")
    p.add_argument("--allow-non-reduce-close", action="store_true")
    p.add_argument("--telegram", action="store_true")
    p.add_argument("--telegram-test", action="store_true")
    p.add_argument("--disable-scanner", action="store_true")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    load_env_file(args.secret_env)
    args.state_dir.mkdir(parents=True, exist_ok=True)
    specs = load_strategy_specs(args.config)
    portfolio = load_portfolio(args.config)
    args.notional_usdt = float(args.notional_usdt if args.notional_usdt is not None else portfolio.get("notional_usdt", 10))
    args.max_concurrent_total = int(args.max_concurrent_total if args.max_concurrent_total is not None else portfolio.get("max_concurrent_total", 16))
    args.max_concurrent_per_strategy = int(args.max_concurrent_per_strategy if args.max_concurrent_per_strategy is not None else portfolio.get("max_concurrent_per_strategy", 5))
    args.one_position_per_symbol = bool(args.one_position_per_symbol if args.one_position_per_symbol is not None else portfolio.get("one_position_per_symbol", False))
    args.same_strategy_symbol_cooldown_min = float(args.same_strategy_symbol_cooldown_min if args.same_strategy_symbol_cooldown_min is not None else portfolio.get("same_strategy_symbol_cooldown_min", 0))
    args.enable_binance_fallback = bool(args.enable_binance_fallback if args.enable_binance_fallback is not None else portfolio.get("enable_binance_fallback", True))
    args.fallback_timeout_seconds = float(args.fallback_timeout_seconds if args.fallback_timeout_seconds is not None else portfolio.get("fallback_timeout_seconds", 5.0))
    args.ticker_max_age_ms = int(args.ticker_max_age_ms if args.ticker_max_age_ms is not None else portfolio.get("ticker_max_age_ms", 600_000))
    state = load_state(args.state_dir / "state.json")
    if recover_from_order_journal(args.state_dir, state, specs):
        save_state(args.state_dir / "state.json", state)
    if args.demo_orders:
        credentials()
    if args.telegram_test:
        ok = send_telegram(build_heartbeat(state, specs))
        append_jsonl(args.state_dir / "notifications.jsonl", {"ts_ms": now_ms(), "kind": "telegram_test", "sent": bool(ok), "text": build_heartbeat(state, specs)})
        print(json.dumps({"telegram_test_sent": bool(ok)}, indent=2))
        return 0 if ok else 2
    if args.mode == "once":
        state = run_once(args, state, specs)
        if args.heartbeat_now:
            msg = build_heartbeat(state, specs)
            notify(args, state, msg, "heartbeat")
            save_state(args.state_dir / "state.json", state)
        print(json.dumps({"status": "ok", "open": len(state.open_positions), "pending": len(state.pending_entries), "heartbeat": build_heartbeat(state, specs)}, ensure_ascii=False, indent=2))
        return 0
    last_heartbeat = 0.0
    print(json.dumps({"ts_ms": now_ms(), "event": "loop_start", "state_dir": str(args.state_dir), "telegram": bool(args.telegram), "demo_orders": bool(args.demo_orders)}, ensure_ascii=False), flush=True)
    while True:
        loop_started = time.time()
        try:
            state = run_once(args, state, specs)
            t = time.time()
            if args.heartbeat_now or t - last_heartbeat >= args.heartbeat_seconds:
                notify(args, state, build_heartbeat(state, specs), "heartbeat")
                save_state(args.state_dir / "state.json", state)
                last_heartbeat = t
                args.heartbeat_now = False
            print(json.dumps({"ts_ms": now_ms(), "event": "loop_ok", "duration_s": round(time.time() - loop_started, 3), "events": state.total_events_parsed, "pending": len(state.pending_entries), "open": len(state.open_positions), "closed": len(state.closed_positions), "api_failures": state.api_failures, "demo_orders_ok": state.demo_orders_placed + state.demo_close_orders_placed, "demo_orders_failed": state.demo_orders_failed + state.demo_close_orders_failed}, ensure_ascii=False), flush=True)
        except KeyboardInterrupt:
            save_state(args.state_dir / "state.json", state)
            raise
        except Exception as exc:
            append_jsonl(args.state_dir / "errors.jsonl", {"ts_ms": now_ms(), "component": "loop", "error": str(exc)})
            save_state(args.state_dir / "state.json", state)
            print(json.dumps({"ts_ms": now_ms(), "event": "loop_error", "error": str(exc)}, ensure_ascii=False), flush=True)
        time.sleep(max(1.0, args.poll_seconds))


if __name__ == "__main__":
    raise SystemExit(main())
