"""Index Price 1m K-line collector.

Polls /fapi/v1/indexPriceKlines for all USDM perp symbols every minute.
Mirrors mark_price_1m collector pattern.

Run via launch_with_proxy.sh for Clash routing.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import requests

LOG = logging.getLogger("index_price_collector")

DEFAULT_DB = (
    "/Volumes/T9/BWE/30_DATA/binance_collectors_runtime/"
    "binance_futures_1m.sqlite3"
)

BASE_URL = "https://fapi.binance.com"
ENDPOINT = "/fapi/v1/indexPriceKlines"
DEFAULT_INTERVAL = "1m"
DEFAULT_LIMIT = 60  # last 60 bars

SCHEMA = """
CREATE TABLE IF NOT EXISTS index_price_1m (
    symbol         TEXT NOT NULL,
    ts_ms          INTEGER NOT NULL,
    interval       TEXT,
    close_time_ms  INTEGER,
    open           REAL,
    high           REAL,
    low            REAL,
    close          REAL,
    collected_at_ms INTEGER,
    raw_json       TEXT,
    PRIMARY KEY (symbol, ts_ms)
);
"""


def list_symbols(con: sqlite3.Connection) -> list[str]:
    rows = con.execute(
        "SELECT DISTINCT symbol FROM klines_1m ORDER BY symbol"
    ).fetchall()
    return [r[0] for r in rows]


def fetch_index_klines(session: requests.Session, symbol: str,
                       interval: str = DEFAULT_INTERVAL,
                       limit: int = DEFAULT_LIMIT) -> Optional[list]:
    try:
        # Index Price uses 'pair' param
        r = session.get(
            BASE_URL + ENDPOINT,
            params={"pair": symbol, "interval": interval, "limit": limit},
            timeout=15,
        )
        if r.status_code == 200:
            return r.json()
        if r.status_code in (400, 404):
            # Symbol might not have index (some custom contracts) — skip silently
            return None
        LOG.warning("HTTP %d for %s", r.status_code, symbol)
        return None
    except Exception as e:
        LOG.warning("fetch_index_klines %s: %s", symbol, e)
        return None


def insert_klines(con: sqlite3.Connection, symbol: str, klines: list) -> int:
    """Insert klines. Each kline = [open_time, open, high, low, close, ignore, close_time, ...]."""
    if not klines:
        return 0
    now_ms = int(time.time() * 1000)
    rows = []
    for k in klines:
        rows.append((
            symbol,
            int(k[0]),       # open_time_ms
            DEFAULT_INTERVAL,
            int(k[6]) if len(k) > 6 else 0,  # close_time_ms
            float(k[1]),     # open
            float(k[2]),     # high
            float(k[3]),     # low
            float(k[4]),     # close
            now_ms,
            json.dumps(k, separators=(",", ":")),
        ))
    cur = con.executemany(
        "INSERT OR IGNORE INTO index_price_1m "
        "(symbol, ts_ms, interval, close_time_ms, open, high, low, close, collected_at_ms, raw_json) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    con.commit()
    return cur.rowcount


def collect_one_symbol(session: requests.Session, symbol: str, db_path: str) -> dict:
    klines = fetch_index_klines(session, symbol)
    if klines is None:
        return {"symbol": symbol, "fetched": 0, "inserted": 0}
    con = sqlite3.connect(db_path, timeout=30)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=30000")
    inserted = insert_klines(con, symbol, klines)
    con.close()
    return {"symbol": symbol, "fetched": len(klines), "inserted": inserted}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db-path", default=DEFAULT_DB)
    ap.add_argument("--cycle-sec", type=int, default=300,
                    help="seconds between cycles (default 5min)")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
    LOG.info("starting index_price_collector")

    con = sqlite3.connect(args.db_path, timeout=30)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=30000")
    con.executescript(SCHEMA)
    con.close()

    session = requests.Session()
    session.headers.update({"User-Agent": "bwe-index-price/1.0"})

    while True:
        cycle_start = time.time()
        con_ro = sqlite3.connect(args.db_path, timeout=30)
        syms = list_symbols(con_ro)
        con_ro.close()
        LOG.info("cycle start: %d symbols", len(syms))

        total_fetched, total_inserted = 0, 0
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futs = {pool.submit(collect_one_symbol, session, s, args.db_path): s for s in syms}
            for fut in as_completed(futs):
                try:
                    r = fut.result()
                    total_fetched += r.get("fetched", 0)
                    total_inserted += r.get("inserted", 0)
                except Exception as e:
                    LOG.warning("collect: %s", e)

        elapsed = time.time() - cycle_start
        LOG.info("cycle done in %.1fs: fetched=%d inserted=%d",
                 elapsed, total_fetched, total_inserted)

        if args.once:
            break
        sleep_for = max(0, args.cycle_sec - elapsed)
        if sleep_for > 0:
            time.sleep(sleep_for)
    return 0


if __name__ == "__main__":
    sys.exit(main())
