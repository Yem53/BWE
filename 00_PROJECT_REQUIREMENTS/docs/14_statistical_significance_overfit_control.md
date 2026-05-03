# 14. 统计显著性与大规模搜索防过拟合

## 目的

30 天数据样本有限，而 v6 搜索空间极大。搜索越大，越容易碰巧找到“历史上看起来很好”的策略。

本层用于控制 false discovery。

## 必做检验

### Bootstrap confidence interval

对每个候选计算：

- median net CI
- mean net CI
- win rate CI
- p25 / p10 CI
- profit factor CI

### Permutation test

至少做：

- shuffled side
- shuffled timestamp within same day
- shuffled symbol within same channel/event
- shuffled entry delay

候选必须显著优于 shuffled baseline。

### Multiple testing penalty

按策略族和参数空间规模加入惩罚：

```text
effective_trials
family_trial_count
parameter_grid_size
complexity_penalty
false_discovery_penalty
```

### Effective sample size

不能只看 raw sample size。必须计算：

- independent event count
- unique symbol count
- unique day count
- unique regime count
- top symbol share
- top day share

### Parameter neighborhood stability

优秀策略的邻近参数也应该大体有效。如果只有单点参数有效，判为高过拟合风险。

## 输出产物

```text
bootstrap_confidence_intervals.csv
permutation_test_results.csv
multiple_testing_penalty.csv
effective_sample_size_report.csv
parameter_neighborhood_stability.csv
false_discovery_audit.md
```

## 晋级规则

进入 `promote_to_paper` 必须满足：

- effective sample size 达标
- bootstrap CI 不完全依赖少数极端样本
- permutation test 显著优于随机
- parameter neighborhood 稳定
- false discovery penalty 后仍有优势

## 降级规则

降级为 `need_more_data`：

- 逻辑合理但样本太少
- unique symbol 太少
- unique day 太少
- 只在单一 regime 有效

降级为 `reject`：

- permutation 不显著
- bootstrap CI 极宽
- 去 top winners 后失效
- 参数邻域只有孤立尖峰

## 禁止

- 不允许用百亿搜索后只看 top mean。
- 不允许忽略多重比较。
- 不允许把样本数 20 左右的策略直接当强结论。
- 不允许把单 symbol 或单日事件撑起来的策略升 paper。

