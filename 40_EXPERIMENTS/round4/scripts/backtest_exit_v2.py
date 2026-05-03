"""Backtest exit_v2 against Hermes live + paper trades.

Runs multiple ExitConfig variants for sensitivity / anti-overfit validation.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "exit_v2"))
from exit_v2 import (
    Bar, Position, ExitConfig, ExitEngine, ExitDecision,
    compute_atr_pct, dynamic_trail_step, is_volume_confirmed_breakdown,
)

LIVE_JOURNAL = Path("/Users/ye/.hermes/research/bwe_live_autotrader_binance_expectancy_runtime/trade_journal.jsonl")
PAPER_JOURNAL = Path("/Users/ye/.hermes/research/bwe_paper_multilot_observer_runtime/trade_journal.jsonl")
KLINE_DB = "/Users/ye/.hermes/research/binance_futures_1m_collector_runtime/binance_futures_1m.sqlite3"
OUT_DIR = Path("/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_closed_trades(path: Path) -> list[dict]:
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
        # Compute original raw 1x pnl_pct from prices (uniform comparison basis)
        ep_val = t.get("entry_px") or t.get("fill_price") or 0
        xp_val = final.get("fill_price") or final.get("exit_px") or 0
        ep = float(ep_val) if ep_val is not None else 0.0
        xp = float(xp_val) if xp_val is not None else 0.0
        side = t["side"]
        if ep == 0:
            continue  # skip malformed trade
        if side == "long":
            orig_raw_pnl = (xp - ep) / ep * 100 if ep > 0 else 0
        else:
            orig_raw_pnl = (ep - xp) / ep * 100 if ep > 0 else 0
        closed.append({
            "trade_id": tid,
            "symbol": t["symbol"],
            "market_symbol": t["market_symbol"],
            "strategy": t["strategy_name"],
            "side": side,
            "entry_ts_ms": int(t.get("entry_ts", t["ts"]) * 1000),
            "entry_px": ep,
            "orig_exit_ts_ms": int(final["ts"] * 1000),
            "orig_exit_px": xp,
            "orig_exit_reason": final.get("exit_reason", "?"),
            "orig_journal_pnl": final.get("pnl_pct", 0),  # leveraged
            "orig_raw_pnl_pct": orig_raw_pnl,             # 1x equivalent
            "hold_minutes_limit": float(t.get("hold_minutes_limit", 60)),
        })
    return closed


def fetch_kline_window(con, market_symbol: str, start_ms: int, end_ms: int) -> list[Bar]:
    cur = con.execute(
        "SELECT open_time_ms, open, high, low, close, volume FROM klines_1m "
        "WHERE symbol=? AND open_time_ms BETWEEN ? AND ? ORDER BY open_time_ms",
        (market_symbol, start_ms, end_ms),
    )
    return [Bar(*r) for r in cur.fetchall()]


def replay_trade(trade: dict, con, engine: ExitEngine, atr_lookback_min: int = 30) -> dict:
    """Replay a trade with new exit engine, using 1m kline minute-by-minute."""
    entry_ts = trade["entry_ts_ms"]
    end_ts = entry_ts + int((trade["hold_minutes_limit"] + 5) * 60_000)
    pre_ts = entry_ts - atr_lookback_min * 60_000

    bars = fetch_kline_window(con, trade["market_symbol"], pre_ts, end_ts)
    if not bars:
        return {"new_pnl_raw_pct": trade["orig_raw_pnl_pct"], "new_exit_reason": "no_kline_data"}

    # Find entry index (first bar with ts_ms >= entry_ts)
    entry_idx = next((i for i, b in enumerate(bars) if b.ts_ms >= entry_ts), None)
    if entry_idx is None:
        return {"new_pnl_raw_pct": trade["orig_raw_pnl_pct"], "new_exit_reason": "entry_not_in_bars"}

    pre_entry_bars = bars[:entry_idx]
    atr_at_entry = compute_atr_pct(pre_entry_bars, period=14, ref_px=trade["entry_px"]) if pre_entry_bars else 0.0

    pos = Position(
        entry_ts_ms=entry_ts,
        entry_px=trade["entry_px"],
        side=trade["side"],
        hold_minutes_limit=trade["hold_minutes_limit"],
        atr_at_entry=atr_at_entry,
        high_water_pct=0.0,
    )

    # Walk minute-by-minute from entry
    decision: ExitDecision | None = None
    for i in range(entry_idx, len(bars)):
        bars_so_far = bars[: i + 1]
        d = engine.decide(pos, bars_so_far)
        if d:
            decision = d
            break

    if decision is None:
        # No trigger — close at last bar
        last = bars[-1]
        if pos.side == "long":
            pnl = (last.close - pos.entry_px) / pos.entry_px * 100
        else:
            pnl = (pos.entry_px - last.close) / pos.entry_px * 100
        return {
            "new_exit_ts_ms": last.ts_ms,
            "new_exit_px": last.close,
            "new_pnl_raw_pct": pnl,
            "new_exit_reason": "data_end_no_trigger",
            "new_hold_min": (last.ts_ms - entry_ts) / 60_000,
            "atr_at_entry": atr_at_entry,
            "final_high_water_pct": pos.high_water_pct,
        }
    return {
        "new_exit_ts_ms": decision.exit_ts_ms,
        "new_exit_px": decision.exit_px,
        "new_pnl_raw_pct": decision.pnl_pct,
        "new_exit_reason": decision.reason,
        "new_hold_min": (decision.exit_ts_ms - entry_ts) / 60_000,
        "atr_at_entry": atr_at_entry,
        "final_high_water_pct": pos.high_water_pct,
        "notes": decision.notes,
    }


def aggregate(trades_with_results: list[dict]) -> dict:
    n = len(trades_with_results)
    orig_total = sum(t["orig_raw_pnl_pct"] for t in trades_with_results)
    new_total = sum(t["new_pnl_raw_pct"] for t in trades_with_results)
    orig_wins = sum(1 for t in trades_with_results if t["orig_raw_pnl_pct"] > 0)
    new_wins = sum(1 for t in trades_with_results if t["new_pnl_raw_pct"] > 0)
    improved = sum(1 for t in trades_with_results if t["new_pnl_raw_pct"] > t["orig_raw_pnl_pct"] + 0.5)
    worsened = sum(1 for t in trades_with_results if t["new_pnl_raw_pct"] < t["orig_raw_pnl_pct"] - 0.5)
    return {
        "n": n,
        "orig_total_pnl_raw": orig_total,
        "new_total_pnl_raw": new_total,
        "delta_total": new_total - orig_total,
        "orig_win_rate": orig_wins / n * 100 if n else 0,
        "new_win_rate": new_wins / n * 100 if n else 0,
        "n_improved": improved,
        "n_worsened": worsened,
        "n_unchanged": n - improved - worsened,
    }


def run_config(label: str, config: ExitConfig, all_trades: dict, con) -> dict:
    """Run one config across both LIVE and PAPER datasets."""
    engine = ExitEngine(config)
    results = {}
    for ds_label, trades in all_trades.items():
        enriched = []
        for t in trades:
            result = replay_trade(t, con, engine)
            enriched.append({**t, **result})
        agg = aggregate(enriched)
        # Also extract TRADOOR for live
        tradoor = next((t for t in enriched if "TRADOOR" in t["symbol"]), None)
        results[ds_label] = {
            "agg": agg,
            "tradoor_orig_raw": tradoor["orig_raw_pnl_pct"] if tradoor else None,
            "tradoor_new_raw": tradoor["new_pnl_raw_pct"] if tradoor else None,
            "tradoor_exit_reason": tradoor["new_exit_reason"] if tradoor else None,
        }
        # Save trades for baseline only (most useful)
        if label == "v2_baseline":
            results[ds_label]["trades"] = enriched
    return {"label": label, "config": config.__dict__, "results": results}


def main() -> int:
    print("=" * 80)
    print("Backtest exit_v2 vs Hermes live + paper trades")
    print("=" * 80)
    print()
    print("Anti-overfit design:")
    print("  - First-principles dynamic trail (5/10/25/50/100% tiers)")
    print("  - ATR-aware hard stop (max 5%, 2.5×ATR)")
    print("  - Volume-confirmed breakdown filter (洗盘 detection)")
    print("  - Sensitivity across multiple configs")
    print()

    con = sqlite3.connect(KLINE_DB)
    all_trades = {
        "LIVE": load_closed_trades(LIVE_JOURNAL),
        "PAPER": load_closed_trades(PAPER_JOURNAL),
    }
    print(f"LIVE trades: {len(all_trades['LIVE'])}")
    print(f"PAPER trades: {len(all_trades['PAPER'])}")
    print()

    # Define configs to test
    configs = [
        ("v2_baseline", ExitConfig()),  # default first-principles (G2 ON)
        ("v2_g2_off", ExitConfig(tradoor_saver_enabled=False)),
        ("v2_g2_threshold_15", ExitConfig(tradoor_saver_hw_threshold=15.0)),
        ("v2_g2_threshold_50", ExitConfig(tradoor_saver_hw_threshold=50.0)),
        ("v2_g2_age_5min", ExitConfig(tradoor_saver_max_hw_age_min=5.0)),
        ("v2_no_volume_confirm", ExitConfig(volume_confirm_enabled=False)),
        ("v2_volume_strict_2x", ExitConfig(volume_confirm_ratio=2.0)),
        ("v2_tiers_tighter", ExitConfig(trail_tiers=(
            (5.0, 3.0), (10.0, 5.0), (25.0, 8.0), (50.0, 12.0), (100.0, 18.0)
        ))),
        ("v2_tiers_wider", ExitConfig(trail_tiers=(
            (5.0, 5.0), (10.0, 10.0), (25.0, 18.0), (50.0, 25.0), (100.0, 35.0)
        ))),
        ("v2_atr_off", ExitConfig(hard_stop_atr_mult=0.0)),  # use min only (5%)
        ("v2_atr_aggressive", ExitConfig(hard_stop_atr_mult=4.0)),
        ("v2_no_min_hold", ExitConfig(catastrophe_min_hold_min=0.0)),
        ("v1_static_5pct", ExitConfig(trail_tiers=((5.0, 5.0),),
                                      tradoor_saver_enabled=False)),  # match v1 backtest
    ]

    all_results = []
    for label, cfg in configs:
        r = run_config(label, cfg, all_trades, con)
        all_results.append(r)

    # Print headline summary table
    print()
    print("=" * 110)
    print(f"{'config':28s} {'LIVE.orig':>10} {'LIVE.new':>10} {'L.delta':>8} {'L.WR':>6} | "
          f"{'PAPER.orig':>11} {'PAPER.new':>11} {'P.delta':>9} {'P.WR':>6} | TRADOOR")
    print("-" * 110)
    for r in all_results:
        live = r["results"]["LIVE"]["agg"]
        paper = r["results"]["PAPER"]["agg"]
        tradoor_new = r["results"]["LIVE"]["tradoor_new_raw"]
        tradoor_str = f"{tradoor_new:>+6.1f}%" if tradoor_new else "n/a"
        print(f"{r['label']:28s} "
              f"{live['orig_total_pnl_raw']:>+9.1f}% {live['new_total_pnl_raw']:>+9.1f}% "
              f"{live['delta_total']:>+7.1f} {live['new_win_rate']:>5.0f}% | "
              f"{paper['orig_total_pnl_raw']:>+10.1f}% {paper['new_total_pnl_raw']:>+10.1f}% "
              f"{paper['delta_total']:>+8.1f} {paper['new_win_rate']:>5.0f}% | "
              f"{tradoor_str}")
    print("=" * 110)

    # Detail on v2_baseline
    baseline = next(r for r in all_results if r["label"] == "v2_baseline")
    print()
    print("=" * 70)
    print("DEEP DIVE: v2_baseline")
    print("=" * 70)
    for ds in ["LIVE", "PAPER"]:
        agg = baseline["results"][ds]["agg"]
        print(f"\n{ds}:")
        print(f"  total trades: {agg['n']}")
        print(f"  orig total raw PnL: {agg['orig_total_pnl_raw']:+.2f}%")
        print(f"  new  total raw PnL: {agg['new_total_pnl_raw']:+.2f}%")
        print(f"  delta:              {agg['delta_total']:+.2f}%")
        print(f"  orig win rate: {agg['orig_win_rate']:.1f}%   →   new: {agg['new_win_rate']:.1f}%")
        print(f"  improved/worsened/unchanged: {agg['n_improved']}/{agg['n_worsened']}/{agg['n_unchanged']}")

        trades = baseline["results"][ds].get("trades", [])
        if trades:
            top_imp = sorted(trades, key=lambda t: -(t["new_pnl_raw_pct"] - t["orig_raw_pnl_pct"]))[:5]
            top_wor = sorted(trades, key=lambda t: (t["new_pnl_raw_pct"] - t["orig_raw_pnl_pct"]))[:5]
            print(f"  Top 5 improved:")
            for t in top_imp:
                d = t["new_pnl_raw_pct"] - t["orig_raw_pnl_pct"]
                print(f"    {t['symbol']:12s}/{t['strategy'][:25]:25s} "
                      f"orig={t['orig_raw_pnl_pct']:+5.1f}% new={t['new_pnl_raw_pct']:+5.1f}% "
                      f"(Δ{d:+5.1f}) reason={t['new_exit_reason']}")
            print(f"  Top 5 worsened:")
            for t in top_wor:
                d = t["new_pnl_raw_pct"] - t["orig_raw_pnl_pct"]
                print(f"    {t['symbol']:12s}/{t['strategy'][:25]:25s} "
                      f"orig={t['orig_raw_pnl_pct']:+5.1f}% new={t['new_pnl_raw_pct']:+5.1f}% "
                      f"(Δ{d:+5.1f}) reason={t['new_exit_reason']}")

    # Save full
    save_path = OUT_DIR / "exit_v2_backtest_results.json"
    serializable = []
    for r in all_results:
        rs = {"label": r["label"], "config": {k: str(v) for k, v in r["config"].items()},
              "results": {ds: {**v, "trades": "(stripped)"} for ds, v in r["results"].items()}}
        for ds in rs["results"]:
            if "trades" in rs["results"][ds]:
                rs["results"][ds].pop("trades", None)
        serializable.append(rs)
    save_path.write_text(json.dumps(serializable, indent=2, default=str))
    print(f"\n  saved: {save_path}")

    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
