"""Backtest 4 enabled strategies on 30d data.

For each BWE event in jsonl, run trigger_engine to find triggers.
For each trigger, compute forward N-minute return (multiple horizons).
Apply side-aware outcome (long/short).
Aggregate per strategy with stats.

This is a SIMPLE backtest — uses fixed-horizon forward returns as proxy
for v2 exit outcome. Real v2 exit may do better/worse.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from collections import defaultdict
from statistics import mean, stdev

sys.path.insert(0, '/Users/ye/.hermes/scripts')
from bwe_live_trigger_strategies import TriggerEngine

LIVE_DB = (
    "/Users/ye/.hermes/research/binance_futures_1m_collector_runtime/"
    "binance_futures_1m.sqlite3"
)
EXT_DB = "/Volumes/T9/binance data/historical/binance_extended_history.sqlite3"
JSONL = "/Users/ye/.hermes/logs/bwe_matrix_posts.jsonl"

ENABLED = {
    'oi_overcrowded_crash_follow_short',
    'pc_pump_cont_long',
    'reserved6_extreme_pump_fade_short',
    'reserved6_extreme_dump_meanrevert_long',
}


def open_db_ro(path: str) -> sqlite3.Connection:
    if path.startswith('/Volumes/T9'):
        return sqlite3.connect(f'file:{path}?mode=ro', uri=True, timeout=30)
    con = sqlite3.connect(path, timeout=30)
    con.execute('PRAGMA query_only=1')
    return con


def forward_return(con, sym, ts_ms, horizon_min):
    """Forward N-min return from current close. Round to minute for kline lookup."""
    ts_min = (ts_ms // 60000) * 60000
    target_min = ts_min + horizon_min * 60000
    cur = con.execute(
        "SELECT close FROM klines_1m WHERE symbol=? AND open_time_ms <= ? "
        "ORDER BY open_time_ms DESC LIMIT 1", (sym, ts_ms)
    ).fetchone()
    fut = con.execute(
        "SELECT close FROM klines_1m WHERE symbol=? AND open_time_ms BETWEEN ? AND ? "
        "ORDER BY ABS(open_time_ms - ?) LIMIT 1",
        (sym, target_min - 60000, target_min + 120000, target_min)
    ).fetchone()
    if not cur or not fut or cur[0] <= 0:
        return None
    return (fut[0] - cur[0]) / cur[0] * 100


def main():
    print("="*80)
    print("Backtest 4 Enabled Strategies on 30d Market Data")
    print("="*80)

    # Load BWE events
    with open(JSONL) as f:
        events_raw = [json.loads(l) for l in f if l.strip()]
    print(f"\nLoaded {len(events_raw)} BWE events from jsonl")

    # Run trigger_engine on each event
    te = TriggerEngine()
    triggers = []
    for ev in events_raw:
        try:
            tlist = te.evaluate_raw_event(ev)
            for t in tlist:
                if t.get('strategy_name') in ENABLED:
                    triggers.append({
                        'strategy': t['strategy_name'],
                        'symbol': t.get('symbol'),
                        'market_symbol': t.get('market_symbol'),
                        'side': t['side'],
                        'event_ts_ms': int(t.get('event_ts_ms') or ev.get('ts_ms') or 0),
                        'channel': t.get('channel'),
                    })
        except Exception:
            pass

    print(f"Found {len(triggers)} enabled-strategy triggers")
    by_strat = defaultdict(int)
    for t in triggers:
        by_strat[t['strategy']] += 1
    for s, n in sorted(by_strat.items(), key=lambda x: -x[1]):
        print(f"  {s:42s} {n:>4} triggers")

    # Compute forward returns for each trigger (multiple horizons)
    print(f"\nComputing forward returns (60min + 120min)...")
    con = open_db_ro(LIVE_DB)
    try:
        con_ext = open_db_ro(EXT_DB)
    except Exception:
        con_ext = None

    def get_fwd(sym, ts_ms, hz):
        # try market_symbol first (e.g. SKYAIUSDT)
        for s_try in [sym, sym + 'USDT' if sym and not sym.endswith('USDT') else sym]:
            r = forward_return(con, s_try, ts_ms, hz)
            if r is not None:
                return r
            if con_ext:
                r = forward_return(con_ext, s_try, ts_ms, hz)
                if r is not None:
                    return r
        return None

    enriched = []
    for i, t in enumerate(triggers):
        sym = t.get('market_symbol') or t['symbol']
        for hz in [60, 120]:
            fwd = get_fwd(sym, t['event_ts_ms'], hz)
            if fwd is None:
                continue
            # Side-aware outcome
            if t['side'] == 'long':
                outcome = fwd
            else:  # short
                outcome = -fwd
            enriched.append({
                **t, 'horizon_min': hz, 'forward_return': fwd, 'outcome': outcome,
            })
        if (i+1) % 50 == 0:
            print(f"  {i+1}/{len(triggers)} processed")

    print(f"\nEnriched: {len(enriched)} (trigger × horizon)")

    # Aggregate per strategy × horizon
    print("\n" + "="*80)
    print("Per-Strategy Backtest Results")
    print("="*80)
    print(f"\n  {'strategy':<42s} {'hz':<5s} {'n':>4s} {'avg':>8s} {'win%':>6s} {'sum':>9s} {'p25':>7s} {'p75':>7s}")
    print("-"*92)

    by_combo = defaultdict(list)
    for e in enriched:
        by_combo[(e['strategy'], e['horizon_min'])].append(e['outcome'])

    summary = []
    for (s, hz), outs in sorted(by_combo.items(), key=lambda x: (x[0][0], x[0][1])):
        if not outs:
            continue
        n = len(outs)
        avg = mean(outs)
        w = sum(1 for o in outs if o > 0) / n * 100
        s_total = sum(outs)
        outs_sorted = sorted(outs)
        p25 = outs_sorted[n//4]
        p75 = outs_sorted[3*n//4]
        print(f"  {s:<42s} {hz:<5d} {n:>4d} {avg:>+7.2f}% {w:>5.1f}% {s_total:>+8.1f}% {p25:>+6.1f}% {p75:>+6.1f}%")
        summary.append({
            'strategy': s, 'horizon_min': hz, 'n': n, 'mean': avg,
            'win_rate': w, 'sum_raw': s_total, 'p25': p25, 'p75': p75,
        })

    # Save summary
    out_path = '/Volumes/T9/BWE/40_EXPERIMENTS/round4/validation/backtest_4strategies_30d.json'
    with open(out_path, 'w') as f:
        json.dump({'summary': summary, 'n_triggers': len(triggers), 'n_enriched': len(enriched)}, f, indent=2)
    print(f"\nSaved: {out_path}")

    # Recommendation
    print("\n" + "="*80)
    print("Recommendation")
    print("="*80)
    for r in summary:
        if r['horizon_min'] == 60:  # focus 60min
            verdict = "✅ KEEP" if r['mean'] > 0.3 and r['win_rate'] > 52 else \
                      "❌ DROP" if r['mean'] < 0 or r['win_rate'] < 48 else "⚠ MARGINAL"
            print(f"  {r['strategy']:42s} 60min: mean {r['mean']:+.2f}% win {r['win_rate']:.1f}%  {verdict}")

    con.close()
    if con_ext:
        con_ext.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
