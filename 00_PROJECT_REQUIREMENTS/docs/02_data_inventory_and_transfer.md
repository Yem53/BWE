# 02. 数据清单与迁移指南

## 需要从 Mac mini 带到 5090 机器的数据

### 必须复制

```text
/Users/ye/Desktop/Github/Autoresearch
/Users/ye/.hermes/research/bwe_three_channel_fullrun3/binance_event_features_20260425_30d
/Users/ye/.hermes/research/bwe_autoresearch_entry_v5_20260425
/Users/ye/Downloads/bwe_entry_research_v5_package
/Users/ye/.hermes/research/*/market_cache  # BWE legacy cache, optional but now included on T9
```

### 建议复制

```text
/Users/ye/.hermes/research/bwe_autoresearch_feature_v3_20260425
/Users/ye/.hermes/research/bwe_autoresearch_entry_v4_20260425
/Users/ye/.hermes/research/bwe_deep_autoresearch_20260425
/Users/ye/Desktop/Telegram
```

## 5090 机器建议目录

```text
/data/bwe/v6/
  code/Autoresearch
  input/binance_event_features_20260425_30d
  reference/bwe_autoresearch_entry_v5_20260425
  reference/bwe_entry_research_v5_package
  reference/legacy_market_cache
  reference/v3_v4_reports
  telegram_exports
  runs
  cache
  logs
```

## 不建议放在内存盘

这些要放 SSD，不要放 tmpfs：

- parquet 原始数据
- full candidate checkpoints
- deep replay outputs
- portfolio replay results
- LLM round artifacts

## 需要在 5090 机器上先做的校验

1. 所有 parquet 能读。
2. 行数和 Mac mini 快照一致。
3. `event_id` 能稳定生成。
4. `bwe_events_recent_binance_features.parquet` 和 forward 表能按事件对齐。
5. raw mark/premium path 覆盖所有 active symbol event。
6. trade kline 缺失要明确标记，不能假装已存在。
7. 如果使用 `legacy_market_cache`，必须先解析成规范 parquet，并生成覆盖率报告。
8. 进入 `medium` 前必须生成 `trade_kline_coverage_report.csv`。
9. 进入 `max_alpha` 前必须决定主路径精度：`1m_trade_kline`、混合路径，或 `1m_mark` fallback。

## 校验输出

迁移后先生成：

```text
data_copy_audit.json
data_copy_audit.md
parquet_row_counts.csv
feature_coverage_by_channel.csv
missing_required_files.csv
```

没有通过数据校验，不允许跑 v6 full。
