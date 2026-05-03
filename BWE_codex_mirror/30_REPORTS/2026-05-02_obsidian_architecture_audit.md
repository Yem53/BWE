# BWE Obsidian Architecture Audit

Checked: 2026-05-02

## Verdict

`/Volumes/T9/BWE` is configured as an Obsidian vault, but the currently mounted T9 copy is not self-complete. The complete vault structure exists in the Samsung backup snapshot:

`/Volumes/Samsung_BWE/T9_BACKUP_20260502/BWE`

Do not assume the active T9 vault has all code/docs just because `00_INDEX.md` links to them.

## Active T9 Vault

Vault root:

`/Volumes/T9/BWE`

Obsidian config directory:

`/Volumes/T9/BWE/.obsidian`

Current config files present:

- `app.json`
- `appearance.json`
- `core-plugins.json`
- `daily-notes.json`
- `graph.json`
- `hotkeys.json`
- `templates.json`
- `workspace.json`

Important config values:

- Templates folder: `Templates`
- Daily notes folder: `99_ADMIN/daily`
- Daily note format: `YYYY-MM-DD`
- Graph view has orphans enabled.
- Core plugins enabled include file explorer, search, switcher, graph, backlink, canvas, outgoing links, tag pane, properties, daily notes, templates, command palette, outline, word count, file recovery, sync, and bases.

## Intended Vault Layout

The HOME file is:

`/Volumes/T9/BWE/00_INDEX.md`

The intended top-level map has nine areas:

- `00_PROJECT_REQUIREMENTS`
- `20_CODE`
- `30_DATA`
- `40_EXPERIMENTS`
- `50_ANALYSIS_REPORTS`
- `60_NEXT_ROUND`
- `90_SOURCE_POINTERS`
- `99_ADMIN`
- `.claude_memory_shared`

The vault guide says agents should maintain MOCs, templates, wikilinks, backlinks, tags, and daily notes.

## Current Active T9 Gaps

Files checked on active T9 show these mismatches:

- `Templates/` exists but is empty.
- Only these MOC files exist on active T9:
  - `00_PROJECT_REQUIREMENTS/00_PROJECT_REQUIREMENTS_MOC.md`
  - `20_CODE/20_CODE_MOC.md`
  - `30_DATA/30_DATA_MOC.md`
- These expected MOCs are missing from active T9:
  - `40_EXPERIMENTS/40_EXPERIMENTS_MOC.md`
  - `50_ANALYSIS_REPORTS/50_ANALYSIS_REPORTS_MOC.md`
  - `60_NEXT_ROUND/60_NEXT_ROUND_MOC.md`
  - `90_SOURCE_POINTERS/90_SOURCE_POINTERS_MOC.md`
  - `99_ADMIN/99_ADMIN_MOC.md`
- `99_ADMIN/day1_active_plan.md` is missing from active T9.
- `未命名.canvas` is `{}`.
- `40_EXPERIMENTS/round5/src` has directories but not the expected Python source files.
- `40_EXPERIMENTS/round4` and `40_EXPERIMENTS/paper_shadow` are effectively empty in the active T9 copy.

This means the active T9 Obsidian graph will show broken links or unresolved references for important project areas.

## Complete Backup Reference

The Samsung backup contains the expected missing pieces:

`/Volumes/Samsung_BWE/T9_BACKUP_20260502/BWE`

Verified in backup:

- Full template set:
  - `Templates/Daily_Note_Template.md`
  - `Templates/Drift_Template.md`
  - `Templates/Experiment_Template.md`
  - `Templates/Plan_Template.md`
  - `Templates/Strategy_Template.md`
  - `Templates/_FOLDER_INDEX.md`
- Full top-level MOC set:
  - `00_PROJECT_REQUIREMENTS/00_PROJECT_REQUIREMENTS_MOC.md`
  - `20_CODE/20_CODE_MOC.md`
  - `30_DATA/30_DATA_MOC.md`
  - `40_EXPERIMENTS/40_EXPERIMENTS_MOC.md`
  - `50_ANALYSIS_REPORTS/50_ANALYSIS_REPORTS_MOC.md`
  - `60_NEXT_ROUND/60_NEXT_ROUND_MOC.md`
  - `90_SOURCE_POINTERS/90_SOURCE_POINTERS_MOC.md`
  - `99_ADMIN/99_ADMIN_MOC.md`
- `99_ADMIN/day1_active_plan.md`
- `99_ADMIN/day2_status_report.md`
- Full round5 files including:
  - `40_EXPERIMENTS/round5/src/paper_shadow_live.py`
  - `40_EXPERIMENTS/round5/paper_shadow/runtime_live/state.json`
  - `40_EXPERIMENTS/round5/specs/PAPER_BACKTEST_DRIFT_LOG.md`

Backup sizes observed:

- `30_DATA`: about 45G
- `40_EXPERIMENTS`: about 10G
- `20_CODE`: about 1.9G
- `99_ADMIN`: about 32M

## Recommended Repair Plan

Do not repair automatically without user confirmation, because this is cross-volume project state.

Recommended sequence:

1. Confirm whether `/Volumes/T9/BWE` or `/Volumes/Samsung_BWE/T9_BACKUP_20260502/BWE` should be treated as the canonical current vault.
2. If T9 should be restored, copy missing low-risk Obsidian structure first:
   - top-level MOCs
   - `Templates/`
   - `99_ADMIN/99_ADMIN_MOC.md`
3. Then reconcile larger content:
   - `40_EXPERIMENTS/round5`
   - `40_EXPERIMENTS/round4`
   - `99_ADMIN/day1_active_plan.md` and status reports
4. Keep hot runtime separate:
   - `/Volumes/T9_HOT/binance_collectors_runtime`
   - `/Volumes/T9_HOT/bwe_logs`
   - `/Volumes/T9_HOT/paper_shadow_runtime_live`
5. Reopen Obsidian and test:
   - `00_INDEX.md`
   - backlinks
   - graph view
   - template insertion
   - daily note creation

## Codex Working Consequence

Until the vault is repaired, Codex should write new summaries and handoffs under:

`/Volumes/T9/BWE_codex`

When inspecting source truth, Codex should explicitly name the checked path and not silently blend active T9, hot runtime, and Samsung backup.

