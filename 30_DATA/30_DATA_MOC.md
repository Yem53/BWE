---
type: moc
tags: [moc, data]
created: 2026-05-02
---

# 📊 30 数据 — MOC

> Binance K 线 + BWE 消息 + caches 数据存储索引.

## 数据位置

### Live Collectors Runtime (主)
**`/Volumes/T9/BWE/30_DATA/binance_collectors_runtime/`**
- `binance_futures_1m.sqlite3` (12 GB, 单表 multi-interval)
  - `klines_1m` 表 with `interval` column: 1s, 1m, 3m, 5m, 15m, 1h
  - `mark_price_1m`, `funding_rate`, `open_interest_5m`, `top_trader_long_short_*`, etc.
  - `ticker_24h`, `liquidations`
- `MIGRATION_LOG.md` — 完整迁移记录
- `restart_all_collectors.sh` — 一键重启
- `logs/` — collector 日志

### BWE Messages
**`/Volumes/T9/BWE/30_DATA/bwe_logs/`**
- `bwe_matrix_posts.jsonl` — Telegram pump alerts (主 event source)
- `bwe_matrix_health.jsonl` — monitor 健康
- `bwe_matrix_events_legacy_*.jsonl` — 历史事件归档

### Historical Reference
**`/Volumes/T9/binance data/historical/`**
- `binance_extended_history.sqlite3` (3.3 GB, 长期历史)

### Cache + 其它
**`/Volumes/T9/BWE/30_DATA/cache/`** — 实验 cache
**`/Volumes/T9/BWE/30_DATA/input/`** — 输入数据
**`/Volumes/T9/BWE/30_DATA/reference/`** — 参考数据

## 数据 Schema 摘要

### `klines_1m` (multi-interval)
```sql
symbol TEXT, interval TEXT, open_time_ms INTEGER, close_time_ms INTEGER,
open REAL, high REAL, low REAL, close REAL, volume REAL,
quote_volume REAL, trade_count INTEGER, taker_buy_base_volume REAL,
taker_buy_quote_volume REAL, contract_type TEXT, status TEXT,
listing_ts_ms INTEGER, collected_at_ms INTEGER, raw_json TEXT
```

### Per-interval row counts (实时)
| Interval | Rows | Backfill 状态 |
|---|---|---|
| 1s | 2.5M+ (backfilling) | 30d 进行中 (~12h) |
| 1m | 7.39M | ✅ 30d 完整 |
| 3m | 161K | ✅ 30d 完整 |
| 5m | 96K | ✅ 30d 完整 |
| 15m | 32K | ✅ 30d 完整 |
| 1h | 7.4K | ✅ 30d 完整 |

## Active Collectors (T9 写入)

| PID | Script | Interval | Poll |
|---|---|---|---|
| 89315 | binance_futures_1m_collector | 1m | 60s |
| 7085 | (same script) | 3m | 180s |
| 7099 | (same script) | 5m | 300s |
| 7114 | (same script) | 15m | 900s |
| 7120 | (same script) | 1h | 3600s |
| 38155 | binance_spot_1s_collector | 1s | 1s |
| 89347 | binance_futures_metric_collector | mark/funding/OI/LS | 60s |
| 91942 | binance_24h_ticker_collector | 24h ticker | varies |
| 91943 | binance_index_price_collector | index | varies |
| 91944 | binance_liquidation_collector | liquidations | varies |
| 67006 | bwe_matrix_monitor | BWE Telegram | 1s |

## Backup + Migration

- 之前在 Mac (`~/.hermes/research/`), 已全迁 T9 (2026-05-02)
- Mac 留 `.MIGRATED_TO_T9.20260502` 备份 (12 GB)
- Symlink 兼容老 hardcoded paths
- Rollback 步骤见 [[binance_collectors_runtime/MIGRATION_LOG]]

## 文件系统

- T9: exFAT (跨 Mac/Win), 4TB 总, 966GB free
- SQLite WAL mode, performance OK (700K rows/s, 23K queries/s)
- APFS 转换待定 (实测 0 lock errors, 暂保 exFAT)

## 相关

- [[../00_INDEX|HOME]]
- [[binance_collectors_runtime/MIGRATION_LOG|Migration Log]]
- [[../40_EXPERIMENTS/round5/specs/PAPER_BACKTEST_DRIFT_LOG|Drift Log (data quality)]]

## 📁 All folder indexes (auto-link)

> Auto-generated indexes for every subfolder with 3+ .md files. Click to explore.

    - [[bwe_autoresearch_entry_v5_20260425/_FOLDER_INDEX|📁 bwe_autoresearch_entry_v5_20260425/]]
    - [[bwe_entry_research_v5_package/_FOLDER_INDEX|📁 bwe_entry_research_v5_package/]]

## 🗂 Standalone
- [[coverage_report|Binance Event Features 30d Coverage Report]]
