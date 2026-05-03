"""Pull 30d Binance extended history (full market 530+ symbols), v2.

Fixes from v1:
  - Use BACKWARD pagination via endTime (Binance fapi futures/data/* ignore startTime)
  - All metric endpoints use period="1h" (5min × 500 only covers 1.74d, but 1h × 500 = 20.8d)
  - DROP taker pull — same data is in klines_1m.taker_buy_quote_volume
  - DROP funding pull — Hermes already has 34d

Pulls (data Hermes has < 30d for):
  - klines_1m: 30d full
  - open_interest 1h: 20.8d (then 2nd batch backward)
  - global_long_short 1h: 20.8d
  - top_account_long_short 1h: 20.8d
  - top_position_long_short 1h: 20.8d

Symbol list: from Hermes symbol_meta (active=1, USDT quote).
DB: /Users/ye/.hermes/research/binance_extended_history.sqlite3 (APFS, NOT T9).

Estimated runtime: ~80min for 530 symbols (~38 calls/symbol @ 5 RPS).
"""
from __future__ import annotations

import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

DB_PATH = "/Users/ye/.hermes/research/binance_extended_history.sqlite3"
HERMES_DB = "/Users/ye/.hermes/research/binance_futures_1m_collector_runtime/binance_futures_1m.sqlite3"
LOG_PATH = "/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits/my_pull_log.txt"

DAYS_BACK = 30
RPS = 5

BASE = "https://fapi.binance.com"

SCHEMA = """
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
"""

PERIOD_MS = {"1m": 60_000, "1h": 3_600_000}


def log(msg, level="INFO"):
    ts = datetime.now(timezone.utc).isoformat()
    line = f"[{ts}] [{level}] {msg}"
    print(line, flush=True)
    with open(LOG_PATH, "a") as f:
        f.write(line + "\n")


def get(path, params, max_retry=5):
    for attempt in range(max_retry):
        try:
            r = requests.get(BASE + path, params=params, timeout=30)
            if r.status_code == 429:
                log("rate-limited, sleep 60s", "WARN"); time.sleep(60); continue
            if r.status_code == 418:
                log("BANNED!! sleep 5min", "ERROR"); time.sleep(300); continue
            if r.status_code == 400:
                return None  # bad symbol
            r.raise_for_status()
            return r.json()
        except Exception as e:
            wait = 2 ** attempt
            log(f"  retry {attempt+1}/{max_retry} after {wait}s: {e}", "WARN")
            time.sleep(wait)
    return None


def pull_klines(con, symbol, start_ms, end_ms):
    """klines: forward pagination (startTime IS honored)."""
    rate_sleep = 1.0 / RPS
    cursor = start_ms; n = 0
    while cursor < end_ms:
        data = get("/fapi/v1/klines", {"symbol": symbol, "interval": "1m",
                                        "startTime": cursor, "endTime": end_ms,
                                        "limit": 1500})
        if not data: break
        rows = [(symbol, int(d[0]), float(d[1]), float(d[2]), float(d[3]), float(d[4]),
                 float(d[5]), float(d[7]), int(d[8]), float(d[9]), float(d[10]),
                 int(d[6])) for d in data]
        con.executemany("INSERT OR REPLACE INTO klines_1m VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        con.commit()
        n += len(rows)
        nxt = int(data[-1][0]) + 60_000
        if nxt <= cursor: break
        cursor = nxt
        time.sleep(rate_sleep)
    return n


def pull_metric_backward(con, symbol, table, endpoint, start_ms, end_ms,
                          row_fn, period="1h"):
    """For futures/data/* endpoints — paginate BACKWARD via endTime."""
    rate_sleep = 1.0 / RPS
    cur_end = end_ms; n = 0
    period_ms = PERIOD_MS[period]
    while cur_end > start_ms:
        data = get(endpoint, {"symbol": symbol, "period": period,
                              "endTime": cur_end, "limit": 500})
        if not data: break
        rows = [row_fn(symbol, d) for d in data]
        # Filter to range
        rows = [r for r in rows if r[1] >= start_ms]
        if not rows: break
        con.executemany(
            f"INSERT OR REPLACE INTO {table} VALUES "
            f"({','.join(['?']*len(rows[0]))})", rows)
        con.commit()
        n += len(rows)
        # Next batch: ends just before oldest of current batch
        oldest_ts = min(r[1] for r in rows)
        cur_end = oldest_ts - period_ms
        if cur_end <= start_ms: break
        time.sleep(rate_sleep)
    return n


def oi_row(sym, d):
    return (sym, int(d["timestamp"]),
            float(d["sumOpenInterest"]), float(d["sumOpenInterestValue"]))


def ls_row(sym, d):
    return (sym, int(d["timestamp"]),
            float(d["longShortRatio"]),
            float(d.get("longAccount") or d.get("longPosition") or 0),
            float(d.get("shortAccount") or d.get("shortPosition") or 0))


def main():
    log(f"FULL-MARKET pull v2 starting (DB={DB_PATH})")
    log(f"Proxy: {os.environ.get('HTTP_PROXY','none')}")

    hcon = sqlite3.connect(HERMES_DB)
    rows = hcon.execute(
        "SELECT symbol FROM symbol_meta WHERE active=1 AND quote_asset='USDT' ORDER BY symbol"
    ).fetchall()
    symbols = [r[0] for r in rows]
    hcon.close()
    log(f"Symbols: {len(symbols)}")

    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.executescript(SCHEMA)

    now_ms = int(time.time() * 1000)
    start_ms = now_ms - DAYS_BACK * 86_400_000

    t_overall = time.time()
    for i, sym in enumerate(symbols, 1):
        cur = con.execute(
            "SELECT klines_done, oi_done, global_ls_done, top_account_ls_done, "
            "top_position_ls_done FROM pull_progress WHERE symbol=?", (sym,))
        row = cur.fetchone()
        kl_d, oi_d, gls_d, tals_d, tpls_d = row if row else (0,0,0,0,0)

        t_sym = time.time()
        log(f"[{i}/{len(symbols)}] {sym}")

        try:
            if not kl_d:
                n = pull_klines(con, sym, start_ms, now_ms)
                log(f"  klines: {n}")
                con.execute("INSERT OR REPLACE INTO pull_progress VALUES (?,?,?,?,?,?,?)",
                            (sym, 1, oi_d, gls_d, tals_d, tpls_d, now_ms)); con.commit()
                kl_d = 1
            if not oi_d:
                n = pull_metric_backward(con, sym, "open_interest_1h",
                                          "/futures/data/openInterestHist",
                                          start_ms, now_ms, oi_row, "1h")
                log(f"  oi: {n}")
                con.execute("UPDATE pull_progress SET oi_done=1 WHERE symbol=?", (sym,))
                con.commit(); oi_d = 1
            if not gls_d:
                n = pull_metric_backward(con, sym, "global_long_short_1h",
                                          "/futures/data/globalLongShortAccountRatio",
                                          start_ms, now_ms, ls_row, "1h")
                log(f"  global_ls: {n}")
                con.execute("UPDATE pull_progress SET global_ls_done=1 WHERE symbol=?", (sym,))
                con.commit(); gls_d = 1
            if not tals_d:
                n = pull_metric_backward(con, sym, "top_account_long_short_1h",
                                          "/futures/data/topLongShortAccountRatio",
                                          start_ms, now_ms, ls_row, "1h")
                log(f"  top_account_ls: {n}")
                con.execute("UPDATE pull_progress SET top_account_ls_done=1 WHERE symbol=?", (sym,))
                con.commit(); tals_d = 1
            if not tpls_d:
                n = pull_metric_backward(con, sym, "top_position_long_short_1h",
                                          "/futures/data/topLongShortPositionRatio",
                                          start_ms, now_ms, ls_row, "1h")
                log(f"  top_position_ls: {n}")
                con.execute("UPDATE pull_progress SET top_position_ls_done=1 WHERE symbol=?", (sym,))
                con.commit()
            elapsed = time.time() - t_sym
            log(f"  done in {elapsed:.1f}s, total elapsed {(time.time()-t_overall)/60:.1f}min")
        except Exception as e:
            log(f"  {sym} FAILED: {e}", "ERROR")
            continue

    log(f"All symbols processed in {(time.time()-t_overall)/60:.1f} min")
    summary = []
    for tbl in ("klines_1m", "open_interest_1h", "global_long_short_1h",
                "top_account_long_short_1h", "top_position_long_short_1h"):
        n, ns = con.execute(f"SELECT COUNT(*), COUNT(DISTINCT symbol) FROM {tbl}").fetchone()
        summary.append(f"{tbl}={n} ({ns} sym)")
    log("FINAL: " + ", ".join(summary))
    con.close()


if __name__ == "__main__":
    main()
