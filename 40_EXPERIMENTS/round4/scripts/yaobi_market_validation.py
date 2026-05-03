"""Validate 妖性分 against the full 226-event market scan + RAVE case study.

Two questions:
  Q1. Across the 226 generic 妖币 events (NOT the BWE-filtered 256 trades),
      does the yaobi score predict event behaviour? — bucket the events by
      symbol score, look at v2 exit PnL distribution.
  Q2. RAVE specifically — what does this 'big drama' coin look like?
      Pull every 5-min ±8% event, show pre-event OHLC + volume, replay v2,
      see if there's a pattern.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "exit_v2"))
from exit_v2 import Bar, ExitConfig, ExitEngine, Position, compute_atr_pct

KLINE_DB = "/Users/ye/.hermes/research/binance_futures_1m_collector_runtime/binance_futures_1m.sqlite3"
SCAN_PATH = Path("/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits/market_scan_exit_v2.json")
SCORE_PATH = Path("/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits/yaobi_score_v0.json")


def fetch_bars(con, symbol, start_ms, end_ms):
    cur = con.execute(
        "SELECT open_time_ms, open, high, low, close, volume FROM klines_1m "
        "WHERE symbol=? AND open_time_ms BETWEEN ? AND ? ORDER BY open_time_ms",
        (symbol, start_ms, end_ms),
    )
    return [Bar(*r) for r in cur.fetchall()]


def aggregate_bucket(events, label):
    if not events:
        return f"  {label:18s} n=0"
    n = len(events)
    pnls = [e["v2_pnl"] for e in events]
    naive = [e["naive_pnl"] for e in events]
    wins = sum(1 for p in pnls if p > 0)
    big_w = sum(1 for p in pnls if p >= 10)
    cat = sum(1 for p in pnls if p <= -15)
    return (f"  {label:18s} n={n:>3d}  "
            f"v2_total={sum(pnls):>+8.1f}%  "
            f"v2_mean={sum(pnls)/n:>+5.2f}%  "
            f"v2_win={wins/n*100:>5.1f}%  "
            f"big_w={big_w:>2d}  cat={cat:>2d}  "
            f"|naive_total={sum(naive):>+7.1f}%")


def q1_market_validation(scan_events, sym_to_score):
    print("=" * 100)
    print("Q1. 226 个市场妖币事件 — 按 symbol 妖性分 bucket")
    print("=" * 100)

    # Attach score
    for e in scan_events:
        e["yaobi_score"] = sym_to_score.get(e["symbol"], None)

    no_score = [e for e in scan_events if e["yaobi_score"] is None]
    if no_score:
        print(f"  ⚠️  {len(no_score)} events have no symbol score:")
        for e in no_score[:5]:
            print(f"     {e['symbol']}")
    scored = [e for e in scan_events if e["yaobi_score"] is not None]

    # By score bucket
    print(f"\n--- by yaobi score bucket ({len(scored)} events) ---")
    buckets = [(0, 30, "稳定<30"), (30, 50, "轻妖30-50"),
               (50, 70, "中妖50-70"), (70, 100, "极妖70+")]
    for lo, hi, lbl in buckets:
        sub = [e for e in scored if lo <= e["yaobi_score"] < hi]
        print(aggregate_bucket(sub, lbl))

    # By score AND side
    print(f"\n--- by side × yaobi bucket ---")
    for side_name in ("pump", "dump"):
        print(f"\n  ▸ {side_name} events (→ {('short' if side_name=='pump' else 'long')}):")
        for lo, hi, lbl in buckets:
            sub = [e for e in scored
                   if lo <= e["yaobi_score"] < hi and e["side"] == side_name]
            print(aggregate_bucket(sub, lbl))

    # By event magnitude × yaobi
    print(f"\n--- by event magnitude × yaobi ---")
    for mag_lo, mag_hi, mag_lbl in [(8, 12, "8-12%"), (12, 20, "12-20%"), (20, 100, "20%+")]:
        ev_in_mag = [e for e in scored if mag_lo <= abs(e["move_pct"]) < mag_hi]
        if not ev_in_mag:
            continue
        print(f"\n  ▸ event 5-min move {mag_lbl} ({len(ev_in_mag)} events):")
        for lo, hi, lbl in buckets:
            sub = [e for e in ev_in_mag if lo <= e["yaobi_score"] < hi]
            print(aggregate_bucket(sub, lbl))

    # Dispersion: is score correlated with PnL variance? (high妖 should be wider)
    print(f"\n--- PnL dispersion by bucket (是否极妖 = 更宽分布?) ---")
    for lo, hi, lbl in buckets:
        sub = [e for e in scored if lo <= e["yaobi_score"] < hi]
        if not sub:
            continue
        pnls = sorted([e["v2_pnl"] for e in sub])
        n = len(pnls)
        p10 = pnls[int(n*0.1)]
        p50 = pnls[n//2]
        p90 = pnls[int(n*0.9)]
        worst = pnls[0]
        best = pnls[-1]
        print(f"  {lbl:12s} n={n:>3d}  worst={worst:>+6.1f}  p10={p10:>+6.1f}  "
              f"p50={p50:>+6.1f}  p90={p90:>+6.1f}  best={best:>+6.1f}  "
              f"range_p10_p90={p90-p10:>5.1f}")

    return scored


def q2_rave_case(con, sym_to_score):
    print()
    print("=" * 100)
    print("Q2. RAVE case study — 'big drama' deep dive")
    print("=" * 100)

    sym = "RAVEUSDT"
    score = sym_to_score.get(sym)
    print(f"  symbol: {sym}")
    print(f"  yaobi_score: {score}")

    # Pull all bars
    cur = con.execute(
        "SELECT open_time_ms, open, high, low, close, volume FROM klines_1m "
        "WHERE symbol=? ORDER BY open_time_ms", (sym,))
    rows = cur.fetchall()
    print(f"  total 1m bars in DB: {len(rows)}")
    if not rows:
        print("  (no data)")
        return

    from datetime import datetime, timezone
    start = datetime.fromtimestamp(rows[0][0]/1000, tz=timezone.utc)
    end = datetime.fromtimestamp(rows[-1][0]/1000, tz=timezone.utc)
    print(f"  span: {start} → {end}")

    # Find all 5-min ±8% events (no cooldown — show every one)
    events = []
    for i in range(5, len(rows)):
        c_now = rows[i][4]; c_then = rows[i-5][4]
        if c_then > 0:
            ret = (c_now - c_then) / c_then * 100
            if abs(ret) >= 8:
                events.append((i, ret))
    print(f"  raw ±8% events (5min window, no cooldown): {len(events)}")

    # Cluster into "drama waves" (consecutive minutes within 15min = one wave)
    waves = []
    cur_wave = []
    for idx, ret in events:
        if cur_wave and idx - cur_wave[-1][0] > 15:
            waves.append(cur_wave); cur_wave = []
        cur_wave.append((idx, ret))
    if cur_wave: waves.append(cur_wave)
    print(f"  drama waves (clustered within 15min): {len(waves)}")

    # Show top 10 waves by max abs return
    waves.sort(key=lambda w: -max(abs(r) for _,r in w))
    print(f"\n  Top 10 RAVE waves by intensity:")
    print(f"  {'time_utc':25s} {'peak_5m':>9s} {'wave_min':>8s} {'pre_vol_x':>10s} {'post_v2_pnl':>11s}")

    eng = ExitEngine(ExitConfig())
    for w in waves[:10]:
        # Wave summary
        peak_idx, peak_ret = max(w, key=lambda x: abs(x[1]))
        peak_ts = rows[peak_idx][0]
        from datetime import datetime, timezone
        tstr = datetime.fromtimestamp(peak_ts/1000, tz=timezone.utc).strftime("%m-%d %H:%M")

        # Pre-event volume (5 min before peak vs 30 min baseline before that)
        pre_5 = rows[max(0, peak_idx-5):peak_idx]
        baseline = rows[max(0, peak_idx-35):peak_idx-5]
        if pre_5 and baseline:
            pre_vol = sum(r[5] for r in pre_5) / len(pre_5)
            base_vol = sum(r[5] for r in baseline) / len(baseline)
            vol_x = pre_vol / base_vol if base_vol > 0 else 0
        else:
            vol_x = 0

        # Replay: synthetic entry at next bar after peak
        if peak_idx + 1 >= len(rows):
            v2_pnl_str = "n/a"
        else:
            entry_ts = rows[peak_idx + 1][0]
            entry_px = rows[peak_idx + 1][1]
            trade_side = "short" if peak_ret > 0 else "long"
            # Bars window
            start_idx = max(0, peak_idx - 35)
            end_idx = min(len(rows), peak_idx + 360)
            wbars = [Bar(*r) for r in rows[start_idx:end_idx]]
            pre_entry = [b for b in wbars if b.ts_ms < entry_ts]
            atr = compute_atr_pct(pre_entry, period=14, ref_px=entry_px) if pre_entry else 0
            pos = Position(entry_ts_ms=entry_ts, entry_px=entry_px,
                           side=trade_side, hold_minutes_limit=360.0,
                           atr_at_entry=atr)
            entry_idx_in_wbars = next((i for i,b in enumerate(wbars) if b.ts_ms >= entry_ts), None)
            if entry_idx_in_wbars is None:
                v2_pnl_str = "n/a"
            else:
                d = None
                for i in range(entry_idx_in_wbars, len(wbars)):
                    dec = eng.decide(pos, wbars[: i+1])
                    if dec:
                        d = dec; break
                if d:
                    v2_pnl = d.pnl_pct
                else:
                    last = wbars[-1]
                    v2_pnl = ((last.close - entry_px)/entry_px*100 if trade_side=="long"
                              else (entry_px - last.close)/entry_px*100)
                v2_pnl_str = f"{v2_pnl:+6.1f}%"

        wave_minutes = w[-1][0] - w[0][0] + 1
        print(f"  {tstr:25s} {peak_ret:>+8.1f}% {wave_minutes:>8d} {vol_x:>9.1f}x {v2_pnl_str:>11s}")

    # Daily price summary for RAVE
    print(f"\n  RAVE daily summary:")
    n_min_day = 1440
    print(f"  {'day':12s} {'open':>9s} {'high':>9s} {'low':>9s} {'close':>9s} {'range_%':>9s} {'vol':>11s}")
    for day_start in range(0, len(rows), n_min_day):
        chunk = rows[day_start:day_start + n_min_day]
        if len(chunk) < 60:
            continue
        ts = chunk[0][0]
        d = datetime.fromtimestamp(ts/1000, tz=timezone.utc).strftime("%m-%d %H:%M")
        op = chunk[0][1]; cl = chunk[-1][4]
        hi = max(r[2] for r in chunk); lo = min(r[3] for r in chunk)
        rng = (hi - lo) / op * 100 if op > 0 else 0
        vol = sum(r[5] for r in chunk)
        print(f"  {d:12s} {op:>9.4f} {hi:>9.4f} {lo:>9.4f} {cl:>9.4f} "
              f"{rng:>8.1f}% {vol/1e6:>10.2f}M")


def main():
    score_data = json.loads(SCORE_PATH.read_text())
    sym_to_score = {m["symbol"]: m["yaobi_score"] for m in score_data["ranked"]}
    scan_data = json.loads(SCAN_PATH.read_text())
    scan_events = scan_data["per_event"]
    print(f"Loaded {len(sym_to_score)} symbol scores, {len(scan_events)} market events")
    print()

    scored = q1_market_validation(scan_events, sym_to_score)

    con = sqlite3.connect(KLINE_DB)
    q2_rave_case(con, sym_to_score)
    con.close()

    # Save attached events
    save_path = Path("/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits/yaobi_market_attached.json")
    save_path.write_text(json.dumps({"events": scored}, indent=2, default=str))
    print(f"\n  saved: {save_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
