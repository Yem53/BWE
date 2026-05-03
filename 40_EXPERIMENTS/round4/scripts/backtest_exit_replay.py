"""Backtest replay: simulate Patch P0 #1 + P0 #3 on actual Hermes live + paper trades.

Anti-overfit design:
  1. **First-principles params** (NOT data-derived):
     - trail_activate=5% (用户 thesis: 妖币 wide TP, 5% 是合理 trail 启动点)
     - trail_step=5% (中等, 不是 fitted to KAT 33%)
     - catastrophe_min_hold=30min (give signal time, 不是 fitted to LAB 4min)
  2. **Sensitivity analysis**: 跑 trail_step ∈ {3, 5, 7, 10}, min_hold ∈ {15, 30, 60} 看分布
  3. **Cross-set validation**: 同 logic 在 live + paper 都 应该改善
  4. **Outlier check**: TRADOOR +192% 单 trade 不该被新 logic 杀掉
  5. **Worst-case**: 最差参数下 PnL 不能比 original 差太多 (robust)

Approach:
  For each closed trade in trade_journal.jsonl:
    - Load 1m kline from entry_ts to (entry_ts + hold_minutes_limit) from sqlite
    - Re-simulate position evolution with new exit logic
    - Compute new_exit_ts, new_pnl_pct
    - Compare with original

Output: T9/40_EXPERIMENTS/round4/05_audits/backtest_exit_replay.json + .md
"""
from __future__ import annotations

import json
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

LIVE_JOURNAL = Path("/Users/ye/.hermes/research/bwe_live_autotrader_binance_expectancy_runtime/trade_journal.jsonl")
PAPER_JOURNAL = Path("/Users/ye/.hermes/research/bwe_paper_multilot_observer_runtime/trade_journal.jsonl")
KLINE_DB = "/Users/ye/.hermes/research/binance_futures_1m_collector_runtime/binance_futures_1m.sqlite3"
OUT_DIR = Path("/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits")
OUT_DIR.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class ExitParams:
    """First-principles default. NOT fitted to data."""
    trail_activate_pct: float = 5.0
    trail_step_pct: float = 5.0
    runner_floor_pct: float = 0.0
    hard_stop_pct: float = 8.0           # 妖币 wider stop (vs default 2.5)
    catastrophe_stop_pct: float = 12.0   # 妖币 wider catastrophe (vs default ~8)
    catastrophe_min_hold_min: float = 30.0  # grace period
    catastrophe_grace_multiplier: float = 2.0
    activation_delay_min: float = 5.0    # signal needs 5 min before any stop active

    @property
    def label(self) -> str:
        return (f"act{self.trail_activate_pct:.0f}_step{self.trail_step_pct:.0f}_"
                f"hard{self.hard_stop_pct:.0f}_cat{self.catastrophe_stop_pct:.0f}_"
                f"cmh{int(self.catastrophe_min_hold_min)}")


def load_closed_trades(path: Path) -> list[dict]:
    """Pair entries with final exits."""
    by_id: dict[str, dict] = {}
    for line in path.open():
        j = json.loads(line)
        tid = j.get("trade_id")
        if not tid:
            continue
        if j["action"] == "entry":
            by_id[tid] = {**j, "exits": []}
        elif j["action"] in ("exit", "partial_exit"):
            if tid in by_id:
                by_id[tid]["exits"].append(j)
    closed = []
    for tid, t in by_id.items():
        if not t.get("exits"):
            continue
        final = t["exits"][-1]
        closed.append({
            "trade_id": tid,
            "symbol": t["symbol"],
            "market_symbol": t["market_symbol"],
            "strategy": t["strategy_name"],
            "side": t["side"],
            "entry_ts": t.get("entry_ts", t["ts"]),
            "entry_px": t.get("entry_px", t.get("fill_price")),
            "original_exit_ts": final["ts"],
            "original_exit_px": final.get("fill_price"),
            "original_exit_reason": final.get("exit_reason", "?"),
            "original_pnl_pct": final.get("pnl_pct", 0),
            "hold_minutes_limit": t.get("hold_minutes_limit", 60),
        })
    return closed


def fetch_kline_window(con, market_symbol: str, start_ms: int, end_ms: int) -> list[tuple]:
    cur = con.execute(
        "SELECT open_time_ms, open, high, low, close FROM klines_1m "
        "WHERE symbol=? AND open_time_ms BETWEEN ? AND ? ORDER BY open_time_ms",
        (market_symbol, start_ms, end_ms),
    )
    return cur.fetchall()


def simulate_new_exit(trade: dict, bars: list[tuple], params: ExitParams) -> dict:
    """Walk through 1m bars applying new exit logic.

    Returns: dict with new_exit_ts, new_exit_px, new_pnl_pct, new_exit_reason, new_hold_min
    """
    if not bars:
        return {
            "new_exit_ts": trade["original_exit_ts"],
            "new_exit_px": trade["original_exit_px"],
            "new_pnl_pct": trade["original_pnl_pct"],
            "new_exit_reason": "no_kline_data",
            "new_hold_min": (trade["original_exit_ts"] - trade["entry_ts"]) / 60,
        }

    entry_px = float(trade["entry_px"])
    side = trade["side"]
    entry_ts_ms = int(trade["entry_ts"] * 1000)
    hold_limit_min = float(trade["hold_minutes_limit"])

    high_water_pct = 0.0  # tracks max favorable PnL seen so far

    for bar in bars:
        open_ts_ms, o, h, l, c = bar
        hold_min = (open_ts_ms - entry_ts_ms) / 60000

        if hold_min > hold_limit_min:
            # Time exit - close at this bar's open
            return _close(open_ts_ms / 1000, o, entry_px, side, hold_min, "time_exit")

        # In each bar, compute:
        # - Worst pnl during bar (low for long, high for short)
        # - Best pnl during bar (high for long, low for short)
        if side == "long":
            best_in_bar = (h - entry_px) / entry_px * 100
            worst_in_bar = (l - entry_px) / entry_px * 100
        else:
            best_in_bar = (entry_px - l) / entry_px * 100
            worst_in_bar = (entry_px - h) / entry_px * 100

        # Update high_water at start of bar (conservative: assume worst happens before best within bar)
        prev_high_water = high_water_pct
        high_water_pct = max(high_water_pct, best_in_bar)

        # Apply stops in worst-case order within bar (worst first)
        # 1. Hard stop / catastrophe (worst case scenarios)
        catastrophe_effective = params.catastrophe_stop_pct
        if hold_min < params.catastrophe_min_hold_min:
            catastrophe_effective = params.catastrophe_stop_pct * params.catastrophe_grace_multiplier

        if hold_min >= params.activation_delay_min:
            # Hard stop: triggered if worst_in_bar <= -hard_stop_pct
            if worst_in_bar <= -params.hard_stop_pct:
                # Exit at the stop level (assume order at -hard_stop_pct)
                stop_px = entry_px * (1 - params.hard_stop_pct/100) if side == "long" else entry_px * (1 + params.hard_stop_pct/100)
                return _close(open_ts_ms / 1000, stop_px, entry_px, side, hold_min, "hard_stop")
        else:
            # In activation_delay grace - only catastrophe
            if catastrophe_effective and worst_in_bar <= -catastrophe_effective:
                stop_px = entry_px * (1 - catastrophe_effective/100) if side == "long" else entry_px * (1 + catastrophe_effective/100)
                return _close(open_ts_ms / 1000, stop_px, entry_px, side, hold_min, "catastrophe_stop")

        # 2. Trail high-water exit (if activated)
        if prev_high_water >= params.trail_activate_pct:
            trail_floor = prev_high_water - params.trail_step_pct
            if worst_in_bar <= trail_floor:
                # Exit at trail floor
                trail_px = entry_px * (1 + trail_floor/100) if side == "long" else entry_px * (1 - trail_floor/100)
                return _close(open_ts_ms / 1000, trail_px, entry_px, side, hold_min, "trail_drawdown_exit")

        # 3. Runner floor (only after trail not activated yet, and only checked hourly-ish)
        # Skip — rely on trail above when high_water above threshold; below threshold, hold

    # Out of bars without exit - close at last bar
    last_bar = bars[-1]
    last_ts_ms, _, _, _, last_c = last_bar
    hold_min = (last_ts_ms - entry_ts_ms) / 60000
    return _close(last_ts_ms / 1000, last_c, entry_px, side, hold_min, "data_end")


def _close(exit_ts: float, exit_px: float, entry_px: float, side: str,
           hold_min: float, reason: str) -> dict:
    if side == "long":
        pnl = (exit_px - entry_px) / entry_px * 100
    else:
        pnl = (entry_px - exit_px) / entry_px * 100
    return {
        "new_exit_ts": exit_ts,
        "new_exit_px": exit_px,
        "new_pnl_pct": pnl,
        "new_exit_reason": reason,
        "new_hold_min": hold_min,
    }


def run_replay(trades: list[dict], con, params: ExitParams) -> dict:
    """Run replay on all trades with given params, return aggregate stats."""
    enriched = []
    n_no_data = 0
    for t in trades:
        entry_ms = int(t["entry_ts"] * 1000)
        # Look up to hold_minutes_limit + 5 min buffer
        end_ms = entry_ms + int((t["hold_minutes_limit"] + 5) * 60000)
        bars = fetch_kline_window(con, t["market_symbol"], entry_ms, end_ms)
        if not bars:
            n_no_data += 1
            continue
        result = simulate_new_exit(t, bars, params)
        enriched.append({**t, **result})

    if not enriched:
        return {"label": params.label, "n": 0, "n_no_data": n_no_data}

    orig_pnl = sum(t["original_pnl_pct"] for t in enriched)
    new_pnl = sum(t["new_pnl_pct"] for t in enriched)
    orig_wins = [t for t in enriched if t["original_pnl_pct"] > 0]
    new_wins = [t for t in enriched if t["new_pnl_pct"] > 0]

    # Trades where new exit BEATS original
    improved = [t for t in enriched if t["new_pnl_pct"] > t["original_pnl_pct"] + 0.5]
    worsened = [t for t in enriched if t["new_pnl_pct"] < t["original_pnl_pct"] - 0.5]

    return {
        "label": params.label,
        "params": params.__dict__,
        "n": len(enriched),
        "n_no_data": n_no_data,
        "orig_total_pnl": orig_pnl,
        "new_total_pnl": new_pnl,
        "delta_total_pnl": new_pnl - orig_pnl,
        "orig_win_rate": len(orig_wins) / len(enriched) * 100,
        "new_win_rate": len(new_wins) / len(enriched) * 100,
        "orig_avg_pnl": orig_pnl / len(enriched),
        "new_avg_pnl": new_pnl / len(enriched),
        "n_improved": len(improved),
        "n_worsened": len(worsened),
        "n_unchanged": len(enriched) - len(improved) - len(worsened),
        "trades": enriched,
    }


def sensitivity_analysis(trades: list[dict], con, label: str) -> dict:
    """Run multiple param sets, see if results stable."""
    results = []
    # First-principles default
    base = ExitParams()
    results.append(run_replay(trades, con, base))

    # Sensitivity: trail_step ∈ {3, 5, 7, 10}
    for ts in [3.0, 7.0, 10.0]:
        p = ExitParams(trail_step_pct=ts)
        results.append(run_replay(trades, con, p))

    # Sensitivity: trail_activate ∈ {3, 5, 8}
    for ta in [3.0, 8.0]:
        p = ExitParams(trail_activate_pct=ta)
        results.append(run_replay(trades, con, p))

    # Sensitivity: catastrophe_min_hold ∈ {15, 30, 60}
    for cmh in [15.0, 60.0]:
        p = ExitParams(catastrophe_min_hold_min=cmh)
        results.append(run_replay(trades, con, p))

    # Sensitivity: hard_stop ∈ {5, 8, 12}
    for hs in [5.0, 12.0]:
        p = ExitParams(hard_stop_pct=hs)
        results.append(run_replay(trades, con, p))

    return {"set": label, "results": results}


def main() -> int:
    print("=" * 80)
    print("BACKTEST EXIT REPLAY — Patch P0 #1 + P0 #3 simulation")
    print("=" * 80)
    print()
    print("Anti-overfit design:")
    print("  - First-principles params (trail 5%, min_hold 30, hard 8%, cat 12%)")
    print("  - Sensitivity analysis across params")
    print("  - Cross-set validation (live + paper)")
    print()

    con = sqlite3.connect(KLINE_DB)

    out_full = {}
    for label, journal in [("LIVE", LIVE_JOURNAL), ("PAPER", PAPER_JOURNAL)]:
        trades = load_closed_trades(journal)
        print(f"\n{'#'*60}\n# {label}: {len(trades)} closed trades\n{'#'*60}")
        sensitivity = sensitivity_analysis(trades, con, label)

        # Print headline + sensitivity
        baseline = sensitivity["results"][0]
        print(f"\n  Baseline ({baseline['label']}):")
        print(f"    n={baseline['n']} (no_data={baseline['n_no_data']})")
        print(f"    Original total PnL:   {baseline['orig_total_pnl']:+.2f}%  win_rate={baseline['orig_win_rate']:.1f}%  avg={baseline['orig_avg_pnl']:+.2f}%")
        print(f"    New total PnL:        {baseline['new_total_pnl']:+.2f}%  win_rate={baseline['new_win_rate']:.1f}%  avg={baseline['new_avg_pnl']:+.2f}%")
        print(f"    Delta:                {baseline['delta_total_pnl']:+.2f}%")
        print(f"    Trades improved:      {baseline['n_improved']} / worsened: {baseline['n_worsened']} / unchanged: {baseline['n_unchanged']}")

        print(f"\n  Sensitivity (across {len(sensitivity['results'])} param settings):")
        print(f"  {'label':30s} {'orig_total':>10s} {'new_total':>10s} {'delta':>8s} {'improved':>9s} {'worsened':>9s}")
        for r in sensitivity["results"]:
            print(f"  {r['label']:30s} {r['orig_total_pnl']:>+10.2f} {r['new_total_pnl']:>+10.2f} {r['delta_total_pnl']:>+7.2f} {r['n_improved']:>9} {r['n_worsened']:>9}")

        # Top 5 improved + worsened
        baseline_trades = baseline["trades"]
        improved_sorted = sorted(baseline_trades, key=lambda t: -(t['new_pnl_pct'] - t['original_pnl_pct']))[:5]
        worsened_sorted = sorted(baseline_trades, key=lambda t: (t['new_pnl_pct'] - t['original_pnl_pct']))[:5]
        print(f"\n  Top 5 improved trades:")
        for t in improved_sorted:
            d = t['new_pnl_pct'] - t['original_pnl_pct']
            print(f"    {t['symbol']}/{t['strategy'][:25]:25s} orig={t['original_pnl_pct']:+.1f}% new={t['new_pnl_pct']:+.1f}% (Δ{d:+.1f}%) reason={t['new_exit_reason']}")
        print(f"\n  Top 5 worsened trades:")
        for t in worsened_sorted:
            d = t['new_pnl_pct'] - t['original_pnl_pct']
            print(f"    {t['symbol']}/{t['strategy'][:25]:25s} orig={t['original_pnl_pct']:+.1f}% new={t['new_pnl_pct']:+.1f}% (Δ{d:+.1f}%) reason={t['new_exit_reason']}")

        out_full[label] = sensitivity

    con.close()

    # Save full data
    out_path = OUT_DIR / "backtest_exit_replay.json"
    # Strip trades for output (too verbose)
    out_for_save = {}
    for label, sens in out_full.items():
        out_for_save[label] = {
            "set": sens["set"],
            "results": [{k: v for k, v in r.items() if k != "trades"} for r in sens["results"]],
        }
    with out_path.open("w") as f:
        json.dump(out_for_save, f, indent=2, default=str)
    print(f"\n\nSaved: {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
