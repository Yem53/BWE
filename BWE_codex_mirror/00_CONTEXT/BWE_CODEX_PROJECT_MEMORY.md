# BWE Codex Project Memory

Created: 2026-05-02
Scope: stable onboarding memory for Codex sessions working from `/Volumes/T9/BWE_codex`.

## My Role

The user calls Codex to assist the BWE project. Codex-produced artifacts should land in:

`/Volumes/T9/BWE_codex`

Use this directory for reports, handoffs, audits, context notes, and Codex working memory. Do not treat it as the trading system itself.

The BWE project and Obsidian vault are separate:

`/Volumes/T9/BWE`

Write-scope lock from the user on 2026-05-02:

- Codex may modify files only under `/Volumes/T9/BWE_codex`.
- Codex may not modify `/Volumes/T9/BWE`.
- Codex may not modify Obsidian vault content or config.
- Codex may inspect BWE and Obsidian files read-only.
- Any BWE/Obsidian repair, sync, or implementation should be written as a proposed plan or patch under `BWE_codex`, not applied directly.

## Default Startup Rule

For future BWE tasks, first browse the BWE project read-only and read:

1. `/Volumes/T9/BWE/CLAUDE.md`
2. `/Volumes/T9/BWE/00_INDEX.md`
3. The relevant BWE subdirectories for the task

Treat BWE's `CLAUDE.md` as the action guideline for project behavior, safety, and workflow conventions. The only exception is write scope: Codex still may modify only `/Volumes/T9/BWE_codex`.

## User Purpose

BWE means Binance Whale Event.

The user's core purpose is:

> Combine BWE Telegram messages with the corresponding symbol's K-line and other Binance trading data, use a Karpathy-style autoresearch loop, max out the 5090 compute, and search for the best entry plus exit strategy combinations.

The practical target is not an academic report. The target is a data-backed crypto futures strategy pipeline that can move from research to paper-shadow and then, only after explicit confirmation, to live trading.

Everything should be judged against four dimensions:

1. Data completeness: BWE message plus corresponding kline plus Binance features are actually joined.
2. Architecture fidelity: Karpathy-style loop discipline, results table, keep/discard/crash behavior, and continuous iteration.
3. Compute use: 5090 should be used for real scoring work, not idle orchestration.
4. Optimization depth: entry and exit must be searched together, not optimized one side in isolation.

## Capital And Risk Posture

- User capital assumption: about 1000 USDT.
- Per-trade sizing target: 5-10%.
- "Positive expectancy can go live" means after gates, not directly after a backtest.
- Stability is more important than highest historical mean return.
- Paper-shadow and explicit user confirmation are mandatory before live promotion.

## Source Map

Current checked paths on 2026-05-02:

- Codex output root: `/Volumes/T9/BWE_codex`
- Intended BWE vault/root: `/Volumes/T9/BWE`
- Hot runtime storage: `/Volumes/T9_HOT`
- Full backup snapshot: `/Volumes/Samsung_BWE/T9_BACKUP_20260502/BWE`

Important current discrepancy:

- `/Volumes/T9/BWE` has the vault entry docs and data directories, but some expected files are missing from the active T9 copy.
- `/Volumes/T9/BWE/40_EXPERIMENTS/round5/src` currently contains directories and metadata, but not the expected Python source files.
- `/Volumes/T9/BWE/Templates` currently exists but is empty.
- `/Volumes/T9/BWE/99_ADMIN/day1_active_plan.md` is missing.
- The full backup under `/Volumes/Samsung_BWE/T9_BACKUP_20260502/BWE` contains the missing templates, MOCs, admin files, and round5 source files.

Therefore, when asked to inspect current BWE code or historical artifacts, first decide which source is intended:

- For current hot runtime state: inspect `/Volumes/T9_HOT`.
- For vault/root docs currently mounted on T9: inspect `/Volumes/T9/BWE`.
- For complete historical code and notes: inspect `/Volumes/Samsung_BWE/T9_BACKUP_20260502/BWE`.
- For Codex output and handoffs: write under `/Volumes/T9/BWE_codex`.

## Key Project Areas

`/Volumes/T9/BWE/00_PROJECT_REQUIREMENTS`

Project scope, data contracts, governance, prompts, manifests, runbooks, and search-budget configs.

`/Volumes/T9/BWE/20_CODE/Autoresearch`

Current AutoResearch code copy. Key modules include:

- `bwe_autoresearch/bwe_loop.py`
- `bwe_autoresearch/bwe_loop_entry_filter.py`
- `bwe_autoresearch/bwe_loop_exit_kernels.py`
- `bwe_autoresearch/bwe_loop_gpu_eval.py`
- `bwe_autoresearch/bwe_loop_score_metric.py`
- `bwe_autoresearch/bwe_loop_score_v2.py`
- `bwe_autoresearch/bwe_loop_results.py`
- `bwe_autoresearch/bwe_paths.py`

`/Volumes/T9/BWE/30_DATA`

Market and event data. Current T9 checked size was about 43G. Important subareas:

- `cache/binance_trade_klines_1m_raw/`
- `cache/normalized/`
- `input/`
- `reference/`

`/Volumes/T9_HOT`

Runtime hot data:

- `binance_collectors_runtime` around 14G
- `bwe_logs` around 27M
- `paper_shadow_runtime_live`

`/Volumes/Samsung_BWE/T9_BACKUP_20260502/BWE/40_EXPERIMENTS`

Full historical experiment archive, about 10G in the backup. Use this when the active T9 copy lacks round files.

## Current Research State

Durable state from current docs and memory:

- BWE v6 archive says the best state is not "final strategy found"; it is "candidate strategy families ready for focused ablation."
- Current focused ablation target is `premium_basis_overheat / long / 30s`.
- Fixed component: entry.
- Mutated component: exit.
- Exit families to compare: `indicator_invalidation`, `breakeven_ratchet`, `state_machine`, `runner_trail`, `fixed_tp_sl`.
- Paper gate should remain closed until focused ablation passes.

Round5 paper-live memory:

- 13 live strategies were tested in paper-shadow/testnet.
- The live runner processed 146 events over about 10.5 hours.
- Testnet result was about `-$89.83`.
- The runner crashed on Binance testnet API failure after reduce-only close problems.
- There was an orphan-position risk pattern: state can be mutated before exchange close confirmation.
- Drift D15 matters: backtests using completed 1m kline close have implicit look-ahead versus true live mark-price execution.

Collector/data direction:

- Recent decision: expand collectors from selected contract pairs to all market contract trading pairs, for all previously collected data types, not just klines.
- Newly added pairs require backfill.
- Delisted pairs must be handled deliberately.

## Operating Rules

For strategy questions:

- Do not answer from intuition.
- Run or inspect data first.
- Compare strategies on the same candidate pool, same exit, and same cost assumptions when possible.
- Use numbers: sum, mean, win rate, p10, stressed median, baseline lift, future-safety pass, concentration, and sample size.

For audits:

- If user asks for Critical/High only, do not pad with medium/low issues.
- Anchor findings to actual files and lines.
- Do not report hypothetical bugs.
- Quote only enough code to prove the issue.

For runtime status:

- Check actual processes, PID files, logs, and state files.
- Treat old reports and memory as leads, not truth.
- If files are missing, say they are missing.

For safety:

- Do not read secrets.
- Do not print credentials.
- Do not call order/cancel endpoints unless explicitly authorized.
- Do not change schedulers or live autotrader config unless requested.

## Obsidian Rule

The BWE root is intended to be an Obsidian vault. The active vault HOME is:

`/Volumes/T9/BWE/00_INDEX.md`

However, current active T9 vault is incomplete compared with the Samsung backup. Codex must not repair Obsidian structure directly. If asked about repair, use the backup as read-only reference and write a proposed repair plan into `BWE_codex`.

## Open Gaps To Keep Visible

- Active T9 `/Volumes/T9/BWE` appears incomplete for round5 source, templates, admin files, and MOCs.
- The complete snapshot exists at `/Volumes/Samsung_BWE/T9_BACKUP_20260502/BWE`.
- Hot runtime is split to `/Volumes/T9_HOT`.
- `BWE_codex` should remain the place where Codex writes summaries, audits, and handoffs.
