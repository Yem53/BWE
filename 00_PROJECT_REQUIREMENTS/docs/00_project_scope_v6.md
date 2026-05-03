# 00. BWE v6 项目范围

## 一句话目标

在最近 1 个月 BWE + Binance 数据上，用 AutoResearch + Codex/LLM 自动研究循环，从零发现最优的开仓和平仓组合策略。

## 不再做什么

v6 不再是：

```text
先筛入场 -> 再给前 17 条入场配退出
```

v6 必须是：

```text
完整策略 = entry gate + entry timing + side + risk + exit state machine + portfolio rule
```

所有候选从一开始就是完整交易策略。

## 搜索原则

1. 策略空间可以百亿级，但必须懒展开。
2. 不把百亿条策略全部落盘。
3. 不让 LLM 对每条策略逐条打分。
4. AutoResearch 负责真实数值实验。
5. Codex/LLM 负责研究方向、策略族设计、结果解释、下一轮 mutation。
6. 最终输出必须是完整策略排名，而不是单独入场排名。

## 基准策略

v6 必须保留这些 baseline：

- 当前 live 里的 `BWE_OI_Price_monitor pump long`
- v5 paper manifest 的 17 条 entry 候选
- 简单固定入场 T0 / 30s / 1m / 3m / 5m
- 简单 fixed TP/SL
- 不使用 Binance 指标的 message-only baseline

baseline 只用于比较，不能限制新策略搜索。

## 最终产物要求

输出目录建议：

```text
/data/bwe/v6/runs/bwe_complete_strategy_v6_max_alpha_YYYYMMDD
```

必须至少包含：

- `complete_strategy_leaderboard.csv`
- `paper_manifest_v6.json`
- `report_v6_zh.md`
- `entry_exit_matrix_summary.csv`
- `exit_state_machine_leaderboard.csv`
- `portfolio_replay_summary.csv`
- `overfit_stress_report.csv`
- `reject_log.csv`
- `llm_round_notes/`
- `round_configs/`

## 本轮加强范围

本轮加强：

- baseline 对照
- 执行成本/滑点/延迟
- 策略去重与多样性
- 统计显著性/多重搜索防过拟合
- paper/shadow 验证路径

暂缓：

- 组合层深度风控
- live 风控
- 自动上线
