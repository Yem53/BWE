"""24h ticker collector — fills the missing 24h aggregate dimension.

Endpoint: GET /fapi/v1/ticker/24hr (no symbol param = returns all symbols in 1 call,
weight=40, very efficient).

Why we need this: klines_1m has minute-by-minute bars but rolling 24h stats
(price_change_percent, 24h_high, 24h_low, weighted_avg_price, count) are not
trivial to compute from minute data and are 'free' from this endpoint.

Frequency: every 5 minutes (configurable). 24h ticker rolls every minute on
Binance side; sampling every 5min gives a good time series for spike detection.

Writes to the same Hermes DB so all data lives in one place.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

DB_PATH = "/Volumes/T9/BWE/30_DATA/binance_collectors_runtime/binance_futures_1m.sqlite3"
LOG_PATH = "/Volumes/T9/BWE/30_DATA/binance_collectors_runtime/logs/ticker_24h_collector.log"
ENDPOINT = "https://fapi.binance.com/fapi/v1/ticker/24hr"
POLL_SECONDS = 300  # every 5 minutes

SCHEMA = """
CREATE TABLE IF NOT EXISTS ticker_24h (
  symbol TEXT NOT NULL,
  ts_ms INTEGER NOT NULL,
  price_change REAL,
  price_change_percent REAL,
  weighted_avg_price REAL,
  last_price REAL,
  last_qty REAL,
  open_price REAL,
  high_price REAL,
  low_price REAL,
  volume REAL,
  quote_volume REAL,
  open_time_ms INTEGER,
  close_time_ms INTEGER,
  trade_count INTEGER,
  collected_at_ms INTEGER NOT NULL,
  PRIMARY KEY (symbol, ts_ms)
);
CREATE INDEX IF NOT EXISTS idx_ticker_24h_sym_ts ON ticker_24h(symbol, ts_ms);
CREATE INDEX IF NOT EXISTS idx_ticker_24h_ts ON ticker_24h(ts_ms);
"""


def log(msg, level="INFO"):
    ts = datetime.now(timezone.utc).isoformat()
    line = json.dumps({"ts": ts, "level": level, "msg": msg})
    print(line, flush=True)
    with open(LOG_PATH, "a") as f:
        f.write(line + "\n")


def init_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=60)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=60000")
    con.executescript(SCHEMA)
    con.close()


def fetch_and_store():
    try:
        r = requests.get(ENDPOINT, timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        log(f"fetch failed: {e}", "ERROR")
        return 0

    now_ms = int(time.time() * 1000)
    rows = []
    for d in data:
        sym = d.get("symbol")
        if not sym or not sym.endswith("USDT"):
            continue
        rows.append((
            sym,
            int(d.get("closeTime") or now_ms),
            float(d.get("priceChange", 0)),
            float(d.get("priceChangePercent", 0)),
            float(d.get("weightedAvgPrice", 0)),
            float(d.get("lastPrice", 0)),
            float(d.get("lastQty", 0)),
            float(d.get("openPrice", 0)),
            float(d.get("highPrice", 0)),
            float(d.get("lowPrice", 0)),
            float(d.get("volume", 0)),
            float(d.get("quoteVolume", 0)),
            int(d.get("openTime", 0)),
            int(d.get("closeTime", now_ms)),
            int(d.get("count", 0)),
            now_ms,
        ))
    if not rows:
        log("no rows to insert", "WARN")
        return 0

    con = sqlite3.connect(DB_PATH, timeout=60)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=60000")
    try:
        con.executemany(
            "INSERT OR REPLACE INTO ticker_24h VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            rows)
        con.commit()
    finally:
        con.close()
    return len(rows)


def main():
    log(f"24h ticker collector starting (POLL={POLL_SECONDS}s, DB={DB_PATH})")
    init_db()
    while True:
        t0 = time.time()
        try:
            n = fetch_and_store()
            log(f"cycle ok: {n} symbols inserted, took {time.time()-t0:.1f}s")
        except Exception as e:
            log(f"cycle exception: {e}", "ERROR")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
