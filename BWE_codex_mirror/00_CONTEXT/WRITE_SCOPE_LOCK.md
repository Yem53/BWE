# Codex Write Scope Lock

Created: 2026-05-02

The user explicitly restricted Codex write permissions:

> Codex has no right to modify BWE files or Obsidian content. Codex may only modify files in BWE_codex.

## Allowed

- Read `/Volumes/T9/BWE` for inspection.
- Read Obsidian vault files for architecture or content understanding.
- Read `/Volumes/T9_HOT` for runtime verification.
- Read `/Volumes/Samsung_BWE/T9_BACKUP_20260502/BWE` as a backup/reference source.
- Write reports, handoffs, context notes, proposed patches, and audit results under `/Volumes/T9/BWE_codex`.

## Forbidden

- Modify any file under `/Volumes/T9/BWE`.
- Modify Obsidian notes, MOCs, templates, canvas files, or `.obsidian` config.
- Repair vault links directly.
- Copy missing templates/MOCs into BWE directly.
- Update BWE source code directly.
- Update BWE runtime config directly.

## Required Behavior

If the user asks for work that would normally require BWE or Obsidian edits:

1. Inspect the relevant files read-only.
2. Write a proposed patch, migration plan, or exact command recipe under `/Volumes/T9/BWE_codex`.
3. State clearly that no BWE/Obsidian files were modified.

For every future BWE task, Codex should first inspect `/Volumes/T9/BWE/CLAUDE.md` and relevant BWE project files read-only, then use those as action guidelines while preserving this write-scope lock.
