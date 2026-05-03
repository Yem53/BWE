#!/usr/bin/env python3
"""OKX SWAP liquidation collector.

Replaces broken Binance fstream liquidation collector (US geo-blocks WS data layer).
OKX is US-friendly: REST + WS direct without proxy.

Subscribes to wss://ws.okx.com:8443/ws/v5/public, channel `liquidation-orders`,
instType `SWAP`. Inserts into existing `liquidations` table (schema-compatible
with old Binance collector).

Symbol naming:
  OKX:     BTC-USDT-SWAP, ETH-USDT-SWAP
  Binance: BTCUSDT, ETHUSDT
We normalize OKX -> Binance form for cross-exchange comparison and store
the original OKX form in raw_json for traceability.
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
DEFAULT_LOG_PATH = "/Volumes/T9/BWE/30_DATA/binance_collectors_runtime/logs/okx_liquidation.log"
WS_URL = "wss://ws.okx.com:8443/ws/v5/public"

LOG = logging.getLogger("okx_liquidation_collector")

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


def normalize_okx_symbol(okx_inst: str) -> str | None:
    """BTC-USDT-SWAP -> BTCUSDT.  Returns None for non-USDT or malformed."""
    if not okx_inst.endswith("-USDT-SWAP"):
        return None
    base = okx_inst.split("-")[0]
    if not base:
        return None
    return f"{base}USDT"


def parse_liquidation_msg(raw: dict) -> list[dict]:
    """Parse OKX liquidation-orders push.

    OKX message:
    {
      "arg": {"channel": "liquidation-orders", "instType": "SWAP"},
      "data": [{
         "details": [{
            "bkLoss": "0",
            "bkPx": "0.04865",
            "ccy": "",
            "posSide": "long",   # liquidated position side
            "side": "sell",       # opposite of posSide; the liquidation order side
            "sz": "20",
            "ts": "1777838404335"
         }],
         "instFamily": "PARTI-USDT",
         "instId": "PARTI-USDT-SWAP",
         "instType": "SWAP",
         "uly": "PARTI-USDT"
      }]
    }
    """
    out = []
    if not isinstance(raw, dict):
        return out
    if raw.get("arg", {}).get("channel") != "liquidation-orders":
        return out
    for entry in raw.get("data") or []:
        inst_id = entry.get("instId", "")
        norm_sym = normalize_okx_symbol(inst_id)
        if not norm_sym:
            continue
        for detail in entry.get("details") or []:
            try:
                ts_ms = int(detail["ts"])
                side = (detail.get("side") or "").upper()  # SELL or BUY
                pos_side = (detail.get("posSide") or "").lower()  # long/short
                px = float(detail.get("bkPx") or 0)
                sz = float(detail.get("sz") or 0)
                if px <= 0 or sz <= 0:
                    continue
                out.append({
                    "symbol": norm_sym,
                    "ts_ms": ts_ms,
                    "side": side,
                    "order_type": "MARKET",
                    "time_in_force": None,
                    "original_qty": sz,
                    "price": px,
                    "avg_price": px,  # OKX gives bankruptcy price; treat as avg
                    "order_status": "FILLED",
                    "last_filled_qty": sz,
                    "accumulated_qty": sz,
                    "raw_json": json.dumps({
                        "src": "okx",
                        "instId": inst_id,
                        "posSide": pos_side,
                        "bkLoss": detail.get("bkLoss"),
                        "ccy": detail.get("ccy"),
                    }, separators=(",", ":")),
                    "collected_at_ms": int(time.time() * 1000),
                })
            except (KeyError, ValueError, TypeError) as e:
                LOG.debug("parse_skip detail=%s err=%s", detail, e)
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


class OkxLiquidationCollector:
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
        if raw.get("event") == "subscribe":
            LOG.info("subscribed: %s", raw.get("arg"))
            return
        if raw.get("event") == "error":
            LOG.error("ws error event: %s", raw)
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
        sub = {"op": "subscribe", "args": [
            {"channel": "liquidation-orders", "instType": "SWAP"},
        ]}
        ws.send(json.dumps(sub))
        LOG.info("subscribe sent")

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
    LOG.info("starting OKX liquidation collector — sqlite=%s", args.db_path)
    LOG.info("(direct connection, no proxy needed; binance fstream fails US geo-block)")

    collector = OkxLiquidationCollector(db_path=args.db_path)

    def _shutdown(signum, frame):
        LOG.info("signal %s — exit", signum)
        sys.exit(0)
    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    collector.run()


if __name__ == "__main__":
    main()
