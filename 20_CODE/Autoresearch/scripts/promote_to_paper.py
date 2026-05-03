"""Filter results.tsv for archetypes ready to enter paper-shadow trading.

Three-gate criteria (configurable):
  1. score gate:    val_score >= MIN_SCORE
  2. sample gate:   triggers >= MIN_TRIGGERS
  3. distinct gate: best score across exit families is meaningfully > median
                    (rules out fluke single-exit hits)

Output:
  H:/BWE/40_EXPERIMENTS/paper_candidates_<timestamp>.csv

Usage:
    python scripts/promote_to_paper.py
    python scripts/promote_to_paper.py --min-score 0.20 --min-triggers 100
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from bwe_autoresearch.bwe_loop_exit_kernels import classify_exit_family

from bwe_autoresearch.bwe_paths import (  # noqa: E402
    REGISTRY_JSONL as REGISTRY_PATH,
    PAPER_CANDIDATES_DIR as PAPER_DIR,
    RESULTS_TSV,
)


def _load_registry() -> dict:
    out = {}
    if REGISTRY_PATH.exists():
        with REGISTRY_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    r = json.loads(line)
                    out[r["id"]] = r
    return out


def _read_results():
    import re
    if not RESULTS_TSV.exists():
        return []
    rows = []
    text = RESULTS_TSV.read_text(encoding="utf-8")
    ENT = re.compile(r"E=(\w+)/")
    EXT = re.compile(r"X=(\w+)/(\S+)")
    TP = re.compile(r"best_tp=([\d.]+)")
    SL = re.compile(r"best_sl=([\d.]+)")
    for line in text.splitlines()[1:]:
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        try:
            score = float(parts[1])
            triggers = int(parts[2])
        except ValueError:
            continue
        if parts[3] not in ("keep", "discard"):
            continue
        em = ENT.search(parts[4])
        xm = EXT.search(parts[4])
        if not em or not xm:
            continue
        rows.append({
            "score": score,
            "triggers": triggers,
            "entry_id": em.group(1),
            "exit_id": xm.group(1),
            "exit_archetype": xm.group(2).rstrip("|").rstrip(),
            "exit_family": classify_exit_family(xm.group(2).rstrip("|").rstrip()),
            "best_tp": float(TP.search(parts[4]).group(1)) if TP.search(parts[4]) else None,
            "best_sl": float(SL.search(parts[4]).group(1)) if SL.search(parts[4]) else None,
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-score", type=float, default=0.20,
                    help="oos_p25_net_pct_after_cost threshold (default 0.20%)")
    ap.add_argument("--min-triggers", type=int, default=100,
                    help="min triggers for the entry's filtered events")
    ap.add_argument("--top-n", type=int, default=30, help="cap on output size")
    args = ap.parse_args()

    rows = _read_results()
    registry = _load_registry()

    # Group by entry_id
    by_entry = {}
    for r in rows:
        by_entry.setdefault(r["entry_id"], []).append(r)

    candidates = []
    for eid, rs in by_entry.items():
        best = max(rs, key=lambda x: x["score"])
        if best["score"] < args.min_score:
            continue
        if best["triggers"] < args.min_triggers:
            continue
        # Distinctness: best score must beat median of this entry's exit-family scores
        scores = [r["score"] for r in rs]
        scores_sorted = sorted(scores)
        median = scores_sorted[len(scores) // 2]
        if best["score"] <= median + 0.01:
            # All exit families gave similar score — winner is just the best of a flat distribution
            continue

        e = registry.get(eid, {})
        candidates.append({
            "entry_id": eid,
            "entry_archetype": e.get("archetype", "?"),
            "channel": e.get("channel", "?"),
            "side": e.get("side", "?"),
            "novel_dim": "; ".join(e.get("novel_dim", []))[:140],
            "best_score": best["score"],
            "median_score": median,
            "score_lift_vs_median": best["score"] - median,
            "best_exit_id": best["exit_id"],
            "best_exit_archetype": best["exit_archetype"],
            "best_exit_family": best["exit_family"],
            "best_tp": best["best_tp"],
            "best_sl": best["best_sl"],
            "triggers": best["triggers"],
            "n_exits_tested": len(rs),
        })
    candidates.sort(key=lambda x: x["best_score"], reverse=True)
    candidates = candidates[: args.top_n]

    PAPER_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PAPER_DIR / f"paper_candidates_{time.strftime('%Y%m%d_%H%M%S')}.csv"

    cols = [
        "entry_id", "entry_archetype", "channel", "side", "novel_dim",
        "best_score", "median_score", "score_lift_vs_median",
        "best_exit_id", "best_exit_archetype", "best_exit_family",
        "best_tp", "best_sl", "triggers", "n_exits_tested",
    ]
    with out_path.open("w", encoding="utf-8") as f:
        f.write(",".join(cols) + "\n")
        for c in candidates:
            f.write(",".join(str(c.get(col, "")).replace(",", ";") for col in cols) + "\n")

    print(f"Gates: min_score={args.min_score} min_triggers={args.min_triggers} top_n={args.top_n}")
    print(f"Examined {len(by_entry)} entries -> {len(candidates)} paper candidates")
    print(f"Output: {out_path}")
    print()
    print(f"=== TOP {min(10, len(candidates))} ===")
    for i, c in enumerate(candidates[:10], 1):
        print(f"  {i:2d}. {c['entry_id']:6s} {c['entry_archetype'][:32]:32s} "
              f"score={c['best_score']:+.4f} (lift +{c['score_lift_vs_median']:.4f}) "
              f"trig={c['triggers']:4d} exit={c['best_exit_family']:9s} "
              f"TP={c['best_tp']:.2f} SL={c['best_sl']:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
