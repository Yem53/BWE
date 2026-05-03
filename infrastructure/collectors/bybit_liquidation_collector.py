#!/usr/bin/env python3
"""Bybit linear-perp liquidation collector.

Complements OKX (covers ~46% of Binance perp universe). Bybit linear has
~700 USDT perp symbols and covers most of Binance meme coins (FLOKI, BOB,
PEPE family, etc.) that OKX doesn't list.

Bybit REST is Cloudflare-geo-blocked from US, but WebSocket (stream.bybit.com)
is direct-accessible. So we hardcode subscription to the Binance perp USDT
TRADING list (read from collector's symbol_meta) and let Bybit silently
ignore non-existent ones.

Schema: same `liquidations` table as OKX collector. Source distinguished
via raw_json {"src": "bybit"}. PRIMARY KEY (symbol, ts_ms, side, original_qty)
naturally dedupes if the same liquidation lands twice.
"""
from __future__ import annotations

import argparse
import json
import logging
import signal
import sqlite3
import sys
import time
from pathlib import Path

import websocket  # pip install websocket-client

DEFAULT_DB = "/Volumes/T9/BWE/30_DATA/binance_collectors_runtime/binance_futures_1m.sqlite3"
DEFAULT_LOG_PATH = "/Volumes/T9/BWE/30_DATA/binance_collectors_runtime/logs/bybit_liquidation.log"
WS_URL = "wss://stream.bybit.com/v5/public/linear"

# Bybit lets you subscribe to ~10 topics per `subscribe` op.  We chunk to avoid
# server-side limits.
SUB_CHUNK = 10
RESUB_INTERVAL_S = 86400  # rotate subscriptions daily for new symbols

LOG = logging.getLogger("bybit_liquidation_collector")

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


def list_binance_perp_syms(db_path: str) -> list[str]:
    """Read Binance perp USDT TRADING symbol list from collector DB."""
    try:
        uri = f"file:{db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=10)
        try:
            rows = conn.execute(
                "SELECT symbol FROM symbol_meta "
                "WHERE status='TRADING' AND quote_asset='USDT' "
                "AND contract_type='PERPETUAL' AND active=1"
            ).fetchall()
        finally:
            conn.close()
        return [r[0] for r in rows if r[0].isascii()]
    except sqlite3.Error as e:
        LOG.error("symbol_meta read failed: %s", e)
        return []


def parse_liquidation_msg(raw: dict) -> list[dict]:
    """Parse Bybit allLiquidation push.

    Bybit v5 message:
    {
      "topic": "allLiquidation.BTCUSDT",
      "ts": 1672304486868,
      "type": "snapshot",
      "data": [{
         "T": 1672304486865,            # liquidation time (ms)
         "s": "BTCUSDT",                # symbol
         "S": "Sell",                    # liquidation order side (filled by exchange)
         "v": "0.001",                   # qty
         "p": "16578"                   # price
      }]
    }
    """
    if not isinstance(raw, dict):
        return []
    topic = raw.get("topic", "")
    if not topic.startswith("allLiquidation.") and not topic.startswith("liquidation."):
        return []
    out = []
    for entry in raw.get("data") or []:
        try:
            ts_ms = int(entry.get("T") or entry.get("updatedTime") or 0)
            sym = entry.get("s") or entry.get("symbol")
            side = (entry.get("S") or entry.get("side") or "").upper()
            qty = float(entry.get("v") or entry.get("size") or 0)
            px = float(entry.get("p") or entry.get("price") or 0)
            if not sym or ts_ms <= 0 or qty <= 0 or px <= 0:
                continue
            out.append({
                "symbol": sym,
                "ts_ms": ts_ms,
                "side": side,
                "order_type": "MARKET",
                "time_in_force": None,
                "original_qty": qty,
                "price": px,
                "avg_price": px,
                "order_status": "FILLED",
                "last_filled_qty": qty,
                "accumulated_qty": qty,
                "raw_json": json.dumps({"src": "bybit", "topic": topic}, separators=(",", ":")),
                "collected_at_ms": int(time.time() * 1000),
            })
        except (KeyError, ValueError, TypeError) as e:
            LOG.debug("parse_skip entry=%s err=%s", entry, e)
    return out


def insert_event(con: sqlite3.Connection, ev: dict) -> bool:
    try:
        con.execute(
            "INSERT OR IGNORE INTO liquidations "
            "(symbol, ts_ms, side, order_type, time_in_force, original_qty, "
            " price, avg_price, order_status, last_filled_qty, accumulated_qty, "
            " raw_json, collected_at_ms) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
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


class BybitLiquidationCollector:
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
        except json.JSONDecodeError:
            return
        # Subscribe ack
        if raw.get("op") == "subscribe":
            success = raw.get("success", False)
            ret_msg = raw.get("ret_msg", "")
            if success:
                LOG.info("subscribe ok ret=%s", ret_msg)
            else:
                LOG.warning("subscribe failed: %s", raw)
            return
        events = parse_liquidation_msg(raw)
        for ev in events:
            insert_event(self.con, ev)
            self.event_count += 1
        if events and self.event_count % 50 == 0:
            hours = (time.time() - self.start_time) / 3600
            rate = self.event_count / max(hours, 0.01)
            LOG.info("events: %d (rate %.1f/h)", self.event_count, rate)

    def on_error(self, ws, error: Exception) -> None:
        LOG.error("ws error: %s", error)

    def on_close(self, ws, code, reason) -> None:
        LOG.warning("ws closed: code=%s reason=%s", code, reason)

    def on_open(self, ws) -> None:
        LOG.info("ws connected: %s", WS_URL)
        syms = list_binance_perp_syms(self.db_path)
        if not syms:
            LOG.error("no symbols from symbol_meta — abort sub")
            return
        topics = [f"allLiquidation.{s}" for s in syms]
        # chunked subscribe
        for i in range(0, len(topics), SUB_CHUNK):
            chunk = topics[i:i + SUB_CHUNK]
            sub = {"op": "subscribe", "args": chunk}
            ws.send(json.dumps(sub))
            time.sleep(0.1)
        LOG.info("subscribe sent: %d symbols in %d chunks", len(syms), (len(topics) + SUB_CHUNK - 1) // SUB_CHUNK)

    def run(self) -> None:
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
                ws.run_forever(ping_interval=20, ping_timeout=10)
            except Exception as e:
                LOG.error("ws.run_forever exception: %s", e)
            LOG.info("reconnect in %ds", backoff)
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db-path", default=DEFAULT_DB)
    ap.add_argument("--log-level", default="INFO")
    args = ap.parse_args()

    log_path = Path(DEFAULT_LOG_PATH)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(log_path)],
    )
    LOG.info("starting Bybit liquidation collector — sqlite=%s", args.db_path)

    collector = BybitLiquidationCollector(db_path=args.db_path)

    def _shutdown(signum, frame):
        LOG.info("signal %s — exit", signum)
        sys.exit(0)
    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    collector.run()


if __name__ == "__main__":
    main()
