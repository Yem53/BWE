---
name: BWE 项目总览
description: BWE (Binance Whale Event) 是 Telegram 三频道消息触发的自动化量化交易研究项目，含 AutoResearch + Codex LLM 循环
type: project
originSessionId: 9aa9a58b-6062-4d43-83be-5004328027b2
---
**BWE = Binance Whale Event**：基于 Telegram 三个频道消息触发的自动化量化交易研究框架。

**Why:** 用户在 H:\ 磁盘维护一个完整的策略研究 pipeline，目标是从历史 BWE 消息中自动发现并验证完整交易策略（trigger + entry + filter + risk + exit）。所有产物都是 paper-only/sandbox-only，禁止任何 live 改动。

**How to apply:** 当用户提到 BWE、AutoResearch、消息触发、三频道、Codex 研究循环、5090 机器执行时，直接关联到这个项目。任何涉及 BWE 的实现都要遵守"sandbox-only、不碰 live、不读 secret"的硬约束。

## 三个消息频道（Telegram）
1. **OI&Price**（方程式OI&Prce异动）—— OI 异动 + 价格变化，主要做空
2. **pricechange**（方程式价格异动监测）—— 价格异动，多空混合
3. **Reserved6**（方程式重大行情提醒）—— 180s 内 8-15% 极端行情，主要做空

## 核心流程
Telegram 消息（T0）→ 标准化事件 → 入场延迟（0/30/60/180/300 秒）→ T0 已知字段过滤 → 开仓 → 动态退出（fixed_tp_sl / prove_then_exit / time_stop / state_machine 等）

## AutoResearch 循环（每轮）
70% 已知策略优化 + 20% 受控新策略发现 + 10% 反常识探索。Codex 在每轮承担 6 个角色：Meta Director / Strategy Architect / Experiment Mutator / Results Analyst / Risk Critic / Lead Synthesizer（每轮 8-15 次调用，总预算 40-150）。

## 验证硬门槛
sample size 达标、median_net>0、p25/p10 不过分负、费用滑点压力后有效、walk-forward 多窗口稳定、去掉 top 1% 赢家不失效、单币种贡献不集中、journal penalty 通过。

## 晋级流程（绝不自动 live）
历史样本外 → paper shadow → 20+ clean complete → journal penalty 复核 → **人工确认**才能升 live。
