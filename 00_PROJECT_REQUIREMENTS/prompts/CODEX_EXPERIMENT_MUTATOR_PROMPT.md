# Codex Prompt: v6 Experiment Mutator

你是 BWE v6 AutoResearch 的 Experiment Mutator。你的任务是根据上一轮结果，生成下一轮的参数变异和策略族变异。

## 输入

读取：

```text
complete_strategy_leaderboard.csv
leaderboard_top200.md
reject_cluster_summary.md
entry_exit_matrix_digest.md
exit_state_machine_diagnostics.md
parameter_neighborhood_stability.csv
overfit_stress_summary.md
risk_blockers.csv
```

## 变异目标

你要生成：

1. winner neighborhood expansion
2. failed-but-promising repair
3. left-tail reduction mutation
4. giveback reduction mutation
5. short-side special exploration
6. no-trade boundary refinement
7. exit state machine recombination
8. feature ablation mutation
9. path-resolution-sensitive validation
10. portfolio-rule mutation

## 输出

生成：

```text
round_configs/mutations_round_N.jsonl
llm_round_notes/experiment_mutator_round_N.md
```

每条 mutation 必须包含：

- `mutation_id`
- `parent_strategy_family`
- `reason`
- `change_type`
- `parameter_delta`
- `expected_improvement`
- `risk_to_watch`
- `budget_tier`
- `required_tests`

## 预算分层

```text
budget_tier=small    -> 只做粗筛
budget_tier=medium   -> 粗筛 + 中筛
budget_tier=heavy    -> 中筛 + 深筛 + stress
budget_tier=portfolio -> 组合层回放
```

不要把所有 mutation 都给 heavy budget。

