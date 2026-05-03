"""Position × Leverage optimization grid — find optimal sizing/leverage combo.

Tests 12 combinations of (pos_pct, leverage) on real Hermes paper + broader-market
data. Outputs ranked table by:
  - total capital PnL (after fees)
  - max capital drawdown
  - Sharpe-like risk-adjusted return
  - liquidation risk count (trades that would have been margin-called)

Default Binance USDM tiers:
  Leverage 1x:  no liquidation risk (your $50 max loss = position size)
  Leverage 3x:  liquidation at ~-33% raw move (maintenance margin reached)
  Leverage 5x:  liquidation at ~-20% raw move
  Leverage 10x: liquidation at ~-10% raw move

exit_v2 hard_stop typically fires at -5% to -10% raw → protects against
liquidation in most scenarios. But edge cases (gap moves) can liquidate.
"""
from __future__ import annotations

import json
import math
import sqlite3
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "exit_v2"))
sys.path.insert(0, "/Users/ye/.hermes/scripts/bwe_v2")
from exit_v2 import Bar, ExitConfig, ExitEngine, Position, compute_atr_pct
from lifecycle_aware_config import build_exit_config

LIVE = Path("/Users/ye/.hermes/research/bwe_live_autotrader_binance_expectancy_runtime/trade_journal.jsonl")
PAPER = Path("/Users/ye/.hermes/research/bwe_paper_multilot_observer_runtime/trade_journal.jsonl")
KLINE_DB = "/Users/ye/.hermes/research/binance_extended_history.sqlite3"
SCORE_PATH = Path("/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits/yaobi_score_v1_30d.json")
DIVE_PATH = Path("/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits/yaobi_per_symbol_dive_v1_30d.json")
OUT = Path("/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits/position_leverage_optimization.json")

# Binance USDM liquidation thresholds (approximate, ignoring tier-based maintenance margin)
LIQUIDATION_RAW_PCT = {
    1: -100.0,  # no liquidation possible
    2: -50.0,
    3: -33.3,
    5: -20.0,
    10: -10.0,
}

# Round-trip fee for spicy 妖币 (from fee_model.py)
ROUND_TRIP_BPS_SPICY = 18.0


def load_closed(path):
    by_id = {}
    for line in path.open():
        j = json.loads(line)
        tid = j.get("trade_id")
        if not tid: continue
        if j["action"] == "entry":
            by_id[tid] = {**j, "exits": []}
        elif j["action"] in ("exit", "partial_exit") and tid in by_id:
            by_id[tid]["exits"].append(j)
    out = []
    for tid, t in by_id.items():
        if not t.get("exits"): continue
        final = t["exits"][-1]
        ep = float(t.get("entry_px") or t.get("fill_price") or 0)
        xp = float(final.get("fill_price") or final.get("exit_px") or 0)
        if ep == 0: continue
        side = t["side"]
        raw = (xp - ep) / ep * 100 if side == "long" else (ep - xp) / ep * 100
        out.append({
            "trade_id": tid, "symbol": t["symbol"], "market_symbol": t["market_symbol"],
            "side": side, "entry_ts_ms": int(t.get("entry_ts", t["ts"]) * 1000),
            "entry_px": ep, "raw_pnl_layer1": raw,
            "hold_minutes_limit": float(t.get("hold_minutes_limit", 60)),
        })
    return out


def replay_with_lifecycle(trade, con, sym_meta):
    sm = sym_meta.get(trade["market_symbol"], {"lifecycle": "quiet"})
    cfg = build_exit_config(sm["lifecycle"])

    entry_ts = trade["entry_ts_ms"]
    end_ts = entry_ts + int((trade["hold_minutes_limit"] + 5) * 60_000)
    pre_ts = entry_ts - 30 * 60_000
    cur = con.execute(
        "SELECT open_time_ms, open, high, low, close, volume FROM klines_1m "
        "WHERE symbol=? AND open_time_ms BETWEEN ? AND ? ORDER BY open_time_ms",
        (trade["market_symbol"], pre_ts, end_ts))
    bars = [Bar(*r) for r in cur.fetchall()]
    if not bars: return trade["raw_pnl_layer1"]
    eidx = next((i for i, b in enumerate(bars) if b.ts_ms >= entry_ts), None)
    if eidx is None: return trade["raw_pnl_layer1"]
    pre = bars[:eidx]
    atr = compute_atr_pct(pre, period=14, ref_px=trade["entry_px"]) if pre else 0
    pos = Position(entry_ts_ms=entry_ts, entry_px=trade["entry_px"], side=trade["side"],
                   hold_minutes_limit=trade["hold_minutes_limit"], atr_at_entry=atr)
    eng = ExitEngine(cfg)
    for i in range(eidx, len(bars)):
        d = eng.decide(pos, bars[: i + 1])
        if d: return d.pnl_pct
    last = bars[-1]
    return ((last.close - pos.entry_px) / pos.entry_px * 100 if pos.side == "long"
            else (pos.entry_px - last.close) / pos.entry_px * 100)


def aggregate_with_pos_lev(raw_pnls, pos_pct, leverage):
    """Compute capital-level metrics for a (pos_pct, leverage) combo.

    capital_pnl_per_trade = raw_pnl × pos_pct/100 × leverage
    Liquidation: if raw_pnl <= LIQUIDATION_RAW_PCT[leverage], cap loss at -pos_pct
    Fees: apply round-trip 18bps × pos × leverage = effective notional fee
    """
    liq_threshold = LIQUIDATION_RAW_PCT.get(leverage, -100.0)
    fee_per_trade_pct = pos_pct * leverage * ROUND_TRIP_BPS_SPICY / 10000  # capital % per trade

    cap_pnls = []
    n_liquidated = 0
    for raw in raw_pnls:
        if raw <= liq_threshold:
            # Margin called — lose the position margin (= pos_pct of capital)
            cap_pnl = -pos_pct
            n_liquidated += 1
        else:
            cap_pnl = raw * pos_pct / 100 * leverage
        # Apply fee
        cap_pnl -= fee_per_trade_pct
        cap_pnls.append(cap_pnl)

    n = len(cap_pnls)
    if n == 0:
        return {}

    total_cap = sum(cap_pnls)
    mean_cap = total_cap / n
    wins = sum(1 for p in cap_pnls if p > 0)

    # Max drawdown
    cumul = 0
    peak = 0
    max_dd = 0
    for p in cap_pnls:
        cumul += p
        if cumul > peak: peak = cumul
        dd = peak - cumul
        if dd > max_dd: max_dd = dd

    # Sharpe-like
    if n > 1:
        variance = sum((p - mean_cap) ** 2 for p in cap_pnls) / (n - 1)
        stdev = math.sqrt(variance)
        sharpe = (mean_cap / stdev * math.sqrt(n)) if stdev > 0 else 999.0
    else:
        sharpe = 0

    return {
        "pos_pct": pos_pct,
        "leverage": leverage,
        "effective_exposure": pos_pct * leverage,
        "n": n,
        "total_cap": total_cap,
        "mean_cap": mean_cap,
        "win_rate": wins / n * 100,
        "max_dd_capital": max_dd,
        "sharpe": sharpe,
        "n_liquidated": n_liquidated,
        "liquidation_pct": n_liquidated / n * 100,
        "best_trade_cap": max(cap_pnls),
        "worst_trade_cap": min(cap_pnls),
    }


def main():
    score_data = json.loads(SCORE_PATH.read_text())
    sym_to_score = {m["symbol"]: m["yaobi_score"] for m in score_data["ranked"]}
    dive_data = json.loads(DIVE_PATH.read_text())
    sym_meta = {r["symbol"]: {"score": r["score"], "lifecycle": r["lifecycle"],
                              "reaction": r["reaction"], "n_waves_14d": r["n_waves"]}
                for r in dive_data["results"]}

    con = sqlite3.connect(KLINE_DB)
    con.execute("PRAGMA query_only=1")
    paper = load_closed(PAPER)
    print(f"PAPER trades: {len(paper)}")

    # Replay all trades once with L2-per-lifecycle (gives raw 1x PnL list)
    print("Replaying 210 trades with L2-per-lifecycle for raw 1x PnL...")
    raw_pnls = []
    for t in paper:
        raw_pnls.append(replay_with_lifecycle(t, con, sym_meta))

    raw_pnls = [p for p in raw_pnls if p is not None]
    print(f"Got {len(raw_pnls)} raw 1x PnLs. Sum = {sum(raw_pnls):+.1f}%")
    print()

    # Test grid: (pos_pct, leverage) combinations
    grid = [
        (5, 1),    # current spec baseline
        (5, 2),
        (5, 3),    # user proposed
        (5, 5),    # user proposed max
        (8, 1),
        (8, 2),
        (8, 3),
        (10, 1),
        (10, 2),
        (10, 3),
        (12, 1),   # current max tier
        (12, 2),
        (12, 3),
        (15, 1),
        (15, 2),
        (20, 1),   # alt: high pos no leverage
    ]

    print("=" * 130)
    print("POSITION × LEVERAGE OPTIMIZATION GRID (BWE PAPER L2-per-lifecycle, 210 trades)")
    print("=" * 130)
    print(f"  {'pos':>4s} {'lev':>4s} {'eff_exp':>8s} {'tot_cap':>9s} {'mean_cap':>10s} "
          f"{'win%':>6s} {'max_DD':>8s} {'sharpe':>8s} {'liq#':>5s} {'liq%':>6s} "
          f"{'best':>8s} {'worst':>9s}")
    print("-" * 130)

    results = []
    for pos, lev in grid:
        agg = aggregate_with_pos_lev(raw_pnls, pos, lev)
        results.append(agg)
        marker = ""
        if agg["max_dd_capital"] > 5.0:
            marker += " ⚠️DD"
        if agg["liquidation_pct"] > 0:
            marker += " ⚠️LIQ"
        if agg["max_dd_capital"] <= 5.0 and agg["liquidation_pct"] == 0:
            marker += " ✓"

        print(f"  {pos:>3d}% {lev:>3d}x {pos*lev:>7d}% "
              f"{agg['total_cap']:>+8.2f}% {agg['mean_cap']:>+9.4f}% "
              f"{agg['win_rate']:>5.1f}% {agg['max_dd_capital']:>7.2f}% "
              f"{agg['sharpe']:>8.2f} {agg['n_liquidated']:>5d} {agg['liquidation_pct']:>5.1f}% "
              f"{agg['best_trade_cap']:>+7.2f}% {agg['worst_trade_cap']:>+8.2f}%{marker}")

    # Identify optimal frontier
    print()
    print("=" * 130)
    print("OPTIMAL CANDIDATES (max_DD ≤ 5% capital + 0 liquidations)")
    print("=" * 130)
    safe = [r for r in results if r["max_dd_capital"] <= 5.0 and r["n_liquidated"] == 0]
    print(f"  {'pos':>4s} {'lev':>4s} {'eff_exp':>8s} {'tot_cap':>9s} {'mean_cap':>10s} "
          f"{'sharpe':>8s} {'max_DD':>8s}")
    safe.sort(key=lambda r: -r["total_cap"])
    for r in safe:
        print(f"  {r['pos_pct']:>3d}% {r['leverage']:>3d}x {r['pos_pct']*r['leverage']:>7d}% "
              f"{r['total_cap']:>+8.2f}% {r['mean_cap']:>+9.4f}% "
              f"{r['sharpe']:>8.2f} {r['max_dd_capital']:>7.2f}%")

    # Best by total cap (regardless of safety)
    print()
    print("=" * 130)
    print("BEST BY TOTAL CAP (ignoring safety constraints — for comparison)")
    print("=" * 130)
    by_cap = sorted(results, key=lambda r: -r["total_cap"])[:5]
    print(f"  {'pos':>4s} {'lev':>4s} {'eff_exp':>8s} {'tot_cap':>9s} {'max_DD':>8s} {'liq%':>6s}")
    for r in by_cap:
        print(f"  {r['pos_pct']:>3d}% {r['leverage']:>3d}x {r['pos_pct']*r['leverage']:>7d}% "
              f"{r['total_cap']:>+8.2f}% {r['max_dd_capital']:>7.2f}% {r['liquidation_pct']:>5.1f}%")

    # Best Sharpe (risk-adjusted)
    print()
    print("=" * 130)
    print("BEST BY SHARPE (risk-adjusted)")
    print("=" * 130)
    by_sharpe = sorted(results, key=lambda r: -r["sharpe"])[:5]
    print(f"  {'pos':>4s} {'lev':>4s} {'eff_exp':>8s} {'tot_cap':>9s} {'sharpe':>8s} {'max_DD':>8s}")
    for r in by_sharpe:
        print(f"  {r['pos_pct']:>3d}% {r['leverage']:>3d}x {r['pos_pct']*r['leverage']:>7d}% "
              f"{r['total_cap']:>+8.2f}% {r['sharpe']:>8.2f} {r['max_dd_capital']:>7.2f}%")

    OUT.write_text(json.dumps(results, indent=2, default=str))
    print(f"\n  saved: {OUT}")
    con.close()


if __name__ == "__main__":
    main()
