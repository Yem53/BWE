#!/usr/bin/env python3
"""Strict offline replay for the v6_multi_8 paper runner strategies.

This script is intentionally offline:
- reads only local runtime artifacts and the local Binance collector SQLite DB;
- never calls Binance REST or testnet order endpoints;
- replays exits candle-by-candle using 1m high/low from the entry candle onward.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import datetime as dt
import importlib.util
import json
import math
import sqlite3
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


CODEX_ROOT = Path("/Volumes/T9/BWE_codex")
RUN_ROOT = CODEX_ROOT / "paper_test/v6_multi_8"
RUNNER_PATH = RUN_ROOT / "scripts/multi_paper_runner.py"
DEFAULT_CONFIG = RUN_ROOT / "config/strategies_9.json"
DEFAULT_STATE = RUN_ROOT / "runtime/state.json"
DEFAULT_EVENTS = RUN_ROOT / "runtime/events.jsonl"
DEFAULT_DECISIONS = RUN_ROOT / "runtime/decisions.jsonl"
DEFAULT_DB = Path("/Volumes/T9_HOT/binance_collectors_runtime/binance_futures_1m.sqlite3")
DEFAULT_OUT_DIR = RUN_ROOT / "runtime/strict_replay_latest"

ROUND_TRIP_COST_BPS = 20.0


def import_runner() -> Any:
    spec = importlib.util.spec_from_file_location("multi_paper_runner_replay", RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import runner from {RUNNER_PATH}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


mpr = import_runner()


@dataclass
class ReplayTrade:
    strategy_id: str
    label: str
    side: str
    trigger: str
    symbol: str
    event_type: str | None
    component: str | None
    event_ts_ms: int | None
    due_ts_ms: int
    entry_ts_ms: int
    exit_ts_ms: int
    entry_price: float
    exit_price: float
    gross_pct: float
    net_pct: float
    exit_reason: str
    source_mode: str


def iso_ms(ts_ms: int | None) -> str:
    if ts_ms is None:
        return ""
    return dt.datetime.fromtimestamp(ts_ms / 1000, tz=dt.timezone.utc).isoformat()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def open_db(path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=30)
    db.row_factory = sqlite3.Row
    return db


def table_bounds(db: sqlite3.Connection, table: str, ts_col: str) -> dict[str, Any]:
    row = db.execute(f"SELECT MIN({ts_col}) AS min_ts, MAX({ts_col}) AS max_ts FROM {table}").fetchone()
    return {"table": table, "min_ts_ms": row["min_ts"], "max_ts_ms": row["max_ts"]}


def first_entry_open(db: sqlite3.Connection, symbol: str, due_ts_ms: int) -> tuple[int, float] | None:
    row = db.execute(
        "SELECT open_time_ms, open FROM klines_1m "
        "WHERE interval='1m' AND symbol=? AND open_time_ms>=? "
        "ORDER BY open_time_ms LIMIT 1",
        (symbol, due_ts_ms),
    ).fetchone()
    if not row:
        return None
    return int(row["open_time_ms"]), float(row["open"])


def bars_from_entry(db: sqlite3.Connection, symbol: str, entry_ts_ms: int, limit: int) -> list[Any]:
    rows = db.execute(
        "SELECT open_time_ms, open, high, low, close, quote_volume FROM klines_1m "
        "WHERE interval='1m' AND symbol=? AND open_time_ms>=? "
        "ORDER BY open_time_ms LIMIT ?",
        (symbol, entry_ts_ms, limit),
    ).fetchall()
    return [
        mpr.Bar(
            int(r["open_time_ms"]),
            float(r["open"]),
            float(r["high"]),
            float(r["low"]),
            float(r["close"]),
            float(r["quote_volume"] or 0.0),
        )
        for r in rows
    ]


def strict_exit(db: sqlite3.Connection, spec: Any, pos: Any) -> Any | None:
    horizon = int((pos.exit or spec.exit).get("horizon", spec.exit.get("horizon", 240)))
    bars = bars_from_entry(db, pos.symbol, pos.entry_ts_ms, horizon)
    return mpr.simulate_exit(pos, bars, spec)


def source_for_condition(field: str) -> str:
    if field in {"marketcap", "move_pct"}:
        return "paper_test/v6_multi_8/runtime/events.jsonl:event.text parsed by runner"
    if field == "top_ratio":
        return "SQLite top_trader_long_short_account_ratio_5m.long_short_ratio as-of due_ts"
    if field == "global_ratio":
        return "SQLite global_long_short_account_ratio_5m.long_short_ratio as-of due_ts"
    if field == "top_position_ratio":
        return "SQLite top_trader_long_short_position_ratio_5m.long_short_ratio as-of scan_ts"
    if field == "quote_volume_24h":
        return "SQLite ticker_24h.quote_volume as-of due_ts"
    if field == "listing_age_days":
        return "SQLite symbol_meta.listing_ts_ms, computed at due_ts"
    if field == "mark_1m_age_ms":
        return "SQLite mark_price_1m.ts_ms age at due_ts"
    if field in {"qv_5m_ratio", "ret_3m", "ret_15m", "ret_60m", "pullback_from_high_60m", "body_ret_1m", "upper_wick_pct"}:
        return "SQLite klines_1m OHLCV, completed 1m bars only"
    if field == "taker_ratio":
        return "SQLite taker_buy_sell_volume_5m.buy_sell_ratio as-of scan_ts"
    if field == "oi_chg_60m":
        return "SQLite open_interest_5m.sum_open_interest as-of scan_ts and scan_ts-60m"
    if field == "bwe_60m":
        return "runtime/events.jsonl BWE events in prior 60m"
    return "unknown"


def condition_sources(specs: list[Any]) -> dict[str, list[dict[str, str]]]:
    out: dict[str, list[dict[str, str]]] = {}
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
    for spec in specs:
        rows: list[dict[str, str]] = []
        for cond in spec.conditions:
            field = str(cond["field"])
            rows.append({"field": field, "source": source_for_condition(field)})
        for component in spec.components:
            entry = dict(component.get("entry") or {})
            if entry.get("trigger") == "bwe60":
                rows.append({"field": "bwe_60m", "source": source_for_condition("bwe_60m")})
            for key, field in field_map.items():
                if key in entry:
                    rows.append({"field": field, "source": source_for_condition(field)})
        out[spec.label] = rows
    return out


def load_events(path: Path) -> list[Any]:
    events: list[Any] = []
    for row in read_jsonl(path):
        event = row.get("event") or {}
        try:
            events.append(mpr.BweEvent(**event))
        except TypeError:
            continue
    return events


def replay_longs(db: sqlite3.Connection, specs: list[Any], events: list[Any], active: set[str]) -> tuple[list[ReplayTrade], dict[str, Any]]:
    trades: list[ReplayTrade] = []
    candidates = Counter()
    rejects = Counter()
    pass_signals = Counter()
    unclosed = Counter()
    no_entry_bar = Counter()
    long_specs = [s for s in specs if s.side == "long" and s.trigger == "bwe"]
    for event in events:
        for spec in long_specs:
            if spec.event_type != "ANY" and event.event_type != spec.event_type:
                continue
            candidates[spec.label] += 1
            due_ts_ms = int(event.ts_ms + spec.entry_delay_s * 1000)
            features = mpr.point_feature_snapshot(db, event.symbol, due_ts_ms)
            ok, reason = mpr.evaluate_long_strategy(event, features, spec, active)
            if not ok:
                rejects[(spec.label, reason)] += 1
                continue
            pass_signals[spec.label] += 1
            entry = first_entry_open(db, event.symbol, due_ts_ms)
            if entry is None:
                no_entry_bar[spec.label] += 1
                continue
            entry_ts_ms, entry_price = entry
            pos = mpr.OpenPosition(
                spec.strategy_id,
                spec.label,
                event.symbol,
                spec.side,
                event.ts_ms,
                due_ts_ms,
                entry_ts_ms,
                entry_price,
                1.0,
                "strict_signal_only",
                dict(spec.exit),
                entry_price,
            )
            closed = strict_exit(db, spec, pos)
            if closed is None:
                unclosed[spec.label] += 1
                continue
            gross = float(closed.pnl_pct)
            trades.append(
                ReplayTrade(
                    strategy_id=spec.strategy_id,
                    label=spec.label,
                    side=spec.side,
                    trigger=spec.trigger,
                    symbol=event.symbol,
                    event_type=event.event_type,
                    component=None,
                    event_ts_ms=event.ts_ms,
                    due_ts_ms=due_ts_ms,
                    entry_ts_ms=entry_ts_ms,
                    exit_ts_ms=int(closed.exit_ts_ms),
                    entry_price=entry_price,
                    exit_price=float(closed.exit_price),
                    gross_pct=gross,
                    net_pct=gross - ROUND_TRIP_COST_BPS / 100.0,
                    exit_reason=str(closed.reason),
                    source_mode="local_db_only",
                )
            )
    diagnostics = {
        "candidates": dict(candidates),
        "pass_signals": dict(pass_signals),
        "rejects": {f"{k[0]}:{k[1]}": v for k, v in rejects.items()},
        "no_entry_bar": dict(no_entry_bar),
        "unclosed": dict(unclosed),
    }
    return trades, diagnostics


def fetch_symbol_bars(db: sqlite3.Connection, symbol: str, start_ms: int, end_ms: int, warmup_min: int, future_min: int) -> list[Any]:
    rows = db.execute(
        "SELECT open_time_ms, open, high, low, close, quote_volume FROM klines_1m "
        "WHERE interval='1m' AND symbol=? AND open_time_ms BETWEEN ? AND ? "
        "ORDER BY open_time_ms",
        (symbol, start_ms - warmup_min * 60_000, end_ms + future_min * 60_000),
    ).fetchall()
    return [
        mpr.Bar(
            int(r["open_time_ms"]),
            float(r["open"]),
            float(r["high"]),
            float(r["low"]),
            float(r["close"]),
            float(r["quote_volume"] or 0.0),
        )
        for r in rows
    ]


def fetch_series(db: sqlite3.Connection, table: str, symbol: str, start_ms: int, end_ms: int, value_col: str) -> tuple[list[int], list[float | None]]:
    rows = db.execute(
        f"SELECT ts_ms, {value_col} FROM {table} WHERE symbol=? AND ts_ms BETWEEN ? AND ? ORDER BY ts_ms",
        (symbol, start_ms, end_ms),
    ).fetchall()
    return [int(r["ts_ms"]) for r in rows], [float(r[value_col]) if r[value_col] is not None else None for r in rows]


def asof_value(times: list[int], values: list[float | None], ts_ms: int) -> float | None:
    idx = bisect.bisect_right(times, ts_ms) - 1
    if idx < 0:
        return None
    return values[idx]


def scanner_values_at(
    bars: list[Any],
    idx: int,
    top_pos: tuple[list[int], list[float | None]],
    taker: tuple[list[int], list[float | None]],
    oi: tuple[list[int], list[float | None]],
    event_times: list[int],
) -> dict[str, Any] | None:
    if idx < 64:
        return None
    prev_start = max(0, idx - 1440)
    prev_qv = [float(b.quote_volume or 0.0) for b in bars[prev_start:idx]]
    if len(prev_qv) < 120:
        return None
    cur = bars[idx]
    qv_avg = sum(prev_qv) / len(prev_qv)
    qv_5m = sum(float(b.quote_volume or 0.0) for b in bars[max(0, idx - 4) : idx + 1])
    highs60 = [float(b.high) for b in bars[idx - 59 : idx + 1]]
    ts5 = (int(cur.open_time_ms) // 300_000) * 300_000
    oi_now = asof_value(oi[0], oi[1], ts5)
    oi_prev = asof_value(oi[0], oi[1], ts5 - 3_600_000)
    oi_chg = None
    if oi_now is not None and oi_prev not in (None, 0):
        oi_chg = (float(oi_now) / float(oi_prev) - 1.0) * 100.0
    left = bisect.bisect_left(event_times, int(cur.open_time_ms) - 3_600_000)
    right = bisect.bisect_right(event_times, int(cur.open_time_ms))
    return {
        "open_time_ms": int(cur.open_time_ms),
        "ret_3m": (float(cur.close) / float(bars[idx - 3].close) - 1.0) * 100.0,
        "ret_15m": (float(cur.close) / float(bars[idx - 15].close) - 1.0) * 100.0,
        "ret_60m": (float(cur.close) / float(bars[idx - 60].close) - 1.0) * 100.0,
        "pullback_from_high_60m": (float(cur.close) / max(highs60) - 1.0) * 100.0,
        "body_ret_1m": (float(cur.close) / float(cur.open) - 1.0) * 100.0,
        "upper_wick_pct": (float(cur.high) / max(float(cur.open), float(cur.close)) - 1.0) * 100.0,
        "qv_5m_ratio": qv_5m / (qv_avg * 5.0) if qv_avg > 0 else None,
        "top_position_ratio": asof_value(top_pos[0], top_pos[1], ts5),
        "taker_ratio": asof_value(taker[0], taker[1], ts5),
        "oi_chg_60m": oi_chg,
        "bwe_60m": right - left,
    }


def replay_scanners(
    db: sqlite3.Connection,
    specs: list[Any],
    active: set[str],
    events: list[Any],
    start_ms: int,
    end_ms: int,
) -> tuple[list[ReplayTrade], dict[str, Any]]:
    scanner_specs = [s for s in specs if s.trigger == "scanner"]
    trades: list[ReplayTrade] = []
    candidates = Counter()
    pass_signals = Counter()
    rejects = Counter()
    unclosed = Counter()
    scanned_symbols = 0
    scanned_bars = 0
    event_times_by_symbol: dict[str, list[int]] = defaultdict(list)
    for event in events:
        event_times_by_symbol[event.symbol].append(int(event.ts_ms))
    for times in event_times_by_symbol.values():
        times.sort()

    max_horizon = max(int(s.exit.get("horizon", 240)) for s in scanner_specs if not s.components)
    for spec in scanner_specs:
        for component in spec.components:
            max_horizon = max(max_horizon, int((component.get("exit") or {}).get("horizon", 240)))

    for symbol in sorted(active):
        bars = fetch_symbol_bars(db, symbol, start_ms, end_ms, warmup_min=1505, future_min=max_horizon)
        if not bars:
            continue
        scanned_symbols += 1
        top_pos = fetch_series(
            db,
            "top_trader_long_short_position_ratio_5m",
            symbol,
            start_ms - 3_700_000,
            end_ms,
            "long_short_ratio",
        )
        taker = fetch_series(db, "taker_buy_sell_volume_5m", symbol, start_ms - 3_700_000, end_ms, "buy_sell_ratio")
        oi = fetch_series(db, "open_interest_5m", symbol, start_ms - 7_300_000, end_ms, "sum_open_interest")
        event_times = event_times_by_symbol.get(symbol, [])
        for idx, bar in enumerate(bars):
            scan_ts = int(bar.open_time_ms)
            if scan_ts < start_ms or scan_ts > end_ms:
                continue
            values = scanner_values_at(bars, idx, top_pos, taker, oi, event_times)
            if values is None:
                continue
            scanned_bars += 1
            for spec in scanner_specs:
                candidates[spec.label] += 1
                chosen = None
                reason = "entry_pass"
                exit_cfg = spec.exit
                if spec.components:
                    reason = "skip_no_component_pass"
                    for component in spec.components:
                        ok, comp_reason = mpr.component_pass(values, component)
                        reason = comp_reason
                        if ok:
                            chosen = str(component.get("label") or "component")
                            exit_cfg = dict(component["exit"])
                            break
                    if chosen is None:
                        rejects[(spec.label, reason)] += 1
                        continue
                else:
                    ok, reason = mpr.evaluate_scanner_conditions(values, spec.conditions)
                    if not ok:
                        rejects[(spec.label, reason)] += 1
                        continue
                pass_signals[spec.label] += 1
                entry_ts_ms = scan_ts + 60_000
                if idx + 1 >= len(bars):
                    unclosed[spec.label] += 1
                    continue
                entry_price = float(bars[idx + 1].open)
                pos = mpr.OpenPosition(
                    spec.strategy_id,
                    spec.label,
                    symbol,
                    spec.side,
                    scan_ts,
                    entry_ts_ms,
                    entry_ts_ms,
                    entry_price,
                    1.0,
                    "strict_signal_only",
                    dict(exit_cfg),
                    entry_price,
                    chosen,
                )
                closed = mpr.simulate_exit(pos, bars[idx + 1 : idx + 1 + int(exit_cfg.get("horizon", 240))], spec)
                if closed is None:
                    unclosed[spec.label] += 1
                    continue
                gross = float(closed.pnl_pct)
                trades.append(
                    ReplayTrade(
                        strategy_id=spec.strategy_id,
                        label=spec.label,
                        side=spec.side,
                        trigger=spec.trigger,
                        symbol=symbol,
                        event_type=None,
                        component=chosen,
                        event_ts_ms=scan_ts,
                        due_ts_ms=entry_ts_ms,
                        entry_ts_ms=entry_ts_ms,
                        exit_ts_ms=int(closed.exit_ts_ms),
                        entry_price=entry_price,
                        exit_price=float(closed.exit_price),
                        gross_pct=gross,
                        net_pct=gross - ROUND_TRIP_COST_BPS / 100.0,
                        exit_reason=str(closed.reason),
                        source_mode="local_db_only",
                    )
                )
    diagnostics = {
        "scanned_symbols": scanned_symbols,
        "scanned_symbol_coverage_pct": scanned_symbols / max(1, len(active)) * 100.0,
        "scanned_bars": scanned_bars,
        "candidates": dict(candidates),
        "pass_signals": dict(pass_signals),
        "rejects": {f"{k[0]}:{k[1]}": v for k, v in rejects.items()},
        "unclosed": dict(unclosed),
    }
    return trades, diagnostics


def summarize(trades: list[ReplayTrade], window_days: float, active_symbol_count: int) -> list[dict[str, Any]]:
    by_label: dict[str, list[ReplayTrade]] = defaultdict(list)
    for trade in trades:
        by_label[trade.label].append(trade)
    rows: list[dict[str, Any]] = []
    for label, group in sorted(by_label.items()):
        n = len(group)
        net_sum = sum(t.net_pct for t in group)
        gross_sum = sum(t.gross_pct for t in group)
        symbols = Counter(t.symbol for t in group)
        reasons = Counter(t.exit_reason for t in group)
        components = Counter(t.component or "" for t in group if t.component)
        rows.append(
            {
                "label": label,
                "side": group[0].side,
                "trigger": group[0].trigger,
                "sample": n,
                "monthly": n / max(window_days, 1e-9) * 30.0,
                "win_net": sum(1 for t in group if t.net_pct > 0) / n * 100.0,
                "win_gross": sum(1 for t in group if t.gross_pct > 0) / n * 100.0,
                "mean_net_pct": net_sum / n,
                "mean_gross_pct": gross_sum / n,
                "sum_net_pct": net_sum,
                "sum_gross_pct": gross_sum,
                "unique_symbols": len(symbols),
                "symbol_coverage_pct_of_active": len(symbols) / max(1, active_symbol_count) * 100.0,
                "top_symbol": symbols.most_common(1)[0][0],
                "top_symbol_share_pct": symbols.most_common(1)[0][1] / n * 100.0,
                "exit_reason_counts": dict(reasons),
                "component_counts": dict(components),
                "first_entry_utc": iso_ms(min(t.entry_ts_ms for t in group)),
                "last_entry_utc": iso_ms(max(t.entry_ts_ms for t in group)),
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        keys: list[str] = []
        for row in rows:
            for key in row:
                if key not in keys:
                    keys.append(key)
        fieldnames = keys
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in row.items()})


def build_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# v6_multi_8 Strict Replay Report")
    lines.append("")
    lines.append(f"- Generated UTC: `{report['generated_utc']}`")
    lines.append(f"- Cost model: `{ROUND_TRIP_COST_BPS:.1f} bps round trip`, net = gross - cost")
    lines.append("- Entry model: BWE long uses next 1m open at/after due_ts; scanner short uses next 1m open after signal bar.")
    lines.append("- Exit model: 1m high/low state machine from the entry candle onward; adverse stop is checked first where same-candle order is ambiguous.")
    lines.append("- Network/order endpoints: not used.")
    lines.append("")
    lines.append("## Runtime Snapshot")
    snap = report["runtime_snapshot"]
    for key in [
        "events",
        "unique_event_symbols",
        "event_dates",
        "state_demo_orders_failed",
        "state_demo_orders_placed",
        "state_api_fallback_count",
        "decisions_fallback_rows",
    ]:
        lines.append(f"- {key}: `{snap.get(key)}`")
    lines.append("")
    lines.append("## Data Sources")
    for row in report["data_sources"]:
        lines.append(f"- `{row['field']}`: {row['source']}")
    lines.append("")
    lines.append("## Summary")
    headers = [
        "label",
        "side",
        "sample",
        "monthly",
        "win_net",
        "mean_net_pct",
        "sum_net_pct",
        "unique_symbols",
        "symbol_coverage_pct_of_active",
        "top_symbol_share_pct",
        "exit_reason_counts",
    ]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in report["summary"]:
        vals = []
        for key in headers:
            val = row.get(key)
            if isinstance(val, float):
                vals.append(f"{val:.4f}")
            elif isinstance(val, dict):
                vals.append(json.dumps(val, ensure_ascii=False, sort_keys=True))
            else:
                vals.append(str(val))
        lines.append("| " + " | ".join(vals) + " |")
    lines.append("")
    lines.append("## Diagnostics")
    lines.append("```json")
    lines.append(json.dumps(report["diagnostics"], ensure_ascii=False, indent=2, sort_keys=True))
    lines.append("```")
    lines.append("")
    lines.append("## Verdict")
    lines.append(report["verdict"])
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--events", type=Path, default=DEFAULT_EVENTS)
    parser.add_argument("--decisions", type=Path, default=DEFAULT_DECISIONS)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args(argv)

    specs = mpr.load_strategy_specs(args.config)
    events = load_events(args.events)
    state = json.loads(args.state.read_text(encoding="utf-8")) if args.state.exists() else {}
    decisions = read_jsonl(args.decisions)
    start_ms = int(state.get("started_ts_ms") or min((e.ts_ms for e in events), default=0))
    with open_db(args.db) as db:
        active = mpr.load_active_symbols(db)
        max_bar = db.execute("SELECT MAX(open_time_ms) AS t FROM klines_1m WHERE interval='1m'").fetchone()["t"]
        end_ms = int(max_bar or max((e.ts_ms for e in events), default=start_ms))
        bounds = [
            table_bounds(db, "klines_1m", "open_time_ms"),
            table_bounds(db, "mark_price_1m", "ts_ms"),
            table_bounds(db, "ticker_24h", "ts_ms"),
            table_bounds(db, "top_trader_long_short_account_ratio_5m", "ts_ms"),
            table_bounds(db, "global_long_short_account_ratio_5m", "ts_ms"),
            table_bounds(db, "top_trader_long_short_position_ratio_5m", "ts_ms"),
            table_bounds(db, "taker_buy_sell_volume_5m", "ts_ms"),
            table_bounds(db, "open_interest_5m", "ts_ms"),
        ]
        long_trades, long_diag = replay_longs(db, specs, events, active)
        scanner_trades, scanner_diag = replay_scanners(db, specs, active, events, start_ms, end_ms)

    trades = long_trades + scanner_trades
    event_dates = sorted({dt.datetime.fromtimestamp(e.ts_ms / 1000, tz=dt.timezone.utc).date().isoformat() for e in events})
    window_days = max(1e-9, (end_ms - start_ms) / 86_400_000.0)
    summary = summarize(trades, window_days, len(active))

    source_rows = []
    seen_source = set()
    for rows in condition_sources(specs).values():
        for row in rows:
            key = (row["field"], row["source"])
            if key not in seen_source:
                seen_source.add(key)
                source_rows.append(row)

    fallback_rows = [r for r in decisions if r.get("decision") == "fallback"]
    report = {
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "inputs": {
            "config": str(args.config),
            "state": str(args.state),
            "events": str(args.events),
            "decisions": str(args.decisions),
            "db": str(args.db),
        },
        "runtime_snapshot": {
            "events": len(events),
            "unique_event_symbols": len({e.symbol for e in events}),
            "event_dates": event_dates,
            "active_usdt_perp_symbols": len(active),
            "window_start_utc": iso_ms(start_ms),
            "window_end_utc": iso_ms(end_ms),
            "window_days": window_days,
            "state_demo_orders_failed": int(state.get("demo_orders_failed") or 0),
            "state_demo_orders_placed": int(state.get("demo_orders_placed") or 0),
            "state_api_fallback_count": int(state.get("api_fallback_count") or 0),
            "decisions_fallback_rows": len(fallback_rows),
        },
        "db_bounds": bounds,
        "data_sources": source_rows,
        "summary": summary,
        "diagnostics": {
            "long": long_diag,
            "scanner": scanner_diag,
            "strict_limitations": [
                "Fallback REST feature rows in decisions.jsonl are not mixed into pass metrics because they lack event_ts_ms/due_ts_ms keys.",
                "Short scanner current-run failed open attempts cannot be exactly reconstructed from runtime logs because open_position failures were not journaled with strategy/component before return.",
                "This is signal-level replay, not a live portfolio promotion or exchange-fill simulation.",
            ],
        },
        "verdict": (
            "Strict local-data replay does not prove a universal live strategy. Long entries have positive gross/net means in this one-day runner window, "
            "but samples are small and concentrated. Short scanner results are replayed from local fields over the same window and remain separate from the long side. "
            "No strategy should be treated as live-ready without a clean paper-shadow run and explicit user confirmation."
        ),
    }

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "trades.csv", [asdict(t) | {"entry_utc": iso_ms(t.entry_ts_ms), "exit_utc": iso_ms(t.exit_ts_ms)} for t in trades])
    write_csv(out_dir / "summary.csv", summary)
    (out_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "report.md").write_text(build_markdown(report), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "trades": len(trades), "strategies": len(summary)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
