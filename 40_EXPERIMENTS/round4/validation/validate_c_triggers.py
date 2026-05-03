"""Validate each C-path trigger on real market data.

For each C trigger, find all historical events matching the condition,
compute forward 60min return in intended direction, report stats.

Decision criteria:
- KEEP: mean trade outcome > 0.5pp AND win rate > 52%
- DROP: mean outcome < 0 OR win rate < 50% OR n_events < 30 (insufficient sample)
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from collections import defaultdict
from statistics import mean, stdev

LIVE_DB = (
    "/Users/ye/.hermes/research/binance_futures_1m_collector_runtime/"
    "binance_futures_1m.sqlite3"
)


def find_oi_spike_events(con, threshold_pct: float = 3.0) -> list[dict]:
    """C1: 5min OI change >= threshold_pct, intent=follow OI direction."""
    rows = con.execute(
        "SELECT symbol, ts_ms, sum_open_interest_value FROM open_interest_5m "
        "ORDER BY symbol, ts_ms"
    ).fetchall()
    by_sym = defaultdict(list)
    for r in rows:
        by_sym[r[0]].append((r[1], r[2]))
    events = []
    for sym, series in by_sym.items():
        for i in range(1, len(series)):
            ts_now, oi_now = series[i]
            ts_prev, oi_prev = series[i-1]
            if oi_prev <= 0:
                continue
            chg = (oi_now - oi_prev) / oi_prev * 100
            if chg >= threshold_pct:
                events.append({"symbol": sym, "event_ts_ms": ts_now,
                               "trigger": "C1_OI_SPIKE", "value": chg,
                               "intent": "long"})  # follow whale long
            elif chg <= -threshold_pct:
                events.append({"symbol": sym, "event_ts_ms": ts_now,
                               "trigger": "C1_OI_SPIKE_DOWN", "value": chg,
                               "intent": "short"})
    return events


def find_squeeze_events(con, ls_threshold: float, px_threshold: float = 3.0) -> list[dict]:
    """C2/C3: extreme LS ratio + price move in same dir as squeeze."""
    rows = con.execute(
        "SELECT g.symbol, g.ts_ms, g.long_account, g.short_account "
        "FROM global_long_short_account_ratio_5m g ORDER BY g.symbol, g.ts_ms"
    ).fetchall()
    events = []
    for sym, ts_ms, la, sa in rows:
        if (la + sa) <= 0:
            continue
        ratio = la / (la + sa)
        # find price move in last 5min
        px_rows = con.execute(
            "SELECT close FROM klines_1m WHERE symbol=? AND open_time_ms <= ? "
            "ORDER BY open_time_ms DESC LIMIT 6", (sym, ts_ms)
        ).fetchall()
        if len(px_rows) < 6:
            continue
        cur, prev = px_rows[0][0], px_rows[5][0]
        if prev <= 0:
            continue
        pct = (cur - prev) / prev * 100
        # C2: short squeeze (low LS + price up = shorts being squeezed)
        if ratio <= ls_threshold and pct >= px_threshold:
            events.append({"symbol": sym, "event_ts_ms": ts_ms,
                           "trigger": "C2_SHORT_SQUEEZE", "value": ratio,
                           "intent": "long", "px_pct": pct})
        # C3: long liquidation (high LS + price down = longs being liquidated)
        if ratio >= (1 - ls_threshold) and pct <= -px_threshold:
            events.append({"symbol": sym, "event_ts_ms": ts_ms,
                           "trigger": "C3_LONG_LIQUI", "value": ratio,
                           "intent": "short", "px_pct": pct})
    return events


def find_diverge_events(con, threshold: float = 0.10) -> list[dict]:
    """C4: top trader vs global LS diverge >= threshold, follow top."""
    g_rows = con.execute(
        "SELECT symbol, ts_ms, long_account, short_account FROM global_long_short_account_ratio_5m"
    ).fetchall()
    g_idx = {(r[0], r[1]): (r[2], r[3]) for r in g_rows}
    t_rows = con.execute(
        "SELECT symbol, ts_ms, long_account, short_account FROM top_trader_long_short_position_ratio_5m"
    ).fetchall()
    events = []
    for sym, ts_ms, t_la, t_sa in t_rows:
        g = g_idx.get((sym, ts_ms))
        if not g:
            continue
        g_la, g_sa = g
        if (t_la + t_sa) == 0 or (g_la + g_sa) == 0:
            continue
        t_ratio = t_la / (t_la + t_sa)
        g_ratio = g_la / (g_la + g_sa)
        diverge = t_ratio - g_ratio
        if abs(diverge) >= threshold:
            # top traders longer than global → follow top long
            intent = "long" if diverge > 0 else "short"
            events.append({"symbol": sym, "event_ts_ms": ts_ms,
                           "trigger": "C4_DIVERGE", "value": diverge,
                           "intent": intent})
    return events


def find_funding_flip_events(con, abs_rate_threshold: float = 0.0005) -> list[dict]:
    """C5: funding flips sign + |rate| >= threshold, fade direction."""
    rows = con.execute(
        "SELECT symbol, ts_ms, funding_rate FROM funding_rate ORDER BY symbol, ts_ms"
    ).fetchall()
    by_sym = defaultdict(list)
    for r in rows:
        by_sym[r[0]].append((r[1], r[2]))
    events = []
    for sym, series in by_sym.items():
        for i in range(1, len(series)):
            ts_now, fr_now = series[i]
            ts_prev, fr_prev = series[i-1]
            if fr_now * fr_prev >= 0:
                continue  # same sign, no flip
            if abs(fr_now) < abs_rate_threshold:
                continue
            # Flip: previous was positive (longs paid shorts), now negative
            #   → shorts dominant → market expecting down → fade short
            # Flip from negative to positive: market expecting up → fade long
            intent = "short" if fr_now < 0 else "long"  # fade the new pressure
            events.append({"symbol": sym, "event_ts_ms": ts_now,
                           "trigger": "C5_FUNDING_FLIP", "value": fr_now,
                           "intent": intent})
    return events


def forward_return_60min(con, sym, event_ts_ms):
    """Forward 60min raw return from current close."""
    cur_rows = con.execute(
        "SELECT close FROM klines_1m WHERE symbol=? AND open_time_ms <= ? "
        "ORDER BY open_time_ms DESC LIMIT 1", (sym, event_ts_ms)
    ).fetchall()
    fut_rows = con.execute(
        "SELECT close FROM klines_1m WHERE symbol=? AND open_time_ms = ? LIMIT 1",
        (sym, event_ts_ms + 60 * 60_000)
    ).fetchall()
    if not cur_rows or not fut_rows or cur_rows[0][0] <= 0:
        return None
    return (fut_rows[0][0] - cur_rows[0][0]) / cur_rows[0][0] * 100


def evaluate_trigger(events: list[dict], con) -> dict:
    """Compute outcomes for a list of events."""
    outcomes = []
    for e in events:
        fwd = forward_return_60min(con, e["symbol"], e["event_ts_ms"])
        if fwd is None:
            continue
        # convert to trade outcome based on intent
        if e["intent"] == "long":
            outcome = fwd
        else:
            outcome = -fwd
        outcomes.append(outcome)
    if not outcomes:
        return {"n": 0}
    wins = sum(1 for o in outcomes if o > 0)
    return {
        "n": len(outcomes),
        "mean": mean(outcomes),
        "median": sorted(outcomes)[len(outcomes)//2],
        "stdev": stdev(outcomes) if len(outcomes) > 1 else 0,
        "win_rate": wins / len(outcomes) * 100,
        "p25": sorted(outcomes)[len(outcomes)//4],
        "p75": sorted(outcomes)[3*len(outcomes)//4],
    }


def main():
    print("=" * 70)
    print("C-Path Trigger Validation on 30-day Market Data")
    print("=" * 70)
    con = sqlite3.connect(LIVE_DB, timeout=60)
    con.execute("PRAGMA query_only=1")

    # ---------- C1 ----------
    print("\n[C1] OI Spike (5min OI change ≥ ±3.0%)")
    t0 = time.time()
    c1_events = find_oi_spike_events(con, threshold_pct=3.0)
    c1_up = [e for e in c1_events if e["trigger"] == "C1_OI_SPIKE"]
    c1_dn = [e for e in c1_events if e["trigger"] == "C1_OI_SPIKE_DOWN"]
    print(f"  found in {time.time()-t0:.1f}s: up={len(c1_up)} dn={len(c1_dn)}")
    c1_up_stats = evaluate_trigger(c1_up, con)
    c1_dn_stats = evaluate_trigger(c1_dn, con)
    print(f"  C1 OI up   (long  intent): {c1_up_stats}")
    print(f"  C1 OI dn   (short intent): {c1_dn_stats}")

    # ---------- C2 + C3 ----------
    print("\n[C2/C3] LS Squeeze (LS ≤ 0.30 + px↑3% OR LS ≥ 0.70 + px↓3%)")
    t0 = time.time()
    sq_events = find_squeeze_events(con, ls_threshold=0.30, px_threshold=3.0)
    c2_events = [e for e in sq_events if e["trigger"] == "C2_SHORT_SQUEEZE"]
    c3_events = [e for e in sq_events if e["trigger"] == "C3_LONG_LIQUI"]
    print(f"  found in {time.time()-t0:.1f}s: C2={len(c2_events)} C3={len(c3_events)}")
    c2_stats = evaluate_trigger(c2_events, con)
    c3_stats = evaluate_trigger(c3_events, con)
    print(f"  C2 short squeeze (long  intent): {c2_stats}")
    print(f"  C3 long liqui    (short intent): {c3_stats}")

    # ---------- C4 ----------
    print("\n[C4] Top vs Global Diverge (|t-g| ≥ 0.10)")
    t0 = time.time()
    c4_events = find_diverge_events(con, threshold=0.10)
    print(f"  found in {time.time()-t0:.1f}s: {len(c4_events)}")
    c4_stats = evaluate_trigger(c4_events, con)
    print(f"  C4 diverge       (follow-top intent): {c4_stats}")

    # ---------- C5 ----------
    print("\n[C5] Funding Flip (sign change + |rate| ≥ 0.05%)")
    t0 = time.time()
    c5_events = find_funding_flip_events(con, abs_rate_threshold=0.0005)
    print(f"  found in {time.time()-t0:.1f}s: {len(c5_events)}")
    c5_stats = evaluate_trigger(c5_events, con)
    print(f"  C5 funding flip  (fade-flip intent): {c5_stats}")

    # ---------- Decision matrix ----------
    print("\n" + "=" * 70)
    print("Decision Matrix (KEEP / DROP)")
    print("=" * 70)
    print(f"{'trigger':<32s} {'n':>6s} {'mean':>7s} {'win%':>7s} {'verdict':>10s}")
    candidates = [
        ("C1_OI_SPIKE_UP (long)", c1_up_stats),
        ("C1_OI_SPIKE_DN (short)", c1_dn_stats),
        ("C2_SHORT_SQUEEZE (long)", c2_stats),
        ("C3_LONG_LIQUI (short)", c3_stats),
        ("C4_DIVERGE (follow-top)", c4_stats),
        ("C5_FUNDING_FLIP (fade)", c5_stats),
    ]
    decisions = {}
    for name, st in candidates:
        if st["n"] < 30:
            verdict = "INSUFF"
        elif st["mean"] > 0.5 and st["win_rate"] > 52:
            verdict = "✅ KEEP"
        elif st["mean"] < 0 or st["win_rate"] < 50:
            verdict = "❌ DROP"
        else:
            verdict = "⚠ MARGINAL"
        decisions[name] = verdict
        if st["n"] >= 30:
            print(f"  {name:<32s} {st['n']:>6d} {st['mean']:>+6.2f}% {st['win_rate']:>6.1f}% {verdict:>10s}")
        else:
            print(f"  {name:<32s} {st['n']:>6d}    n/a    n/a {verdict:>10s}")

    # save
    with open("/Volumes/T9/BWE/40_EXPERIMENTS/round4/validation/c_trigger_validation.json", "w") as f:
        json.dump({
            "C1_up": c1_up_stats, "C1_dn": c1_dn_stats,
            "C2": c2_stats, "C3": c3_stats,
            "C4": c4_stats, "C5": c5_stats,
            "decisions": decisions,
        }, f, indent=2, default=str)
    print(f"\n  Saved: c_trigger_validation.json")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
