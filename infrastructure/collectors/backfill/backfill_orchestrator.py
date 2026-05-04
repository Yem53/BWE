#!/usr/bin/env python3
"""Unified rate-aware backfill orchestrator for Binance Futures USDM perp.

Priorities (in order):
1. BWE-涉及 symbols × all intervals (klines 1m/3m/5m/15m/1h + 1s aggTrades)
2. Rest of TRADING × klines only (1s aggTrades skipped — too expensive)
3. SETTLING (delisting) × klines only

Architecture:
- Gap detection per (symbol, interval) by querying DB MIN/MAX(open_time_ms)
- Token bucket rate limiter: budget=1500 weight/min (75% of Binance 2400, leaves headroom)
- Persistent state: /Volumes/T9/BWE/30_DATA/binance_collectors_runtime/backfill_state.json
- Robust: 418/429 → exponential backoff up to 5min; conn errors → retry
- Resume on restart: skip (sym, interval) already up-to-date

Endpoint weights (https://binance-docs.github.io/apidocs/futures/en/#limits):
- klines: 1-2 weight
- aggTrades: 20 weight  ← expensive
- exchangeInfo: 1 weight (but server-heavy, easy to IP-ban)
"""
from __future__ import annotations
import argparse, json, os, re, signal, sqlite3, sys, threading, time
import urllib.request, urllib.error, urllib.parse
from collections import deque
from pathlib import Path
from typing import Optional

# === Constants ===
DB = "/Volumes/T9/BWE/30_DATA/binance_collectors_runtime/binance_futures_1m.sqlite3"
BWE_JSONL = "/Volumes/T9/BWE/30_DATA/bwe_logs/bwe_matrix_posts.jsonl"
STATE = "/Volumes/T9/BWE/30_DATA/binance_collectors_runtime/backfill_state.json"
LOG = "/Volumes/T9/BWE/30_DATA/binance_collectors_runtime/logs/backfill_orchestrator.log"
BASE = "https://fapi.binance.com"
PROXY = "http://127.0.0.1:7897"

INTERVAL_MS = {'1s_perp': 1_000, '1m': 60_000, '3m': 180_000, '5m': 300_000, '15m': 900_000, '1h': 3_600_000}
KLINE_INTERVALS = ['1m', '3m', '5m', '15m', '1h']  # fapi-supported kline intervals (no 1s)

# Endpoint weights (assumed limit=1000)
WEIGHT = {'klines': 2, 'aggTrades': 20, 'exchangeInfo': 1}

DEFAULT_DAYS = 30
WEIGHT_BUDGET_PER_MIN = 1500  # of Binance 2400 — leaves 900 for continuous collectors
KLINE_LIMIT = 1500  # max per fapi
AGGTRADES_LIMIT = 1000


# === Token bucket rate limiter ===
class RateLimiter:
    def __init__(self, budget_per_min: int):
        self.budget = budget_per_min
        self.tokens = float(budget_per_min)
        self.last = time.time()
        self.lock = threading.Lock()
    def acquire(self, weight: int):
        """Block until `weight` tokens available."""
        while True:
            with self.lock:
                now = time.time()
                elapsed = now - self.last
                refill = elapsed * (self.budget / 60.0)
                self.tokens = min(self.budget, self.tokens + refill)
                self.last = now
                if self.tokens >= weight:
                    self.tokens -= weight
                    return
                wait = (weight - self.tokens) / (self.budget / 60.0)
            time.sleep(min(wait, 5.0))


# === HTTP with backoff ===
def _http_get_raw(url: str, timeout: int = 20):
    handler = urllib.request.ProxyHandler({'http': PROXY, 'https': PROXY})
    opener = urllib.request.build_opener(handler)
    req = urllib.request.Request(url, headers={'User-Agent': 'Hermes-BWE-orchestrator/1.0'})
    return opener.open(req, timeout=timeout)


def http_get(url: str, weight: int, limiter: RateLimiter, max_retries: int = 6) -> Optional[list | dict]:
    """GET with rate budget + exponential backoff on 418/429/network."""
    backoff = 1.0
    for attempt in range(max_retries):
        limiter.acquire(weight)
        try:
            with _http_get_raw(url) as resp:
                if resp.status == 200:
                    return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 418:
                wait = min(300, backoff * 30)  # ban: wait 30s, 60s, 120s, 240s, max 5min
                log({'event': 'rate_limit_418', 'wait_s': wait, 'attempt': attempt})
                time.sleep(wait)
                backoff *= 2
                continue
            elif e.code == 429:
                wait = min(60, backoff * 5)
                log({'event': 'rate_limit_429', 'wait_s': wait, 'attempt': attempt})
                time.sleep(wait)
                backoff *= 2
                continue
            elif e.code in (400, 404):
                return None  # symbol invalid
            else:
                log({'event': 'http_error', 'code': e.code, 'url': url[:100]})
                time.sleep(backoff)
                backoff *= 2
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as e:
            # VPN flap, network error
            log({'event': 'net_error', 'attempt': attempt, 'err': str(e)[:100]})
            time.sleep(backoff)
            backoff *= 2
    return None


# === Logging ===
def log(d: dict):
    d['ts_ms'] = int(time.time() * 1000)
    line = json.dumps(d, ensure_ascii=False)
    print(line, flush=True)
    try:
        with open(LOG, 'a') as f:
            f.write(line + '\n')
    except Exception:
        pass


# === Persistent state ===
def load_state() -> dict:
    try:
        return json.loads(Path(STATE).read_text())
    except Exception:
        return {}


def save_state(state: dict):
    try:
        Path(STATE).write_text(json.dumps(state, indent=2))
    except Exception as e:
        log({'event': 'save_state_err', 'err': str(e)[:100]})


# === Symbol discovery ===
def get_bwe_symbols(days_lookback: int = 7) -> set:
    """Symbols from BWE messages."""
    SYM_RE = re.compile(r'\b([A-Z][A-Z0-9]+USDT)\b')
    cutoff_ms = int((time.time() - days_lookback * 86400) * 1000)
    syms = set()
    try:
        with open(BWE_JSONL) as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                ts = obj.get('event_ts_ms') or obj.get('ts_ms') or 0
                if ts < cutoff_ms:
                    continue
                for m in SYM_RE.findall(obj.get('text', '')):
                    syms.add(m)
    except FileNotFoundError:
        log({'event': 'bwe_jsonl_missing'})
    return syms


def get_market_perp_symbols(limiter: RateLimiter) -> tuple[set, set]:
    """(TRADING, SETTLING) sets. Skip non-ASCII symbols (Chinese meme futures)."""
    info = http_get(f"{BASE}/fapi/v1/exchangeInfo", WEIGHT['exchangeInfo'], limiter)
    if not info:
        return set(), set()
    trading, settling = set(), set()
    for s in info.get('symbols', []):
        if s.get('contractType') != 'PERPETUAL' or s.get('quoteAsset') != 'USDT':
            continue
        sym = s['symbol']
        if not sym.isascii():
            log({'event': 'skip_nonascii_symbol', 'symbol': sym})
            continue
        if s.get('status') == 'TRADING':
            trading.add(sym)
        elif s.get('status') == 'SETTLING':
            settling.add(sym)
    return trading, settling


# === Gap detection ===
def get_existing_range(conn, symbol: str, interval: str) -> tuple[Optional[int], Optional[int]]:
    """(min_ms, max_ms) of existing data, or (None, None) if empty."""
    row = conn.execute(
        "SELECT MIN(open_time_ms), MAX(open_time_ms) FROM klines_1m WHERE symbol=? AND interval=?",
        (symbol, interval)
    ).fetchone()
    return row if row else (None, None)


# === Fetch + insert ===
def fetch_and_insert_klines(conn, limiter: RateLimiter, symbol: str, interval: str,
                            start_ms: int, end_ms: int, status: str = 'TRADING') -> int:
    """Fetch klines in window, insert into DB. Return rows inserted."""
    cur = start_ms
    total_inserted = 0
    while cur < end_ms:
        url = (f"{BASE}/fapi/v1/klines?symbol={symbol}&interval={interval}"
               f"&startTime={cur}&endTime={end_ms}&limit={KLINE_LIMIT}")
        ks = http_get(url, WEIGHT['klines'], limiter)
        if not ks:
            break
        rows = []
        now_ms = int(time.time() * 1000)
        for k in ks:
            try:
                rows.append((
                    symbol, interval, int(k[0]), int(k[6]),
                    float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5]),
                    float(k[7]), int(k[8]),
                    float(k[9]), float(k[10]),
                    str(k[11]),
                    'PERPETUAL', status, 0, now_ms, ''
                ))
            except (ValueError, IndexError, TypeError):
                continue
        if rows:
            res = conn.executemany('''
                INSERT OR IGNORE INTO klines_1m
                (symbol, interval, open_time_ms, close_time_ms, open, high, low, close, volume,
                 quote_volume, trade_count, taker_buy_base_volume, taker_buy_quote_volume,
                 ignore_value, contract_type, status, listing_ts_ms, collected_at_ms, raw_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', rows)
            conn.commit()
            total_inserted += res.rowcount
        last_open = int(ks[-1][0])
        if len(ks) < KLINE_LIMIT:
            break
        cur = last_open + INTERVAL_MS[interval]
    return total_inserted


def fetch_and_insert_aggtrades_1s(conn, limiter: RateLimiter, symbol: str,
                                  start_ms: int, end_ms: int) -> int:
    """Fetch aggTrades in window, aggregate to 1s bars, insert. Heavy weight (20)."""
    bars = {}  # sec_ms → bar dict
    cur = start_ms
    while cur < end_ms:
        # 1-hour windows to keep payload <1000 trades for low-volume coins
        win_end = min(cur + 3600_000, end_ms)
        url = f"{BASE}/fapi/v1/aggTrades?symbol={symbol}&startTime={cur}&endTime={win_end}&limit={AGGTRADES_LIMIT}"
        trades = http_get(url, WEIGHT['aggTrades'], limiter)
        if not trades:
            cur = win_end + 1
            continue
        for t in trades:
            try:
                ts = int(t['T'])
                sec_ms = (ts // 1000) * 1000
                price = float(t['p'])
                qty = float(t['q'])
                is_buyer_maker = t.get('m', False)
                if sec_ms not in bars:
                    bars[sec_ms] = {'o': price, 'h': price, 'l': price, 'c': price,
                                    'v': 0.0, 'qv': 0.0, 'n': 0, 'tbb': 0.0, 'tbq': 0.0}
                b = bars[sec_ms]
                if price > b['h']: b['h'] = price
                if price < b['l']: b['l'] = price
                b['c'] = price
                b['v'] += qty
                b['qv'] += qty * price
                b['n'] += 1
                if not is_buyer_maker:
                    b['tbb'] += qty
                    b['tbq'] += qty * price
            except (KeyError, ValueError, TypeError):
                continue
        last_T = max(int(t['T']) for t in trades)
        if len(trades) < AGGTRADES_LIMIT or last_T >= win_end - 1:
            cur = win_end + 1
        else:
            cur = last_T + 1
    if not bars:
        return 0
    now_ms = int(time.time() * 1000)
    rows = [
        (symbol, '1s_perp', sec_ms, sec_ms + 999,
         b['o'], b['h'], b['l'], b['c'], b['v'],
         b['qv'], b['n'], b['tbb'], b['tbq'],
         '0', 'PERPETUAL', 'TRADING', 0, now_ms, '')
        for sec_ms, b in bars.items()
    ]
    res = conn.executemany('''
        INSERT OR IGNORE INTO klines_1m
        (symbol, interval, open_time_ms, close_time_ms, open, high, low, close, volume,
         quote_volume, trade_count, taker_buy_base_volume, taker_buy_quote_volume,
         ignore_value, contract_type, status, listing_ts_ms, collected_at_ms, raw_json)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ''', rows)
    conn.commit()
    return res.rowcount


# === Orchestration ===
def backfill_symbol_klines(conn, limiter: RateLimiter, symbol: str, days: int,
                           intervals: list, status: str = 'TRADING'):
    end_ms = int(time.time() * 1000)
    target_start = end_ms - days * 86400 * 1000
    for interval in intervals:
        existing_min, existing_max = get_existing_range(conn, symbol, interval)
        # Determine gap: fill from target_start to (existing_min - 1) and from (existing_max + 1) to end_ms
        gaps = []
        if existing_min is None:
            gaps.append((target_start, end_ms))
        else:
            if target_start < existing_min:
                gaps.append((target_start, existing_min - 1))
            if existing_max < end_ms - INTERVAL_MS[interval]:
                gaps.append((existing_max + INTERVAL_MS[interval], end_ms))
        total = 0
        for g_start, g_end in gaps:
            inserted = fetch_and_insert_klines(conn, limiter, symbol, interval,
                                              g_start, g_end, status)
            total += inserted
        if total or gaps:
            log({'event': 'kline_done', 'symbol': symbol, 'interval': interval,
                 'inserted': total, 'gaps': len(gaps)})


def backfill_symbol_aggtrades(conn, limiter: RateLimiter, symbol: str, days: int):
    end_ms = int(time.time() * 1000)
    target_start = end_ms - days * 86400 * 1000
    existing_min, existing_max = get_existing_range(conn, symbol, '1s_perp')
    gaps = []
    if existing_min is None:
        gaps.append((target_start, end_ms))
    else:
        if target_start < existing_min:
            gaps.append((target_start, existing_min - 1))
        if existing_max < end_ms - 60_000:
            gaps.append((existing_max + 1, end_ms))
    total = 0
    for g_start, g_end in gaps:
        inserted = fetch_and_insert_aggtrades_1s(conn, limiter, symbol, g_start, g_end)
        total += inserted
    if total or gaps:
        log({'event': 'aggtrades_done', 'symbol': symbol, 'inserted': total, 'gaps': len(gaps)})


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--days', type=int, default=DEFAULT_DAYS)
    p.add_argument('--bwe-only', action='store_true', help='Only BWE symbols (skip TRADING/SETTLING phases)')
    p.add_argument('--skip-aggtrades', action='store_true', help='Skip 1s aggTrades (klines only)')
    p.add_argument('--rate', type=int, default=WEIGHT_BUDGET_PER_MIN)
    args = p.parse_args()

    log({'event': 'orchestrator_start', 'args': vars(args)})

    limiter = RateLimiter(args.rate)
    conn = sqlite3.connect(DB, timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA wal_autocheckpoint=2000")  # 2000 pages = ~8MB autocheckpoint

    # Discover symbols
    bwe_syms = sorted(get_bwe_symbols(7))
    trading, settling = get_market_perp_symbols(limiter)
    bwe_in_trading = sorted(s for s in bwe_syms if s in trading)
    rest_trading = sorted(trading - set(bwe_syms))
    log({'event': 'symbols_discovered', 'bwe': len(bwe_syms),
         'bwe_in_trading': len(bwe_in_trading),
         'rest_trading': len(rest_trading), 'settling': len(settling)})

    # Phase A: BWE × klines + 1s aggTrades
    log({'event': 'phase_A_start', 'symbols': len(bwe_in_trading)})
    for i, sym in enumerate(bwe_in_trading):
        backfill_symbol_klines(conn, limiter, sym, args.days, KLINE_INTERVALS, 'TRADING')
        if not args.skip_aggtrades:
            backfill_symbol_aggtrades(conn, limiter, sym, args.days)
        log({'event': 'phase_A_progress', 'i': i+1, 'total': len(bwe_in_trading), 'sym': sym})

    if args.bwe_only:
        log({'event': 'orchestrator_done', 'phases_skipped': ['B', 'C']})
        return

    # Phase B: rest of TRADING × klines (no 1s)
    log({'event': 'phase_B_start', 'symbols': len(rest_trading)})
    for i, sym in enumerate(rest_trading):
        backfill_symbol_klines(conn, limiter, sym, args.days, KLINE_INTERVALS, 'TRADING')
        log({'event': 'phase_B_progress', 'i': i+1, 'total': len(rest_trading), 'sym': sym})
        if (i + 1) % 25 == 0:  # checkpoint every 25 symbols to prevent WAL bloat
            res = conn.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
            log({'event': 'wal_checkpoint', 'phase': 'B', 'after_sym': sym, 'result': res})

    # Phase C: SETTLING × klines (delisting)
    log({'event': 'phase_C_start', 'symbols': len(settling)})
    for i, sym in enumerate(sorted(settling)):
        backfill_symbol_klines(conn, limiter, sym, args.days, KLINE_INTERVALS, 'SETTLING')
        log({'event': 'phase_C_progress', 'i': i+1, 'total': len(settling), 'sym': sym})
        if (i + 1) % 25 == 0:
            res = conn.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
            log({'event': 'wal_checkpoint', 'phase': 'C', 'after_sym': sym, 'result': res})

    log({'event': 'orchestrator_done'})
    conn.close()


if __name__ == '__main__':
    main()
