"""Parameter sweep on Reserved6 strategies.

Sweep magnitude threshold (5/8/10/12/15%) × hold horizon (30/60/90/120/180 min)
+ separate pump/dump split.

For each combo: count events, mean outcome, win rate, train/test split (70/30).
Output: Pareto frontier of robust winners.
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from itertools import product
from statistics import mean

JSONL = "/Users/ye/.hermes/logs/bwe_matrix_posts.jsonl"
DB = "/Users/ye/.hermes/research/binance_futures_1m_collector_runtime/binance_futures_1m.sqlite3"

SYMBOL_RE = re.compile(r"\b([A-Z][A-Z0-9]+USDT)\b")
PCT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")


def parse(text: str):
    sm = SYMBOL_RE.search(text); pm = PCT_RE.search(text)
    if not sm or not pm:
        return None
    pct = float(pm.group(1))
    if "🟢" in text or "飙升" in text or "surged" in text.lower():
        side = "pump"
    elif "🔻" in text or "下跌" in text or "drop" in text.lower():
        side = "dump"
    else:
        return None
    return sm.group(1), side, pct


def fwd(con, sym, ts_ms, hz, fallback_con=None):
    target = (ts_ms // 60000 + hz) * 60000
    for c in [con, fallback_con]:
        if c is None: continue
        cur = c.execute("SELECT close FROM klines_1m WHERE symbol=? AND open_time_ms <= ? ORDER BY open_time_ms DESC LIMIT 1", (sym, ts_ms)).fetchone()
        fut = c.execute("SELECT close FROM klines_1m WHERE symbol=? AND open_time_ms BETWEEN ? AND ? ORDER BY ABS(open_time_ms - ?) LIMIT 1", (sym, target-60000, target+120000, target)).fetchone()
        if cur and fut and cur[0] > 0:
            return (fut[0] - cur[0]) / cur[0] * 100
    return None


def main():
    print("="*92)
    print("Reserved6 Parameter Sweep on 30d Data")
    print("="*92)

    # Load Reserved6 events with klines available
    con = sqlite3.connect(DB, timeout=30)
    con.execute("PRAGMA query_only=1")
    try:
        con_ext = sqlite3.connect("file:/Volumes/T9/binance data/historical/binance_extended_history.sqlite3?mode=ro", uri=True, timeout=30)
    except Exception:
        con_ext = None

    events = []
    with open(JSONL) as f:
        for line in f:
            try: d = json.loads(line)
            except: continue
            if (d.get("channel") or d.get("source")) != "BWE_Reserved6":
                continue
            if d.get("type") != "post":
                continue
            res = parse(d.get("text", ""))
            if not res:
                continue
            sym, side, pct = res
            ts = int(d.get("event_ts_ms") or d.get("ts_ms") or 0)
            events.append({"sym": sym, "side": side, "pct": pct, "ts_ms": ts})

    print(f"\nLoaded {len(events)} Reserved6 events")

    MAGS = [5, 8, 10, 12, 15]
    HZS = [30, 60, 90, 120, 180]

    # Side × magnitude × horizon × direction (fade/follow)
    print(f"\nSweeping {len(MAGS)} mag × {len(HZS)} hz × 2 sides × 2 directions = {len(MAGS)*len(HZS)*4} combos\n")
    print(f"  {'side':<5s} {'min_mag':<8s} {'hz':<4s} {'dir':<8s} {'n':>4s} {'avg':>8s} {'win%':>6s} {'sum':>9s} {'train_avg':>10s} {'test_avg':>10s} {'robust?':>8s}")
    print("-"*112)

    robust = []
    for side in ['pump', 'dump']:
        for min_mag in MAGS:
            sub = [e for e in events if e['side'] == side and e['pct'] >= min_mag]
            for hz in HZS:
                # Compute outcomes for this filter
                outcomes_fade = []
                outcomes_follow = []
                ts_outs = []
                for e in sub:
                    f = fwd(con, e['sym'], e['ts_ms'], hz, fallback_con=con_ext)
                    if f is None: continue
                    if side == 'pump':
                        fade_o = -f  # short fades pump
                        follow_o = f   # long follows pump
                    else:
                        fade_o = f   # long fades dump (mean revert)
                        follow_o = -f  # short follows dump
                    outcomes_fade.append(fade_o)
                    outcomes_follow.append(follow_o)
                    ts_outs.append((e['ts_ms'], fade_o, follow_o))

                n = len(outcomes_fade)
                if n < 20: continue

                # Train/test split (70/30 by time)
                ts_outs.sort()
                split = int(n * 0.7)

                for direction, outs, get_train, get_test in [
                    ('fade', outcomes_fade, [t[1] for t in ts_outs[:split]], [t[1] for t in ts_outs[split:]]),
                    ('follow', outcomes_follow, [t[2] for t in ts_outs[:split]], [t[2] for t in ts_outs[split:]]),
                ]:
                    avg = mean(outs)
                    w = sum(1 for o in outs if o > 0) / n * 100
                    s_total = sum(outs)
                    train_avg = mean(get_train) if get_train else 0
                    test_avg = mean(get_test) if get_test else 0

                    # Robustness: train AND test both > 0.5%
                    is_robust = (train_avg > 0.5 and test_avg > 0.5 and len(get_test) >= 10)

                    if avg > 0.3 or is_robust:  # only print interesting ones
                        mark = "✅" if is_robust else "⚠"
                        print(f"  {side:<5s} {min_mag:<8d} {hz:<4d} {direction:<8s} {n:>4d} {avg:>+7.2f}% {w:>5.1f}% {s_total:>+8.1f}% {train_avg:>+9.2f}% {test_avg:>+9.2f}% {mark:>8s}")
                        if is_robust:
                            robust.append({
                                'side': side, 'min_mag': min_mag, 'hz': hz, 'direction': direction,
                                'n': n, 'avg': avg, 'win_rate': w, 'train_avg': train_avg, 'test_avg': test_avg,
                            })

    print("\n" + "="*92)
    print(f"Robust winners (train>0.5% AND test>0.5% AND test_n>=10): {len(robust)}")
    print("="*92)
    for r in sorted(robust, key=lambda x: -x['test_avg'])[:10]:
        print(f"  ✅ {r['side']} mag>={r['min_mag']}% hz={r['hz']}min {r['direction']:6s} → train +{r['train_avg']:.2f}% / test +{r['test_avg']:.2f}% / n={r['n']} / win {r['win_rate']:.1f}%")

    # Save
    with open('/Volumes/T9/BWE/40_EXPERIMENTS/round4/validation/sweep_reserved6_results.json', 'w') as f:
        json.dump({'robust_winners': robust, 'n_total_events': len(events)}, f, indent=2)
    print(f"\nSaved: sweep_reserved6_results.json")
    con.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
