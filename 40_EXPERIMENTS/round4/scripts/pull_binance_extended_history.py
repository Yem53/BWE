#!/usr/bin/env python3
"""Pull extended Binance USDT-M futures history into an isolated SQLite DB."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AUDIT_JSON = Path("/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits/yaobi_score_v0.json")
DB_PATH = Path("/Volumes/T9/BWE/30_DATA/cache/binance_extended_history.sqlite3")
LOG_PATH = Path("/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits/codex_pull_log.txt")

BASE_URL = "https://fapi.binance.com"
CORE_SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT")

MINUTE_MS = 60_000
HOUR_MS = 60 * MINUTE_MS
DAY_MS = 24 * HOUR_MS

KLINE_LOOKBACK_MS = 30 * DAY_MS
FUNDING_LOOKBACK_MS = 90 * DAY_MS
OI_LOOKBACK_MS = 30 * DAY_MS

KLINE_LIMIT = 1500
FUNDING_LIMIT = 1000
OI_LIMIT = 500

KLINE_WINDOW_MS = KLINE_LIMIT * MINUTE_MS
FUNDING_WINDOW_MS = FUNDING_LIMIT * 8 * HOUR_MS
OI_WINDOW_MS = OI_LIMIT * HOUR_MS

REQUEST_SLEEP_SECONDS = 0.05
RATE_LIMIT_SLEEP_SECONDS = 60
REQUEST_TIMEOUT_SECONDS = 30
MAX_TRANSIENT_RETRIES = 5


def _load_requests_module() -> Any:
    """Import requests, re-execing with system Python if this Python lacks it."""
    try:
        import requests  # type: ignore

        return requests
    except ModuleNotFoundError as exc:
        candidate = Path("/usr/bin/python3")
        already_reexeced = os.environ.get("BWE_REQUESTS_REEXEC") == "1"
        current = Path(sys.executable).resolve()
        if candidate.exists() and not already_reexeced and current != candidate.resolve():
            check = subprocess.run(
                [str(candidate), "-c", "import requests"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if check.returncode == 0:
                env = os.environ.copy()
                env["BWE_REQUESTS_REEXEC"] = "1"
                os.execve(str(candidate), [str(candidate), *sys.argv], env)
        raise SystemExit(
            "Missing required dependency: requests. "
            "Install requests for this Python or run with /usr/bin/python3."
        ) from exc


requests = _load_requests_module()


class InvalidSymbolError(Exception):
    """Raised for Binance HTTP 400 responses on a symbol."""


class BinanceRequestError(Exception):
    """Raised after request retries are exhausted."""


class SystemicBlocker(Exception):
    """Raised when continuing the job would be unsafe or impossible."""


def log(level: str, message: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(f"[{ts}] [{level}] {message}\n")


def now_ms() -> int:
    return int(time.time() * 1000)


def to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def load_symbols() -> list[str]:
    with AUDIT_JSON.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)

    ranked = payload.get("ranked")
    if not isinstance(ranked, list):
        raise ValueError(f"{AUDIT_JSON} does not contain a ranked array")

    top = sorted(
        ranked,
        key=lambda row: float(row.get("yaobi_score") or 0.0),
        reverse=True,
    )[:100]

    symbols: list[str] = []
    seen: set[str] = set()
    for row in top:
        symbol = str(row.get("symbol", "")).strip().upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        symbols.append(symbol)

    for symbol in CORE_SYMBOLS:
        if symbol not in seen:
            seen.add(symbol)
            symbols.append(symbol)

    return symbols


def connect_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DB_PATH))
    con.execute("PRAGMA journal_mode=DELETE")
    con.execute("PRAGMA synchronous=NORMAL")
    return con


def init_schema(con: sqlite3.Connection) -> None:
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS klines_1m (
          symbol TEXT NOT NULL, open_time_ms INTEGER NOT NULL,
          open REAL, high REAL, low REAL, close REAL,
          volume REAL, quote_volume REAL, trades INTEGER,
          taker_buy_volume REAL, taker_buy_quote_volume REAL,
          close_time_ms INTEGER,
          PRIMARY KEY (symbol, open_time_ms)
        );
        CREATE TABLE IF NOT EXISTS funding_rate (
          symbol TEXT NOT NULL, funding_time_ms INTEGER NOT NULL,
          funding_rate REAL, mark_price REAL,
          PRIMARY KEY (symbol, funding_time_ms)
        );
        CREATE TABLE IF NOT EXISTS open_interest_hist (
          symbol TEXT NOT NULL, period TEXT NOT NULL, ts_ms INTEGER NOT NULL,
          sum_open_interest REAL, sum_open_interest_value REAL,
          PRIMARY KEY (symbol, period, ts_ms)
        );
        CREATE INDEX IF NOT EXISTS idx_klines_symbol_ts ON klines_1m(symbol, open_time_ms);
        CREATE INDEX IF NOT EXISTS idx_funding_symbol_ts ON funding_rate(symbol, funding_time_ms);
        CREATE INDEX IF NOT EXISTS idx_oi_symbol_ts ON open_interest_hist(symbol, ts_ms);
        """
    )
    con.commit()


def get_max_ts(con: sqlite3.Connection, table: str, column: str, symbol: str, period: str | None = None) -> int | None:
    if table == "open_interest_hist":
        row = con.execute(
            "SELECT MAX(ts_ms) FROM open_interest_hist WHERE symbol = ? AND period = ?",
            (symbol, period),
        ).fetchone()
    else:
        row = con.execute(
            f"SELECT MAX({column}) FROM {table} WHERE symbol = ?",
            (symbol,),
        ).fetchone()
    value = row[0] if row else None
    return int(value) if value is not None else None


def fetch_json(session: Any, path: str, params: dict[str, Any]) -> Any:
    url = f"{BASE_URL}{path}"
    transient_attempts = 0
    while True:
        try:
            response = session.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
            time.sleep(REQUEST_SLEEP_SECONDS)
        except requests.exceptions.RequestException as exc:  # type: ignore[attr-defined]
            if "Operation not permitted" in str(exc):
                raise SystemicBlocker(
                    f"network blocked by local environment while requesting {url} {params}: {exc}"
                ) from exc
            transient_attempts += 1
            if transient_attempts > MAX_TRANSIENT_RETRIES:
                raise BinanceRequestError(f"request failed after retries: {url} {params}: {exc}") from exc
            wait_seconds = min(2**transient_attempts, 60)
            log("WARN", f"request exception retry {transient_attempts}/{MAX_TRANSIENT_RETRIES}: {exc}")
            time.sleep(wait_seconds)
            continue

        status = response.status_code
        if status == 429:
            log("WARN", f"HTTP 429 rate limited for {path} {params}; sleeping {RATE_LIMIT_SLEEP_SECONDS}s")
            time.sleep(RATE_LIMIT_SLEEP_SECONDS)
            continue
        if status == 418:
            raise SystemicBlocker(f"Binance returned HTTP 418/IP ban for {path} {params}: {response.text[:500]}")
        if status == 400:
            raise InvalidSymbolError(f"HTTP 400 for {path} {params}: {response.text[:500]}")
        if status in (500, 502, 503, 504):
            transient_attempts += 1
            if transient_attempts > MAX_TRANSIENT_RETRIES:
                raise BinanceRequestError(
                    f"HTTP {status} after retries for {path} {params}: {response.text[:500]}"
                )
            wait_seconds = min(2**transient_attempts, 60)
            log("WARN", f"HTTP {status} retry {transient_attempts}/{MAX_TRANSIENT_RETRIES} for {path} {params}")
            time.sleep(wait_seconds)
            continue
        if status >= 400:
            raise BinanceRequestError(f"HTTP {status} for {path} {params}: {response.text[:500]}")

        try:
            return response.json()
        except ValueError as exc:
            raise BinanceRequestError(f"non-JSON response for {path} {params}: {response.text[:500]}") from exc


def insert_klines(con: sqlite3.Connection, symbol: str, rows: list[list[Any]]) -> int:
    payload = [
        (
            symbol,
            int(row[0]),
            to_float(row[1]),
            to_float(row[2]),
            to_float(row[3]),
            to_float(row[4]),
            to_float(row[5]),
            to_float(row[7]),
            to_int(row[8]),
            to_float(row[9]),
            to_float(row[10]),
            to_int(row[6]),
        )
        for row in rows
    ]
    before = con.total_changes
    con.executemany(
        """
        INSERT OR IGNORE INTO klines_1m (
          symbol, open_time_ms, open, high, low, close, volume, quote_volume,
          trades, taker_buy_volume, taker_buy_quote_volume, close_time_ms
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        payload,
    )
    return con.total_changes - before


def insert_funding(con: sqlite3.Connection, rows: list[dict[str, Any]]) -> int:
    payload = [
        (
            str(row.get("symbol", "")),
            int(row["fundingTime"]),
            to_float(row.get("fundingRate")),
            to_float(row.get("markPrice")),
        )
        for row in rows
    ]
    before = con.total_changes
    con.executemany(
        """
        INSERT OR IGNORE INTO funding_rate (
          symbol, funding_time_ms, funding_rate, mark_price
        ) VALUES (?, ?, ?, ?)
        """,
        payload,
    )
    return con.total_changes - before


def insert_oi(con: sqlite3.Connection, symbol: str, rows: list[dict[str, Any]]) -> int:
    payload = [
        (
            str(row.get("symbol") or symbol),
            "1h",
            int(row["timestamp"]),
            to_float(row.get("sumOpenInterest")),
            to_float(row.get("sumOpenInterestValue")),
        )
        for row in rows
    ]
    before = con.total_changes
    con.executemany(
        """
        INSERT OR IGNORE INTO open_interest_hist (
          symbol, period, ts_ms, sum_open_interest, sum_open_interest_value
        ) VALUES (?, ?, ?, ?, ?)
        """,
        payload,
    )
    return con.total_changes - before


def pull_klines(con: sqlite3.Connection, session: Any, symbol: str, end_ms: int) -> int:
    floor = end_ms - KLINE_LOOKBACK_MS
    max_seen = get_max_ts(con, "klines_1m", "open_time_ms", symbol)
    start_ms = max(floor, (max_seen + 1) if max_seen is not None else floor)
    inserted = 0

    while start_ms <= end_ms:
        window_end = min(start_ms + KLINE_WINDOW_MS - 1, end_ms)
        data = fetch_json(
            session,
            "/fapi/v1/klines",
            {
                "symbol": symbol,
                "interval": "1m",
                "startTime": start_ms,
                "endTime": window_end,
                "limit": KLINE_LIMIT,
            },
        )
        if not data:
            break
        inserted += insert_klines(con, symbol, data)
        last_open = int(data[-1][0])
        next_start = last_open + MINUTE_MS
        if next_start <= start_ms:
            break
        start_ms = next_start

    return inserted


def pull_funding(con: sqlite3.Connection, session: Any, symbol: str, end_ms: int) -> int:
    floor = end_ms - FUNDING_LOOKBACK_MS
    max_seen = get_max_ts(con, "funding_rate", "funding_time_ms", symbol)
    start_ms = max(floor, (max_seen + 1) if max_seen is not None else floor)
    inserted = 0

    while start_ms <= end_ms:
        window_end = min(start_ms + FUNDING_WINDOW_MS - 1, end_ms)
        data = fetch_json(
            session,
            "/fapi/v1/fundingRate",
            {
                "symbol": symbol,
                "startTime": start_ms,
                "endTime": window_end,
                "limit": FUNDING_LIMIT,
            },
        )
        if not data:
            break
        inserted += insert_funding(con, data)
        last_ts = int(data[-1]["fundingTime"])
        next_start = last_ts + 1
        if next_start <= start_ms:
            break
        start_ms = next_start

    return inserted


def pull_oi(con: sqlite3.Connection, session: Any, symbol: str, end_ms: int) -> int:
    floor = end_ms - OI_LOOKBACK_MS
    max_seen = get_max_ts(con, "open_interest_hist", "ts_ms", symbol, period="1h")
    start_ms = max(floor, (max_seen + 1) if max_seen is not None else floor)
    inserted = 0

    while start_ms <= end_ms:
        window_end = min(start_ms + OI_WINDOW_MS - 1, end_ms)
        data = fetch_json(
            session,
            "/futures/data/openInterestHist",
            {
                "symbol": symbol,
                "period": "1h",
                "startTime": start_ms,
                "endTime": window_end,
                "limit": OI_LIMIT,
            },
        )
        if not data:
            break
        inserted += insert_oi(con, symbol, data)
        last_ts = int(data[-1]["timestamp"])
        next_start = last_ts + 1
        if next_start <= start_ms:
            break
        start_ms = next_start

    return inserted


def process_symbol(con: sqlite3.Connection, session: Any, symbol: str, end_ms: int) -> tuple[int, int, int]:
    n_klines = pull_klines(con, session, symbol, end_ms)
    n_funding = pull_funding(con, session, symbol, end_ms)
    n_oi = pull_oi(con, session, symbol, end_ms)
    con.commit()
    log(
        "INFO",
        f"completed {symbol}: n_klines={n_klines} n_funding={n_funding} n_oi={n_oi}",
    )
    return n_klines, n_funding, n_oi


def count_table(con: sqlite3.Connection, table: str) -> tuple[int, int]:
    symbol_column = "symbol"
    row = con.execute(f"SELECT COUNT(*), COUNT(DISTINCT {symbol_column}) FROM {table}").fetchone()
    return int(row[0]), int(row[1])


def print_verification(con: sqlite3.Connection) -> None:
    print("VERIFICATION QUERY OUTPUT:")
    print("klines:", con.execute("SELECT COUNT(*), COUNT(DISTINCT symbol) FROM klines_1m").fetchall())
    print("funding:", con.execute("SELECT COUNT(*), COUNT(DISTINCT symbol) FROM funding_rate").fetchall())
    print("oi:", con.execute("SELECT COUNT(*), COUNT(DISTINCT symbol) FROM open_interest_hist").fetchall())


def main() -> int:
    start_time = time.monotonic()
    symbols = load_symbols()
    failures: list[str] = []
    processed = 0
    systemic_blocker: str | None = None

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    log("INFO", f"starting Binance extended history pull: symbols={len(symbols)} db={DB_PATH}")

    con = connect_db()
    init_schema(con)
    session = requests.Session()
    session.headers.update({"User-Agent": "BWE-binance-extended-history/1.0"})
    batch_end_ms = now_ms()

    for idx, symbol in enumerate(symbols, start=1):
        log("INFO", f"processing {idx}/{len(symbols)} {symbol}")
        try:
            process_symbol(con, session, symbol, batch_end_ms)
            processed += 1
        except InvalidSymbolError as exc:
            con.rollback()
            failures.append(symbol)
            log("ERROR", f"failed {symbol}: {exc}")
            processed += 1
        except SystemicBlocker as exc:
            con.rollback()
            systemic_blocker = str(exc)
            log("ERROR", f"systemic blocker while processing {symbol}: {systemic_blocker}")
            break
        except Exception as exc:  # Continue per symbol as requested.
            con.rollback()
            failures.append(symbol)
            log("ERROR", f"failed {symbol}: {exc}\n{traceback.format_exc()}")
            processed += 1

    kline_count, _ = count_table(con, "klines_1m")
    funding_count, _ = count_table(con, "funding_rate")
    oi_count, _ = count_table(con, "open_interest_hist")
    elapsed_minutes = (time.monotonic() - start_time) / 60

    print(f"Total symbols processed: {processed} / {len(symbols)}")
    print(f"Failed symbols: {failures}")
    print(f"Total 1m bars: {kline_count}")
    print(f"Total funding records: {funding_count}")
    print(f"Total OI records: {oi_count}")
    print(f"Elapsed time: {elapsed_minutes:.2f} minutes")
    if systemic_blocker:
        print(f"Systemic blocker: {systemic_blocker}")
    print_verification(con)
    con.close()

    if systemic_blocker:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
