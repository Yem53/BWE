"""4-layer PnL comparison with NEW Layer 3.5 design.

Layer 3.5 design (after 30d data analysis):
  - Rule A:  n_waves < 3                   → SKIP (insufficient history)
  - Rule B:  reaction=trend_continue + dur 3-20 → ENTER (5% pos), use exit_v2 baseline
  - Rule C:  reaction=mean_revert + lifecycle in (sustained, single_burst) → ENTER 8% (high conf)
  - Rule D:  score>=80 + pre_vol<2.5     → ENTER 8% (high conf)
  - Rule E:  RELAXED — only SKIP if duration EXACTLY 4 (was 3-6 in L3)
  - Rule F:  pre_vol>=7x                  → SKIP (simplest, data shows F variants <1%)
  - Default: ENTER 5%

Critical L3.5 design choices (vs L4 which underperformed):
  ✗ NO direction-check (BWE direction is ground truth)
  ✗ NO per-thesis exit config (always use exit_v2 baseline)
  ✓ Variable position size (5% / 8%) based on rule confidence
  ✓ Skip rules ONLY for clear data-supported reasons (insufficient history, dead-zone, high-prevol)
"""
from __future__ import annotations

import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "exit_v2"))
from exit_v2 import Bar, ExitConfig, ExitEngine, Position, compute_atr_pct

LIVE = Path("/Users/ye/.hermes/research/bwe_live_autotrader_binance_expectancy_runtime/trade_journal.jsonl")
PAPER = Path("/Users/ye/.hermes/research/bwe_paper_multilot_observer_runtime/trade_journal.jsonl")
KLINE_DB = "/Users/ye/.hermes/research/binance_extended_history.sqlite3"
SCORE_PATH = Path("/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits/yaobi_score_v1_30d.json")
DIVE_PATH = Path("/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits/yaobi_per_symbol_dive_v1_30d.json")
OUT_PATH = Path("/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits/three_layer_v3_l35.json")


def load_closed(path: Path):
    by_id = {}
    for line in path.open():
        j = json.loads(line)
        tid = j.get("trade_id")
        if not tid:
            continue
        if j["action"] == "entry":
            by_id[tid] = {**j, "exits": []}
        elif j["action"] in ("exit", "partial_exit") and tid in by_id:
            by_id[tid]["exits"].append(j)
    out = []
    for tid, t in by_id.items():
        if not t.get("exits"):
            continue
        final = t["exits"][-1]
        ep = float(t.get("entry_px") or t.get("fill_price") or 0)
        xp = float(final.get("fill_price") or final.get("exit_px") or 0)
        if ep == 0:
            continue
        side = t["side"]
        raw = (xp - ep) / ep * 100 if side == "long" else (ep - xp) / ep * 100
        out.append({
            "trade_id": tid, "symbol": t["symbol"],
            "market_symbol": t["market_symbol"],
            "strategy": t["strategy_name"], "side": side,
            "entry_ts_ms": int(t.get("entry_ts", t["ts"]) * 1000),
            "entry_px": ep,
            "raw_pnl_layer1": raw,
            "hold_minutes_limit": float(t.get("hold_minutes_limit", 60)),
        })
    return out


def replay_v2(trade, con, exit_config):
    entry_ts = trade["entry_ts_ms"]
    end_ts = entry_ts + int((trade["hold_minutes_limit"] + 5) * 60_000)
    pre_ts = entry_ts - 30 * 60_000
    cur = con.execute(
        "SELECT open_time_ms, open, high, low, close, volume FROM klines_1m "
        "WHERE symbol=? AND open_time_ms BETWEEN ? AND ? ORDER BY open_time_ms",
        (trade["market_symbol"], pre_ts, end_ts))
    bars = [Bar(*r) for r in cur.fetchall()]
    if not bars:
        return trade["raw_pnl_layer1"]
    eidx = next((i for i, b in enumerate(bars) if b.ts_ms >= entry_ts), None)
    if eidx is None:
        return trade["raw_pnl_layer1"]
    pre = bars[:eidx]
    atr = compute_atr_pct(pre, period=14, ref_px=trade["entry_px"]) if pre else 0
    pos = Position(entry_ts_ms=entry_ts, entry_px=trade["entry_px"], side=trade["side"],
                   hold_minutes_limit=trade["hold_minutes_limit"], atr_at_entry=atr)
    eng = ExitEngine(exit_config)
    for i in range(eidx, len(bars)):
        d = eng.decide(pos, bars[: i + 1])
        if d:
            return d.pnl_pct
    last = bars[-1]
    return ((last.close - pos.entry_px) / pos.entry_px * 100 if pos.side == "long"
            else (pos.entry_px - last.close) / pos.entry_px * 100)


def compute_wave_features(trade, con):
    entry_ts = trade["entry_ts_ms"]
    pre_ts = entry_ts - 60 * 60_000
    cur = con.execute(
        "SELECT open_time_ms, open, high, low, close, volume FROM klines_1m "
        "WHERE symbol=? AND open_time_ms BETWEEN ? AND ? ORDER BY open_time_ms",
        (trade["market_symbol"], pre_ts, entry_ts))
    rows = cur.fetchall()
    if len(rows) < 35:
        return {"pre_vol": 0, "duration": 0, "magnitude": 0}
    recent = rows[-5:]
    base = rows[-35:-5]
    rv = sum(r[5] for r in recent) / len(recent)
    bv = sum(r[5] for r in base) / len(base)
    pre_vol = rv / bv if bv > 0 else 0
    wave_dur = 0
    for i in range(len(rows) - 1, max(0, len(rows) - 15), -1):
        if i < 5:
            break
        ret = abs((rows[i][4] - rows[i - 5][4]) / rows[i - 5][4] * 100) if rows[i - 5][4] > 0 else 0
        if ret >= 5:
            wave_dur = (rows[-1][0] - rows[i][0]) / 60_000 + 1
        else:
            break
    return {"pre_vol": pre_vol, "duration": int(wave_dur), "magnitude": 0}


def apply_rules_l3(symbol_meta, wave_features):
    """OLD L3 rules (for comparison)"""
    n_waves = symbol_meta.get("n_waves_14d", 0)
    lifecycle = symbol_meta.get("lifecycle", "quiet")
    reaction = symbol_meta.get("reaction", "n/a")
    score = symbol_meta.get("score", 0)
    duration = wave_features["duration"]
    pre_vol = wave_features["pre_vol"]
    if n_waves < 3:
        return ("SKIP", 0, "A")
    if reaction == "trend_continue" and 3 <= duration <= 20:
        return ("ENTER", 5, "B")
    if reaction == "mean_revert" and lifecycle in ("sustained", "single_burst"):
        return ("ENTER", 8, "C")
    if score >= 80 and pre_vol < 2.5:
        return ("ENTER", 8, "D")
    if 3 <= duration <= 6:
        return ("SKIP", 0, "E")
    if pre_vol >= 7.0:
        return ("ENTER", 5, "F-FOLLOW")
    return ("ENTER", 5, "G")


def apply_rules_l35(symbol_meta, wave_features):
    """L3.5 — relaxed E, F=SKIP, variable position 5/8%"""
    n_waves = symbol_meta.get("n_waves_14d", 0)
    lifecycle = symbol_meta.get("lifecycle", "quiet")
    reaction = symbol_meta.get("reaction", "n/a")
    score = symbol_meta.get("score", 0)
    duration = wave_features["duration"]
    pre_vol = wave_features["pre_vol"]
    if n_waves < 3:
        return ("SKIP", 0, "A")
    if reaction == "trend_continue" and 3 <= duration <= 20:
        return ("ENTER", 5, "B")
    if reaction == "mean_revert" and lifecycle in ("sustained", "single_burst"):
        return ("ENTER", 8, "C")
    if score >= 80 and pre_vol < 2.5:
        return ("ENTER", 8, "D")
    if duration == 4:  # RELAXED: only worst single
        return ("SKIP", 0, "E")
    if pre_vol >= 7.0:
        return ("SKIP", 0, "F")
    return ("ENTER", 5, "G")


def apply_rules_l35b(symbol_meta, wave_features):
    """L3.5b — KEEP strict E (3-6), F=SKIP, variable position 5/8% — isolates position-sizing alpha"""
    n_waves = symbol_meta.get("n_waves_14d", 0)
    lifecycle = symbol_meta.get("lifecycle", "quiet")
    reaction = symbol_meta.get("reaction", "n/a")
    score = symbol_meta.get("score", 0)
    duration = wave_features["duration"]
    pre_vol = wave_features["pre_vol"]
    if n_waves < 3:
        return ("SKIP", 0, "A")
    if reaction == "trend_continue" and 3 <= duration <= 20:
        return ("ENTER", 5, "B")
    if reaction == "mean_revert" and lifecycle in ("sustained", "single_burst"):
        return ("ENTER", 8, "C")
    if score >= 80 and pre_vol < 2.5:
        return ("ENTER", 8, "D")
    if 3 <= duration <= 6:  # KEEP strict E
        return ("SKIP", 0, "E")
    if pre_vol >= 7.0:
        return ("SKIP", 0, "F")
    return ("ENTER", 5, "G")


def aggregate(label, pnls_raw, pnls_cap=None):
    n = len(pnls_raw)
    n_zero = sum(1 for p in pnls_raw if p == 0)
    nonzero_idx = [i for i, p in enumerate(pnls_raw) if p != 0]
    nonzero_raw = [pnls_raw[i] for i in nonzero_idx]
    nonzero_cap = [pnls_cap[i] for i in nonzero_idx] if pnls_cap else nonzero_raw
    if not nonzero_raw:
        return {"label": label, "n_total": n, "n_traded": 0, "total_raw": 0, "total_cap": 0,
                "win_rate": 0, "mean_raw": 0, "mean_cap": 0}
    wins = sum(1 for p in nonzero_raw if p > 0)
    return {
        "label": label, "n_total": n, "n_traded": len(nonzero_raw),
        "n_skip": n_zero,
        "trade_rate": len(nonzero_raw) / n * 100,
        "total_raw": sum(nonzero_raw),
        "total_cap": sum(nonzero_cap),
        "win_rate": wins / len(nonzero_raw) * 100,
        "mean_raw": sum(nonzero_raw) / len(nonzero_raw),
        "mean_cap": sum(nonzero_cap) / len(nonzero_raw),
        "best": max(nonzero_raw), "worst": min(nonzero_raw),
        "big_wins_10pct": sum(1 for p in nonzero_raw if p >= 10),
        "catastrophes_15pct": sum(1 for p in nonzero_raw if p <= -15),
    }


def main():
    print("Loading data...")
    score_data = json.loads(SCORE_PATH.read_text())
    sym_to_score = {m["symbol"]: m["yaobi_score"] for m in score_data["ranked"]}
    dive_data = json.loads(DIVE_PATH.read_text())
    sym_meta = {}
    for r in dive_data["results"]:
        sym_meta[r["symbol"]] = {
            "score": r["score"], "lifecycle": r["lifecycle"],
            "reaction": r["reaction"], "n_waves_14d": r["n_waves"],
        }

    con = sqlite3.connect(KLINE_DB)
    live = load_closed(LIVE)
    paper = load_closed(PAPER)
    print(f"LIVE: {len(live)} closed, PAPER: {len(paper)} closed")

    fade_cfg = ExitConfig()  # baseline

    for label, trades in [("LIVE", live), ("PAPER", paper)]:
        print(f"\n{'=' * 100}")
        print(f"{label} sample (n={len(trades)})")
        print('=' * 100)

        layer1_raw, layer1_cap = [], []
        layer2_raw, layer2_cap = [], []
        layer3_raw, layer3_cap = [], []
        layer35_raw, layer35_cap = [], []
        layer35b_raw, layer35b_cap = [], []
        rule_breakdown_l3 = Counter()
        rule_breakdown_l35 = Counter()
        rule_breakdown_l35b = Counter()

        for t in trades:
            sym = t["market_symbol"]
            l1 = t["raw_pnl_layer1"]
            layer1_raw.append(l1)
            layer1_cap.append(l1 * 0.05)  # uniform 5%

            l2 = replay_v2(t, con, fade_cfg)
            layer2_raw.append(l2)
            layer2_cap.append(l2 * 0.05)

            sm = sym_meta.get(sym, {"score": sym_to_score.get(sym, 30),
                                     "lifecycle": "quiet", "reaction": "n/a", "n_waves_14d": 0})
            wf = compute_wave_features(t, con)

            # L3 (old)
            l3_action, l3_pct, l3_rid = apply_rules_l3(sm, wf)
            rule_breakdown_l3[l3_rid] += 1
            if l3_action == "SKIP":
                layer3_raw.append(0); layer3_cap.append(0)
            else:
                layer3_raw.append(l2)
                layer3_cap.append(l2 * 0.05)  # L3 uniform 5%

            # L3.5 (relaxed E + var pos)
            l35_action, l35_pct, l35_rid = apply_rules_l35(sm, wf)
            rule_breakdown_l35[l35_rid] += 1
            if l35_action == "SKIP":
                layer35_raw.append(0); layer35_cap.append(0)
            else:
                layer35_raw.append(l2)
                layer35_cap.append(l2 * l35_pct / 100)

            # L3.5b (strict E + var pos — isolates position-sizing alpha)
            l35b_action, l35b_pct, l35b_rid = apply_rules_l35b(sm, wf)
            rule_breakdown_l35b[l35b_rid] += 1
            if l35b_action == "SKIP":
                layer35b_raw.append(0); layer35b_cap.append(0)
            else:
                layer35b_raw.append(l2)
                layer35b_cap.append(l2 * l35b_pct / 100)

        # Print results
        print(f"\n  {'Layer':50s} {'n_trade':>8s} {'total_raw':>10s} {'total_cap':>10s} "
              f"{'win%':>6s} {'mean_raw':>9s} {'mean_cap':>9s} {'big_w':>6s} {'cat':>4s}")
        for layer_label, raws, caps in [
            ("L1 — 原始 buggy logic", layer1_raw, layer1_cap),
            ("L2 — exit_v2 only (5% pos)", layer2_raw, layer2_cap),
            ("L3 — exit_v2 + rule SKIP (5% pos)", layer3_raw, layer3_cap),
            ("L3.5 — relaxed E + var pos (5/8%)", layer35_raw, layer35_cap),
            ("L3.5b — strict E + var pos (5/8%) ⭐️", layer35b_raw, layer35b_cap),
        ]:
            agg = aggregate(layer_label, raws, caps)
            print(f"  {agg['label']:50s} {agg['n_traded']:>8d} "
                  f"{agg['total_raw']:>+9.1f}% {agg['total_cap']:>+9.2f}% "
                  f"{agg['win_rate']:>5.1f}% {agg['mean_raw']:>+8.2f}% "
                  f"{agg['mean_cap']:>+8.3f}% "
                  f"{agg.get('big_wins_10pct', 0):>6d} "
                  f"{agg.get('catastrophes_15pct', 0):>4d}")

        # Rule breakdown for L3 and L3.5 side-by-side
        print(f"\n  Rule trigger comparison (L3 vs L3.5):")
        print(f"    {'rule':10s} {'L3 count':>10s} {'L3.5 count':>12s} {'delta':>8s}")
        all_rules = sorted(set(rule_breakdown_l3.keys()) | set(rule_breakdown_l35.keys()))
        for r in all_rules:
            c3 = rule_breakdown_l3.get(r, 0)
            c35 = rule_breakdown_l35.get(r, 0)
            delta = c35 - c3
            print(f"    {r:10s} {c3:>10d} {c35:>12d} {delta:>+8d}")

        # Save
        if label == "LIVE":
            agg_l35 = aggregate("L3.5", layer35_raw, layer35_cap)
            agg_l3 = aggregate("L3", layer3_raw, layer3_cap)
            agg_l2 = aggregate("L2", layer2_raw, layer2_cap)
            with open(OUT_PATH, "w") as f:
                json.dump({"LIVE": {"L2": agg_l2, "L3": agg_l3, "L3.5": agg_l35,
                                     "rule_breakdown_l35": dict(rule_breakdown_l35)}},
                          f, indent=2, default=str)

    con.close()
    print(f"\n  saved: {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
