# 01. v6 数据合同

## 主输入

v6 使用最近 1 个月数据，但要尽可能完整：

```text
BWE events
Binance event-time features
Binance 1m forward path
Binance mark / premium / basis / OI / taker / long-short / top trader / funding
BTC/ETH regime
symbol metadata
```

## 当前 Mac mini 30 天数据快照

已观察到的目录：

```text
/Users/ye/.hermes/research/bwe_three_channel_fullrun3/binance_event_features_20260425_30d
```

当前行数快照：

| 文件 | 行数 | 说明 |
|---|---:|---|
| `bwe_events_recent_base.parquet` | 7353 | BWE 原始事件基础表 |
| `bwe_events_recent_binance_features.parquet` | 7317 | 拼接 Binance 特征后的事件表 |
| `bwe_forward_recent_binance_features_merged.parquet` | 73170 | 事件后 forward path/label 表 |
| `raw/mark_price_1m.parquet` | 4068517 | mark price 1m 路径 |
| `raw/premium_index_1m.parquet` | 4068517 | premium index 1m 路径 |
| `raw/open_interest_hist.parquet` | 746037 | OI hist |
| `raw/global_long_short_account_ratio.parquet` | 746041 | 全市场 long/short account ratio |
| `raw/top_trader_long_short_account_ratio.parquet` | 745035 | top trader account ratio |
| `raw/top_trader_long_short_position_ratio.parquet` | 744535 | top trader position ratio |
| `raw/taker_buy_sell_volume.parquet` | 744417 | taker buy/sell volume |
| `raw/basis_perpetual.parquet` | 796406 | basis |
| `raw/funding_rate.parquet` | 19050 | funding |
| `raw/exchange_info.parquet` | 716 | symbol metadata |
| `raw/local_kline_1m_event_window.parquet` | 0 | 当前缺口：trade kline 未接上 |

时间范围：

```text
2026-03-21T14:59:00Z -> 2026-04-20T16:30:00Z
```

## Trade kline 补强要求

当前主数据包没有接上本地 trade kline。v6 必须在 5090 上先做：

```text
legacy_market_cache -> normalized trade kline parquet
trade kline coverage audit
missing event trade kline补采计划
```

没有完成覆盖率审计前：

- `smoke` 可以使用 `1m_mark` fallback。
- `medium/max_alpha` 不能把 first-touch 结果称为真实成交路径。
- `max_alpha` 必须优先使用 `1m_trade_kline`，不足部分明确 fallback。

## 必需字段分区

### 1. entry_time_features

消息发出时刻 T0 已经知道的字段。

允许用于 T0 入场：

- BWE channel
- BWE event_type
- symbol
- message timestamp
- parsed move_pct / oi_ratio_pct / marketcap / quote volume
- latest OI bucket before T0
- latest funding before T0
- latest long/short ratios before T0
- latest top trader ratios before T0
- latest taker flow bucket before T0
- latest basis before T0
- latest mark/premium/index before T0
- BTC/ETH pre-event regime
- listing_age_days
- liquidity_bucket

### 2. delayed_entry_features

只能用于 T0+30s / 1m / 3m / 5m 等等待入场规则。

允许：

- 已经发生的 1m mark path
- 已经发生的 premium path
- 已经发生的 kline confirmation
- 已经发生的 OI/taker/stat bucket update
- BTC/ETH 在等待期间的变化

禁止把 T0+5m 确认用于 T0 立即入场。

### 3. in_position_features

只能用于持仓中退出或减仓：

- 逐分钟 mark price
- 逐分钟 premium
- OI 是否继续支持方向
- taker flow 是否反转
- premium / basis 是否过热
- top trader ratio 是否反转
- BTC/ETH 是否反向
- 持仓时间
- 当前未实现收益
- MFE/MAE 的在线可见状态

### 4. future_labels

只能用于评估，不允许用于交易规则：

- `ret_*`
- `net_*`
- `mfe`
- `mae`
- future max/min
- final outcome
- forward horizon label
- any field computed after decision time

## 事件主键

建议 v6 统一使用：

```text
event_id = hash(channel, message_ts_ms, raw_symbol, event_type, raw_message)
```

所有 path、features、labels、portfolio replay 都必须能回连到 `event_id`。

## 完整策略主键

```text
strategy_id = hash(strategy_family, entry_rule, exit_rule, risk_rule, portfolio_rule, version)
```

候选空间百亿级时，不要将所有策略落盘为 JSON；只落盘：

- strategy_family
- parameter_seed
- grid_id
- strategy_hash
- sampled parameters
- decision metrics
