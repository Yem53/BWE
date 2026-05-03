# 13. 策略去重与多样性

## 目的

百亿级搜索会产生大量相似策略。最终 paper manifest 如果全是同一策略的参数变体，会造成假多样性，也会提高过拟合风险。

## Strategy fingerprint

每条策略必须生成 fingerprint：

```text
strategy_family
channel/event/side
entry_timing_bucket
entry_feature_set
entry_condition_shape
exit_family
exit_state_machine_shape
risk_shape
portfolio_shape
```

输出：

```text
strategy_fingerprint
strategy_similarity_cluster_id
```

## 相似性维度

至少按以下维度聚类：

- 触发频道/事件
- long/short/no_trade
- entry timing
- 使用的 feature family
- threshold bucket
- exit family
- hold time distribution
- symbol exposure
- return path shape
- failure mode

## 去重规则

同一 similarity cluster 中：

- 只保留 robust score 最高的少数代表
- 如果收益接近，保留左尾更好的
- 如果左尾接近，保留复杂度更低的
- 如果复杂度接近，保留样本更分散的

## 多样性目标

最终 paper manifest 要尽量覆盖：

- 不同 channel
- 不同 event_type
- long / short / no_trade
- 不同 entry timing
- 不同 exit family
- 不同 market regime
- 不同 liquidity bucket
- 不同 symbol set

## 输出产物

```text
strategy_fingerprint.parquet
strategy_similarity_clusters.csv
strategy_dedup_leaderboard.csv
manifest_diversity_report.csv
cluster_representatives.jsonl
```

## 晋级规则

最终 `paper_manifest_v6.json`：

- 总数建议 5-30 条
- 同一 similarity cluster 最多 1-2 条
- 如果全是 OI pump long，必须明确说明其它方向为什么失败
- 如果没有 short 策略，必须有 short-side rejection evidence
- 如果没有 no_trade 策略，必须有 no_trade boundary analysis

## 禁止

- 不允许把 20 条几乎相同的参数变体都放入 paper manifest。
- 不允许只按 robust score 排，不做相似性聚类。
- 不允许忽略 symbol concentration。

