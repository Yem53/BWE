"""Liquidation Orders WebSocket collector.

Subscribes to Binance USDM `!forceOrder@arr` stream and writes every
liquidation event to SQLite + monthly parquet on T9.

Run via launch_with_proxy.sh wrapper for Clash routing.

Schema (sqlite + parquet identical):
    symbol, ts_ms, side, order_type, time_in_force, original_qty,
    price, avg_price, order_status, last_filled_qty, accumulated_qty,
    raw_json

Volume estimate: ~100-300 events/day market-wide. Storage trivial.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

import websocket  # pip install websocket-client

LOG = logging.getLogger("liquidation_collector")

WS_URL = "wss://fstream.binance.com/ws/!forceOrder@arr"

DEFAULT_DB = (
    "/Volumes/T9/BWE/30_DATA/binance_collectors_runtime/"
    "binance_futures_1m.sqlite3"
)
DEFAULT_PARQUET_DIR = "/Volumes/T9/binance data/streams"

SCHEMA = """
CREATE TABLE IF NOT EXISTS liquidations (
    symbol           TEXT NOT NULL,
    ts_ms            INTEGER NOT NULL,
    side             TEXT,
    order_type       TEXT,
    time_in_force    TEXT,
    original_qty     REAL,
    price            REAL,
    avg_price        REAL,
    order_status     TEXT,
    last_filled_qty  REAL,
    accumulated_qty  REAL,
    raw_json         TEXT,
    collected_at_ms  INTEGER,
    PRIMARY KEY (symbol, ts_ms, side, original_qty)
);
"""


def parse_force_order(raw: dict) -> dict | None:
    """Parse Binance forceOrder ws message into our schema.

    Binance message shape (USDM):
    {
      "e": "forceOrder",
      "E": <event_time_ms>,
      "o": {
         "s": "BTCUSDT", "S": "SELL", "o": "LIMIT", "f": "IOC",
         "q": "0.014", "p": "60000", "ap": "59950", "X": "FILLED",
         "l": "0.014", "z": "0.014", "T": <trade_time_ms>
      }
    }
    """
    o = raw.get("o", {})
    if not o.get("s"):
        return None
    return {
        "symbol": o["s"],
        "ts_ms": int(o.get("T", raw.get("E", time.time() * 1000))),
        "side": o.get("S"),
        "order_type": o.get("o"),
        "time_in_force": o.get("f"),
        "original_qty": _to_float(o.get("q")),
        "price": _to_float(o.get("p")),
        "avg_price": _to_float(o.get("ap")),
        "order_status": o.get("X"),
        "last_filled_qty": _to_float(o.get("l")),
        "accumulated_qty": _to_float(o.get("z")),
        "raw_json": json.dumps(raw, separators=(",", ":")),
        "collected_at_ms": int(time.time() * 1000),
    }


def _to_float(v) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def insert_event(con: sqlite3.Connection, ev: dict) -> bool:
    try:
        con.execute(
            "INSERT OR IGNORE INTO liquidations "
            "(symbol, ts_ms, side, order_type, time_in_force, original_qty, "
            "price, avg_price, order_status, last_filled_qty, accumulated_qty, "
            "raw_json, collected_at_ms) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                ev["symbol"], ev["ts_ms"], ev["side"], ev["order_type"],
                ev["time_in_force"], ev["original_qty"], ev["price"],
                ev["avg_price"], ev["order_status"], ev["last_filled_qty"],
                ev["accumulated_qty"], ev["raw_json"], ev["collected_at_ms"],
            ),
        )
        con.commit()
        return True
    except Exception as e:
        LOG.warning("insert failed: %s", e)
        return False


class LiquidationCollector:
    def __init__(self, db_path: str = DEFAULT_DB):
        self.db_path = db_path
        self.con = sqlite3.connect(db_path, timeout=30, check_same_thread=False)
        self.con.execute("PRAGMA journal_mode=WAL")
        self.con.execute("PRAGMA busy_timeout=30000")
        self.con.executescript(SCHEMA)
        self.event_count = 0
        self.start_time = time.time()

    def on_message(self, ws, message: str) -> None:
        try:
            raw = json.loads(message)
            ev = parse_force_order(raw)
            if ev is None:
                return
            insert_event(self.con, ev)
            self.event_count += 1
            if self.event_count % 10 == 0:
                hours = (time.time() - self.start_time) / 3600
                rate = self.event_count / max(hours, 0.01)
                LOG.info("events: %d (rate %.1f/h)", self.event_count, rate)
        except Exception as e:
            LOG.warning("on_message: %s", e)

    def on_error(self, ws, error: Exception) -> None:
        LOG.error("ws error: %s", error)

    def on_close(self, ws, code, reason) -> None:
        LOG.warning("ws closed: %s %s", code, reason)

    def on_open(self, ws) -> None:
        LOG.info("ws connected: %s", WS_URL)

    def run(self) -> None:
        # Use proxy from env (Clash via launch_with_proxy.sh)
        proxy_url = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
        proxy_host, proxy_port = None, None
        if proxy_url:
            from urllib.parse import urlparse
            u = urlparse(proxy_url)
            proxy_host, proxy_port = u.hostname, u.port
            LOG.info("via proxy %s:%s", proxy_host, proxy_port)

        backoff = 5
        while True:
            try:
                ws = websocket.WebSocketApp(
                    WS_URL,
                    on_message=self.on_message,
                    on_error=self.on_error,
                    on_close=self.on_close,
                    on_open=self.on_open,
                )
                ws.run_forever(
                    http_proxy_host=proxy_host,
                    http_proxy_port=proxy_port,
                    proxy_type="http",
                    ping_interval=30,
                    ping_timeout=10,
                )
                # Reconnect with backoff
                LOG.info("reconnecting in %ds...", backoff)
                time.sleep(backoff)
                backoff = min(backoff * 2, 120)  # max 2 min
            except KeyboardInterrupt:
                LOG.info("interrupted, exiting")
                break
            except Exception as e:
                LOG.error("run loop: %s", e)
                time.sleep(backoff)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db-path", default=DEFAULT_DB)
    ap.add_argument("--log-level", default="INFO")
    args = ap.parse_args()

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    )
    LOG.info("starting liquidation collector — sqlite=%s", args.db_path)
    c = LiquidationCollector(db_path=args.db_path)
    c.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
