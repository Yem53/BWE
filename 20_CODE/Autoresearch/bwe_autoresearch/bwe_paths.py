"""Centralized path resolution for BWE Autoresearch.

Single source of truth for all hardcoded paths in the project. Resolves
the project root via (in priority order):

  1. `BWE_ROOT` environment variable (explicit override)
  2. Walking up from this file (when imported from inside the repo)
  3. Common locations: /Volumes/T9/BWE (Mac), H:/BWE (Windows)
  4. Falls back to "H:/BWE" (legacy default)

This lets the same code run on:
  - Windows 5090 (H: drive)            → BWE_ROOT=H:/BWE
  - Mac mini  (T9 external drive)      → BWE_ROOT=/Volumes/T9/BWE
  - Any other machine where H: drive is mounted differently

Usage:
    from bwe_autoresearch.bwe_paths import BWE_ROOT, RESULTS_TSV, DEBATES_DIR
    # all paths are pathlib.Path instances
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _autodetect_root() -> Path:
    # 1. Explicit env var
    env_root = os.environ.get("BWE_ROOT")
    if env_root:
        p = Path(env_root)
        if p.exists():
            return p

    # 2. Walk up from this file: bwe_paths.py is at <BWE_ROOT>/20_CODE/Autoresearch/bwe_autoresearch/
    here = Path(__file__).resolve()
    for ancestor in [here.parent, here.parent.parent, here.parent.parent.parent, here.parent.parent.parent.parent]:
        if (ancestor / "20_CODE").exists() and (ancestor / "40_EXPERIMENTS").exists():
            return ancestor

    # 3. Common machine-specific locations
    candidates = [
        Path("/Volumes/T9/BWE"),       # Mac mini with T9 external drive
        Path("H:/BWE"),                 # Windows 5090 with H: external drive
        Path("/mnt/t9/BWE"),            # WSL / Linux mount
    ]
    for c in candidates:
        if c.exists() and (c / "20_CODE").exists():
            return c

    # 4. Last-resort fallback (preserve legacy Windows-only behavior)
    return Path("H:/BWE")


BWE_ROOT: Path = _autodetect_root()

# Top-level subdirs
PROJECT_REQUIREMENTS_DIR: Path = BWE_ROOT / "00_PROJECT_REQUIREMENTS"
CODE_DIR: Path             = BWE_ROOT / "20_CODE"
DATA_DIR: Path             = BWE_ROOT / "30_DATA"
EXPERIMENTS_DIR: Path      = BWE_ROOT / "40_EXPERIMENTS"
ANALYSIS_REPORTS_DIR: Path = BWE_ROOT / "50_ANALYSIS_REPORTS"
NEXT_ROUND_DIR: Path       = BWE_ROOT / "60_NEXT_ROUND"
SOURCE_POINTERS_DIR: Path  = BWE_ROOT / "90_SOURCE_POINTERS"
ADMIN_DIR: Path            = BWE_ROOT / "99_ADMIN"

# Code subdirs
AUTORESEARCH_DIR: Path = CODE_DIR / "Autoresearch"
PROMPTS_DIR: Path      = AUTORESEARCH_DIR / "prompts"
SCRIPTS_DIR: Path      = AUTORESEARCH_DIR / "scripts"

# Experiment subdirs
ANALYSIS_DIR: Path        = EXPERIMENTS_DIR / "analysis"
DEBATES_DIR: Path         = EXPERIMENTS_DIR / "debates"
PAPER_DIR: Path           = EXPERIMENTS_DIR / "paper_shadow"
PAPER_CANDIDATES_DIR: Path = EXPERIMENTS_DIR / "paper_candidates"
ARCHIVE_DIR: Path         = EXPERIMENTS_DIR / "all_runs_archive"
REGISTRY_BACKUPS_DIR: Path = EXPERIMENTS_DIR / "registry_backups"

# Specific files
# Note: results.tsv lives at the Karpathy autoresearch repo root, not in EXPERIMENTS_DIR
RESULTS_TSV: Path     = AUTORESEARCH_DIR / "results.tsv"
REGISTRY_JSONL: Path  = EXPERIMENTS_DIR / "hypothesis_registry.jsonl"
COMBO_CURSOR: Path    = EXPERIMENTS_DIR / "combo_cursor.json"
COVERAGE_HTML: Path   = EXPERIMENTS_DIR / "coverage_map.html"
MORNING_BRIEF_LATEST: Path = EXPERIMENTS_DIR / "morning_brief_latest.md"

# Data subdirs
DATA_INPUT_DIR: Path     = DATA_DIR / "input"
DATA_REFERENCE_DIR: Path = DATA_DIR / "reference"
DATA_CACHE_DIR: Path     = DATA_DIR / "cache"
DATA_NORMALIZED_DIR: Path = DATA_CACHE_DIR / "normalized"

# Common data files
_KLINE_FILE = os.environ.get("BWE_KLINE_PARQUET_FILE", "trade_kline_1m_event_windows.parquet")
KLINE_PARQUET: Path  = DATA_NORMALIZED_DIR / _KLINE_FILE
EVENTS_PARQUET: Path = DATA_INPUT_DIR / "binance_event_features_20260425_30d" / "bwe_events_recent_binance_features.parquet"
LEGACY_MARKET_CACHE: Path = DATA_REFERENCE_DIR / "legacy_market_cache"

# Admin / pipeline
LOOP_PID_FILE: Path  = ADMIN_DIR / "loop_run.pid"
PIPELINE_LOG: Path   = ADMIN_DIR / "round3_pipeline.log"
DAY1_PLAN: Path      = ADMIN_DIR / "day1_active_plan.md"

# Memory mirror (for cross-machine sync)
CLAUDE_MEMORY_SHARED: Path = BWE_ROOT / ".claude_memory_shared"


def is_mac() -> bool:
    return sys.platform == "darwin"


def is_windows() -> bool:
    return sys.platform == "win32"


def info() -> str:
    """Render a short summary for debugging path resolution."""
    return (
        f"BWE_ROOT = {BWE_ROOT} (exists={BWE_ROOT.exists()})\n"
        f"  platform = {sys.platform}\n"
        f"  EXPERIMENTS_DIR = {EXPERIMENTS_DIR}\n"
        f"  DATA_DIR = {DATA_DIR}\n"
        f"  KLINE_PARQUET exists = {KLINE_PARQUET.exists()}\n"
        f"  EVENTS_PARQUET exists = {EVENTS_PARQUET.exists()}\n"
    )


if __name__ == "__main__":
    print(info())
