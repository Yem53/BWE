"""Simulate user-chosen layered sizing (Option C base) on real data.

Layered scheme (per-symbol or per-rule):
  - Score ≥ 85 / Rule C/D + sc≥85    → 12% × 3x = 36% effective
  - Score 70-85 / Rule C/D            → 8% × 3x = 24% effective
  - Score 50-70 / Rule G default       → 5% × 3x = 15% effective
  - Score < 50  / Rule G low conf     → 3% × 2x = 6% effective
  - Rule A/E/F SKIP                    → 0% (no entry)

Apply to:
  1. BWE PAPER L2-per-lifecycle (210 trades, score-based layering)
  2. Broader L4-tier (1425 events, rule+score-based layering)

Output: max DD, total cap, sharpe, liquidation count → inform DD threshold choice.
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
OUT = Path("/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits/layered_sizing_simulation.json")

LIQUIDATION_THRESHOLD_RAW = {1: -100.0, 2: -50.0, 3: -33.3, 5: -20.0}
ROUND_TRIP_BPS_SPICY = 18.0
ROUND_TRIP_BPS_LIQUID = 12.0


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


def layered_sizing(score: float, rule_id: str = "G") -> tuple[float, float]:
    """Return (pos_pct, leverage) based on score + rule.

    User-chosen layered scheme (Option C base):
      - Rule C/D + sc≥85 OR sc≥85       → 12% × 3x  (36% eff)
      - Rule C/D OR sc 70-85            → 8% × 3x   (24% eff)
      - Rule G + sc 50-70 OR sc default → 5% × 3x   (15% eff)
      - Rule G + sc < 50                → 3% × 2x   (6% eff)
      - Rule A/E/F                      → 0 (SKIP)
    """
    if rule_id in ("A", "E", "F"):
        return 0, 0
    if rule_id in ("C", "D") and score >= 85:
        return 12, 3
    if rule_id in ("C", "D"):
        return 8, 3
    if score >= 85:
        return 12, 3
    if score >= 70:
        return 8, 3
    if score >= 50:
        return 5, 3
    return 3, 2


def compute_metrics(cap_pnls: list[float], n_liquidated: int) -> dict:
    n = len(cap_pnls)
    if n == 0:
        return {}
    total = sum(cap_pnls)
    mean = total / n
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

    if n > 1:
        var = sum((p - mean) ** 2 for p in cap_pnls) / (n - 1)
        stdev = math.sqrt(var)
        sharpe = (mean / stdev * math.sqrt(n)) if stdev > 0 else 999.0
    else:
        sharpe = 0

    return {
        "n": n, "total_cap": total, "mean_cap": mean,
        "win_rate": wins / n * 100, "max_dd_capital": max_dd,
        "sharpe": sharpe, "n_liquidated": n_liquidated,
        "best": max(cap_pnls), "worst": min(cap_pnls),
    }


def simulate_paper(con, paper, sym_meta, sym_to_score):
    """BWE PAPER L2-per-lifecycle with score-based layered sizing (no rule engine)."""
    print("=" * 100)
    print("BWE PAPER L2-per-lifecycle — score-based layered sizing")
    print("=" * 100)

    cap_pnls = []
    n_liq = 0
    sizing_dist = Counter()

    for t in paper:
        raw = replay_with_lifecycle(t, con, sym_meta)
        if raw is None:
            continue
        sym = t["market_symbol"]
        score = sym_to_score.get(sym, 30)
        pos_pct, lev = layered_sizing(score, rule_id="G")  # BWE has no rule engine
        sizing_dist[(pos_pct, lev)] += 1

        if pos_pct == 0:
            continue
        # Liquidation check
        liq_thresh = LIQUIDATION_THRESHOLD_RAW.get(lev, -100.0)
        if raw <= liq_thresh:
            n_liq += 1
            cap_pnl = -pos_pct  # lose entire margin
        else:
            cap_pnl = raw * pos_pct / 100 * lev
        # Apply fee (spicy assumption)
        fee_pct = pos_pct * lev * ROUND_TRIP_BPS_SPICY / 10000
        cap_pnl -= fee_pct
        cap_pnls.append(cap_pnl)

    metrics = compute_metrics(cap_pnls, n_liq)
    print(f"\n  Sizing distribution ((pos, lev): count):")
    for (p, l), c in sorted(sizing_dist.items()):
        eff = p * l
        print(f"    {p}% × {l}x = {eff}% effective: {c}")
    print(f"\n  Aggregate metrics:")
    print(f"    n={metrics['n']}, total_cap={metrics['total_cap']:+.2f}%")
    print(f"    mean_cap={metrics['mean_cap']:+.4f}%, win={metrics['win_rate']:.1f}%")
    print(f"    max_DD_capital={metrics['max_dd_capital']:.2f}%, sharpe={metrics['sharpe']:.2f}")
    print(f"    liquidations: {n_liq}")
    print(f"    best={metrics['best']:+.2f}%, worst={metrics['worst']:+.2f}%")

    return metrics, dict(sizing_dist)


def simulate_broader(con, sym_meta, sym_to_score):
    """1425 broader-market events with rule+score layered sizing."""
    print("\n" + "=" * 100)
    print("Broader market 1425 events — rule+score layered sizing")
    print("=" * 100)

    EVENT_PCT = 8.0
    HOLD_MIN_LIMIT = 360.0
    MIN_PRE_BARS = 35

    syms = sorted([r[0] for r in con.execute("SELECT DISTINCT symbol FROM klines_1m").fetchall()])
    cap_pnls = []
    n_liq = 0
    sizing_dist = Counter()

    for sym in syms:
        rows = con.execute(
            "SELECT open_time_ms, open, high, low, close, volume FROM klines_1m "
            "WHERE symbol=? ORDER BY open_time_ms", (sym,)).fetchall()
        if len(rows) < MIN_PRE_BARS + 6: continue
        last_ev = -10**18
        for k in range(5, len(rows) - 1):
            if k < MIN_PRE_BARS: continue
            if rows[k][0] - last_ev < 60 * 60_000: continue
            c_now = rows[k][4]; c_then = rows[k-5][4]
            if c_then <= 0: continue
            ret = (c_now - c_then) / c_then * 100
            if abs(ret) < EVENT_PCT: continue

            entry_idx = k + 1
            entry_px = rows[entry_idx][1]

            # Compute features
            pre5 = rows[k-5:k]; base = rows[max(0, k-35):k-5]
            rv = sum(r[5] for r in pre5)/max(1, len(pre5))
            bv = sum(r[5] for r in base)/max(1, len(base))
            pre_vol = rv/bv if bv > 0 else 0
            wave_dur = 0
            for kk in range(k, max(0, k-15), -1):
                if kk < 5: break
                rt = abs((rows[kk][4] - rows[kk-5][4]) / rows[kk-5][4] * 100) if rows[kk-5][4] > 0 else 0
                if rt >= 5: wave_dur = (rows[k][0] - rows[kk][0])/60_000 + 1
                else: break

            meta = sym_meta.get(sym, {"score": sym_to_score.get(sym, 30),
                                       "lifecycle": "quiet", "reaction": "n/a", "n_waves_14d": 0})
            score = meta["score"]; lc = meta["lifecycle"]; rx = meta["reaction"]; n_w = meta["n_waves_14d"]

            # Determine rule + direction
            if n_w < 3:
                rule_id = "A"; trade_side = None
            elif rx == "trend_continue" and 3 <= wave_dur <= 20:
                rule_id = "B"; trade_side = "long" if ret > 0 else "short"  # follow
            elif rx == "mean_revert" and lc in ("sustained", "single_burst"):
                rule_id = "C"; trade_side = "short" if ret > 0 else "long"  # fade
            elif score >= 80 and pre_vol < 2.5:
                rule_id = "D"; trade_side = "short" if ret > 0 else "long"
            elif 3 <= wave_dur <= 6:
                rule_id = "E"; trade_side = None
            elif pre_vol >= 7.0:
                rule_id = "F"; trade_side = "long" if ret > 0 else "short"
            else:
                rule_id = "G"; trade_side = "short" if ret > 0 else "long"

            pos_pct, lev = layered_sizing(score, rule_id)
            sizing_dist[(pos_pct, lev)] += 1

            if pos_pct == 0 or trade_side is None:
                last_ev = rows[k][0]; continue

            # Replay with baseline exit
            start = max(0, entry_idx - 35); end = min(len(rows), entry_idx + 365)
            bars = [Bar(*r) for r in rows[start:end]]
            pre_entry = [b for b in bars if b.ts_ms < rows[entry_idx][0]]
            atr = compute_atr_pct(pre_entry, 14, entry_px) if pre_entry else 0
            pos = Position(entry_ts_ms=int(rows[entry_idx][0]), entry_px=float(entry_px),
                           side=trade_side, hold_minutes_limit=HOLD_MIN_LIMIT, atr_at_entry=atr)
            eng = ExitEngine(ExitConfig())
            eidx = next((j for j, b in enumerate(bars) if b.ts_ms >= rows[entry_idx][0]), None)
            if eidx is None:
                last_ev = rows[k][0]; continue
            raw_pnl = None
            for j in range(eidx, len(bars)):
                d = eng.decide(pos, bars[:j+1])
                if d:
                    raw_pnl = d.pnl_pct; break
            if raw_pnl is None:
                last = bars[-1]
                raw_pnl = ((last.close - entry_px)/entry_px*100 if trade_side == "long"
                           else (entry_px - last.close)/entry_px*100)

            # Apply leverage + fees
            liq_thresh = LIQUIDATION_THRESHOLD_RAW.get(lev, -100.0)
            if raw_pnl <= liq_thresh:
                n_liq += 1
                cap_pnl = -pos_pct
            else:
                cap_pnl = raw_pnl * pos_pct / 100 * lev
            fee_pct = pos_pct * lev * ROUND_TRIP_BPS_SPICY / 10000
            cap_pnl -= fee_pct
            cap_pnls.append(cap_pnl)
            last_ev = rows[k][0]

    metrics = compute_metrics(cap_pnls, n_liq)
    print(f"\n  Sizing distribution:")
    for (p, l), c in sorted(sizing_dist.items()):
        eff = p * l
        print(f"    {p}% × {l}x = {eff}% effective: {c}")
    print(f"\n  Aggregate metrics:")
    print(f"    n={metrics['n']}, total_cap={metrics['total_cap']:+.2f}%")
    print(f"    mean_cap={metrics['mean_cap']:+.4f}%, win={metrics['win_rate']:.1f}%")
    print(f"    max_DD_capital={metrics['max_dd_capital']:.2f}%, sharpe={metrics['sharpe']:.2f}")
    print(f"    liquidations: {n_liq}")
    print(f"    best={metrics['best']:+.2f}%, worst={metrics['worst']:+.2f}%")

    return metrics, dict(sizing_dist)


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

    paper_metrics, paper_sizing = simulate_paper(con, paper, sym_meta, sym_to_score)
    broader_metrics, broader_sizing = simulate_broader(con, sym_meta, sym_to_score)

    print("\n" + "=" * 100)
    print("DD THRESHOLD RECOMMENDATION (data-driven)")
    print("=" * 100)
    paper_dd = paper_metrics["max_dd_capital"]
    broader_dd = broader_metrics["max_dd_capital"]
    print(f"  PAPER max_DD: {paper_dd:.2f}%")
    print(f"  Broader max_DD: {broader_dd:.2f}%")
    max_observed = max(paper_dd, broader_dd)
    print(f"  Max observed: {max_observed:.2f}%")
    rec = max_observed * 1.5
    print(f"  → Recommended DD threshold: {rec:.0f}% (1.5× headroom over observed max)")
    print(f"     - Conservative: {max_observed:.0f}% (= observed, may false-fail)")
    print(f"     - Recommended: {rec:.0f}% (1.5× headroom)")
    print(f"     - Permissive: {max_observed * 2:.0f}% (2× headroom)")

    OUT.write_text(json.dumps({
        "paper": paper_metrics,
        "paper_sizing_dist": {f"{p}x{l}": c for (p, l), c in paper_sizing.items()},
        "broader": broader_metrics,
        "broader_sizing_dist": {f"{p}x{l}": c for (p, l), c in broader_sizing.items()},
        "dd_threshold_recommendation": {
            "max_observed": max_observed,
            "conservative": max_observed,
            "recommended_1_5x": rec,
            "permissive_2x": max_observed * 2,
        }
    }, indent=2, default=str))
    print(f"\n  saved: {OUT}")
    con.close()


if __name__ == "__main__":
    main()
