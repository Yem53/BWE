"""3-layer PnL comparison on the SAME 80 Hermes live + 180 paper trades.

Layer 1 (原始 buggy logic):    journal-recorded raw 1x PnL (pre-exit_v2)
Layer 2 (exit_v2 only):        re-replay trades with exit_v2 baseline
Layer 3 (rule engine + exit_v2): Layer 2 BUT if rule engine says SKIP, trade=0

This isolates each layer's contribution apples-to-apples.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "exit_v2"))
from exit_v2 import Bar, ExitConfig, ExitEngine, Position, compute_atr_pct

LIVE = Path("/Users/ye/.hermes/research/bwe_live_autotrader_binance_expectancy_runtime/trade_journal.jsonl")
PAPER = Path("/Users/ye/.hermes/research/bwe_paper_multilot_observer_runtime/trade_journal.jsonl")
KLINE_DB = "/Users/ye/.hermes/research/binance_extended_history.sqlite3"
SCORE_PATH = Path("/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits/yaobi_score_v0.json")
DIVE_PATH = Path("/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits/yaobi_per_symbol_dive.json")


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
        raw = (xp-ep)/ep*100 if side=="long" else (ep-xp)/ep*100
        out.append({
            "trade_id": tid, "symbol": t["symbol"],
            "market_symbol": t["market_symbol"],
            "strategy": t["strategy_name"], "side": side,
            "entry_ts_ms": int(t.get("entry_ts", t["ts"])*1000),
            "entry_px": ep,
            "raw_pnl_layer1": raw,  # Layer 1: original buggy logic
            "hold_minutes_limit": float(t.get("hold_minutes_limit", 60)),
        })
    return out


def replay_v2(trade, con, exit_config):
    entry_ts = trade["entry_ts_ms"]
    end_ts = entry_ts + int((trade["hold_minutes_limit"]+5)*60_000)
    pre_ts = entry_ts - 30*60_000
    cur = con.execute(
        "SELECT open_time_ms, open, high, low, close, volume FROM klines_1m "
        "WHERE symbol=? AND open_time_ms BETWEEN ? AND ? ORDER BY open_time_ms",
        (trade["market_symbol"], pre_ts, end_ts))
    bars = [Bar(*r) for r in cur.fetchall()]
    if not bars: return trade["raw_pnl_layer1"]
    eidx = next((i for i,b in enumerate(bars) if b.ts_ms >= entry_ts), None)
    if eidx is None: return trade["raw_pnl_layer1"]
    pre = bars[:eidx]
    atr = compute_atr_pct(pre, period=14, ref_px=trade["entry_px"]) if pre else 0
    pos = Position(entry_ts_ms=entry_ts, entry_px=trade["entry_px"],
                   side=trade["side"],
                   hold_minutes_limit=trade["hold_minutes_limit"],
                   atr_at_entry=atr)
    eng = ExitEngine(exit_config)
    for i in range(eidx, len(bars)):
        d = eng.decide(pos, bars[:i+1])
        if d: return d.pnl_pct
    last = bars[-1]
    return ((last.close-pos.entry_px)/pos.entry_px*100 if pos.side=="long"
            else (pos.entry_px-last.close)/pos.entry_px*100)


def compute_wave_features(trade, con):
    """Extract pre-event 5min vol ratio + recent wave duration at entry."""
    entry_ts = trade["entry_ts_ms"]
    pre_ts = entry_ts - 60*60_000  # 60 min before
    cur = con.execute(
        "SELECT open_time_ms, open, high, low, close, volume FROM klines_1m "
        "WHERE symbol=? AND open_time_ms BETWEEN ? AND ? ORDER BY open_time_ms",
        (trade["market_symbol"], pre_ts, entry_ts))
    rows = cur.fetchall()
    if len(rows) < 35:
        return {"pre_vol": 0, "duration": 0, "magnitude": 0}
    # Pre-vol: last 5 vs prior 30
    recent = rows[-5:]
    base = rows[-35:-5]
    rv = sum(r[5] for r in recent)/len(recent)
    bv = sum(r[5] for r in base)/len(base)
    pre_vol = rv/bv if bv>0 else 0
    # Find wave duration: count how many recent bars had 5min ret >= 5%
    wave_dur = 0
    for i in range(len(rows)-1, max(0, len(rows)-15), -1):
        if i < 5: break
        ret = abs((rows[i][4] - rows[i-5][4]) / rows[i-5][4] * 100) if rows[i-5][4]>0 else 0
        if ret >= 5: wave_dur = (rows[-1][0] - rows[i][0])/60_000 + 1
        else: break
    # Magnitude: max abs 5min ret in last 30 min
    mag = 0
    for i in range(5, len(rows[-30:])):
        idx = len(rows) - 30 + i
        ret = abs((rows[idx][4] - rows[idx-5][4]) / rows[idx-5][4] * 100) if rows[idx-5][4]>0 else 0
        mag = max(mag, ret)
    return {"pre_vol": pre_vol, "duration": int(wave_dur), "magnitude": mag}


def apply_rules(symbol_meta, wave_features):
    """Rule engine v1 (F=FOLLOW). Returns (action, position_pct)."""
    n_waves = symbol_meta.get("n_waves_14d", 0)
    lifecycle = symbol_meta.get("lifecycle", "quiet")
    reaction = symbol_meta.get("reaction", "n/a")
    score = symbol_meta.get("score", 0)
    duration = wave_features["duration"]
    pre_vol = wave_features["pre_vol"]

    if n_waves < 3:
        return ("SKIP", 0, "A")
    if reaction == "trend_continue" and 3 <= duration <= 20:
        return ("FOLLOW", 5, "B")
    if reaction == "mean_revert" and lifecycle in ("sustained", "single_burst"):
        return ("FADE", 8, "C")
    if score >= 80 and pre_vol < 2.5:
        return ("FADE", 8, "D")
    if 3 <= duration <= 6:
        return ("SKIP", 0, "E")
    if pre_vol >= 7.0:
        return ("FOLLOW", 5, "F")
    return ("FADE", 5, "G")


def infer_bwe_thesis(strategy):
    """Infer if BWE strategy implicitly is FADE (反向) or FOLLOW (顺向)."""
    s = strategy.lower()
    if "_cont_" in s or "cont_long" in s:
        return "FOLLOW"
    return "FADE"  # crash_bounce / overcrowded / unwind / etc all fade


def aggregate(label, pnls):
    n = len(pnls)
    n_zero = sum(1 for p in pnls if p == 0)
    nonzero = [p for p in pnls if p != 0]
    if not nonzero:
        return {"label": label, "n_total": n, "n_traded": 0,
                "total_raw": 0, "win_rate": 0, "mean_per_trade": 0}
    wins = sum(1 for p in nonzero if p > 0)
    return {
        "label": label, "n_total": n, "n_traded": len(nonzero),
        "n_skip": n_zero,
        "trade_rate": len(nonzero)/n*100,
        "total_raw": sum(nonzero),
        "win_rate": wins/len(nonzero)*100,
        "mean_per_trade_raw": sum(nonzero)/len(nonzero),
        "best": max(nonzero), "worst": min(nonzero),
        "big_wins_10pct": sum(1 for p in nonzero if p>=10),
        "catastrophes_15pct": sum(1 for p in nonzero if p<=-15),
    }


def main():
    print("Loading data...")
    score_data = json.loads(SCORE_PATH.read_text())
    sym_to_score = {m["symbol"]: m["yaobi_score"] for m in score_data["ranked"]}
    dive_data = json.loads(DIVE_PATH.read_text())
    sym_meta = {}
    for r in dive_data["results"]:
        sym_meta[r["symbol"]] = {
            "score": r["score"],
            "lifecycle": r["lifecycle"],
            "reaction": r["reaction"],
            "n_waves_14d": r["n_waves"],
        }

    con = sqlite3.connect(KLINE_DB)
    live = load_closed(LIVE)
    paper = load_closed(PAPER)
    print(f"LIVE: {len(live)} closed, PAPER: {len(paper)} closed")

    # Per-thesis configs
    fade_cfg = ExitConfig()  # baseline
    follow_cfg = ExitConfig(
        trail_tiers=((5, 6), (10, 12), (25, 20), (50, 30), (100, 40)),
        tradoor_saver_hw_threshold=15.0,
        tradoor_saver_max_hw_age_min=20.0,
    )

    for label, trades in [("LIVE", live), ("PAPER", paper)]:
        print(f"\n{'='*100}")
        print(f"{label} sample (n={len(trades)})")
        print('='*100)

        layer1 = []  # original buggy
        layer2 = []  # exit_v2 only
        layer3 = []  # rule engine + exit_v2 (simplified: SKIP if rule SKIP, else baseline exit)
        layer4 = []  # full: rule engine + per-thesis exit + direction conflict skip

        rule_breakdown = {}
        for t in trades:
            sym = t["market_symbol"]
            # Layer 1
            l1 = t["raw_pnl_layer1"]
            layer1.append(l1)

            # Layer 2: exit_v2 baseline
            l2 = replay_v2(t, con, fade_cfg)
            layer2.append(l2)

            # Layer 3 + 4: need features
            sm = sym_meta.get(sym, {"score": sym_to_score.get(sym, 30),
                                     "lifecycle": "quiet", "reaction": "n/a",
                                     "n_waves_14d": 0})
            wf = compute_wave_features(t, con)
            action, pct, rid = apply_rules(sm, wf)
            rule_breakdown[rid] = rule_breakdown.get(rid, 0) + 1

            if action == "SKIP":
                layer3.append(0)
                layer4.append(0)
            else:
                # Layer 3: just use baseline exit
                layer3.append(l2)
                # Layer 4: per-thesis exit + check direction
                bwe_thesis = infer_bwe_thesis(t["strategy"])
                if action != bwe_thesis:
                    # Direction conflict: skip (rule engine override)
                    layer4.append(0)
                else:
                    cfg = follow_cfg if action == "FOLLOW" else fade_cfg
                    l4 = replay_v2(t, con, cfg)
                    layer4.append(l4)

        for layer, name in [(layer1, "Layer 1 — 原始 buggy logic"),
                             (layer2, "Layer 2 — exit_v2 only"),
                             (layer3, "Layer 3 — exit_v2 + rule SKIP filter"),
                             (layer4, "Layer 4 — full (per-thesis + dir-check)")]:
            agg = aggregate(name, layer)
            print(f"\n  {agg['label']}:")
            print(f"    n={agg['n_total']:>3d}  traded={agg['n_traded']:>3d} "
                  f"({agg.get('trade_rate', 100):.0f}%)  "
                  f"total_raw={agg['total_raw']:>+8.1f}%  "
                  f"win={agg['win_rate']:>5.1f}%  "
                  f"mean/trade={agg['mean_per_trade_raw']:>+5.2f}%  "
                  f"big_w={agg.get('big_wins_10pct',0):>2d} cat={agg.get('catastrophes_15pct',0):>2d}")

        print(f"\n  Rule trigger distribution:")
        for rid in "ABCDEFG":
            cnt = rule_breakdown.get(rid, 0)
            if cnt:
                print(f"    Rule {rid}: {cnt}")

    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
