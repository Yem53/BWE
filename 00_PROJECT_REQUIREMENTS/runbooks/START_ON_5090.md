# 在 5090 机器上启动 v6 的步骤

## 1. 复制本指导包

建议放到：

```text
/data/bwe/v6
```

目录结构：

```text
/data/bwe/v6/docs
/data/bwe/v6/prompts
/data/bwe/v6/configs
/data/bwe/v6/manifests
/data/bwe/v6/runbooks
```

## 2. 复制数据和代码

从 Mac mini 或 T9 复制：

```text
Autoresearch repo -> /data/bwe/v6/code/Autoresearch
30d feature dir  -> /data/bwe/v6/input/binance_event_features_20260425_30d
v5 results       -> /data/bwe/v6/reference/bwe_autoresearch_entry_v5_20260425
v5 package       -> /data/bwe/v6/reference/bwe_entry_research_v5_package
legacy cache     -> /data/bwe/v6/reference/legacy_market_cache
```

## 3. 填写 manifest

```bash
cp /data/bwe/v6/manifests/data_manifest_template.json /data/bwe/v6/manifests/data_manifest.json
```

然后把里面路径改成 5090 机器上的真实路径。

## 4. 安装/登录 Codex

确认：

```bash
codex --version
codex login
```

使用 ChatGPT Pro 订阅登录。

## 5. 先让 Codex 做数据审计和 smoke plan

这一步必须包含两项数据补强：

```text
legacy_market_cache -> normalized trade kline parquet
1m trade kline coverage audit / missing window plan
```

没有 `trade_kline_coverage_report.csv` 和 `trade_kline_path_resolution_decision.md`，不要进入 medium。

```bash
cd /data/bwe/v6
codex exec --cd /data/bwe/v6/code/Autoresearch \
  --sandbox workspace-write \
  --ask-for-approval never \
  "$(cat /data/bwe/v6/prompts/CODEX_START_V6_COMPLETE_STRATEGY_LAB.md)"
```

## 6. 不要直接 full

顺序必须是：

```text
smoke -> medium -> max_alpha
```

进入 medium 前还必须有：

```text
baseline_comparison.csv
execution_cost_model.json
strategy_similarity_clusters.csv
statistical_significance_plan.md
```

## 7. 每轮结束后让 LLM 读摘要

不要让 Codex 读巨大 parquet。让 AutoResearch 先生成：

```text
leaderboard_top200.md
reject_cluster_summary.md
exit_state_machine_diagnostics.md
overfit_stress_summary.md
portfolio_failure_cases.md
research_ledger.md
```

每轮建议调用顺序：

```text
Meta Research Director
Strategy Architect
Experiment Mutator
Results Analyst
Risk Critic
Lead Synthesizer
```

然后调用：

```bash
codex exec --cd /data/bwe/v6/code/Autoresearch \
  --sandbox workspace-write \
  --ask-for-approval never \
  "$(cat /data/bwe/v6/prompts/CODEX_ROUND_ANALYST_PROMPT.md)"
```

风险审计调用：

```bash
codex exec --cd /data/bwe/v6/code/Autoresearch \
  --sandbox workspace-write \
  --ask-for-approval never \
  "$(cat /data/bwe/v6/prompts/CODEX_RISK_CRITIC_PROMPT.md)"
```

## 8. 最终不要升 live

v6 只输出 paper 策略。任何 live 改动必须另起项目、另做风控审计。
