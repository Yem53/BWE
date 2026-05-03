---
type: moc
tags: [moc, requirements]
created: 2026-05-02
---

# 📌 00 项目需求 — MOC

> 业务目标、资金、安全规则的 single source of truth.

## 核心要求 (用户原话)

> "结合 BWE 的消息, 加上消息对应时间的交易对 K 线图和 binance 其它的交易数据, 然后使用 GitHub 项目 auto research 的架构, 榨干 5090 的算力, 然后去寻找最优的开仓和平仓的策略组合."

## 4 个评分维度

1. **数据完整性** — 消息 + kline + binance 其它数据 join
2. **架构忠实度** — Karpathy autoresearch loop, 单文件纪律, NEVER STOP, results.tsv per-experiment commit
3. **5090 利用率** — GPU 真实 scoring, not 90%+ idle
4. **优化深度** — entry × exit 真正联合搜索, 不只单边

## 资金 + 风险 posture

- **$1000 USDT** trading capital
- **5-10% per-trade sizing** (paper 当前 7.5%)
- "正收益就上 live" — 任何正期望值 → promote (after gates)
- 用户从 Mac mini trading, NOT 5090

## 三个 Telegram 频道

| Channel | 行为 | 默认方向 |
|---|---|---|
| `BWE_OI_Price_monitor` (方程式 OI&Price 异动) | OI 异动 + 价格变化 | 多 short |
| `BWE_pricechange_monitor` (方程式价格异动监测) | Price moves | long+short mix |
| `BWE_Reserved6` (方程式重大行情提醒) | 180s 内 8-15% 极端行情 | 多 short |

## Hard Rules (sandbox-only)

1. NEVER read or print API keys / tokens / secrets
2. NEVER edit live autotrader configs
3. NEVER call Binance/OKX order endpoints (testnet 除外, 用户授权后)
4. NEVER auto-promote backtest winner to live — 必过 paper-shadow + journal penalty + 用户**显式**确认
5. 所有 experiment artifacts under `40_EXPERIMENTS/<run_id>/`, reports under `50_ANALYSIS_REPORTS/`, never H:\ root
6. Stability over absolute return — primary sort key 是 `stability_score`, 不是 `mean_return`

## 相关文档

- [[../CLAUDE|CLAUDE.md]] — 全局指令
- [[../AGENTS|AGENTS.md]] — agent 编排
- [[../40_EXPERIMENTS/round5/specs/BWE_PROJECT_DESIGN_RULES|BWE Project Design Rules]] — 10 原则
- [[../README|README]]
- [[../中文导航|中文导航]]

## 📁 All folder indexes (auto-link)

> Auto-generated indexes for every subfolder with 3+ .md files. Click to explore.

  - [[docs/_FOLDER_INDEX|📁 docs/]]
  - [[prompts/_FOLDER_INDEX|📁 prompts/]]
  - [[root_indexes/_FOLDER_INDEX|📁 root_indexes/]]
