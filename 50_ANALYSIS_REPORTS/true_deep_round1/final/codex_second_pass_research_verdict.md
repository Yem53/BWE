# Codex 二次深度研究裁决

## 1. 这轮到底完成了什么
这不是重新跑 5000 亿级搜索，也不是把之前的短 memo 换个名字。这个目录做的是：把已经完成的 GPU fused strong 结果、AutoResearch 扩展层、entry/exit catalog、discovery queue、baseline、execution stress 和 cluster 稳定性放到同一个研究框架里，由八个角色分别审查，然后互相质询，最后给出可执行的下一轮 ablation 决策。

关键事实：

- 搜索空间记录：`500000000000`。
- coarse eval：`100000000`。
- medium eval：`5000000`。
- deep eval：`200000`。
- stress eval：`20000`。
- path resolution：`1m_trade_kline`。
- paper only：`True`。
- live allowed：`False`。

## 2. 样本数政策结论
你要求“样本数量少不作为筛查标准，只要大于 15 就可以”。这轮数据支持这个政策，因为最终 200k leaderboard 中没有 `sample_size <= 15` 的候选。也就是说，这一轮不是在一堆 3、5、8 个样本的小点上做幻想，而是所有候选至少进入了 early-alpha 层。

但这不代表所有样本层级的证据权重一样。最终解释应这样处理：

- 16-29：可以作为 early-alpha 研究信号，不能直接 paper。
- 30-49：可以作为 exploratory watchlist。
- 50-99：可以作为 validated watchlist。
- 100+：可以作为 higher-confidence watchlist。

## 3. 最强 raw alpha 与最强高置信 alpha 的分歧
最强 raw 候选是：

`v6_f468dea25e7faf1bcd`  
`freshness_strict_confirmation / long / 30s / state_machine`  
sample `27`，median `23.2943`，p10 `14.8108`，stressed median `23.0260`。

这很强，但它属于 early-alpha，并且 top raw 区域存在明显 cluster 重复。因此它的正确身份是：强研究线索，不是最终候选。

最强 100+ 样本候选是：

`v6_4aea03e3fa32fdedbb`  
`freshness_strict_confirmation / long / 30s / breakeven_ratchet`  
sample `102`，median `21.8662`，p10 `10.5059`，stressed median `21.5979`。

这是非常重要的：高置信层没有崩掉。raw 第一名需要谨慎，但 100+ 样本层仍然保留了强正收益，这让整轮研究更可信。

## 4. Entry 侧最值得吸收的信号
从 entry catalog 看，下一轮最值得优先验证的不是单一策略，而是几个 entry family：

| strategy_family               | channel              | event_type   | side   | entry_timing   |   tested_strategies |   sample_gt15_count |   sample_ge50_count |   sample_ge100_count |   median_sample_size |   max_sample_size |   best_median_net_pct |   median_of_median_net_pct |   median_p10_net_pct |   best_robust_score |   median_robust_score |   median_stability_score |   best_stability_score |   positive_stress_rate_pct |   positive_p10_rate_pct |   future_safety_pass_rate_pct |   median_baseline_lift_pct |   unique_clusters |   unique_exit_families |   unique_entry_families |   median_top_symbol_share_pct | best_strategy_id      |   best_sample_size | best_sample_tier            |   entry_catalog_score |
|:------------------------------|:---------------------|:-------------|:-------|:---------------|--------------------:|--------------------:|--------------------:|---------------------:|---------------------:|------------------:|----------------------:|---------------------------:|---------------------:|--------------------:|----------------------:|-------------------------:|-----------------------:|---------------------------:|------------------------:|------------------------------:|---------------------------:|------------------:|-----------------------:|------------------------:|------------------------------:|:----------------------|-------------------:|:----------------------------|----------------------:|
| premium_basis_overheat        | BWE_OI_Price_monitor | pump         | long   | 30s            |                2641 |                2641 |                2428 |                 2428 |                  341 |               954 |               20.1791 |                   11.463   |             -2.22416 |           0.103282  |             0.0474451 |                 0.69605  |               0.892122 |                    95.797  |                32.2605  |                           100 |                   11.9147  |                27 |                     10 |                       1 |                       6.07966 | v6_28d858af6439dc2b01 |                321 | higher_confidence_watchlist |              0.885534 |
| oi_funding_continuation       | ANY                  | ANY          | long   | 1m             |                5476 |                5476 |                4136 |                 3954 |                  245 |               472 |               18.8787 |                   11.4456  |             -2.22416 |           0.0936207 |             0.0380684 |                 0.63808  |               0.875338 |                    94.9963 |                 6.61066 |                           100 |                   11.8973  |                16 |                      6 |                       1 |                       4.08163 | v6_871de8c3a69cf23372 |                222 | higher_confidence_watchlist |              0.853883 |
| contrarian_crash_fade         | BWE_OI_Price_monitor | pump         | long   | 30s            |               18694 |               18694 |               17474 |                15811 |                  341 |               954 |               20.1791 |                    8.09538 |             -4.22416 |           0.103282  |             0.0216621 |                 0.553214 |               0.892122 |                    87.3114 |                 8.09886 |                           100 |                    8.54711 |                60 |                     11 |                       1 |                       7.5     | v6_b1c1ca8225d6820489 |                321 | higher_confidence_watchlist |              0.852524 |
| freshness_strict_confirmation | ANY                  | ANY          | long   | 30s            |                5751 |                5751 |                3630 |                 2905 |                  111 |              1491 |               23.2943 |                   10.398   |             -2.22416 |           0.129127  |             0.0317929 |                 0.570519 |               0.873063 |                    94.9052 |                 5.35559 |                           100 |                   10.8497  |                39 |                     10 |                       1 |                       7.97434 | v6_691c612b10d572162f |                 79 | validated_watchlist         |              0.837379 |
| oi_funding_continuation       | ANY                  | pump         | long   | 30s            |                 298 |                 298 |                 210 |                  166 |                  102 |               102 |               21.8662 |                   15.7337  |             -2.22416 |           0.118654  |             0.0497955 |                 0.756715 |               0.885509 |                   100      |                27.5168  |                           100 |                   16.1854  |                 3 |                      2 |                       1 |                       3.92157 | v6_62a7735fcc14133733 |                102 | higher_confidence_watchlist |              0.825631 |
| oi_funding_continuation       | ANY                  | pump         | long   | 1m             |               10776 |               10776 |                7496 |                 6537 |                  185 |              3795 |               20.0794 |                    5.88553 |             -1.82416 |           0.111435  |             0.020322  |                 0.48803  |               0.889894 |                    88.9105 |                20.2765  |                           100 |                    6.33726 |                24 |                     11 |                       1 |                      10       | v6_f70c9ed57173dd6a00 |                201 | higher_confidence_watchlist |              0.816893 |
| liquidity_filtered_momentum   | BWE_OI_Price_monitor | pump         | long   | T0             |                8607 |                8607 |                5529 |                 4511 |                  145 |               954 |               17.4629 |                    5.24523 |             -3.22416 |           0.0819699 |             0.0183718 |                 0.56391  |               0.792909 |                    89.8571 |                 6.26234 |                           100 |                    5.69696 |                33 |                     10 |                       1 |                       6.07966 | v6_1119ad97a5655ef5ec |                381 | higher_confidence_watchlist |              0.812913 |
| oi_funding_continuation       | ANY                  | pump         | long   | 3m             |                4184 |                4184 |                3648 |                 3648 |                  764 |              3795 |               16.3512 |                    8.89097 |             -5.22416 |           0.0782296 |             0.0287738 |                 0.596151 |               0.802939 |                    86.5918 |                 4.78011 |                           100 |                    9.3427  |                44 |                      9 |                       1 |                       4.05759 | v6_7e52621494b6ff6de9 |                 30 | exploratory_watchlist       |              0.812039 |

我的二次判断：

1. `premium_basis_overheat / 30s / long` 应该排第一。它不是 raw top，但是 discovery queue 把它推到第一，因为它有较好的完整策略组合、较强 stress 表现，并且可以与多个 exit family 做隔离测试。
2. `freshness_strict_confirmation / 30s / long` 是 raw alpha 来源，但必须先解决 cluster 重复和 sample tier 问题。
3. `oi_funding_continuation / 1m or 30s / long` 更像广谱 continuation alpha，样本更厚，适合当第二或第三个 ablation 方向。
4. `contrarian_crash_fade / 30s / long` 不该丢，但 p10 和 adverse-regime 风险要更严。

## 5. Exit 侧最值得吸收的模块
从 exit catalog 看：

| exit_family            | side   |   horizon_min |   tested_strategies |   sample_gt15_count |   sample_ge50_count |   sample_ge100_count |   median_sample_size |   max_sample_size |   best_median_net_pct |   median_of_median_net_pct |   median_p10_net_pct |   best_robust_score |   median_robust_score |   median_stability_score |   best_stability_score |   positive_stress_rate_pct |   positive_p10_rate_pct |   future_safety_pass_rate_pct |   median_baseline_lift_pct |   unique_clusters |   unique_exit_families |   unique_entry_families |   median_top_symbol_share_pct | best_strategy_id      |   best_sample_size | best_sample_tier            |   exit_catalog_score |
|:-----------------------|:-------|--------------:|--------------------:|--------------------:|--------------------:|---------------------:|---------------------:|------------------:|----------------------:|---------------------------:|---------------------:|--------------------:|----------------------:|-------------------------:|-----------------------:|---------------------------:|------------------------:|------------------------------:|---------------------------:|------------------:|-----------------------:|------------------------:|------------------------------:|:----------------------|-------------------:|:----------------------------|---------------------:|
| breakeven_ratchet      | long   |           240 |               19942 |               19942 |               19587 |                17723 |                  341 |              1430 |              21.8662  |                   14.3287  |             -3.22416 |           0.119914  |             0.0417179 |                 0.70251  |               0.892122 |                        100 |               10.8414   |                           100 |                   14.7804  |                67 |                      1 |                       9 |                       4.05759 | v6_28d858af6439dc2b01 |                321 | higher_confidence_watchlist |             0.891176 |
| runner_trail           | long   |           240 |               20674 |               20674 |               16788 |                16042 |                  340 |              3795 |              19.6109  |                    9.95274 |             -3.22416 |           0.103218  |             0.027894  |                 0.611985 |               0.874656 |                        100 |                7.93751  |                           100 |                   10.4045  |                94 |                      1 |                       9 |                       6.07966 | v6_a007baac46dfabbc59 |                196 | higher_confidence_watchlist |             0.875588 |
| state_machine          | long   |           240 |               20312 |               20312 |               17355 |                14130 |                  341 |              3795 |              23.2943  |                   10.2326  |             -3.22416 |           0.129127  |             0.0264864 |                 0.599198 |               0.880292 |                        100 |                7.36018  |                           100 |                   10.6843  |               109 |                      1 |                       7 |                       5.89569 | v6_bb5a10b92455024a2a |                321 | higher_confidence_watchlist |             0.873235 |
| time_decay             | long   |           240 |               16329 |               16329 |               13448 |                11740 |                  341 |              1401 |              19.2482  |                   11.1786  |             -4.22416 |           0.0953066 |             0.0305313 |                 0.607848 |               0.877655 |                        100 |                0.698144 |                           100 |                   11.6303  |                96 |                      1 |                       6 |                       5.89569 | v6_2e078d5e7379ffb44f |                141 | higher_confidence_watchlist |             0.86     |
| indicator_invalidation | long   |           240 |                4050 |                4050 |                3381 |                 2668 |                  220 |               954 |              19.7098  |                   10.4965  |             -5.22416 |           0.0950865 |             0.0293652 |                 0.5499   |               0.885809 |                        100 |               17.3086   |                           100 |                   10.9482  |                26 |                      1 |                       7 |                      12.5     | v6_ef65d121e8a0c33a26 |                321 | higher_confidence_watchlist |             0.847647 |
| failed_continuation    | long   |           240 |               11422 |               11422 |                9742 |                 9659 |                  462 |              1401 |              20.8055  |                    9.58221 |             -5.22416 |           0.11274   |             0.0234387 |                 0.585601 |               0.865891 |                        100 |                7.36298  |                           100 |                   10.0339  |                55 |                      1 |                       7 |                       6.07966 | v6_8f21b07ab27a9ca722 |                 68 | validated_watchlist         |             0.845882 |
| fixed_tp_sl            | long   |           240 |                8804 |                8804 |                7926 |                 7637 |                  347 |              3795 |               7.77584 |                    4.77584 |             -2.22416 |           0.042243  |             0.0114529 |                 0.501235 |               0.688776 |                        100 |               21.0927   |                           100 |                    5.22757 |                69 |                      1 |                       7 |                       4.05759 | v6_ca60f9ead3c1807ba3 |                321 | higher_confidence_watchlist |             0.827353 |
| partial_ladder         | long   |           240 |               14175 |               14175 |               11028 |                10981 |                  341 |              3795 |              13.0094  |                    5.46001 |             -3.22416 |           0.0632122 |             0.0133973 |                 0.489157 |               0.795069 |                        100 |                2.44797  |                           100 |                    5.91174 |                86 |                      1 |                       8 |                       6.07966 | v6_58bc6eedb077fcdf78 |                321 | higher_confidence_watchlist |             0.823529 |

我的二次判断：

- `breakeven_ratchet` 是最像“可复用 exit module”的东西。它不是只在一个小样本 raw top 上赢，而是在高样本、stress 和组合 funnel 里都很强。
- `state_machine` 是 raw top 的主要来源，但它的风险是 path-shape overfit，所以要通过 cluster representative 和 exit swap 来验证。
- `runner_trail` 继续保留，它可能适合趋势延续型 entry。
- `fixed_tp_sl` 不像赢家，但必须保留为 control，否则无法证明复杂 exit 的增益。

## 6. 完整策略组合的优先级
完整策略 funnel 里，真正应该进入下一轮的不是“榜首一条”，而是一组带有因果测试价值的组合：

| strategy_family               | side   | entry_timing   | exit_family       |   tested_strategies |   sample_gt15_count |   sample_ge50_count |   sample_ge100_count |   median_sample_size |   max_sample_size |   best_median_net_pct |   median_of_median_net_pct |   median_p10_net_pct |   best_robust_score |   median_robust_score |   median_stability_score |   best_stability_score |   positive_stress_rate_pct |   positive_p10_rate_pct |   future_safety_pass_rate_pct |   median_baseline_lift_pct |   unique_clusters |   unique_exit_families |   unique_entry_families |   median_top_symbol_share_pct | best_strategy_id      |   best_sample_size | best_sample_tier            |   combined_funnel_score |
|:------------------------------|:-------|:---------------|:------------------|--------------------:|--------------------:|--------------------:|---------------------:|---------------------:|------------------:|----------------------:|---------------------------:|---------------------:|--------------------:|----------------------:|-------------------------:|-----------------------:|---------------------------:|------------------------:|------------------------------:|---------------------------:|------------------:|-----------------------:|------------------------:|------------------------------:|:----------------------|-------------------:|:----------------------------|------------------------:|
| oi_funding_continuation       | long   | 1m             | breakeven_ratchet |                3610 |                3610 |                3610 |                 3610 |                  292 |               400 |               20.0794 |                   13.4258  |             -2.22416 |           0.111435  |             0.0417179 |                 0.737729 |               0.889894 |                        100 |                22.133   |                           100 |                   13.8776  |                 4 |                      1 |                       1 |                       3.55731 | v6_f70c9ed57173dd6a00 |                201 | higher_confidence_watchlist |                0.853812 |
| freshness_strict_confirmation | long   | 30s            | breakeven_ratchet |                3781 |                3781 |                3781 |                 2848 |                  102 |               111 |               21.8662 |                   15.7592  |             -2.22416 |           0.119914  |             0.0497955 |                 0.733183 |               0.885509 |                        100 |                24.676   |                           100 |                   16.2109  |                 4 |                      1 |                       1 |                       3.92157 | v6_4aea03e3fa32fdedbb |                102 | higher_confidence_watchlist |                0.850359 |
| oi_funding_continuation       | long   | 1m             | runner_trail      |                4576 |                4576 |                3795 |                 3705 |                  163 |               255 |               17.982  |                   12.4288  |             -2.22416 |           0.0955797 |             0.0380684 |                 0.643333 |               0.874656 |                        100 |                19.8645  |                           100 |                   12.8806  |                12 |                      1 |                       1 |                       5.65957 | v6_a007baac46dfabbc59 |                196 | higher_confidence_watchlist |                0.842063 |
| contrarian_crash_fade         | long   | 30s            | breakeven_ratchet |                2997 |                2997 |                2997 |                 2997 |                  341 |              1401 |               20.1791 |                   10.5656  |             -2.22416 |           0.103282  |             0.0309196 |                 0.680622 |               0.892122 |                        100 |                 6.63997 |                           100 |                   11.0174  |                 8 |                      1 |                       1 |                       6.07966 | v6_b1c1ca8225d6820489 |                321 | higher_confidence_watchlist |                0.840359 |
| state_machine_runner          | long   | T0             | state_machine     |                3582 |                3582 |                3014 |                 2615 |                  321 |              1401 |               15.3114 |                    9.54019 |             -2.22416 |           0.0815584 |             0.0235308 |                 0.603603 |               0.867323 |                        100 |                10.9994  |                           100 |                    9.99192 |                24 |                      1 |                       1 |                       6.07966 | v6_193850a81510091fa9 |                321 | higher_confidence_watchlist |                0.822646 |
| contrarian_crash_fade         | long   | 30s            | state_machine     |                3232 |                3232 |                3010 |                 2672 |                  341 |              1401 |               16.6358 |                   10.4551  |             -5.22416 |           0.0883564 |             0.0256745 |                 0.634816 |               0.880292 |                        100 |                 6.06436 |                           100 |                   10.9069  |                10 |                      1 |                       1 |                       6.07966 | v6_bb5a10b92455024a2a |                321 | higher_confidence_watchlist |                0.820045 |
| freshness_strict_confirmation | long   | 30s            | time_decay        |                 668 |                 668 |                 668 |                  668 |                  227 |               273 |               18.4457 |                   17.7881  |             -1.82416 |           0.0953066 |             0.0790649 |                 0.759598 |               0.877655 |                        100 |                17.0659  |                           100 |                   18.2398  |                 6 |                      1 |                       1 |                       3.52423 | v6_2e078d5e7379ffb44f |                141 | higher_confidence_watchlist |                0.81296  |
| premium_basis_overheat        | long   | 30s            | breakeven_ratchet |                 553 |                 553 |                 553 |                  553 |                  420 |              1401 |               20.1791 |                   16.3591  |             -5.22416 |           0.103282  |             0.0635075 |                 0.722941 |               0.892122 |                        100 |                19.8915  |                           100 |                   16.8108  |                 5 |                      1 |                       1 |                       6.07966 | v6_28d858af6439dc2b01 |                321 | higher_confidence_watchlist |                0.809821 |

优先级：

1. `premium_basis_overheat / 30s / indicator_invalidation / long`：先做 complete strategy neighborhood。
2. `premium_basis_overheat / 30s / long`：固定 entry，swap exits。
3. `freshness_strict_confirmation / 30s / breakeven_ratchet / long`：高置信版本，验证 raw alpha 是否能转成更厚样本。
4. `oi_funding_continuation / 1m / breakeven_ratchet / long`：验证广谱 continuation 是否比 raw freshness 更稳定。

## 7. 红队质疑
我不会把这轮结果说成“已经可以 paper”。主要反对意见有四个：

1. **cluster duplication**：raw top 多条几乎同构，必须用 cluster representative。
2. **multiple testing**：5000 亿参数空间天然有选择偏差，所以必须保留 permutation、bootstrap、ESS、multiple testing penalty。
3. **1m path resolution**：这是 1m trade kline，不是 tick replay。exit state machine 可能比真实 paper replay 更干净。
4. **long/short imbalance**：long 占绝大多数，short 不能简单判死刑，需要单独 balanced probe。

## 8. 执行成本判断
stress latency 不是当前最大风险，至少在 top stress 集合里没有明显把收益打没：

|   latency_seconds |   rows |   strategies |   median_stressed |   p10_stressed |   min_stressed |   median_missed_fill |
|------------------:|-------:|-------------:|------------------:|---------------:|---------------:|---------------------:|
|                 0 |  20000 |        20000 |           16.3057 |        13.372  |        10.3158 |                  0   |
|                 1 |  20000 |        20000 |           16.2987 |        13.3651 |        10.3089 |                  2.5 |
|                 3 |  20000 |        20000 |           16.2918 |        13.3581 |        10.302  |                  7.5 |
|                 5 |  20000 |        20000 |           16.2878 |        13.3541 |        10.2979 |                 12.5 |
|                10 |  20000 |        20000 |           16.2817 |        13.348  |        10.2919 |                 25   |
|                30 |  20000 |        20000 |           16.2713 |        13.3377 |        10.2815 |                 75   |

但这不等于执行没风险。下一轮必须继续保留 fee、slippage、latency、missed fill，而且 paper validator 需要检查 1m 内部路径顺序。

## 9. 最终裁决
最终结论：

**可以进入 focused ablation，不可以直接进入 paper-shadow。**

下一步只跑一个假设，不要又展开成全局 max_alpha：

`premium_basis_overheat / 30s / long`  
固定 entry，比较：

- `indicator_invalidation`
- `breakeven_ratchet`
- `state_machine`
- `runner_trail`
- `fixed_tp_sl`

如果它在 fixed TP/SL control 或至少一个非优化 exit 下仍然保留正 baseline lift，并且 stressed median/p10 还可以，才进入第二个假设。

## 10. 对你的项目有什么价值
这轮真正吸收了 AutoResearch 对你项目有用的部分：

- 从 leaderboard 变成 hypothesis ledger。
- 从“哪个策略最高”变成“哪个 entry/exit module 可复用”。
- 从 raw alpha 变成 sample-tier alpha。
- 从单角色总结变成多角色质询。
- 从宽搜索变成下一轮 one-hypothesis ablation。

这就是我认为现在最稳的研究推进方式。
