# 07. v6 验收清单

## 数据验收

- [ ] 30 天 BWE 事件读取成功。
- [ ] Binance features 表读取成功。
- [ ] forward path 表读取成功。
- [ ] mark/premium raw path 读取成功。
- [ ] local trade kline 缺失被明确记录，不能假装存在。
- [ ] `legacy_market_cache` 已解析成规范 parquet，或明确记录解析失败原因。
- [ ] 已生成 `trade_kline_coverage_report.csv`。
- [ ] 已生成 `trade_kline_path_resolution_decision.md`。
- [ ] 所有事件有稳定 `event_id`。
- [ ] 所有策略有稳定 `strategy_id`。
- [ ] feature freshness 可计算。
- [ ] future label 字段被隔离。

## 搜索验收

- [ ] 从完整策略空间搜索，不被 v5 17 条限制。
- [ ] 覆盖 long / short / no_trade。
- [ ] 覆盖 T0 / 30s / 1m / 3m / 5m / conditional wait。
- [ ] 覆盖至少 8 类退出家族。
- [ ] 覆盖 risk rule 和 portfolio rule。
- [ ] 支持 checkpoint/resume。
- [ ] 有 smoke/medium/max_alpha 三档。
- [ ] 必跑 baseline：message-only、timing、simple exit、current live、v5 reference、random/shuffled。
- [ ] 所有候选必须与同口径 baseline 比较。

## 回测验收

- [ ] 所有结果扣除手续费和滑点。
- [ ] 支持 latency stress。
- [ ] 支持 liquidity-aware slippage。
- [ ] 支持 limit missed-fill sensitivity，或明确不使用 limit fill 假设。
- [ ] 支持 first-touch path simulation。
- [ ] first-touch 结果标注 trade kline 覆盖率和 fallback 策略。
- [ ] 支持 partial exit。
- [ ] 支持 trailing stop。
- [ ] 支持 breakeven。
- [ ] 支持 runner。
- [ ] 支持 indicator invalidation exit。
- [ ] 标注 path_resolution。

## 稳健性验收

- [ ] purged chronological walk-forward。
- [ ] bootstrap confidence interval。
- [ ] permutation test。
- [ ] multiple testing penalty。
- [ ] effective sample size report。
- [ ] remove top 1% winners。
- [ ] remove top symbol。
- [ ] remove top 5 symbols。
- [ ] fee/slippage stress。
- [ ] latency stress。
- [ ] threshold neighborhood stability。
- [ ] strategy complexity penalty。
- [ ] symbol concentration report。
- [ ] strategy fingerprint 和 similarity cluster。
- [ ] paper manifest 去重和多样性报告。

## 组合层验收

- [ ] 同币种只持一单。
- [ ] 最大并发仓位。
- [ ] same-symbol cooldown。
- [ ] 日亏损暂停。
- [ ] 连亏暂停。
- [ ] 多策略同时触发优先级。
- [ ] 资金占用模拟。
- [ ] portfolio drawdown。

## LLM 验收

- [ ] LLM 只读摘要，不读巨大 parquet。
- [ ] 每轮有 `llm_round_notes`。
- [ ] 每轮有下一轮 search_space 修改说明。
- [ ] Risk Critic 单独审计未来函数/过拟合。
- [ ] 最终报告区分事实、推断、待验证。

## 最终产物验收

- [ ] `paper_manifest_v6.json`
- [ ] `complete_strategy_leaderboard.csv`
- [ ] `report_v6_zh.md`
- [ ] `reject_log.csv`
- [ ] `overfit_stress_report.csv`
- [ ] `portfolio_replay_summary.csv`
- [ ] `data_contract_v6.md`
- [ ] `run_summary.json`
