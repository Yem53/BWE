# Codex Prompt: Start BWE Complete Strategy Lab v6

你现在要在本机启动 BWE Complete Strategy AutoResearch v6。目标是用最近 1 个月 BWE + Binance 数据，从零搜索完整开仓和平仓组合策略，不受 v5 17 条入场候选限制。

## 权限边界

- 只做 sandbox / paper research。
- 不下单。
- 不改 live autotrader。
- 不读 secrets。
- 不发 Telegram。
- 不改 launchd。
- v5 只能作为 baseline/reference。

## 输入

请先读取：

```text
README.md
docs/00_project_scope_v6.md
docs/01_data_contract_v6.md
docs/02_data_inventory_and_transfer.md
docs/03_feature_freshness_future_safety.md
docs/04_complete_strategy_search_space.md
docs/05_llm_autoresearch_loop.md
docs/06_5090_execution_plan.md
docs/07_acceptance_checklist.md
docs/08_data_field_requirements.md
docs/09_trade_kline_legacy_cache_normalization.md
docs/10_llm_autoresearch_governance.md
docs/11_baseline_comparison_framework.md
docs/12_execution_cost_latency_model.md
docs/13_strategy_dedup_diversity.md
docs/14_statistical_significance_overfit_control.md
docs/15_paper_shadow_validation_path.md
configs/v6_max_alpha_search_budget.yaml
manifests/data_manifest.json
```

如果 `manifests/data_manifest.json` 不存在，请从 `manifests/data_manifest_template.json` 复制并让操作者填真实路径，或者根据当前机器路径自动生成草案。

## 第一阶段任务

1. 校验数据路径和 parquet 行数。
2. 生成 `data_copy_audit.md/json`。
3. 解析 `legacy_market_cache`，生成规范 parquet 和覆盖率审计。
4. 审计/补齐 1m trade kline event windows，并输出 path resolution 决策。
5. 建立 baseline comparison、execution cost、dedup/diversity、statistical significance 验证层。
6. 审查当前 Autoresearch repo 里 v3/v4/v5 的实现。
7. 设计 v6 代码结构。
8. 建立 `research_ledger.md/jsonl` 和 round directive 机制。
9. 先实现 smoke 级完整策略搜索，不要直接 full。

## v6 必须实现

完整策略候选必须包含：

- trigger
- side
- entry timing
- entry conditions
- initial stop
- take profit
- partial exit
- trailing stop
- breakeven
- runner
- indicator invalidation exit
- max hold time
- portfolio constraints

## 输出

先输出：

```text
v6_implementation_plan.md
data_copy_audit.md
legacy_market_cache_parse_audit.csv
trade_kline_coverage_report.csv
trade_kline_path_resolution_decision.md
research_ledger.md
round_configs/round_1_research_directive.yaml
baseline_catalog.jsonl
execution_cost_model.json
strategy_fingerprint_schema.md
statistical_significance_plan.md
paper_forward_plan.md
smoke_run_command.sh
```

然后实现并运行 smoke。

## 成功标准

- smoke 跑通。
- 有防未来函数测试。
- 有 freshness 测试。
- 有完整策略 leaderboard。
- 有 reject log。
- 有 LLM brief。
- 已声明 `path_resolution`，且 first-touch 结果不夸大路径精度。
- 所有产物明确 `paper_only=true` 和 `live_allowed=false`。
