"""Market scan: validate exit_v2 generalizes to ALL recent 妖币 events.

Logic:
  1. Scan binance_futures_1m.sqlite3 (535 symbols, 5.6 days, 4.3M bars)
  2. Detect "妖币 events": 5-min window with abs(return) >= EVENT_PCT
  3. For each event simulate two synthetic entries:
       - Pump event (≥ +EVENT_PCT) → SHORT entry next bar (fade thesis,
         matches BWE oi_overcrowded_crash_follow_short winner)
       - Dump event (≤ -EVENT_PCT) → LONG entry next bar (bounce thesis,
         matches BWE pc_crash_bounce_long)
  4. Apply 3 exit policies and compare:
       - exit_v2_baseline (G2 ON, default first-principles)
       - exit_v2_no_g2
       - naive: fixed -5% SL / +20% TP / 6h time exit
  5. Aggregate: total raw PnL, win rate, exit reason mix, per-side
       and per-event-magnitude breakdown.

Anti-double-count: per symbol, after firing an event we skip the next
60 minutes so we don't trigger 6 entries on the same minute-by-minute drift.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "exit_v2"))
from exit_v2 import (
    Bar,
    ExitConfig,
    ExitDecision,
    ExitEngine,
    Position,
    compute_atr_pct,
)

KLINE_DB = "/Users/ye/.hermes/research/binance_futures_1m_collector_runtime/binance_futures_1m.sqlite3"
OUT_DIR = Path("/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Event detection params
EVENT_WINDOW_MIN = 5            # look at 5-min returns
EVENT_PCT = 8.0                 # |return| >= 8% qualifies as 妖币 event
COOLDOWN_MIN = 60               # skip same symbol for 60 min after an event
HOLD_MIN_LIMIT = 360.0          # 6h hold limit
MIN_PRE_BARS = 35               # need at least 35 bars before entry for ATR + volume

# Naive baseline params
NAIVE_TP_PCT = 20.0
NAIVE_SL_PCT = 5.0


@dataclass
class Event:
    symbol: str
    event_ts_ms: int            # close_ts of the bar that completed the move
    side: str                   # "pump" or "dump"
    move_pct: float             # signed 5-min return
    entry_ts_ms: int            # next bar after event_ts_ms
    entry_px: float
    trade_side: str             # "short" for pump, "long" for dump


def scan_symbol(con: sqlite3.Connection, symbol: str) -> list[Event]:
    """Walk a single symbol's bars and emit events."""
    cur = con.execute(
        "SELECT open_time_ms, open, high, low, close, volume FROM klines_1m "
        "WHERE symbol=? ORDER BY open_time_ms",
        (symbol,),
    )
    rows = cur.fetchall()
    if len(rows) < MIN_PRE_BARS + EVENT_WINDOW_MIN + 1:
        return []

    events: list[Event] = []
    last_event_ts = -10**18

    for i in range(EVENT_WINDOW_MIN, len(rows) - 1):
        if i < MIN_PRE_BARS:
            continue
        ts_now, _, _, _, close_now, _ = rows[i]
        if ts_now - last_event_ts < COOLDOWN_MIN * 60_000:
            continue
        ts_then, _, _, _, close_then, _ = rows[i - EVENT_WINDOW_MIN]
        if close_then <= 0:
            continue
        ret = (close_now - close_then) / close_then * 100

        side = None
        if ret >= EVENT_PCT:
            side = "pump"
        elif ret <= -EVENT_PCT:
            side = "dump"
        if side is None:
            continue

        # Entry at next bar's open
        next_row = rows[i + 1]
        entry_ts_ms = next_row[0]
        entry_px = float(next_row[1])  # open of bar after event
        trade_side = "short" if side == "pump" else "long"

        events.append(Event(
            symbol=symbol,
            event_ts_ms=int(ts_now),
            side=side,
            move_pct=float(ret),
            entry_ts_ms=int(entry_ts_ms),
            entry_px=entry_px,
            trade_side=trade_side,
        ))
        last_event_ts = ts_now

    return events


def fetch_bars(con: sqlite3.Connection, symbol: str,
               start_ms: int, end_ms: int) -> list[Bar]:
    cur = con.execute(
        "SELECT open_time_ms, open, high, low, close, volume FROM klines_1m "
        "WHERE symbol=? AND open_time_ms BETWEEN ? AND ? ORDER BY open_time_ms",
        (symbol, start_ms, end_ms),
    )
    return [Bar(*r) for r in cur.fetchall()]


def replay_with_engine(event: Event, bars: list[Bar],
                       engine: ExitEngine) -> dict:
    """Replay event with exit_v2 engine."""
    if not bars:
        return {"pnl_pct": 0.0, "exit_reason": "no_bars", "hold_min": 0.0}

    pre_entry_bars = [b for b in bars if b.ts_ms < event.entry_ts_ms]
    atr_at_entry = compute_atr_pct(pre_entry_bars, period=14,
                                   ref_px=event.entry_px) if pre_entry_bars else 0.0

    pos = Position(
        entry_ts_ms=event.entry_ts_ms,
        entry_px=event.entry_px,
        side=event.trade_side,
        hold_minutes_limit=HOLD_MIN_LIMIT,
        atr_at_entry=atr_at_entry,
    )

    # Find entry index
    entry_idx = next((i for i, b in enumerate(bars)
                     if b.ts_ms >= event.entry_ts_ms), None)
    if entry_idx is None:
        return {"pnl_pct": 0.0, "exit_reason": "entry_not_in_bars",
                "hold_min": 0.0}

    decision: ExitDecision | None = None
    for i in range(entry_idx, len(bars)):
        d = engine.decide(pos, bars[: i + 1])
        if d:
            decision = d
            break

    if decision is None:
        last = bars[-1]
        if pos.side == "long":
            pnl = (last.close - pos.entry_px) / pos.entry_px * 100
        else:
            pnl = (pos.entry_px - last.close) / pos.entry_px * 100
        return {
            "pnl_pct": pnl,
            "exit_reason": "data_end",
            "hold_min": (last.ts_ms - event.entry_ts_ms) / 60_000.0,
            "high_water_pct": pos.high_water_pct,
            "atr_at_entry": atr_at_entry,
        }
    return {
        "pnl_pct": decision.pnl_pct,
        "exit_reason": decision.reason,
        "hold_min": (decision.exit_ts_ms - event.entry_ts_ms) / 60_000.0,
        "high_water_pct": pos.high_water_pct,
        "atr_at_entry": atr_at_entry,
    }


def replay_naive(event: Event, bars: list[Bar]) -> dict:
    """Naive baseline: -5% SL / +20% TP / 6h time exit."""
    end_ts = event.entry_ts_ms + int(HOLD_MIN_LIMIT * 60_000)
    in_trade = [b for b in bars if event.entry_ts_ms <= b.ts_ms <= end_ts]
    if not in_trade:
        return {"pnl_pct": 0.0, "exit_reason": "no_bars", "hold_min": 0.0}

    for b in in_trade:
        if event.trade_side == "long":
            best_in_bar = (b.high - event.entry_px) / event.entry_px * 100
            worst_in_bar = (b.low - event.entry_px) / event.entry_px * 100
        else:
            best_in_bar = (event.entry_px - b.low) / event.entry_px * 100
            worst_in_bar = (event.entry_px - b.high) / event.entry_px * 100
        if worst_in_bar <= -NAIVE_SL_PCT:
            return {"pnl_pct": -NAIVE_SL_PCT, "exit_reason": "naive_sl",
                    "hold_min": (b.ts_ms - event.entry_ts_ms) / 60_000.0}
        if best_in_bar >= NAIVE_TP_PCT:
            return {"pnl_pct": NAIVE_TP_PCT, "exit_reason": "naive_tp",
                    "hold_min": (b.ts_ms - event.entry_ts_ms) / 60_000.0}

    last = in_trade[-1]
    if event.trade_side == "long":
        pnl = (last.close - event.entry_px) / event.entry_px * 100
    else:
        pnl = (event.entry_px - last.close) / event.entry_px * 100
    return {"pnl_pct": pnl, "exit_reason": "naive_time",
            "hold_min": (last.ts_ms - event.entry_ts_ms) / 60_000.0}


def aggregate(results: list[dict], label: str) -> dict:
    if not results:
        return {"label": label, "n": 0}
    n = len(results)
    pnls = [r["pnl_pct"] for r in results]
    wins = sum(1 for p in pnls if p > 0)
    big_wins = sum(1 for p in pnls if p >= 10)
    catastrophes = sum(1 for p in pnls if p <= -15)
    reasons = Counter(r["exit_reason"] for r in results)
    return {
        "label": label,
        "n": n,
        "total_pnl_raw": sum(pnls),
        "mean_pnl": sum(pnls) / n,
        "median_pnl": sorted(pnls)[n // 2],
        "win_rate": wins / n * 100,
        "n_wins": wins,
        "n_big_wins_10pct": big_wins,
        "n_catastrophes_15pct": catastrophes,
        "best_pnl": max(pnls),
        "worst_pnl": min(pnls),
        "exit_reasons": dict(reasons.most_common()),
    }


def main() -> int:
    print("=" * 80)
    print("Market scan: validate exit_v2 on recent market 妖币 events")
    print("=" * 80)
    print(f"DB: {KLINE_DB}")
    print(f"Event def: 5-min window |return| >= {EVENT_PCT}%, cooldown {COOLDOWN_MIN}min")
    print(f"Hold limit: {HOLD_MIN_LIMIT/60:.0f}h, naive baseline: -{NAIVE_SL_PCT}/+{NAIVE_TP_PCT}%")
    print()

    con = sqlite3.connect(KLINE_DB)
    cur = con.execute("SELECT DISTINCT symbol FROM klines_1m")
    symbols = sorted([r[0] for r in cur.fetchall()])
    print(f"Symbols: {len(symbols)}")
    print()

    t0 = time.time()
    print(f"[scan] enumerating events...")
    all_events: list[Event] = []
    for i, sym in enumerate(symbols):
        if i % 50 == 0:
            print(f"  {i}/{len(symbols)} {sym}")
        events = scan_symbol(con, sym)
        all_events.extend(events)
    print(f"[scan] done in {time.time()-t0:.1f}s, total events: {len(all_events)}")

    pumps = [e for e in all_events if e.side == "pump"]
    dumps = [e for e in all_events if e.side == "dump"]
    print(f"  pump events (→ short): {len(pumps)}")
    print(f"  dump events (→ long):  {len(dumps)}")
    print()

    # Replay each event with 3 policies
    eng_v2 = ExitEngine(ExitConfig())                                # G2 ON
    eng_v2_no_g2 = ExitEngine(ExitConfig(tradoor_saver_enabled=False))

    print("[replay] applying 3 exit policies to each event...")
    t0 = time.time()
    results_v2 = []
    results_v2_no_g2 = []
    results_naive = []
    per_event = []

    for ev_idx, ev in enumerate(all_events):
        if ev_idx % 200 == 0:
            print(f"  {ev_idx}/{len(all_events)}")
        # Fetch bars: pre-entry MIN_PRE_BARS + post-entry HOLD_MIN_LIMIT + 5
        start_ms = ev.entry_ts_ms - (MIN_PRE_BARS + 5) * 60_000
        end_ms = ev.entry_ts_ms + int((HOLD_MIN_LIMIT + 5) * 60_000)
        bars = fetch_bars(con, ev.symbol, start_ms, end_ms)

        r_v2 = replay_with_engine(ev, bars, eng_v2)
        r_v2_no_g2 = replay_with_engine(ev, bars, eng_v2_no_g2)
        r_naive = replay_naive(ev, bars)

        results_v2.append(r_v2)
        results_v2_no_g2.append(r_v2_no_g2)
        results_naive.append(r_naive)
        per_event.append({
            "symbol": ev.symbol,
            "event_ts_ms": ev.event_ts_ms,
            "side": ev.side,
            "move_pct": ev.move_pct,
            "trade_side": ev.trade_side,
            "v2_pnl": r_v2["pnl_pct"],
            "v2_no_g2_pnl": r_v2_no_g2["pnl_pct"],
            "naive_pnl": r_naive["pnl_pct"],
            "v2_reason": r_v2["exit_reason"],
            "atr": r_v2.get("atr_at_entry", 0),
        })

    print(f"[replay] done in {time.time()-t0:.1f}s")
    print()

    # Aggregate overall
    print("=" * 80)
    print("OVERALL (all events)")
    print("=" * 80)
    for results, label in [(results_naive, "naive_-5/+20"),
                            (results_v2_no_g2, "exit_v2 (no G2)"),
                            (results_v2, "exit_v2 (G2 ON)")]:
        agg = aggregate(results, label)
        print(f"\n{label}:")
        print(f"  n={agg['n']}  total_pnl={agg['total_pnl_raw']:+.1f}%  "
              f"mean={agg['mean_pnl']:+.2f}%  median={agg['median_pnl']:+.2f}%")
        print(f"  win_rate={agg['win_rate']:.1f}%  big_wins(>=10%)={agg['n_big_wins_10pct']}  "
              f"catastrophes(<=-15%)={agg['n_catastrophes_15pct']}")
        print(f"  best={agg['best_pnl']:+.1f}%  worst={agg['worst_pnl']:+.1f}%")
        print(f"  reasons: {agg['exit_reasons']}")

    # Per-side aggregate
    print()
    print("=" * 80)
    print("BY SIDE (pump → short, dump → long)")
    print("=" * 80)
    for side_label in ("pump", "dump"):
        side_idx = [i for i, e in enumerate(all_events) if e.side == side_label]
        if not side_idx:
            continue
        print(f"\n--- {side_label} events ({len(side_idx)} total) ---")
        for results, label in [(results_naive, "naive"),
                                (results_v2_no_g2, "exit_v2_no_g2"),
                                (results_v2, "exit_v2_g2")]:
            sub = [results[i] for i in side_idx]
            agg = aggregate(sub, label)
            print(f"  {label:15s} total={agg['total_pnl_raw']:+8.1f}%  "
                  f"mean={agg['mean_pnl']:+5.2f}%  win={agg['win_rate']:5.1f}%  "
                  f"big_wins={agg['n_big_wins_10pct']:>3}  cat={agg['n_catastrophes_15pct']:>3}")

    # By event magnitude
    print()
    print("=" * 80)
    print("BY EVENT MAGNITUDE")
    print("=" * 80)
    buckets = [(8, 12), (12, 20), (20, 100)]
    for lo, hi in buckets:
        idx = [i for i, e in enumerate(all_events)
               if lo <= abs(e.move_pct) < hi]
        if not idx:
            continue
        print(f"\n--- 5-min move {lo}% to {hi}% ({len(idx)} events) ---")
        for results, label in [(results_naive, "naive"),
                                (results_v2_no_g2, "exit_v2_no_g2"),
                                (results_v2, "exit_v2_g2")]:
            sub = [results[i] for i in idx]
            agg = aggregate(sub, label)
            print(f"  {label:15s} total={agg['total_pnl_raw']:+8.1f}%  "
                  f"mean={agg['mean_pnl']:+5.2f}%  win={agg['win_rate']:5.1f}%  "
                  f"best={agg['best_pnl']:+6.1f}%  worst={agg['worst_pnl']:+6.1f}%")

    # Per-symbol top winners + losers
    print()
    print("=" * 80)
    print("TOP 10 winners & losers (exit_v2 G2 ON)")
    print("=" * 80)
    sorted_pe = sorted(per_event, key=lambda x: -x["v2_pnl"])
    print("\nTop 10 winners:")
    for x in sorted_pe[:10]:
        print(f"  {x['symbol']:14s} {x['side']:>4s}@{x['move_pct']:+5.1f}% → "
              f"{x['trade_side']:>5s} v2_pnl={x['v2_pnl']:+6.1f}% "
              f"reason={x['v2_reason']}")
    print("\nTop 10 losers:")
    for x in sorted_pe[-10:]:
        print(f"  {x['symbol']:14s} {x['side']:>4s}@{x['move_pct']:+5.1f}% → "
              f"{x['trade_side']:>5s} v2_pnl={x['v2_pnl']:+6.1f}% "
              f"reason={x['v2_reason']}")

    # Save
    save = {
        "params": {
            "event_pct": EVENT_PCT,
            "event_window_min": EVENT_WINDOW_MIN,
            "cooldown_min": COOLDOWN_MIN,
            "hold_min_limit": HOLD_MIN_LIMIT,
            "naive_sl": NAIVE_SL_PCT,
            "naive_tp": NAIVE_TP_PCT,
        },
        "n_events": len(all_events),
        "n_pumps": len(pumps),
        "n_dumps": len(dumps),
        "agg_overall": {
            "naive": aggregate(results_naive, "naive"),
            "v2_no_g2": aggregate(results_v2_no_g2, "v2_no_g2"),
            "v2_g2": aggregate(results_v2, "v2_g2"),
        },
        "per_event": per_event,
    }
    out_path = OUT_DIR / "market_scan_exit_v2.json"
    out_path.write_text(json.dumps(save, indent=2, default=str))
    print(f"\n  saved: {out_path}")

    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
