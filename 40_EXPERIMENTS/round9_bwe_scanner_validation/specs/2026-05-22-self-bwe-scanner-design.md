---
type: spec
tags: [scanner, infrastructure, bwe-replica, data-collection, round9]
created: 2026-05-22
status: design
priority: high
---

# Self-Hosted BWE Scanner — Design Spec

> Brainstormed 2026-05-22. Implements a personal "BWE backend": real-time multi-window
> anomaly detection across all Binance USDT-M perps → fire alerts → archive as a research
> dataset + push a high-signal subset to Telegram.

## 1. Goal

Build a standalone service that **replicates BWE's detection logic** (reverse-engineered from
89k real channel messages) directly against Binance, so the user owns an independent real-time
monitoring + alert-archive system. Primary deliverable is the **structured alert archive** — a
growing research corpus the user mines later for new strategies. Telegram push is the
"it's working for me" surface.

## 2. Non-Goals (YAGNI — explicitly out of scope)

- **Not** required to improve the current live strategies (B / D / Champion_E). The Rule #0
  validation showed only a narrow, modest 1h-pump→B edge; the user explicitly de-scoped the
  "feed the bot" purpose. (The optional B-feed hook is deferred — see §11.)
- **No** changes to the live trading bot's Python (`live_runner.py`). Fully isolated process.
- **No** news/listing channels in v1 (BWE has Binance/Upbit listing + Korean monitors — a *different
  data source*, not price scanning). Noted as a separate future module (§11) for full BWE parity.

> Note: market cap **is** captured (see §2.5 / §6) — Rule #2 only forbids *using* market cap to
> define 妖币, not recording it. BWE includes it, so we include it (parity).
- **No** automatic strategy promotion — research on the archive is a separate, later effort
  gated by Rule #0 backtesting.

## 2.5 Parity & Surpass BWE (HARD REQUIREMENT)

User directive: **the system may only be stronger than BWE, never weaker.** Concretely:

**Parity (must match BWE):**
- All price windows BWE fires on: 3s/5s/10s/30s/60s/90s + 180s extreme (§5).
- 1h OI + price (§5).
- **Market cap + OI/marketcap ratio** in every alert (BWE includes these). Source: CoinGecko
  circulating-supply cache (refreshed daily; supply moves slowly), MC = `supply × live_price`,
  `oi_mc_ratio = OI_usd / MC`. Symbol→CoinGecko-id mapping table, cached. Missing-mapping → null
  (logged), never blocks the alert.

**Surpass (inherent architectural wins — no extra feature-piling needed):**
1. **Structured archive** (clean JSON) vs BWE's lossy Telegram text → directly research-ready.
2. **Zero parse loss** — the Round 6 audit found BWE's text parser dropped 47% of events; direct
   detection drops nothing.
3. **Lower latency** — direct Binance WS vs BWE's detect→format→push→our-scrape chain.
4. **Extensible windows** — can add windows BWE lacks (5m/15m momentum, short-window OI spikes,
   taker/CVD-flow anomalies) via config.
5. **Research-time feature join** — archive stores `symbol+ts`, so ATR/RSI/funding/CVD/vol-zscore
   can be joined from klines later → richer than BWE's fixed text fields.

These are acceptance criteria: a feature is not "done" if it's weaker than BWE's equivalent.

## 3. Background

- BWE's three channels were reverse-engineered (see `../parse_alerts.py`, `../data/alerts.jsonl`):
  BWE = all-perp price/OI scanner over fixed windows, pushes when a threshold is crossed.
  Confirmed exact windows + thresholds via histograms over 89k messages.
- Rule #0 validation (`../ec2_backtest_missed.py`): for the *current* strategies the marginal
  value is narrow (B benefits modestly from missed 1h pumps; D does not; 3s/180s are noise
  *for the current strategies*). → The collector is justified as **infrastructure / data
  collection** (a Rule #0 exemption), not as a current-strategy profit play.
- The live bot's `load_recent_bwe_symbols()` expects `{ts_ms, symbol}` JSON lines; the old
  `bwe_matrix_monitor.py` only wrote raw `text` — a format mismatch that (along with a missing
  feed file) left the BWE feed dead on EC2. This collector emits the parsed symbol directly.

## 4. Architecture

Standalone EC2 systemd process (`bwe-scanner.service`), isolated from the trading bot.

```
Binance WS  !markPrice@arr@1s  ─┐
                                ├─→ ws_feed: rolling price buffers (per symbol)
Binance REST openInterestHist ──┘        + OI buffers (5-min poll, all perps)
        │
        ▼
   detectors (PURE fns): per symbol, per window → |Δ| vs threshold → Alert[]
        │
        ├─→ store:  append JSONL (daily file) [+ optional SQLite mirror]  ← research corpus
        └─→ notify: Telegram push (high-signal subset only)
```

**Module boundaries (each independently testable):**

| File (`infrastructure/collectors/bwe_scanner/`) | Responsibility | Depends on |
|---|---|---|
| `ws_feed.py` | WS client (reconnect/backoff), rolling price buffers, OI poller | websocket, requests |
| `detectors.py` | **pure**: buffers → window Δ → threshold → `Alert` dataclasses | (none — pure) |
| `store.py` | append `Alert` to JSONL (daily) + optional SQLite | stdlib |
| `notify.py` | Telegram push of filtered subset (reuse bot token) | requests |
| `scanner.py` | main loop: wire feed→detect→store+notify; config; signals; heartbeat | all above |
| `config.json` | windows, thresholds, cooldowns, push filter, paths, exclude lists | — |
| `tests/` | pytest unit tests | pytest |

Rolling-buffer memory budget: short windows need 1s resolution for ~200s (≈200 samples/symbol);
the 1h window uses a 10s-downsampled ring (≈360 samples/symbol). ~400 symbols → a few MB. OK.

## 5. Detection windows + default thresholds

Defaults seeded from the reverse-engineered histograms (`../data/alerts.jsonl`); all tunable in
`config.json`. Fire when `|Δ%| ≥ threshold` over the window (both directions; sign recorded).

| window_type | window_sec | default threshold | source feed |
|---|---|---|---|
| `price_3s`  | 3   | 2.0% | pricechange |
| `price_5s`  | 5   | 3.0% | pricechange |
| `price_10s` | 10  | 3.0% | pricechange |
| `price_30s` | 30  | 4.0% | pricechange |
| `price_60s` | 60  | 5.0% | pricechange |
| `price_90s` | 90  | 5.0% | pricechange |
| `price_180s_extreme` | 180 | 8.0% | reserved6 |
| `oi_price_1h` | 3600 | price ≥5.0% **OR** OI ≥5.0% | oi_price |

Per `(symbol, window_type)` cooldown: default 600s (so a sustained move logs once, not every tick).
Universe: all USDT-M perps, ASCII symbols. **Default = capture everything (no mainstream exclusion)** —
a faithful BWE replica alerts on BTC/ETH too, and a research corpus wants full coverage; 妖币/mainstream
filtering happens at research time. A config flag can exclude mainstream if desired later.

## 6. Storage schema (the research corpus — primary deliverable)

Append-only JSONL, one alert per line, daily-rotated file `alerts_YYYY-MM-DD.jsonl`:

```json
{"ts_ms": 1779000000000, "symbol": "XXXUSDT", "window_type": "price_60s", "window_sec": 60,
 "price_chg_pct": 6.2, "oi_chg_pct": null, "price": 0.12345, "chg_24h_pct": 15.0,
 "quote_vol_24h": 1234567.0, "oi_usd": 4900000.0, "market_cap_usd": 8000000.0,
 "oi_mc_ratio_pct": 10.7, "fired_at": "2026-05-22T13:30:00Z"}
```

- `oi_chg_pct` / `oi_usd` non-null only for `oi_price_1h`. `chg_24h_pct` / `quote_vol_24h` enriched
  from a periodic `/fapi/v1/ticker/24hr` snapshot (1 call/min) so every alert carries context.
- `market_cap_usd` / `oi_mc_ratio_pct`: BWE-parity (§2.5) — MC from CoinGecko supply cache ×
  live price; null when symbol unmapped. These are fields only (Rule #2: never used to define 妖币).
- Optional SQLite mirror (`alerts.db`, same columns + indexes on symbol/ts/window_type) for
  queryable research. JSONL is the canonical store.
- **Location:** written on EC2 (`/home/ubuntu/bwe-scanner/data/`); **rsync to
  `/Volumes/T9/BWE/30_DATA/bwe_scanner_alerts/` periodically** (cron on Mac or push from EC2)
  so research runs on the Mac corpus.

## 7. Telegram delivery (high-signal subset)

Store **all** alerts; push only a configurable high-signal subset (default):
push if `window_type in {price_180s_extreme, oi_price_1h}` OR (`window_type in {price_60s,
price_90s}` AND `|price_chg_pct| ≥ 8.0`). Avoids flooding (BWE pricechange ≈360/day).

- Reuse the bot's Telegram token (`BWE_LIVE_TELEGRAM_BOT_TOKEN`); push to a **separate chat/channel**
  (`BWE_SCANNER_TELEGRAM_CHAT_ID`) so scanner alerts don't mix with trade alerts.
- Message format (bilingual, BWE-style), e.g.:
  `🔔 XXXUSDT +8.4% / 180s · 24h +15% · vol $1.2M`
- Per-symbol push cooldown (default 600s) independent of the storage cooldown.

## 8. Reliability

- systemd `bwe-scanner.service`: `Restart=on-failure`, append stdout/stderr logs, single-instance
  guard (pkill prior on start, like `run_live.sh`).
- WS reconnect with exponential backoff (reuse the proven pattern in
  `infrastructure/collectors/bwe_matrix_monitor.py`).
- Heartbeat: log + optional Telegram heartbeat every N min (symbols tracked, alerts fired,
  WS uptime, buffer depth). Stale-WS watchdog: if no WS message for >30s, force reconnect.
- Buffers are in-memory; a restart loses history and re-warms (~60 min for the 1h window). Acceptable.

## 9. Testing strategy (TDD)

- `detectors.py` (pure) — unit tests: synthetic buffer with known prices → assert correct Δ% and
  fire/no-fire at thresholds; multi-window; cooldown suppression; OI-OR-price logic.
- `store.py` — round-trip: write Alert → read back JSONL line → assert schema; assert the live
  bot's `load_recent_bwe_symbols()` can parse `{ts_ms,symbol}` from our lines (import + assert).
- `notify.py` — push-filter predicate unit tests (which alerts qualify); Telegram send mocked.
- `scanner.py` — `--dry-run` mode: no Telegram, print alerts to stdout; run live on EC2 ~5 min and
  eyeball that detections match real market moves (smoke test).

## 10. Config (`config.json`)

```json
{
  "windows": { "price_3s": {"sec": 3, "thr_pct": 2.0}, "...": {} },
  "oi_price_1h": {"sec": 3600, "price_thr_pct": 5.0, "oi_thr_pct": 5.0},
  "store_cooldown_sec": 600,
  "push_cooldown_sec": 600,
  "push_filter": {"types": ["price_180s_extreme", "oi_price_1h"], "short_window_min_pct": 8.0},
  "exclude_mainstream": true,
  "oi_poll_sec": 300,
  "ticker24h_poll_sec": 60,
  "paths": {"jsonl_dir": "/home/ubuntu/bwe-scanner/data", "sqlite": null},
  "telegram": {"enabled": true, "chat_id_env": "BWE_SCANNER_TELEGRAM_CHAT_ID",
               "token_env": "BWE_LIVE_TELEGRAM_BOT_TOKEN"}
}
```

## 11. Deployment + future

- Deploy under `/home/ubuntu/bwe-scanner/` on EC2 Tokyo (Binance reachable; US Mac is geo-blocked).
- systemd unit + secrets (reuse the bot's Telegram token; new chat id).
- Backfill note: no historical backfill — the corpus grows forward from launch. (Historical BWE
  messages already archived in `../data/alerts.jsonl` for past research.)
- Resources: current **t3.micro is sufficient** (measured 2026-05-22: load 0.04, 526 MB RAM free,
  17 GB disk free; scanner adds ~5-10% CPU, ~50-70 MB RAM, ~0.1-0.3 MB/day). **Add a 1 GB swapfile**
  as cheap insurance (1 GB-RAM box, zero swap currently). Monitor sustained CPU post-deploy; only
  consider t3.small if it ever sustains >20% (unlikely).
- **Deferred / future (not built now):**
  - **News/listing parity module** (for full BWE parity): Binance listing announcements + Korean/Upbit
    monitors. Different data source (announcement/news feeds, not price scanning) — separate module.
  - Extra surpass windows (5m/15m momentum, short-window OI spikes, taker/CVD anomalies).
  - Optional B-feed hook: write the validated `oi_price_1h` pump subset (24h ∈ [10,20%]) to the
    bot's `BWE_LIVE_BWE_LOG` — a one-line env toggle, only if later wanted.
  - Research phase: mine the archive for new strategies (Rule #0 backtesting applies there).

## 12. Success criteria

1. Service runs stably on EC2 (systemd, auto-reconnect) and fires alerts that visibly match real
   market moves (smoke-test verified).
2. All alerts persist to daily JSONL with the full schema; corpus syncs to `30_DATA` on the Mac.
3. Telegram pushes only the high-signal subset (no flood).
4. All unit tests pass; `detectors.py` is pure and fully covered.
5. Zero impact on the live trading bot (separate process, separate API session, weight budget
   respected: ~1 ticker call/min + ~OI polling ≤ a few hundred weight/min, well under 2400/min).
