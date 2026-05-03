#!/usr/bin/env python3
"""Continuously collect Binance USD-M Futures 1m closed klines into SQLite.

Design goals:
- Public/read-only Binance API only.
- Start from today's UTC 00:00 for existing symbols when no cursor exists.
- Preserve every raw Binance kline field needed for minute-path replay/backtests.
- Keep SQLite in WAL mode so external backtests can read while the collector writes.
- Refresh the full symbol universe weekly and on startup; new symbols get a cursor immediately.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

import requests

DEFAULT_CONFIG_PATH = Path('/Users/ye/.hermes/scripts/binance_futures_1m_collector_config.json')
DEFAULT_RUNTIME_DIR = Path('/Users/ye/.hermes/research/binance_futures_1m_collector_runtime')
DEFAULT_DB_PATH = DEFAULT_RUNTIME_DIR / 'binance_futures_1m.sqlite3'
BINANCE_FAPI_BASE_URL = 'https://fapi.binance.com'
INTERVAL_MS = {
    '1m': 60_000,
    '3m': 3 * 60_000,
    '5m': 5 * 60_000,
    '15m': 15 * 60_000,
    '30m': 30 * 60_000,
    '1h': 60 * 60_000,
}


def now_ms() -> int:
    return int(time.time() * 1000)


def today_utc_start_ms(ts_ms: int) -> int:
    dt = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
    start = datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)
    return int(start.timestamp() * 1000)


def interval_to_ms(interval: str) -> int:
    if interval not in INTERVAL_MS:
        raise ValueError(f'unsupported interval: {interval}')
    return INTERVAL_MS[interval]


def floor_time_ms(ts_ms: int, step_ms: int) -> int:
    return int(ts_ms // step_ms * step_ms)


def latest_closed_open_time_ms(ts_ms: int, *, interval: str, close_lag_ms: int) -> int:
    step = interval_to_ms(interval)
    safe_now = max(0, int(ts_ms) - int(close_lag_ms))
    current_open = floor_time_ms(safe_now, step)
    return current_open - step


def initial_cursor_ms(*, now_ms_value: int, listing_ts_ms: int, interval: str) -> int:
    step = interval_to_ms(interval)
    start = today_utc_start_ms(now_ms_value)
    if listing_ts_ms and int(listing_ts_ms) > start:
        start = floor_time_ms(int(listing_ts_ms), step)
    return start


def default_config() -> Dict[str, Any]:
    return {
        'base_url': BINANCE_FAPI_BASE_URL,
        'runtime_dir': str(DEFAULT_RUNTIME_DIR),
        'db_path': str(DEFAULT_DB_PATH),
        'interval': '1m',
        'quote_asset': 'USDT',
        'contract_type': 'PERPETUAL',
        'symbol_status': 'TRADING',
        'fetch_limit': 500,
        'max_batches_per_symbol': 3,
        'request_sleep_seconds': 0.08,
        'poll_seconds': 60.0,
        'symbol_refresh_seconds': 7 * 24 * 60 * 60,
        'close_lag_ms': 2_000,
        'request_timeout_seconds': 20,
        'request_retries': 3,
        'request_backoff_seconds': 1.0,
        'https_proxy': '',
        'user_agent': 'Hermes-BWE-binance-futures-1m-collector/1.0',
    }


@dataclass(frozen=True)
class SymbolMeta:
    symbol: str
    pair: str
    base_asset: str
    quote_asset: str
    margin_asset: str
    contract_type: str
    status: str
    listing_ts_ms: int
    delivery_ts_ms: int
    price_precision: int
    quantity_precision: int
    first_seen_ms: int
    last_seen_ms: int
    active: bool


def discover_usdm_perpetual_symbols(exchange_info: Dict[str, Any], *, now_ms: int, quote_asset: str = 'USDT') -> List[SymbolMeta]:
    out: List[SymbolMeta] = []
    for item in exchange_info.get('symbols') or []:
        if str(item.get('status') or '').upper() != 'TRADING':
            continue
        if str(item.get('contractType') or '').upper() != 'PERPETUAL':
            continue
        if str(item.get('quoteAsset') or '').upper() != quote_asset.upper():
            continue
        if str(item.get('marginAsset') or '').upper() != quote_asset.upper():
            continue
        symbol = str(item.get('symbol') or '').upper()
        if not symbol:
            continue
        out.append(SymbolMeta(
            symbol=symbol,
            pair=str(item.get('pair') or symbol).upper(),
            base_asset=str(item.get('baseAsset') or '').upper(),
            quote_asset=str(item.get('quoteAsset') or '').upper(),
            margin_asset=str(item.get('marginAsset') or '').upper(),
            contract_type=str(item.get('contractType') or '').upper(),
            status=str(item.get('status') or '').upper(),
            listing_ts_ms=int(item.get('onboardDate') or item.get('onboard_date') or 0),
            delivery_ts_ms=int(item.get('deliveryDate') or item.get('delivery_date') or 0),
            price_precision=int(item.get('pricePrecision') or 0),
            quantity_precision=int(item.get('quantityPrecision') or 0),
            first_seen_ms=int(now_ms),
            last_seen_ms=int(now_ms),
            active=True,
        ))
    out.sort(key=lambda x: x.symbol)
    return out


def normalize_kline(raw: List[Any], *, meta: SymbolMeta, interval: str, collected_at_ms: int) -> Dict[str, Any]:
    if len(raw) < 12:
        raise ValueError(f'Binance kline payload too short: {raw!r}')
    return {
        'symbol': meta.symbol,
        'interval': interval,
        'open_time_ms': int(raw[0]),
        'open': float(raw[1]),
        'high': float(raw[2]),
        'low': float(raw[3]),
        'close': float(raw[4]),
        'volume': float(raw[5]),
        'close_time_ms': int(raw[6]),
        'quote_volume': float(raw[7]),
        'trade_count': int(raw[8]),
        'taker_buy_base_volume': float(raw[9]),
        'taker_buy_quote_volume': float(raw[10]),
        'ignore_value': str(raw[11]),
        'contract_type': meta.contract_type,
        'status': meta.status,
        'listing_ts_ms': int(meta.listing_ts_ms or 0),
        'collected_at_ms': int(collected_at_ms),
        'raw_json': json.dumps(raw, ensure_ascii=False, separators=(',', ':')),
    }


class CollectorStore:
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), timeout=30)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        cur = self.conn.cursor()
        cur.execute('PRAGMA journal_mode=WAL')
        cur.execute('PRAGMA synchronous=NORMAL')
        cur.execute('PRAGMA busy_timeout=5000')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS symbol_meta (
                symbol TEXT PRIMARY KEY,
                pair TEXT,
                base_asset TEXT,
                quote_asset TEXT,
                margin_asset TEXT,
                contract_type TEXT,
                status TEXT,
                listing_ts_ms INTEGER,
                delivery_ts_ms INTEGER,
                price_precision INTEGER,
                quantity_precision INTEGER,
                first_seen_ms INTEGER,
                last_seen_ms INTEGER,
                active INTEGER NOT NULL DEFAULT 1
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS collector_state (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at_ms INTEGER
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS klines_1m (
                symbol TEXT NOT NULL,
                interval TEXT NOT NULL,
                open_time_ms INTEGER NOT NULL,
                close_time_ms INTEGER NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume REAL NOT NULL,
                quote_volume REAL NOT NULL,
                trade_count INTEGER NOT NULL,
                taker_buy_base_volume REAL NOT NULL,
                taker_buy_quote_volume REAL NOT NULL,
                ignore_value TEXT,
                contract_type TEXT,
                status TEXT,
                listing_ts_ms INTEGER,
                collected_at_ms INTEGER NOT NULL,
                raw_json TEXT,
                PRIMARY KEY (symbol, interval, open_time_ms)
            )
        ''')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_klines_1m_symbol_open_time ON klines_1m(symbol, open_time_ms)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_klines_1m_open_time ON klines_1m(open_time_ms)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_klines_1m_interval_symbol_time ON klines_1m(interval, symbol, open_time_ms)')
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    @staticmethod
    def _cursor_key(symbol: str, interval: str) -> str:
        return f'cursor:{interval}:{symbol}'

    def get_state(self, key: str) -> Optional[str]:
        row = self.conn.execute('SELECT value FROM collector_state WHERE key = ?', (key,)).fetchone()
        return None if row is None else str(row['value'])

    def set_state(self, key: str, value: Any, updated_at_ms: Optional[int] = None) -> None:
        ts = int(updated_at_ms if updated_at_ms is not None else now_ms())
        self.conn.execute(
            'INSERT INTO collector_state(key, value, updated_at_ms) VALUES (?, ?, ?) '
            'ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at_ms = excluded.updated_at_ms',
            (key, str(value), ts),
        )
        self.conn.commit()

    def get_cursor(self, symbol: str, interval: str) -> Optional[int]:
        value = self.get_state(self._cursor_key(symbol, interval))
        return None if value is None else int(value)

    def set_cursor(self, symbol: str, interval: str, cursor_ms: int) -> None:
        self.set_state(self._cursor_key(symbol, interval), int(cursor_ms))

    def upsert_symbols(self, symbols: Iterable[SymbolMeta], *, interval: str, today_start_ms: int) -> None:
        step = interval_to_ms(interval)
        for meta in symbols:
            existing = self.conn.execute('SELECT first_seen_ms FROM symbol_meta WHERE symbol = ?', (meta.symbol,)).fetchone()
            first_seen_ms = int(existing['first_seen_ms']) if existing is not None and existing['first_seen_ms'] else int(meta.first_seen_ms)
            self.conn.execute('''
                INSERT INTO symbol_meta(
                    symbol, pair, base_asset, quote_asset, margin_asset, contract_type, status,
                    listing_ts_ms, delivery_ts_ms, price_precision, quantity_precision,
                    first_seen_ms, last_seen_ms, active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    pair = excluded.pair,
                    base_asset = excluded.base_asset,
                    quote_asset = excluded.quote_asset,
                    margin_asset = excluded.margin_asset,
                    contract_type = excluded.contract_type,
                    status = excluded.status,
                    listing_ts_ms = excluded.listing_ts_ms,
                    delivery_ts_ms = excluded.delivery_ts_ms,
                    price_precision = excluded.price_precision,
                    quantity_precision = excluded.quantity_precision,
                    last_seen_ms = excluded.last_seen_ms,
                    active = excluded.active
            ''', (
                meta.symbol, meta.pair, meta.base_asset, meta.quote_asset, meta.margin_asset, meta.contract_type, meta.status,
                int(meta.listing_ts_ms or 0), int(meta.delivery_ts_ms or 0), int(meta.price_precision), int(meta.quantity_precision),
                first_seen_ms, int(meta.last_seen_ms), 1 if meta.active else 0,
            ))
            if self.get_cursor(meta.symbol, interval) is None:
                cursor = max(int(today_start_ms), floor_time_ms(int(meta.listing_ts_ms or 0), step) if meta.listing_ts_ms else int(today_start_ms))
                self.conn.execute(
                    'INSERT OR IGNORE INTO collector_state(key, value, updated_at_ms) VALUES (?, ?, ?)',
                    (self._cursor_key(meta.symbol, interval), str(cursor), int(meta.last_seen_ms)),
                )
        self.conn.commit()

    def deactivate_missing_symbols(self, active_symbols: Iterable[str], *, now_ms_value: int) -> None:
        active_set = {str(s).upper() for s in active_symbols}
        rows = self.conn.execute('SELECT symbol FROM symbol_meta WHERE active = 1').fetchall()
        for row in rows:
            symbol = str(row['symbol'])
            if symbol not in active_set:
                self.conn.execute('UPDATE symbol_meta SET active = 0, last_seen_ms = ? WHERE symbol = ?', (int(now_ms_value), symbol))
        self.conn.commit()

    def list_active_symbols(self, *, limit: Optional[int] = None) -> List[SymbolMeta]:
        sql = 'SELECT * FROM symbol_meta WHERE active = 1 ORDER BY symbol'
        params: tuple[Any, ...] = ()
        if limit is not None:
            sql += ' LIMIT ?'
            params = (int(limit),)
        rows = self.conn.execute(sql, params).fetchall()
        return [SymbolMeta(
            symbol=str(r['symbol']),
            pair=str(r['pair'] or r['symbol']),
            base_asset=str(r['base_asset'] or ''),
            quote_asset=str(r['quote_asset'] or ''),
            margin_asset=str(r['margin_asset'] or ''),
            contract_type=str(r['contract_type'] or ''),
            status=str(r['status'] or ''),
            listing_ts_ms=int(r['listing_ts_ms'] or 0),
            delivery_ts_ms=int(r['delivery_ts_ms'] or 0),
            price_precision=int(r['price_precision'] or 0),
            quantity_precision=int(r['quantity_precision'] or 0),
            first_seen_ms=int(r['first_seen_ms'] or 0),
            last_seen_ms=int(r['last_seen_ms'] or 0),
            active=bool(r['active']),
        ) for r in rows]

    def upsert_klines(self, rows: Iterable[Dict[str, Any]]) -> int:
        inserted = 0
        max_cursor: Dict[tuple[str, str], int] = {}
        for row in rows:
            cur = self.conn.execute('''
                INSERT OR IGNORE INTO klines_1m(
                    symbol, interval, open_time_ms, close_time_ms, open, high, low, close, volume,
                    quote_volume, trade_count, taker_buy_base_volume, taker_buy_quote_volume,
                    ignore_value, contract_type, status, listing_ts_ms, collected_at_ms, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                row['symbol'], row['interval'], int(row['open_time_ms']), int(row['close_time_ms']),
                float(row['open']), float(row['high']), float(row['low']), float(row['close']), float(row['volume']),
                float(row['quote_volume']), int(row['trade_count']), float(row['taker_buy_base_volume']), float(row['taker_buy_quote_volume']),
                row.get('ignore_value'), row.get('contract_type'), row.get('status'), int(row.get('listing_ts_ms') or 0),
                int(row['collected_at_ms']), row.get('raw_json'),
            ))
            if cur.rowcount == 1:
                inserted += 1
            key = (str(row['symbol']), str(row['interval']))
            next_cursor = int(row['open_time_ms']) + interval_to_ms(str(row['interval']))
            max_cursor[key] = max(max_cursor.get(key, 0), next_cursor)
        ts = now_ms()
        for (symbol, interval), cursor in max_cursor.items():
            current = self.get_cursor(symbol, interval)
            if current is None or int(cursor) > int(current):
                self.conn.execute(
                    'INSERT INTO collector_state(key, value, updated_at_ms) VALUES (?, ?, ?) '
                    'ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at_ms = excluded.updated_at_ms',
                    (self._cursor_key(symbol, interval), str(int(cursor)), ts),
                )
        self.conn.commit()
        return inserted

    def count_klines(self) -> int:
        return int(self.conn.execute('SELECT COUNT(*) AS n FROM klines_1m').fetchone()['n'])

    def summary(self) -> Dict[str, Any]:
        symbols = int(self.conn.execute('SELECT COUNT(*) AS n FROM symbol_meta WHERE active = 1').fetchone()['n'])
        rows = self.count_klines()
        minmax = self.conn.execute('SELECT MIN(open_time_ms) AS min_ts, MAX(open_time_ms) AS max_ts FROM klines_1m').fetchone()
        return {
            'db_path': str(self.db_path),
            'active_symbols': symbols,
            'kline_rows': rows,
            'min_open_time_ms': minmax['min_ts'],
            'max_open_time_ms': minmax['max_ts'],
            'last_symbol_refresh_ms': self.get_state('last_symbol_refresh_ms'),
        }


class BinanceFuturesPublicClient:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.base_url = str(config.get('base_url') or BINANCE_FAPI_BASE_URL).rstrip('/')
        self.session = requests.Session()
        # Ignore process/macOS proxy environment by default; explicit config https_proxy is still honored.
        self.session.trust_env = False
        self.session.headers.update({'User-Agent': str(config.get('user_agent') or default_config()['user_agent'])})
        https_proxy = str(config.get('https_proxy') or '').strip()
        if https_proxy:
            self.session.proxies.update({'http': https_proxy, 'https': https_proxy})

    def _get_json(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        timeout = float(self.config.get('request_timeout_seconds', 20))
        retries = int(self.config.get('request_retries', 3))
        backoff = float(self.config.get('request_backoff_seconds', 1.0))
        last_error: Optional[Exception] = None
        for attempt in range(max(1, retries)):
            try:
                resp = self.session.get(f'{self.base_url}{path}', params=params or {}, timeout=timeout)
                resp.raise_for_status()
                return resp.json()
            except Exception as exc:
                last_error = exc
                if attempt < retries - 1:
                    time.sleep(backoff * (2 ** attempt))
        raise RuntimeError(f'Binance public GET failed path={path} params={params}: {last_error}')

    def exchange_info(self) -> Dict[str, Any]:
        return self._get_json('/fapi/v1/exchangeInfo')

    def klines(self, *, symbol: str, interval: str, start_time_ms: int, end_time_ms: int, limit: int) -> List[List[Any]]:
        params = {
            'symbol': symbol,
            'interval': interval,
            'startTime': int(start_time_ms),
            'endTime': int(end_time_ms),
            'limit': int(limit),
        }
        payload = self._get_json('/fapi/v1/klines', params=params)
        if not isinstance(payload, list):
            raise RuntimeError(f'unexpected kline payload for {symbol}: {payload!r}')
        return payload


class BinanceFutures1mCollector:
    def __init__(
        self,
        *,
        config: Dict[str, Any],
        store: CollectorStore,
        client: Any,
        now_ms_fn: Callable[[], int] = now_ms,
    ):
        self.config = config
        self.store = store
        self.client = client
        self.now_ms_fn = now_ms_fn

    @property
    def interval(self) -> str:
        return str(self.config.get('interval') or '1m')

    def refresh_symbols(self) -> int:
        ts = int(self.now_ms_fn())
        payload = self.client.exchange_info()
        symbols = discover_usdm_perpetual_symbols(
            payload,
            now_ms=ts,
            quote_asset=str(self.config.get('quote_asset') or 'USDT'),
        )
        self.store.upsert_symbols(symbols, interval=self.interval, today_start_ms=today_utc_start_ms(ts))
        self.store.deactivate_missing_symbols([s.symbol for s in symbols], now_ms_value=ts)
        self.store.set_state('last_symbol_refresh_ms', ts, updated_at_ms=ts)
        return len(symbols)

    def _symbol_refresh_due(self) -> bool:
        last = self.store.get_state('last_symbol_refresh_ms')
        if last is None:
            return True
        interval_s = int(self.config.get('symbol_refresh_seconds', 7 * 24 * 60 * 60))
        return (int(self.now_ms_fn()) - int(last)) >= interval_s * 1000

    def run_once(self, *, force_symbol_refresh: bool = False, max_symbols: Optional[int] = None) -> Dict[str, Any]:
        started = int(self.now_ms_fn())
        refreshed_symbols: Optional[int] = None
        if force_symbol_refresh or self._symbol_refresh_due():
            refreshed_symbols = self.refresh_symbols()
        symbols = self.store.list_active_symbols(limit=max_symbols)
        interval = self.interval
        step = interval_to_ms(interval)
        close_lag_ms = int(self.config.get('close_lag_ms', 2_000))
        end_open = latest_closed_open_time_ms(int(self.now_ms_fn()), interval=interval, close_lag_ms=close_lag_ms)
        limit = int(self.config.get('fetch_limit', 500))
        max_batches = int(self.config.get('max_batches_per_symbol', 3))
        sleep_s = float(self.config.get('request_sleep_seconds', 0.08))
        inserted_total = 0
        fetched_total = 0
        errors: List[Dict[str, str]] = []
        processed_symbols = 0
        for meta in symbols:
            processed_symbols += 1
            cursor = self.store.get_cursor(meta.symbol, interval)
            if cursor is None:
                cursor = initial_cursor_ms(now_ms_value=int(self.now_ms_fn()), listing_ts_ms=meta.listing_ts_ms, interval=interval)
                self.store.set_cursor(meta.symbol, interval, cursor)
            if cursor > end_open:
                continue
            for _batch in range(max_batches):
                if cursor > end_open:
                    break
                try:
                    raw_rows = self.client.klines(
                        symbol=meta.symbol,
                        interval=interval,
                        start_time_ms=int(cursor),
                        end_time_ms=int(end_open),
                        limit=limit,
                    )
                except Exception as exc:
                    errors.append({'symbol': meta.symbol, 'error': str(exc)[:500]})
                    break
                if not raw_rows:
                    break
                collected_at = int(self.now_ms_fn())
                normalized = []
                max_next = int(cursor)
                for raw in raw_rows:
                    try:
                        row = normalize_kline(raw, meta=meta, interval=interval, collected_at_ms=collected_at)
                    except Exception as exc:
                        errors.append({'symbol': meta.symbol, 'error': f'normalize: {exc}'[:500]})
                        continue
                    if int(row['close_time_ms']) > collected_at - close_lag_ms:
                        continue
                    if int(row['open_time_ms']) < int(cursor):
                        continue
                    normalized.append(row)
                    max_next = max(max_next, int(row['open_time_ms']) + step)
                advanced = max_next > int(cursor)
                if normalized:
                    inserted_total += self.store.upsert_klines(normalized)
                    fetched_total += len(normalized)
                    cursor = max_next
                if len(raw_rows) < limit or not advanced:
                    break
                if sleep_s > 0:
                    time.sleep(sleep_s)
            if sleep_s > 0:
                time.sleep(sleep_s)
        result = {
            'ts_ms': int(self.now_ms_fn()),
            'duration_ms': int(self.now_ms_fn()) - started,
            'symbols': len(symbols),
            'processed_symbols': processed_symbols,
            'refreshed_symbols': refreshed_symbols,
            'fetched_rows': fetched_total,
            'inserted_rows': inserted_total,
            'errors_count': len(errors),
            'errors_sample': errors[:5],
            'db_path': str(self.store.db_path),
        }
        self.store.set_state('last_run_summary_json', json.dumps(result, ensure_ascii=False), updated_at_ms=int(self.now_ms_fn()))
        return result

    def run_forever(self, *, poll_seconds: Optional[float] = None, max_symbols: Optional[int] = None) -> None:
        poll = float(poll_seconds if poll_seconds is not None else self.config.get('poll_seconds', 60.0))
        first_pass = True
        while True:
            try:
                result = self.run_once(force_symbol_refresh=first_pass, max_symbols=max_symbols)
                first_pass = False
                print(json.dumps(result, ensure_ascii=False), flush=True)
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                print(json.dumps({'ts_ms': int(self.now_ms_fn()), 'fatal_loop_error': str(exc)}, ensure_ascii=False), flush=True)
            time.sleep(max(1.0, poll))


def deep_merge(base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(path: Optional[Path]) -> Dict[str, Any]:
    cfg = default_config()
    if path and path.exists():
        cfg = deep_merge(cfg, json.loads(path.read_text(encoding='utf-8')))
    runtime_dir = Path(str(cfg.get('runtime_dir') or DEFAULT_RUNTIME_DIR)).expanduser()
    cfg['runtime_dir'] = str(runtime_dir)
    if not cfg.get('db_path'):
        cfg['db_path'] = str(runtime_dir / 'binance_futures_1m.sqlite3')
    cfg['db_path'] = str(Path(str(cfg['db_path'])).expanduser())
    return cfg


def build_collector(config: Dict[str, Any]) -> BinanceFutures1mCollector:
    runtime_dir = Path(str(config.get('runtime_dir') or DEFAULT_RUNTIME_DIR))
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / 'logs').mkdir(parents=True, exist_ok=True)
    store = CollectorStore(Path(str(config.get('db_path') or runtime_dir / 'binance_futures_1m.sqlite3')))
    client = BinanceFuturesPublicClient(config)
    return BinanceFutures1mCollector(config=config, store=store, client=client)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description='Binance USD-M Futures 1m kline collector')
    ap.add_argument('--config', type=Path, default=DEFAULT_CONFIG_PATH)
    ap.add_argument('--runtime-dir', type=Path)
    ap.add_argument('--db-path', type=Path)
    ap.add_argument('--once', action='store_true', help='Run one polling pass and exit')
    ap.add_argument('--bootstrap-symbols', action='store_true', help='Refresh symbols and exit')
    ap.add_argument('--force-symbol-refresh', action='store_true')
    ap.add_argument('--status', action='store_true', help='Print DB summary and exit')
    ap.add_argument('--max-symbols', type=int, help='Limit symbols for validation/testing')
    ap.add_argument('--poll-seconds', type=float)
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    if args.runtime_dir:
        cfg['runtime_dir'] = str(args.runtime_dir)
        if not args.db_path:
            cfg['db_path'] = str(args.runtime_dir / 'binance_futures_1m.sqlite3')
    if args.db_path:
        cfg['db_path'] = str(args.db_path)
    collector = build_collector(cfg)
    try:
        if args.status:
            print(json.dumps(collector.store.summary(), ensure_ascii=False, indent=2))
            return 0
        if args.bootstrap_symbols:
            count = collector.refresh_symbols()
            print(json.dumps({'refreshed_symbols': count, **collector.store.summary()}, ensure_ascii=False, indent=2))
            return 0
        if args.once:
            result = collector.run_once(force_symbol_refresh=args.force_symbol_refresh, max_symbols=args.max_symbols)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        collector.run_forever(poll_seconds=args.poll_seconds, max_symbols=args.max_symbols)
        return 0
    finally:
        collector.store.close()


if __name__ == '__main__':
    raise SystemExit(main())
