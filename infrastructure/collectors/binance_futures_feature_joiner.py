#!/usr/bin/env python3
"""Asof-join BWE event rows with Binance futures entry-time features from SQLite.

The joiner is read-only: it never writes to the market data DB and only writes the
requested enriched parquet plus a feature registry JSON.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd

DEFAULT_DB_PATH = Path('/Volumes/T9/BWE/30_DATA/binance_collectors_runtime/binance_futures_1m.sqlite3')
DEFAULT_REGISTRY_NAME = 'feature_registry.json'

TABLE_FEATURE_COLUMNS: Dict[str, List[str]] = {
    'funding_rate': ['funding_rate', 'mark_price'],
    'mark_price_1m': ['open', 'high', 'low', 'close'],
    'premium_index_1m': ['open', 'high', 'low', 'close'],
    'open_interest_5m': ['sum_open_interest', 'sum_open_interest_value'],
    'global_long_short_account_ratio_5m': ['long_short_ratio', 'long_account', 'short_account'],
    'top_trader_long_short_account_ratio_5m': ['long_short_ratio', 'long_account', 'short_account'],
    'top_trader_long_short_position_ratio_5m': ['long_short_ratio', 'long_account', 'short_account'],
    'taker_buy_sell_volume_5m': ['buy_sell_ratio', 'buy_vol', 'sell_vol'],
    'basis_perpetual_5m': ['basis', 'basis_rate', 'index_price', 'futures_price', 'annualized_basis_rate'],
}

SYMBOL_COLUMN_CANDIDATES = ['api_symbol', 'symbol', 'binance_symbol', 'ticker', 'asset']
TS_COLUMN_CANDIDATES = ['ts_ms', 'event_ts_ms', 'message_ts_ms', 'timestamp_ms', 'time_ms', 'timestamp']


def normalize_symbol(value: Any) -> str:
    text = str(value or '').upper().strip()
    text = text.replace('/USDT:USDT', 'USDT').replace('/USDT', 'USDT')
    text = re.sub(r'[^A-Z0-9]', '', text)
    if text and not text.endswith('USDT') and len(text) <= 12:
        text = f'{text}USDT'
    return text


def load_events(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == '.parquet':
        return pd.read_parquet(path)
    if suffix in {'.csv', '.txt'}:
        return pd.read_csv(path)
    raise ValueError(f'unsupported event file type: {path}')


def detect_column(df: pd.DataFrame, explicit: Optional[str], candidates: Iterable[str], *, kind: str) -> str:
    if explicit:
        if explicit not in df.columns:
            raise ValueError(f'{kind} column not found: {explicit}')
        return explicit
    for col in candidates:
        if col in df.columns:
            return col
    raise ValueError(f'cannot detect {kind} column; available columns={list(df.columns)}')


def ensure_ts_ms(series: pd.Series) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(series):
        return (series.astype('int64') // 1_000_000).astype('int64')
    numeric = pd.to_numeric(series, errors='coerce')
    # Heuristic: real seconds timestamps are ~1e9-1e10; ms timestamps are ~1e12-1e13.
    # Very small synthetic/test values are treated as already being in ms.
    median = numeric.dropna().median()
    if 1_000_000_000 <= median < 20_000_000_000:
        numeric = numeric * 1000
    return numeric.astype('Int64').astype('int64')


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return row is not None


def read_feature_table(conn: sqlite3.Connection, table: str, symbols: List[str], min_ts: int, max_ts: int) -> pd.DataFrame:
    if not symbols or not table_exists(conn, table):
        return pd.DataFrame()
    wanted = TABLE_FEATURE_COLUMNS[table]
    existing_cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    cols = ['symbol', 'ts_ms'] + [c for c in wanted if c in existing_cols]
    if len(cols) <= 2:
        return pd.DataFrame()
    placeholders = ','.join('?' for _ in symbols)
    params: List[Any] = list(symbols) + [int(min_ts), int(max_ts)]
    sql = f"SELECT {', '.join(cols)} FROM {table} WHERE symbol IN ({placeholders}) AND ts_ms BETWEEN ? AND ? ORDER BY symbol, ts_ms"
    return pd.read_sql_query(sql, conn, params=params)


def asof_join_one_table(events: pd.DataFrame, features: pd.DataFrame, *, table: str, symbol_col: str, ts_col: str) -> pd.DataFrame:
    if features.empty:
        for col in TABLE_FEATURE_COLUMNS[table]:
            events[f'{table}_{col}'] = pd.NA
        events[f'{table}_known_ts_ms'] = pd.NA
        return events

    rename = {col: f'{table}_{col}' for col in features.columns if col not in {'symbol', 'ts_ms'}}
    right = features.rename(columns=rename).rename(columns={'ts_ms': f'{table}_known_ts_ms', 'symbol': '__feature_symbol'})
    out_parts: List[pd.DataFrame] = []
    feature_ts_col = f'{table}_known_ts_ms'
    for symbol, left_group in events.groupby(symbol_col, sort=False, dropna=False):
        left_sorted = left_group.sort_values(ts_col)
        right_group = right[right['__feature_symbol'] == symbol].sort_values(feature_ts_col)
        if right_group.empty:
            enriched = left_sorted.copy()
            for col in rename.values():
                enriched[col] = pd.NA
            enriched[feature_ts_col] = pd.NA
        else:
            enriched = pd.merge_asof(
                left_sorted,
                right_group.drop(columns=['__feature_symbol']),
                left_on=ts_col,
                right_on=feature_ts_col,
                direction='backward',
                allow_exact_matches=True,
            )
        out_parts.append(enriched)
    return pd.concat(out_parts, ignore_index=True).sort_values('__original_order').reset_index(drop=True)


def build_registry(enriched_columns: Iterable[str]) -> List[Dict[str, Any]]:
    registry: List[Dict[str, Any]] = []
    columns = set(enriched_columns)
    for table, feature_cols in TABLE_FEATURE_COLUMNS.items():
        for col in feature_cols:
            feature = f'{table}_{col}'
            if feature not in columns:
                continue
            registry.append({
                'feature': feature,
                'source': table,
                'known_at': f'latest_{table}_before_event_ts',
                'allowed_for_entry': True,
            })
    return registry


def join_features(
    *,
    events_path: Path,
    db_path: Path,
    output_path: Path,
    registry_path: Optional[Path] = None,
    symbol_column: Optional[str] = None,
    ts_column: Optional[str] = None,
    lookback_days: int = 35,
) -> Dict[str, Any]:
    events = load_events(events_path).copy()
    raw_symbol_col = detect_column(events, symbol_column, SYMBOL_COLUMN_CANDIDATES, kind='symbol')
    raw_ts_col = detect_column(events, ts_column, TS_COLUMN_CANDIDATES, kind='timestamp')
    join_symbol_col = '__join_symbol'
    join_ts_col = '__join_ts_ms'
    events['__original_order'] = range(len(events))
    events[join_symbol_col] = events[raw_symbol_col].map(normalize_symbol)
    events[join_ts_col] = ensure_ts_ms(events[raw_ts_col])

    symbols = sorted(s for s in events[join_symbol_col].dropna().unique().tolist() if s)
    min_ts = int(events[join_ts_col].min()) - int(lookback_days) * 24 * 60 * 60 * 1000
    max_ts = int(events[join_ts_col].max())

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        for table in TABLE_FEATURE_COLUMNS:
            features = read_feature_table(conn, table, symbols, min_ts, max_ts)
            events = asof_join_one_table(events, features, table=table, symbol_col=join_symbol_col, ts_col=join_ts_col)

    registry = build_registry(events.columns)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    public = events.drop(columns=['__original_order', join_symbol_col, join_ts_col])
    public.to_parquet(output_path, index=False)
    if registry_path is None:
        registry_path = output_path.with_name(DEFAULT_REGISTRY_NAME)
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding='utf-8')

    return {
        'rows': int(len(public)),
        'symbols': int(len(symbols)),
        'features': int(len(registry)),
        'output_path': str(output_path),
        'registry_path': str(registry_path),
    }


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description='Asof join Binance futures collector metrics into BWE events')
    ap.add_argument('--events', type=Path, required=True, help='Input BWE events parquet/csv')
    ap.add_argument('--db-path', type=Path, default=DEFAULT_DB_PATH)
    ap.add_argument('--output', type=Path, required=True, help='Output enriched parquet')
    ap.add_argument('--registry', type=Path, help='Output feature registry JSON')
    ap.add_argument('--symbol-column')
    ap.add_argument('--ts-column')
    ap.add_argument('--lookback-days', type=int, default=35)
    args = ap.parse_args(argv)
    result = join_features(
        events_path=args.events,
        db_path=args.db_path,
        output_path=args.output,
        registry_path=args.registry,
        symbol_column=args.symbol_column,
        ts_column=args.ts_column,
        lookback_days=args.lookback_days,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
