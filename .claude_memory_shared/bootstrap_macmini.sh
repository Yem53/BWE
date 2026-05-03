#!/usr/bin/env bash
# Bootstrap Claude Code memory on Mac mini from H: drive shared folder.
# Run once when entering BWE Autoresearch on a new Claude Code install on macOS.
#
# Usage:
#   cd /Volumes/T9/BWE
#   bash .claude_memory_shared/bootstrap_macmini.sh
#
# What it does:
#   1. Resolves the Claude Code project hash for the current cwd
#   2. Creates ~/.claude/projects/<hash>/memory/ if missing
#   3. Copies all .md files from .claude_memory_shared/ into it
#   4. Reports what was synced

set -euo pipefail

SHARED_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SHARED_DIR")"

# Claude Code's project hash: typically the cwd with / replaced and special chars escaped.
# On Mac for /Volumes/T9/BWE: the hash directory is usually "-Volumes-T9-BWE".
CWD_HASH="$(echo "$PROJECT_ROOT" | sed 's|/|-|g')"

CLAUDE_PROJECT_DIR="$HOME/.claude/projects/$CWD_HASH"
CLAUDE_MEMORY_DIR="$CLAUDE_PROJECT_DIR/memory"

echo "[bootstrap] cwd: $PROJECT_ROOT"
echo "[bootstrap] inferred Claude project hash: $CWD_HASH"
echo "[bootstrap] target memory dir: $CLAUDE_MEMORY_DIR"

mkdir -p "$CLAUDE_MEMORY_DIR"

# If target already has files, ask for confirmation before overwriting
if [ -n "$(ls -A "$CLAUDE_MEMORY_DIR" 2>/dev/null)" ]; then
    echo "[bootstrap] WARNING: target already has files:"
    ls "$CLAUDE_MEMORY_DIR"
    read -p "Overwrite with H: drive shared memory? [y/N] " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        echo "[bootstrap] aborted"
        exit 1
    fi
fi

cp -v "$SHARED_DIR"/*.md "$CLAUDE_MEMORY_DIR/"

echo ""
echo "[bootstrap] done. Files synced:"
ls -la "$CLAUDE_MEMORY_DIR"
echo ""
echo "[bootstrap] Going forward, every memory edit must write to BOTH:"
echo "  - $CLAUDE_MEMORY_DIR/<file>.md"
echo "  - $SHARED_DIR/<file>.md"
echo ""
echo "[bootstrap] Also CLAUDE.md at $PROJECT_ROOT/CLAUDE.md is auto-loaded."
