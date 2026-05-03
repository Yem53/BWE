# 05. Codex/LLM + AutoResearch 循环

## 角色分工

AutoResearch 负责：

- 生成候选
- 数值回测
- 路径模拟
- walk-forward
- stress test
- portfolio replay
- 产物落盘

Codex/LLM 负责：

- 维护研究账本
- 设计完整策略族
- 根据失败簇生成变异
- 分析失败簇
- 发现被误杀的策略族
- 解释哪些退出机制有效
- 提出下一轮 mutation
- 审计未来函数/过拟合风险
- 生成最终中文报告

## 不允许的 LLM 用法

不要让 LLM：

- 对每条策略逐条打分
- 直接替代回测
- 看未来标签后生成规则
- 读取 live secrets
- 修改 live trading 程序

## 每轮推荐 Codex 调用量

质量优先，但控制在 Pro 套餐内：

```text
每轮 8-15 次 Codex 调用
完整项目 5-10 轮
总调用 40-150 次，预留到 200 次以内
```

## 每轮流程

```text
Round N
1. Meta Research Director 读取研究账本，决定本轮主攻方向
2. Strategy Architect 读取上一轮摘要，设计新策略族
3. Experiment Mutator 根据赢家邻域和失败簇生成变异
4. AutoResearch 展开候选并粗筛
5. Results Analyst 分析 leaderboard/reject log
6. AutoResearch 中筛与深筛
7. Risk Critic 审计未来函数、过拟合、左尾、symbol 依赖
8. AutoResearch portfolio replay
9. Lead Synthesizer 生成下一轮配置和研究笔记
10. Research Ledger 更新本轮假设、证据、淘汰和下一轮原因
```

## 给 LLM 的摘要文件

每阶段都要生成 LLM 可读摘要，避免让 Codex 读巨大 parquet：

```text
llm_brief_round_N.md
leaderboard_top200.md
reject_cluster_summary.md
entry_exit_matrix_digest.md
exit_state_machine_diagnostics.md
overfit_stress_summary.md
portfolio_failure_cases.md
next_round_questions.md
research_ledger.md
risk_blockers.csv
```

## 研究治理

详细规则见：

```text
docs/10_llm_autoresearch_governance.md
```

这个文件定义：

- 研究账本
- 晋级/淘汰闸门
- LLM 调用预算
- 防止研究漂移
- 停止规则
- 最终结论分类

## Codex CLI 使用方式

在 5090 机器上登录 Codex 后，可以用：

```bash
codex exec --cd /data/bwe/v6/code/Autoresearch \
  --sandbox workspace-write \
  --ask-for-approval never \
  "$(cat /data/bwe/v6/prompts/CODEX_ROUND_ANALYST_PROMPT.md)"
```

建议只给 Codex 写权限到：

```text
/data/bwe/v6/code/Autoresearch
/data/bwe/v6/runs
```

不要给 live autotrader 目录写权限。
