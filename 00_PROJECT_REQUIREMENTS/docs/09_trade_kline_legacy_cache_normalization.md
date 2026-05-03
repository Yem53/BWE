# 09. Trade Kline 与 Legacy Cache 规范化

## 为什么必须做

v6 的完整策略搜索包含大量退出逻辑：

- fixed TP/SL
- first-touch
- trailing stop
- breakeven
- partial exit
- failed continuation
- indicator invalidation
- runner

这些退出逻辑对路径精度敏感。当前主数据包里：

```text
raw/local_kline_1m_event_window.parquet rows = 0
```

所以如果不补 trade kline，只能使用：

```text
path_resolution=1m_mark
```

这可以做早期研究，但不能把 first-touch 结果说成真实成交路径。

## 两个必须补强点

### 1. legacy_market_cache 规范化

T9 已带：

```text
data_snapshot/legacy_market_cache
```

它是旧 BWE run 的 OHLCV window JSON cache。v6 使用前必须先转成规范 parquet。

目标输出：

```text
normalized/legacy_trade_kline_1m_windows.parquet
normalized/legacy_market_cache_parse_audit.csv
normalized/legacy_market_cache_coverage_by_symbol.csv
normalized/legacy_market_cache_coverage_by_event.csv
```

最低字段：

```text
source_run
source_file
api_symbol
interval
open_time_ms
close_time_ms
open
high
low
close
volume
quote_volume
trade_count
taker_buy_base_volume
taker_buy_quote_volume
event_id_nullable
event_ts_ms_nullable
minute_offset_nullable
parse_status
parse_error
```

注意：

- 不能直接把 JSON cache 当成主数据。
- 必须去重。
- 必须检查 symbol/time 覆盖。
- 必须标明哪些事件被 legacy cache 覆盖，哪些没有。

### 2. 1m trade kline 覆盖率审计/补齐

v6 在进入 `medium` 之前必须生成 trade kline 覆盖率报告。

目标输出：

```text
normalized/trade_kline_1m_event_windows.parquet
trade_kline_coverage_report.csv
trade_kline_missing_events.csv
trade_kline_path_resolution_decision.md
```

覆盖率指标：

```text
events_total
events_with_trade_kline_window
event_coverage_pct
symbols_total
symbols_with_trade_kline
symbol_coverage_pct
minutes_expected
minutes_available
minute_coverage_pct
coverage_by_channel
coverage_by_event_type
coverage_by_symbol
```

## 路径精度决策

```text
trade_kline_event_coverage >= 95% 且 minute_coverage >= 98%
  -> 可以使用 path_resolution=1m_trade_kline 做主回放

80% <= trade_kline_event_coverage < 95%
  -> trade kline 用于 sensitivity / validation，主结论仍标注混合精度

trade_kline_event_coverage < 80%
  -> 不允许把 trade kline 作为主路径，只能使用 1m_mark fallback
```

任何 first-touch 结论都必须写明：

```text
path_resolution
trade_kline_coverage_pct
fallback_count
fallback_policy
```

## Binance 补采规则

如果 legacy cache 覆盖不足，5090 上应该补采最近 30 天事件窗口的 trade kline。

优先补：

1. v6 主样本事件相关 symbol。
2. BWE_OI_Price_monitor pump/crash。
3. v5/v6 baseline 触发过的 symbol。
4. 低覆盖但高频出现 symbol。
5. BTC/ETH regime reference。

建议补窗口：

```text
event_ts - 60m  到  event_ts + 240m
```

至少补：

```text
event_ts - 5m 到 event_ts + 60m
```

## AutoResearch 约束

- `smoke` 可以使用 `1m_mark` fallback。
- `medium` 必须先完成 trade kline 覆盖率审计。
- `max_alpha` 必须优先使用 `1m_trade_kline`，不足部分明确 fallback。
- 如果没有 trade kline 覆盖率报告，禁止声称完整退出策略已严谨验证。

