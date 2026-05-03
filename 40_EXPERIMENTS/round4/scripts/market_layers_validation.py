"""Validate L1-L4 (and L3.5/L3.5b) on broader market 妖币 events.

For each detected wave (5min ±8%) in 30d × 530 symbols:
  - L1 naive: -5% SL / +20% TP / 6h time exit
  - L2 exit_v2: always fade direction (pump→short / dump→long), exit_v2 baseline
  - L3 strict E: L2 + rule SKIP filter (E SKIPs duration 3-6, F=FOLLOW, uniform 5%)
  - L3.5 relaxed E: L2 + rule SKIP (E SKIPs only duration==4, F=SKIP, var 5/8%)
  - L3.5b strict E + var pos: L2 + rule SKIP (E SKIPs 3-6, F=SKIP, var 5/8%)
  - L4 directional: rule decides fade/follow + var pos (no per-thesis exit since we
    use exit_v2 baseline for both — per-thesis would need new replay)

Comparison apples-to-apples on the same 1407+ market events (no BWE pre-filtering).
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "exit_v2"))
from exit_v2 import Bar, ExitConfig, ExitEngine, Position, compute_atr_pct

KLINE_DB = "/Users/ye/.hermes/research/binance_extended_history.sqlite3"
SCORE_PATH = Path("/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits/yaobi_score_v1_30d.json")
DIVE_PATH = Path("/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits/yaobi_per_symbol_dive_v1_30d.json")
OUT_PATH = Path("/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits/market_layers_v3.json")

EVENT_PCT = 8.0
EVENT_WINDOW_MIN = 5
COOLDOWN_MIN = 60
HOLD_MIN_LIMIT = 360.0
MIN_PRE_BARS = 35
NAIVE_TP_PCT = 20.0
NAIVE_SL_PCT = 5.0


def fetch_bars_full(con, symbol):
    cur = con.execute(
        "SELECT open_time_ms, open, high, low, close, volume FROM klines_1m "
        "WHERE symbol=? ORDER BY open_time_ms",
        (symbol,))
    return cur.fetchall()


def find_events(rows):
    events = []
    last_event = -10**18
    for i in range(EVENT_WINDOW_MIN, len(rows) - 1):
        if i < MIN_PRE_BARS:
            continue
        if rows[i][0] - last_event < COOLDOWN_MIN * 60_000:
            continue
        c_now = rows[i][4]
        c_then = rows[i - EVENT_WINDOW_MIN][4]
        if c_then <= 0:
            continue
        ret = (c_now - c_then) / c_then * 100
        if abs(ret) < EVENT_PCT:
            continue
        side_natural = "pump" if ret > 0 else "dump"
        # Entry at next bar's open
        next_row = rows[i + 1]
        events.append({
            "symbol": rows[i][0],  # placeholder, set later
            "event_idx": i,
            "event_ts_ms": int(rows[i][0]),
            "side": side_natural,
            "move_pct": float(ret),
            "entry_idx": i + 1,
            "entry_ts_ms": int(next_row[0]),
            "entry_px": float(next_row[1]),
        })
        last_event = rows[i][0]
    return events


def compute_wave_features_at_event(rows, event_idx):
    """Pre-vol ratio + wave duration as the puller would see them."""
    # Pre-vol: 5min before event vs prior 30min
    if event_idx < 35:
        return {"pre_vol": 0, "duration": 0}
    pre5 = rows[event_idx - 5:event_idx]
    base = rows[event_idx - 35:event_idx - 5]
    rv = sum(r[5] for r in pre5) / len(pre5)
    bv = sum(r[5] for r in base) / len(base)
    pre_vol = rv / bv if bv > 0 else 0
    # Wave duration: count how many recent bars had 5min ret >= 5%
    wave_dur = 0
    for k in range(event_idx, max(0, event_idx - 15), -1):
        if k < 5:
            break
        ret = abs((rows[k][4] - rows[k - 5][4]) / rows[k - 5][4] * 100) if rows[k - 5][4] > 0 else 0
        if ret >= 5:
            wave_dur = (rows[event_idx][0] - rows[k][0]) / 60_000 + 1
        else:
            break
    return {"pre_vol": pre_vol, "duration": int(wave_dur)}


def replay_naive(rows, entry_idx, entry_px, side_natural):
    """L1 naive: -5% SL / +20% TP / 6h time. Side = fade thesis (pump→short, dump→long)."""
    trade_side = "short" if side_natural == "pump" else "long"
    end_idx = min(entry_idx + int(HOLD_MIN_LIMIT), len(rows))
    for k in range(entry_idx, end_idx):
        h, l, c = rows[k][2], rows[k][3], rows[k][4]
        if trade_side == "long":
            best = (h - entry_px) / entry_px * 100
            worst = (l - entry_px) / entry_px * 100
        else:
            best = (entry_px - l) / entry_px * 100
            worst = (entry_px - h) / entry_px * 100
        if worst <= -NAIVE_SL_PCT:
            return -NAIVE_SL_PCT
        if best >= NAIVE_TP_PCT:
            return NAIVE_TP_PCT
    last = rows[end_idx - 1] if end_idx else rows[entry_idx]
    if trade_side == "long":
        return (last[4] - entry_px) / entry_px * 100
    return (entry_px - last[4]) / entry_px * 100


def replay_v2(rows, entry_idx, entry_px, trade_side, engine):
    start_idx = max(0, entry_idx - 35)
    end_idx = min(len(rows), entry_idx + int(HOLD_MIN_LIMIT) + 5)
    bars = [Bar(*r) for r in rows[start_idx:end_idx]]
    pre_entry = [b for b in bars if b.ts_ms < rows[entry_idx][0]]
    atr = compute_atr_pct(pre_entry, period=14, ref_px=entry_px) if pre_entry else 0.0
    pos = Position(entry_ts_ms=int(rows[entry_idx][0]), entry_px=entry_px,
                   side=trade_side, hold_minutes_limit=HOLD_MIN_LIMIT, atr_at_entry=atr)
    eidx = next((i for i, b in enumerate(bars) if b.ts_ms >= rows[entry_idx][0]), None)
    if eidx is None:
        return None
    for i in range(eidx, len(bars)):
        d = engine.decide(pos, bars[: i + 1])
        if d:
            return d.pnl_pct
    last = bars[-1]
    return ((last.close - entry_px) / entry_px * 100 if trade_side == "long"
            else (entry_px - last.close) / entry_px * 100)


def apply_rules_l3(meta, wave_feat):
    n_waves = meta.get("n_waves_14d", 0)
    lifecycle = meta.get("lifecycle", "quiet")
    reaction = meta.get("reaction", "n/a")
    score = meta.get("score", 0)
    duration = wave_feat["duration"]; pre_vol = wave_feat["pre_vol"]
    if n_waves < 3: return ("SKIP", 0, "fade", "A")
    if reaction == "trend_continue" and 3 <= duration <= 20:
        return ("ENTER", 5, "fade", "B")  # L3 doesn't change direction
    if reaction == "mean_revert" and lifecycle in ("sustained", "single_burst"):
        return ("ENTER", 8, "fade", "C")
    if score >= 80 and pre_vol < 2.5:
        return ("ENTER", 8, "fade", "D")
    if 3 <= duration <= 6: return ("SKIP", 0, "fade", "E")
    if pre_vol >= 7.0: return ("ENTER", 5, "fade", "F-FOLLOW")
    return ("ENTER", 5, "fade", "G")


def apply_rules_l35(meta, wave_feat):
    n_waves = meta.get("n_waves_14d", 0)
    lifecycle = meta.get("lifecycle", "quiet")
    reaction = meta.get("reaction", "n/a")
    score = meta.get("score", 0)
    duration = wave_feat["duration"]; pre_vol = wave_feat["pre_vol"]
    if n_waves < 3: return ("SKIP", 0, "fade", "A")
    if reaction == "trend_continue" and 3 <= duration <= 20:
        return ("ENTER", 5, "fade", "B")
    if reaction == "mean_revert" and lifecycle in ("sustained", "single_burst"):
        return ("ENTER", 8, "fade", "C")
    if score >= 80 and pre_vol < 2.5:
        return ("ENTER", 8, "fade", "D")
    if duration == 4: return ("SKIP", 0, "fade", "E")
    if pre_vol >= 7.0: return ("SKIP", 0, "fade", "F")
    return ("ENTER", 5, "fade", "G")


def apply_rules_l35b(meta, wave_feat):
    n_waves = meta.get("n_waves_14d", 0)
    lifecycle = meta.get("lifecycle", "quiet")
    reaction = meta.get("reaction", "n/a")
    score = meta.get("score", 0)
    duration = wave_feat["duration"]; pre_vol = wave_feat["pre_vol"]
    if n_waves < 3: return ("SKIP", 0, "fade", "A")
    if reaction == "trend_continue" and 3 <= duration <= 20:
        return ("ENTER", 5, "fade", "B")
    if reaction == "mean_revert" and lifecycle in ("sustained", "single_burst"):
        return ("ENTER", 8, "fade", "C")
    if score >= 80 and pre_vol < 2.5:
        return ("ENTER", 8, "fade", "D")
    if 3 <= duration <= 6: return ("SKIP", 0, "fade", "E")
    if pre_vol >= 7.0: return ("SKIP", 0, "fade", "F")
    return ("ENTER", 5, "fade", "G")


def apply_rules_l4(meta, wave_feat):
    """L4 — rule decides direction (fade vs follow). Position 5/8."""
    n_waves = meta.get("n_waves_14d", 0)
    lifecycle = meta.get("lifecycle", "quiet")
    reaction = meta.get("reaction", "n/a")
    score = meta.get("score", 0)
    duration = wave_feat["duration"]; pre_vol = wave_feat["pre_vol"]
    if n_waves < 3: return ("SKIP", 0, "fade", "A")
    if reaction == "trend_continue" and 3 <= duration <= 20:
        return ("ENTER", 5, "follow", "B")  # L4: switch to follow
    if reaction == "mean_revert" and lifecycle in ("sustained", "single_burst"):
        return ("ENTER", 8, "fade", "C")
    if score >= 80 and pre_vol < 2.5:
        return ("ENTER", 8, "fade", "D")
    if 3 <= duration <= 6: return ("SKIP", 0, "fade", "E")
    if pre_vol >= 7.0: return ("ENTER", 5, "follow", "F")  # L4: high pre-vol → follow
    return ("ENTER", 5, "fade", "G")


def aggregate(layer_name, raws, caps, n_total):
    n_traded = sum(1 for r in raws if r != 0)
    if n_traded == 0:
        return {"label": layer_name, "n_total": n_total, "n_traded": 0,
                "total_raw": 0, "total_cap": 0, "win_rate": 0,
                "mean_raw": 0, "mean_cap": 0,
                "best": 0, "worst": 0, "big_w": 0, "cat": 0}
    nonzero_raws = [r for r in raws if r != 0]
    nonzero_caps = [caps[i] for i, r in enumerate(raws) if r != 0]
    wins = sum(1 for r in nonzero_raws if r > 0)
    return {
        "label": layer_name, "n_total": n_total, "n_traded": n_traded,
        "trade_rate": n_traded / n_total * 100,
        "total_raw": sum(nonzero_raws),
        "total_cap": sum(nonzero_caps),
        "win_rate": wins / n_traded * 100,
        "mean_raw": sum(nonzero_raws) / n_traded,
        "mean_cap": sum(nonzero_caps) / n_traded,
        "best": max(nonzero_raws), "worst": min(nonzero_raws),
        "big_w": sum(1 for r in nonzero_raws if r >= 10),
        "cat": sum(1 for r in nonzero_raws if r <= -15),
    }


def main():
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
    con.execute("PRAGMA query_only=1")
    cur = con.execute("SELECT DISTINCT symbol FROM klines_1m")
    symbols = sorted([r[0] for r in cur.fetchall()])
    print(f"Scanning {len(symbols)} symbols (30d backfill) for ±{EVENT_PCT}% events...")

    eng = ExitEngine(ExitConfig())

    all_events = []
    t0 = time.time()
    for i, sym in enumerate(symbols, 1):
        if i % 50 == 0:
            print(f"  [{i}/{len(symbols)}] {sym} elapsed={(time.time()-t0)/60:.1f}min, events={len(all_events)}")
        rows = fetch_bars_full(con, sym)
        if len(rows) < MIN_PRE_BARS + EVENT_WINDOW_MIN:
            continue
        evs = find_events(rows)
        for ev in evs:
            ev["symbol"] = sym
            wave_feat = compute_wave_features_at_event(rows, ev["event_idx"])
            ev["wave_feat"] = wave_feat
            # Compute fade & follow PnL with exit_v2 baseline
            fade_side = "short" if ev["side"] == "pump" else "long"
            follow_side = "long" if ev["side"] == "pump" else "short"
            ev["naive_pnl"] = replay_naive(rows, ev["entry_idx"], ev["entry_px"], ev["side"])
            ev["fade_v2"] = replay_v2(rows, ev["entry_idx"], ev["entry_px"], fade_side, eng)
            ev["follow_v2"] = replay_v2(rows, ev["entry_idx"], ev["entry_px"], follow_side, eng)
            if ev["fade_v2"] is None or ev["follow_v2"] is None:
                continue
            all_events.append(ev)

    print(f"Total events detected: {len(all_events)} (in {(time.time()-t0)/60:.1f}min)")

    # Now apply each layer to get raw + cap PnL
    n = len(all_events)
    layers = {
        "L1 — naive (-5% SL / +20% TP)": [],
        "L2 — exit_v2 only (5% pos)": [],
        "L3 — exit_v2 + rule SKIP strict E (5% pos)": [],
        "L3.5 — relaxed E + var pos (5/8%)": [],
        "L3.5b — strict E + var pos (5/8%) ⭐️": [],
        "L4 — directional rule (var pos)": [],
    }
    rule_break = {layer: Counter() for layer in layers}

    for ev in all_events:
        fade_pnl = ev["fade_v2"]
        follow_pnl = ev["follow_v2"]

        # L1 naive — always fade thesis (5% pos)
        layers["L1 — naive (-5% SL / +20% TP)"].append(
            (ev["naive_pnl"], ev["naive_pnl"] * 0.05, "fade", "naive"))
        # L2 — always fade with exit_v2 (5% pos)
        layers["L2 — exit_v2 only (5% pos)"].append(
            (fade_pnl, fade_pnl * 0.05, "fade", "L2"))

        meta = sym_meta.get(ev["symbol"], {"score": sym_to_score.get(ev["symbol"], 30),
                                           "lifecycle": "quiet", "reaction": "n/a",
                                           "n_waves_14d": 0})

        # L3
        a, p, dir_, rid = apply_rules_l3(meta, ev["wave_feat"])
        rule_break["L3 — exit_v2 + rule SKIP strict E (5% pos)"][rid] += 1
        if a == "SKIP":
            layers["L3 — exit_v2 + rule SKIP strict E (5% pos)"].append((0, 0, "skip", rid))
        else:
            pnl = fade_pnl if dir_ == "fade" else follow_pnl
            layers["L3 — exit_v2 + rule SKIP strict E (5% pos)"].append(
                (pnl, pnl * 0.05, dir_, rid))  # L3 uniform 5%

        # L3.5
        a, p, dir_, rid = apply_rules_l35(meta, ev["wave_feat"])
        rule_break["L3.5 — relaxed E + var pos (5/8%)"][rid] += 1
        if a == "SKIP":
            layers["L3.5 — relaxed E + var pos (5/8%)"].append((0, 0, "skip", rid))
        else:
            pnl = fade_pnl if dir_ == "fade" else follow_pnl
            layers["L3.5 — relaxed E + var pos (5/8%)"].append((pnl, pnl * p / 100, dir_, rid))

        # L3.5b
        a, p, dir_, rid = apply_rules_l35b(meta, ev["wave_feat"])
        rule_break["L3.5b — strict E + var pos (5/8%) ⭐️"][rid] += 1
        if a == "SKIP":
            layers["L3.5b — strict E + var pos (5/8%) ⭐️"].append((0, 0, "skip", rid))
        else:
            pnl = fade_pnl if dir_ == "fade" else follow_pnl
            layers["L3.5b — strict E + var pos (5/8%) ⭐️"].append(
                (pnl, pnl * p / 100, dir_, rid))

        # L4
        a, p, dir_, rid = apply_rules_l4(meta, ev["wave_feat"])
        rule_break["L4 — directional rule (var pos)"][rid] += 1
        if a == "SKIP":
            layers["L4 — directional rule (var pos)"].append((0, 0, "skip", rid))
        else:
            pnl = fade_pnl if dir_ == "fade" else follow_pnl
            layers["L4 — directional rule (var pos)"].append((pnl, pnl * p / 100, dir_, rid))

    # Aggregate
    print()
    print("=" * 130)
    print(f"BROADER MARKET 30d × {len(symbols)} symbols × ±{EVENT_PCT}% events = {n} events")
    print("=" * 130)
    print(f"{'Layer':52s} {'n_trade':>8s} {'tot_raw':>10s} {'tot_cap':>10s} "
          f"{'win%':>6s} {'mean_raw':>10s} {'mean_cap':>10s} {'big_w':>6s} {'cat':>4s}")
    print("-" * 130)
    aggs = {}
    for layer_label, results in layers.items():
        raws = [r[0] for r in results]
        caps = [r[1] for r in results]
        agg = aggregate(layer_label, raws, caps, n)
        aggs[layer_label] = agg
        print(f"  {agg['label']:50s} {agg['n_traded']:>8d} "
              f"{agg['total_raw']:>+9.1f}% {agg['total_cap']:>+9.2f}% "
              f"{agg['win_rate']:>5.1f}% {agg['mean_raw']:>+9.2f}% "
              f"{agg['mean_cap']:>+9.3f}% {agg['big_w']:>6d} {agg['cat']:>4d}")

    # Rule breakdowns
    print()
    print("=" * 90)
    print("Rule trigger breakdown (where each layer differs)")
    print("=" * 90)
    print(f"{'rule':12s} {'L3':>8s} {'L3.5':>8s} {'L3.5b':>8s} {'L4':>8s}")
    all_rules = sorted(set().union(*[set(rb.keys()) for rb in rule_break.values()]))
    for r in all_rules:
        print(f"  {r:10s} "
              f"{rule_break['L3 — exit_v2 + rule SKIP strict E (5% pos)'].get(r, 0):>8d} "
              f"{rule_break['L3.5 — relaxed E + var pos (5/8%)'].get(r, 0):>8d} "
              f"{rule_break['L3.5b — strict E + var pos (5/8%) ⭐️'].get(r, 0):>8d} "
              f"{rule_break['L4 — directional rule (var pos)'].get(r, 0):>8d}")

    # Save
    OUT_PATH.write_text(json.dumps({
        "n_symbols": len(symbols),
        "n_events": n,
        "params": {"event_pct": EVENT_PCT, "hold_min": HOLD_MIN_LIMIT,
                   "naive_tp": NAIVE_TP_PCT, "naive_sl": NAIVE_SL_PCT},
        "aggregates": aggs,
        "rule_breakdown": {k: dict(v) for k, v in rule_break.items()},
    }, indent=2, default=str))
    print(f"\n  saved: {OUT_PATH}")
    con.close()


if __name__ == "__main__":
    main()
