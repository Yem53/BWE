"""Fetch 15m Klines from Binance Futures for R5 7d hold granularity upgrade.

Output: legacy_market_cache compatible JSON files.
Idempotent (skip existing). Memory-safe per-symbol (no batch accumulation).
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import requests

OUT_DIR = Path("/Volumes/T9/BWE/30_DATA/reference/legacy_market_cache/r5_15m_collection")
OUT_DIR.mkdir(parents=True, exist_ok=True)
LOG = Path("/Volumes/T9/BWE/40_EXPERIMENTS/round4/99_logs/fetch_15m.log")
LOG.parent.mkdir(parents=True, exist_ok=True)
RANGES_CSV = Path("/Volumes/T9/BWE/40_EXPERIMENTS/round4/per_symbol_15m_fetch_ranges.csv")

PROXIES_CLASH = {
    "http": "http://127.0.0.1:7897",
    "https": "http://127.0.0.1:7897",
}


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with LOG.open("a") as f:
        f.write(line + "\n")


def fetch_chunk(symbol: str, start_ms: int, end_ms: int, proxies: dict | None) -> list:
    url = "https://fapi.binance.com/fapi/v1/klines"
    params = {
        "symbol": symbol,
        "interval": "15m",
        "startTime": start_ms,
        "endTime": end_ms,
        "limit": 1500,
    }
    r = requests.get(url, params=params, proxies=proxies, timeout=30)
    if r.status_code == 429:
        log(f"  {symbol}: 429 rate limit, sleep 60s")
        time.sleep(60)
        r = requests.get(url, params=params, proxies=proxies, timeout=30)
    r.raise_for_status()
    return r.json()


def fetch_symbol(symbol: str, start_ms: int, end_ms: int) -> list[dict]:
    """Paginate fetch. Tries direct first, falls back to Clash proxy."""
    all_bars = []
    cursor = start_ms
    proxies = None  # try direct first
    n_calls = 0

    while cursor < end_ms:
        # 15m bars × 1500 limit = 22.5 days max per call, but use start->end span
        chunk_end = min(cursor + 1500 * 15 * 60 * 1000, end_ms)
        try:
            chunk = fetch_chunk(symbol, cursor, chunk_end, proxies)
            n_calls += 1
        except (requests.HTTPError, requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            if proxies is None:
                proxies = PROXIES_CLASH
                log(f"  {symbol}: direct failed ({type(e).__name__}), trying Clash proxy")
                continue
            log(f"  {symbol}: proxy also failed ({type(e).__name__}), abort")
            break

        if not chunk:
            break
        all_bars.extend(chunk)

        # Advance cursor to past last bar's close_time
        last_close = chunk[-1][6]
        new_cursor = last_close + 1
        if new_cursor <= cursor:
            break
        cursor = new_cursor

        time.sleep(0.2)  # ~5 req/sec

    # Dedupe by open_time_ms, sort
    seen = set()
    dedup = []
    for bar in all_bars:
        ts = bar[0]
        if ts in seen:
            continue
        seen.add(ts)
        try:
            dedup.append({
                "ts_ms": int(bar[0]),
                "open": float(bar[1]),
                "high": float(bar[2]),
                "low": float(bar[3]),
                "close": float(bar[4]),
                "volume": float(bar[5]),
                "close_time_ms": int(bar[6]),
                "quote_volume": float(bar[7]),
            })
        except (ValueError, TypeError, IndexError):
            continue

    return sorted(dedup, key=lambda x: x["ts_ms"])


def main() -> int:
    rows = list(csv.DictReader(open(RANGES_CSV)))
    log(f"=== fetch 15m klines for {len(rows)} symbols ===")

    n_done = 0
    n_skipped = 0
    n_failed = 0
    total_bars = 0
    t0 = time.time()

    for i, row in enumerate(rows, 1):
        sym = row["api_symbol"]
        start = int(row["fetch_start_ms"])
        end = int(row["fetch_end_ms"])
        h = hashlib.md5(f"{sym}_15m_r5_collection".encode()).hexdigest()[:12]
        out_file = OUT_DIR / f"ohlcv_window_binanceusdm_{sym}_15m_{h}.json"

        if out_file.exists() and out_file.stat().st_size > 1000:
            n_skipped += 1
            continue

        try:
            bars = fetch_symbol(sym, start, end)
        except Exception as e:
            log(f"  [{i}/{len(rows)}] {sym}: EXCEPTION {type(e).__name__}: {e}")
            n_failed += 1
            continue

        if bars:
            out_file.write_text(json.dumps(bars))
            n_done += 1
            total_bars += len(bars)
            if n_done % 10 == 0 or n_done <= 5:
                log(f"  [{i}/{len(rows)}] {sym}: {len(bars)} bars (cumulative: {n_done} done, {total_bars:,} bars, {time.time()-t0:.0f}s)")
        else:
            log(f"  [{i}/{len(rows)}] {sym}: NO DATA")
            n_failed += 1

    elapsed = time.time() - t0
    log(f"=== DONE ===")
    log(f"  symbols processed: {len(rows)}")
    log(f"  succeeded: {n_done}")
    log(f"  skipped (already existed): {n_skipped}")
    log(f"  failed/no data: {n_failed}")
    log(f"  total bars: {total_bars:,}")
    log(f"  elapsed: {elapsed:.0f}s")
    log(f"  output: {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
