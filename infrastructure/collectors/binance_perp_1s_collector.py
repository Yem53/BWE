#!/usr/bin/env python3
"""Binance Futures (perp) 1s kline collector via aggTrades aggregation.

fapi 不支持 1s kline interval, 但 fapi /aggTrades 提供 ms 级 trade data.
此 collector 拉 aggTrades, aggregate 成 1s OHLCV bars, 写入 SQLite klines_1m
表 with interval='1s_perp'.

Targets BWE-涉及 symbols (从 BWE matrix events 中读), 不是全市场.
30d backfill + forward continuous.

Storage estimate: 297 symbols × ~50% non-empty 1s bars × 30 day × ~80B = ~30GB
"""
from __future__ import annotations
import argparse, json, os, sqlite3, sys, time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import urllib.request, urllib.parse, urllib.error

DEFAULT_DB = "/Volumes/T9/BWE/30_DATA/binance_collectors_runtime/binance_futures_1m.sqlite3"
DEFAULT_BWE_JSONL = "/Volumes/T9/BWE/30_DATA/bwe_logs/bwe_matrix_posts.jsonl"
DEFAULT_LOG = "/Volumes/T9/BWE/30_DATA/binance_collectors_runtime/logs/perp_1s_collector.log"

BASE_URL = "https://fapi.binance.com"
INTERVAL = "1s_perp"  # 用 _perp 后缀区分跟之前的 spot 1s
PROXY = "http://127.0.0.1:7897"


def log(msg: dict):
    msg["ts_ms"] = int(time.time() * 1000)
    line = json.dumps(msg, ensure_ascii=False)
    print(line, flush=True)
    try:
        with open(DEFAULT_LOG, 'a') as f:
            f.write(line + '\n')
    except: pass


def get_bwe_symbols(jsonl_path: str, days_lookback: int = 7) -> set:
    """Extract BWE-涉及 symbols from past N days of posts."""
    import re
    SYM_RE = re.compile(r'\b([A-Z][A-Z0-9]+USDT)\b')
    cutoff_ms = int((time.time() - days_lookback * 86400) * 1000)
    syms = set()
    try:
        with open(jsonl_path) as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except: continue
                ts = obj.get('event_ts_ms') or obj.get('ts_ms') or 0
                if ts < cutoff_ms: continue
                text = obj.get('text', '')
                for m in SYM_RE.findall(text):
                    syms.add(m)
    except FileNotFoundError:
        log({"error": "BWE jsonl not found", "path": jsonl_path})
    return syms


def http_get(url: str, retries: int = 3) -> Optional[dict | list]:
    """GET with proxy + retry."""
    handler = urllib.request.ProxyHandler({'http': PROXY, 'https': PROXY})
    opener = urllib.request.build_opener(handler)
    req = urllib.request.Request(url, headers={'User-Agent': 'Hermes-BWE-perp-1s/1.0'})
    for attempt in range(retries):
        try:
            with opener.open(req, timeout=15) as resp:
                if resp.status != 200: continue
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(2 ** attempt * 2)
                continue
            elif e.code in (400, 404):  # symbol不存在
                return None
            else:
                time.sleep(2 ** attempt)
        except Exception:
            time.sleep(2 ** attempt)
    return None


def aggregate_aggtrades_to_1s(trades: list) -> dict:
    """Convert aggTrades list → {sec_open_ms: {open, high, low, close, volume, ...}}.

    aggTrade fields: a (id), p (price), q (qty), f, l, T (timestamp ms), m (isBuyerMaker)
    """
    bars = {}
    for t in trades:
        try:
            ts = int(t['T'])
            sec_ms = (ts // 1000) * 1000
            price = float(t['p'])
            qty = float(t['q'])
            is_buyer_maker = t.get('m', False)

            if sec_ms not in bars:
                bars[sec_ms] = {
                    'open_time_ms': sec_ms,
                    'close_time_ms': sec_ms + 999,
                    'open': price, 'high': price, 'low': price, 'close': price,
                    'volume': 0.0, 'quote_volume': 0.0,
                    'trade_count': 0,
                    'taker_buy_base_volume': 0.0,
                    'taker_buy_quote_volume': 0.0,
                }
            b = bars[sec_ms]
            if price > b['high']: b['high'] = price
            if price < b['low']: b['low'] = price
            b['close'] = price  # last
            b['volume'] += qty
            b['quote_volume'] += qty * price
            b['trade_count'] += 1
            # taker buys = NOT buyer-maker (taker is the buyer)
            if not is_buyer_maker:
                b['taker_buy_base_volume'] += qty
                b['taker_buy_quote_volume'] += qty * price
        except (KeyError, ValueError, TypeError):
            continue
    return bars


def fetch_aggtrades(symbol: str, start_ms: int, end_ms: int) -> list:
    """Fetch aggTrades for symbol in [start_ms, end_ms). Up to 1000 per call."""
    url = (f"{BASE_URL}/fapi/v1/aggTrades?symbol={symbol}"
           f"&startTime={start_ms}&endTime={end_ms}&limit=1000")
    data = http_get(url)
    if not isinstance(data, list):
        return []
    return data


def fetch_window_with_pagination(symbol: str, start_ms: int, end_ms: int) -> list:
    """Fetch ALL aggTrades in window, paginating if > 1000."""
    all_trades = []
    cur_start = start_ms
    while cur_start < end_ms:
        # Cap window to 1 hour to avoid timeout (binance recommends ≤ 1h ranges)
        window_end = min(cur_start + 3600_000, end_ms)
        trades = fetch_aggtrades(symbol, cur_start, window_end)
        if not trades:
            cur_start = window_end + 1
            continue
        all_trades.extend(trades)
        last_T = max(int(t['T']) for t in trades)
        if len(trades) < 1000 or last_T >= window_end - 1:
            cur_start = window_end + 1
        else:
            cur_start = last_T + 1  # 继续 paginate
        time.sleep(0.20)  # rate limit (200ms = 5 req/s, safer)
    return all_trades


def insert_bars(conn: sqlite3.Connection, symbol: str, bars: dict):
    """Insert 1s bars into klines_1m table with interval='1s_perp'."""
    if not bars: return 0
    rows = [
        (symbol, INTERVAL, b['open_time_ms'], b['close_time_ms'],
         b['open'], b['high'], b['low'], b['close'], b['volume'],
         b['quote_volume'], b['trade_count'],
         b['taker_buy_base_volume'], b['taker_buy_quote_volume'],
         '0', 'PERPETUAL', 'TRADING', 0,
         int(time.time() * 1000),
         '')
        for b in bars.values()
    ]
    cur = conn.executemany('''
        INSERT OR IGNORE INTO klines_1m
        (symbol, interval, open_time_ms, close_time_ms, open, high, low, close, volume,
         quote_volume, trade_count, taker_buy_base_volume, taker_buy_quote_volume,
         ignore_value, contract_type, status, listing_ts_ms, collected_at_ms, raw_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', rows)
    conn.commit()
    return cur.rowcount


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--bwe-jsonl", default=DEFAULT_BWE_JSONL)
    p.add_argument("--bwe-lookback-days", type=int, default=7)
    p.add_argument("--backfill-days", type=int, default=30)
    p.add_argument("--forward", action="store_true",
                   help="Forward mode (collect new only, no backfill)")
    p.add_argument("--symbols", nargs='*',
                   help="Specific symbols (override BWE auto-detection)")
    p.add_argument("--all-perp", action="store_true",
                   help="Full market: all USDT PERPETUAL symbols (TRADING + SETTLING)")
    args = p.parse_args()

    log({"event": "perp_1s_collector_start", "args": vars(args)})

    # Symbol selection: --all-perp > --symbols > BWE-jsonl
    if args.all_perp:
        info = http_get(f"{BASE_URL}/fapi/v1/exchangeInfo")
        if not info:
            log({"fatal": "exchangeInfo fetch failed"})
            sys.exit(1)
        symbols = sorted(
            s['symbol'] for s in info.get('symbols', [])
            if s.get('contractType') == 'PERPETUAL'
            and s.get('quoteAsset') == 'USDT'
            and s.get('status') == 'TRADING'
        )
    elif args.symbols:
        symbols = sorted(set(args.symbols))
    else:
        symbols = sorted(get_bwe_symbols(args.bwe_jsonl, args.bwe_lookback_days))
    log({"event": "symbols_loaded", "count": len(symbols), "sample": list(symbols)[:10]})

    if not symbols:
        log({"fatal": "no symbols to collect"})
        sys.exit(1)

    conn = sqlite3.connect(args.db, timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")

    if args.forward:
        # Forward mode: poll每 60s, fetch last 60s aggTrades for each symbol
        log({"event": "forward_mode_start", "symbols": len(symbols)})
        while True:
            cycle_start = time.time()
            cycle_inserted = 0
            for sym in symbols:
                end_ms = int(time.time() * 1000)
                start_ms = end_ms - 60_000  # last 60s
                trades = fetch_aggtrades(sym, start_ms, end_ms)
                if trades:
                    bars = aggregate_aggtrades_to_1s(trades)
                    cycle_inserted += insert_bars(conn, sym, bars)
            log({"cycle_inserted": cycle_inserted, "elapsed_s": time.time() - cycle_start})
            sleep_for = max(1, 60 - (time.time() - cycle_start))
            time.sleep(sleep_for)
    else:
        # Backfill mode: 30d 后到 now (chronological)
        end_ms = int(time.time() * 1000)
        start_ms = end_ms - args.backfill_days * 86400 * 1000
        total_inserted = 0
        for i, sym in enumerate(symbols):
            sym_start = time.time()
            try:
                trades = fetch_window_with_pagination(sym, start_ms, end_ms)
                if trades:
                    bars = aggregate_aggtrades_to_1s(trades)
                    inserted = insert_bars(conn, sym, bars)
                    total_inserted += inserted
                    log({"sym": sym, "trades": len(trades), "bars": len(bars),
                         "inserted": inserted, "elapsed_s": round(time.time() - sym_start, 1),
                         "progress": f"{i+1}/{len(symbols)}"})
                else:
                    log({"sym": sym, "no_data": True, "progress": f"{i+1}/{len(symbols)}"})
            except Exception as e:
                log({"sym": sym, "error": str(e)})
        log({"backfill_complete": True, "total_inserted": total_inserted})


if __name__ == "__main__":
    main()
