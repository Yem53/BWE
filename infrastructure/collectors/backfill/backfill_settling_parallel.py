#!/usr/bin/env python3
"""Parallel SETTLING-only kline backfill.

4 workers, each owns:
- HTTP session (independent)
- Rate budget 400 weight/min (total 1600 < Binance 2400)
- DB connection (WAL allows concurrent)

Gap-detect: skips symbols/intervals already complete (via SELECT MIN/MAX).
"""
from __future__ import annotations
import json, os, sqlite3, sys, time, threading
import urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

DB = "/Volumes/T9_HOT/binance_collectors_runtime/binance_futures_1m.sqlite3"
SETTLING_FILE = "/tmp/settling_symbols.txt"
LOG = "/Volumes/T9/BWE/30_DATA/binance_collectors_runtime/logs/parallel_settling.log"
BASE = "https://fapi.binance.com"
PROXY = "http://127.0.0.1:7897"

INTERVALS = ['1m', '3m', '5m', '15m', '1h']
INTERVAL_MS = {'1m': 60_000, '3m': 180_000, '5m': 300_000, '15m': 900_000, '1h': 3_600_000}
DAYS = 30
KLINE_LIMIT = 1500
WORKERS = 2
RATE_PER_WORKER = 700  # weight/min, total 1400/min budget (safer, less WAL pressure)
CHECKPOINT_EVERY_N = 10  # PASSIVE checkpoint per worker every N syms

print_lock = threading.Lock()


def log(d: dict):
    d['ts_ms'] = int(time.time() * 1000)
    line = json.dumps(d, ensure_ascii=False)
    with print_lock:
        print(line, flush=True)
        try:
            with open(LOG, 'a') as f:
                f.write(line + '\n')
        except Exception:
            pass


class RateLimiter:
    def __init__(self, budget_per_min: int):
        self.budget = budget_per_min
        self.tokens = float(budget_per_min)
        self.last = time.time()
        self.lock = threading.Lock()
    def acquire(self, weight: int):
        while True:
            with self.lock:
                now = time.time()
                elapsed = now - self.last
                self.tokens = min(self.budget, self.tokens + elapsed * (self.budget / 60.0))
                self.last = now
                if self.tokens >= weight:
                    self.tokens -= weight
                    return
                wait = (weight - self.tokens) / (self.budget / 60.0)
            time.sleep(min(wait, 5.0))


def http_get(url: str, weight: int, limiter: RateLimiter, max_retries: int = 6):
    handler = urllib.request.ProxyHandler({'http': PROXY, 'https': PROXY})
    opener = urllib.request.build_opener(handler)
    req = urllib.request.Request(url, headers={'User-Agent': 'Hermes-BWE-parallel/1.0'})
    backoff = 1.0
    for attempt in range(max_retries):
        limiter.acquire(weight)
        try:
            with opener.open(req, timeout=20) as resp:
                if resp.status == 200:
                    return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 418:
                wait = min(300, backoff * 30)
                log({'event': 'rate_418', 'wait_s': wait, 'sym': url[-30:], 'attempt': attempt})
                time.sleep(wait)
                backoff *= 2
            elif e.code == 429:
                wait = min(60, backoff * 5)
                time.sleep(wait)
                backoff *= 2
            elif e.code in (400, 404):
                return None
            else:
                time.sleep(backoff)
                backoff *= 2
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as e:
            log({'event': 'net_err', 'attempt': attempt, 'err': str(e)[:80]})
            time.sleep(backoff)
            backoff *= 2
    return None


def get_existing_range(conn, symbol, interval):
    row = conn.execute(
        "SELECT MIN(open_time_ms), MAX(open_time_ms) FROM klines_1m WHERE symbol=? AND interval=?",
        (symbol, interval)
    ).fetchone()
    return row if row else (None, None)


def fetch_and_insert(conn, limiter, symbol, interval, start_ms, end_ms):
    cur = start_ms
    total = 0
    while cur < end_ms:
        url = (f"{BASE}/fapi/v1/klines?symbol={symbol}&interval={interval}"
               f"&startTime={cur}&endTime={end_ms}&limit={KLINE_LIMIT}")
        ks = http_get(url, 2, limiter)
        if not ks:
            break
        rows = []
        now_ms = int(time.time() * 1000)
        for k in ks:
            try:
                rows.append((
                    symbol, interval, int(k[0]), int(k[6]),
                    float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5]),
                    float(k[7]), int(k[8]), float(k[9]), float(k[10]),
                    str(k[11]), 'PERPETUAL', 'SETTLING', 0, now_ms, ''
                ))
            except (ValueError, IndexError, TypeError):
                continue
        if rows:
            res = conn.executemany('''
                INSERT OR IGNORE INTO klines_1m
                (symbol, interval, open_time_ms, close_time_ms, open, high, low, close, volume,
                 quote_volume, trade_count, taker_buy_base_volume, taker_buy_quote_volume,
                 ignore_value, contract_type, status, listing_ts_ms, collected_at_ms, raw_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', rows)
            conn.commit()
            total += res.rowcount
        last_open = int(ks[-1][0])
        if len(ks) < KLINE_LIMIT:
            break
        cur = last_open + INTERVAL_MS[interval]
    return total


# Per-worker symbol counter for periodic checkpoint
_worker_counters = {}
_worker_lock = threading.Lock()

def worker_process_symbol(symbol, limiter, worker_id):
    """Process one symbol: 5 intervals."""
    conn = sqlite3.connect(DB, timeout=120)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA wal_autocheckpoint=2000")
    end_ms = int(time.time() * 1000)
    target_start = end_ms - DAYS * 86400 * 1000
    sym_total = 0
    t0 = time.time()
    for interval in INTERVALS:
        existing_min, existing_max = get_existing_range(conn, symbol, interval)
        gaps = []
        if existing_min is None:
            gaps.append((target_start, end_ms))
        else:
            if target_start < existing_min:
                gaps.append((target_start, existing_min - 1))
            if existing_max < end_ms - INTERVAL_MS[interval]:
                gaps.append((existing_max + INTERVAL_MS[interval], end_ms))
        for g_start, g_end in gaps:
            sym_total += fetch_and_insert(conn, limiter, symbol, interval, g_start, g_end)

    # Periodic checkpoint per worker
    with _worker_lock:
        _worker_counters[worker_id] = _worker_counters.get(worker_id, 0) + 1
        ctr = _worker_counters[worker_id]
    if ctr % CHECKPOINT_EVERY_N == 0:
        try:
            res = conn.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
            log({'event': 'checkpoint', 'worker': worker_id, 'after_n': ctr, 'result': res})
        except Exception as e:
            log({'event': 'checkpoint_err', 'err': str(e)[:80]})
    conn.close()
    log({'event': 'sym_done', 'symbol': symbol, 'inserted': sym_total,
         'elapsed_s': round(time.time() - t0, 1)})
    return symbol, sym_total


def main():
    syms = sorted(set(Path(SETTLING_FILE).read_text().strip().split("\n")))
    log({'event': 'parallel_start', 'workers': WORKERS, 'syms': len(syms),
         'rate_per_worker': RATE_PER_WORKER, 'total_rate': WORKERS * RATE_PER_WORKER})

    # One limiter per worker (so each gets isolated rate budget)
    limiters = [RateLimiter(RATE_PER_WORKER) for _ in range(WORKERS)]

    completed = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as exe:
        futures = {}
        for i, sym in enumerate(syms):
            wid = i % WORKERS
            futures[exe.submit(worker_process_symbol, sym, limiters[wid], wid)] = sym
        for f in as_completed(futures):
            try:
                sym, total = f.result()
                completed += 1
                log({'event': 'progress', 'completed': completed, 'total': len(syms), 'sym': sym})
            except Exception as e:
                sym = futures[f]
                log({'event': 'error', 'sym': sym, 'err': str(e)[:100]})

    log({'event': 'parallel_done', 'completed': completed})


if __name__ == '__main__':
    main()
