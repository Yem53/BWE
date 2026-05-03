# 12. 执行成本、滑点与延迟模型

## 目的

BWE 策略是消息触发型策略，真实 alpha 可能很短。费用、滑点和延迟会直接决定策略是否还能赚钱。

v6 必须把所有策略在成本后评估，不能只看裸收益。

## 成本模型分层

### Base cost

最低成本假设：

```text
taker_fee_bps
basic_slippage_bps
```

### Stress cost

压力假设：

```text
taker_fee_bps + higher_slippage_bps + latency_penalty
```

### Liquidity-aware cost

按流动性桶调节：

```text
high liquidity -> lower slippage
mid liquidity  -> normal slippage
low liquidity  -> high slippage
new listing    -> extra slippage
```

### Entry type sensitivity

至少比较：

- market entry
- limit entry with possible missed fill
- chase entry with max price offset

## 延迟模型

必须模拟：

```text
message_parse_latency_ms
decision_latency_ms
order_submit_latency_ms
exchange_ack_latency_ms
fill_latency_ms
```

第一版可用离散档：

```text
0s
1s
3s
5s
10s
30s
```

延迟通过 entry price 偏移或下一根路径价格模拟。

## 输出产物

```text
execution_cost_model.json
latency_stress_grid.json
fee_slippage_latency_stress.csv
execution_model_sensitivity.md
missed_fill_simulation.csv
```

## 必须记录

每条策略结果必须记录：

- `fee_model_id`
- `slippage_model_id`
- `latency_model_id`
- `entry_order_type`
- `path_resolution`
- `gross_return_pct`
- `net_return_pct`
- `stress_net_return_pct`
- `missed_fill_rate_pct` if limit-like entry

## 晋级规则

进入 `promote_to_paper` 的策略必须：

- base cost 后仍有效
- stress cost 后 median 不为负
- latency stress 后不完全失效
- 低流动性样本不主导收益

## 禁止

- 不允许只用裸收益排序。
- 不允许忽略 BWE 消息到下单之间的延迟。
- 不允许将 limit fill 假设成 100% 成交。
- 不允许对低流动性 symbol 使用和 BTC/ETH 一样的滑点假设。

