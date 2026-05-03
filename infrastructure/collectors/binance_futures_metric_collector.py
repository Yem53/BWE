#!/usr/bin/env python3
"""Collect extended Binance USD-M Futures public market metrics into the kline SQLite DB.

This companion collector intentionally does not place orders or use private endpoints.
It shares the existing research DB used by binance_futures_1m_collector.py and adds
long-lived truth tables for funding, mark price, premium index, OI, long/short ratios,
taker flow, and perpetual basis.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import binance_futures_1m_collector as core  # noqa: E402

DAY_MS = 24 * 60 * 60 * 1000
DEFAULT_RUNTIME_DIR = Path('/Users/ye/.hermes/research/binance_futures_1m_collector_runtime')
DEFAULT_DB_PATH = DEFAULT_RUNTIME_DIR / 'binance_futures_1m.sqlite3'
DEFAULT_CONFIG_PATH = Path('/Users/ye/.hermes/scripts/binance_futures_metric_collector_config.json')
PRICE_KLINE_METRICS = {'mark_price_1m', 'premium_index_1m'}
RATIO_METRICS = {
    'global_long_short_account_ratio_5m',
    'top_trader_long_short_account_ratio_5m',
    'top_trader_long_short_position_ratio_5m',
}


@dataclass(frozen=True)
class MetricSpec:
    name: str
    table: str
    period_ms: int
    limit_key: str
    default_limit: int


METRIC_SPECS: Dict[str, MetricSpec] = {
    'mark_price_1m': MetricSpec('mark_price_1m', 'mark_price_1m', 60_000, 'fetch_limit_1m', 500),
    'premium_index_1m': MetricSpec('premium_index_1m', 'premium_index_1m', 60_000, 'fetch_limit_1m', 500),
    'funding_rate': MetricSpec('funding_rate', 'funding_rate', 8 * 60 * 60_000, 'funding_fetch_limit', 1000),
    'open_interest_5m': MetricSpec('open_interest_5m', 'open_interest_5m', 5 * 60_000, 'fetch_limit_5m', 500),
    'global_long_short_account_ratio_5m': MetricSpec('global_long_short_account_ratio_5m', 'global_long_short_account_ratio_5m', 5 * 60_000, 'fetch_limit_5m', 500),
    'top_trader_long_short_account_ratio_5m': MetricSpec('top_trader_long_short_account_ratio_5m', 'top_trader_long_short_account_ratio_5m', 5 * 60_000, 'fetch_limit_5m', 500),
    'top_trader_long_short_position_ratio_5m': MetricSpec('top_trader_long_short_position_ratio_5m', 'top_trader_long_short_position_ratio_5m', 5 * 60_000, 'fetch_limit_5m', 500),
    'taker_buy_sell_volume_5m': MetricSpec('taker_buy_sell_volume_5m', 'taker_buy_sell_volume_5m', 5 * 60_000, 'fetch_limit_5m', 500),
    'basis_perpetual_5m': MetricSpec('basis_perpetual_5m', 'basis_perpetual_5m', 5 * 60_000, 'fetch_limit_5m', 500),
}

DEFAULT_METRICS = {name: True for name in METRIC_SPECS}


def now_ms() -> int:
    return int(time.time() * 1000)


def default_config() -> Dict[str, Any]:
    return {
        'base_url': core.BINANCE_FAPI_BASE_URL,
        'runtime_dir': str(DEFAULT_RUNTIME_DIR),
        'db_path': str(DEFAULT_DB_PATH),
        'quote_asset': 'USDT',
        'symbol_refresh_seconds': 3600,
        'bootstrap_backfill_days_new_symbol': 3,
        'bootstrap_backfill_days_existing_symbol': 30,
        'bootstrap_backfill_hours_price_1m': 12,
        'bootstrap_backfill_days_basis': 3,
        'fetch_limit_1m': 500,
        'fetch_limit_5m': 500,
        'funding_fetch_limit': 1000,
        'max_batches_per_metric_per_symbol': 1,
        'request_sleep_seconds': 0.08,
        'request_timeout_seconds': 20,
        'request_retries': 3,
        'request_backoff_seconds': 1.0,
        'empty_backoff_seconds': 30 * 60,
        'close_lag_ms': 5_000,
        'https_proxy': '',
        'user_agent': 'Hermes-BWE-binance-futures-metric-collector/1.0',
        'metrics': dict(DEFAULT_METRICS),
    }


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
    cfg['metrics'] = deep_merge(dict(DEFAULT_METRICS), dict(cfg.get('metrics') or {}))
    return cfg


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == '':
        return None
    try:
        return float(value)
    except Exception:
        return None


def _to_int(value: Any) -> int:
    if value is None or value == '':
        return 0
    return int(float(value))


def _raw_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(',', ':'))


def _floor(ts_ms: int, step_ms: int) -> int:
    return int(ts_ms // step_ms * step_ms)


def _latest_closed_ts(now_ms_value: int, step_ms: int, close_lag_ms: int) -> int:
    safe_now = max(0, int(now_ms_value) - int(close_lag_ms))
    current_open = _floor(safe_now, step_ms)
    return current_open - step_ms


def metric_initial_cursor(meta: core.SymbolMeta, metric: str, *, now_ms_value: int, config: Dict[str, Any]) -> int:
    spec = METRIC_SPECS[metric]
    listing_ts = int(meta.listing_ts_ms or 0)
    if metric in PRICE_KLINE_METRICS:
        backfill_ms = int(float(config.get('bootstrap_backfill_hours_price_1m', 12))) * 60 * 60 * 1000
    elif metric == 'basis_perpetual_5m':
        backfill_ms = int(config.get('bootstrap_backfill_days_basis', 3)) * DAY_MS
    else:
        new_days = int(config.get('bootstrap_backfill_days_new_symbol', 3))
        existing_days = int(config.get('bootstrap_backfill_days_existing_symbol', 30))
        if listing_ts and listing_ts >= int(now_ms_value) - new_days * DAY_MS:
            backfill_ms = new_days * DAY_MS
        else:
            backfill_ms = existing_days * DAY_MS
    cursor = int(now_ms_value) - int(backfill_ms)
    if listing_ts:
        cursor = max(cursor, listing_ts)
    return _floor(cursor, spec.period_ms)


def normalize_price_kline(metric: str, raw: Sequence[Any], *, symbol: str, collected_at_ms: int) -> Dict[str, Any]:
    if len(raw) < 7:
        raise ValueError(f'{metric} kline payload too short: {raw!r}')
    return {
        'symbol': str(symbol).upper(),
        'ts_ms': int(raw[0]),
        'interval': '1m',
        'close_time_ms': int(raw[6]),
        'open': _to_float(raw[1]),
        'high': _to_float(raw[2]),
        'low': _to_float(raw[3]),
        'close': _to_float(raw[4]),
        'volume': _to_float(raw[5]) if len(raw) > 5 else None,
        'quote_volume': _to_float(raw[7]) if len(raw) > 7 else None,
        'trade_count': _to_int(raw[8]) if len(raw) > 8 else None,
        'collected_at_ms': int(collected_at_ms),
        'raw_json': _raw_json(list(raw)),
    }


def normalize_funding_rate(raw: Dict[str, Any], *, collected_at_ms: int) -> Dict[str, Any]:
    return {
        'symbol': str(raw.get('symbol') or '').upper(),
        'ts_ms': _to_int(raw.get('fundingTime')),
        'funding_rate': _to_float(raw.get('fundingRate')),
        'mark_price': _to_float(raw.get('markPrice')),
        'collected_at_ms': int(collected_at_ms),
        'raw_json': _raw_json(raw),
    }


def normalize_open_interest(raw: Dict[str, Any], *, collected_at_ms: int) -> Dict[str, Any]:
    return {
        'symbol': str(raw.get('symbol') or '').upper(),
        'ts_ms': _to_int(raw.get('timestamp')),
        'sum_open_interest': _to_float(raw.get('sumOpenInterest')),
        'sum_open_interest_value': _to_float(raw.get('sumOpenInterestValue')),
        'collected_at_ms': int(collected_at_ms),
        'raw_json': _raw_json(raw),
    }


def normalize_long_short_ratio(metric: str, raw: Dict[str, Any], *, collected_at_ms: int) -> Dict[str, Any]:
    long_value = raw.get('longAccount', raw.get('longPosition'))
    short_value = raw.get('shortAccount', raw.get('shortPosition'))
    return {
        'symbol': str(raw.get('symbol') or '').upper(),
        'ts_ms': _to_int(raw.get('timestamp')),
        'long_short_ratio': _to_float(raw.get('longShortRatio')),
        'long_account': _to_float(long_value),
        'short_account': _to_float(short_value),
        'collected_at_ms': int(collected_at_ms),
        'raw_json': _raw_json(raw),
    }


def normalize_taker_buy_sell(raw: Dict[str, Any], *, collected_at_ms: int) -> Dict[str, Any]:
    return {
        'symbol': str(raw.get('symbol') or '').upper(),
        'ts_ms': _to_int(raw.get('timestamp')),
        'buy_sell_ratio': _to_float(raw.get('buySellRatio')),
        'buy_vol': _to_float(raw.get('buyVol')),
        'sell_vol': _to_float(raw.get('sellVol')),
        'collected_at_ms': int(collected_at_ms),
        'raw_json': _raw_json(raw),
    }


def normalize_basis(raw: Dict[str, Any], *, symbol: str, collected_at_ms: int) -> Dict[str, Any]:
    return {
        'symbol': str(symbol or raw.get('symbol') or raw.get('pair') or '').upper(),
        'ts_ms': _to_int(raw.get('timestamp')),
        'pair': str(raw.get('pair') or symbol or '').upper(),
        'contract_type': str(raw.get('contractType') or 'PERPETUAL').upper(),
        'basis': _to_float(raw.get('basis')),
        'basis_rate': _to_float(raw.get('basisRate')),
        'index_price': _to_float(raw.get('indexPrice')),
        'futures_price': _to_float(raw.get('futuresPrice')),
        'annualized_basis_rate': _to_float(raw.get('annualizedBasisRate')),
        'collected_at_ms': int(collected_at_ms),
        'raw_json': _raw_json(raw),
    }


class MetricCollectorStore(core.CollectorStore):
    METRIC_TABLES = set(METRIC_SPECS) | {'collector_health'}

    def _init_db(self) -> None:  # type: ignore[override]
        super()._init_db()
        cur = self.conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS mark_price_1m (
                symbol TEXT NOT NULL,
                ts_ms INTEGER NOT NULL,
                interval TEXT,
                close_time_ms INTEGER,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                quote_volume REAL,
                trade_count INTEGER,
                collected_at_ms INTEGER NOT NULL,
                raw_json TEXT,
                PRIMARY KEY(symbol, ts_ms)
            )
        ''')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_mark_price_1m_symbol_ts ON mark_price_1m(symbol, ts_ms)')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS premium_index_1m (
                symbol TEXT NOT NULL,
                ts_ms INTEGER NOT NULL,
                interval TEXT,
                close_time_ms INTEGER,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                quote_volume REAL,
                trade_count INTEGER,
                collected_at_ms INTEGER NOT NULL,
                raw_json TEXT,
                PRIMARY KEY(symbol, ts_ms)
            )
        ''')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_premium_index_1m_symbol_ts ON premium_index_1m(symbol, ts_ms)')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS funding_rate (
                symbol TEXT NOT NULL,
                ts_ms INTEGER NOT NULL,
                funding_rate REAL,
                mark_price REAL,
                collected_at_ms INTEGER NOT NULL,
                raw_json TEXT,
                PRIMARY KEY(symbol, ts_ms)
            )
        ''')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_funding_rate_symbol_ts ON funding_rate(symbol, ts_ms)')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS open_interest_5m (
                symbol TEXT NOT NULL,
                ts_ms INTEGER NOT NULL,
                sum_open_interest REAL,
                sum_open_interest_value REAL,
                collected_at_ms INTEGER NOT NULL,
                raw_json TEXT,
                PRIMARY KEY(symbol, ts_ms)
            )
        ''')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_open_interest_5m_symbol_ts ON open_interest_5m(symbol, ts_ms)')
        for table in [
            'global_long_short_account_ratio_5m',
            'top_trader_long_short_account_ratio_5m',
            'top_trader_long_short_position_ratio_5m',
        ]:
            cur.execute(f'''
                CREATE TABLE IF NOT EXISTS {table} (
                    symbol TEXT NOT NULL,
                    ts_ms INTEGER NOT NULL,
                    long_short_ratio REAL,
                    long_account REAL,
                    short_account REAL,
                    collected_at_ms INTEGER NOT NULL,
                    raw_json TEXT,
                    PRIMARY KEY(symbol, ts_ms)
                )
            ''')
            cur.execute(f'CREATE INDEX IF NOT EXISTS idx_{table}_symbol_ts ON {table}(symbol, ts_ms)')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS taker_buy_sell_volume_5m (
                symbol TEXT NOT NULL,
                ts_ms INTEGER NOT NULL,
                buy_sell_ratio REAL,
                buy_vol REAL,
                sell_vol REAL,
                collected_at_ms INTEGER NOT NULL,
                raw_json TEXT,
                PRIMARY KEY(symbol, ts_ms)
            )
        ''')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_taker_buy_sell_volume_5m_symbol_ts ON taker_buy_sell_volume_5m(symbol, ts_ms)')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS basis_perpetual_5m (
                symbol TEXT NOT NULL,
                ts_ms INTEGER NOT NULL,
                pair TEXT,
                contract_type TEXT,
                basis REAL,
                basis_rate REAL,
                index_price REAL,
                futures_price REAL,
                annualized_basis_rate REAL,
                collected_at_ms INTEGER NOT NULL,
                raw_json TEXT,
                PRIMARY KEY(symbol, ts_ms)
            )
        ''')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_basis_perpetual_5m_symbol_ts ON basis_perpetual_5m(symbol, ts_ms)')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS collector_metric_state (
                metric TEXT NOT NULL,
                symbol TEXT NOT NULL,
                cursor_ms INTEGER,
                last_success_ms INTEGER,
                last_error_ms INTEGER,
                error_count INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                last_empty_ms INTEGER,
                rows_fetched INTEGER NOT NULL DEFAULT 0,
                rows_inserted INTEGER NOT NULL DEFAULT 0,
                updated_at_ms INTEGER,
                PRIMARY KEY(metric, symbol)
            )
        ''')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_collector_metric_state_metric_cursor ON collector_metric_state(metric, cursor_ms)')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS collector_health (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_ms INTEGER NOT NULL,
                duration_ms INTEGER,
                kind TEXT,
                active_symbol_count INTEGER,
                metrics_json TEXT,
                max_lag_ms INTEGER,
                errors_count INTEGER,
                backoff_count INTEGER,
                raw_json TEXT
            )
        ''')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_collector_health_ts ON collector_health(ts_ms)')
        self.conn.commit()

    def count_rows(self, table: str) -> int:
        if table not in self.METRIC_TABLES and table not in {'klines_1m', 'symbol_meta', 'collector_state'}:
            raise ValueError(f'unsupported table: {table}')
        return int(self.conn.execute(f'SELECT COUNT(*) AS n FROM {table}').fetchone()['n'])

    def upsert_rows(self, table: str, rows: Iterable[Dict[str, Any]]) -> int:
        if table not in METRIC_SPECS:
            raise ValueError(f'unsupported metric table: {table}')
        inserted = 0
        rows = list(rows)
        for row in rows:
            if table in PRICE_KLINE_METRICS:
                cur = self.conn.execute(f'''
                    INSERT OR IGNORE INTO {table}(
                        symbol, ts_ms, interval, close_time_ms, open, high, low, close,
                        volume, quote_volume, trade_count, collected_at_ms, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    row['symbol'], int(row['ts_ms']), row.get('interval'), row.get('close_time_ms'),
                    row.get('open'), row.get('high'), row.get('low'), row.get('close'), row.get('volume'),
                    row.get('quote_volume'), row.get('trade_count'), int(row['collected_at_ms']), row.get('raw_json'),
                ))
            elif table == 'funding_rate':
                cur = self.conn.execute('''
                    INSERT OR IGNORE INTO funding_rate(
                        symbol, ts_ms, funding_rate, mark_price, collected_at_ms, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (row['symbol'], int(row['ts_ms']), row.get('funding_rate'), row.get('mark_price'), int(row['collected_at_ms']), row.get('raw_json')))
            elif table == 'open_interest_5m':
                cur = self.conn.execute('''
                    INSERT OR IGNORE INTO open_interest_5m(
                        symbol, ts_ms, sum_open_interest, sum_open_interest_value, collected_at_ms, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (row['symbol'], int(row['ts_ms']), row.get('sum_open_interest'), row.get('sum_open_interest_value'), int(row['collected_at_ms']), row.get('raw_json')))
            elif table in RATIO_METRICS:
                cur = self.conn.execute(f'''
                    INSERT OR IGNORE INTO {table}(
                        symbol, ts_ms, long_short_ratio, long_account, short_account, collected_at_ms, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (row['symbol'], int(row['ts_ms']), row.get('long_short_ratio'), row.get('long_account'), row.get('short_account'), int(row['collected_at_ms']), row.get('raw_json')))
            elif table == 'taker_buy_sell_volume_5m':
                cur = self.conn.execute('''
                    INSERT OR IGNORE INTO taker_buy_sell_volume_5m(
                        symbol, ts_ms, buy_sell_ratio, buy_vol, sell_vol, collected_at_ms, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (row['symbol'], int(row['ts_ms']), row.get('buy_sell_ratio'), row.get('buy_vol'), row.get('sell_vol'), int(row['collected_at_ms']), row.get('raw_json')))
            elif table == 'basis_perpetual_5m':
                cur = self.conn.execute('''
                    INSERT OR IGNORE INTO basis_perpetual_5m(
                        symbol, ts_ms, pair, contract_type, basis, basis_rate, index_price,
                        futures_price, annualized_basis_rate, collected_at_ms, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    row['symbol'], int(row['ts_ms']), row.get('pair'), row.get('contract_type'), row.get('basis'),
                    row.get('basis_rate'), row.get('index_price'), row.get('futures_price'),
                    row.get('annualized_basis_rate'), int(row['collected_at_ms']), row.get('raw_json'),
                ))
            else:  # pragma: no cover - table whitelist above should prevent this
                raise ValueError(f'unsupported metric table: {table}')
            if cur.rowcount == 1:
                inserted += 1
        self.conn.commit()
        return inserted

    def get_metric_state(self, metric: str, symbol: str) -> Optional[Dict[str, Any]]:
        row = self.conn.execute(
            'SELECT * FROM collector_metric_state WHERE metric = ? AND symbol = ?',
            (metric, symbol.upper()),
        ).fetchone()
        return None if row is None else dict(row)

    def get_metric_cursor(self, metric: str, symbol: str) -> Optional[int]:
        state = self.get_metric_state(metric, symbol)
        if not state or state.get('cursor_ms') is None:
            return None
        return int(state['cursor_ms'])

    def record_metric_success(self, metric: str, symbol: str, *, cursor_ms: int, rows: int, inserted: int = 0, ts_ms: Optional[int] = None) -> None:
        ts = int(ts_ms or now_ms())
        self.conn.execute('''
            INSERT INTO collector_metric_state(
                metric, symbol, cursor_ms, last_success_ms, last_error_ms, error_count,
                last_error, last_empty_ms, rows_fetched, rows_inserted, updated_at_ms
            ) VALUES (?, ?, ?, ?, NULL, 0, NULL, NULL, ?, ?, ?)
            ON CONFLICT(metric, symbol) DO UPDATE SET
                cursor_ms = excluded.cursor_ms,
                last_success_ms = excluded.last_success_ms,
                error_count = 0,
                last_error = NULL,
                rows_fetched = collector_metric_state.rows_fetched + excluded.rows_fetched,
                rows_inserted = collector_metric_state.rows_inserted + excluded.rows_inserted,
                updated_at_ms = excluded.updated_at_ms
        ''', (metric, symbol.upper(), int(cursor_ms), ts, int(rows), int(inserted), ts))
        self.conn.commit()

    def record_metric_empty(self, metric: str, symbol: str, *, ts_ms: Optional[int] = None) -> None:
        ts = int(ts_ms or now_ms())
        self.conn.execute('''
            INSERT INTO collector_metric_state(metric, symbol, cursor_ms, last_empty_ms, updated_at_ms)
            VALUES (?, ?, NULL, ?, ?)
            ON CONFLICT(metric, symbol) DO UPDATE SET
                last_empty_ms = excluded.last_empty_ms,
                updated_at_ms = excluded.updated_at_ms
        ''', (metric, symbol.upper(), ts, ts))
        self.conn.commit()

    def record_metric_error(self, metric: str, symbol: str, error: str, *, ts_ms: Optional[int] = None) -> None:
        ts = int(ts_ms or now_ms())
        self.conn.execute('''
            INSERT INTO collector_metric_state(
                metric, symbol, cursor_ms, last_error_ms, error_count, last_error, updated_at_ms
            ) VALUES (?, ?, NULL, ?, 1, ?, ?)
            ON CONFLICT(metric, symbol) DO UPDATE SET
                last_error_ms = excluded.last_error_ms,
                error_count = collector_metric_state.error_count + 1,
                last_error = excluded.last_error,
                updated_at_ms = excluded.updated_at_ms
        ''', (metric, symbol.upper(), ts, str(error)[:1000], ts))
        self.conn.commit()

    def record_health(self, summary: Dict[str, Any]) -> None:
        self.conn.execute('''
            INSERT INTO collector_health(
                ts_ms, duration_ms, kind, active_symbol_count, metrics_json,
                max_lag_ms, errors_count, backoff_count, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            int(summary.get('ts_ms') or now_ms()),
            int(summary.get('duration_ms') or 0),
            str(summary.get('kind') or 'metric_run'),
            int(summary.get('active_symbols') or 0),
            json.dumps(summary.get('metrics') or {}, ensure_ascii=False, separators=(',', ':')),
            int(summary.get('max_lag_ms') or 0),
            int(summary.get('errors_count') or 0),
            int(summary.get('backoff_count') or 0),
            json.dumps(summary, ensure_ascii=False, separators=(',', ':')),
        ))
        self.conn.commit()

    def metric_row_counts(self) -> Dict[str, int]:
        return {name: self.count_rows(name) for name in METRIC_SPECS}

    def summary(self) -> Dict[str, Any]:  # type: ignore[override]
        base = super().summary()
        base.update({
            'metric_rows': self.metric_row_counts(),
            'health_rows': self.count_rows('collector_health'),
        })
        return base


class BinanceFuturesMetricsClient(core.BinanceFuturesPublicClient):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._last_request_monotonic = 0.0
        self.backoff_count = 0

    def _rate_limit(self) -> None:
        min_gap = float(self.config.get('request_sleep_seconds', 0.0))
        if min_gap <= 0:
            return
        elapsed = time.monotonic() - self._last_request_monotonic
        if elapsed < min_gap:
            time.sleep(min_gap - elapsed)
        self._last_request_monotonic = time.monotonic()

    def _get_json(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:  # type: ignore[override]
        timeout = float(self.config.get('request_timeout_seconds', 20))
        retries = int(self.config.get('request_retries', 3))
        backoff = float(self.config.get('request_backoff_seconds', 1.0))
        last_error: Optional[Exception] = None
        for attempt in range(max(1, retries)):
            self._rate_limit()
            try:
                resp = self.session.get(f'{self.base_url}{path}', params=params or {}, timeout=timeout)
                if resp.status_code in (418, 429):
                    self.backoff_count += 1
                    retry_after = resp.headers.get('Retry-After')
                    wait_s = float(retry_after) if retry_after else backoff * (2 ** attempt) * 5
                    time.sleep(max(1.0, wait_s))
                    last_error = RuntimeError(f'HTTP {resp.status_code}: {resp.text[:300]}')
                    continue
                if resp.status_code >= 500 and attempt < retries - 1:
                    self.backoff_count += 1
                    time.sleep(backoff * (2 ** attempt))
                    last_error = RuntimeError(f'HTTP {resp.status_code}: {resp.text[:300]}')
                    continue
                resp.raise_for_status()
                return resp.json()
            except Exception as exc:
                last_error = exc
                if attempt < retries - 1:
                    self.backoff_count += 1
                    time.sleep(backoff * (2 ** attempt))
        raise RuntimeError(f'Binance public GET failed path={path} params={params}: {last_error}')

    def mark_price_klines(self, *, symbol: str, interval: str, start_time_ms: int, end_time_ms: int, limit: int) -> List[List[Any]]:
        payload = self._get_json('/fapi/v1/markPriceKlines', {
            'symbol': symbol, 'interval': interval, 'startTime': int(start_time_ms), 'endTime': int(end_time_ms), 'limit': int(limit),
        })
        if not isinstance(payload, list):
            raise RuntimeError(f'unexpected mark price kline payload for {symbol}: {payload!r}')
        return payload

    def premium_index_klines(self, *, symbol: str, interval: str, start_time_ms: int, end_time_ms: int, limit: int) -> List[List[Any]]:
        payload = self._get_json('/fapi/v1/premiumIndexKlines', {
            'symbol': symbol, 'interval': interval, 'startTime': int(start_time_ms), 'endTime': int(end_time_ms), 'limit': int(limit),
        })
        if not isinstance(payload, list):
            raise RuntimeError(f'unexpected premium index kline payload for {symbol}: {payload!r}')
        return payload

    def funding_rate(self, *, symbol: str, start_time_ms: int, end_time_ms: int, limit: int) -> List[Dict[str, Any]]:
        payload = self._get_json('/fapi/v1/fundingRate', {
            'symbol': symbol, 'startTime': int(start_time_ms), 'endTime': int(end_time_ms), 'limit': int(limit),
        })
        if not isinstance(payload, list):
            raise RuntimeError(f'unexpected funding payload for {symbol}: {payload!r}')
        return payload

    def open_interest_hist(self, *, symbol: str, period: str, start_time_ms: int, end_time_ms: int, limit: int) -> List[Dict[str, Any]]:
        payload = self._get_json('/futures/data/openInterestHist', {
            'symbol': symbol, 'period': period, 'startTime': int(start_time_ms), 'endTime': int(end_time_ms), 'limit': int(limit),
        })
        if not isinstance(payload, list):
            raise RuntimeError(f'unexpected OI payload for {symbol}: {payload!r}')
        return payload

    def global_long_short_account_ratio(self, *, symbol: str, period: str, start_time_ms: int, end_time_ms: int, limit: int) -> List[Dict[str, Any]]:
        payload = self._get_json('/futures/data/globalLongShortAccountRatio', {
            'symbol': symbol, 'period': period, 'startTime': int(start_time_ms), 'endTime': int(end_time_ms), 'limit': int(limit),
        })
        if not isinstance(payload, list):
            raise RuntimeError(f'unexpected global L/S payload for {symbol}: {payload!r}')
        return payload

    def top_trader_long_short_account_ratio(self, *, symbol: str, period: str, start_time_ms: int, end_time_ms: int, limit: int) -> List[Dict[str, Any]]:
        payload = self._get_json('/futures/data/topLongShortAccountRatio', {
            'symbol': symbol, 'period': period, 'startTime': int(start_time_ms), 'endTime': int(end_time_ms), 'limit': int(limit),
        })
        if not isinstance(payload, list):
            raise RuntimeError(f'unexpected top account L/S payload for {symbol}: {payload!r}')
        return payload

    def top_trader_long_short_position_ratio(self, *, symbol: str, period: str, start_time_ms: int, end_time_ms: int, limit: int) -> List[Dict[str, Any]]:
        payload = self._get_json('/futures/data/topLongShortPositionRatio', {
            'symbol': symbol, 'period': period, 'startTime': int(start_time_ms), 'endTime': int(end_time_ms), 'limit': int(limit),
        })
        if not isinstance(payload, list):
            raise RuntimeError(f'unexpected top position L/S payload for {symbol}: {payload!r}')
        return payload

    def taker_buy_sell_volume(self, *, symbol: str, period: str, start_time_ms: int, end_time_ms: int, limit: int) -> List[Dict[str, Any]]:
        payload = self._get_json('/futures/data/takerlongshortRatio', {
            'symbol': symbol, 'period': period, 'startTime': int(start_time_ms), 'endTime': int(end_time_ms), 'limit': int(limit),
        })
        if not isinstance(payload, list):
            raise RuntimeError(f'unexpected taker buy/sell payload for {symbol}: {payload!r}')
        return payload

    def basis(self, *, pair: str, contract_type: str, period: str, start_time_ms: int, end_time_ms: int, limit: int) -> List[Dict[str, Any]]:
        payload = self._get_json('/futures/data/basis', {
            'pair': pair, 'contractType': contract_type, 'period': period,
            'startTime': int(start_time_ms), 'endTime': int(end_time_ms), 'limit': int(limit),
        })
        if not isinstance(payload, list):
            raise RuntimeError(f'unexpected basis payload for {pair}: {payload!r}')
        return payload


class BinanceFuturesMetricCollector:
    def __init__(self, *, config: Dict[str, Any], store: MetricCollectorStore, client: Any, now_ms_fn: Callable[[], int] = now_ms):
        self.config = config
        self.store = store
        self.client = client
        self.now_ms_fn = now_ms_fn

    def enabled_metrics(self) -> List[str]:
        metrics_cfg = dict(self.config.get('metrics') or {})
        return [name for name in METRIC_SPECS if bool(metrics_cfg.get(name, False))]

    def refresh_symbols(self) -> int:
        ts = int(self.now_ms_fn())
        payload = self.client.exchange_info()
        symbols = core.discover_usdm_perpetual_symbols(payload, now_ms=ts, quote_asset=str(self.config.get('quote_asset') or 'USDT'))
        self.store.upsert_symbols(symbols, interval='1m', today_start_ms=core.today_utc_start_ms(ts))
        self.store.deactivate_missing_symbols([s.symbol for s in symbols], now_ms_value=ts)
        self.store.set_state('last_symbol_refresh_ms', ts, updated_at_ms=ts)
        return len(symbols)

    def _symbol_refresh_due(self) -> bool:
        last = self.store.get_state('last_symbol_refresh_ms')
        if last is None:
            return True
        interval_s = int(self.config.get('symbol_refresh_seconds', 3600))
        return (int(self.now_ms_fn()) - int(last)) >= interval_s * 1000

    def _metric_end_ts(self, metric: str, now_value: int) -> int:
        spec = METRIC_SPECS[metric]
        close_lag_ms = int(self.config.get('close_lag_ms', 5_000))
        if metric == 'funding_rate':
            return int(now_value) - close_lag_ms
        return _latest_closed_ts(now_value, spec.period_ms, close_lag_ms)

    def _should_skip_empty_backoff(self, metric: str, symbol: str, now_value: int) -> bool:
        state = self.store.get_metric_state(metric, symbol)
        if not state or not state.get('last_empty_ms'):
            return False
        backoff_s = int(self.config.get('empty_backoff_seconds', 30 * 60))
        return int(now_value) - int(state['last_empty_ms']) < backoff_s * 1000

    def _fetch_metric(self, metric: str, meta: core.SymbolMeta, *, cursor: int, end_ts: int, limit: int) -> List[Any]:
        if metric == 'mark_price_1m':
            return self.client.mark_price_klines(symbol=meta.symbol, interval='1m', start_time_ms=cursor, end_time_ms=end_ts, limit=limit)
        if metric == 'premium_index_1m':
            return self.client.premium_index_klines(symbol=meta.symbol, interval='1m', start_time_ms=cursor, end_time_ms=end_ts, limit=limit)
        if metric == 'funding_rate':
            return self.client.funding_rate(symbol=meta.symbol, start_time_ms=cursor, end_time_ms=end_ts, limit=limit)
        if metric == 'open_interest_5m':
            return self.client.open_interest_hist(symbol=meta.symbol, period='5m', start_time_ms=cursor, end_time_ms=end_ts, limit=limit)
        if metric == 'global_long_short_account_ratio_5m':
            return self.client.global_long_short_account_ratio(symbol=meta.symbol, period='5m', start_time_ms=cursor, end_time_ms=end_ts, limit=limit)
        if metric == 'top_trader_long_short_account_ratio_5m':
            return self.client.top_trader_long_short_account_ratio(symbol=meta.symbol, period='5m', start_time_ms=cursor, end_time_ms=end_ts, limit=limit)
        if metric == 'top_trader_long_short_position_ratio_5m':
            return self.client.top_trader_long_short_position_ratio(symbol=meta.symbol, period='5m', start_time_ms=cursor, end_time_ms=end_ts, limit=limit)
        if metric == 'taker_buy_sell_volume_5m':
            return self.client.taker_buy_sell_volume(symbol=meta.symbol, period='5m', start_time_ms=cursor, end_time_ms=end_ts, limit=limit)
        if metric == 'basis_perpetual_5m':
            return self.client.basis(pair=meta.pair or meta.symbol, contract_type='PERPETUAL', period='5m', start_time_ms=cursor, end_time_ms=end_ts, limit=limit)
        raise ValueError(f'unsupported metric: {metric}')

    def _normalize_metric_rows(self, metric: str, raw_rows: Sequence[Any], meta: core.SymbolMeta, *, collected_at: int, end_ts: int) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for raw in raw_rows:
            if metric in PRICE_KLINE_METRICS:
                row = normalize_price_kline(metric, raw, symbol=meta.symbol, collected_at_ms=collected_at)
            elif metric == 'funding_rate':
                row = normalize_funding_rate(raw, collected_at_ms=collected_at)
            elif metric == 'open_interest_5m':
                row = normalize_open_interest(raw, collected_at_ms=collected_at)
            elif metric in RATIO_METRICS:
                row = normalize_long_short_ratio(metric, raw, collected_at_ms=collected_at)
                if not row.get('symbol'):
                    row['symbol'] = meta.symbol
            elif metric == 'taker_buy_sell_volume_5m':
                row = normalize_taker_buy_sell(raw, collected_at_ms=collected_at)
                if not row.get('symbol'):
                    row['symbol'] = meta.symbol
            elif metric == 'basis_perpetual_5m':
                row = normalize_basis(raw, symbol=meta.symbol, collected_at_ms=collected_at)
            else:
                raise ValueError(f'unsupported metric: {metric}')
            if not row.get('symbol'):
                row['symbol'] = meta.symbol
            if int(row.get('ts_ms') or 0) <= 0:
                continue
            if int(row['ts_ms']) > int(end_ts):
                continue
            rows.append(row)
        rows.sort(key=lambda r: int(r['ts_ms']))
        return rows

    def _collect_metric_for_symbol(self, metric: str, meta: core.SymbolMeta, *, now_value: int) -> Dict[str, Any]:
        spec = METRIC_SPECS[metric]
        cursor = self.store.get_metric_cursor(metric, meta.symbol)
        if cursor is None:
            cursor = metric_initial_cursor(meta, metric, now_ms_value=now_value, config=self.config)
            self.store.record_metric_success(metric, meta.symbol, cursor_ms=cursor, rows=0, inserted=0, ts_ms=now_value)
        if self._should_skip_empty_backoff(metric, meta.symbol, now_value):
            return {'fetched': 0, 'inserted': 0, 'errors': 0, 'skipped_empty_backoff': 1}
        end_ts = self._metric_end_ts(metric, now_value)
        if cursor > end_ts:
            return {'fetched': 0, 'inserted': 0, 'errors': 0, 'lag_ms': 0}
        limit = int(self.config.get(spec.limit_key, spec.default_limit))
        max_batches = int(self.config.get('max_batches_per_metric_per_symbol', 1))
        fetched_total = 0
        inserted_total = 0
        max_lag = max(0, int(end_ts) - int(cursor))
        for _ in range(max(1, max_batches)):
            if cursor > end_ts:
                break
            raw_rows = self._fetch_metric(metric, meta, cursor=int(cursor), end_ts=int(end_ts), limit=limit)
            if not raw_rows:
                self.store.record_metric_empty(metric, meta.symbol, ts_ms=now_value)
                break
            collected_at = int(self.now_ms_fn())
            rows = self._normalize_metric_rows(metric, raw_rows, meta, collected_at=collected_at, end_ts=end_ts)
            rows = [r for r in rows if int(r['ts_ms']) >= int(cursor)]
            if not rows:
                self.store.record_metric_empty(metric, meta.symbol, ts_ms=now_value)
                break
            inserted = self.store.upsert_rows(metric, rows)
            fetched_total += len(rows)
            inserted_total += inserted
            if metric == 'funding_rate':
                next_cursor = max(int(r['ts_ms']) for r in rows) + 1
            else:
                next_cursor = max(int(r['ts_ms']) for r in rows) + spec.period_ms
            self.store.record_metric_success(metric, meta.symbol, cursor_ms=next_cursor, rows=len(rows), inserted=inserted, ts_ms=now_value)
            cursor = next_cursor
            if len(raw_rows) < limit:
                break
        return {'fetched': fetched_total, 'inserted': inserted_total, 'errors': 0, 'lag_ms': max_lag}

    def run_once(
        self,
        *,
        force_symbol_refresh: bool = False,
        max_symbols: Optional[int] = None,
        symbols_filter: Optional[Iterable[str]] = None,
    ) -> Dict[str, Any]:
        started = int(self.now_ms_fn())
        refreshed_symbols: Optional[int] = None
        if force_symbol_refresh or self._symbol_refresh_due():
            refreshed_symbols = self.refresh_symbols()
        symbols = self.store.list_active_symbols(limit=None if symbols_filter else max_symbols)
        if symbols_filter:
            wanted = {str(s).upper().strip() for s in symbols_filter if str(s).strip()}
            symbols = [s for s in symbols if s.symbol in wanted]
            if max_symbols is not None:
                symbols = symbols[:max_symbols]
        now_value = int(self.now_ms_fn())
        metrics_summary: Dict[str, Dict[str, Any]] = {}
        errors_sample: List[Dict[str, str]] = []
        max_lag_ms = 0
        for metric in self.enabled_metrics():
            summary = {'symbols': 0, 'fetched': 0, 'inserted': 0, 'errors': 0, 'skipped_empty_backoff': 0, 'max_lag_ms': 0}
            for meta in symbols:
                summary['symbols'] += 1
                try:
                    result = self._collect_metric_for_symbol(metric, meta, now_value=now_value)
                    summary['fetched'] += int(result.get('fetched') or 0)
                    summary['inserted'] += int(result.get('inserted') or 0)
                    summary['errors'] += int(result.get('errors') or 0)
                    summary['skipped_empty_backoff'] += int(result.get('skipped_empty_backoff') or 0)
                    lag = int(result.get('lag_ms') or 0)
                    summary['max_lag_ms'] = max(summary['max_lag_ms'], lag)
                    max_lag_ms = max(max_lag_ms, lag)
                except Exception as exc:
                    summary['errors'] += 1
                    err = str(exc)[:500]
                    self.store.record_metric_error(metric, meta.symbol, err, ts_ms=now_value)
                    if len(errors_sample) < 10:
                        errors_sample.append({'metric': metric, 'symbol': meta.symbol, 'error': err})
            metrics_summary[metric] = summary
        ended = int(self.now_ms_fn())
        total_errors = sum(int(v.get('errors') or 0) for v in metrics_summary.values())
        result = {
            'kind': 'metric_run',
            'ts_ms': ended,
            'duration_ms': ended - started,
            'active_symbols': len(symbols),
            'refreshed_symbols': refreshed_symbols,
            'metrics': metrics_summary,
            'max_lag_ms': max_lag_ms,
            'errors_count': total_errors,
            'errors_sample': errors_sample,
            'backoff_count': int(getattr(self.client, 'backoff_count', 0)),
            'db_path': str(self.store.db_path),
        }
        self.store.set_state('last_metric_run_summary_json', json.dumps(result, ensure_ascii=False), updated_at_ms=ended)
        self.store.record_health(result)
        return result

    def run_forever(
        self,
        *,
        poll_seconds: Optional[float] = None,
        max_symbols: Optional[int] = None,
        symbols_filter: Optional[Iterable[str]] = None,
    ) -> None:
        poll = float(poll_seconds if poll_seconds is not None else self.config.get('poll_seconds', 60.0))
        first_pass = True
        while True:
            try:
                result = self.run_once(
                    force_symbol_refresh=first_pass,
                    max_symbols=max_symbols,
                    symbols_filter=symbols_filter,
                )
                first_pass = False
                print(json.dumps(result, ensure_ascii=False), flush=True)
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                print(json.dumps({'ts_ms': int(self.now_ms_fn()), 'fatal_loop_error': str(exc)}, ensure_ascii=False), flush=True)
            time.sleep(max(1.0, poll))


def build_collector(config: Dict[str, Any]) -> BinanceFuturesMetricCollector:
    runtime_dir = Path(str(config.get('runtime_dir') or DEFAULT_RUNTIME_DIR))
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / 'logs').mkdir(parents=True, exist_ok=True)
    store = MetricCollectorStore(Path(str(config.get('db_path') or runtime_dir / 'binance_futures_1m.sqlite3')))
    client = BinanceFuturesMetricsClient(config)
    return BinanceFuturesMetricCollector(config=config, store=store, client=client)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description='Binance USD-M Futures extended public metric collector')
    ap.add_argument('--config', type=Path, default=DEFAULT_CONFIG_PATH)
    ap.add_argument('--runtime-dir', type=Path)
    ap.add_argument('--db-path', type=Path)
    ap.add_argument('--once', action='store_true')
    ap.add_argument('--force-symbol-refresh', action='store_true')
    ap.add_argument('--status', action='store_true')
    ap.add_argument('--max-symbols', type=int)
    ap.add_argument('--symbols', help='Comma-separated symbols to collect for targeted smoke/backfill, e.g. BTCUSDT,ETHUSDT')
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
    symbols_filter = [s.strip().upper() for s in str(args.symbols or '').split(',') if s.strip()]
    try:
        if args.status:
            print(json.dumps(collector.store.summary(), ensure_ascii=False, indent=2))
            return 0
        if args.once:
            result = collector.run_once(
                force_symbol_refresh=args.force_symbol_refresh,
                max_symbols=args.max_symbols,
                symbols_filter=symbols_filter or None,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        collector.run_forever(poll_seconds=args.poll_seconds, max_symbols=args.max_symbols, symbols_filter=symbols_filter or None)
        return 0
    finally:
        collector.store.close()


if __name__ == '__main__':
    raise SystemExit(main())
