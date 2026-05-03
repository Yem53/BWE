"""Parallel Binance puller — 6 workers, ~1.5h instead of ~10h.

Mac-mini-safe:
  - 6 workers max (well under CPU/RAM limits)
  - Per-thread SQLite connection + WAL mode (concurrent-safe)
  - Per-call sleep 0.2s so total throughput stays safely under Binance limit
    (6 workers × ~0.6 RPS each = ~3.5 RPS × 7 weight avg = 24 weight/sec
     = 1500/min, vs 2400/min Binance cap)
  - HTTP 429/418 detection: ALL threads pause if rate-limited

Each worker handles one symbol end-to-end (klines + OI + 3 long-short).
Resume via pull_progress table — already-done symbols skipped.
"""
from __future__ import annotations

import os
import sqlite3
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import requests

DB_PATH = "/Users/ye/.hermes/research/binance_extended_history.sqlite3"
HERMES_DB = "/Users/ye/.hermes/research/binance_futures_1m_collector_runtime/binance_futures_1m.sqlite3"
LOG_PATH = "/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits/my_pull_log.txt"

DAYS_BACK = 30
N_WORKERS = 4         # reduced from 8 after rate-limit thrashing (8 workers × bursts ≈ over 2400/min)
PER_CALL_SLEEP = 0.2  # 4 workers × ~0.6 RPS = 2.4 RPS × 7 weight ≈ 17 weight/sec = 1000/min (40% of cap)
PAUSE_AFTER_429 = 90  # full rolling-1min weight window reset

BASE = "https://fapi.binance.com"
PERIOD_MS = {"1m": 60_000, "1h": 3_600_000}

# Global rate-limit pause — if any thread hits 429/418 it sets this
_global_pause_until = 0.0
_pause_lock = threading.Lock()
_log_lock = threading.Lock()
_thread_local = threading.local()


def log(msg, level="INFO"):
    ts = datetime.now(timezone.utc).isoformat()
    line = f"[{ts}] [{level}] {msg}"
    with _log_lock:
        print(line, flush=True)
        with open(LOG_PATH, "a") as f:
            f.write(line + "\n")


def get_thread_con():
    if not hasattr(_thread_local, 'con'):
        _thread_local.con = sqlite3.connect(DB_PATH, timeout=60,
                                              check_same_thread=False)
        _thread_local.con.execute("PRAGMA journal_mode=WAL")
        _thread_local.con.execute("PRAGMA busy_timeout=60000")
        _thread_local.con.execute("PRAGMA synchronous=NORMAL")
    return _thread_local.con


def respect_pause():
    global _global_pause_until
    while True:
        with _pause_lock:
            wait = _global_pause_until - time.time()
        if wait <= 0:
            return
        time.sleep(min(wait, 5))


def get(path, params, max_retry=5):
    global _global_pause_until
    for attempt in range(max_retry):
        respect_pause()
        try:
            r = requests.get(BASE + path, params=params, timeout=30)
            if r.status_code == 429:
                log(f"rate-limited, ALL threads pause {PAUSE_AFTER_429}s", "WARN")
                with _pause_lock:
                    _global_pause_until = max(_global_pause_until,
                                              time.time() + PAUSE_AFTER_429)
                # Add jitter so threads don't all wake at exact same instant
                import random
                time.sleep(random.uniform(0, 5))
                continue
            if r.status_code == 418:
                log("BANNED!! ALL threads pause 5min", "ERROR")
                with _pause_lock:
                    _global_pause_until = max(_global_pause_until,
                                              time.time() + 300)
                continue
            if r.status_code == 400:
                return None  # bad symbol
            r.raise_for_status()
            return r.json()
        except Exception as e:
            wait = 2 ** attempt
            log(f"  retry {attempt+1}/{max_retry} after {wait}s: {type(e).__name__}",
                "WARN")
            time.sleep(wait)
    return None


def pull_klines(con, symbol, start_ms, end_ms):
    cursor = start_ms; n = 0
    while cursor < end_ms:
        data = get("/fapi/v1/klines", {"symbol": symbol, "interval": "1m",
                                        "startTime": cursor, "endTime": end_ms,
                                        "limit": 1500})
        if not data: break
        rows = [(symbol, int(d[0]), float(d[1]), float(d[2]), float(d[3]), float(d[4]),
                 float(d[5]), float(d[7]), int(d[8]), float(d[9]), float(d[10]),
                 int(d[6])) for d in data]
        con.executemany("INSERT OR REPLACE INTO klines_1m VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        rows)
        con.commit()
        n += len(rows)
        nxt = int(data[-1][0]) + 60_000
        if nxt <= cursor: break
        cursor = nxt
        time.sleep(PER_CALL_SLEEP)
    return n


def pull_metric_backward(con, symbol, table, endpoint, start_ms, end_ms,
                          row_fn, period="1h"):
    cur_end = end_ms; n = 0
    period_ms = PERIOD_MS[period]
    while cur_end > start_ms:
        data = get(endpoint, {"symbol": symbol, "period": period,
                              "endTime": cur_end, "limit": 500})
        if not data: break
        rows = [row_fn(symbol, d) for d in data]
        rows = [r for r in rows if r[1] >= start_ms]
        if not rows: break
        con.executemany(
            f"INSERT OR REPLACE INTO {table} VALUES "
            f"({','.join(['?']*len(rows[0]))})", rows)
        con.commit()
        n += len(rows)
        oldest_ts = min(r[1] for r in rows)
        cur_end = oldest_ts - period_ms
        if cur_end <= start_ms: break
        time.sleep(PER_CALL_SLEEP)
    return n


def oi_row(sym, d):
    return (sym, int(d["timestamp"]),
            float(d["sumOpenInterest"]), float(d["sumOpenInterestValue"]))


def ls_row(sym, d):
    return (sym, int(d["timestamp"]),
            float(d["longShortRatio"]),
            float(d.get("longAccount") or d.get("longPosition") or 0),
            float(d.get("shortAccount") or d.get("shortPosition") or 0))


def process_symbol(sym, idx, total, start_ms, end_ms):
    con = get_thread_con()
    cur = con.execute(
        "SELECT klines_done, oi_done, global_ls_done, top_account_ls_done, "
        "top_position_ls_done FROM pull_progress WHERE symbol=?", (sym,))
    row = cur.fetchone()
    kl_d, oi_d, gls_d, tals_d, tpls_d = row if row else (0, 0, 0, 0, 0)

    if all([kl_d, oi_d, gls_d, tals_d, tpls_d]):
        return f"[{idx}/{total}] {sym} skip(done)"

    t0 = time.time()
    log(f"[{idx}/{total}] {sym} START")

    try:
        # FIX: only mark done if pull actually got data (n>0) — prevents marking
        # symbols as "done" when HTTP errors caused retries to exhaust.
        if not kl_d:
            n = pull_klines(con, sym, start_ms, end_ms)
            if n > 0:
                con.execute("INSERT OR REPLACE INTO pull_progress VALUES (?,?,?,?,?,?,?)",
                            (sym, 1, oi_d, gls_d, tals_d, tpls_d, end_ms))
                con.commit()
            else:
                log(f"  {sym}: klines pulled 0 rows (skip mark-done)", "WARN")
                # Still create progress row so other endpoints can update
                con.execute("INSERT OR IGNORE INTO pull_progress VALUES (?,?,?,?,?,?,?)",
                            (sym, 0, oi_d, gls_d, tals_d, tpls_d, end_ms))
                con.commit()
        if not oi_d:
            n = pull_metric_backward(con, sym, "open_interest_1h",
                                      "/futures/data/openInterestHist",
                                      start_ms, end_ms, oi_row, "1h")
            if n > 0:
                con.execute("UPDATE pull_progress SET oi_done=1 WHERE symbol=?", (sym,))
                con.commit()
        if not gls_d:
            n = pull_metric_backward(con, sym, "global_long_short_1h",
                                      "/futures/data/globalLongShortAccountRatio",
                                      start_ms, end_ms, ls_row, "1h")
            if n > 0:
                con.execute("UPDATE pull_progress SET global_ls_done=1 WHERE symbol=?", (sym,))
                con.commit()
        if not tals_d:
            n = pull_metric_backward(con, sym, "top_account_long_short_1h",
                                      "/futures/data/topLongShortAccountRatio",
                                      start_ms, end_ms, ls_row, "1h")
            if n > 0:
                con.execute("UPDATE pull_progress SET top_account_ls_done=1 WHERE symbol=?", (sym,))
                con.commit()
        if not tpls_d:
            n = pull_metric_backward(con, sym, "top_position_long_short_1h",
                                      "/futures/data/topLongShortPositionRatio",
                                      start_ms, end_ms, ls_row, "1h")
            if n > 0:
                con.execute("UPDATE pull_progress SET top_position_ls_done=1 WHERE symbol=?", (sym,))
                con.commit()
        elapsed = time.time() - t0
        return f"[{idx}/{total}] {sym} DONE in {elapsed:.1f}s"
    except Exception as e:
        log(f"  {sym} FAILED: {e}", "ERROR")
        return f"[{idx}/{total}] {sym} FAILED"


def main():
    log(f"PARALLEL pull starting (DB={DB_PATH}, workers={N_WORKERS})")
    log(f"Proxy: {os.environ.get('HTTP_PROXY','none (Proton VPN direct)')}")

    hcon = sqlite3.connect(HERMES_DB)
    rows = hcon.execute(
        "SELECT symbol FROM symbol_meta WHERE active=1 AND quote_asset='USDT' ORDER BY symbol"
    ).fetchall()
    symbols = [r[0] for r in rows]
    hcon.close()
    log(f"Symbols: {len(symbols)}")

    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    init_con = sqlite3.connect(DB_PATH)
    init_con.execute("PRAGMA journal_mode=WAL")
    # Schema (idempotent)
    init_con.executescript("""
CREATE TABLE IF NOT EXISTS klines_1m (
  symbol TEXT NOT NULL, open_time_ms INTEGER NOT NULL,
  open REAL, high REAL, low REAL, close REAL,
  volume REAL, quote_volume REAL, trades INTEGER,
  taker_buy_volume REAL, taker_buy_quote_volume REAL,
  close_time_ms INTEGER,
  PRIMARY KEY (symbol, open_time_ms)
);
CREATE TABLE IF NOT EXISTS open_interest_1h (
  symbol TEXT NOT NULL, ts_ms INTEGER NOT NULL,
  sum_open_interest REAL, sum_open_interest_value REAL,
  PRIMARY KEY (symbol, ts_ms)
);
CREATE TABLE IF NOT EXISTS global_long_short_1h (
  symbol TEXT NOT NULL, ts_ms INTEGER NOT NULL,
  long_short_ratio REAL, long_account REAL, short_account REAL,
  PRIMARY KEY (symbol, ts_ms)
);
CREATE TABLE IF NOT EXISTS top_account_long_short_1h (
  symbol TEXT NOT NULL, ts_ms INTEGER NOT NULL,
  long_short_ratio REAL, long_account REAL, short_account REAL,
  PRIMARY KEY (symbol, ts_ms)
);
CREATE TABLE IF NOT EXISTS top_position_long_short_1h (
  symbol TEXT NOT NULL, ts_ms INTEGER NOT NULL,
  long_short_ratio REAL, long_account REAL, short_account REAL,
  PRIMARY KEY (symbol, ts_ms)
);
CREATE TABLE IF NOT EXISTS pull_progress (
  symbol TEXT PRIMARY KEY,
  klines_done INTEGER DEFAULT 0,
  oi_done INTEGER DEFAULT 0,
  global_ls_done INTEGER DEFAULT 0,
  top_account_ls_done INTEGER DEFAULT 0,
  top_position_ls_done INTEGER DEFAULT 0,
  updated_at_ms INTEGER
);
CREATE INDEX IF NOT EXISTS idx_klines_sym_ts ON klines_1m(symbol, open_time_ms);
CREATE INDEX IF NOT EXISTS idx_oi_sym_ts ON open_interest_1h(symbol, ts_ms);
CREATE INDEX IF NOT EXISTS idx_g_ls_sym_ts ON global_long_short_1h(symbol, ts_ms);
CREATE INDEX IF NOT EXISTS idx_ta_ls_sym_ts ON top_account_long_short_1h(symbol, ts_ms);
CREATE INDEX IF NOT EXISTS idx_tp_ls_sym_ts ON top_position_long_short_1h(symbol, ts_ms);
""")
    init_con.close()

    now_ms = int(time.time() * 1000)
    start_ms = now_ms - DAYS_BACK * 86_400_000

    t_overall = time.time()
    completed = 0
    with ThreadPoolExecutor(max_workers=N_WORKERS, thread_name_prefix="pull") as pool:
        futures = {pool.submit(process_symbol, sym, i, len(symbols),
                               start_ms, now_ms): sym
                   for i, sym in enumerate(symbols, 1)}
        for fut in as_completed(futures):
            result = fut.result()
            completed += 1
            if "DONE" in result or "FAILED" in result:
                if completed % 25 == 0 or completed >= len(symbols) - 5:
                    elapsed = (time.time() - t_overall) / 60
                    eta = elapsed / completed * (len(symbols) - completed)
                    log(f"PROGRESS: {completed}/{len(symbols)}  elapsed={elapsed:.1f}min  eta={eta:.1f}min")

    elapsed = (time.time() - t_overall) / 60
    log(f"All symbols processed in {elapsed:.1f} min")

    fcon = sqlite3.connect(DB_PATH)
    summary = []
    for tbl in ("klines_1m", "open_interest_1h", "global_long_short_1h",
                "top_account_long_short_1h", "top_position_long_short_1h"):
        n, ns = fcon.execute(f"SELECT COUNT(*), COUNT(DISTINCT symbol) FROM {tbl}").fetchone()
        summary.append(f"{tbl}={n} ({ns} sym)")
    log("FINAL: " + ", ".join(summary))
    fcon.close()


if __name__ == "__main__":
    main()
