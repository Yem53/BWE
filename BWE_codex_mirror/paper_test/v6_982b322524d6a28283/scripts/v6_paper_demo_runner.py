#!/usr/bin/env python3
"""Codex-owned paper/demo runner for BWE strategy v6_982b322524d6a28283.

Writes only under /Volumes/T9/BWE_codex. Secrets are read from environment
variables at runtime and are never persisted.
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
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


CODEX_ROOT = Path("/Volumes/T9/BWE_codex")
RUN_ROOT = CODEX_ROOT / "paper_test/v6_982b322524d6a28283"
DEFAULT_STATE_DIR = RUN_ROOT / "runtime"
DEFAULT_BWE_LOG = Path("/Volumes/T9_HOT/bwe_logs/bwe_matrix_posts.jsonl")
DEFAULT_DB = Path("/Volumes/T9_HOT/binance_collectors_runtime/binance_futures_1m.sqlite3")
DEFAULT_PRICE_BASE_URL = "https://fapi.binance.com"
DEFAULT_DEMO_BASE_URL = "https://testnet.binancefuture.com"


@dataclass(frozen=True)
class StrategyConfig:
    strategy_id: str = "v6_982b322524d6a28283"
    family: str = "liquidity_filtered_momentum"
    trigger_source: str = "BWE_event_stream"
    event_type: str = "pump"
    side: str = "long"
    entry_delay_s: int = 180
    marketcap_max: float = 71_000_000.0
    top_ratio_min: float = 2.2404000759124756
    global_ratio_min: float = 1.6828899383544922
    max_feature_age_ms: int = 10 * 60 * 1000
    sl_pct: float = 0.05
    failed_check_min: int = 10
    failed_threshold_fraction_of_sl: float = 0.35
    max_hold_min: int = 240
    max_concurrent_positions: int = 5
    one_position_per_symbol: bool = True


@dataclass
class BweEvent:
    ts_ms: int
    source: str
    post_id: str
    text: str
    symbol: str
    event_type: str
    marketcap: float | None


@dataclass
class FeatureSnapshot:
    top_ratio: float | None
    top_ratio_age_ms: int | None
    global_ratio: float | None
    global_ratio_age_ms: int | None


@dataclass
class PendingEntry:
    event: BweEvent
    due_ts_ms: int


@dataclass
class OpenPosition:
    strategy_id: str
    symbol: str
    side: str
    event_ts_ms: int
    due_ts_ms: int
    entry_ts_ms: int
    entry_price: float
    qty: float
    mode: str
    notional_usdt: float = 0.0
    top_ratio: float | None = None
    global_ratio: float | None = None
    marketcap: float | None = None
    order_id: str | None = None
    demo_entry_price: float | None = None
    close_attempts: int = 0


@dataclass
class ClosedPosition:
    strategy_id: str
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
    order_id: str | None = None
    close_order_id: str | None = None
    demo_entry_price: float | None = None
    demo_exit_price: float | None = None
    demo_pnl_pct: float | None = None


@dataclass
class Bar:
    open_time_ms: int
    open: float
    high: float
    low: float
    close: float


@dataclass
class RunnerState:
    started_ts_ms: int
    cursor_byte: int = 0
    total_posts_seen: int = 0
    total_events_parsed: int = 0
    pending_entries: list[PendingEntry] = field(default_factory=list)
    open_positions: list[OpenPosition] = field(default_factory=list)
    closed_positions: list[ClosedPosition] = field(default_factory=list)
    skip_reasons: dict[str, int] = field(default_factory=dict)
    demo_orders_placed: int = 0
    demo_orders_failed: int = 0
    notifications_sent: int = 0


_MC_RE = re.compile(r"MarketCap:\s*\$?\s*([0-9]+(?:\.[0-9]+)?)\s*([KMBT]?)", re.I)
_SYMBOL_RE = re.compile(r"\b([A-Z0-9]{2,30}USDT)\b")
_POSITIVE_RE = re.compile(r"(?<![A-Za-z0-9])\+\s*([0-9]+(?:\.[0-9]+)?)\s*%")
_NEGATIVE_RE = re.compile(r"(?<![A-Za-z0-9])-\s*([0-9]+(?:\.[0-9]+)?)\s*%")
_MC_MULT = {"": 1.0, "K": 1_000.0, "M": 1_000_000.0, "B": 1_000_000_000.0, "T": 1_000_000_000_000.0}


def now_ms() -> int:
    return int(time.time() * 1000)


def iso_ms(ts_ms: int) -> str:
    return dt.datetime.fromtimestamp(ts_ms / 1000, tz=dt.timezone.utc).isoformat()


def parse_marketcap(text: str) -> float | None:
    match = _MC_RE.search(text)
    if not match:
        return None
    return float(match.group(1)) * _MC_MULT.get(match.group(2).upper(), 1.0)


def parse_bwe_post(raw: dict[str, Any]) -> BweEvent | None:
    text = str(raw.get("text") or "")
    symbol_match = _SYMBOL_RE.search(text)
    if not symbol_match:
        return None
    if _POSITIVE_RE.search(text) or "上涨" in text:
        event_type = "pump"
    elif _NEGATIVE_RE.search(text) or "下跌" in text:
        event_type = "dump"
    else:
        return None
    return BweEvent(
        ts_ms=int(raw.get("ts_ms") or 0),
        source=str(raw.get("source") or ""),
        post_id=str(raw.get("post_id") or ""),
        text=text,
        symbol=symbol_match.group(1),
        event_type=event_type,
        marketcap=parse_marketcap(text),
    )


def evaluate_entry(
    event: BweEvent,
    features: FeatureSnapshot,
    cfg: StrategyConfig,
    active_symbols: set[str],
) -> tuple[bool, str]:
    if event.event_type != cfg.event_type:
        return False, "skip_not_pump"
    if event.symbol not in active_symbols:
        return False, "skip_not_active_usdt_perp"
    if event.marketcap is None:
        return False, "skip_missing_marketcap"
    if event.marketcap > cfg.marketcap_max:
        return False, "skip_marketcap_above_threshold"
    if features.top_ratio is None:
        return False, "skip_missing_top_ratio"
    if features.top_ratio_age_ms is None or features.top_ratio_age_ms > cfg.max_feature_age_ms:
        return False, "skip_top_ratio_stale"
    if features.top_ratio < cfg.top_ratio_min:
        return False, "skip_top_ratio_below_threshold"
    if features.global_ratio is None:
        return False, "skip_missing_global_ratio"
    if features.global_ratio_age_ms is None or features.global_ratio_age_ms > cfg.max_feature_age_ms:
        return False, "skip_global_ratio_stale"
    if features.global_ratio < cfg.global_ratio_min:
        return False, "skip_global_ratio_below_threshold"
    return True, "entry_pass"


def simulate_failed_continuation_exit(
    pos: OpenPosition,
    bars: list[Bar],
    cfg: StrategyConfig,
) -> ClosedPosition | None:
    if not bars:
        return None
    entry = pos.entry_price
    if entry <= 0:
        return None
    stop_price = entry * (1.0 - cfg.sl_pct)
    proof_checked = False
    max_bars = min(len(bars), cfg.max_hold_min)
    for idx in range(max_bars):
        bar = bars[idx]
        hold_min = idx + 1
        if bar.low <= stop_price:
            return ClosedPosition(
                strategy_id=pos.strategy_id,
                symbol=pos.symbol,
                side=pos.side,
                event_ts_ms=pos.event_ts_ms,
                entry_ts_ms=pos.entry_ts_ms,
                exit_ts_ms=bar.open_time_ms,
                entry_price=entry,
                exit_price=stop_price,
                pnl_pct=-cfg.sl_pct * 100.0,
                reason="initial_stop",
                mode=pos.mode,
                qty=pos.qty,
                notional_usdt=pos.notional_usdt,
                order_id=pos.order_id,
                demo_entry_price=pos.demo_entry_price,
            )
        if not proof_checked and hold_min >= cfg.failed_check_min:
            proof_checked = True
            close_ret = bar.close / entry - 1.0
            if close_ret < -cfg.sl_pct * cfg.failed_threshold_fraction_of_sl:
                return ClosedPosition(
                    strategy_id=pos.strategy_id,
                    symbol=pos.symbol,
                    side=pos.side,
                    event_ts_ms=pos.event_ts_ms,
                    entry_ts_ms=pos.entry_ts_ms,
                    exit_ts_ms=bar.open_time_ms,
                    entry_price=entry,
                    exit_price=bar.close,
                    pnl_pct=close_ret * 100.0,
                    reason="failed_continuation_exit",
                    mode=pos.mode,
                    qty=pos.qty,
                    notional_usdt=pos.notional_usdt,
                    order_id=pos.order_id,
                    demo_entry_price=pos.demo_entry_price,
                )
    if len(bars) >= cfg.max_hold_min:
        bar = bars[cfg.max_hold_min - 1]
        pnl_pct = (bar.close / entry - 1.0) * 100.0
        return ClosedPosition(
            strategy_id=pos.strategy_id,
            symbol=pos.symbol,
            side=pos.side,
            event_ts_ms=pos.event_ts_ms,
            entry_ts_ms=pos.entry_ts_ms,
            exit_ts_ms=bar.open_time_ms,
            entry_price=entry,
            exit_price=bar.close,
            pnl_pct=pnl_pct,
            reason="time_exit",
            mode=pos.mode,
            qty=pos.qty,
            notional_usdt=pos.notional_usdt,
            order_id=pos.order_id,
            demo_entry_price=pos.demo_entry_price,
        )
    return None


def round_step(qty: float, step_size: float, min_qty: float, precision: int) -> float | None:
    if qty <= 0 or step_size <= 0:
        return None
    rounded = math.floor(qty / step_size) * step_size
    rounded = round(rounded, precision)
    if rounded < min_qty:
        return None
    return rounded


def fmt_usd(value: float | None) -> str:
    if value is None:
        return "NA"
    if abs(value) >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}B"
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    if abs(value) >= 1_000:
        return f"{value / 1_000:.2f}K"
    return f"{value:.2f}"


def build_open_message(
    cfg: StrategyConfig,
    *,
    symbol: str,
    mode: str,
    entry_price: float,
    qty: float,
    notional: float,
    top_ratio: float,
    global_ratio: float,
    marketcap: float,
    order_id: str | None,
) -> str:
    order_part = f" order={order_id}" if order_id else ""
    return (
        f"BWE paper OPEN {cfg.strategy_id}\n"
        f"{symbol} LONG {mode}{order_part}\n"
        f"entry={entry_price:.8g} qty={qty:.8g} notional={notional:.2f} USDT\n"
        f"mc={fmt_usd(marketcap)} topLS={top_ratio:.3f} globalLS={global_ratio:.3f}\n"
        f"exit=failed_continuation sl={cfg.sl_pct * 100:.2f}% check={cfg.failed_check_min}m max={cfg.max_hold_min}m"
    )


def build_exit_message(closed: ClosedPosition) -> str:
    demo = ""
    if closed.demo_exit_price is not None:
        demo = f" demo_exit={closed.demo_exit_price:.8g}"
    return (
        f"BWE paper EXIT {closed.strategy_id}\n"
        f"{closed.symbol} {closed.side.upper()} reason={closed.reason}\n"
        f"model_exit={closed.exit_price:.8g}{demo} pnl={closed.pnl_pct:.2f}%\n"
        f"entry_utc={iso_ms(closed.entry_ts_ms)} exit_utc={iso_ms(closed.exit_ts_ms)}"
    )


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def inc_reason(state: RunnerState, reason: str) -> None:
    state.skip_reasons[reason] = state.skip_reasons.get(reason, 0) + 1


def state_to_dict(state: RunnerState) -> dict[str, Any]:
    return {
        "started_ts_ms": state.started_ts_ms,
        "cursor_byte": state.cursor_byte,
        "total_posts_seen": state.total_posts_seen,
        "total_events_parsed": state.total_events_parsed,
        "pending_entries": [
            {"event": asdict(p.event), "due_ts_ms": p.due_ts_ms} for p in state.pending_entries
        ],
        "open_positions": [asdict(p) for p in state.open_positions],
        "closed_positions": [asdict(p) for p in state.closed_positions[-200:]],
        "skip_reasons": state.skip_reasons,
        "demo_orders_placed": state.demo_orders_placed,
        "demo_orders_failed": state.demo_orders_failed,
        "notifications_sent": state.notifications_sent,
    }


def state_from_dict(raw: dict[str, Any]) -> RunnerState:
    state = RunnerState(
        started_ts_ms=int(raw.get("started_ts_ms") or now_ms()),
        cursor_byte=int(raw.get("cursor_byte") or 0),
        total_posts_seen=int(raw.get("total_posts_seen") or 0),
        total_events_parsed=int(raw.get("total_events_parsed") or 0),
        skip_reasons=dict(raw.get("skip_reasons") or {}),
        demo_orders_placed=int(raw.get("demo_orders_placed") or 0),
        demo_orders_failed=int(raw.get("demo_orders_failed") or 0),
        notifications_sent=int(raw.get("notifications_sent") or 0),
    )
    for item in raw.get("pending_entries") or []:
        state.pending_entries.append(PendingEntry(event=BweEvent(**item["event"]), due_ts_ms=int(item["due_ts_ms"])))
    for item in raw.get("open_positions") or []:
        state.open_positions.append(OpenPosition(**item))
    for item in raw.get("closed_positions") or []:
        state.closed_positions.append(ClosedPosition(**item))
    return state


def load_state(path: Path) -> RunnerState:
    if not path.exists():
        return RunnerState(started_ts_ms=now_ms())
    return state_from_dict(json.loads(path.read_text(encoding="utf-8")))


def save_state(path: Path, state: RunnerState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state_to_dict(state), indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def open_db(db_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=30)


def load_active_symbols(db: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in db.execute(
            "SELECT symbol FROM symbol_meta WHERE status='TRADING' AND quote_asset='USDT' AND contract_type='PERPETUAL'"
        )
    }


def ratio_at(db: sqlite3.Connection, table: str, symbol: str, ts_ms: int) -> tuple[float | None, int | None]:
    row = db.execute(
        f"SELECT ts_ms, long_short_ratio FROM {table} WHERE symbol=? AND ts_ms<=? ORDER BY ts_ms DESC LIMIT 1",
        (symbol, ts_ms),
    ).fetchone()
    if not row:
        return None, None
    row_ts = int(row[0])
    value = float(row[1])
    return value, max(0, ts_ms - row_ts)


def feature_snapshot(db: sqlite3.Connection, symbol: str, ts_ms: int) -> FeatureSnapshot:
    top, top_age = ratio_at(db, "top_trader_long_short_account_ratio_5m", symbol, ts_ms)
    global_ratio, global_age = ratio_at(db, "global_long_short_account_ratio_5m", symbol, ts_ms)
    return FeatureSnapshot(
        top_ratio=top,
        top_ratio_age_ms=top_age,
        global_ratio=global_ratio,
        global_ratio_age_ms=global_age,
    )


def bars_after_entry(db: sqlite3.Connection, symbol: str, entry_ts_ms: int, current_ts_ms: int, limit: int) -> list[Bar]:
    rows = db.execute(
        "SELECT open_time_ms, open, high, low, close FROM klines_1m "
        "WHERE symbol=? AND open_time_ms>? AND close_time_ms<=? "
        "ORDER BY open_time_ms LIMIT ?",
        (symbol, entry_ts_ms, current_ts_ms - 5_000, limit),
    ).fetchall()
    return [
        Bar(open_time_ms=int(r[0]), open=float(r[1]), high=float(r[2]), low=float(r[3]), close=float(r[4]))
        for r in rows
    ]


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
    last_newline = chunk.rfind(b"\n")
    if last_newline < 0:
        return [], cursor_byte
    complete = chunk[: last_newline + 1]
    new_cursor = cursor_byte + len(complete)
    return [ln for ln in complete.decode("utf-8", errors="replace").splitlines() if ln.strip()], new_cursor


def request_json(url: str, *, method: str = "GET", body: bytes | None = None, headers: dict[str, str] | None = None, timeout: float = 10.0) -> Any:
    req = urllib.request.Request(url, data=body, headers=headers or {"User-Agent": "BWE-Codex-Paper/1.0"}, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def get_mark_price(symbol: str, base_url: str = DEFAULT_PRICE_BASE_URL) -> float:
    url = f"{base_url.rstrip('/')}/fapi/v1/premiumIndex?{urllib.parse.urlencode({'symbol': symbol})}"
    data = request_json(url)
    return float(data["markPrice"])


def credentials() -> tuple[str, str]:
    api_key = os.getenv("BINANCE_DEMO_API_KEY") or os.getenv("BINANCE_TESTNET_API_KEY")
    secret = os.getenv("BINANCE_DEMO_API_SECRET") or os.getenv("BINANCE_TESTNET_SECRET")
    if not api_key or not secret:
        raise RuntimeError("Binance demo/testnet credentials are not present in env")
    return api_key, secret


def signed_request(base_url: str, method: str, path: str, params: dict[str, Any] | None = None, timeout: float = 10.0) -> dict[str, Any] | list[Any]:
    api_key, secret = credentials()
    payload = dict(params or {})
    payload["timestamp"] = now_ms()
    payload["recvWindow"] = 5000
    query = urllib.parse.urlencode(payload)
    signature = hmac.new(secret.encode("utf-8"), query.encode("utf-8"), hashlib.sha256).hexdigest()
    full_query = f"{query}&signature={signature}"
    headers = {
        "X-MBX-APIKEY": api_key,
        "User-Agent": "BWE-Codex-Paper/1.0",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    if method == "GET":
        url = f"{base_url.rstrip('/')}{path}?{full_query}"
        return request_json(url, headers=headers, timeout=timeout)
    url = f"{base_url.rstrip('/')}{path}"
    return request_json(url, method=method, body=full_query.encode("utf-8"), headers=headers, timeout=timeout)


def demo_exchange_filters(symbol: str, base_url: str) -> dict[str, Any] | None:
    url = f"{base_url.rstrip('/')}/fapi/v1/exchangeInfo?{urllib.parse.urlencode({'symbol': symbol})}"
    data = request_json(url)
    symbols = data.get("symbols") or []
    if not symbols:
        return None
    raw = symbols[0]
    filters = {f["filterType"]: f for f in raw.get("filters", [])}
    lot = filters.get("LOT_SIZE", {})
    min_notional = filters.get("MIN_NOTIONAL", {})
    return {
        "stepSize": float(lot.get("stepSize", "0.001")),
        "minQty": float(lot.get("minQty", "0")),
        "quantityPrecision": int(raw.get("quantityPrecision", 3)),
        "minNotional": float(min_notional.get("notional", "5")),
    }


def qty_for_notional(symbol: str, price: float, notional: float, demo_base_url: str) -> float | None:
    filters = demo_exchange_filters(symbol, demo_base_url)
    if not filters or price <= 0:
        return None
    qty = round_step(notional / price, filters["stepSize"], filters["minQty"], filters["quantityPrecision"])
    if qty is None:
        return None
    if qty * price < filters["minNotional"]:
        return None
    return qty


def place_demo_market_order(symbol: str, side: str, qty: float, demo_base_url: str, reduce_only: bool) -> dict[str, Any]:
    params: dict[str, Any] = {
        "symbol": symbol,
        "side": side.upper(),
        "type": "MARKET",
        "quantity": qty,
        "newOrderRespType": "RESULT",
    }
    if reduce_only:
        params["reduceOnly"] = "true"
    data = signed_request(demo_base_url, "POST", "/fapi/v1/order", params)
    if not isinstance(data, dict):
        raise RuntimeError("demo order response was not an object")
    return data


def send_telegram(text: str, token_env: str, chat_id_env: str) -> bool:
    token = os.getenv(token_env) or os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv(chat_id_env) or os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False
    body = json.dumps(
        {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
    ).encode("utf-8")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.status == 200


def discover_telegram_chats(token_env: str) -> list[dict[str, Any]]:
    token = os.getenv(token_env) or os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Telegram token env is not set")
    data = request_json(f"https://api.telegram.org/bot{token}/getUpdates")
    chats = []
    seen: set[str] = set()
    for item in data.get("result") or []:
        message = item.get("message") or item.get("channel_post") or {}
        chat = message.get("chat") or {}
        if "id" not in chat:
            continue
        key = str(chat["id"])
        if key in seen:
            continue
        seen.add(key)
        chats.append({"id": chat.get("id"), "type": chat.get("type"), "title": chat.get("title"), "username": chat.get("username")})
    return chats


def notify(args: argparse.Namespace, state: RunnerState, text: str) -> None:
    append_jsonl(args.state_dir / "notifications.jsonl", {"ts_ms": now_ms(), "text": text})
    if not args.telegram:
        return
    try:
        if send_telegram(text, args.telegram_token_env, args.telegram_chat_id_env):
            state.notifications_sent += 1
    except Exception as exc:
        append_jsonl(args.state_dir / "errors.jsonl", {"ts_ms": now_ms(), "component": "telegram", "error": str(exc)})


def process_new_posts(args: argparse.Namespace, state: RunnerState, cfg: StrategyConfig) -> None:
    lines, cursor = read_new_lines(args.bwe_log, state.cursor_byte)
    state.cursor_byte = cursor
    for line in lines:
        state.total_posts_seen += 1
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            inc_reason(state, "skip_bad_json")
            continue
        event = parse_bwe_post(raw)
        if event is None:
            inc_reason(state, "skip_not_bwe_price_event")
            continue
        state.total_events_parsed += 1
        append_jsonl(args.state_dir / "events.jsonl", {"ts_ms": now_ms(), "event": asdict(event)})
        if event.event_type != cfg.event_type:
            inc_reason(state, "skip_not_pump")
            continue
        pending = PendingEntry(event=event, due_ts_ms=event.ts_ms + cfg.entry_delay_s * 1000)
        state.pending_entries.append(pending)


def has_open_symbol(state: RunnerState, symbol: str) -> bool:
    return any(p.symbol == symbol for p in state.open_positions)


def process_pending(args: argparse.Namespace, state: RunnerState, cfg: StrategyConfig, db: sqlite3.Connection, active_symbols: set[str]) -> None:
    current = now_ms()
    remaining: list[PendingEntry] = []
    for pending in state.pending_entries:
        if pending.due_ts_ms > current:
            remaining.append(pending)
            continue
        event = pending.event
        if cfg.one_position_per_symbol and has_open_symbol(state, event.symbol):
            inc_reason(state, "skip_symbol_already_open")
            continue
        if len(state.open_positions) >= cfg.max_concurrent_positions:
            inc_reason(state, "skip_max_concurrent_positions")
            remaining.append(pending)
            continue
        features = feature_snapshot(db, event.symbol, pending.due_ts_ms)
        ok, reason = evaluate_entry(event, features, cfg, active_symbols)
        if not ok:
            inc_reason(state, reason)
            append_jsonl(args.state_dir / "decisions.jsonl", {"ts_ms": current, "symbol": event.symbol, "decision": "skip", "reason": reason, "event": asdict(event), "features": asdict(features)})
            continue
        try:
            entry_price = get_mark_price(event.symbol, args.price_base_url)
        except Exception as exc:
            inc_reason(state, "skip_mark_price_unavailable")
            append_jsonl(args.state_dir / "errors.jsonl", {"ts_ms": current, "component": "mark_price", "symbol": event.symbol, "error": str(exc)})
            continue
        qty = args.notional_usdt / entry_price
        order_id: str | None = None
        demo_entry_price: float | None = None
        mode = "signal_only"
        if args.demo_orders:
            mode = "demo_order"
            demo_qty = qty_for_notional(event.symbol, entry_price, args.notional_usdt, args.demo_base_url)
            if demo_qty is None:
                state.demo_orders_failed += 1
                inc_reason(state, "skip_demo_qty_or_symbol_unavailable")
                append_jsonl(args.state_dir / "decisions.jsonl", {"ts_ms": current, "symbol": event.symbol, "decision": "skip", "reason": "skip_demo_qty_or_symbol_unavailable"})
                continue
            qty = demo_qty
            try:
                order = place_demo_market_order(event.symbol, "BUY", qty, args.demo_base_url, reduce_only=False)
                order_id = str(order.get("orderId") or "")
                fill_qty = float(order.get("executedQty") or qty)
                fill_price = float(order.get("avgPrice") or 0.0)
                if fill_price > 0:
                    entry_price = fill_price
                    demo_entry_price = fill_price
                qty = fill_qty if fill_qty > 0 else qty
                state.demo_orders_placed += 1
            except Exception as exc:
                state.demo_orders_failed += 1
                inc_reason(state, "skip_demo_order_failed")
                append_jsonl(args.state_dir / "errors.jsonl", {"ts_ms": current, "component": "demo_open_order", "symbol": event.symbol, "error": str(exc)})
                continue
        pos = OpenPosition(
            strategy_id=cfg.strategy_id,
            symbol=event.symbol,
            side=cfg.side,
            event_ts_ms=event.ts_ms,
            due_ts_ms=pending.due_ts_ms,
            entry_ts_ms=current,
            entry_price=entry_price,
            qty=qty,
            mode=mode,
            notional_usdt=qty * entry_price,
            top_ratio=features.top_ratio,
            global_ratio=features.global_ratio,
            marketcap=event.marketcap,
            order_id=order_id,
            demo_entry_price=demo_entry_price,
        )
        state.open_positions.append(pos)
        append_jsonl(args.state_dir / "trades.jsonl", {"ts_ms": current, "action": "open", "position": asdict(pos)})
        notify(
            args,
            state,
            build_open_message(
                cfg,
                symbol=event.symbol,
                mode=mode,
                entry_price=entry_price,
                qty=qty,
                notional=qty * entry_price,
                top_ratio=float(features.top_ratio),
                global_ratio=float(features.global_ratio),
                marketcap=float(event.marketcap),
                order_id=order_id,
            ),
        )
    state.pending_entries = remaining


def close_demo_position(args: argparse.Namespace, pos: OpenPosition) -> tuple[str | None, float | None]:
    if not pos.order_id:
        return None, None
    order = place_demo_market_order(
        pos.symbol,
        "SELL",
        pos.qty,
        args.demo_base_url,
        reduce_only=not args.allow_non_reduce_close,
    )
    order_id = str(order.get("orderId") or "")
    avg_price = float(order.get("avgPrice") or 0.0)
    return order_id, avg_price if avg_price > 0 else None


def process_exits(args: argparse.Namespace, state: RunnerState, cfg: StrategyConfig, db: sqlite3.Connection) -> None:
    current = now_ms()
    still_open: list[OpenPosition] = []
    for pos in state.open_positions:
        bars = bars_after_entry(db, pos.symbol, pos.entry_ts_ms, current, cfg.max_hold_min)
        closed = simulate_failed_continuation_exit(pos, bars, cfg)
        if closed is None:
            still_open.append(pos)
            continue
        if pos.mode == "demo_order":
            try:
                close_order_id, demo_exit_price = close_demo_position(args, pos)
                closed.close_order_id = close_order_id
                closed.demo_exit_price = demo_exit_price
                if demo_exit_price and pos.demo_entry_price:
                    closed.demo_pnl_pct = (demo_exit_price / pos.demo_entry_price - 1.0) * 100.0
            except Exception as exc:
                pos.close_attempts += 1
                still_open.append(pos)
                append_jsonl(args.state_dir / "errors.jsonl", {"ts_ms": current, "component": "demo_close_order", "symbol": pos.symbol, "error": str(exc), "close_attempts": pos.close_attempts})
                continue
        state.closed_positions.append(closed)
        append_jsonl(args.state_dir / "trades.jsonl", {"ts_ms": current, "action": "close", "position": asdict(closed)})
        notify(args, state, build_exit_message(closed))
    state.open_positions = still_open


def run_once(args: argparse.Namespace, state: RunnerState, cfg: StrategyConfig) -> RunnerState:
    if args.start_at_end and state.cursor_byte == 0 and args.bwe_log.exists():
        state.cursor_byte = args.bwe_log.stat().st_size
    with open_db(args.db) as db:
        active_symbols = load_active_symbols(db)
        process_new_posts(args, state, cfg)
        process_pending(args, state, cfg, db, active_symbols)
        process_exits(args, state, cfg, db)
    save_state(args.state_dir / "state.json", state)
    return state


def build_status_message(state: RunnerState, cfg: StrategyConfig, args: argparse.Namespace) -> str:
    return (
        f"BWE paper status {cfg.strategy_id}\n"
        f"mode={'demo_order' if args.demo_orders else 'signal_only'} trigger=BWE entry_delay={cfg.entry_delay_s}s\n"
        f"pending={len(state.pending_entries)} open={len(state.open_positions)} closed={len(state.closed_positions)} "
        f"demo_orders={state.demo_orders_placed}/{state.demo_orders_failed}\n"
        f"mc_gate<=71M missing_mc_skips={state.skip_reasons.get('skip_missing_marketcap', 0)}"
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["once", "loop"], default="once")
    parser.add_argument("--bwe-log", type=Path, default=DEFAULT_BWE_LOG)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    parser.add_argument("--start-at-end", action="store_true", help="Initialize cursor at current end of BWE log")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument("--notional-usdt", type=float, default=10.0)
    parser.add_argument("--price-base-url", default=os.getenv("BINANCE_PRICE_BASE_URL", DEFAULT_PRICE_BASE_URL))
    parser.add_argument("--demo-base-url", default=os.getenv("BINANCE_DEMO_BASE_URL", DEFAULT_DEMO_BASE_URL))
    parser.add_argument("--demo-orders", action="store_true", help="Place real Binance futures demo/testnet orders")
    parser.add_argument("--allow-non-reduce-close", action="store_true", help="Allow close order without reduceOnly if reduceOnly is incompatible")
    parser.add_argument("--telegram", action="store_true")
    parser.add_argument("--telegram-test", action="store_true")
    parser.add_argument("--discover-telegram-chat-id", action="store_true")
    parser.add_argument("--telegram-token-env", default="BWE_TRADE_TEST_BOT_TOKEN")
    parser.add_argument("--telegram-chat-id-env", default="BWE_TRADE_TEST_CHAT_ID")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    args.state_dir.mkdir(parents=True, exist_ok=True)
    cfg = StrategyConfig()

    if args.discover_telegram_chat_id:
        chats = discover_telegram_chats(args.telegram_token_env)
        print(json.dumps({"chats": chats}, indent=2, ensure_ascii=False))
        return 0

    state = load_state(args.state_dir / "state.json")

    if args.telegram_test:
        msg = build_status_message(state, cfg, args)
        ok = send_telegram(msg, args.telegram_token_env, args.telegram_chat_id_env)
        append_jsonl(args.state_dir / "notifications.jsonl", {"ts_ms": now_ms(), "text": msg, "sent": bool(ok), "kind": "telegram_test"})
        print(json.dumps({"telegram_test_sent": bool(ok)}, indent=2))
        return 0 if ok else 2

    if args.demo_orders:
        credentials()

    if args.mode == "once":
        state = run_once(args, state, cfg)
        print(json.dumps({"state": state_to_dict(state), "status": build_status_message(state, cfg, args)}, indent=2, ensure_ascii=False))
        return 0

    while True:
        try:
            state = run_once(args, state, cfg)
        except KeyboardInterrupt:
            save_state(args.state_dir / "state.json", state)
            raise
        except Exception as exc:
            append_jsonl(args.state_dir / "errors.jsonl", {"ts_ms": now_ms(), "component": "loop", "error": str(exc)})
            save_state(args.state_dir / "state.json", state)
        time.sleep(max(0.5, args.poll_seconds))


if __name__ == "__main__":
    raise SystemExit(main())
