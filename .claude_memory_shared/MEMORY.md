# Memory index

## ⭐ MUST READ FIRST FOR BWE PROJECT
- **[BWE Project Design Rules](BWE_PROJECT_DESIGN_RULES.md)** — 10 core principles + 9 historical mistakes + workflow templates. Read this BEFORE doing any BWE work to avoid repeating known low-level errors.

## User & feedback
- [BWE working directory](feedback_bwe_workdir.md) — H:\BWE is the active project root
- [Max out Claude calls](feedback_max_out_claude_calls.md) — `--effort max` + 1M context for all subprocess calls; user has Max plan headroom
- [Memory must mirror to H drive](feedback_memory_must_mirror_to_h_drive.md) — every memory write goes to both ~/.claude AND H:\BWE\.claude_memory_shared\ for portability
- [妖币 strategy: wide TP + dynamic exit + wider SL](feedback_yaobi_strategy_wide_tp_dynamic_exit.md) — small-cap volatile coins, TP up to 5-15%, dynamic trailing, SL not too conservative
- [Mac mini is primary, 5090 is GPU-only](feedback_macmini_primary_5090_compute_only.md) — 2026-04-27 migration, Mac mini handles all LLM/orchestration; 5090 only for GPU loop runs

## Project: BWE Autoresearch
- [Real purpose](project_bwe_real_purpose.md) — find optimal entry × exit on Binance via BWE telegram + 5090 GPU; $1000 cap, 5-10% sizing
- [Active plan](project_bwe_active_plan.md) — current research roadmap (start at H:/BWE/99_ADMIN/day1_active_plan.md)
- [Overview](project_bwe_overview.md) — system architecture summary
- [Safety rules](project_bwe_safety_rules.md) — sandbox-only, no live trading

## Reference
- [BWE paths](reference_bwe_paths.md) — key dirs: 20_CODE, 40_EXPERIMENTS, 99_ADMIN

## Round 5 Layer A (2026-04-30) — most recent
- [Round 5 Layer A v2 final results](project_round5_layer_a_v2_results.md) — 3 winners (ST15/EP11 真 winner, ST9/EP13 + ST9/EP11 sparse-but-strong), 5,548 实验 / 9 min Mac, 8 bugs 修复, 代码栈 ~30 commits, 下一步 A+B+D 深挖

## Round 6 audit (2026-04-30) — needs brainstorm
- [Round 6 audit findings](project_round6_audit_findings.md) — User caught a structural bug: I treated BWE messages as data source, should be attention pointers + live binance fetch. Parser drops 47% of pricechange-pump events. 11 of 14 channels ignored (incl. binance/upbit listing alerts). Need full architecture rebuild in Round 6.
- Paper-shadow on PID 14005 continues running on v2/v3 (validates within constrained view).
- Spec at: /Volumes/T9/BWE/40_EXPERIMENTS/round5/specs/2026-04-30-round6-architecture-audit.md

## V4 search archive (2026-04-30) — exit + entry 40-round iterative search
- [V4 exit archive](project_v4_exit_search_archive.md) — 4 best exits (EP_AGGRESSIVE/BALANCED/SAFE/SAFEST), winner: 60min ATR×10 + extr lock 35→18 @ +12% (sum +1783, cap 34%)
- [V4 entry archive](project_v4_entry_search_archive.md) — best entry: 3-13% pricechange-pump + top_LS>0.9 + funding>0 (n=525/30d, sum +4177, win 74%, cap 63%)
- [V5 search prompt](project_v5_search_prompt.md) — tomorrow's true 40-round search with 30 distinct mechanisms + Phase 4 deep search
- Honest finding: phase 2-4 of v4 had partial parameter sweeps, not all new mechanisms. v5 will redo with strict "new mechanism per round" rule.

## Obsidian Vault (2026-05-02)
- [Vault HOME](00_INDEX.md) — 入口 + Quick Links
- [Vault Usage Guide](VAULT_USAGE.md) — 使用说明 + 6 大提升
- [CLAUDE.md (with vault sync rule)](CLAUDE.md) — 项目级指令
- 9 MOCs in 00-99 directories
- 5 Templates in /Templates/
- .obsidian/ configured (templates, daily-notes, hotkeys, graph)

## Vault Audit (2026-05-02)
- 578 .md files, **100% linked, 0 orphans, 0 broken**
- 68 folder indexes (auto-generated for every dir with 2+ .md)
- 8 MOCs (00_INDEX + 7 region MOCs)
- 6 templates (Daily / Strategy / Drift / Plan / Experiment + folder index)
- Knowledge graph navigable via Cmd+G in Obsidian
