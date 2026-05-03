# 10. LLM + AutoResearch 研究治理增强

## 为什么要加强

普通循环是：

```text
LLM 提策略 -> AutoResearch 回测 -> LLM 读结果 -> 下一轮
```

这还不够。v6 目标是最大化 alpha 发现概率，必须让循环具备：

- 研究记忆
- 预算分配
- 晋级/淘汰闸门
- 失败簇解释
- 参数邻域扩展
- 风险审计
- 停止规则
- 反思改写

否则 LLM 容易反复提出相似策略，AutoResearch 也容易把算力花在低质量空间。

## 强化后的外层循环

```text
Round N
1. Meta Research Director 读取长期研究账本，决定本轮主攻方向
2. Strategy Architect 生成完整策略族
3. Experiment Mutator 根据上一轮失败簇和赢家邻域生成变异
4. AutoResearch 展开候选并粗筛
5. Results Analyst 分析排行榜、失败簇、有效 feature/exit 组合
6. Risk Critic 做未来函数、过拟合、左尾、路径精度审计
7. Lead Synthesizer 合并意见，生成下一轮配置
8. Research Ledger 更新：保留什么、淘汰什么、下一轮为什么这么做
```

## 研究账本

每轮必须维护：

```text
research_ledger.md
research_ledger.jsonl
```

每条记录至少包含：

- round_id
- hypothesis
- strategy_families_added
- strategy_families_removed
- mutation_reason
- compute_budget_used
- codex_calls_used
- top_findings
- rejected_because
- risk_blockers
- next_round_decision

## 晋级/淘汰闸门

### Promote to more budget

满足多数条件才加预算：

- median > baseline
- p25/p10 左尾不恶化
- stress median > 0
- walk-forward positive rate 高
- 去 top winner 后仍有效
- 去 top symbol 后仍有效
- strategy complexity 可接受
- path resolution 足够支撑该退出结论

### Mutate

满足以下条件进入变异：

- median 正但左尾差
- entry 有 alpha 但 exit giveback 高
- exit 有效但样本少
- 某 feature 在部分 regime 有效
- long/short 方向不稳定但 no_trade 边界有价值

### Reject

直接淘汰：

- future safety violation
- stress 后失效
- top 1% winner dependent
- single symbol dependent
- walk-forward 多数窗口失败
- path resolution 不足却依赖 first-touch 结论
- 复杂度高但收益不显著

## LLM 调用预算

质量优先，但限制在 ChatGPT Pro/Codex 订阅可控范围内：

```text
每轮目标 10-18 次 Codex 调用
完整项目 5-10 轮
总调用目标 80-180 次
硬上限 220 次
```

调用优先级：

1. Risk Critic
2. Results Analyst
3. Lead Synthesizer
4. Strategy Architect
5. Experiment Mutator
6. Meta Research Director

如果额度紧张，减少 Strategy Architect 和 Mutator 的次数，不减少 Risk Critic。

## 防止 LLM 研究漂移

每轮 prompt 必须带上：

- 项目目标
- 当前数据限制
- 当前 best baseline
- 当前 reject 原因分布
- 本轮预算
- 不能触碰 live/secrets
- 不允许把 v5 17 条当搜索边界

每轮 LLM 输出必须写明：

- 哪些结论来自回测证据
- 哪些只是推断
- 哪些需要下一轮验证

## 停止规则

满足以下任一条件可以停止 max-alpha 研究：

- 连续 3 轮没有提升 top robust score。
- 连续 3 轮新策略都被同类 risk blocker 拦截。
- top 策略邻域稳定，继续扩大空间没有改善。
- 当前样本量不足成为主瓶颈，更多搜索只会增加过拟合。
- 组合层回放显示收益被并发/cooldown/滑点持续吃掉。

停止不是失败，而是进入下一阶段：

```text
paper forward test
shadow replay
more data collection
exit-only refinement
```

## 最终研究结论格式

最终报告必须分成四类：

- `promote_to_paper`
- `watchlist`
- `need_more_data`
- `reject`

任何策略不得直接标记 live。

