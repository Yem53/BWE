"""Round 4 reset — backup R3 state, reset cursor + best_score for R4 fresh start.

Run on 5090 (Windows) BEFORE launching R4 main loop. Mac side already
prepared:
  - hypothesis_registry.jsonl now has E300-E339 + X300-X319 R4 archetypes
  - bwe_loop.py variant grid widened to wide-TP / log-spaced
  - paper_shadow_sim.py cross-family lookup fix
  - TEAM_PHILOSOPHY.md 妖币 regime upgrade

R3 artifacts kept as snapshot in registry_backups + EXPERIMENTS_DIR.

Usage on 5090:
    cd H:\\BWE\\20_CODE\\Autoresearch
    python scripts/round4_reset.py            # dry-run, prints what would change
    python scripts/round4_reset.py --execute  # actually perform the reset

This is destructive (resets results.tsv, cursor, best_score). Always run dry-run first.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

# Allow running as `python scripts/round4_reset.py` from any cwd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bwe_autoresearch.bwe_paths import (
    AUTORESEARCH_DIR,
    EXPERIMENTS_DIR,
    REGISTRY_BACKUPS_DIR,
)


TSV_HEADER = "commit\tval_score\ttriggers\tstatus\tdescription\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true",
                    help="Actually perform the reset (default: dry-run)")
    args = ap.parse_args()

    results_tsv = AUTORESEARCH_DIR / "results.tsv"
    best_score_json = AUTORESEARCH_DIR / "best_score.json"
    cursor_json = EXPERIMENTS_DIR / "combo_cursor.json"
    ts = time.strftime("%Y%m%d_%H%M%S")

    print(f"=== Round 4 reset (dry-run={'no' if args.execute else 'YES'}) ===\n")

    # 1. Backup current results.tsv → registry_backups/results_round3_<ts>.tsv
    if results_tsv.exists():
        backup_results = REGISTRY_BACKUPS_DIR / f"results_round3_{ts}.tsv"
        n_lines = sum(1 for _ in results_tsv.open(encoding="utf-8"))
        print(f"[1] backup results.tsv ({n_lines} lines) → {backup_results}")
        if args.execute:
            shutil.copy2(results_tsv, backup_results)
    else:
        print(f"[1] results.tsv missing — nothing to backup")

    # 2. Reset results.tsv to empty (header only)
    print(f"[2] reset {results_tsv} to header only")
    if args.execute:
        results_tsv.write_text(TSV_HEADER, encoding="utf-8")

    # 3. Reset cursor → 0
    cur = json.loads(cursor_json.read_text())["cursor"] if cursor_json.exists() else None
    print(f"[3] reset cursor: was {cur} → 0")
    if args.execute:
        cursor_json.write_text(json.dumps({"cursor": 0}, indent=2))

    # 4. Reset best_score → -inf (json: null sentinel; bwe_loop_results._read_best
    #    returns -inf on missing file)
    if best_score_json.exists():
        prev = best_score_json.read_text()
        backup_best = REGISTRY_BACKUPS_DIR / f"best_score_round3_{ts}.json"
        print(f"[4] backup best_score: {prev.strip()} → {backup_best}; then delete")
        if args.execute:
            shutil.copy2(best_score_json, backup_best)
            best_score_json.unlink()
    else:
        print(f"[4] best_score.json missing — nothing to backup")

    # 5. Sanity print of registry size + R4 archetype IDs
    registry = EXPERIMENTS_DIR / "hypothesis_registry.jsonl"
    if registry.exists():
        n_total = sum(1 for _ in registry.open(encoding="utf-8"))
        with registry.open(encoding="utf-8") as f:
            ids = [json.loads(line)["id"] for line in f]
        r4_entries = [i for i in ids if i.startswith("E3")]
        r4_exits = [i for i in ids if i.startswith("X3")]
        print(f"\n[5] registry sanity: total={n_total} rows; "
              f"R4 entries={len(r4_entries)} (E300-E339 expected 40); "
              f"R4 exits={len(r4_exits)} (X300-X319 expected 20)")

    print(f"\n=== {'EXECUTED' if args.execute else 'DRY-RUN'} ===")
    if not args.execute:
        print("Re-run with --execute to perform the reset.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
