"""Memory-safe builder of event_windows_hourly.parquet for R5 7d hold.

Strategy (avoids 1m rebuild OOM that killed prior attempt):
  1. Stream-parse 6301 ohlcv_window_*_1h_*.json files (3.6x fewer than 1m).
  2. Per-symbol bar dict, peak RAM <500 MB.
  3. For each event, slice +/-1h to +168h window from symbol's hourly bars.
  4. **Broadcast each hour bar to 60 minute slots** for GPU eval kernel
     compatibility (kernel walks minute-by-minute; we keep dense [N_e, T=10080]).
  5. Within each hour H, all 60 minutes get same OHLC (high/low for whole hour).
     Loses sub-hour timing precision but **OK for 妖币 thesis** (TP=20% at 23h
     vs 23h30m doesn't matter).

Expected output:
  - 7317 events × 168 hourly bars × 60 minutes = 73.7M rows
  - But with broadcast (60 dup per hour) parquet zstd compression → ~200-500 MB

Usage:
  python scripts/build_event_windows_hourly.py
"""
from __future__ import annotations

import argparse
import gc
import json
import re
import sys
import time
from pathlib import Path

import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq

LEGACY_ROOT = Path("/Volumes/T9/BWE/30_DATA/reference/legacy_market_cache")
EVENTS_PARQUET_5H = Path("/Volumes/T9/BWE/30_DATA/cache/normalized/trade_kline_1m_event_windows.parquet")
OUTPUT_PARQUET = Path("/Volumes/T9/BWE/30_DATA/cache/normalized/trade_kline_1m_event_windows_7d.parquet")
PROGRESS_LOG = Path("/Volumes/T9/BWE/40_EXPERIMENTS/round4/99_logs/build_hourly_progress.log")

PATTERN_A = re.compile(
    r"^ohlcv_window_(?P<exchange>[a-z0-9]+)_(?P<symbol>[A-Z0-9]+)_(?P<interval>\w+)_(?P<hash>[0-9a-f]+)\.json$"
)


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    PROGRESS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with PROGRESS_LOG.open("a") as f:
        f.write(line + "\n")


def collect_hourly_bars(forward_min: int = 10080) -> dict[str, dict[int, dict]]:
    """Stream parse all Pattern A 1h JSONs.

    Returns dict[symbol -> dict[hour_ts_ms -> bar]] where hour_ts_ms is
    aligned to hour boundary (3600000 ms).
    """
    files = []
    for p in LEGACY_ROOT.rglob("*1h*.json"):
        if PATTERN_A.match(p.name):
            files.append(p)
    log(f"found {len(files)} Pattern A 1h files")

    by_symbol: dict[str, dict[int, dict]] = {}
    parsed_files = 0
    parsed_bars = 0
    skipped_files = 0

    for fp in files:
        try:
            m = PATTERN_A.match(fp.name)
            if not m or m.group("interval") != "1h":
                skipped_files += 1
                continue
            symbol = m.group("symbol")

            with fp.open() as f:
                data = json.load(f)

            if not isinstance(data, list):
                skipped_files += 1
                continue

            d = by_symbol.setdefault(symbol, {})
            for bar in data:
                if not isinstance(bar, dict):
                    continue
                ts = bar.get("ts_ms")
                if ts is None:
                    continue
                # Align to hour
                hour_ts = (int(ts) // 3600000) * 3600000
                if hour_ts in d:
                    continue
                d[hour_ts] = {
                    "ts_ms": hour_ts,
                    "open": float(bar.get("open", 0)),
                    "high": float(bar.get("high", 0)),
                    "low": float(bar.get("low", 0)),
                    "close": float(bar.get("close", 0)),
                    "volume": float(bar.get("volume", 0)),
                    "quote_volume": float(bar.get("quote_volume", 0)),
                }
                parsed_bars += 1

            parsed_files += 1
            if parsed_files % 1000 == 0:
                gc.collect()
                log(f"  parsed {parsed_files}/{len(files)}, {parsed_bars:,} hourly bars, {len(by_symbol)} symbols")
        except (json.JSONDecodeError, ValueError, OSError):
            skipped_files += 1
            continue

    log(f"COMPLETE phase 1: parsed={parsed_files} skipped={skipped_files} bars={parsed_bars:,} symbols={len(by_symbol)}")
    return by_symbol


def build_event_windows_dense(by_symbol: dict, max_forward_min: int, max_back_min: int) -> None:
    """Build event_windows_7d.parquet with hourly bars broadcast to 1m grid.

    For each event:
      - Determine path_ts (event_ts aligned to minute)
      - Iterate from path_ts-max_back_min to path_ts+max_forward_min in 1m steps
      - For minute t, find containing hour bar, broadcast its OHLC to row
      - Store with same schema as 5h event_windows.parquet
    """
    log("loading events list from 5h event_windows.parquet")
    events_df = pl.read_parquet(EVENTS_PARQUET_5H).select(
        ["event_id", "api_symbol", "event_ts_ms", "channel", "event_type"]
    ).unique(subset=["event_id"])
    log(f"events: {events_df.height}")

    schema = pa.schema([
        ("event_id", pa.large_string()),
        ("api_symbol", pa.large_string()),
        ("event_ts_ms", pa.int64()),
        ("path_ts_ms", pa.int64()),
        ("minute_offset", pa.int64()),
        ("open_time_ms", pa.int64()),
        ("close_time_ms", pa.int64()),
        ("trade_open", pa.float64()),
        ("trade_high", pa.float64()),
        ("trade_low", pa.float64()),
        ("trade_close", pa.float64()),
        ("trade_volume", pa.float64()),
        ("trade_quote_volume", pa.float64()),
        ("trade_count", pa.int64()),
        ("trade_taker_buy_base_volume", pa.float64()),
        ("trade_taker_buy_quote_volume", pa.float64()),
        ("trade_kline_available", pa.bool_()),
        ("channel", pa.large_string()),
        ("event_type", pa.large_string()),
    ])

    OUTPUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    writer = pq.ParquetWriter(OUTPUT_PARQUET, schema, compression="zstd")

    n_events_processed = 0
    n_events_with_data = 0
    n_rows_total = 0
    log(f"building dense event windows: back={max_back_min}min forward={max_forward_min}min (broadcast hourly→1m)")

    for row in events_df.iter_rows(named=True):
        event_id = row["event_id"]
        symbol = row["api_symbol"]
        event_ts = int(row["event_ts_ms"])
        channel = row["channel"]
        event_type = row["event_type"]

        path_ts = (event_ts // 60000) * 60000
        ts_start = path_ts - max_back_min * 60000
        ts_end = path_ts + max_forward_min * 60000

        bars_dict = by_symbol.get(symbol, {})
        if not bars_dict:
            n_events_processed += 1
            continue

        rows = []
        ts = ts_start
        while ts <= ts_end:
            hour_ts = (ts // 3600000) * 3600000
            bar = bars_dict.get(hour_ts)
            if bar is not None:
                offset = (ts - path_ts) // 60000
                rows.append({
                    "event_id": event_id,
                    "api_symbol": symbol,
                    "event_ts_ms": event_ts,
                    "path_ts_ms": path_ts,
                    "minute_offset": offset,
                    "open_time_ms": ts,
                    "close_time_ms": ts + 60000 - 1,
                    "trade_open": bar["open"],
                    "trade_high": bar["high"],
                    "trade_low": bar["low"],
                    "trade_close": bar["close"],
                    "trade_volume": bar["volume"] / 60.0,  # split hourly volume to per-minute
                    "trade_quote_volume": bar["quote_volume"] / 60.0,
                    "trade_count": 0,
                    "trade_taker_buy_base_volume": 0.0,
                    "trade_taker_buy_quote_volume": 0.0,
                    "trade_kline_available": True,
                    "channel": channel,
                    "event_type": event_type,
                })
            ts += 60000

        if rows:
            n_events_with_data += 1
            tbl = pa.Table.from_pylist(rows, schema=schema)
            writer.write_table(tbl)
            n_rows_total += len(rows)

        n_events_processed += 1
        if n_events_processed % 500 == 0:
            log(f"  events {n_events_processed}/{events_df.height}, {n_events_with_data} have data, {n_rows_total:,} rows")

    writer.close()

    log(f"BUILD COMPLETE")
    log(f"  events processed: {n_events_processed}")
    log(f"  events with kline coverage: {n_events_with_data}")
    log(f"  total rows: {n_rows_total:,}")
    log(f"  output: {OUTPUT_PARQUET}")
    log(f"  size: {OUTPUT_PARQUET.stat().st_size / 1024 / 1024:.1f} MB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-forward-min", type=int, default=10080,
                    help="Forward window in minutes (default 10080 = 7 days)")
    ap.add_argument("--max-back-min", type=int, default=60,
                    help="Backward window in minutes (default 60 = 1 hour)")
    args = ap.parse_args()

    log(f"=== HOURLY event_windows builder START (forward={args.max_forward_min}min back={args.max_back_min}min) ===")
    t0 = time.time()

    by_symbol = collect_hourly_bars(args.max_forward_min)
    log(f"phase 1 elapsed: {(time.time()-t0):.1f}s")

    t1 = time.time()
    build_event_windows_dense(by_symbol, args.max_forward_min, args.max_back_min)
    log(f"phase 2 elapsed: {(time.time()-t1):.1f}s")

    log(f"=== TOTAL ELAPSED: {(time.time()-t0):.1f}s ===")


if __name__ == "__main__":
    sys.exit(main())
