# Codex BWE Onboarding Handoff

Date: 2026-05-02

## What Codex Is Here For

Codex is the BWE auxiliary operator/reviewer/writer. Outputs should go to:

`/Volumes/T9/BWE_codex`

The main BWE project is:

`/Volumes/T9/BWE`

But current source completeness must be checked before use because the mounted T9 copy is missing several files that exist in the Samsung backup.

## User Objective

Use BWE Telegram events plus Binance K-line and related futures data to search for the best entry plus exit strategy combinations through a Karpathy-style AutoResearch loop, using 5090 compute where appropriate.

## Read First

1. `00_CONTEXT/BWE_CODEX_PROJECT_MEMORY.md`
2. `00_CONTEXT/WRITE_SCOPE_LOCK.md`
3. `30_REPORTS/2026-05-02_obsidian_architecture_audit.md`
4. BWE action guideline, read-only: `/Volumes/T9/BWE/CLAUDE.md`
5. Active BWE vault home, read-only: `/Volumes/T9/BWE/00_INDEX.md`
6. Backup active plan if needed, read-only: `/Volumes/Samsung_BWE/T9_BACKUP_20260502/BWE/99_ADMIN/day1_active_plan.md`

## Path Rules

- Write Codex reports/handoffs/context to `/Volumes/T9/BWE_codex`.
- Inspect active vault docs at `/Volumes/T9/BWE` read-only.
- Inspect hot runtime data at `/Volumes/T9_HOT`.
- Use `/Volumes/Samsung_BWE/T9_BACKUP_20260502/BWE` read-only when active T9 lacks expected code/docs.
- Do not modify `/Volumes/T9/BWE`, Obsidian notes, MOCs, templates, canvas files, or `.obsidian` config.
- If a requested action would require modifying BWE or Obsidian, write the proposed patch/plan under `BWE_codex` instead.

## Current Important Facts

- Active T9 vault is incomplete relative to the Samsung backup.
- Round5 paper-live validation previously crashed after about 10.5 hours and showed about `-$89.83` testnet PnL.
- D15 look-ahead drift remains central: kline close backtests are not equivalent to true live mark-price entry.
- Current research recommendation is focused ablation before paper-shadow, especially `premium_basis_overheat / long / 30s` with exit-family swaps.
- Collector scope was recently expanded in memory to all market contract trading pairs, not only selected pairs.

## Non-Negotiables

- No secret reads.
- No live/autotrader edits unless explicitly requested.
- No Binance/OKX order endpoint calls unless explicitly authorized for that action.
- No strategy claims without data.
- No "current/running/complete" claims without live path verification.
- No BWE/Obsidian writes; `BWE_codex` is the only writable project area for Codex.
