# BWE Complete Strategy AutoResearch v6 指导包

本目录用于把 BWE v6 项目的数据要求、研究流程、5090 机器执行方式、Codex/LLM 调用规范集中带到新机器上。

## 目标

用最近 1 个月 BWE 消息和 Binance 数据，从零搜索完整交易策略：

```text
BWE 消息触发
-> 是否交易
-> long / short / no_trade
-> 入场时机
-> 入场条件
-> 初始风控
-> 持仓中监控
-> 平仓状态机
-> 组合层约束
```

核心目标不是生成最多策略，而是在强防过拟合约束下，最大化找到真实 alpha 的概率。

## 当前已知源数据位置

Mac mini 上当前主要输入：

```text
/Users/ye/.hermes/research/bwe_three_channel_fullrun3/binance_event_features_20260425_30d
/Users/ye/.hermes/research/bwe_autoresearch_entry_v5_20260425
/Users/ye/Downloads/bwe_entry_research_v5_package
/Users/ye/Desktop/Github/Autoresearch
```

本 T9 目录中已经放入对应快照：

```text
data_snapshot/binance_event_features_20260425_30d
data_snapshot/bwe_autoresearch_entry_v5_20260425
data_snapshot/bwe_entry_research_v5_package
data_snapshot/legacy_market_cache
code_snapshot/Autoresearch
```

在 5090 机器上可以把这些路径映射到本地高速 SSD，例如：

```text
/data/bwe/v6/input/binance_event_features_30d
/data/bwe/v6/reference/entry_v5_results
/data/bwe/v6/reference/bwe_entry_research_v5_package
/data/bwe/v6/code/Autoresearch
```

## 目录说明

```text
data_snapshot/
  binance_event_features_20260425_30d/
  bwe_autoresearch_entry_v5_20260425/
  bwe_entry_research_v5_package/
  legacy_market_cache/

code_snapshot/
  Autoresearch/

docs/
  00_project_scope_v6.md
  01_data_contract_v6.md
  02_data_inventory_and_transfer.md
  03_feature_freshness_future_safety.md
  04_complete_strategy_search_space.md
  05_llm_autoresearch_loop.md
  06_5090_execution_plan.md
  07_acceptance_checklist.md
  08_data_field_requirements.md
  09_trade_kline_legacy_cache_normalization.md
  10_llm_autoresearch_governance.md
  11_baseline_comparison_framework.md
  12_execution_cost_latency_model.md
  13_strategy_dedup_diversity.md
  14_statistical_significance_overfit_control.md
  15_paper_shadow_validation_path.md

configs/
  v6_max_alpha_search_budget.yaml

manifests/
  data_manifest_template.json

prompts/
  CODEX_START_V6_COMPLETE_STRATEGY_LAB.md
  CODEX_META_RESEARCH_DIRECTOR_PROMPT.md
  CODEX_STRATEGY_ARCHITECT_PROMPT.md
  CODEX_EXPERIMENT_MUTATOR_PROMPT.md
  CODEX_ROUND_ANALYST_PROMPT.md
  CODEX_RISK_CRITIC_PROMPT.md
  CODEX_LEAD_SYNTHESIZER_PROMPT.md

runbooks/
  START_ON_5090.md
```

## 重要边界

- 本轮只做 sandbox / paper research。
- 不下单。
- 不改 live autotrader。
- 不读 secrets。
- 不发 Telegram。
- v5 的 17 条策略只能做 baseline/reference，不能限制 v6 搜索空间。
- v6 必须从完整策略空间中搜索 entry + exit 组合。

## 推荐启动顺序

1. 在 5090 机器上复制代码和 30 天数据。
2. 按 `runbooks/START_ON_5090.md` 做环境检查。
3. 用 `manifests/data_manifest_template.json` 填真实路径。
4. 用 `prompts/CODEX_START_V6_COMPLETE_STRATEGY_LAB.md` 启动 Codex。
5. 先跑 `smoke`，再跑 `medium`，最后跑 `max_alpha`。
