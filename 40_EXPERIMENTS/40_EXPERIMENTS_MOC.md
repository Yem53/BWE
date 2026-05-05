---
type: moc
tags: [moc, experiments]
created: 2026-05-02
---

# 🔬 40 实验 — MOC

> Round 1-5 历史 + Round 5 active experiments + paper-shadow + V4 archives.

## Round 历史

| Round | 状态 | 主题 | 关键发现 |
|---|---|---|---|
| Round 1-3 | archived | Initial autoresearch loop + LLM debate | 524 archetypes mapped |
| **Round 4** | archived | 20K-class GPU loop | results.tsv per-experiment commits |
| **Round 5** | 🟢 ACTIVE | Layer A v2/v3 + V4 grid + paper-shadow | 14+ drifts fixed, paper-LIVE-testnet 跑步中 |
| Round 6 | planned | Architecture rebuild — BWE 消息为 pointer 不是 source | 待启动 |

## Round 5 (当前活跃)

### 关键 specs
- [[round5/specs/BWE_PROJECT_DESIGN_RULES|BWE Project Design Rules]] — 10 原则 + Rule #0
- [[round5/specs/PAPER_BACKTEST_DRIFT_LOG|Paper-Backtest Drift Log]] — 14+ drift 持续追踪
- [[round5/specs/2026-04-30-v4-entry-search-archive|V4 Entry Archive]]
- [[round5/specs/2026-04-30-v4-exit-search-archive|V4 Exit Archive]]
- [[round5/specs/2026-05-01-v5-search-prompt|V5 Search Prompt]]
- [[round5/specs/2026-04-30-round6-architecture-audit|Round 6 Architecture Audit]]
- [[round5/specs/2026-04-30-layer-a-v3-grid-expansion-design|Layer A v3 Design]]
- [[round5/specs/2026-04-30-layer-b-design|Layer B Design]]

### Paper-Shadow (active)
- [[round5/paper_shadow/MORNING_BRIEFING|Morning Briefing]] (晨简报)
- [[round5/paper_shadow/STRATEGIES_LIVE|strategies_live.json (13 strategies)]]
- [[round5/paper_shadow/RESTART_LIVE|restart_live.sh]]
- runtime_live/ — paper-LIVE state + logs (跑步中)
- runtime/ — old kline-mode paper (停了)

### V8 5090 Paper-Shadow
- [[v8_5090_paper_shadow_20260504_2347/paper_gate_summary|V8 5090 paper gate summary]] — 20 signal-only candidates, no order endpoints.

### Plans
- [[round5/plans/2026-04-30-layer-a-v3-plan|Layer A v3 Plan]]

### Stage outputs
- `round5/stage1/` — Stage 1 results
- `round5/stage2/` — Stage 2 results
- `round5/stage3/` — Stage 3 robustness + v4 backtest drift checks

## 关键策略 Summary

### 13 Active Paper Strategies
- 4 Legacy: ST15v2, ST15v3, ST8/EP3, ST9/EP13
- 9 V4 matrix:
  - **BROAD** entry (yao≥1, mag 3-10%) × 3 exits = PS5/6/7
  - **CHAMP** entry (top_LS>0.9, funding>0) × 3 exits = PS8/9/10
  - **QUAL** entry (top_LS>1, funding>0, yao≥1) × 3 exits = PS11/12/13

### V4 Backtest Winners (含 1m kline look-ahead bias)
- CHAMP_AGG: n=525, mean +7.96%, sum +4177%, WR 74%
- After D1-D4 fix: n=534, mean +10.00% (alpha confirmed real)
- After D9 cap=5: mean +2.72% (paper-aligned realistic)

## Paper-LIVE 真实数据 (持续累积)

- 2026-05-02 02:14 UTC: Paper-LIVE PID started with mark price API + testnet
- 7h 后: 30 closed trades, sum -110%, LABUSDT 单币 80%
- 真实 alpha estimate: +1~3% mean per trade (after market friction)

## 相关

- [[../00_INDEX|HOME]]
- [[../50_ANALYSIS_REPORTS/50_ANALYSIS_REPORTS_MOC|50 Analysis Reports]]
- [[../60_NEXT_ROUND/60_NEXT_ROUND_MOC|60 Next Round]]

## 📁 All folder indexes (auto-link)

> Auto-generated indexes for every subfolder with 3+ .md files. Click to explore.

  - [[all_runs_archive/_FOLDER_INDEX|📁 all_runs_archive/]]
    - [[bwe_complete_strategy_v6_max_alpha_aggressive_base_20260426_105007/_FOLDER_INDEX|📁 bwe_complete_strategy_v6_max_alpha_aggressive_base_20260426_105007/]]
    - [[bwe_complete_strategy_v6_max_alpha_aggressive_base_20260426_105213/_FOLDER_INDEX|📁 bwe_complete_strategy_v6_max_alpha_aggressive_base_20260426_105213/]]
    - [[bwe_complete_strategy_v6_max_alpha_aggressive_base_20260426_105303/_FOLDER_INDEX|📁 bwe_complete_strategy_v6_max_alpha_aggressive_base_20260426_105303/]]
    - [[bwe_complete_strategy_v6_max_alpha_aggressive_strong_20260426_105007/_FOLDER_INDEX|📁 bwe_complete_strategy_v6_max_alpha_aggressive_strong_20260426_105007/]]
    - [[bwe_complete_strategy_v6_max_alpha_aggressive_strong_20260426_105213/_FOLDER_INDEX|📁 bwe_complete_strategy_v6_max_alpha_aggressive_strong_20260426_105213/]]
    - [[bwe_complete_strategy_v6_max_alpha_aggressive_strong_20260426_105303/_FOLDER_INDEX|📁 bwe_complete_strategy_v6_max_alpha_aggressive_strong_20260426_105303/]]
    - [[bwe_complete_strategy_v6_max_alpha_gpu_fused_base_20260426_115022/_FOLDER_INDEX|📁 bwe_complete_strategy_v6_max_alpha_gpu_fused_base_20260426_115022/]]
    - [[bwe_complete_strategy_v6_max_alpha_gpu_fused_base_20260426_115115/_FOLDER_INDEX|📁 bwe_complete_strategy_v6_max_alpha_gpu_fused_base_20260426_115115/]]
    - [[bwe_complete_strategy_v6_max_alpha_gpu_fused_strong_20260426_115022/_FOLDER_INDEX|📁 bwe_complete_strategy_v6_max_alpha_gpu_fused_strong_20260426_115022/]]
    - [[bwe_complete_strategy_v6_max_alpha_gpu_fused_strong_20260426_115115/_FOLDER_INDEX|📁 bwe_complete_strategy_v6_max_alpha_gpu_fused_strong_20260426_115115/]]
      - [[llm_round_notes/_FOLDER_INDEX|📁 llm_round_notes/]]
        - [[deep_round1_autoresearch_expanded_20260426_134513/_FOLDER_INDEX|📁 deep_round1_autoresearch_expanded_20260426_134513/]]
        - [[deep_round1_autoresearch_expanded_20260426_134601/_FOLDER_INDEX|📁 deep_round1_autoresearch_expanded_20260426_134601/]]
        - [[deep_round1_autoresearch_expanded_20260426_134801/_FOLDER_INDEX|📁 deep_round1_autoresearch_expanded_20260426_134801/]]
          - [[role_memos/_FOLDER_INDEX|📁 role_memos/]]
          - [[role_memos/_FOLDER_INDEX|📁 role_memos/]]
          - [[cross_exam/_FOLDER_INDEX|📁 cross_exam/]]
          - [[role_memos/_FOLDER_INDEX|📁 role_memos/]]
          - [[cross_exam/_FOLDER_INDEX|📁 cross_exam/]]
          - [[final/_FOLDER_INDEX|📁 final/]]
          - [[role_memos/_FOLDER_INDEX|📁 role_memos/]]
    - [[bwe_complete_strategy_v6_medium_20260426_000612/_FOLDER_INDEX|📁 bwe_complete_strategy_v6_medium_20260426_000612/]]
    - [[bwe_complete_strategy_v6_medium_20260426_000641/_FOLDER_INDEX|📁 bwe_complete_strategy_v6_medium_20260426_000641/]]
    - [[bwe_complete_strategy_v6_smoke_20260425_233130/_FOLDER_INDEX|📁 bwe_complete_strategy_v6_smoke_20260425_233130/]]
    - [[bwe_complete_strategy_v6_smoke_20260425_233200/_FOLDER_INDEX|📁 bwe_complete_strategy_v6_smoke_20260425_233200/]]
      - [[llm_round_notes/_FOLDER_INDEX|📁 llm_round_notes/]]
    - [[bwe_complete_strategy_v6_smoke_20260425_233523/_FOLDER_INDEX|📁 bwe_complete_strategy_v6_smoke_20260425_233523/]]
      - [[llm_round_notes/_FOLDER_INDEX|📁 llm_round_notes/]]
    - [[bwe_complete_strategy_v6_smoke_20260425_235328/_FOLDER_INDEX|📁 bwe_complete_strategy_v6_smoke_20260425_235328/]]
      - [[llm_round_notes/_FOLDER_INDEX|📁 llm_round_notes/]]
  - [[paper_shadow/_FOLDER_INDEX|📁 paper_shadow/]]
    - [[00_planning/_FOLDER_INDEX|📁 00_planning/]]
    - [[04_codex_tasks/_FOLDER_INDEX|📁 04_codex_tasks/]]
  - [[round4/_FOLDER_INDEX|📁 round4/]]
    - [[archive/_FOLDER_INDEX|📁 archive/]]
    - [[paper_shadow/_FOLDER_INDEX|📁 paper_shadow/]]
    - [[specs/_FOLDER_INDEX|📁 specs/]]

## 🗂 Standalone files (mostly archive)

- [[2026-04-30-layer-a-short-deepening-plan|Layer A Short Deepening Plan]]
- [[corrections_report|Corrections Report (paper-shadow runtime/)]]
- [[r4_score_metric_proposal|Round 4 Score Metric Proposal]]
- [[x100_audit_report|Round 4 x100 Audit Report]]
- [[alerts_spec_v1|Round 4 Alerts Spec v1]]
- [[p0_fixes_spec|Round 4 P0 Fixes Spec]]
- [[compare_v2_v3|Round 5 Stage 3 v2 vs v3 compare]]
- [[morning_brief_20260427_193732|Morning Brief 2026-04-27]]

## 📁 More folder indexes

- [[debates/_FOLDER_INDEX|📁 debates/]]
- [[analysis/_FOLDER_INDEX|📁 analysis/]]
