# Codex Task #4 — Fetch 15m Klines from Binance for R5 Granularity Upgrade

## Mission

抓取 **327 symbols × per-symbol time range** 的 15m kline 数据 (Binance Futures USD-M),
存为 JSON 兼容 BWE Autoresearch legacy_market_cache 格式. 用于 R5 7d hold 24h-168h 段
颗粒度升级 (1m for 0-24h, **15m for 24h-168h** 替代当前 1h).

## Hard safety rules

- 只读 + 写抓取数据, **不动**任何现有 BWE 文件
- **不要动** R5 main loop (`C:\bwe_compute\round5.pid` 跑着,不要 stop)
- **不要动** 当前 combined builder 输出 `event_windows_7d.parquet`
- 不调用任何下单 endpoint (klines 是 read-only public market data)
- 不读 secrets / API keys (klines 是 public, 不需 key)
- 输出 **只**写到 `/Volumes/T9/BWE/30_DATA/reference/legacy_market_cache/r5_15m_collection/`
- 进度日志 写到 `/Volumes/T9/BWE/40_EXPERIMENTS/round4/99_logs/codex_15m_fetch.log`

## Input

`/Volumes/T9/BWE/40_EXPERIMENTS/round4/per_symbol_15m_fetch_ranges.csv`

Schema:
- `api_symbol`: string (e.g. `BTCUSDT`, `RAVEUSDT`)
- `fetch_start_ms`: int (1h before earliest event_ts for this symbol)
- `fetch_end_ms`: int (168h after latest event_ts for this symbol)
- `n_events`: int (informational, how many events use this symbol)

327 rows total. Per symbol time span varies (some 1 day, some 5 months).

## Binance API spec

```
GET https://fapi.binance.com/fapi/v1/klines
  ?symbol={SYMBOL}
  &interval=15m
  &startTime={fetch_start_ms}
  &endTime={fetch_end_ms}
  &limit=1500
```

**Response**: list of arrays:
```
[
  [open_time_ms, open_str, high_str, low_str, close_str, volume_str,
   close_time_ms, quote_volume_str, n_trades, taker_buy_base, taker_buy_quote, ignore],
  ...
]
```

Per call max 1500 bars = 15 days × 4 bars/h × 24h = 1500 / 96 bars/day = **15 days per call max**.

Per-symbol fetch may need multiple calls (paginate by startTime advance).
e.g. RAVEUSDT span 18 days = 2 calls.

## Network

Mac is behind potential proxy/firewall. Try in order:
1. Direct HTTPS (binance fapi public endpoints often accessible)
2. If 451/403/timeout: proxy `http://127.0.0.1:7897` (Clash Verge for Hermes)
3. Hermes scripts use these env vars:
   ```
   HTTP_PROXY=http://127.0.0.1:7897
   HTTPS_PROXY=http://127.0.0.1:7897
   ALL_PROXY=socks5h://127.0.0.1:7897
   ```

## Rate limit

Binance futures klines call costs **5 weight** per request. Limit 2400 weight/min.
**Max 480 calls/min** safe rate. With 327 symbols × ~3-5 calls/symbol average = 1000-1500 total
calls. Throttle to **~5 calls/sec** (300/min) for safety margin = 5-7 min total fetch time.

If you hit 429 rate limit: sleep 60s + retry.

## Output format (must match PATTERN_A)

For each symbol, write **ONE merged JSON file**:
```
/Volumes/T9/BWE/30_DATA/reference/legacy_market_cache/r5_15m_collection/
   ohlcv_window_binanceusdm_<SYMBOL>_15m_<hash>.json
```

Where `<hash>` is 12-char hex (e.g. md5 of "{symbol}_15m_r5_collection")[:12].

**Content** (list, sorted by ts_ms ascending, deduped):
```json
[
  {
    "ts_ms": 1775106360000,
    "open": 0.4954,
    "high": 0.4955,
    "low": 0.4953,
    "close": 0.4955,
    "volume": 7360.0,
    "close_time_ms": 1775106419999,
    "quote_volume": 3646.4467
  },
  ...
]
```

## Implementation guidance

Write a Python script `scripts/fetch_15m_klines.py` (Mac venv `/tmp/codex_round4_venv/bin/python`):

```python
import csv, hashlib, json, os, time
from pathlib import Path
import requests

OUT_DIR = Path("/Volumes/T9/BWE/30_DATA/reference/legacy_market_cache/r5_15m_collection")
OUT_DIR.mkdir(parents=True, exist_ok=True)
LOG = Path("/Volumes/T9/BWE/40_EXPERIMENTS/round4/99_logs/codex_15m_fetch.log")
RANGES_CSV = Path("/Volumes/T9/BWE/40_EXPERIMENTS/round4/per_symbol_15m_fetch_ranges.csv")

def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with LOG.open("a") as f:
        f.write(line + "\n")

# Try direct, fallback to proxy
PROXIES_DIRECT = None
PROXIES_CLASH = {
    "http": "http://127.0.0.1:7897",
    "https": "http://127.0.0.1:7897",
}

def fetch_chunk(symbol, start_ms, end_ms, proxies):
    url = "https://fapi.binance.com/fapi/v1/klines"
    params = {"symbol": symbol, "interval": "15m",
              "startTime": start_ms, "endTime": end_ms, "limit": 1500}
    r = requests.get(url, params=params, proxies=proxies, timeout=30)
    r.raise_for_status()
    return r.json()

def fetch_symbol(symbol, start_ms, end_ms):
    """Paginate fetch until we cover [start_ms, end_ms]."""
    all_bars = []
    cursor = start_ms
    proxies = None  # try direct first
    while cursor < end_ms:
        chunk_end = min(cursor + 1500 * 15 * 60 * 1000, end_ms)
        try:
            chunk = fetch_chunk(symbol, cursor, chunk_end, proxies)
        except (requests.HTTPError, requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            if proxies is None:
                proxies = PROXIES_CLASH
                log(f"  {symbol}: switching to proxy")
                continue
            log(f"  {symbol}: proxy also failed, skip")
            break
        if not chunk:
            break
        all_bars.extend(chunk)
        last_close = chunk[-1][6]  # close_time_ms
        cursor = last_close + 1
        time.sleep(0.2)  # 5 req/sec rate limit
    # dedupe by open_time_ms
    seen = set()
    dedup = []
    for bar in all_bars:
        ts = bar[0]
        if ts in seen: continue
        seen.add(ts)
        dedup.append({
            "ts_ms": int(bar[0]),
            "open": float(bar[1]),
            "high": float(bar[2]),
            "low": float(bar[3]),
            "close": float(bar[4]),
            "volume": float(bar[5]),
            "close_time_ms": int(bar[6]),
            "quote_volume": float(bar[7]),
        })
    return sorted(dedup, key=lambda x: x["ts_ms"])

def main():
    rows = list(csv.DictReader(open(RANGES_CSV)))
    log(f"=== fetch 15m klines for {len(rows)} symbols ===")
    for i, row in enumerate(rows, 1):
        sym = row["api_symbol"]
        start = int(row["fetch_start_ms"])
        end = int(row["fetch_end_ms"])
        h = hashlib.md5(f"{sym}_15m_r5_collection".encode()).hexdigest()[:12]
        out_file = OUT_DIR / f"ohlcv_window_binanceusdm_{sym}_15m_{h}.json"
        if out_file.exists() and out_file.stat().st_size > 1000:
            log(f"  [{i}/{len(rows)}] {sym}: SKIP (already exists, {out_file.stat().st_size} bytes)")
            continue
        bars = fetch_symbol(sym, start, end)
        if bars:
            out_file.write_text(json.dumps(bars))
            log(f"  [{i}/{len(rows)}] {sym}: {len(bars)} bars -> {out_file.name}")
        else:
            log(f"  [{i}/{len(rows)}] {sym}: NO DATA")
    log("=== DONE ===")

if __name__ == "__main__":
    main()
```

Save as `/Volumes/T9/BWE/20_CODE/Autoresearch/scripts/fetch_15m_klines.py` then run:
```bash
nohup /tmp/codex_round4_venv/bin/python scripts/fetch_15m_klines.py > /tmp/codex_15m.out 2>&1 &
```

Idempotent (skip existing files), can resume if interrupted.

## 期望耗时

327 symbols × ~3-5 calls × 0.2s sleep + network = **5-15 min** total.

## 汇报格式 (中文简洁)

```
=== 15m kline fetch ===
- 总 symbols: 327
- 成功: N (覆盖 X% events)
- 失败/无数据: M (列出 symbol)
- 总 bars 抓取: K
- 输出目录: /Volumes/T9/BWE/30_DATA/reference/legacy_market_cache/r5_15m_collection/
- 总耗时: T 秒

[安全确认]
- 未动 R5 main loop ✓
- 未动 event_windows_7d.parquet ✓
- 未读 secrets ✓
- 未调下单端点 ✓
```
