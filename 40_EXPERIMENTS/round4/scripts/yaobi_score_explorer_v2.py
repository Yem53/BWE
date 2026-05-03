"""Throwaway exploration: compute 妖币 score for all symbols, sanity-check ranking.

NOT production code. Purpose: calibrate composite score weights / thresholds
against real market data before committing to a design.

Uses what we have (5.6d × 535 symbols of 1m kline). Funding & market cap
deferred until data layer ships.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

KLINE_DB = "/Users/ye/.hermes/research/binance_extended_history.sqlite3"

WEIGHTS = {
    "big_moves_5min": 35,
    "max_daily_range": 25,
    "avg_atr": 25,
    "low_volume_bonus": 15,  # inverse: small vol = spicier
}


def compute_metrics(con: sqlite3.Connection, symbol: str) -> dict | None:
    cur = con.execute(
        "SELECT open_time_ms, open, high, low, close, volume FROM klines_1m "
        "WHERE symbol=? ORDER BY open_time_ms",
        (symbol,),
    )
    rows = cur.fetchall()
    if len(rows) < 60:
        return None

    # 1. 5-min ±8% big-move count
    big_moves = 0
    for i in range(5, len(rows)):
        c_now = rows[i][4]
        c_then = rows[i - 5][4]
        if c_then > 0:
            ret = abs((c_now - c_then) / c_then * 100)
            if ret >= 8.0:
                big_moves += 1

    # 2. Max daily high-low range %
    daily_ranges: list[float] = []
    n_min_day = 1440
    for day_start in range(0, len(rows), n_min_day):
        chunk = rows[day_start:day_start + n_min_day]
        if len(chunk) < 60:
            continue
        highs = [r[2] for r in chunk]
        lows = [r[3] for r in chunk]
        opens = [r[1] for r in chunk]
        if not opens or opens[0] <= 0:
            continue
        rng = (max(highs) - min(lows)) / opens[0] * 100
        daily_ranges.append(rng)
    max_daily_range = max(daily_ranges) if daily_ranges else 0.0

    # 3. Avg ATR % over rolling 30-min windows
    atrs: list[float] = []
    for i in range(30, len(rows), 30):
        sliced = rows[max(0, i - 30):i]
        trs = []
        for j in range(1, len(sliced)):
            h, l = sliced[j][2], sliced[j][3]
            prev_c = sliced[j - 1][4]
            tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
            trs.append(tr)
        if trs and sliced[-1][4] > 0:
            atrs.append(sum(trs) / len(trs) / sliced[-1][4] * 100)
    avg_atr = sum(atrs) / len(atrs) if atrs else 0.0

    # 4. 24h quote volume (last 1440 bars)
    last_24h = rows[-1440:] if len(rows) >= 1440 else rows
    quote_vol = sum(r[4] * r[5] for r in last_24h)

    return {
        "symbol": symbol,
        "big_moves_5min_8pct": big_moves,
        "max_daily_range_pct": max_daily_range,
        "avg_atr_pct": avg_atr,
        "quote_vol_24h_usd": quote_vol,
        "n_bars": len(rows),
    }


def percentile_rank(values: list[float]) -> dict[float, float]:
    """Map each value to its percentile rank in [0, 1]."""
    sorted_vals = sorted(set(values))
    if len(sorted_vals) <= 1:
        return {v: 0.5 for v in values}
    return {v: i / (len(sorted_vals) - 1) for i, v in enumerate(sorted_vals)}


def main() -> int:
    con = sqlite3.connect(KLINE_DB)
    symbols = sorted({r[0] for r in con.execute("SELECT DISTINCT symbol FROM klines_1m")})
    print(f"Computing metrics for {len(symbols)} symbols...")

    metrics: list[dict] = []
    for i, sym in enumerate(symbols):
        if i % 100 == 0:
            print(f"  {i}/{len(symbols)}")
        m = compute_metrics(con, sym)
        if m:
            metrics.append(m)

    # Normalize each metric
    bm_rank = percentile_rank([m["big_moves_5min_8pct"] for m in metrics])
    dr_rank = percentile_rank([m["max_daily_range_pct"] for m in metrics])
    atr_rank = percentile_rank([m["avg_atr_pct"] for m in metrics])
    vol_rank = percentile_rank([m["quote_vol_24h_usd"] for m in metrics])

    for m in metrics:
        m["yaobi_score"] = (
            WEIGHTS["big_moves_5min"] * bm_rank[m["big_moves_5min_8pct"]] +
            WEIGHTS["max_daily_range"] * dr_rank[m["max_daily_range_pct"]] +
            WEIGHTS["avg_atr"] * atr_rank[m["avg_atr_pct"]] +
            WEIGHTS["low_volume_bonus"] * (1 - vol_rank[m["quote_vol_24h_usd"]])
        )

    metrics.sort(key=lambda m: -m["yaobi_score"])

    # Print top 30
    print(f"\n{'=' * 100}")
    print(f"TOP 30 妖币 (highest score)")
    print(f"{'=' * 100}")
    print(f"{'symbol':14s} {'score':>6s} {'big_5m':>7s} {'max_d_rng':>10s} {'atr':>6s} {'vol_24h_M':>11s}")
    for m in metrics[:30]:
        print(f"  {m['symbol']:12s} {m['yaobi_score']:>6.1f} {m['big_moves_5min_8pct']:>7d} "
              f"{m['max_daily_range_pct']:>9.1f}% {m['avg_atr_pct']:>5.2f}% "
              f"${m['quote_vol_24h_usd']/1e6:>9.1f}M")

    # Print bottom 30 (supposedly stable)
    print(f"\n{'=' * 100}")
    print(f"BOTTOM 30 (lowest score = stable / blue chip)")
    print(f"{'=' * 100}")
    for m in metrics[-30:]:
        print(f"  {m['symbol']:12s} {m['yaobi_score']:>6.1f} {m['big_moves_5min_8pct']:>7d} "
              f"{m['max_daily_range_pct']:>9.1f}% {m['avg_atr_pct']:>5.2f}% "
              f"${m['quote_vol_24h_usd']/1e6:>9.1f}M")

    # Reference symbols — sanity check
    refs = [
        # Expected high (妖币 candidates)
        "TRADOORUSDT", "KATUSDT", "BSBUSDT", "ZKJUSDT", "PRLUSDT",
        "DAMUSDT", "0GUSDT", "APEUSDT", "ORCAUSDT", "PUMPBTCUSDT",
        "RAVEUSDT", "QUSDT", "NOTUSDT", "DUSDT",
        # Expected low (majors)
        "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT",
    ]
    print(f"\n{'=' * 100}")
    print(f"REFERENCE SYMBOLS — sanity check")
    print(f"{'=' * 100}")
    sym_idx = {m["symbol"]: i for i, m in enumerate(metrics)}
    print(f"{'symbol':14s} {'score':>6s} {'rank':>10s} {'big_5m':>7s} {'max_d_rng':>10s} {'atr':>6s} {'vol_24h_M':>11s}")
    for r in refs:
        i = sym_idx.get(r)
        if i is None:
            print(f"  {r:12s} NOT IN DB")
            continue
        m = metrics[i]
        print(f"  {m['symbol']:12s} {m['yaobi_score']:>6.1f} {i+1:>4d}/{len(metrics):<4d} "
              f"{m['big_moves_5min_8pct']:>7d} {m['max_daily_range_pct']:>9.1f}% "
              f"{m['avg_atr_pct']:>5.2f}% ${m['quote_vol_24h_usd']/1e6:>9.1f}M")

    # Score distribution buckets
    print(f"\n{'=' * 100}")
    print(f"SCORE DISTRIBUTION")
    print(f"{'=' * 100}")
    buckets = [(0, 30), (30, 50), (50, 60), (60, 80), (80, 90), (90, 101)]
    for lo, hi in buckets:
        n = sum(1 for m in metrics if lo <= m["yaobi_score"] < hi)
        pct = n / len(metrics) * 100
        bar = "█" * int(pct / 2)
        print(f"  {lo:>3d}-{hi:<3d}: {n:>4d} ({pct:>5.1f}%) {bar}")

    # Save full ranking
    out_path = Path("/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits/yaobi_score_v1_30d.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    import json
    out_path.write_text(json.dumps({
        "weights": WEIGHTS,
        "n_symbols": len(metrics),
        "ranked": metrics,
    }, indent=2, default=str))
    print(f"\n  saved: {out_path}")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
