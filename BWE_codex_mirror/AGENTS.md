# BWE Codex Working Contract

This workspace exists to support the BWE project. Treat `/Volumes/T9/BWE_codex` as Codex's output and context area, and do not scatter Codex-produced reports, handoffs, or working notes into the BWE vault unless the user explicitly asks for a BWE-side edit.

## Write Scope Lock

The user explicitly restricted Codex write permission on 2026-05-02:

- Codex may modify files only under `/Volumes/T9/BWE_codex`.
- Codex has no permission to modify `/Volumes/T9/BWE`.
- Codex has no permission to modify Obsidian vault content, including notes, MOCs, templates, canvas files, `.obsidian` config, or any BWE-side documentation.
- Codex may inspect BWE/Obsidian files read-only and may write observations, audits, proposed patches, or handoffs into `BWE_codex`.
- If a task requires BWE or Obsidian edits, stop and provide a proposed patch/plan under `BWE_codex`; do not apply it.

Start new BWE work by reading:

- `00_CONTEXT/BWE_CODEX_PROJECT_MEMORY.md`
- `00_CONTEXT/WRITE_SCOPE_LOCK.md`
- `30_REPORTS/2026-05-02_obsidian_architecture_audit.md`
- `00_HANDOFF/2026-05-02_codex_bwe_onboarding.md`

Then inspect the BWE project read-only before acting:

- `/Volumes/T9/BWE/CLAUDE.md` is the default BWE action guideline.
- `/Volumes/T9/BWE/00_INDEX.md` is the BWE vault/project entrypoint.
- Browse the relevant BWE folders for the task before making claims or writing a Codex artifact.
- If BWE's `CLAUDE.md` conflicts with the Codex write-scope lock, keep the write-scope lock: do not modify BWE or Obsidian.

Operational rules:

- Verify current local state before making "running/current/complete" claims.
- Strategy and parameter answers must be data-driven: run or inspect real data, then answer with numbers.
- Never read or print secrets, API keys, tokens, or credentials.
- Never call Binance/OKX order endpoints, including testnet, without explicit user authorization for that exact action.
- Never auto-promote a backtest winner to live. Promotion requires paper-shadow evidence plus explicit user confirmation.
- When BWE docs and disk state disagree, report the disagreement and identify the checked path, but do not repair BWE/Obsidian directly.

<claude-mem-context>
# Memory Context

# [BWE_codex] recent context, 2026-05-03 5:38pm EDT

Legend: 🎯session 🔴bugfix 🟣feature 🔄refactor ✅change 🔵discovery ⚖️decision
Format: ID TIME TYPE TITLE
Fetch details: get_observations([IDs]) | Search: mem-search skill

Stats: 50 obs (33,554t read) | 1,521,484t work | 98% savings

### May 3, 2026
516 12:31a ⚖️ Strategy Development Continuation with Archival Requirements
517 12:32a 🔵 Active Paper Trading Runner in Tmux Session
518 " 🔵 Exact Minute-Level Strategy Validation Infrastructure
519 12:37a 🟣 Market-Native Scanner Strategy Search Engine
520 " 🔴 DataFrame Index Preservation in safe_merge_asof
521 " 🔵 Missing NumPy Dependency in Execution Environment
522 12:38a 🔵 System Python Environment Has Required Dependencies
523 12:39a 🔵 Market-Native Search Completed Without Objective-Passing Strategies
524 " ⚖️ Full Production Market-Native Search Launched
525 12:40a 🔵 Production Search Processing 540 Symbols in 36 Batches
526 " 🔵 Entry Probe Phase 28% Complete With 1242 Candidates Found
527 1:08a 🔵 Scanner-native market microstructure search found no strategies passing hard gates
528 " 🔵 Scanner-native market search found zero passing strategies; long_accel failed on asymmetric TP/SL
529 1:09a 🔵 SHORT strategy search space shows clear quality vs. frequency trade-off
530 " 🔵 Selection bias excluded long_washout_bounce despite superior probe results; tp24 exits outperform tp4
531 1:10a 🔵 Exit strategy preferences diverge sharply by SHORT family type
532 1:11a 🔵 Selection algorithm prioritizes monthly_triggers causing systematic exclusion of lower-frequency higher-quality patterns
533 1:12a 🔵 Failed-continuation exit logic captures partial losses before reversal, explaining systematic underperformance
534 3:05a 🔵 Scanner-native research scripts code audit for look-ahead and timing bugs
535 4:46a 🔵 Market-native delayed-entry backtest pipeline audit: no critical look-ahead bugs found
536 4:47a 🔵 Market-native event ranker scoring methodology confirmed safe from threshold overfitting
537 5:59a 🔵 Dense anomaly oracle ceiling audit structure and future-data separation
538 6:00a 🔵 Oracle ceiling audit run scale and memory management
539 6:55a 🔵 Dense anomaly selector scripts security audit completed
540 7:14a 🔵 BWE Codex Dense Anomaly Pipeline Read-Only Audit Completed
541 8:59a 🔵 Codex discovery scripts implement strict train/validation isolation and lookahead prevention
542 9:00a 🔵 Safe timestamp pattern prevents current-bucket lookahead in 5m aggregated metrics
543 9:02a 🔵 Scanner-native all-market search bottleneck: frequency-quality trade-off unresolved across multiple search branches
544 11:39a 🔵 BWE_codex market_native_leaf_selector iteration failed - exploring next scanner-native directions
545 11:40a 🔵 BWE_codex leaf_selector search running with 0 passes, 8 failed branches identified
546 11:41a 🔵 leaf_selector progressed to task 45/198, still 0 passes; best mean=-0.146% vs 8% gate
547 12:21p 🔵 BWE market data inventory and usage audit completed
548 " 🔵 BWE feature registry and unsupported depth/orderbook data gap identified
549 12:23p 🔵 BWE collector runtime state and data coverage gaps discovered
550 12:24p 🔵 BWE collector errors and GPU scanner architecture documented
551 12:43p 🔵 Scanner-native strategy scripts pass all low-level constraint audits
552 12:44p 🔵 Static symbol feature filtering correctly implemented and verified in run metadata
553 12:45p 🔵 Complete static symbol feature lifecycle traced from database query to score filtering
554 1:57p 🔵 BWE_codex session context loaded for new-session handoff
555 1:58p 🔵 Multi-9 paper/demo runner operational state after 13+ hours runtime
556 1:59p 🔵 Round5 paper-LIVE runner stopped at 10:06 AM, not currently running
557 2:46p 🔵 Trading strategies not opening positions, fallback logic triggered instead
558 2:47p 🔵 Zero positions opened: All 9 strategies failed entry conditions despite 662 fallback API calls
559 " 🔵 43 long strategy entries passed all conditions but failed on testnet symbol availability
560 3:00p ⚖️ Offline strict replay script to validate 9-strategy zero-position outcome
561 3:03p 🔵 Strict offline replay confirmed 41 long entries should have opened using DB-only features
562 3:05p 🟣 Implemented strict offline replay script for v6_multi_8 nine-strategy validation
563 3:28p 🔵 Binance demo order placement completely broken - zero successful orders
564 " 🔵 Root cause found: notional_usdt=10 below Binance minNotional=50 requirement
565 5:28p ⚖️ Session recovery protocol via BWE_codex disk-based archives

Access 1521k tokens of past work via get_observations([IDs]) or mem-search skill.
</claude-mem-context>
