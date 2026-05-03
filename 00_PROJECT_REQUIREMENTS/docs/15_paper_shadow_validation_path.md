# 15. Paper / Shadow 验证路径

## 目的

v6 的最终结果只允许是 paper 候选。为了避免研究和真实系统断层，需要提前定义 paper/shadow 验证路径。

本文件不设计 live 风控细节；live 风控之后另起阶段。

## 阶段定义

### Research

离线历史数据研究。

输出：

```text
paper_manifest_v6.json
report_v6_zh.md
```

### Paper forward

新消息出现时，只记录策略信号和模拟成交，不下单。

记录：

- signal time
- decision
- entry price assumption
- exit decision
- simulated pnl
- reason codes
- feature freshness
- path resolution

### Shadow

更接近真实执行环境的影子交易。

记录：

- real-time feature availability
- measured decision latency
- order simulation latency
- missed fill simulation
- slippage estimate
- strategy conflict

### Small live

不在 v6 范围内。必须另起风控审计后才允许讨论。

## Promote from research to paper forward

必须满足：

- 超过 baseline
- stress 后仍有效
- path resolution 充分声明
- future safety pass
- false discovery audit pass
- strategy dedup pass
- 有明确 no-trade/fallback 逻辑

## Promote from paper forward to shadow

至少需要：

- 连续一段新数据 paper 表现不崩
- 真实 feature freshness 达标
- 决策延迟在模型假设内
- 模拟滑点没有明显低估
- 信号频率和历史预期一致

## 输出产物

```text
paper_forward_plan.md
paper_forward_signal_schema.json
shadow_validation_plan.md
promotion_gate_research_to_paper.csv
promotion_gate_paper_to_shadow.csv
```

## 明确禁止

- v6 不输出 live_allowed=true。
- v6 不写 live 下单逻辑。
- v6 不改 launchd。
- v6 不读取交易所 secret。
- v6 不发 Telegram 下单信号。

