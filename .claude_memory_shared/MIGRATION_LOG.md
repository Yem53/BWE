# BWE Data Migration: Mac → T9 (2026-05-02)

## 概述

把所有 BWE/binance 相关数据 + collector 从 Mac 本地 (`/Users/ye/.hermes/research/`)
迁移到 T9 移动硬盘 (`/Volumes/T9/BWE/30_DATA/`), 同时升级单 1m → 多 timeframe collector
(1m/3m/5m/15m/1h).

## 迁移内容

### 数据迁移
| 原位置 (Mac) | 新位置 (T9) | 大小 |
|---|---|---|
| `~/.hermes/research/binance_futures_1m_collector_runtime/binance_futures_1m.sqlite3` | `/Volumes/T9/BWE/30_DATA/binance_collectors_runtime/binance_futures_1m.sqlite3` | 12 GB |
| `~/.hermes/research/binance_futures_1m_collector_runtime/binance_futures_1m.sqlite3-wal` | (同上 dir) | 1.1 GB |
| logs/ | (同上 dir/logs) | small |

### 配置文件改动 (8 个文件)
| 文件 | 改动 |
|---|---|
| `~/.hermes/scripts/binance_futures_1m_collector_config.json` | `db_path` + `runtime_dir` → T9 |
| `~/.hermes/scripts/binance_futures_metric_collector_config.json` | `db_path` + `runtime_dir` → T9 |
| `~/.hermes/scripts/binance_24h_ticker_collector.py` | hardcode `DB_PATH` → T9 |
| `~/.hermes/scripts/binance_index_price_collector.py` | hardcode → T9 |
| `~/.hermes/scripts/binance_liquidation_collector.py` | hardcode → T9 |
| `~/.hermes/scripts/binance_daily_snapshot_collector.py` | hardcode → T9 |
| `~/.hermes/scripts/binance_futures_feature_joiner.py` | hardcode → T9 |
| `~/.hermes/scripts/run_binance_futures_*_collector.sh` (wrapper scripts) | `RUNTIME_DIR` → T9 |
| `~/Library/LaunchAgents/ai.hermes.binance-futures-{1m,metric}-collector.plist` | log paths → T9 |
| `/Volumes/T9/BWE/40_EXPERIMENTS/round5/src/paths.py` | `LIVE_DB` → T9 |

### Symlink 兼容
Mac 老路径仍可访问 (透明指向 T9):
```
~/.hermes/research/binance_futures_1m_collector_runtime/binance_futures_1m.sqlite3 → 
  /Volumes/T9/BWE/30_DATA/binance_collectors_runtime/binance_futures_1m.sqlite3
```

老 Mac DB 文件保留作 rollback (改名加 `.MIGRATED_TO_T9.20260502` 后缀)。

## 升级: Multi-Timeframe Collector

DB schema 已设计支持多 interval (有 `interval TEXT` 列), 单表 `klines_1m` 存所有 tf 数据。

新增 4 个 collector instance (复用同一个 collector 脚本, 不同 config):
| Interval | Config | Poll seconds | 备注 |
|---|---|---|---|
| 1m | `binance_futures_1m_collector_config.json` | 60 | 已存在 |
| 3m | `binance_futures_3m_collector_config.json` | 180 | NEW |
| 5m | `binance_futures_5m_collector_config.json` | 300 | NEW |
| 15m | `binance_futures_15m_collector_config.json` | 900 | NEW |
| 1h | `binance_futures_1h_collector_config.json` | 3600 | NEW |

启动后 1 分钟数据状态:
```
interval | rows (含 30d backfill)
─────────┼─────
1m       | 7,372,600
3m       | 40,066
5m       | 24,165
15m      | 8,378
1h       | 1,918
```

## 1s K 线 (未实施, 备用方案)

Binance fapi 不支持 1s kline interval. 选项:
1. **Spot 1s kline** (api.binance.com /api/v3/klines): 支持, 但 spot price ≠ perp price (~0.05% drift)
2. **aggTrades aggregate to 1s**: 自己写 collector 收 ms 级 trades, aggregate 到 1s
3. **paper-LIVE mark price 实时记录**: 已经在做 (paper_shadow_live)

**当前决策**: 不做 1s collector. paper-LIVE 已捕捉实时 mark price, 1s 数据成本高 (估 1GB/day raw aggTrades 全市场)。
未来如需历史 1s 数据, 用 aggTrades on-demand 拉取 (binance 保留 ~3 天)。

## 当前运行进程 (postmigration)

```
Writers (写入 T9 DB):
  PID 89315  binance_futures_1m_collector  (1m interval)
  PID 89347  binance_futures_metric_collector (mark/funding/OI/LS)
  PID 91942  binance_24h_ticker_collector
  PID 91943  binance_index_price_collector
  PID 91944  binance_liquidation_collector
  PID 7085   binance_futures_3m_collector
  PID 7099   binance_futures_5m_collector
  PID 7114   binance_futures_15m_collector
  PID 7120   binance_futures_1h_collector

Readers:
  PID 92288  paper_shadow_live (paper-LIVE mode + testnet)
  PID 34857  bwe_live_autotrader (用 alerts_v2_state, 不读此 DB)
```

## Rollback 步骤 (如需)

如需恢复到 Mac 本地存储:

```bash
# 1. Stop all collectors
pkill -f "binance_futures.*collector"

# 2. Restore Mac DB
cd /Users/ye/.hermes/research/binance_futures_1m_collector_runtime/
rm binance_futures_1m.sqlite3{,-wal,-shm}  # remove symlinks
mv binance_futures_1m.sqlite3.MIGRATED_TO_T9.20260502 binance_futures_1m.sqlite3
mv binance_futures_1m.sqlite3-wal.MIGRATED_TO_T9.20260502 binance_futures_1m.sqlite3-wal
mv binance_futures_1m.sqlite3-shm.MIGRATED_TO_T9.20260502 binance_futures_1m.sqlite3-shm

# 3. Restore configs (all .bak.20260502 files)
for cfg in /Users/ye/.hermes/scripts/binance_futures_*_collector_config.json; do
    [ -f "$cfg.bak.20260502" ] && cp "$cfg.bak.20260502" "$cfg"
done

# Restore wrapper scripts
for ws in /Users/ye/.hermes/scripts/run_binance_futures_*_collector.sh; do
    [ -f "$ws.bak.20260502" ] && cp "$ws.bak.20260502" "$ws"
done

# Restore plists
for plist in ~/Library/LaunchAgents/ai.hermes.binance-futures-{1m,metric}-collector.plist; do
    [ -f "$plist.bak.20260502" ] && cp "$plist.bak.20260502" "$plist"
done

# Restore paths.py
cp /Volumes/T9/BWE/40_EXPERIMENTS/round5/src/paths.py.bak.20260502 \
   /Volumes/T9/BWE/40_EXPERIMENTS/round5/src/paths.py

# Restore hardcoded scripts
for s in binance_24h_ticker_collector.py binance_index_price_collector.py binance_liquidation_collector.py binance_daily_snapshot_collector.py binance_futures_feature_joiner.py; do
    [ -f /Users/ye/.hermes/scripts/$s.bak.20260502 ] && cp /Users/ye/.hermes/scripts/$s.bak.20260502 /Users/ye/.hermes/scripts/$s
done

# 4. Restart collectors via launchctl bootstrap
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/ai.hermes.binance-futures-1m-collector.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/ai.hermes.binance-futures-metric-collector.plist
```

## 释放 Mac 空间 (确认稳定后)

迁移已稳定运行 24h+ 后, 可删除 Mac 老 DB 备份释放 12GB:

```bash
rm /Users/ye/.hermes/research/binance_futures_1m_collector_runtime/binance_futures_1m.sqlite3{,-wal,-shm}.MIGRATED_TO_T9.20260502
```

## 验证 Checklist

- [x] DB 复制完成, row count 一致 (7,367,262 rows)
- [x] 所有 collector 写 T9 DB (lsof 验证)
- [x] paper-LIVE 读 T9 DB (paths.py 更新, 启动日志显示 T9 path)
- [x] Multi-timeframe data flowing (3m/5m/15m/1h rows 在累积)
- [x] Symlink 兼容老 hardcoded path
- [x] Rollback 脚本准备好
- [x] Mac launchd plists 更新到 T9 paths
- [ ] 24h 后稳定性验证 (待观察)
- [ ] 删除 Mac 老 .MIGRATED_TO_T9 备份 (待确认)

---

## 2026-05-02 11:15 UTC: BWE 消息 + 1s K线 补充迁移

### BWE 消息缓存迁移
| 文件 | 原位置 | 新位置 | 大小 |
|---|---|---|---|
| `bwe_matrix_posts.jsonl` | `~/.hermes/logs/` | `/Volumes/T9/BWE/30_DATA/bwe_logs/` | 2 MB |
| `bwe_matrix_health.jsonl` | `~/.hermes/logs/` | `/Volumes/T9/BWE/30_DATA/bwe_logs/` | 21 MB |
| `bwe_matrix_events_legacy_*.jsonl` | `~/.hermes/logs/` | `/Volumes/T9/BWE/30_DATA/bwe_logs/` | 4.3 MB |

**改动**:
- `bwe_matrix_watchdog.py` hardcoded paths → T9
- `bwe_matrix_monitor.py` 启动 cmd 参数指 T9 path
- `paths.py` JSONL → T9
- 创建 Mac → T9 symlink (兼容老引用)
- Mac 老 jsonl 改名 `.MIGRATED_TO_T9.20260502`

**注意**: `bwe_live_autotrader (PID 34857)` 仍 use Mac symlink path 作 event_log. 它 file handle 在 mv 前已 open old inode, 可能 read stale data. **建议方便时重启 autotrader 让它重新 open via symlink → T9**.

### 1s K线 spot collector (NEW)
- 脚本: `binance_spot_1s_collector.py` (复制 1m collector 改 endpoint)
- 改动: `/fapi/v1/` → `/api/v3/`, base_url → spot api, 加 '1s' 到 INTERVAL_MS dict, 跳过 marginAsset filter
- Config: `binance_spot_1s_collector_config.json` (interval=1s, 30d backfill)
- 数据: 432 USDT spot pairs × 86400 sec/day × 30 day = **1.12B bars** total target
- 存储估算: ~112GB raw, ~32GB compressed
- Backfill 时间: ~12.4h sustained
- 当前 PID: 38155

### Final Process Inventory (16 processes)

**Writers (10 collectors)**:
1. PID 89315 binance_futures_1m_collector
2. PID 7085 binance_futures_3m_collector
3. PID 7099 binance_futures_5m_collector
4. PID 7114 binance_futures_15m_collector
5. PID 7120 binance_futures_1h_collector
6. PID 38155 binance_spot_1s_collector (backfilling 30d)
7. PID 89347 binance_futures_metric_collector
8. PID 91942 binance_24h_ticker_collector
9. PID 91943 binance_index_price_collector
10. PID 91944 binance_liquidation_collector
11. PID 67006 bwe_matrix_monitor (BWE Telegram → jsonl)

**Readers**:
- PID 84745 paper_shadow_live (read T9 DB + T9 jsonl)

**Other**:
- PID 34857 bwe_live_autotrader (uses old Mac path via symlink)

### Data Volume

```
T9 /Volumes/T9/BWE/30_DATA/ = 39 GB total

binance_collectors_runtime/binance_futures_1m.sqlite3:
  klines_1m table:
    - 1s:    362,000 rows (backfilling)
    - 1m:  7,385,731 rows (30d historical)
    - 3m:    161,040 rows
    - 5m:     96,624 rows
    - 15m:    32,208 rows
    - 1h:      7,392 rows
  + mark_price, funding_rate, OI, LS tables: ~25M rows total

bwe_logs/:
  - bwe_matrix_posts.jsonl: 2 MB (BWE Telegram pump alerts)
  - bwe_matrix_health.jsonl: 21 MB (monitoring)
  - bwe_matrix_events_legacy_*.jsonl: 4.3 MB (historical)
```
