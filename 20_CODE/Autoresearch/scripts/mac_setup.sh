#!/usr/bin/env bash
# Mac mini setup for BWE Autoresearch
# One-time bootstrap when you plug the H: drive into Mac mini.
#
# Prerequisites:
#   - macOS 13+ (Ventura or newer)
#   - Homebrew installed (https://brew.sh)
#   - The "T9" external drive plugged in (so /Volumes/T9 exists)
#
# Usage:
#   cd /Volumes/T9/BWE/20_CODE/Autoresearch
#   bash scripts/mac_setup.sh

set -euo pipefail

echo "============================================================"
echo "BWE Autoresearch — Mac mini setup"
echo "============================================================"

# 1. Verify H: drive (T9) is mounted
if [ ! -d "/Volumes/T9/BWE" ]; then
    echo "ERROR: /Volumes/T9/BWE not found. Is the T9 external drive plugged in?"
    echo "  - Plug the drive in and re-run this script"
    exit 1
fi
BWE_ROOT="/Volumes/T9/BWE"
echo "[1/8] BWE_ROOT = $BWE_ROOT  ✓"

# 2. Verify Python 3.12+
if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 not found. Install via:"
    echo "  brew install python@3.12"
    exit 1
fi
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "[2/8] python3 version = $PY_VER  $([ "$PY_VER" \> "3.10" ] && echo ✓ || echo "(too old, need 3.10+)")"

# 3. Verify claude CLI
if ! command -v claude >/dev/null 2>&1; then
    echo "[3/8] claude CLI not found. Installing via npm..."
    if ! command -v npm >/dev/null 2>&1; then
        echo "ERROR: npm not found. Install via:"
        echo "  brew install node"
        exit 1
    fi
    npm install -g @anthropic-ai/claude-code
    echo "  installed: $(claude --version 2>&1 | head -1)"
else
    echo "[3/8] claude CLI = $(which claude)  ✓"
fi

# 4. Create venv for project
VENV_DIR="$BWE_ROOT/.venv_mac"
if [ ! -d "$VENV_DIR" ]; then
    echo "[4/8] Creating virtualenv at $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
fi
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
echo "[4/8] venv activated: $(which python)"

# 5. Install Python deps (lightweight set for Mac — no GPU needed)
echo "[5/8] Installing Python dependencies..."
pip install --quiet --upgrade pip
pip install --quiet \
    polars \
    pandas \
    pyarrow \
    numpy \
    psutil
# Optional: torch CPU build for paper_shadow_sim / rescore (not needed for Round 4 LLM debate)
# pip install --quiet torch --index-url https://download.pytorch.org/whl/cpu
echo "  done"

# 6. Bootstrap Claude Code memory from H: drive
MEMORY_BOOTSTRAP="$BWE_ROOT/.claude_memory_shared/bootstrap_macmini.sh"
if [ -f "$MEMORY_BOOTSTRAP" ]; then
    echo "[6/8] Bootstrapping Claude Code memory..."
    bash "$MEMORY_BOOTSTRAP" || echo "  (skip — memory bootstrap returned non-zero, may already be set up)"
else
    echo "[6/8] Memory bootstrap script not found, skipping"
fi

# 7. Verify path resolution
echo "[7/8] Verifying bwe_paths.py auto-detection..."
cd "$BWE_ROOT/20_CODE/Autoresearch"
python -c "
import sys
sys.path.insert(0, '.')
from bwe_autoresearch import bwe_paths as P
print('  BWE_ROOT     =', P.BWE_ROOT)
print('  RESULTS_TSV  =', P.RESULTS_TSV, '(exists:', P.RESULTS_TSV.exists(), ')')
print('  REGISTRY     =', P.REGISTRY_JSONL, '(exists:', P.REGISTRY_JSONL.exists(), ')')
print('  KLINE        =', P.KLINE_PARQUET, '(exists:', P.KLINE_PARQUET.exists(), ')')
print('  EVENTS       =', P.EVENTS_PARQUET, '(exists:', P.EVENTS_PARQUET.exists(), ')')
print('  DEBATES_DIR  =', P.DEBATES_DIR, '(exists:', P.DEBATES_DIR.exists(), ')')
"

# 8. Create convenience launch script
LAUNCH_SCRIPT="$BWE_ROOT/20_CODE/Autoresearch/scripts/launch_round_mac.sh"
cat > "$LAUNCH_SCRIPT" <<'EOF'
#!/usr/bin/env bash
# Launch a Round N debate pipeline on Mac mini.
# Usage: bash scripts/launch_round_mac.sh round_4_yaobi_wide_exit
set -euo pipefail
REASON="${1:-round_N_debate}"
BWE_ROOT="/Volumes/T9/BWE"
cd "$BWE_ROOT/20_CODE/Autoresearch"
source "$BWE_ROOT/.venv_mac/bin/activate"
export BWE_ROOT BWE_LLM_EFFORT="${BWE_LLM_EFFORT:-max}" BWE_DEBATE_REASON="$REASON"
echo "[launch_round_mac] starting at $(date)"
echo "  BWE_ROOT=$BWE_ROOT"
echo "  BWE_LLM_EFFORT=$BWE_LLM_EFFORT"
echo "  BWE_DEBATE_REASON=$REASON"
python -u scripts/round3_auto_launcher.py --skip-rescore "$@" 2>&1 | tee "$BWE_ROOT/99_ADMIN/${REASON}.log"
EOF
chmod +x "$LAUNCH_SCRIPT"
echo "[8/8] Launch script created: $LAUNCH_SCRIPT"

echo ""
echo "============================================================"
echo "✓ Setup complete"
echo "============================================================"
echo ""
echo "To launch Round 4 (or any subsequent round):"
echo ""
echo "  cd $BWE_ROOT/20_CODE/Autoresearch"
echo "  source $VENV_DIR/bin/activate"
echo "  bash scripts/launch_round_mac.sh round_4_yaobi_wide_exit"
echo ""
echo "Or for just the LLM debate (no analyze/rescore/merge):"
echo ""
echo "  python -u -m bwe_autoresearch.bwe_loop_llm_team --reason round_4_yaobi_wide_exit --recent-n 50 --deep"
echo ""
echo "Notes:"
echo "  - BWE_LLM_EFFORT defaults to 'max' (extended thinking)"
echo "  - On Mac, claude.exe console issue does NOT exist (macOS doesn't have Windows console concept)"
echo "  - Round 4 ETA with --effort max: ~5-7h"
echo ""
