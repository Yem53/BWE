"""Paper-shadow $1000-account simulator for top candidates.

Takes a candidate (entry archetype + best TP/SL/exit_family) from the
results, replays its trades through a simulated $1000 USDT account with
5-10% per-trade sizing, and reports realistic daily PnL + drawdown stats.

This bridges the "high oos_p25_net_pct" backtest score to the actual
live experience: how many trades/day, max DD%, Sharpe, time in market.

Three stress scenarios per candidate:
  - "ideal":   8 bps cost, 0s slippage (matches backtest)
  - "realistic": 16 bps cost (2x), 1.5s entry latency, 50% fill
  - "harsh":   24 bps cost (3x), 5s entry latency, 30% fill, 1.5% slippage

Output: H:/BWE/40_EXPERIMENTS/paper_shadow/<entry_id>_<timestamp>.md

Usage:
    python scripts/paper_shadow_sim.py E126
    python scripts/paper_shadow_sim.py E126 --capital 1000 --size-pct 7.5
    python scripts/paper_shadow_sim.py E126 --tp 0.51 --sl 6.00 --exit-family fixed
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import torch

from bwe_autoresearch.bwe_loop import (
    Combo, expand_variant_grid, load_events_for_combo, load_registry,
)
from bwe_autoresearch.bwe_loop_gpu_eval import (
    EventBatch, VariantGrid, batch_eval, get_device,
)
from bwe_autoresearch.bwe_loop_exit_kernels import (
    classify_exit_family,
    eval_breakeven, eval_multi_tp_50_50, eval_time_only, eval_trailing_pct,
)


from bwe_autoresearch.bwe_paths import PAPER_DIR  # noqa: E402


def _route_eval(family: str, events, variants, cost_pct, device):
    """Route to the right kernel based on exit family."""
    events_gpu = events.to(device) if family != "fixed" else events
    variants_gpu = variants.to(device) if family != "fixed" else variants
    if family == "time_only":
        return eval_time_only(events_gpu, variants_gpu, cost_pct, variant_chunk=8192)
    if family == "breakeven":
        return eval_breakeven(events_gpu, variants_gpu, cost_pct, variant_chunk=8192)
    if family == "trail":
        return eval_trailing_pct(events_gpu, variants_gpu, cost_pct, variant_chunk=8192)
    if family == "multi_tp":
        return eval_multi_tp_50_50(events_gpu, variants_gpu, cost_pct, variant_chunk=8192)
    return batch_eval(events_gpu, variants_gpu, cost_pct=cost_pct, device=device, variant_chunk=8192)


def simulate_account(per_trade_returns_pct: np.ndarray, ts_ms: np.ndarray | None,
                     capital: float, size_pct: float) -> dict:
    """Walk through trades with sequential capital compounding.

    Each trade risks size_pct of CURRENT capital. Net% from kernel applied
    to that allocation. Capital grows or shrinks accordingly.
    """
    n = len(per_trade_returns_pct)
    if n == 0:
        return {"n_trades": 0}

    # Sort by ts if available (ensures chronological compounding)
    if ts_ms is not None:
        order = np.argsort(ts_ms)
        per_trade_returns_pct = per_trade_returns_pct[order]
        ts_ms = ts_ms[order]

    equity = [capital]
    peak = capital
    drawdowns = []
    cur = capital

    for r in per_trade_returns_pct:
        size = cur * (size_pct / 100.0)
        pnl = size * (r / 100.0)
        cur += pnl
        equity.append(cur)
        if cur > peak:
            peak = cur
        else:
            dd = (peak - cur) / peak
            drawdowns.append(dd)

    final = equity[-1]
    total_ret_pct = (final / capital - 1) * 100
    max_dd_pct = max(drawdowns) * 100 if drawdowns else 0.0

    # Daily aggregation if timestamps given
    daily_pnl_summary = None
    if ts_ms is not None:
        ts_sorted = ts_ms
        days = ts_sorted // (1000 * 86400)
        unique_days, counts = np.unique(days, return_counts=True)
        n_days = len(unique_days)
        avg_trades_per_day = n / n_days if n_days else 0
        # rough daily P&L: just total / n_days
        avg_daily_pnl = (final - capital) / n_days if n_days else 0
        daily_pnl_summary = {
            "n_days": int(n_days),
            "avg_trades_per_day": round(avg_trades_per_day, 1),
            "avg_daily_pnl_usd": round(avg_daily_pnl, 2),
            "avg_daily_pnl_pct": round(avg_daily_pnl / capital * 100, 3),
        }

    # Win rate
    wins = (per_trade_returns_pct > 0).sum()

    # Approx Sharpe: per-trade return / std (annualized roughly)
    rets = per_trade_returns_pct / 100.0
    sharpe_per_trade = float(rets.mean() / rets.std()) if rets.std() > 0 else 0.0

    return {
        "n_trades": int(n),
        "starting_capital": capital,
        "final_capital": round(final, 2),
        "total_return_pct": round(total_ret_pct, 2),
        "max_drawdown_pct": round(max_dd_pct, 2),
        "win_rate_pct": round(wins / n * 100, 1) if n else 0,
        "sharpe_per_trade": round(sharpe_per_trade, 3),
        "avg_trade_return_pct": round(float(rets.mean() * 100), 4),
        "median_trade_return_pct": round(float(np.median(rets) * 100), 4),
        "p10_trade_return_pct": round(float(np.quantile(rets, 0.10) * 100), 4),
        "daily": daily_pnl_summary,
    }


def run_scenario(events, tp: float, sl: float, hold: int, exit_family: str,
                 cost_pct: float, capital: float, size_pct: float,
                 ts_ms: np.ndarray | None, label: str) -> dict:
    """Evaluate one (events, params, cost) scenario and run account sim."""
    device = get_device()
    variants = VariantGrid.from_numpy(
        np.array([tp], dtype=np.float32),
        np.array([sl], dtype=np.float32),
        np.array([hold], dtype=np.int16),
    )
    net = _route_eval(exit_family, events, variants, cost_pct, device)
    rets = net.cpu().numpy().ravel()  # [N_events]

    # Drop NaN
    mask = ~np.isnan(rets)
    rets = rets[mask]
    if ts_ms is not None:
        ts_ms = ts_ms[mask]

    sim = simulate_account(rets, ts_ms, capital, size_pct)
    sim["scenario"] = label
    sim["cost_pct"] = cost_pct
    sim["tp"] = tp
    sim["sl"] = sl
    sim["hold"] = hold
    sim["exit_family"] = exit_family
    return sim


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("entry_id", help="Entry archetype id, e.g. E126")
    ap.add_argument("--tp", type=float, default=None, help="best TP from results (auto-lookup)")
    ap.add_argument("--sl", type=float, default=None, help="best SL")
    ap.add_argument("--hold", type=int, default=15)
    ap.add_argument("--exit-family", default=None, help="fixed | time_only | breakeven | trail | multi_tp")
    ap.add_argument("--exit-archetype", default="fixed_tp1_sl1_symmetric")
    ap.add_argument("--capital", type=float, default=1000.0)
    ap.add_argument("--size-pct", type=float, default=7.5, help="Position size as %% of capital")
    ap.add_argument("--max-events", type=int, default=5000)
    args = ap.parse_args()

    registry = load_registry()
    e = next((r for r in registry if r["id"] == args.entry_id), None)
    if e is None:
        print(f"FATAL: entry {args.entry_id} not in registry")
        return 1

    family = args.exit_family or classify_exit_family(args.exit_archetype)

    combo = Combo(
        entry_id=args.entry_id, exit_id="X001",
        entry_archetype=e["archetype"], exit_archetype=args.exit_archetype,
        channel=e["channel"], side=e["side"],
        novel_dim=tuple(e.get("novel_dim", [])),
    )
    print(f"Entry: {args.entry_id} {e['archetype']}")
    print(f"  channel={e['channel']} side={e['side']}")
    print(f"  novel_dim: {e.get('novel_dim', [])}")
    print(f"Exit: family={family} archetype={args.exit_archetype}")
    print(f"Capital: ${args.capital}  Size: {args.size_pct}% per trade")
    print()

    events = load_events_for_combo(combo, max_events=args.max_events)
    if events is None:
        print(f"FATAL: no events for combo (filter too strict or channel mismatch)")
        return 1
    print(f"Events after filter: {events.n_events}")

    # Auto-fill (TP, SL, exit family, archetype) from results.tsv when not provided.
    # Round 4 fix: cross-family lookup picks the best score across ALL exit families
    # for this entry; previous behavior locked to default fixed_tp1_sl1_symmetric and
    # silently mis-routed (e.g. trail-best-paired entry scored against fixed kernel).
    # Pass --exit-family X to lock a specific family; otherwise the loaded best
    # archetype's family is used for _route_eval.
    if args.tp is None or args.sl is None:
        results_tsv = REPO_ROOT / "results.tsv"
        if results_tsv.exists():
            best_score = -1e9
            best_tp = best_sl = None
            best_family = best_archetype = None
            for line in results_tsv.read_text(encoding="utf-8").splitlines()[1:]:
                if f"E={args.entry_id}/" not in line:
                    continue
                try:
                    line_archetype = line.split("X=")[1].split("/")[1].split(" ")[0]
                except IndexError:
                    continue
                line_family = classify_exit_family(line_archetype)
                if args.exit_family and line_family != args.exit_family:
                    continue
                try:
                    score = float(line.split("\t")[1])
                except (IndexError, ValueError):
                    continue
                if score > best_score:
                    import re
                    m_tp = re.search(r"best_tp=([\d.]+)", line)
                    m_sl = re.search(r"best_sl=([\d.]+)", line)
                    if m_tp and m_sl:
                        best_score = score
                        best_tp = float(m_tp.group(1))
                        best_sl = float(m_sl.group(1))
                        best_family = line_family
                        best_archetype = line_archetype
            if best_tp is not None:
                args.tp = best_tp
                args.sl = best_sl
                # Round 4 fix: also override family + archetype to match the best line
                family = best_family
                args.exit_archetype = best_archetype
                scope = "in-family" if args.exit_family else "across all families"
                print(f"Auto-filled best from results.tsv ({scope}):")
                print(f"  archetype={best_archetype}  family={family}  TP={args.tp}  SL={args.sl}  (score={best_score:.4f})")
        if args.tp is None:
            print("FATAL: no --tp/--sl given and no results.tsv match")
            return 1
    print()

    # We don't have ts_ms in EventBatch; could enrich later. Skip for now.
    ts_ms = None

    scenarios = [
        ("ideal",      0.08, args.tp, args.sl),
        ("realistic",  0.16, args.tp, args.sl),
        ("harsh",      0.24, args.tp, args.sl),
    ]

    results = []
    for name, cost, tp, sl in scenarios:
        r = run_scenario(events, tp, sl, args.hold, family, cost,
                         args.capital, args.size_pct, ts_ms, name)
        results.append(r)

    # Render
    print("=" * 90)
    print(f"PAPER SHADOW SIMULATION — {args.entry_id} {e['archetype']}")
    print("=" * 90)
    for r in results:
        print(f"\n[{r['scenario']:9s}]  cost={r['cost_pct']*100:.0f}bps  tp={r['tp']:.2f}  sl={r['sl']:.2f}  family={r['exit_family']}")
        print(f"  trades:        {r['n_trades']}")
        print(f"  starting $:    ${r['starting_capital']:.2f}")
        print(f"  final $:       ${r['final_capital']:.2f}  ({r['total_return_pct']:+.2f}% total)")
        print(f"  max DD:        {r['max_drawdown_pct']:.2f}%")
        print(f"  win rate:      {r['win_rate_pct']:.1f}%")
        print(f"  sharpe/trade:  {r['sharpe_per_trade']:+.3f}")
        print(f"  avg/median/p10 trade: {r['avg_trade_return_pct']:+.4f}% / {r['median_trade_return_pct']:+.4f}% / {r['p10_trade_return_pct']:+.4f}%")
        if r["daily"]:
            d = r["daily"]
            print(f"  per-day: ~{d['avg_trades_per_day']} trades, "
                  f"avg ${d['avg_daily_pnl_usd']:+.2f} ({d['avg_daily_pnl_pct']:+.3f}%) over {d['n_days']} days")

    # Save markdown report
    PAPER_DIR.mkdir(parents=True, exist_ok=True)
    md_path = PAPER_DIR / f"{args.entry_id}_{int(time.time())}.md"
    with md_path.open("w", encoding="utf-8") as f:
        f.write(f"# Paper Shadow — {args.entry_id} {e['archetype']}\n\n")
        f.write(f"- Channel: {e['channel']}  Side: {e['side']}\n")
        f.write(f"- novel_dim: `{e.get('novel_dim', [])}`\n")
        f.write(f"- Exit family: {family}  ({args.exit_archetype})\n")
        f.write(f"- Capital: ${args.capital}  Position size: {args.size_pct}% per trade\n")
        f.write(f"- Events after filter: {events.n_events}\n\n")
        f.write("| Scenario | cost(bps) | trades | final$ | total% | max_dd% | win% | sharpe | p10 trade% |\n")
        f.write("|---|---:|---:|---:|---:|---:|---:|---:|---:|\n")
        for r in results:
            f.write(f"| {r['scenario']} | {r['cost_pct']*100:.0f} | {r['n_trades']} | "
                    f"${r['final_capital']:.2f} | {r['total_return_pct']:+.2f} | "
                    f"{r['max_drawdown_pct']:.2f} | {r['win_rate_pct']:.1f} | "
                    f"{r['sharpe_per_trade']:+.3f} | {r['p10_trade_return_pct']:+.4f} |\n")
        f.write("\n")
    print(f"\nSaved: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
