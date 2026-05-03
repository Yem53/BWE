"""Memory-safe combined builder: 1m for 0-24h, 1h broadcast for 24h-168h.

User's specified granularity (2026-04-28): 前 24h 用分钟级 k 线, 后 156h 用 15min;
但 15m kline 在 legacy_market_cache 不存在 (只有 1m/5m/1h), 降级用 1h broadcast.

Strategy (memory-safe — avoids prior OOM):
  1. Per-symbol streaming: load all 1m/1h JSONs of one symbol at a time
  2. Extract per-event window for that symbol (0-24h with 1m, 24h-168h with 1h broadcast)
  3. Write to parquet, free memory, move to next symbol
  4. Peak RAM: one symbol's bars only (< 50 MB)

Output:
  /Volumes/T9/BWE/30_DATA/cache/normalized/trade_kline_1m_event_windows_7d.parquet
  Replaces existing 7d (hourly-only) parquet with this finer-grained version.
"""
from __future__ import annotations

import argparse
import gc
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq

LEGACY_ROOT = Path("/Volumes/T9/BWE/30_DATA/reference/legacy_market_cache")
EVENTS_PARQUET_5H = Path("/Volumes/T9/BWE/30_DATA/cache/normalized/trade_kline_1m_event_windows.parquet")
OUTPUT_PARQUET = Path("/Volumes/T9/BWE/30_DATA/cache/normalized/trade_kline_1m_event_windows_7d.parquet")
PROGRESS_LOG = Path("/Volumes/T9/BWE/40_EXPERIMENTS/round4/99_logs/build_combined_progress.log")

PATTERN_A = re.compile(
    r"^ohlcv_window_(?P<exchange>[a-z0-9]+)_(?P<symbol>[A-Z0-9]+)_(?P<interval>\w+)_(?P<hash>[0-9a-f]+)\.json$"
)


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    PROGRESS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with PROGRESS_LOG.open("a") as f:
        f.write(line + "\n")


def index_files_by_symbol() -> tuple[dict[str, list[Path]], dict[str, list[Path]]]:
    """Build symbol -> list of (1m, 1h) JSON file paths."""
    log("indexing files by symbol...")
    sym_1m: dict[str, list[Path]] = defaultdict(list)
    sym_1h: dict[str, list[Path]] = defaultdict(list)
    for p in LEGACY_ROOT.rglob("*.json"):
        m = PATTERN_A.match(p.name)
        if not m:
            continue
        symbol = m.group("symbol")
        interval = m.group("interval")
        if interval == "1m":
            sym_1m[symbol].append(p)
        elif interval == "1h":
            sym_1h[symbol].append(p)
    log(f"indexed {len(sym_1m)} symbols with 1m data, {len(sym_1h)} symbols with 1h data")
    return dict(sym_1m), dict(sym_1h)


def load_symbol_bars(files: list[Path], align_minute: bool) -> dict[int, dict]:
    """Load all OHLCV bars from list of JSONs into dict[ts_ms -> bar].

    align_minute: True for 1m (round to minute boundary 60000ms),
                  False for 1h (round to hour boundary 3600000ms).
    """
    bars: dict[int, dict] = {}
    align = 60000 if align_minute else 3600000
    for fp in files:
        try:
            with fp.open() as f:
                data = json.load(f)
            if not isinstance(data, list):
                continue
            for bar in data:
                if not isinstance(bar, dict):
                    continue
                ts = bar.get("ts_ms")
                if ts is None:
                    continue
                aligned_ts = (int(ts) // align) * align
                if aligned_ts in bars:
                    continue
                bars[aligned_ts] = {
                    "open": float(bar.get("open", 0)),
                    "high": float(bar.get("high", 0)),
                    "low": float(bar.get("low", 0)),
                    "close": float(bar.get("close", 0)),
                    "volume": float(bar.get("volume", 0)),
                    "quote_volume": float(bar.get("quote_volume", 0)),
                }
        except (json.JSONDecodeError, ValueError, OSError):
            continue
    return bars


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-back-min", type=int, default=60)
    ap.add_argument("--minute-precision-min", type=int, default=1440,
                    help="Forward minutes using 1m precision (default 1440 = 24h)")
    ap.add_argument("--max-forward-min", type=int, default=10080,
                    help="Total forward (default 10080 = 7d). 1m for 0..1440, 1h for 1441..10080")
    args = ap.parse_args()

    log(f"=== combined builder START (1m for 0..{args.minute_precision_min}min, 1h for {args.minute_precision_min}..{args.max_forward_min}min) ===")
    t0 = time.time()

    log("loading events list")
    events_df = pl.read_parquet(EVENTS_PARQUET_5H).select(
        ["event_id", "api_symbol", "event_ts_ms", "channel", "event_type"]
    ).unique(subset=["event_id"])
    log(f"  events: {events_df.height}")

    # Group events by symbol
    events_by_symbol: dict[str, list[dict]] = defaultdict(list)
    for row in events_df.iter_rows(named=True):
        events_by_symbol[row["api_symbol"]].append(row)
    log(f"  unique event symbols: {len(events_by_symbol)}")

    sym_1m_files, sym_1h_files = index_files_by_symbol()

    # Schema (same as existing event_windows)
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

    n_symbols_done = 0
    n_events_with_data = 0
    n_rows_total = 0
    log(f"per-symbol processing ({len(events_by_symbol)} symbols)")

    sym_keys = sorted(events_by_symbol.keys())
    for symbol in sym_keys:
        sym_events = events_by_symbol[symbol]

        # Load bars for this symbol (free after use)
        bars_1m = load_symbol_bars(sym_1m_files.get(symbol, []), align_minute=True)
        bars_1h = load_symbol_bars(sym_1h_files.get(symbol, []), align_minute=False)

        # Process each event
        for event in sym_events:
            event_id = event["event_id"]
            event_ts = int(event["event_ts_ms"])
            channel = event["channel"]
            event_type = event["event_type"]
            path_ts = (event_ts // 60000) * 60000

            rows = []
            # 1m precision: -max_back_min to +minute_precision_min
            ts = path_ts - args.max_back_min * 60000
            while ts <= path_ts + args.minute_precision_min * 60000:
                bar = bars_1m.get(ts)
                if bar is not None:
                    offset = (ts - path_ts) // 60000
                    rows.append({
                        "event_id": event_id, "api_symbol": symbol,
                        "event_ts_ms": event_ts, "path_ts_ms": path_ts,
                        "minute_offset": offset, "open_time_ms": ts,
                        "close_time_ms": ts + 59999,
                        "trade_open": bar["open"], "trade_high": bar["high"],
                        "trade_low": bar["low"], "trade_close": bar["close"],
                        "trade_volume": bar["volume"], "trade_quote_volume": bar["quote_volume"],
                        "trade_count": 0, "trade_taker_buy_base_volume": 0.0,
                        "trade_taker_buy_quote_volume": 0.0,
                        "trade_kline_available": True,
                        "channel": channel, "event_type": event_type,
                    })
                ts += 60000

            # 1h broadcast: minute_precision_min to max_forward_min
            ts = path_ts + (args.minute_precision_min + 1) * 60000
            while ts <= path_ts + args.max_forward_min * 60000:
                hour_ts = (ts // 3600000) * 3600000
                bar = bars_1h.get(hour_ts)
                if bar is not None:
                    offset = (ts - path_ts) // 60000
                    rows.append({
                        "event_id": event_id, "api_symbol": symbol,
                        "event_ts_ms": event_ts, "path_ts_ms": path_ts,
                        "minute_offset": offset, "open_time_ms": ts,
                        "close_time_ms": ts + 59999,
                        "trade_open": bar["open"], "trade_high": bar["high"],
                        "trade_low": bar["low"], "trade_close": bar["close"],
                        "trade_volume": bar["volume"] / 60.0,
                        "trade_quote_volume": bar["quote_volume"] / 60.0,
                        "trade_count": 0, "trade_taker_buy_base_volume": 0.0,
                        "trade_taker_buy_quote_volume": 0.0,
                        "trade_kline_available": True,
                        "channel": channel, "event_type": event_type,
                    })
                ts += 60000

            if rows:
                n_events_with_data += 1
                writer.write_table(pa.Table.from_pylist(rows, schema=schema))
                n_rows_total += len(rows)

        n_symbols_done += 1
        if n_symbols_done % 50 == 0:
            log(f"  symbols {n_symbols_done}/{len(events_by_symbol)}, "
                f"{n_events_with_data} events have data, {n_rows_total:,} rows")

        # Free per-symbol memory
        del bars_1m, bars_1h
        if n_symbols_done % 100 == 0:
            gc.collect()

    writer.close()

    log("BUILD COMPLETE")
    log(f"  symbols processed: {n_symbols_done}")
    log(f"  events with data: {n_events_with_data}")
    log(f"  total rows: {n_rows_total:,}")
    log(f"  output: {OUTPUT_PARQUET}")
    log(f"  size: {OUTPUT_PARQUET.stat().st_size / 1024 / 1024:.1f} MB")
    log(f"  total elapsed: {(time.time()-t0):.1f}s")

    return 0


if __name__ == "__main__":
    sys.exit(main())
