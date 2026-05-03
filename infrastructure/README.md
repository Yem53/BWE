# BWE Infrastructure

This directory contains the infrastructure code + configs needed to run BWE collectors / paper-LIVE on **any machine** (Mac mini, Windows, Linux VPS).

## Layout

```
infrastructure/
├── collectors/                     # Python collector scripts
│   ├── binance_futures_1m_collector.py    # 1m/3m/5m/15m/1h klines (one script, different configs)
│   ├── binance_futures_metric_collector.py # OI / funding / top_LS / mark_price / etc.
│   ├── binance_24h_ticker_collector.py     # 24h ticker
│   ├── binance_index_price_collector.py    # Index price klines
│   ├── binance_liquidation_collector.py    # Binance fstream liquidations (US-blocked at data layer)
│   ├── binance_perp_1s_collector.py        # 1s aggTrades aggregated bars (BWE-涉及 syms)
│   ├── binance_daily_snapshot_collector.py # Daily exchangeInfo / leverageBracket
│   ├── binance_futures_feature_joiner.py   # Cross-table feature join
│   ├── bwe_matrix_monitor.py               # BWE Telegram channel listener
│   ├── bwe_matrix_watchdog.py              # Watchdog for the listener
│   ├── okx_liquidation_collector.py        # OKX SWAP liquidations (US-direct, no proxy)
│   ├── bybit_liquidation_collector.py      # Bybit linear liquidations (US-direct)
│   ├── collectors_watchdog.sh              # cron watchdog (Mac/Linux)
│   └── configs/
│       ├── binance_futures_1m_collector_config.json
│       ├── binance_futures_3m_collector_config.json
│       ├── binance_futures_5m_collector_config.json
│       ├── binance_futures_15m_collector_config.json
│       ├── binance_futures_1h_collector_config.json
│       └── binance_futures_metric_collector_config.json
├── clashverge/
│   └── LProtonCrypto.template.yaml         # Clash Verge profile (sanitized — Proton creds redacted)
├── launchd/
│   └── *.plist.template.plist              # macOS LaunchAgents templates
├── windows-setup/
│   ├── SETUP_PROMPT.md                     # ← Paste this into Claude Code on Windows to bootstrap
│   └── (TODO: setup.ps1 for one-shot install)
├── docs/
│   └── (architecture diagrams, runbooks)
└── .env.example                            # Environment variable template
```

## Architecture

```
                BWE Telegram channels (3 channels)
                            │
                            ▼
                bwe_matrix_monitor.py
                            │
                  bwe_matrix_posts.jsonl  ◄──── consumed by paper-LIVE + backtest
                            │
                            ▼
                paper_shadow_live.py / multi_paper_runner.py
                            │
                       Telegram alerts (OPEN / CLOSE / heartbeat)


                Binance fapi REST  ──proxy──►  binance_*_collector.py  ──► binance_futures_1m.sqlite3
                                                                                  │
                                                                                  ▼
                OKX/Bybit fstream WS (direct)  ──► okx/bybit_liq_collector.py  ──► (same DB)


               WAL checkpointer daemon (every 60s)
               Collector watchdog (every 60s, restart dead processes)
```

## Geographic constraints (US user)

| Endpoint | Direct US | Via Proton VPN | Via AWS Tokyo |
|---|---|---|---|
| binance fapi REST | 451 (blocked) | ✅ 200 | ✅ 200 |
| binance fstream WS | handshake OK, **no frames** | handshake OK, **no frames** | handshake OK, **no frames** |
| OKX REST | 451 (CloudFront block) | ✅ 200 | ✅ 200 |
| OKX WS | ✅ frames | ✅ frames | ✅ frames |
| Bybit REST | 451 (CloudFront block) | ✅ 200 | ✅ 200 |
| Bybit WS | ✅ frames | ✅ frames | ✅ frames |

**Conclusion**: Binance fstream is unobtainable from any commercial US-accessible node (Proton, AWS, Vultr, etc.) due to deep fingerprint detection. Use OKX + Bybit liquidations as proxy (covers ~80-90% of Binance perp universe).

## Critical notes

1. **Database is local-only** (sqlite3, not in git). 22+ GB. Both Mac and Windows independently collect to their own DB.
2. **`.env` is not in git**. Transfer manually via password manager.
3. **Proton credentials sanitized**. Use your own Proton subscription URL when importing on a new machine.
4. **All collectors are crash-resilient**: systemd / cron watchdog respawns dead processes.

## How to verify a fresh deployment

```bash
# 1. Proxy works
curl -o /dev/null -w "fapi: %{http_code}\n" https://fapi.binance.com/fapi/v1/exchangeInfo
# Should be 200

# 2. OKX direct (no proxy)
unset HTTP_PROXY HTTPS_PROXY
curl -o /dev/null -w "okx: %{http_code}\n" https://www.okx.com/api/v5/public/instruments?instType=SWAP
# Should be 200

# 3. SQLite DB created
sqlite3 ./30_DATA/binance_collectors_runtime/binance_futures_1m.sqlite3 \
    "SELECT name FROM sqlite_master WHERE type='table'"

# 4. BWE jsonl alive
tail -1 ./30_DATA/bwe_logs/bwe_matrix_posts.jsonl | python3 -c "import json,sys; print(json.loads(sys.stdin.read())['text'][:80])"
```

See `windows-setup/SETUP_PROMPT.md` for full bootstrap on a fresh Windows machine.
