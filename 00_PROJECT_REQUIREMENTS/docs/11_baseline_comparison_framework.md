# 11. Baseline 对照框架

## 目的

v6 的策略空间会非常大，复杂策略很容易看起来有效。Baseline 对照层的目的，是强制所有完整策略证明自己真的超过简单规则，而不是只是在噪音里被挑出来。

## 必跑 baseline

### Message-only baseline

只使用 BWE 消息本身：

```text
channel + event_type + side + fixed entry delay + fixed exit
```

不使用 Binance OI、taker、funding、premium、basis、top trader 等特征。

### Timing baseline

固定入场时机：

```text
T0
T0+30s
T0+1m
T0+3m
T0+5m
```

每个频道/事件/方向都要有同口径比较。

### Simple exit baseline

简单退出：

```text
fixed horizon
fixed TP/SL
time stop
max hold
```

用于判断复杂退出状态机是否真的提升收益质量。

### Current live baseline

当前 live 里的：

```text
BWE_OI_Price_monitor pump long
```

必须用 v6 的同一套数据、费用、滑点、路径精度、walk-forward、stress 重新评估。

### v5 reference baseline

v5 的 17 条 paper entry 候选只做 reference baseline：

```text
data_snapshot/bwe_autoresearch_entry_v5_20260425/paper_manifest_entry_v5.json
```

它们不能限制 v6 搜索空间。

### Random / shuffled baseline

用于检验发现是否超过随机：

- random event entry
- random symbol within same channel/event bucket
- shuffled event timestamp
- shuffled side
- shuffled entry delay

## 输出产物

```text
baseline_catalog.jsonl
baseline_comparison.csv
baseline_vs_strategy_lift.csv
baseline_failure_cases.md
```

## 必须比较的指标

- sample size
- win rate
- mean / median net
- p25 / p10
- profit factor
- max drawdown
- longest losing streak
- fee/slippage/latency stress
- walk-forward positive rate
- remove top 1% winner
- remove top symbol
- path_resolution

## 晋级规则

完整策略要进入 `promote_to_paper`，必须至少超过：

```text
message-only baseline
same timing baseline
simple TP/SL baseline
current live baseline or explain why not comparable
```

如果策略只比很弱 baseline 好，但不如当前 live 策略，只能进入：

```text
watchlist
need_more_data
reject
```

## 禁止

- 不允许只和随机 baseline 比。
- 不允许用不同费用模型和 baseline 比。
- 不允许用更高路径精度的候选去和低路径精度 baseline 比，却不声明差异。
- 不允许把 v5 17 条当作 v6 的搜索边界。

