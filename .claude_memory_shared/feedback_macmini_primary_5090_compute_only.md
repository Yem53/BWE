---
name: Mac mini is primary, 5090 is GPU-only on-demand compute
description: As of 2026-04-27, all BWE Autoresearch operations move to Mac mini; 5090 is reserved for occasional GPU loop runs only
type: feedback
---

## Decision

User migrated all BWE Autoresearch from Windows 5090 to Mac mini on 2026-04-27.

**Reason:** Windows console-window flashing on every `claude -p` subprocess call could not be fully suppressed even with all known patches (CREATE_NO_WINDOW + STARTUPINFO/SW_HIDE + direct claude.exe). Mac mini's macOS has no equivalent console-window concept → 100% silent for LLM debate work.

User's exact words (2026-04-27):
> "现在把所有东西全部准备迁移到macmini上"

## Architecture going forward

```
Mac mini (24/7 primary)              5090 Windows (GPU on-demand)
─────────────────────                ──────────────────────────────
- BWE Telegram monitoring            - 20K-class backtest loops
- Live trading bot                   - GPU first-touch scoring
- Claude Code primary editing        - (only when explicitly needed)
- Round N LLM debates                - Plug H: in for the run, then unplug
- analyze / merge / paper_sim
- 中文 morning_brief
- All pipeline orchestration

H: drive (T9, 4TB exFAT) is plugged into Mac mini by default.
Move it to 5090 only for the GPU loop event (probably <1× per week after Round 4-5 stabilize).
```

## What's been refactored to support cross-platform (2026-04-27)

- **`bwe_autoresearch/bwe_paths.py`** (NEW) — single path-resolution module
- All hardcoded `Path("H:/BWE/...")` replaced with imports from bwe_paths in 14 files
- `round3_auto_launcher.py` auto-detects Python (`sys.executable`) and skips `PYTHONUSERBASE` on Mac
- Windows-only flags (`CREATE_NO_WINDOW`, `STARTUPINFO`, `CLAUDE_CODE_GIT_BASH_PATH`) gated by `sys.platform == "win32"` so they no-op on Mac
- `scripts/mac_setup.sh` creates `.venv_mac/`, installs deps, bootstraps memory

## Path resolution

`bwe_paths.BWE_ROOT` resolves in priority order:
1. `BWE_ROOT` env var
2. Walking up from `bwe_paths.py` location
3. Auto-detect: `/Volumes/T9/BWE`, `H:/BWE`, `/mnt/t9/BWE`
4. Fallback: `H:/BWE`

On Mac it'll find `/Volumes/T9/BWE`. On Windows `H:/BWE`. No env var needed for the common case.

## Setup steps for new Claude Code session on Mac

1. Plug in T9 external drive (gives `/Volumes/T9/BWE`)
2. Open Claude Code with cwd = `/Volumes/T9/BWE`
3. Run one-time bootstrap: `bash /Volumes/T9/BWE/.claude_memory_shared/bootstrap_macmini.sh`
4. Run setup: `bash /Volumes/T9/BWE/20_CODE/Autoresearch/scripts/mac_setup.sh`
5. CLAUDE.md auto-loads project context

## How to apply

- When user is on Mac mini, prefer Mac-native commands; never reach for `H:\\` paths
- The python interpreter to use on Mac is `python` from `.venv_mac/` (not `python3` directly, to ensure project deps are loaded)
- For any GPU work (loop runs), instruct user to physically move H: to 5090 first
- LLM debate / analysis / paper_sim / merge → all run fine on Mac with no GPU
- If a script still has a hardcoded H:/ path I missed, the script will raise FileNotFoundError on Mac — patch it to use bwe_paths
