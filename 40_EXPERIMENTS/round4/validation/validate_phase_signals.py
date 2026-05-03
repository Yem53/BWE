"""Validate which signal Phase wins on real market data.

Methodology:
1. Find all ±8% events (5min close-to-close) in last 5.8d (live DB)
2. For each event, fetch all 9 candidate signals at event_ts
3. Compute forward 60min raw return (signed, market direction)
4. Apply rule_engine to determine intended direction (long/short)
5. Compute "trade outcome" = forward return × side_factor (positive = profit)
6. Per signal: split events into high/low signal value, compare mean outcome
7. Per Phase: sum of useful signal alphas

Output: ranked signals by alpha + Phase comparison + recommendation.

This is a research artifact — does NOT run in production.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev

# Allow imports from bwe_v2/
sys.path.insert(0, "/Users/ye/.hermes/scripts/bwe_v2")
sys.path.insert(0, "/Volumes/T9/BWE/40_EXPERIMENTS/round4/exit_v2")

LIVE_DB = (
    "/Users/ye/.hermes/research/binance_futures_1m_collector_runtime/"
    "binance_futures_1m.sqlite3"
)

# Phases as defined in brainstorming
PHASE_SIGNALS = {
    1: ["oi_change_5m", "taker_buy_ratio", "ls_global_extreme", "funding_flip"],
    2: ["oi_change_5m", "taker_buy_ratio", "ls_global_extreme", "funding_flip",
        "ls_top_trader_diverge", "basis_perp"],
    3: ["oi_change_5m", "taker_buy_ratio", "ls_global_extreme", "funding_flip",
        "ls_top_trader_diverge", "basis_perp",
        "mark_price_diverge", "premium_index_extreme", "vol_spike"],
}


def find_8pct_events(con: sqlite3.Connection, threshold: float = 8.0) -> list[dict]:
    """Find all ±threshold% close-to-close 5-min events across all symbols.

    Returns list of {symbol, event_ts_ms, event_close, prior_close, magnitude_pct, side}.
    """
    # Get all symbols
    syms = [r[0] for r in con.execute(
        "SELECT DISTINCT symbol FROM klines_1m"
    ).fetchall()]

    events = []
    for sym in syms:
        rows = con.execute(
            "SELECT open_time_ms, close, volume FROM klines_1m "
            "WHERE symbol = ? ORDER BY open_time_ms",
            (sym,),
        ).fetchall()
        if len(rows) < 6:
            continue

        # Iterate sliding 5-min window
        last_event_idx = -1000  # cooldown: don't double-count clustered events
        for i in range(5, len(rows)):
            cur_close = rows[i][1]
            prior_close = rows[i - 5][1]
            if prior_close <= 0:
                continue
            pct = (cur_close - prior_close) / prior_close * 100
            if abs(pct) < threshold:
                continue
            # 30-min cooldown to dedupe wave clusters
            if i - last_event_idx < 30:
                continue
            last_event_idx = i
            events.append({
                "symbol": sym,
                "event_ts_ms": rows[i][0],
                "event_idx": i,
                "event_close": cur_close,
                "prior_close": prior_close,
                "magnitude_pct": pct,
                "side": "pump" if pct > 0 else "dump",
                "event_volume": rows[i][2],
            })
    return events


def lookup_signals(con: sqlite3.Connection, sym: str, ts_ms: int) -> dict:
    """Fetch all candidate signal values at or just before ts_ms.

    Returns dict of signal_name → value (or None if missing).
    """
    out = {}

    # OI 5min change: compare current OI value to OI 5min ago
    try:
        rows = con.execute(
            "SELECT ts_ms, sum_open_interest_value FROM open_interest_5m "
            "WHERE symbol = ? AND ts_ms <= ? "
            "ORDER BY ts_ms DESC LIMIT 2",
            (sym, ts_ms),
        ).fetchall()
        if len(rows) >= 2:
            cur_oi, prev_oi = rows[0][1], rows[1][1]
            out["oi_change_5m"] = (cur_oi - prev_oi) / prev_oi * 100 if prev_oi > 0 else 0.0
    except Exception:
        pass

    # Taker buy/sell ratio (last bar)
    try:
        rows = con.execute(
            "SELECT buy_vol, sell_vol FROM taker_buy_sell_volume_5m "
            "WHERE symbol = ? AND ts_ms <= ? "
            "ORDER BY ts_ms DESC LIMIT 1",
            (sym, ts_ms),
        ).fetchall()
        if rows:
            buy, sell = rows[0]
            out["taker_buy_ratio"] = buy / (buy + sell) if (buy + sell) > 0 else 0.5
    except Exception:
        pass

    # Global LS account ratio (raw and extreme metric)
    try:
        rows = con.execute(
            "SELECT long_account, short_account FROM global_long_short_account_ratio_5m "
            "WHERE symbol = ? AND ts_ms <= ? "
            "ORDER BY ts_ms DESC LIMIT 1",
            (sym, ts_ms),
        ).fetchall()
        if rows:
            la, sa = rows[0]
            ratio = la / (la + sa) if (la + sa) > 0 else 0.5
            out["ls_global"] = ratio
            out["ls_global_extreme"] = abs(ratio - 0.5) * 2  # 0=balanced, 1=extreme one-sided
    except Exception:
        pass

    # Top trader position divergence vs global
    try:
        rows = con.execute(
            "SELECT long_account, short_account FROM top_trader_long_short_position_ratio_5m "
            "WHERE symbol = ? AND ts_ms <= ? "
            "ORDER BY ts_ms DESC LIMIT 1",
            (sym, ts_ms),
        ).fetchall()
        if rows and "ls_global" in out:
            tlp, tsp = rows[0]
            top_ratio = tlp / (tlp + tsp) if (tlp + tsp) > 0 else 0.5
            out["ls_top_trader"] = top_ratio
            out["ls_top_trader_diverge"] = abs(top_ratio - out["ls_global"])
    except Exception:
        pass

    # Funding rate (latest snapshot)
    try:
        rows = con.execute(
            "SELECT funding_rate FROM funding_rate "
            "WHERE symbol = ? AND ts_ms <= ? "
            "ORDER BY ts_ms DESC LIMIT 2",
            (sym, ts_ms),
        ).fetchall()
        if rows:
            cur_fr = rows[0][0]
            out["funding_rate"] = cur_fr
            if len(rows) >= 2:
                prev_fr = rows[1][0]
                out["funding_flip"] = 1.0 if (cur_fr * prev_fr) < 0 else 0.0
    except Exception:
        pass

    # Basis perpetual (perp - spot)
    try:
        rows = con.execute(
            "SELECT basis FROM basis_perpetual_5m "
            "WHERE symbol = ? AND ts_ms <= ? "
            "ORDER BY ts_ms DESC LIMIT 1",
            (sym, ts_ms),
        ).fetchall()
        if rows:
            out["basis_perp"] = rows[0][0]
    except Exception:
        pass

    # Mark price divergence (mark vs last close of klines)
    try:
        rows = con.execute(
            "SELECT close FROM mark_price_1m "
            "WHERE symbol = ? AND ts_ms <= ? "
            "ORDER BY ts_ms DESC LIMIT 1",
            (sym, ts_ms),
        ).fetchall()
        kline_rows = con.execute(
            "SELECT close FROM klines_1m "
            "WHERE symbol = ? AND open_time_ms <= ? "
            "ORDER BY open_time_ms DESC LIMIT 1",
            (sym, ts_ms),
        ).fetchall()
        if rows and kline_rows:
            mark = rows[0][0]
            last_close = kline_rows[0][0]
            out["mark_price_diverge"] = (mark - last_close) / last_close * 100 if last_close > 0 else 0.0
    except Exception:
        pass

    # Premium index (extreme = abs value)
    try:
        rows = con.execute(
            "SELECT close FROM premium_index_1m "
            "WHERE symbol = ? AND ts_ms <= ? "
            "ORDER BY ts_ms DESC LIMIT 1",
            (sym, ts_ms),
        ).fetchall()
        if rows:
            out["premium_index_extreme"] = abs(rows[0][0])
    except Exception:
        pass

    # Volume spike (event vol vs prior 30bar mean)
    try:
        rows = con.execute(
            "SELECT volume FROM klines_1m "
            "WHERE symbol = ? AND open_time_ms <= ? "
            "ORDER BY open_time_ms DESC LIMIT 31",
            (sym, ts_ms),
        ).fetchall()
        if len(rows) >= 11:
            cur_vol = rows[0][0]
            prior_mean = sum(r[0] for r in rows[1:]) / max(1, len(rows) - 1)
            out["vol_spike"] = cur_vol / prior_mean if prior_mean > 0 else 1.0
    except Exception:
        pass

    return out


def forward_return_60min(con: sqlite3.Connection, sym: str, event_ts_ms: int,
                          event_close: float) -> float:
    """Compute forward 60min return from event close → event+60min close."""
    target_ts = event_ts_ms + 60 * 60_000
    rows = con.execute(
        "SELECT close FROM klines_1m WHERE symbol = ? AND open_time_ms = ? LIMIT 1",
        (sym, target_ts),
    ).fetchall()
    if not rows or rows[0][0] <= 0 or event_close <= 0:
        return None
    return (rows[0][0] - event_close) / event_close * 100


def determine_intended_direction(features, side: str) -> str:
    """Apply rule_engine to determine if we'd FADE or FOLLOW for this event.

    Returns 'long' / 'short' / None.
    """
    # Simplified: most ±8% events without features → FADE
    # If reaction == trend_continue → FOLLOW
    # else FADE
    if features and features.get("reaction") == "trend_continue":
        return "long" if side == "pump" else "short"
    # Default fade
    return "short" if side == "pump" else "long"


def compute_trade_outcome(forward_return_pct: float, intended_dir: str) -> float:
    """Convert market return → trade PnL based on intended direction."""
    if intended_dir == "long":
        return forward_return_pct
    elif intended_dir == "short":
        return -forward_return_pct
    return 0.0


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    LOG = logging.getLogger("validate")

    LOG.info("=== Loading ±8%% events from live DB ===")
    con = sqlite3.connect(LIVE_DB, timeout=60)
    con.execute("PRAGMA query_only=1")
    t0 = time.time()
    events = find_8pct_events(con, threshold=8.0)
    LOG.info("found %d events in %.1fs", len(events), time.time() - t0)

    # Load symbol_features for direction logic
    feature_rows = con.execute(
        "SELECT symbol, lifecycle, reaction, yaobi_score FROM symbol_features"
    ).fetchall()
    sym_features = {r[0]: {"lifecycle": r[1], "reaction": r[2], "score": r[3]}
                    for r in feature_rows}
    LOG.info("loaded features for %d symbols", len(sym_features))

    LOG.info("\n=== Enriching events with signals + forward returns ===")
    enriched = []
    for i, ev in enumerate(events):
        if i % 50 == 0:
            LOG.info("  [%d/%d]", i, len(events))
        signals = lookup_signals(con, ev["symbol"], ev["event_ts_ms"])
        fwd = forward_return_60min(con, ev["symbol"], ev["event_ts_ms"], ev["event_close"])
        if fwd is None:
            continue
        feats = sym_features.get(ev["symbol"])
        intended_dir = determine_intended_direction(feats, ev["side"])
        outcome = compute_trade_outcome(fwd, intended_dir)
        enriched.append({
            **ev,
            "forward_return_60min_pct": fwd,
            "intended_direction": intended_dir,
            "trade_outcome_pct": outcome,
            "signals": signals,
            "features": feats,
        })

    con.close()
    LOG.info("enriched %d events with signals + forward returns", len(enriched))

    if not enriched:
        LOG.error("No enriched events — aborting")
        return 1

    # ==========================
    # Per-signal alpha analysis
    # ==========================
    LOG.info("\n=== Per-signal alpha (split by signal value) ===\n")
    LOG.info(f"{'signal':<28s} {'n_high':>8s} {'mean_high':>10s} {'n_low':>8s} {'mean_low':>10s} {'spread':>10s}")

    signal_alphas = {}
    all_signal_names = set()
    for ev in enriched:
        all_signal_names.update(ev["signals"].keys())

    for sig_name in sorted(all_signal_names):
        valid = [e for e in enriched if sig_name in e["signals"]]
        if len(valid) < 20:
            continue
        sig_values = [e["signals"][sig_name] for e in valid]
        # split at median
        med = sorted(sig_values)[len(sig_values) // 2]
        high = [e["trade_outcome_pct"] for e in valid if e["signals"][sig_name] > med]
        low = [e["trade_outcome_pct"] for e in valid if e["signals"][sig_name] <= med]
        if not high or not low:
            continue
        h_mean, l_mean = mean(high), mean(low)
        spread = h_mean - l_mean
        signal_alphas[sig_name] = {
            "n_high": len(high), "mean_high": h_mean,
            "n_low": len(low), "mean_low": l_mean,
            "spread": spread,
        }
        LOG.info(f"{sig_name:<28s} {len(high):>8d} {h_mean:>10.2f}% {len(low):>8d} {l_mean:>10.2f}% {spread:>10.2f}%")

    # Direction-aware spread (which side helps)
    LOG.info("\n=== Best direction per signal (use signal direction with positive spread) ===")
    useful_signals = {}
    for sig_name, stats in signal_alphas.items():
        if abs(stats["spread"]) >= 0.5:  # at least 0.5pp spread to be "useful"
            useful_signals[sig_name] = stats
            LOG.info(f"  {sig_name:<28s}  spread {stats['spread']:+.2f}%  ({'use HIGH' if stats['spread'] > 0 else 'use LOW'})")
        else:
            LOG.info(f"  {sig_name:<28s}  spread {stats['spread']:+.2f}%  (not useful, < 0.5pp)")

    # ==========================
    # Phase comparison
    # ==========================
    LOG.info("\n=== Phase comparison (sum of |spread| across included signals) ===\n")
    phase_results = {}
    for phase, sig_list in PHASE_SIGNALS.items():
        total_alpha = 0.0
        used = 0
        for s in sig_list:
            if s in useful_signals:
                total_alpha += abs(useful_signals[s]["spread"])
                used += 1
        n_total = len(sig_list)
        phase_results[phase] = {
            "total_alpha": total_alpha,
            "useful_signals": used,
            "total_signals": n_total,
            "alpha_per_signal": total_alpha / n_total if n_total else 0,
        }
        LOG.info(
            f"  Phase-{phase} ({n_total} signals): "
            f"useful={used}/{n_total}, total_alpha={total_alpha:.2f}pp, "
            f"alpha/signal={total_alpha/n_total:.2f}pp"
        )

    # Overall stats
    LOG.info("\n=== Overall sample stats ===")
    outcomes = [e["trade_outcome_pct"] for e in enriched]
    LOG.info(f"  n_events: {len(enriched)}")
    LOG.info(f"  mean trade outcome: {mean(outcomes):.2f}%")
    LOG.info(f"  median: {sorted(outcomes)[len(outcomes)//2]:.2f}%")
    LOG.info(f"  stdev: {stdev(outcomes):.2f}%")
    LOG.info(f"  win rate (>0): {sum(1 for o in outcomes if o > 0)/len(outcomes)*100:.1f}%")
    LOG.info(f"  pump events: {sum(1 for e in enriched if e['side']=='pump')}")
    LOG.info(f"  dump events: {sum(1 for e in enriched if e['side']=='dump')}")

    # Save full enriched data + summary for review
    out_path = Path("/Volumes/T9/BWE/40_EXPERIMENTS/round4/validation/phase_signal_validation.json")
    with open(out_path, "w") as f:
        json.dump({
            "n_events": len(enriched),
            "signal_alphas": signal_alphas,
            "useful_signals": list(useful_signals.keys()),
            "phase_results": phase_results,
            "overall": {
                "mean_outcome": mean(outcomes),
                "win_rate_pct": sum(1 for o in outcomes if o > 0)/len(outcomes)*100,
                "n_pump": sum(1 for e in enriched if e['side']=='pump'),
                "n_dump": sum(1 for e in enriched if e['side']=='dump'),
            },
        }, f, indent=2, default=str)
    LOG.info(f"\nSaved: {out_path}")

    # ==========================
    # Recommendation
    # ==========================
    LOG.info("\n=== Recommendation ===")
    best = max(phase_results.items(), key=lambda x: x[1]["alpha_per_signal"])
    LOG.info(f"  Best alpha/signal: Phase-{best[0]} ({best[1]['alpha_per_signal']:.2f}pp/signal)")
    most = max(phase_results.items(), key=lambda x: x[1]["total_alpha"])
    LOG.info(f"  Best total alpha: Phase-{most[0]} ({most[1]['total_alpha']:.2f}pp total)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
