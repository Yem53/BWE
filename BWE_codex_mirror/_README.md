# BWE_codex Mirror

This is a **snapshot** of `/Volumes/T9/BWE_codex/` (Mac local path).

The original directory is sibling to BWE (`/Volumes/T9/BWE_codex/`), but for Windows / single-repo distribution we mirror the lightweight content here.

**Excluded** from mirror:
- `codex_discovery/` (11 GB research output, regenerable)
- `paper_test/v6_multi_8/runtime/` (live state, machine-specific)
- `*.sqlite3` (DB files)
- `*.log` (logs)
- `_backup_*/`, `__pycache__/`

**On Windows**:
- Clone the BWE repo → `BWE_codex_mirror/` is here
- Optionally rename / move to `D:\BWE_codex` if you want the same `/Volumes/T9/BWE_codex` parity
- `runtime/` will be regenerated when codex paper runs

To keep this mirror in sync from Mac:
```bash
rsync -a --exclude codex_discovery --exclude '*.sqlite3' --exclude '*.log' \
    /Volumes/T9/BWE_codex/ /Volumes/T9/BWE/BWE_codex_mirror/
```
