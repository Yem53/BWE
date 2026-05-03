# 文件索引

## 起点

- `README.md`：总入口，说明目标、目录和启动顺序。
- `runbooks/START_ON_5090.md`：把硬盘接到 5090 机器后，从零启动 v6 的步骤。
- `DATA_SNAPSHOT_INDEX.md`：T9 上已经复制的数据和代码快照说明。

## 已带快照

- `data_snapshot/binance_event_features_20260425_30d/`：30 天 BWE + Binance 特征数据。
- `data_snapshot/bwe_autoresearch_entry_v5_20260425/`：v5 本地真实运行结果，用作 baseline/reference。
- `data_snapshot/bwe_entry_research_v5_package/`：GPT Pro 生成的 v5 策略族/DSL/阈值包。
- `data_snapshot/legacy_market_cache/`：本机已有 BWE 历史 run 的 OHLCV window JSON cache，约 25G，用作补充参考。
- `code_snapshot/Autoresearch/`：当前 Autoresearch 代码快照，已排除 `.git`、`.venv`、缓存。

## 数据与合同

- `docs/01_data_contract_v6.md`：v6 数据合同、字段分区、防未来函数边界。
- `docs/02_data_inventory_and_transfer.md`：需要迁移哪些 Mac mini 数据，以及 5090 目录建议。
- `docs/03_feature_freshness_future_safety.md`：Binance 指标 freshness、未来函数、路径精度规则。
- `docs/08_data_field_requirements.md`：字段级要求，哪些字段必须有，哪些可选，缺失怎么处理。
- `docs/09_trade_kline_legacy_cache_normalization.md`：legacy OHLCV cache 规范化和 1m trade kline 覆盖率/补采要求。
- `docs/10_llm_autoresearch_governance.md`：LLM + AutoResearch 外层循环、研究账本、闸门、停止规则。
- `docs/11_baseline_comparison_framework.md`：baseline 对照、当前 live/v5/reference/random 对照要求。
- `docs/12_execution_cost_latency_model.md`：费用、滑点、延迟、限价未成交模型。
- `docs/13_strategy_dedup_diversity.md`：策略 fingerprint、相似性聚类、manifest 多样性。
- `docs/14_statistical_significance_overfit_control.md`：bootstrap、permutation、多重搜索惩罚、有效样本量。
- `docs/15_paper_shadow_validation_path.md`：research -> paper forward -> shadow 的验证路径。
- `manifests/data_manifest_template.json`：5090 上填写真实路径的 manifest 模板。

## 搜索与运行

- `docs/04_complete_strategy_search_space.md`：完整策略搜索空间。
- `docs/06_5090_execution_plan.md`：smoke / medium / max_alpha 执行规模。
- `configs/v6_max_alpha_search_budget.yaml`：机器可读的搜索预算配置。

## LLM + AutoResearch

- `docs/05_llm_autoresearch_loop.md`：Codex/LLM 在研究循环中的角色。
- `prompts/CODEX_START_V6_COMPLETE_STRATEGY_LAB.md`：首次启动 v6 项目的 prompt。
- `prompts/CODEX_META_RESEARCH_DIRECTOR_PROMPT.md`：每轮决定研究方向、预算和停止/继续条件。
- `prompts/CODEX_STRATEGY_ARCHITECT_PROMPT.md`：每轮生成下一批完整策略族的 prompt。
- `prompts/CODEX_EXPERIMENT_MUTATOR_PROMPT.md`：根据赢家邻域和失败簇生成下一轮变异。
- `prompts/CODEX_ROUND_ANALYST_PROMPT.md`：每轮结果分析 prompt。
- `prompts/CODEX_RISK_CRITIC_PROMPT.md`：风险审计 prompt。
- `prompts/CODEX_LEAD_SYNTHESIZER_PROMPT.md`：汇总多角色意见并生成下一轮配置的 prompt。

## 验收

- `docs/07_acceptance_checklist.md`：最终验收清单。
