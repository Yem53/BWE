"""Throwaway exploration: measure opportunity cost of 妖币-score gating.

Question: if we enforce BWE-and-yaobi-score串联 (option b), how many trades
do we drop AND what's the realized PnL of the dropped vs kept set?

Anti-overfit framing: we don't tune the threshold here, we just CHARACTERIZE
the trade-off curve so the human can pick the gate level with eyes open.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "exit_v2"))
from exit_v2 import (
    Bar, ExitConfig, ExitEngine, Position, compute_atr_pct,
)

LIVE_JOURNAL = Path("/Users/ye/.hermes/research/bwe_live_autotrader_binance_expectancy_runtime/trade_journal.jsonl")
PAPER_JOURNAL = Path("/Users/ye/.hermes/research/bwe_paper_multilot_observer_runtime/trade_journal.jsonl")
KLINE_DB = "/Users/ye/.hermes/research/binance_futures_1m_collector_runtime/binance_futures_1m.sqlite3"
SCORE_PATH = Path("/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits/yaobi_score_v0.json")


def load_closed_trades(path: Path) -> list[dict]:
    by_id: dict[str, dict] = {}
    for line in path.open():
        j = json.loads(line)
        tid = j.get("trade_id")
        if not tid:
            continue
        if j["action"] == "entry":
            by_id[tid] = {**j, "exits": []}
        elif j["action"] in ("exit", "partial_exit") and tid in by_id:
            by_id[tid]["exits"].append(j)

    closed = []
    for tid, t in by_id.items():
        if not t.get("exits"):
            continue
        final = t["exits"][-1]
        ep = float(t.get("entry_px") or t.get("fill_price") or 0)
        xp = float(final.get("fill_price") or final.get("exit_px") or 0)
        if ep == 0:
            continue
        side = t["side"]
        raw_pnl = (xp - ep) / ep * 100 if side == "long" else (ep - xp) / ep * 100
        closed.append({
            "trade_id": tid,
            "symbol": t["symbol"],
            "market_symbol": t["market_symbol"],
            "strategy": t["strategy_name"],
            "side": side,
            "entry_ts_ms": int(t.get("entry_ts", t["ts"]) * 1000),
            "entry_px": ep,
            "raw_pnl_pct": raw_pnl,
            "hold_minutes_limit": float(t.get("hold_minutes_limit", 60)),
        })
    return closed


def replay_with_v2(trade: dict, con) -> float:
    """Replay one trade with exit_v2 baseline, return raw_pnl_pct."""
    entry_ts = trade["entry_ts_ms"]
    end_ts = entry_ts + int((trade["hold_minutes_limit"] + 5) * 60_000)
    pre_ts = entry_ts - 30 * 60_000

    cur = con.execute(
        "SELECT open_time_ms, open, high, low, close, volume FROM klines_1m "
        "WHERE symbol=? AND open_time_ms BETWEEN ? AND ? ORDER BY open_time_ms",
        (trade["market_symbol"], pre_ts, end_ts),
    )
    bars = [Bar(*r) for r in cur.fetchall()]
    if not bars:
        return trade["raw_pnl_pct"]

    entry_idx = next((i for i, b in enumerate(bars) if b.ts_ms >= entry_ts), None)
    if entry_idx is None:
        return trade["raw_pnl_pct"]

    pre = bars[:entry_idx]
    atr = compute_atr_pct(pre, period=14, ref_px=trade["entry_px"]) if pre else 0.0

    pos = Position(
        entry_ts_ms=entry_ts, entry_px=trade["entry_px"], side=trade["side"],
        hold_minutes_limit=trade["hold_minutes_limit"], atr_at_entry=atr,
    )
    eng = ExitEngine(ExitConfig())

    decision = None
    for i in range(entry_idx, len(bars)):
        d = eng.decide(pos, bars[: i + 1])
        if d:
            decision = d
            break

    if decision is None:
        last = bars[-1]
        if pos.side == "long":
            return (last.close - pos.entry_px) / pos.entry_px * 100
        return (pos.entry_px - last.close) / pos.entry_px * 100
    return decision.pnl_pct


def main() -> int:
    print("=" * 80)
    print("妖性过滤的机会成本分析")
    print("=" * 80)

    score_data = json.loads(SCORE_PATH.read_text())
    sym_to_score = {m["symbol"]: m["yaobi_score"] for m in score_data["ranked"]}
    print(f"Loaded {len(sym_to_score)} symbol scores")

    con = sqlite3.connect(KLINE_DB)
    live = load_closed_trades(LIVE_JOURNAL)
    paper = load_closed_trades(PAPER_JOURNAL)
    print(f"LIVE trades: {len(live)}  PAPER trades: {len(paper)}")
    print()

    # Replay each trade with v2 exit + attach yaobi score
    for label, trades in [("LIVE", live), ("PAPER", paper)]:
        print(f"[{label}] replaying {len(trades)} trades with exit_v2 baseline...")
        for t in trades:
            t["v2_pnl"] = replay_with_v2(t, con)
            t["yaobi_score"] = sym_to_score.get(t["market_symbol"], None)

    # Combined analysis
    for label, trades in [("LIVE", live), ("PAPER", paper)]:
        print()
        print("=" * 80)
        print(f"{label} — yaobi-gate impact")
        print("=" * 80)

        scored = [t for t in trades if t["yaobi_score"] is not None]
        unscored = [t for t in trades if t["yaobi_score"] is None]
        if unscored:
            print(f"  ⚠️  {len(unscored)} trades have no score (symbol not in DB):")
            for t in unscored[:5]:
                print(f"     {t['market_symbol']:14s} pnl={t['v2_pnl']:+6.1f}%")

        thresholds = [
            ("无过滤 (现状)", 0),
            ("≥30 排除稳定币", 30),
            ("≥40 排除半稳定", 40),
            ("≥50 只允许中+极妖", 50),
            ("≥60 严格中+极妖", 60),
            ("≥70 只极妖", 70),
        ]

        print(f"\n{'gate':25s} {'kept':>5s} {'drop':>5s} {'kept_total_pnl':>15s} "
              f"{'drop_total_pnl':>15s} {'kept_win%':>10s} {'drop_win%':>10s}")
        print("-" * 100)
        for desc, thresh in thresholds:
            kept = [t for t in scored if t["yaobi_score"] >= thresh]
            drop = [t for t in scored if t["yaobi_score"] < thresh]
            kept_pnl = sum(t["v2_pnl"] for t in kept)
            drop_pnl = sum(t["v2_pnl"] for t in drop)
            kept_wins = sum(1 for t in kept if t["v2_pnl"] > 0)
            drop_wins = sum(1 for t in drop if t["v2_pnl"] > 0)
            kept_wr = kept_wins / len(kept) * 100 if kept else 0
            drop_wr = drop_wins / len(drop) * 100 if drop else 0
            print(f"  {desc:23s} {len(kept):>5d} {len(drop):>5d} "
                  f"{kept_pnl:>+13.1f}%  {drop_pnl:>+13.1f}% "
                  f"{kept_wr:>9.1f}% {drop_wr:>9.1f}%")

        # Score distribution of trades
        print(f"\n  trade-symbol score distribution ({len(scored)} trades):")
        buckets = [(0, 30), (30, 50), (50, 70), (70, 100)]
        for lo, hi in buckets:
            sub = [t for t in scored if lo <= t["yaobi_score"] < hi]
            if not sub:
                continue
            wins = sum(1 for t in sub if t["v2_pnl"] > 0)
            total = sum(t["v2_pnl"] for t in sub)
            mean = total / len(sub)
            label_b = {(0,30):"稳定", (30,50):"轻妖", (50,70):"中妖", (70,100):"极妖"}[(lo,hi)]
            print(f"    {label_b} (score {lo}-{hi}): n={len(sub):>3d}  total_pnl={total:>+8.1f}%  "
                  f"mean={mean:>+5.1f}%  win={wins/len(sub)*100:>5.1f}%")

        # Show what would be dropped at the recommended (>=50) gate
        print(f"\n  Trades dropped at ≥50 gate (sorted by missed PnL desc):")
        dropped_at_50 = sorted([t for t in scored if t["yaobi_score"] < 50],
                                key=lambda t: -t["v2_pnl"])
        print(f"    Top 5 'missed wins' (would have helped if kept):")
        for t in dropped_at_50[:5]:
            print(f"      {t['market_symbol']:14s} score={t['yaobi_score']:>4.1f}  "
                  f"v2_pnl={t['v2_pnl']:+6.1f}%  strategy={t['strategy'][:30]}")
        print(f"    Top 5 'avoided losers' (good to drop):")
        for t in dropped_at_50[-5:]:
            print(f"      {t['market_symbol']:14s} score={t['yaobi_score']:>4.1f}  "
                  f"v2_pnl={t['v2_pnl']:+6.1f}%  strategy={t['strategy'][:30]}")

    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
