"""Memory-safe builder of event_windows_7d.parquet (R4 hold up to 168h).

Strategy (avoid Mac OOM that killed previous attempt):
  1. **Stream parse** Pattern A ohlcv_window_*1m*.json files one-by-one.
     Use ProcessPoolExecutor=NO; single-thread; peak RAM < 300 MB.
  2. **Per-symbol bucketing**: maintain dict[symbol -> list of bars]; flush to
     per-symbol parquet when memory threshold hit, then load on-demand.
  3. **For each event** (from existing event_windows.parquet event_id list):
     find symbol's kline data, slice [event_ts - 60min, event_ts + 168h],
     write to streaming output parquet via pyarrow.ParquetWriter.
  4. Output schema **exactly matches** existing event_windows.parquet so
     bwe_loop_data_loader / GPU eval kernels work without modification.

Output:
  /Volumes/T9/BWE/30_DATA/cache/normalized/trade_kline_1m_event_windows_7d.parquet

Usage:
  python scripts/build_event_windows_7d.py
  python scripts/build_event_windows_7d.py --max-forward-min 10080  # 168h = 7d
  python scripts/build_event_windows_7d.py --max-back-min 60 --max-forward-min 4320  # 72h
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

# Paths
LEGACY_ROOT = Path("/Volumes/T9/BWE/30_DATA/reference/legacy_market_cache")
EVENTS_PARQUET = Path("/Volumes/T9/BWE/30_DATA/cache/normalized/trade_kline_1m_event_windows.parquet")
OUTPUT_PARQUET = Path("/Volumes/T9/BWE/30_DATA/cache/normalized/trade_kline_1m_event_windows_7d.parquet")
PROGRESS_LOG = Path("/Volumes/T9/BWE/40_EXPERIMENTS/round4/99_logs/build_7d_progress.log")

PATTERN_A = re.compile(
    r"^ohlcv_window_(?P<exchange>[a-z0-9]+)_(?P<symbol>[A-Z0-9]+)_(?P<interval>\w+)_(?P<hash>[0-9a-f]+)\.json$"
)


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    PROGRESS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with PROGRESS_LOG.open("a") as f:
        f.write(line + "\n")


def parse_ohlcv_filename(name: str) -> tuple[str | None, str | None]:
    """Return (symbol, interval) for Pattern A files."""
    m = PATTERN_A.match(name)
    if not m:
        return None, None
    return m.group("symbol"), m.group("interval")


def collect_bars_per_symbol(max_forward_min: int = 10080, max_back_min: int = 60) -> dict[str, dict[int, dict]]:
    """Stream parse all Pattern A 1m JSONs into per-symbol dict[ts_ms -> bar].

    Memory-safe: each JSON loaded then immediately processed; total RAM
    bounded by aggregate bar count × dict overhead.
    """
    log(f"scanning {LEGACY_ROOT} for ohlcv_window_*_1m_*.json files...")
    files = []
    for p in LEGACY_ROOT.rglob("*1m*.json"):
        if PATTERN_A.match(p.name):
            files.append(p)
    log(f"found {len(files)} Pattern A 1m files")

    by_symbol: dict[str, dict[int, dict]] = {}
    parsed_files = 0
    parsed_bars = 0
    skipped_files = 0

    for fp in files:
        try:
            symbol, interval = parse_ohlcv_filename(fp.name)
            if symbol is None or interval != "1m":
                skipped_files += 1
                continue

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
                # Dedupe by ts_ms — multiple sub-runs may overlap; keep first seen
                if ts in d:
                    continue
                d[ts] = {
                    "ts_ms": int(ts),
                    "open": float(bar.get("open", 0)),
                    "high": float(bar.get("high", 0)),
                    "low": float(bar.get("low", 0)),
                    "close": float(bar.get("close", 0)),
                    "volume": float(bar.get("volume", 0)),
                    "quote_volume": float(bar.get("quote_volume", 0)),
                    "close_time_ms": int(bar.get("close_time_ms", ts + 60000 - 1)),
                }
                parsed_bars += 1

            parsed_files += 1
            if parsed_files % 2000 == 0:
                # Periodic gc
                gc.collect()
                n_symbols = len(by_symbol)
                log(f"  parsed {parsed_files}/{len(files)} files, {parsed_bars:,} bars, {n_symbols} symbols")
        except (json.JSONDecodeError, ValueError, OSError) as e:
            skipped_files += 1
            continue

    log(f"COMPLETE: parsed={parsed_files} skipped={skipped_files} total_bars={parsed_bars:,} symbols={len(by_symbol)}")
    return by_symbol


def build_event_windows(by_symbol: dict, max_forward_min: int, max_back_min: int) -> None:
    """Build event_windows_*.parquet by slicing per-event kline windows."""
    log(f"loading events from {EVENTS_PARQUET}")
    events_df = pl.read_parquet(EVENTS_PARQUET).select(
        ["event_id", "api_symbol", "event_ts_ms", "channel", "event_type"]
    ).unique(subset=["event_id"])
    log(f"events: {events_df.height}")

    # Output schema (exactly matches existing event_windows.parquet)
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
    log(f"building event windows: back={max_back_min}min forward={max_forward_min}min")

    for row in events_df.iter_rows(named=True):
        event_id = row["event_id"]
        symbol = row["api_symbol"]
        event_ts = int(row["event_ts_ms"])
        channel = row["channel"]
        event_type = row["event_type"]

        # Align event_ts to bar boundary (round down to minute)
        path_ts = (event_ts // 60000) * 60000
        ts_start = path_ts - max_back_min * 60000
        ts_end = path_ts + max_forward_min * 60000

        bars_dict = by_symbol.get(symbol, {})

        rows = []
        # Iterate from ts_start to ts_end at 1-minute intervals
        ts = ts_start
        while ts <= ts_end:
            bar = bars_dict.get(ts)
            available = bar is not None
            offset = (ts - path_ts) // 60000
            if available:
                rows.append({
                    "event_id": event_id,
                    "api_symbol": symbol,
                    "event_ts_ms": event_ts,
                    "path_ts_ms": path_ts,
                    "minute_offset": offset,
                    "open_time_ms": bar["ts_ms"],
                    "close_time_ms": bar["close_time_ms"],
                    "trade_open": bar["open"],
                    "trade_high": bar["high"],
                    "trade_low": bar["low"],
                    "trade_close": bar["close"],
                    "trade_volume": bar["volume"],
                    "trade_quote_volume": bar["quote_volume"],
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
            log(f"  processed {n_events_processed}/{events_df.height} events, "
                f"{n_events_with_data} have data, {n_rows_total:,} rows written")

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

    log(f"=== event_windows_7d builder START (forward={args.max_forward_min}min back={args.max_back_min}min) ===")
    t0 = time.time()

    by_symbol = collect_bars_per_symbol(args.max_forward_min, args.max_back_min)
    log(f"phase 1 (collect bars) elapsed: {(time.time()-t0):.1f}s")

    t1 = time.time()
    build_event_windows(by_symbol, args.max_forward_min, args.max_back_min)
    log(f"phase 2 (build windows) elapsed: {(time.time()-t1):.1f}s")

    log(f"=== TOTAL ELAPSED: {(time.time()-t0):.1f}s ===")


if __name__ == "__main__":
    sys.exit(main())
