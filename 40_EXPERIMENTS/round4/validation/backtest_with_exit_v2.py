"""Backtest 4 enabled strategies USING REAL exit_v2 simulation.

Per user's preference: time_exit DISABLED. Exit only via:
  - TP ladder (partial exits)
  - Dynamic trailing stop
  - ATR-aware hard stop
  - Catastrophe stop (with head-grace)
  - G2 TRADOOR-saver
  - Volume-confirmed breakdown

Lifecycle-aware: sustained/late_burst → wider trail; spike_decay → tighter.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from collections import defaultdict
from statistics import mean, stdev

sys.path.insert(0, '/Users/ye/.hermes/scripts')
sys.path.insert(0, '/Users/ye/.hermes/scripts/bwe_v2')
sys.path.insert(0, '/Volumes/T9/BWE/40_EXPERIMENTS/round4/exit_v2')

from bwe_live_trigger_strategies import TriggerEngine
from exit_v2 import ExitEngine, ExitConfig, Position, Bar
from lifecycle_aware_config import build_exit_config

LIVE_DB = "/Users/ye/.hermes/research/binance_futures_1m_collector_runtime/binance_futures_1m.sqlite3"
EXT_DB = "/Volumes/T9/binance data/historical/binance_extended_history.sqlite3"
JSONL = "/Users/ye/.hermes/logs/bwe_matrix_posts.jsonl"

ENABLED = {
    'oi_overcrowded_crash_follow_short',
    'reserved6_extreme_pump_fade_short',
    'reserved6_extreme_dump_meanrevert_long',
    'pc_pump_cont_long',  # include for comparison even though disabled in live
}

MAX_BARS_AFTER_ENTRY = 4320  # = 72h max scan,exit_v2 will exit much earlier


def open_db(path):
    if path.startswith('/Volumes/T9'):
        return sqlite3.connect(f'file:{path}?mode=ro', uri=True, timeout=30)
    c = sqlite3.connect(path, timeout=30)
    c.execute("PRAGMA query_only=1")
    return c


def get_bars(con, sym, from_ts_ms, n=MAX_BARS_AFTER_ENTRY, fallback_con=None):
    """Get n minute bars starting from from_ts_ms."""
    for c in [con, fallback_con]:
        if c is None: continue
        rows = c.execute(
            "SELECT open_time_ms, open, high, low, close, volume "
            "FROM klines_1m WHERE symbol=? AND open_time_ms >= ? "
            "ORDER BY open_time_ms LIMIT ?",
            (sym, from_ts_ms, n)
        ).fetchall()
        if len(rows) >= 60:  # at least 1h of data
            return [Bar(ts_ms=r[0], open=r[1], high=r[2], low=r[3], close=r[4], volume=r[5]) for r in rows]
    return []


def get_lifecycle(con_features, sym):
    r = con_features.execute(
        "SELECT lifecycle, yaobi_score FROM symbol_features WHERE symbol=?",
        (sym,)
    ).fetchone()
    if r:
        return r[0]
    return "quiet"


def compute_atr_pct(bars, period=14):
    if len(bars) < period + 1:
        return 1.0
    trs = []
    for i in range(-period, 0):
        h, l = bars[i].high, bars[i].low
        prev_c = bars[i-1].close if i-1 >= -len(bars) else bars[i].close
        tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
        trs.append(tr)
    atr = sum(trs) / len(trs)
    cur_close = bars[-1].close
    return atr / cur_close * 100 if cur_close > 0 else 1.0


def simulate_trade(entry_bar_idx, bars, side, lifecycle):
    """Simulate trade from entry_bar onwards with exit_v2 (NO TIME EXIT)."""
    if entry_bar_idx >= len(bars) - 5:
        return None  # not enough bars

    entry_bar = bars[entry_bar_idx]
    pre_entry_bars = bars[max(0, entry_bar_idx - 30):entry_bar_idx + 1]
    atr_pct = compute_atr_pct(pre_entry_bars)

    # Build lifecycle-aware ExitConfig + DISABLE time exit
    cfg = build_exit_config(lifecycle)
    cfg = ExitConfig(
        activation_delay_min=cfg.activation_delay_min,
        trail_activate_pct=cfg.trail_activate_pct,
        trail_tiers=cfg.trail_tiers,
        hard_stop_min_pct=cfg.hard_stop_min_pct,
        hard_stop_atr_mult=cfg.hard_stop_atr_mult,
        catastrophe_min_hold_min=cfg.catastrophe_min_hold_min,
        catastrophe_grace_multiplier=cfg.catastrophe_grace_multiplier,
        catastrophe_pct=cfg.catastrophe_pct,
        volume_confirm_enabled=cfg.volume_confirm_enabled,
        volume_confirm_lookback_min=cfg.volume_confirm_lookback_min,
        volume_confirm_baseline_min=cfg.volume_confirm_baseline_min,
        volume_confirm_ratio=cfg.volume_confirm_ratio,
        tradoor_saver_enabled=cfg.tradoor_saver_enabled,
        tradoor_saver_hw_threshold=cfg.tradoor_saver_hw_threshold,
        tradoor_saver_max_hw_age_min=cfg.tradoor_saver_max_hw_age_min,
        tradoor_saver_vol_ratio=cfg.tradoor_saver_vol_ratio,
        time_exit_at_hold_limit=False,  # ⭐ user preference
    )
    engine = ExitEngine(cfg)

    pos = Position(
        side=side,
        entry_ts_ms=entry_bar.ts_ms,
        entry_px=entry_bar.close,
        hold_minutes_limit=999_999,
        atr_at_entry=atr_pct,
        high_water_pct=0.0,
    )

    # Walk forward bars
    for i in range(entry_bar_idx + 1, len(bars)):
        slice_bars = bars[max(0, i - 60):i + 1]
        decision = engine.decide(pos, slice_bars)
        if decision is not None:
            hold_min = (bars[i].ts_ms - entry_bar.ts_ms) / 60000
            return {
                "exit_ts_ms": decision.exit_ts_ms,
                "exit_px": decision.exit_px,
                "pnl_pct": decision.pnl_pct,
                "reason": decision.reason,
                "hold_min": hold_min,
                "lifecycle": lifecycle,
            }

    # Walked to end without exit → mark as max-hold
    last_bar = bars[-1]
    hold_min = (last_bar.ts_ms - entry_bar.ts_ms) / 60000
    if pos.side == "long":
        pnl = (last_bar.close - pos.entry_px) / pos.entry_px * 100
    else:
        pnl = (pos.entry_px - last_bar.close) / pos.entry_px * 100
    return {
        "exit_ts_ms": last_bar.ts_ms,
        "exit_px": last_bar.close,
        "pnl_pct": pnl,
        "reason": "end_of_data",
        "hold_min": hold_min,
        "lifecycle": lifecycle,
    }


def main():
    print("="*92)
    print("Backtest WITH exit_v2 (time_exit DISABLED) on 30d")
    print("="*92)

    # Load BWE events
    with open(JSONL) as f:
        events_raw = [json.loads(l) for l in f if l.strip()]

    # Run trigger_engine
    te = TriggerEngine()
    triggers = []
    for ev in events_raw:
        try:
            for t in te.evaluate_raw_event(ev):
                if t.get('strategy_name') in ENABLED:
                    sym = t.get('market_symbol') or t.get('symbol')
                    if sym and not sym.endswith('USDT'):
                        sym = sym + 'USDT'
                    triggers.append({
                        'strategy': t['strategy_name'],
                        'symbol': sym,
                        'side': t['side'],
                        'event_ts_ms': int(t.get('event_ts_ms') or ev.get('ts_ms') or 0),
                        'entry_delay_s': int(t.get('entry_delay_s') or 0),
                    })
        except Exception:
            pass

    print(f"\n{len(triggers)} enabled-strategy triggers")
    by_strat = defaultdict(int)
    for t in triggers: by_strat[t['strategy']] += 1
    for s, n in sorted(by_strat.items(), key=lambda x: -x[1]):
        print(f"  {s:42s} {n}")

    # Connect DBs
    con = open_db(LIVE_DB)
    try: con_ext = open_db(EXT_DB)
    except: con_ext = None
    con_features = open_db(LIVE_DB)

    # Simulate each trade
    print(f"\nSimulating exits via exit_v2 (time_exit=False)...")
    results = []
    for i, t in enumerate(triggers):
        sym = t['symbol']
        entry_target_ts = t['event_ts_ms'] + t['entry_delay_s'] * 1000

        # Get bars from entry to +72h (4320 min)
        bars = get_bars(con, sym, entry_target_ts, n=4320, fallback_con=con_ext)
        if len(bars) < 60:
            continue

        # Find entry bar (closest to entry_target_ts)
        entry_idx = 0  # first bar at or after entry_target_ts

        lifecycle = get_lifecycle(con_features, sym)
        outcome = simulate_trade(entry_idx, bars, t['side'], lifecycle)
        if outcome is None:
            continue
        results.append({
            **t,
            **outcome,
        })
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(triggers)}")

    print(f"\nSimulated {len(results)} trades")

    # Aggregate
    print("\n" + "="*92)
    print("Per-Strategy Results (real exit_v2,no time exit)")
    print("="*92)
    print(f"  {'strategy':<42s} {'n':>4s} {'avg':>8s} {'win%':>6s} {'sum':>9s} {'avg_hold':>10s} {'reasons':<30s}")
    print("-"*100)

    by_strat_data = defaultdict(list)
    for r in results:
        by_strat_data[r['strategy']].append(r)

    summary = []
    for s, data in sorted(by_strat_data.items(), key=lambda x: -len(x[1])):
        pnls = [r['pnl_pct'] for r in data]
        holds = [r['hold_min'] for r in data]
        n = len(pnls)
        avg = mean(pnls)
        w = sum(1 for p in pnls if p > 0) / n * 100
        s_total = sum(pnls)
        avg_hold = mean(holds)

        # Reason breakdown
        from collections import Counter
        reasons = Counter(r['reason'] for r in data)
        top_reasons = ', '.join(f"{rc}:{cnt}" for rc, cnt in reasons.most_common(3))

        print(f"  {s:<42s} {n:>4d} {avg:>+7.2f}% {w:>5.1f}% {s_total:>+8.1f}% {avg_hold:>7.0f}min  {top_reasons[:30]}")
        summary.append({'strategy': s, 'n': n, 'mean': avg, 'win_rate': w,
                        'sum_raw': s_total, 'avg_hold_min': avg_hold,
                        'reasons': dict(reasons)})

    # Save
    out_path = '/Volumes/T9/BWE/40_EXPERIMENTS/round4/validation/backtest_with_exit_v2_results.json'
    with open(out_path, 'w') as f:
        json.dump({'summary': summary, 'n_triggers': len(triggers), 'n_simulated': len(results)}, f, indent=2)
    print(f"\nSaved: {out_path}")

    con.close()
    if con_ext: con_ext.close()
    con_features.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
