---
type: moc
tags: [moc, code]
created: 2026-05-02
---

# 💻 20 代码 — MOC

> Autoresearch 框架 + LLM team + paper-shadow 代码归档.

## 主要代码位置

### Autoresearch (核心 loop)
- `20_CODE/Autoresearch/bwe_autoresearch/` — 核心 loop + LLM team
- `20_CODE/Autoresearch/prompts/` — 11 个 LLM 角色 prompt + TEAM_PHILOSOPHY.md
- `20_CODE/Autoresearch/scripts/` — analyze, rescore, paper_shadow, brief

### Round 5 实验代码
- `40_EXPERIMENTS/round5/src/` — 当前活跃代码
  - `paper_shadow.py` — kline-mode paper (legacy)
  - `paper_shadow_live.py` — mark price API mode + testnet
  - `binance_client.py` — public API wrapper
  - `binance_testnet_client.py` — HMAC-signed testnet client
  - `backtest_runner.py` — single experiment runner
  - `events.py` — BWE event parser
  - `paths.py` — path constants (T9 paths)

### Hermes Scripts (data collectors)
- `~/.hermes/scripts/binance_futures_1m_collector.py` — 1m+ kline collector (multi-tf 复用)
- `~/.hermes/scripts/binance_spot_1s_collector.py` — 1s spot collector (NEW)
- `~/.hermes/scripts/binance_futures_metric_collector.py` — mark/funding/OI/LS
- `~/.hermes/scripts/bwe_matrix_monitor.py` — BWE Telegram listener
- `~/.hermes/scripts/bwe_live_autotrader.py` — real trader (HTTP 451 blocked)

## LLM Debate Config (Round 4+)

- `--model claude-opus-4-7` (1M context, 64K output)
- `--effort max` (deepest extended-thinking budget)
- `--exclude-dynamic-system-prompt-sections`
- 用户 Max $200/mo, 不需要 downgrade

## 重要 Rules

- DRY, YAGNI, TDD, frequent commits
- Karpathy autoresearch single-file 纪律
- 真实工程 — 不要 mock data, 不要 fake completions
- 数据驱动 (Rule #0)

## 相关

- [[../CLAUDE|CLAUDE.md]]
- [[../40_EXPERIMENTS/round5/specs/BWE_PROJECT_DESIGN_RULES|Design Rules]]
- [[../40_EXPERIMENTS/round5/specs/PAPER_BACKTEST_DRIFT_LOG|Drift Log]]

## 📁 All folder indexes (auto-link)

> Auto-generated indexes for every subfolder with 3+ .md files. Click to explore.

  - [[Autoresearch/_FOLDER_INDEX|📁 Autoresearch/]]
    - [[prompts/_FOLDER_INDEX|📁 prompts/]]
      - [[bwe_deep_autoresearch_20260425/_FOLDER_INDEX|📁 bwe_deep_autoresearch_20260425/]]
      - [[bwe_deep_autoresearch_20260425_round2_full_exit/_FOLDER_INDEX|📁 bwe_deep_autoresearch_20260425_round2_full_exit/]]

## 🗂 Standalone
- [[experiment_guardrails|Autoresearch Experiment Guardrails]]
