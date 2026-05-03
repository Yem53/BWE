"""C-trigger threshold grid sweep on 30d data.

For each candidate trigger family, sweep multiple thresholds.
Apply train/test split (70/30 by time). Identify robust winners.

Output: ranked combos with mean / win_rate / sample_size + train/test
significance check.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from collections import defaultdict
from itertools import product
from statistics import mean, stdev

LIVE_DB = (
    "/Users/ye/.hermes/research/binance_futures_1m_collector_runtime/"
    "binance_futures_1m.sqlite3"
)


def find_c2_c3_events(con, ls_extreme: float, px_threshold: float) -> tuple[list, list]:
    """LS extreme + price move events. Returns (c2_long_squeeze, c3_short_liqui)."""
    rows = con.execute(
        "SELECT g.symbol, g.ts_ms, g.long_account, g.short_account "
        "FROM global_long_short_account_ratio_5m g "
    ).fetchall()
    c2, c3 = [], []
    for sym, ts_ms, la, sa in rows:
        if (la + sa) <= 0:
            continue
        ratio = la / (la + sa)
        # Price 5min move
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
        if ratio <= ls_extreme and pct >= px_threshold:
            c2.append({"symbol": sym, "event_ts_ms": ts_ms, "intent": "long",
                       "ls": ratio, "px_pct": pct})
        if ratio >= (1 - ls_extreme) and pct <= -px_threshold:
            c3.append({"symbol": sym, "event_ts_ms": ts_ms, "intent": "short",
                       "ls": ratio, "px_pct": pct})
    return c2, c3


def find_c5_events(con, abs_rate_threshold: float) -> list:
    """Funding flip events."""
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
                continue
            if abs(fr_now) < abs_rate_threshold:
                continue
            intent = "short" if fr_now < 0 else "long"
            events.append({"symbol": sym, "event_ts_ms": ts_now,
                           "intent": intent, "rate": fr_now})
    return events


def forward_return(con, sym, ts_ms, horizon_min):
    cur = con.execute(
        "SELECT close FROM klines_1m WHERE symbol=? AND open_time_ms <= ? "
        "ORDER BY open_time_ms DESC LIMIT 1", (sym, ts_ms)
    ).fetchone()
    fut = con.execute(
        "SELECT close FROM klines_1m WHERE symbol=? AND open_time_ms = ? LIMIT 1",
        (sym, ts_ms + horizon_min * 60_000)
    ).fetchone()
    if not cur or not fut or cur[0] <= 0:
        return None
    return (fut[0] - cur[0]) / cur[0] * 100


def evaluate(events, con, horizon_min: int) -> dict:
    """Compute trade outcomes. Train/test split by time (first 70% / last 30%)."""
    enriched = []
    for e in events:
        fwd = forward_return(con, e["symbol"], e["event_ts_ms"], horizon_min)
        if fwd is None:
            continue
        outcome = fwd if e["intent"] == "long" else -fwd
        enriched.append({"ts_ms": e["event_ts_ms"], "outcome": outcome})
    if len(enriched) < 30:
        return {"n": len(enriched), "insufficient": True}
    enriched.sort(key=lambda x: x["ts_ms"])
    split_idx = int(len(enriched) * 0.7)
    train = enriched[:split_idx]
    test = enriched[split_idx:]
    train_outs = [e["outcome"] for e in train]
    test_outs = [e["outcome"] for e in test]

    return {
        "n": len(enriched),
        "n_train": len(train), "n_test": len(test),
        "train_mean": mean(train_outs),
        "train_win": sum(1 for o in train_outs if o > 0) / len(train_outs) * 100,
        "test_mean": mean(test_outs),
        "test_win": sum(1 for o in test_outs if o > 0) / len(test_outs) * 100,
        "robust": (mean(train_outs) > 0.3 and mean(test_outs) > 0.3
                   and len(test) >= 20),
    }


def main():
    con = sqlite3.connect(LIVE_DB, timeout=60)
    con.execute("PRAGMA query_only=1")

    print("=" * 80)
    print("C-Trigger GRID SEARCH on 30d data (train 70% / test 30%)")
    print("=" * 80)

    results = []

    print("\n[C2/C3] LS extreme + px sweep")
    print(f"  {'ls_threshold':<15s} {'px_threshold':<15s} {'horizon_min':<13s} {'C2_n':<6s} {'C2_train':<10s} {'C2_test':<10s} {'C3_n':<6s} {'C3_train':<10s} {'C3_test':<10s} {'robust?':<8s}")
    for ls_t, px_t, hz in product([0.25, 0.30, 0.35, 0.40], [2.0, 3.0, 4.0, 5.0], [60, 120]):
        c2, c3 = find_c2_c3_events(con, ls_t, px_t)
        c2r = evaluate(c2, con, hz)
        c3r = evaluate(c3, con, hz)
        if c3r.get("insufficient") and c2r.get("insufficient"):
            continue
        c2_train = c2r.get("train_mean", "n/a")
        c2_test = c2r.get("test_mean", "n/a")
        c3_train = c3r.get("train_mean", "n/a")
        c3_test = c3r.get("test_mean", "n/a")
        robust = "✅" if c3r.get("robust") else "❌"
        c2_train_s = f"{c2_train:+.2f}%" if isinstance(c2_train, float) else c2_train
        c2_test_s = f"{c2_test:+.2f}%" if isinstance(c2_test, float) else c2_test
        c3_train_s = f"{c3_train:+.2f}%" if isinstance(c3_train, float) else c3_train
        c3_test_s = f"{c3_test:+.2f}%" if isinstance(c3_test, float) else c3_test
        print(f"  {ls_t:<15.2f} {px_t:<15.1f} {hz:<13d} {c2r.get('n', 0):<6d} {c2_train_s:<10s} {c2_test_s:<10s} {c3r.get('n', 0):<6d} {c3_train_s:<10s} {c3_test_s:<10s} {robust:<8s}")
        if c3r.get("robust") and c3r.get("n", 0) >= 50:
            results.append({"trigger": f"C3_ls{ls_t}_px{px_t}_hz{hz}min", **c3r})

    print("\n[C5] funding flip rate sweep")
    print(f"  {'rate_threshold':<18s} {'horizon_min':<13s} {'n':<6s} {'train_mean':<12s} {'test_mean':<12s} {'robust?':<8s}")
    for rate_t, hz in product([0.0001, 0.0003, 0.0005, 0.0010], [60, 120]):
        ev = find_c5_events(con, rate_t)
        r = evaluate(ev, con, hz)
        if r.get("insufficient"):
            continue
        train_s = f"{r.get('train_mean', 0):+.2f}%"
        test_s = f"{r.get('test_mean', 0):+.2f}%"
        robust = "✅" if r.get("robust") else "❌"
        print(f"  {rate_t:<18.4f} {hz:<13d} {r['n']:<6d} {train_s:<12s} {test_s:<12s} {robust:<8s}")
        if r.get("robust") and r.get("n", 0) >= 50:
            results.append({"trigger": f"C5_rate{rate_t}_hz{hz}min", **r})

    # Summary
    print("\n" + "=" * 80)
    print(f"ROBUST WINNERS (train/test 双向 alpha > 0.3% AND test_n >= 20):")
    print("=" * 80)
    if not results:
        print("  ❌ 没有 robust 组合通过 train/test 双重检验.")
        print("  → C 路在当前数据 + 这个搜索网格里找不到稳定的独立 trigger.")
        print("  → 唯一可能的 winner 仍是 C3 (LS≥0.70 + px≤-3% short),已在原始测试中确认.")
    else:
        for r in sorted(results, key=lambda x: x.get("test_mean", 0), reverse=True):
            print(f"  ✅ {r['trigger']:40s} train +{r['train_mean']:.2f}% / test +{r['test_mean']:.2f}% / n={r['n']}")

    # Save
    with open("/Volumes/T9/BWE/40_EXPERIMENTS/round4/validation/c_grid_results.json", "w") as f:
        json.dump({"robust_winners": results}, f, indent=2, default=str)
    print("\nSaved: c_grid_results.json")
    con.close()


if __name__ == "__main__":
    main()
