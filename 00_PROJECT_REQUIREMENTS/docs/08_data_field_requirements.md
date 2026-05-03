# 08. v6 字段级数据要求

## 事件字段

必须：

- `event_id`
- `channel`
- `event_type`
- `symbol`
- `api_symbol`
- `ts_ms`
- `message_ts`
- `raw_message`
- `parsed_direction`
- `core_complete`

强烈建议：

- `move_pct`
- `oi_ratio_pct`
- `marketcap`
- `quote_volume_24h`
- `listing_age_days`
- `liquidity_bucket`
- `symbol_status`

## Binance T0 特征

必须尽量有：

- `open_interest_hist__sumOpenInterest`
- `open_interest_hist__sumOpenInterestValue`
- `open_interest_hist__age_ms`
- `funding_rate`
- `funding_age_ms`
- `global_long_short_account_ratio__longShortRatio`
- `global_long_short_account_ratio__age_ms`
- `top_trader_long_short_account_ratio__longShortRatio`
- `top_trader_long_short_account_ratio__age_ms`
- `top_trader_long_short_position_ratio__longShortRatio`
- `top_trader_long_short_position_ratio__age_ms`
- `taker_buy_sell_volume__buySellRatio`
- `taker_buy_sell_volume__buyVol`
- `taker_buy_sell_volume__sellVol`
- `taker_buy_sell_volume__age_ms`
- `basis_perpetual__basisRate`
- `basis_perpetual__basis`
- `basis_perpetual__age_ms`
- `mark_1m_close`
- `mark_1m_high`
- `mark_1m_low`
- `mark_1m_age_ms`
- `premium_1m_close`
- `premium_1m_high`
- `premium_1m_low`
- `premium_1m_age_ms`
- `mark_minus_index_proxy_pct`

## BTC/ETH regime

建议有：

- `btc_pre5m`
- `btc_pre15m`
- `btc_pre30m`
- `btc_pre60m`
- `eth_pre5m`
- `eth_pre15m`
- `eth_pre30m`
- `eth_pre60m`
- `btc_volatility_pre30m`
- `eth_volatility_pre30m`

如果没有，可先从 mark/kline 自行生成。

## 路径字段

用于退出模拟的 path 表必须有：

- `event_id`
- `api_symbol`
- `event_ts_ms`
- `path_ts_ms`
- `minute_offset`
- `mark_open`
- `mark_high`
- `mark_low`
- `mark_close`
- `premium_open`
- `premium_high`
- `premium_low`
- `premium_close`

如果 trade kline 可补齐，还应有：

- `trade_open`
- `trade_high`
- `trade_low`
- `trade_close`
- `trade_volume`
- `trade_quote_volume`
- `trade_count`
- `trade_taker_buy_quote_volume`

当前已知 `local_kline_1m_event_window.parquet` 行数为 0，所以 v6 初期应使用 `1m_mark` fallback，并标注路径精度。

在 5090 上必须尝试生成：

```text
normalized/trade_kline_1m_event_windows.parquet
normalized/legacy_trade_kline_1m_windows.parquet
trade_kline_coverage_report.csv
```

如果这些文件不存在，完整退出策略报告必须降级为 `path_resolution=1m_mark` 研究。

## Future label 字段

这些字段只能用于评分：

- `ret_*`
- `net_*`
- `mfe_*`
- `mae_*`
- `future_*`
- `forward_*`
- `label_*`

严禁用于：

- entry condition
- entry timing condition
- exit trigger
- portfolio rule

## 输出字段

`complete_strategy_leaderboard.csv` 至少包含：

- `strategy_id`
- `strategy_family`
- `channel`
- `event_type`
- `side`
- `entry_timing`
- `entry_conditions_json`
- `exit_state_machine_json`
- `risk_rule_json`
- `portfolio_rule_json`
- `sample_size`
- `win_rate_pct`
- `mean_net_pct`
- `median_net_pct`
- `p25_net_pct`
- `p10_net_pct`
- `profit_factor`
- `max_drawdown_pct`
- `longest_losing_streak`
- `mfe_capture_ratio`
- `giveback_ratio`
- `avg_hold_minutes`
- `stress_fee_slippage_median_net_pct`
- `stress_latency_median_net_pct`
- `walk_forward_positive_rate_pct`
- `remove_top_1pct_mean_net_pct`
- `top1_removed_mean_net_pct`
- `top5_removed_mean_net_pct`
- `symbol_count`
- `top_symbol_share_pct`
- `portfolio_drawdown_pct`
- `decision`
- `reject_reason`
- `path_resolution`
- `paper_only`
- `live_allowed`
