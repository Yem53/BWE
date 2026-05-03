# BWE Autoresearch — Migration to Mac mini

Done on 2026-04-27 to escape Windows console-window flashing for `claude -p` subprocess calls. Mac mini becomes the canonical workstation; 5090 reserved for occasional GPU loop runs only.

## Why we migrated

- Windows spawns visible console windows for every `claude -p` subprocess call,
  even with all known suppression flags (`CREATE_NO_WINDOW`, `STARTUPINFO/SW_HIDE`,
  direct `claude.exe` invocation). Round 4 with `--effort max` would have flashed
  ~5-7h continuously.
- Mac mini's macOS doesn't have the Windows console-window concept at all → 100% silent.
- Mac mini is also the user's primary machine where the live trading bot, BWE
  Telegram listener, and Claude Code primary session already live.

## What changed in the codebase

### New: centralized path module

`bwe_autoresearch/bwe_paths.py` — auto-detects `BWE_ROOT` via:
1. `BWE_ROOT` env var (explicit override)
2. Walking up from this file's location
3. Common locations: `/Volumes/T9/BWE` (Mac), `H:/BWE` (Windows), `/mnt/t9/BWE` (Linux/WSL)
4. Fallback: `H:/BWE`

All scripts that used hardcoded `Path("H:/BWE/...")` now import from `bwe_paths`.

### Refactored files (use `bwe_paths` instead of hardcoded Windows paths)

```
bwe_autoresearch/
  bwe_loop.py
  bwe_loop_data_loader.py
  bwe_loop_llm_team.py
  bwe_loop_monitor.py
  coverage_map_gen.py
  hypothesis_registry_seed.py

scripts/
  analyze_results.py
  merge_accepted_archetypes.py
  morning_brief_zh.py
  paper_shadow_sim.py
  promote_to_paper.py
  rescore_with_v2.py
  round3_auto_launcher.py
```

### Cross-platform launcher

`scripts/round3_auto_launcher.py`:
- `BWE_PYTHON` env var no longer needed — auto-detects via `sys.executable` on Mac/Linux
- `PYTHONUSERBASE=H:\py312-userbase` only set on Windows
- All hardcoded paths use `bwe_paths`

### Subprocess silence patches (Windows-only, harmless on Mac)

The `bwe_loop_llm_team.py:call_claude` adds:
- `creationflags=CREATE_NO_WINDOW` on Windows
- `STARTUPINFO/SW_HIDE` on Windows
- Prefers direct `claude.exe` from `node_modules/@anthropic-ai/claude-code/bin/`

These are no-ops on Mac (`sys.platform != "win32"` guards skip them).

## Mac mini setup steps

### 1. Plug in the T9 external drive

Confirm `/Volumes/T9/BWE` exists.

### 2. Run the setup script

```bash
cd /Volumes/T9/BWE/20_CODE/Autoresearch
bash scripts/mac_setup.sh
```

This:
- Creates `/Volumes/T9/BWE/.venv_mac/`
- Installs `polars pandas pyarrow numpy psutil` into it
- Installs `claude` CLI globally via npm if missing
- Bootstraps Claude Code memory from `/Volumes/T9/BWE/.claude_memory_shared/`
- Verifies `bwe_paths.py` resolves to the right BWE_ROOT
- Creates `scripts/launch_round_mac.sh` convenience wrapper

### 3. Open Claude Code at `/Volumes/T9/BWE`

The `H:/BWE/CLAUDE.md` file (which is at `/Volumes/T9/BWE/CLAUDE.md` on Mac) auto-loads
all project context. The `.claude_memory_shared/` provides per-conversation auto-memory.

### 4. Launch Round 4

```bash
cd /Volumes/T9/BWE/20_CODE/Autoresearch
bash scripts/launch_round_mac.sh round_4_yaobi_wide_exit
```

This kicks off the same pipeline (`analyze → debate → merge → paper_sim → 中文 brief`)
that Windows ran, but completely silently on Mac.

ETA with `--effort max`: ~5-7h. Run it before bed; check `morning_brief_latest.md` in the morning.

## What's still on the 5090

Nothing critical. The `H:/py312-userbase` directory has the Windows torch+CUDA install,
which is only needed for the GPU loop (the 20K-combo backtest). After this migration,
plug H: into 5090 only for those runs.

## Files unique to 5090 (don't break Mac)

- `H:\py312-userbase\` (2.87 GB torch+CUDA Windows binaries) — leave on 5090, not on H:
- `CLAUDE_CODE_GIT_BASH_PATH` env var (Git Bash on Windows) — Mac uses native bash

## Rollback

If anything is wrong on Mac, set explicit override:

```bash
export BWE_ROOT=/Volumes/T9/BWE
```

If a script still has a hardcoded path I missed, search and replace:

```bash
cd /Volumes/T9/BWE/20_CODE/Autoresearch
grep -rn "H:/BWE\|H:\\\\BWE" --include="*.py"
```

## Test before committing trust to Mac

After running `mac_setup.sh`, smoke-test with:

```bash
python -m bwe_autoresearch.bwe_paths
# Should print BWE_ROOT = /Volumes/T9/BWE plus path existence checks

python -c "from bwe_autoresearch.bwe_loop_llm_team import CLAUDE_BIN; print(CLAUDE_BIN)"
# Should print the Mac claude path (e.g. /usr/local/bin/claude or /opt/homebrew/bin/claude)
```

If both succeed, you're good to launch Round 4.
