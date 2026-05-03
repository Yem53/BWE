"""Optimization tests — squeeze more alpha from L2/L3.5b (BWE) and L4 (broader).

BWE optimizations (run on Hermes 82+210 trades):
  - L2-base:           ExitConfig() default
  - L2-wide-trail:     wider trail tiers for high-score coins (sustained type)
  - L2-tight-trail:    tighter trail for spike_decay coins (decay fast → lock fast)
  - L2-per-lifecycle:  combine wide/tight based on per-symbol lifecycle
  - L3.5b-tier-pos:    L3.5b but with 3% / 5% / 8% / 12% pos tiers (not just 5/8)

Broader market optimizations (run on 1425 events):
  - L4-base:           current L4 (rule + var pos 5/8 + exit_v2 baseline)
  - L4-wider-follow:   B/F follow trades use wider G2 trail config
  - L4-12pct-D:        D rule (highest-confidence) bumps to 12% pos
  - L4-continuous-pos: position pct = score-weighted (linear from 5% at score 50 to 12% at score 90)
  - L4-tier-pos:       3 (B follow weak), 5 (G), 8 (C/D), 12 (D high-score) pos
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "exit_v2"))
from exit_v2 import Bar, ExitConfig, ExitEngine, Position, compute_atr_pct

LIVE = Path("/Users/ye/.hermes/research/bwe_live_autotrader_binance_expectancy_runtime/trade_journal.jsonl")
PAPER = Path("/Users/ye/.hermes/research/bwe_paper_multilot_observer_runtime/trade_journal.jsonl")
KLINE_DB = "/Users/ye/.hermes/research/binance_extended_history.sqlite3"
SCORE_PATH = Path("/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits/yaobi_score_v1_30d.json")
DIVE_PATH = Path("/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits/yaobi_per_symbol_dive_v1_30d.json")

EVENT_PCT = 8.0
HOLD_MIN_LIMIT = 360.0
MIN_PRE_BARS = 35


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
            "trade_id": tid, "symbol": t["symbol"],
            "market_symbol": t["market_symbol"], "strategy": t["strategy_name"],
            "side": side, "entry_ts_ms": int(t.get("entry_ts", t["ts"]) * 1000),
            "entry_px": ep, "raw_pnl_layer1": raw,
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
    if not bars: return trade["raw_pnl_layer1"]
    eidx = next((i for i, b in enumerate(bars) if b.ts_ms >= entry_ts), None)
    if eidx is None: return trade["raw_pnl_layer1"]
    pre = bars[:eidx]
    atr = compute_atr_pct(pre, period=14, ref_px=trade["entry_px"]) if pre else 0
    pos = Position(entry_ts_ms=entry_ts, entry_px=trade["entry_px"], side=trade["side"],
                   hold_minutes_limit=trade["hold_minutes_limit"], atr_at_entry=atr)
    eng = ExitEngine(exit_config)
    for i in range(eidx, len(bars)):
        d = eng.decide(pos, bars[: i + 1])
        if d: return d.pnl_pct
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
    if len(rows) < 35: return {"pre_vol": 0, "duration": 0}
    pre5 = rows[-5:]; base = rows[-35:-5]
    rv = sum(r[5] for r in pre5)/len(pre5); bv = sum(r[5] for r in base)/len(base)
    pre_vol = rv/bv if bv > 0 else 0
    wave_dur = 0
    for i in range(len(rows)-1, max(0, len(rows)-15), -1):
        if i < 5: break
        ret = abs((rows[i][4] - rows[i-5][4]) / rows[i-5][4] * 100) if rows[i-5][4] > 0 else 0
        if ret >= 5: wave_dur = (rows[-1][0] - rows[i][0])/60_000 + 1
        else: break
    return {"pre_vol": pre_vol, "duration": int(wave_dur)}


# Exit config variants
def cfg_base():
    return ExitConfig()

def cfg_wide_trail():
    """Wider trail for sustained / late_burst — let runners run further."""
    return ExitConfig(
        trail_tiers=((5, 5), (10, 10), (25, 18), (50, 28), (100, 40)),
        tradoor_saver_max_hw_age_min=20.0,
    )

def cfg_tight_trail():
    """Tighter trail for spike_decay — lock profits fast."""
    return ExitConfig(
        trail_tiers=((5, 3), (10, 5), (25, 8), (50, 12), (100, 18)),
    )


def per_symbol_cfg_l2(symbol_meta):
    """Lifecycle-aware ExitConfig selection."""
    lc = symbol_meta.get("lifecycle", "quiet")
    if lc in ("sustained", "late_burst"):
        return cfg_wide_trail()
    if lc == "spike_decay":
        return cfg_tight_trail()
    return cfg_base()


def aggregate(label, raws, caps, n_total):
    nz = [r for r in raws if r != 0]
    nzc = [caps[i] for i, r in enumerate(raws) if r != 0]
    if not nz: return {"label": label, "n_traded": 0, "total_raw": 0, "total_cap": 0,
                       "win_rate": 0, "mean_raw": 0, "mean_cap": 0}
    wins = sum(1 for r in nz if r > 0)
    return {"label": label, "n_traded": len(nz),
            "total_raw": sum(nz), "total_cap": sum(nzc),
            "win_rate": wins/len(nz)*100,
            "mean_raw": sum(nz)/len(nz), "mean_cap": sum(nzc)/len(nz),
            "big_w": sum(1 for r in nz if r >= 10),
            "cat": sum(1 for r in nz if r <= -15)}


# ============== BWE OPTIMIZATIONS ==============
def run_bwe_optimization():
    print("=" * 130)
    print("BWE OPTIMIZATION — Hermes 82 LIVE + 210 PAPER trades")
    print("=" * 130)

    score_data = json.loads(SCORE_PATH.read_text())
    sym_to_score = {m["symbol"]: m["yaobi_score"] for m in score_data["ranked"]}
    dive_data = json.loads(DIVE_PATH.read_text())
    sym_meta = {r["symbol"]: {"score": r["score"], "lifecycle": r["lifecycle"],
                              "reaction": r["reaction"], "n_waves_14d": r["n_waves"]}
                for r in dive_data["results"]}

    con = sqlite3.connect(KLINE_DB)
    live = load_closed(LIVE); paper = load_closed(PAPER)

    for label, trades in [("LIVE", live), ("PAPER", paper)]:
        print(f"\n--- {label} (n={len(trades)}) ---")
        layers = {
            "L2-base (current)": [],
            "L2-wide-trail": [],
            "L2-tight-trail": [],
            "L2-per-lifecycle": [],
            "L3.5b-tier-pos (3/5/8/12)": [],
        }
        for t in trades:
            sym = t["market_symbol"]
            sm = sym_meta.get(sym, {"score": sym_to_score.get(sym, 30),
                                     "lifecycle": "quiet", "reaction": "n/a",
                                     "n_waves_14d": 0})
            wf = compute_wave_features(t, con)

            # L2 variants
            l2_base = replay_v2(t, con, cfg_base())
            l2_wide = replay_v2(t, con, cfg_wide_trail())
            l2_tight = replay_v2(t, con, cfg_tight_trail())
            l2_per = replay_v2(t, con, per_symbol_cfg_l2(sm))

            layers["L2-base (current)"].append(l2_base)
            layers["L2-wide-trail"].append(l2_wide)
            layers["L2-tight-trail"].append(l2_tight)
            layers["L2-per-lifecycle"].append(l2_per)

            # L3.5b with 4-tier pos sizing
            n_waves = sm["n_waves_14d"]; lc = sm["lifecycle"]; rx = sm["reaction"]; sc = sm["score"]
            dur = wf["duration"]; pv = wf["pre_vol"]
            pos_pct = 0
            if n_waves < 3: pos_pct = 0
            elif rx == "trend_continue" and 3 <= dur <= 20: pos_pct = 5
            elif rx == "mean_revert" and lc in ("sustained", "single_burst"):
                # Tier C: 8 default, 12 if score >= 85 (very high confidence)
                pos_pct = 12 if sc >= 85 else 8
            elif sc >= 80 and pv < 2.5:
                pos_pct = 12 if sc >= 85 else 8
            elif 3 <= dur <= 6: pos_pct = 0
            elif pv >= 7.0: pos_pct = 0
            else: pos_pct = 5  # G default

            # For weak signals (G default with low score), use 3%
            if pos_pct == 5 and sc < 50: pos_pct = 3

            cap = l2_base * pos_pct / 100 if pos_pct > 0 else 0
            layers["L3.5b-tier-pos (3/5/8/12)"].append((l2_base if pos_pct > 0 else 0, cap))

        # Print
        print(f"  {'Layer':35s} {'n_trade':>8s} {'total_raw':>10s} {'total_cap':>10s} "
              f"{'win%':>6s} {'mean_raw':>9s} {'mean_cap':>10s}")
        for layer_name, results in layers.items():
            if isinstance(results[0], tuple):  # L3.5b case (raw, cap)
                raws = [r[0] for r in results]; caps = [r[1] for r in results]
            else:
                raws = results; caps = [r * 0.05 for r in results]
            agg = aggregate(layer_name, raws, caps, len(trades))
            print(f"  {agg['label']:35s} {agg['n_traded']:>8d} "
                  f"{agg['total_raw']:>+9.1f}% {agg['total_cap']:>+9.2f}% "
                  f"{agg['win_rate']:>5.1f}% {agg['mean_raw']:>+8.2f}% "
                  f"{agg['mean_cap']:>+9.3f}%")

    con.close()


# ============== BROADER MARKET OPTIMIZATIONS ==============
def run_broader_optimization():
    print()
    print("=" * 130)
    print("BROADER MARKET OPTIMIZATION — 1425 events")
    print("=" * 130)

    # Use saved market_layers data + enrich with new exit config replays
    # For optimization, we need to re-run replays with new exit configs.
    # Let's just compute new variants using the same event list.

    # Load score + dive
    score_data = json.loads(SCORE_PATH.read_text())
    sym_to_score = {m["symbol"]: m["yaobi_score"] for m in score_data["ranked"]}
    dive_data = json.loads(DIVE_PATH.read_text())
    sym_meta = {r["symbol"]: {"score": r["score"], "lifecycle": r["lifecycle"],
                              "reaction": r["reaction"], "n_waves_14d": r["n_waves"]}
                for r in dive_data["results"]}

    # Re-detect events on the fly (faster than loading from intermediate JSON)
    con = sqlite3.connect(KLINE_DB)
    con.execute("PRAGMA query_only=1")
    syms = sorted([r[0] for r in con.execute("SELECT DISTINCT symbol FROM klines_1m").fetchall()])

    eng_base = ExitEngine(cfg_base())
    eng_wide = ExitEngine(cfg_wide_trail())

    layers = {
        "L4-base (current)": [],
        "L4-wider-follow": [],
        "L4-12pct-D-rule": [],
        "L4-continuous-pos": [],
        "L4-tier-3-5-8-12": [],
    }

    print(f"  Processing 1425 events with multiple exit configs...")
    t0 = time.time()
    n_events = 0
    for i, sym in enumerate(syms):
        if i % 100 == 0: print(f"    {i}/{len(syms)} elapsed={(time.time()-t0)/60:.1f}min")
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
            fade_side = "short" if ret > 0 else "long"
            follow_side = "long" if ret > 0 else "short"

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

            # Replay fade and follow with base + wide configs
            start = max(0, entry_idx - 35); end = min(len(rows), entry_idx + 365)
            bars = [Bar(*r) for r in rows[start:end]]
            pre_entry = [b for b in bars if b.ts_ms < rows[entry_idx][0]]
            atr = compute_atr_pct(pre_entry, 14, entry_px) if pre_entry else 0

            def replay(side, exit_config):
                pos = Position(entry_ts_ms=int(rows[entry_idx][0]), entry_px=float(entry_px),
                               side=side, hold_minutes_limit=HOLD_MIN_LIMIT, atr_at_entry=atr)
                eng = ExitEngine(exit_config)
                eidx = next((j for j, b in enumerate(bars) if b.ts_ms >= rows[entry_idx][0]), None)
                if eidx is None: return None
                for j in range(eidx, len(bars)):
                    d = eng.decide(pos, bars[:j+1])
                    if d: return d.pnl_pct
                last = bars[-1]
                return ((last.close - entry_px)/entry_px*100 if side == "long"
                        else (entry_px - last.close)/entry_px*100)

            fade_v2 = replay(fade_side, cfg_base())
            follow_v2 = replay(follow_side, cfg_base())
            follow_wide = replay(follow_side, cfg_wide_trail())

            if fade_v2 is None or follow_v2 is None: continue
            n_events += 1

            # Apply rules + position sizing variants
            meta = sym_meta.get(sym, {"score": sym_to_score.get(sym, 30),
                                       "lifecycle": "quiet", "reaction": "n/a", "n_waves_14d": 0})
            n_w = meta["n_waves_14d"]; lc = meta["lifecycle"]; rx = meta["reaction"]; sc = meta["score"]

            # L4 base: rule decides direction + var pos 5/8 + baseline exit
            if n_w < 3: l4_base = (0, 0)
            elif rx == "trend_continue" and 3 <= wave_dur <= 20:
                l4_base = (follow_v2, follow_v2 * 0.05)
            elif rx == "mean_revert" and lc in ("sustained", "single_burst"):
                l4_base = (fade_v2, fade_v2 * 0.08)
            elif sc >= 80 and pre_vol < 2.5:
                l4_base = (fade_v2, fade_v2 * 0.08)
            elif 3 <= wave_dur <= 6: l4_base = (0, 0)
            elif pre_vol >= 7.0: l4_base = (follow_v2, follow_v2 * 0.05)
            else: l4_base = (fade_v2, fade_v2 * 0.05)
            layers["L4-base (current)"].append(l4_base)

            # L4-wider-follow: same rules but follow trades use cfg_wide_trail
            if n_w < 3: l4_wf = (0, 0)
            elif rx == "trend_continue" and 3 <= wave_dur <= 20:
                l4_wf = (follow_wide, follow_wide * 0.05)  # wider trail for follow
            elif rx == "mean_revert" and lc in ("sustained", "single_burst"):
                l4_wf = (fade_v2, fade_v2 * 0.08)
            elif sc >= 80 and pre_vol < 2.5:
                l4_wf = (fade_v2, fade_v2 * 0.08)
            elif 3 <= wave_dur <= 6: l4_wf = (0, 0)
            elif pre_vol >= 7.0: l4_wf = (follow_wide, follow_wide * 0.05)
            else: l4_wf = (fade_v2, fade_v2 * 0.05)
            layers["L4-wider-follow"].append(l4_wf)

            # L4-12pct-D: D rule bumps to 12% pos
            if n_w < 3: l4_12 = (0, 0)
            elif rx == "trend_continue" and 3 <= wave_dur <= 20:
                l4_12 = (follow_v2, follow_v2 * 0.05)
            elif rx == "mean_revert" and lc in ("sustained", "single_burst"):
                l4_12 = (fade_v2, fade_v2 * 0.08)
            elif sc >= 80 and pre_vol < 2.5:
                l4_12 = (fade_v2, fade_v2 * 0.12)  # bumped
            elif 3 <= wave_dur <= 6: l4_12 = (0, 0)
            elif pre_vol >= 7.0: l4_12 = (follow_v2, follow_v2 * 0.05)
            else: l4_12 = (fade_v2, fade_v2 * 0.05)
            layers["L4-12pct-D-rule"].append(l4_12)

            # L4-continuous-pos: linear from 5% (sc=50) to 12% (sc=90)
            cont_pct = max(3, min(12, 5 + (sc - 50) * 0.175))  # 50→5, 90→12, capped at 3-12
            if n_w < 3: l4_cont = (0, 0)
            elif 3 <= wave_dur <= 6: l4_cont = (0, 0)
            elif rx == "trend_continue" and 3 <= wave_dur <= 20:
                l4_cont = (follow_v2, follow_v2 * cont_pct / 100)
            elif pre_vol >= 7.0: l4_cont = (follow_v2, follow_v2 * cont_pct / 100)
            else: l4_cont = (fade_v2, fade_v2 * cont_pct / 100)
            layers["L4-continuous-pos"].append(l4_cont)

            # L4-tier-3-5-8-12: bucketed
            if n_w < 3: l4_tier = (0, 0)
            elif rx == "trend_continue" and 3 <= wave_dur <= 20:
                l4_tier = (follow_v2, follow_v2 * 0.05)  # weak follow → 5%
            elif rx == "mean_revert" and lc in ("sustained", "single_burst"):
                pct = 12 if sc >= 85 else 8
                l4_tier = (fade_v2, fade_v2 * pct / 100)
            elif sc >= 80 and pre_vol < 2.5:
                pct = 12 if sc >= 85 else 8
                l4_tier = (fade_v2, fade_v2 * pct / 100)
            elif 3 <= wave_dur <= 6: l4_tier = (0, 0)
            elif pre_vol >= 7.0: l4_tier = (follow_v2, follow_v2 * 0.05)
            else:
                pct = 3 if sc < 50 else 5
                l4_tier = (fade_v2, fade_v2 * pct / 100)
            layers["L4-tier-3-5-8-12"].append(l4_tier)

            last_ev = rows[k][0]

    print(f"  Total events processed: {n_events}")
    print()
    print(f"  {'Layer':35s} {'n_trade':>8s} {'total_raw':>10s} {'total_cap':>10s} "
          f"{'win%':>6s} {'mean_raw':>9s} {'mean_cap':>10s} {'big_w':>6s} {'cat':>4s}")
    for layer_name, results in layers.items():
        raws = [r[0] for r in results]; caps = [r[1] for r in results]
        agg = aggregate(layer_name, raws, caps, len(results))
        print(f"  {agg['label']:35s} {agg['n_traded']:>8d} "
              f"{agg['total_raw']:>+9.1f}% {agg['total_cap']:>+9.2f}% "
              f"{agg['win_rate']:>5.1f}% {agg['mean_raw']:>+8.2f}% "
              f"{agg['mean_cap']:>+9.3f}% "
              f"{agg.get('big_w', 0):>6d} {agg.get('cat', 0):>4d}")

    con.close()


def main():
    run_bwe_optimization()
    run_broader_optimization()


if __name__ == "__main__":
    main()
