# BWE — Binance Whale Event Trading Research

> **🪟 Setting up on Windows / new machine?** Read [`infrastructure/windows-setup/SETUP_PROMPT.md`](infrastructure/windows-setup/SETUP_PROMPT.md) first. Paste it as your first message to Claude Code on the new machine — it bootstraps everything.

> **🛠 Infrastructure overview**: [`infrastructure/README.md`](infrastructure/README.md) — what runs where, geographic constraints (US block on binance fstream), how OKX+Bybit fill the gap.

> **⚙️ Project rules / guardrails**: [`CLAUDE.md`](CLAUDE.md) — the BWE project's working contract.

---

# BWE v6 Research Archive

This folder is the curated working archive for the BWE Complete Strategy AutoResearch v6 project.

It is organized as a read-first project entrypoint. Source workspaces were copied here without deleting or moving the original locations.

## Folder Map

| Folder | Purpose |
|---|---|
| `00_PROJECT_REQUIREMENTS` | Project scope, docs, configs, prompts, manifests, runbooks, and root index files. |
| `20_CODE` | Current AutoResearch code copy. The Python virtualenv and cache files are excluded. |
| `30_DATA` | Input data, reference packages, legacy cache, and normalized cache artifacts. |
| `40_EXPERIMENTS` | Full run archive copied from the v6 runs directory. |
| `50_ANALYSIS_REPORTS` | Curated AutoResearch Round 1 analysis outputs. |
| `60_NEXT_ROUND` | Focused ablation config for the next research round. |
| `90_SOURCE_POINTERS` | JSON pointers back to the original source locations. |
| `99_ADMIN` | Copy logs, file inventory, and folder size summary. |

## Key Reports

- Long-form final verdict: `50_ANALYSIS_REPORTS\longform_round1\final\final_verdict_zh.md`
- Long-form next-round config: `60_NEXT_ROUND\focused_ablation\next_ablation_config_longform.yaml`
- AutoResearch hypothesis ledger: `50_ANALYSIS_REPORTS\autoresearch_expanded_round1\hypothesis_ledger.jsonl`
- Entry catalog: `50_ANALYSIS_REPORTS\autoresearch_expanded_round1\entry_catalog_scoreboard.csv`
- Exit catalog: `50_ANALYSIS_REPORTS\autoresearch_expanded_round1\exit_catalog_scoreboard.csv`
- Complete entry/exit funnel: `50_ANALYSIS_REPORTS\autoresearch_expanded_round1\entry_exit_combined_funnel.csv`

## Current Research State

- Main completed run: GPU fused strong max-alpha.
- Search target recorded: 500B candidate-space sample.
- Actual staged evaluation: 100M coarse, 5M medium, 200K deep, 20K stress.
- Current recommendation: run focused ablation before paper-shadow.
- First next-round hypothesis: `premium_basis_overheat / long / 30s`, fixed entry with exit-family swap.

## Safety Boundary

This archive is for sandbox / paper research only.

- No production orders.
- No credential reads.
- No notifications.
- No scheduler changes.
- No live autotrader edits.

Original source pointers are recorded in `90_SOURCE_POINTERS\source_paths.json`.
