"""Legacy market cache loader (Day 1.2).

Walks H:/BWE/30_DATA/reference/legacy_market_cache/ (10 sub-runs, ~30-50K JSON
files, ~26GB) and unifies all 1m OHLCV windows into a single polars/parquet
table.

Output schema (one row per 1m bar):
    source_run    str    # subdir name, e.g. "bwe_three_channel_run5"
    symbol        str    # normalized, e.g. "AAVEUSDT" (no -SWAP, no dashes)
    interval      str    # always "1m" (other intervals filtered out)
    ts_ms         i64    # bar open time in ms
    close_time_ms i64
    open          f64
    high          f64
    low           f64
    close         f64
    volume        f64
    quote_volume  f64    # may be NaN for some sources
    src_file      str    # filename for traceability

Usage:
    from bwe_autoresearch.bwe_loop_data_loader import load_legacy_cache
    df = load_legacy_cache()  # reads cached parquet if exists

    # Or rebuild from scratch:
    df = load_legacy_cache(rebuild=True)

CLI:
    python -m bwe_autoresearch.bwe_loop_data_loader --rebuild
"""

from __future__ import annotations

import argparse
import json
import re
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Iterator

import polars as pl

from bwe_autoresearch.bwe_paths import (  # noqa: E402
    LEGACY_MARKET_CACHE as LEGACY_ROOT,
    DATA_CACHE_DIR,
)
OUTPUT_DIR = DATA_CACHE_DIR / "legacy_unified"
OUTPUT_PARQUET = OUTPUT_DIR / "legacy_kline_1m_unified.parquet"
OUTPUT_COVERAGE = OUTPUT_DIR / "legacy_kline_1m_coverage.csv"

# Pattern A: ohlcv_window_binanceusdm_{SYMBOL}_{interval}_{hash}.json
PATTERN_A = re.compile(
    r"^ohlcv_window_(?P<exchange>[a-z0-9]+)_(?P<symbol>[A-Z0-9]+)_(?P<interval>\w+)_(?P<hash>[0-9a-f]+)\.json$"
)
# Pattern B: {SYMBOL_WITH_DASHES}_{ts_start}_{ts_end}.json
# e.g. 0G-USDT-SWAP_1758419979000_1772258720000.json -> symbol "0GUSDT"
PATTERN_B = re.compile(
    r"^(?P<raw_symbol>[A-Z0-9-]+)_(?P<ts_start>\d{13})_(?P<ts_end>\d{13})\.json$"
)


def parse_filename(name: str) -> tuple[str | None, str | None]:
    """Return (normalized_symbol, interval) or (None, None) if unmatched.

    Pattern B does not encode interval; assume 1m by inspection (legacy phase1).
    """
    m = PATTERN_A.match(name)
    if m:
        return m.group("symbol"), m.group("interval")
    m = PATTERN_B.match(name)
    if m:
        raw = m.group("raw_symbol")
        # Strip "-SWAP" suffix and remove dashes -> "0G-USDT-SWAP" -> "0GUSDT"
        normalized = raw.replace("-SWAP", "").replace("-", "")
        return normalized, "1m"  # phase1 cache is 1m only
    return None, None


def _classify_payload(data: object) -> str:
    """Classify the JSON payload format.

    Returns one of:
      - "list_ohlcv"   : list[dict] with OHLCV keys -> usable
      - "dict_price_map": dict[ts_str -> float] -> price proxy only, NOT OHLC
      - "dict_ohlcv"   : dict[ts_str -> dict OHLCV] -> usable, rare
      - "empty"        : empty container
      - "unknown"
    """
    if isinstance(data, list):
        if not data:
            return "empty"
        first = data[0]
        if isinstance(first, dict) and "open" in first:
            return "list_ohlcv"
        return "unknown"
    if isinstance(data, dict):
        if not data:
            return "empty"
        first_val = next(iter(data.values()))
        if isinstance(first_val, dict) and "open" in first_val:
            return "dict_ohlcv"
        if isinstance(first_val, (int, float)):
            return "dict_price_map"
        return "unknown"
    return "unknown"


def parse_one_file(path_str: str) -> tuple[list[dict], str]:
    """Parse a single JSON OHLCV file.

    Returns (rows, status) where status is one of:
      - "ok"             : rows is list of OHLCV bar dicts
      - "skip_price_map" : phase1-style price map, no real OHLC available
      - "skip_unknown"   : unrecognized format
      - "skip_filename"  : filename did not match either pattern
      - "skip_interval"  : not 1m
      - "skip_io"        : read/JSON error
      - "skip_empty"     : empty payload
    """
    path = Path(path_str)
    name = path.name
    symbol, interval = parse_filename(name)
    if symbol is None:
        return [], "skip_filename"
    if interval != "1m":
        return [], "skip_interval"

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return [], "skip_io"

    kind = _classify_payload(data)
    if kind == "empty":
        return [], "skip_empty"
    if kind == "dict_price_map":
        return [], "skip_price_map"
    if kind == "unknown":
        return [], "skip_unknown"

    source_run = path.parent.name
    out: list[dict] = []

    iterable: Iterator[dict]
    if kind == "list_ohlcv":
        iterable = iter(data)  # type: ignore[arg-type]
    else:  # dict_ohlcv
        iterable = iter(data.values())  # type: ignore[arg-type]

    for bar in iterable:
        if not isinstance(bar, dict):
            continue
        try:
            out.append(
                {
                    "source_run": source_run,
                    "symbol": symbol,
                    "interval": "1m",
                    "ts_ms": int(bar["ts_ms"]),
                    "close_time_ms": int(bar.get("close_time_ms", 0)) or None,
                    "open": float(bar["open"]),
                    "high": float(bar["high"]),
                    "low": float(bar["low"]),
                    "close": float(bar["close"]),
                    "volume": float(bar.get("volume", 0.0)),
                    "quote_volume": float(bar.get("quote_volume", 0.0)) or None,
                    "src_file": name,
                }
            )
        except (KeyError, TypeError, ValueError):
            continue

    return (out, "ok") if out else ([], "skip_empty")


def iter_legacy_files(root: Path = LEGACY_ROOT) -> Iterator[Path]:
    """Yield every .json file under the legacy cache root."""
    for sub in sorted(root.iterdir()):
        if not sub.is_dir():
            continue
        for f in sub.iterdir():
            if f.suffix == ".json":
                yield f


def load_legacy_cache(
    rebuild: bool = False,
    workers: int = 8,
    sample_limit: int | None = None,
) -> pl.DataFrame:
    """Load the unified legacy cache as a polars DataFrame.

    If a cached parquet already exists and rebuild=False, just reads it.
    Otherwise walks all legacy files, parses in parallel, writes parquet.

    Args:
        rebuild: if True, ignore cached parquet and rebuild from raw JSONs.
        workers: parallel processes for JSON parsing.
        sample_limit: if set, stop after this many files (for quick tests).
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not rebuild and OUTPUT_PARQUET.exists():
        return pl.read_parquet(OUTPUT_PARQUET)

    t0 = time.time()
    files = list(iter_legacy_files(LEGACY_ROOT))
    if sample_limit:
        files = files[:sample_limit]
    n_files = len(files)
    print(f"[load_legacy_cache] discovered {n_files:,} JSON files; parsing with {workers} workers...")

    # Incremental flush to part files to avoid OOM on 50K-file scans.
    parts_dir = OUTPUT_DIR / "_parts"
    if parts_dir.exists():
        for p in parts_dir.iterdir():
            p.unlink()
    parts_dir.mkdir(parents=True, exist_ok=True)

    flush_threshold = 5_000_000  # 5M rows per part
    buffer: list[dict] = []
    part_idx = 0

    def _flush() -> None:
        nonlocal part_idx, buffer
        if not buffer:
            return
        part_path = parts_dir / f"part_{part_idx:04d}.parquet"
        pl.DataFrame(buffer).write_parquet(part_path, compression="zstd")
        print(f"  flushed part {part_idx} -> {part_path.name} ({len(buffer):,} rows)")
        part_idx += 1
        buffer = []

    status_counts: dict[str, int] = {}
    completed = 0
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(parse_one_file, str(f)): f for f in files}
        for fut in as_completed(futures):
            completed += 1
            try:
                bars, status = fut.result()
            except Exception:
                bars, status = [], "skip_exception"
            status_counts[status] = status_counts.get(status, 0) + 1
            if bars:
                buffer.extend(bars)
                if len(buffer) >= flush_threshold:
                    _flush()
            if completed % 2000 == 0:
                print(
                    f"  ... {completed:,}/{n_files:,} files parsed, "
                    f"{len(buffer):,} buffered; parts={part_idx}; "
                    f"statuses={dict(sorted(status_counts.items()))}"
                )
    _flush()  # final partial flush

    n_ok = status_counts.get("ok", 0)
    print(
        f"[load_legacy_cache] parsed {n_ok:,} usable files; "
        f"final status counts: {dict(sorted(status_counts.items()))}"
    )
    if part_idx == 0:
        raise RuntimeError("No usable bars loaded — check legacy cache layout")

    # Concat all parts via polars scan (streaming, low memory)
    print(f"[load_legacy_cache] concatenating {part_idx} part files into final parquet...")
    df = (
        pl.scan_parquet(parts_dir / "part_*.parquet")
        .unique(subset=["source_run", "symbol", "ts_ms"], keep="last")
        .sort(["source_run", "symbol", "ts_ms"])
        .collect(streaming=True)
    )

    df.write_parquet(OUTPUT_PARQUET, compression="zstd")
    elapsed = time.time() - t0
    # Cleanup parts after successful final write
    for p in parts_dir.iterdir():
        p.unlink()
    parts_dir.rmdir()

    coverage = (
        df.group_by(["source_run", "symbol"])
        .agg(
            pl.len().alias("n_bars"),
            pl.col("ts_ms").min().alias("ts_min"),
            pl.col("ts_ms").max().alias("ts_max"),
        )
        .sort(["source_run", "symbol"])
    )
    coverage.write_csv(OUTPUT_COVERAGE)

    print(
        f"[load_legacy_cache] wrote {OUTPUT_PARQUET} ({df.height:,} rows, "
        f"{len(df['symbol'].unique()):,} symbols, {len(df['source_run'].unique())} runs) in {elapsed:.1f}s"
    )
    print(f"[load_legacy_cache] coverage report: {OUTPUT_COVERAGE}")
    return df


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true", help="Rebuild from raw JSONs")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument(
        "--sample-limit",
        type=int,
        default=None,
        help="Limit number of input files for quick testing",
    )
    args = ap.parse_args()
    df = load_legacy_cache(
        rebuild=args.rebuild, workers=args.workers, sample_limit=args.sample_limit
    )
    print("\nSummary:")
    print(f"  rows           : {df.height:,}")
    print(f"  symbols        : {df['symbol'].n_unique():,}")
    print(f"  source_runs    : {df['source_run'].n_unique()}")
    print(f"  ts_ms range    : {df['ts_ms'].min()} - {df['ts_ms'].max()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
