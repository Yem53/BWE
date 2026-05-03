"""Deep dive on top 妖币: lifecycle, reaction pattern, wave structure.

For each top-N 妖币:
  1. Lifecycle: events distribution across days → spike_decay / sustained /
     single_burst / quiet
  2. Reaction: post-event 30min/1h/3h price → mean_revert / trend_continue / mixed
  3. Wave structure: avg duration, pre-event volume ratio
  4. v2 PnL & win rate (separately for fade/follow theses)

Aggregate insights across 30 top 妖币 to reveal common patterns + differences.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "exit_v2"))
from exit_v2 import Bar, ExitConfig, ExitEngine, Position, compute_atr_pct

KLINE_DB = "/Users/ye/.hermes/research/binance_futures_1m_collector_runtime/binance_futures_1m.sqlite3"
SCORE_PATH = Path("/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits/yaobi_score_v0.json")
OUT_PATH = Path("/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits/yaobi_per_symbol_dive.json")

TOP_N = 100
EVENT_PCT = 8.0
WAVE_GAP_MIN = 15
POST_HORIZONS = [30, 60, 180]  # minutes after wave end


@dataclass
class Wave:
    start_idx: int
    end_idx: int
    peak_idx: int
    peak_ret: float
    duration_min: int
    pre_vol_ratio: float = 0.0
    post_returns: dict[int, float] = field(default_factory=dict)  # horizon → ret%
    fade_v2_pnl: float | None = None
    follow_v2_pnl: float | None = None


def find_waves(rows: list) -> list[Wave]:
    """Find all ±8% events, cluster into waves."""
    raw = []
    for i in range(5, len(rows)):
        c_now = rows[i][4]; c_then = rows[i-5][4]
        if c_then > 0:
            ret = (c_now - c_then) / c_then * 100
            if abs(ret) >= EVENT_PCT:
                raw.append((i, ret))

    waves: list[Wave] = []
    cur: list[tuple[int, float]] = []
    for idx, ret in raw:
        if cur and idx - cur[-1][0] > WAVE_GAP_MIN:
            peak_idx, peak_ret = max(cur, key=lambda x: abs(x[1]))
            waves.append(Wave(start_idx=cur[0][0], end_idx=cur[-1][0],
                              peak_idx=peak_idx, peak_ret=peak_ret,
                              duration_min=cur[-1][0] - cur[0][0] + 1))
            cur = []
        cur.append((idx, ret))
    if cur:
        peak_idx, peak_ret = max(cur, key=lambda x: abs(x[1]))
        waves.append(Wave(start_idx=cur[0][0], end_idx=cur[-1][0],
                          peak_idx=peak_idx, peak_ret=peak_ret,
                          duration_min=cur[-1][0] - cur[0][0] + 1))
    return waves


def enrich_wave(w: Wave, rows: list) -> None:
    """Compute pre-vol ratio + post-event returns."""
    pi = w.peak_idx
    # Pre-vol: 5 min before wave start vs prior 30 min baseline
    s = w.start_idx
    pre5 = rows[max(0, s - 5):s]
    base30 = rows[max(0, s - 35):s - 5]
    if pre5 and base30:
        pre_vol = sum(r[5] for r in pre5) / len(pre5)
        base_vol = sum(r[5] for r in base30) / len(base30)
        w.pre_vol_ratio = pre_vol / base_vol if base_vol > 0 else 0

    # Post-returns: from end of wave, look forward H minutes
    end_close = rows[w.end_idx][4]
    for h in POST_HORIZONS:
        target = w.end_idx + h
        if target < len(rows) and end_close > 0:
            ret = (rows[target][4] - end_close) / end_close * 100
            w.post_returns[h] = ret


def replay_v2(entry_idx: int, side: str, rows: list, engine: ExitEngine) -> float | None:
    """Replay v2 exit from entry_idx (next bar = entry)."""
    if entry_idx + 1 >= len(rows):
        return None
    entry_ts = rows[entry_idx + 1][0]
    entry_px = rows[entry_idx + 1][1]
    start_idx = max(0, entry_idx - 35)
    end_idx = min(len(rows), entry_idx + 360)
    bars = [Bar(*r) for r in rows[start_idx:end_idx]]
    pre = [b for b in bars if b.ts_ms < entry_ts]
    atr = compute_atr_pct(pre, period=14, ref_px=entry_px) if pre else 0.0
    pos = Position(entry_ts_ms=entry_ts, entry_px=entry_px, side=side,
                   hold_minutes_limit=360.0, atr_at_entry=atr)
    eidx = next((i for i, b in enumerate(bars) if b.ts_ms >= entry_ts), None)
    if eidx is None:
        return None
    for i in range(eidx, len(bars)):
        d = engine.decide(pos, bars[: i + 1])
        if d:
            return d.pnl_pct
    last = bars[-1]
    return ((last.close - entry_px) / entry_px * 100 if side == "long"
            else (entry_px - last.close) / entry_px * 100)


def classify_lifecycle(waves: list[Wave], rows: list) -> str:
    """spike_decay | sustained | single_burst | quiet."""
    n = len(waves)
    if n == 0:
        return "quiet"
    if n <= 2:
        return "single_burst"
    # Time-of-occurrence distribution
    span_ms = rows[-1][0] - rows[0][0]
    if span_ms <= 0:
        return "single_burst"
    # Fraction of waves in first half of timeline
    midpoint = rows[0][0] + span_ms / 2
    early = sum(1 for w in waves if rows[w.start_idx][0] < midpoint)
    if early / n >= 0.75:
        return "spike_decay"
    if early / n <= 0.25:
        return "late_burst"
    return "sustained"


def classify_reaction(waves: list[Wave]) -> str:
    """mean_revert | trend_continue | mixed.

    Look at 60-min post-event return vs peak direction.
    Mean-revert: post_ret has OPPOSITE sign of peak_ret.
    Trend-continue: post_ret has SAME sign.
    """
    if not waves:
        return "n/a"
    revert = 0; cont = 0; n_eligible = 0
    for w in waves:
        if 60 not in w.post_returns:
            continue
        n_eligible += 1
        post = w.post_returns[60]
        if (w.peak_ret > 0 and post < -1) or (w.peak_ret < 0 and post > 1):
            revert += 1
        elif (w.peak_ret > 0 and post > 1) or (w.peak_ret < 0 and post < -1):
            cont += 1
    if n_eligible == 0:
        return "n/a"
    if revert / n_eligible >= 0.6:
        return "mean_revert"
    if cont / n_eligible >= 0.6:
        return "trend_continue"
    return "mixed"


def analyze_symbol(con, symbol, eng):
    cur = con.execute(
        "SELECT open_time_ms, open, high, low, close, volume FROM klines_1m "
        "WHERE symbol=? ORDER BY open_time_ms", (symbol,))
    rows = cur.fetchall()
    if len(rows) < 60:
        return None
    waves = find_waves(rows)

    # Enrich + replay
    for w in waves:
        enrich_wave(w, rows)
        # Fade thesis: trade against the move
        fade_side = "short" if w.peak_ret > 0 else "long"
        w.fade_v2_pnl = replay_v2(w.peak_idx, fade_side, rows, eng)
        # Follow thesis: trade with the move
        follow_side = "long" if w.peak_ret > 0 else "short"
        w.follow_v2_pnl = replay_v2(w.peak_idx, follow_side, rows, eng)

    # Aggregate
    fade_pnls = [w.fade_v2_pnl for w in waves if w.fade_v2_pnl is not None]
    follow_pnls = [w.follow_v2_pnl for w in waves if w.follow_v2_pnl is not None]

    return {
        "symbol": symbol,
        "n_bars": len(rows),
        "n_waves": len(waves),
        "lifecycle": classify_lifecycle(waves, rows),
        "reaction": classify_reaction(waves),
        "avg_wave_duration_min": (sum(w.duration_min for w in waves) / len(waves)
                                   if waves else 0),
        "avg_pre_vol_ratio": (sum(w.pre_vol_ratio for w in waves) / len(waves)
                              if waves else 0),
        "max_peak_ret": max((abs(w.peak_ret) for w in waves), default=0),
        "fade_total_pnl": sum(fade_pnls),
        "fade_mean_pnl": sum(fade_pnls)/len(fade_pnls) if fade_pnls else 0,
        "fade_win_rate": sum(1 for p in fade_pnls if p > 0)/len(fade_pnls)*100 if fade_pnls else 0,
        "follow_total_pnl": sum(follow_pnls),
        "follow_mean_pnl": sum(follow_pnls)/len(follow_pnls) if follow_pnls else 0,
        "follow_win_rate": sum(1 for p in follow_pnls if p > 0)/len(follow_pnls)*100 if follow_pnls else 0,
        "waves": [{"peak_ret": w.peak_ret, "duration_min": w.duration_min,
                   "pre_vol_x": w.pre_vol_ratio,
                   "post_30m": w.post_returns.get(30, 0),
                   "post_60m": w.post_returns.get(60, 0),
                   "post_180m": w.post_returns.get(180, 0),
                   "fade_v2": w.fade_v2_pnl, "follow_v2": w.follow_v2_pnl}
                  for w in waves],
    }


def main():
    score_data = json.loads(SCORE_PATH.read_text())
    sym_to_score = {m["symbol"]: m["yaobi_score"] for m in score_data["ranked"]}
    # Top N + reference picks
    top = sorted(sym_to_score.items(), key=lambda x: -x[1])[:TOP_N]
    print(f"Analyzing top {TOP_N} 妖币 (deep dive)...")
    print()

    con = sqlite3.connect(KLINE_DB)
    eng = ExitEngine(ExitConfig())
    results = []
    for sym, score in top:
        r = analyze_symbol(con, sym, eng)
        if r:
            r["score"] = score
            results.append(r)

    # Print summary table
    print("=" * 130)
    print(f"{'symbol':12s} {'score':>5s} {'n_w':>4s} {'lifecycle':>14s} "
          f"{'reaction':>15s} {'dur':>5s} {'pre_v':>6s} {'max_pk':>7s} | "
          f"{'fade_tot':>9s} {'fade_w%':>7s} | {'follow_tot':>10s} {'flw_w%':>7s}")
    print("-" * 130)
    for r in results:
        print(f"{r['symbol']:12s} {r['score']:>5.1f} {r['n_waves']:>4d} "
              f"{r['lifecycle']:>14s} {r['reaction']:>15s} "
              f"{r['avg_wave_duration_min']:>4.1f}m {r['avg_pre_vol_ratio']:>5.1f}x "
              f"{r['max_peak_ret']:>+6.1f}% | "
              f"{r['fade_total_pnl']:>+8.1f}% {r['fade_win_rate']:>6.1f}% | "
              f"{r['follow_total_pnl']:>+9.1f}% {r['follow_win_rate']:>6.1f}%")

    # Aggregate
    print()
    print("=" * 90)
    print("LIFECYCLE distribution + thesis effectiveness")
    print("=" * 90)
    lifecycle_groups: dict[str, list] = {}
    reaction_groups: dict[str, list] = {}
    for r in results:
        lifecycle_groups.setdefault(r["lifecycle"], []).append(r)
        reaction_groups.setdefault(r["reaction"], []).append(r)

    for lc, group in sorted(lifecycle_groups.items(), key=lambda x: -len(x[1])):
        n_waves_total = sum(g["n_waves"] for g in group)
        fade_total = sum(g["fade_total_pnl"] for g in group)
        follow_total = sum(g["follow_total_pnl"] for g in group)
        symbols = ", ".join(g["symbol"].replace("USDT","") for g in group[:8])
        if len(group) > 8: symbols += f" (+{len(group)-8} more)"
        print(f"  {lc:14s} {len(group):>3d} coins  {n_waves_total:>3d} waves  "
              f"fade_total={fade_total:>+7.1f}%  follow_total={follow_total:>+7.1f}%")
        print(f"    coins: {symbols}")

    print()
    print("=" * 90)
    print("REACTION pattern distribution")
    print("=" * 90)
    for rx, group in sorted(reaction_groups.items(), key=lambda x: -len(x[1])):
        n_waves_total = sum(g["n_waves"] for g in group)
        fade_total = sum(g["fade_total_pnl"] for g in group)
        follow_total = sum(g["follow_total_pnl"] for g in group)
        symbols = ", ".join(g["symbol"].replace("USDT","") for g in group[:8])
        if len(group) > 8: symbols += f" (+{len(group)-8} more)"
        print(f"  {rx:15s} {len(group):>3d} coins  {n_waves_total:>3d} waves  "
              f"fade_total={fade_total:>+7.1f}%  follow_total={follow_total:>+7.1f}%")
        print(f"    coins: {symbols}")

    # Cross-tab: lifecycle × reaction → which combo wins?
    print()
    print("=" * 90)
    print("CROSS-TAB: which lifecycle × reaction combo wins?")
    print("=" * 90)
    print(f"{'lifecycle×reaction':30s} {'n_coins':>8s} {'n_waves':>8s} "
          f"{'fade_PnL':>10s} {'follow_PnL':>11s}  best_thesis")
    cross: dict[tuple, list] = {}
    for r in results:
        cross.setdefault((r["lifecycle"], r["reaction"]), []).append(r)
    for (lc, rx), group in sorted(cross.items(), key=lambda x: -len(x[1])):
        n_waves = sum(g["n_waves"] for g in group)
        fade = sum(g["fade_total_pnl"] for g in group)
        follow = sum(g["follow_total_pnl"] for g in group)
        best = "FADE" if fade > follow else ("FOLLOW" if follow > fade else "tie")
        print(f"  {lc+'×'+rx:30s} {len(group):>8d} {n_waves:>8d} "
              f"{fade:>+9.1f}% {follow:>+10.1f}%  → {best}")

    # Pre-vol ratio analysis
    print()
    print("=" * 90)
    print("PRE-EVENT VOLUME RATIO — does it predict winner waves?")
    print("=" * 90)
    all_waves = []
    for r in results:
        for w in r["waves"]:
            if w["fade_v2"] is not None and w["pre_vol_x"] > 0:
                all_waves.append(w)
    if all_waves:
        all_waves.sort(key=lambda w: -w["pre_vol_x"])
        print(f"  Total waves with pre-vol data: {len(all_waves)}")
        # Bucket by pre-vol ratio
        for lo, hi, lbl in [(0, 1.5, "<1.5x"), (1.5, 2.5, "1.5-2.5x"),
                             (2.5, 4.0, "2.5-4x"), (4.0, 100, ">=4x")]:
            sub = [w for w in all_waves if lo <= w["pre_vol_x"] < hi]
            if not sub:
                continue
            fade_avg = sum(w["fade_v2"] for w in sub) / len(sub)
            fade_win = sum(1 for w in sub if w["fade_v2"] > 0) / len(sub) * 100
            print(f"  pre_vol_x {lbl:10s}: n={len(sub):>3d}  "
                  f"fade_mean={fade_avg:>+5.2f}%  fade_win={fade_win:>5.1f}%")

    # Wave duration analysis
    print()
    print("=" * 90)
    print("WAVE DURATION — does it predict winner waves?")
    print("=" * 90)
    all_w_dur = [w for r in results for w in r["waves"] if w["fade_v2"] is not None]
    for lo, hi, lbl in [(1, 3, "1-2 min"), (3, 6, "3-5 min"),
                         (6, 10, "6-9 min"), (10, 99, "10+ min")]:
        sub = [w for w in all_w_dur if lo <= w["duration_min"] < hi]
        if not sub:
            continue
        fade_avg = sum(w["fade_v2"] for w in sub) / len(sub)
        fade_win = sum(1 for w in sub if w["fade_v2"] > 0) / len(sub) * 100
        print(f"  duration {lbl:10s}: n={len(sub):>3d}  "
              f"fade_mean={fade_avg:>+5.2f}%  fade_win={fade_win:>5.1f}%")

    OUT_PATH.write_text(json.dumps({"results": results}, indent=2, default=str))
    print(f"\n  saved: {OUT_PATH}")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
