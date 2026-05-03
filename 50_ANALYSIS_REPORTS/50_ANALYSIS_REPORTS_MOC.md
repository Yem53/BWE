---
type: moc
tags: [moc, reports]
created: 2026-05-02
---

# 📝 50 分析报告 — MOC

> Stage 输出 + cross-round 对比 + morning briefs.

## Active Reports

- [[../40_EXPERIMENTS/morning_brief_latest|Morning Brief Latest]] — 每日中文总结 (auto-generated)
- [[../40_EXPERIMENTS/round5/paper_shadow/MORNING_BRIEFING|Paper-LIVE Morning Briefing]]
- [[../40_EXPERIMENTS/round5/specs/PAPER_BACKTEST_DRIFT_LOG|Drift Log Analysis]]

## Stage 输出

- `round5/stage1/` — Stage 1 (initial filter pass)
- `round5/stage2/` — Stage 2 (parameter grid search)
- `round5/stage3/` — Stage 3 (robustness + drift checks)

## Cross-Round 对比

- TBD: V4 vs V5 winners (after V5 complete)
- TBD: Backtest vs paper-LIVE-testnet (24-48h sample)

## 最关键 metric

- Mean per trade > 0% → alpha exists
- Win rate > 50% → mean reversion edge real
- Sum / n × WR + ATR scaling → real PnL projection
- Sample size > 200 trades → 统计稳定

## 相关

- [[../00_INDEX|HOME]]
- [[../40_EXPERIMENTS/40_EXPERIMENTS_MOC|40 Experiments]]

## 📁 All folder indexes (auto-link)

> Auto-generated indexes for every subfolder with 3+ .md files. Click to explore.

  - [[autoresearch_expanded_round1/_FOLDER_INDEX|📁 autoresearch_expanded_round1/]]
    - [[role_memos/_FOLDER_INDEX|📁 role_memos/]]
    - [[cross_exam/_FOLDER_INDEX|📁 cross_exam/]]
    - [[final/_FOLDER_INDEX|📁 final/]]
    - [[role_memos/_FOLDER_INDEX|📁 role_memos/]]

## 🗂 Standalone files

- [[longform_round1/00_long_form_method|longform_round1: 00_long_form_method]]
- [[true_deep_round1/00_method_and_scope|true_deep_round1: 00_method_and_scope]]
