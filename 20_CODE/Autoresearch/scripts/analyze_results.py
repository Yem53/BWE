"""Aggregate results.tsv into per-family / per-archetype summaries.

Used as input to Round 2+ LLM team debates. The Synthesizer reads this
to understand which entry families are saturating, which exits dominate,
and what coverage gaps remain.

Output files (in H:/BWE/40_EXPERIMENTS/analysis/<timestamp>/):
  summary.md                    — human-readable overview
  by_entry_family.csv           — per entry-channel-side aggregation
  by_exit_family.csv            — per exit-kernel aggregation
  by_entry_archetype.csv        — top 50 entries by best score
  by_exit_x_entry.csv           — pivot: exit_family rows × entry top-20 cols
  crash_audit.csv               — which archetypes crashed and why
  coverage_gaps.md              — uncovered (entry, exit_family) cells

Usage:
    python scripts/analyze_results.py
    python scripts/analyze_results.py --top-n 100 --since-cursor 0
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from bwe_autoresearch.bwe_loop_exit_kernels import classify_exit_family

from bwe_autoresearch.bwe_paths import (  # noqa: E402
    REGISTRY_JSONL as REGISTRY_PATH,
    ANALYSIS_DIR as OUTPUT_BASE,
    RESULTS_TSV,
)

ENTRY_RE = re.compile(r"E=(\w+)/([^\s]+)")
EXIT_RE = re.compile(r"X=(\w+)/([^\s]+)")
NVAR_RE = re.compile(r"n_var=(\d+)")
TP_RE = re.compile(r"best_tp=([\d.]+)")
SL_RE = re.compile(r"best_sl=([\d.]+)")
ELAPSED_RE = re.compile(r"elapsed=([\d.]+)s")


def _load_registry() -> dict:
    out = {}
    if not REGISTRY_PATH.exists():
        return out
    with REGISTRY_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            out[r["id"]] = r
    return out


def _parse_row(parts: list[str]) -> Optional[dict]:
    """Parse a results.tsv row into a structured dict."""
    if len(parts) < 5:
        return None
    try:
        commit = parts[0]
        val_score = float(parts[1])
        triggers = int(parts[2])
        status = parts[3]
        desc = parts[4]
    except (ValueError, IndexError):
        return None
    em = ENTRY_RE.search(desc)
    xm = EXIT_RE.search(desc)
    if not em or not xm:
        return None
    return {
        "commit": commit,
        "val_score": val_score,
        "triggers": triggers,
        "status": status,
        "entry_id": em.group(1),
        "entry_archetype": em.group(2).rstrip("|").rstrip(),
        "exit_id": xm.group(1),
        "exit_archetype": xm.group(2).rstrip("|").rstrip(),
        "n_variants": int(NVAR_RE.search(desc).group(1)) if NVAR_RE.search(desc) else None,
        "best_tp": float(TP_RE.search(desc).group(1)) if TP_RE.search(desc) else None,
        "best_sl": float(SL_RE.search(desc).group(1)) if SL_RE.search(desc) else None,
        "elapsed_s": float(ELAPSED_RE.search(desc).group(1)) if ELAPSED_RE.search(desc) else None,
        "description": desc,
    }


def _read_results() -> list[dict]:
    if not RESULTS_TSV.exists():
        return []
    rows = []
    text = RESULTS_TSV.read_text(encoding="utf-8")
    for line in text.splitlines()[1:]:
        parts = line.split("\t")
        r = _parse_row(parts)
        if r:
            rows.append(r)
    return rows


def _q(values, p):
    if not values:
        return float("nan")
    s = sorted(values)
    n = len(s)
    if n == 1:
        return s[0]
    k = (n - 1) * p
    lo = int(k)
    hi = min(lo + 1, n - 1)
    frac = k - lo
    return s[lo] * (1 - frac) + s[hi] * frac


def _safe_div(a, b):
    return a / b if b else float("nan")


def aggregate(rows: list[dict], registry: dict) -> dict:
    """Build all aggregations needed for LLM input + reports."""
    # Annotate each row with channel, side, exit_family
    for r in rows:
        e = registry.get(r["entry_id"], {})
        r["channel"] = e.get("channel", "unknown")
        r["side"] = e.get("side", "unknown")
        r["exit_family"] = classify_exit_family(r["exit_archetype"])
        r["channel_side"] = f"{r['channel']}/{r['side']}"

    succ = [r for r in rows if r["status"] in ("keep", "discard")]
    crashes = [r for r in rows if r["status"] == "crash"]
    skips = [r for r in rows if r["status"] == "skip"]

    # By entry channel/side
    by_chan = {}
    for r in succ:
        key = r["channel_side"]
        by_chan.setdefault(key, []).append(r["val_score"])

    by_chan_summary = []
    for key, scores in sorted(by_chan.items()):
        by_chan_summary.append({
            "channel_side": key,
            "n": len(scores),
            "mean": sum(scores) / len(scores),
            "median": _q(scores, 0.5),
            "p75": _q(scores, 0.75),
            "max": max(scores),
            "min": min(scores),
            "n_positive": sum(1 for s in scores if s > 0),
        })

    # By exit family
    by_exit_fam = {}
    for r in succ:
        key = r["exit_family"]
        by_exit_fam.setdefault(key, []).append(r["val_score"])

    by_exit_summary = []
    for key, scores in sorted(by_exit_fam.items()):
        by_exit_summary.append({
            "exit_family": key,
            "n": len(scores),
            "mean": sum(scores) / len(scores),
            "median": _q(scores, 0.5),
            "p75": _q(scores, 0.75),
            "max": max(scores),
            "n_positive": sum(1 for s in scores if s > 0),
        })

    # By entry archetype (top by best score)
    by_entry_arch = {}
    for r in succ:
        key = r["entry_id"]
        by_entry_arch.setdefault(key, []).append(r)

    entry_arch_summary = []
    for eid, rs in by_entry_arch.items():
        scores = [r["val_score"] for r in rs]
        e = registry.get(eid, {})
        entry_arch_summary.append({
            "entry_id": eid,
            "archetype": e.get("archetype", rs[0]["entry_archetype"]),
            "channel": e.get("channel", "?"),
            "side": e.get("side", "?"),
            "novel_dim": "; ".join(e.get("novel_dim", []))[:120],
            "n_exits_tested": len(rs),
            "best_score": max(scores),
            "median_score": _q(scores, 0.5),
            "best_exit": max(rs, key=lambda x: x["val_score"])["exit_archetype"],
            "best_exit_family": max(rs, key=lambda x: x["val_score"])["exit_family"],
            "best_tp": max(rs, key=lambda x: x["val_score"])["best_tp"],
            "best_sl": max(rs, key=lambda x: x["val_score"])["best_sl"],
            "best_triggers": max(rs, key=lambda x: x["val_score"])["triggers"],
        })
    entry_arch_summary.sort(key=lambda x: x["best_score"], reverse=True)

    # Pivot: best score per (entry, exit_family)
    pivot = {}
    for r in succ:
        eid = r["entry_id"]
        fam = r["exit_family"]
        key = (eid, fam)
        prev = pivot.get(key)
        if prev is None or r["val_score"] > prev["val_score"]:
            pivot[key] = r

    # Crash audit
    crash_by_entry = {}
    for r in crashes:
        crash_by_entry.setdefault(r["entry_id"], []).append(r)

    crash_summary = []
    for eid, rs in sorted(crash_by_entry.items(), key=lambda x: -len(x[1])):
        e = registry.get(eid, {})
        crash_summary.append({
            "entry_id": eid,
            "archetype": e.get("archetype", "?"),
            "channel": e.get("channel", "?"),
            "n_crashes": len(rs),
            "novel_dim": "; ".join(e.get("novel_dim", []))[:120],
            "sample_desc": rs[0]["description"][:80],
        })

    return {
        "n_rows": len(rows),
        "n_succ": len(succ),
        "n_crashes": len(crashes),
        "n_skips": len(skips),
        "by_channel_side": by_chan_summary,
        "by_exit_family": by_exit_summary,
        "by_entry_archetype": entry_arch_summary,
        "pivot": pivot,
        "crashes": crash_summary,
    }


def render_summary_md(agg: dict, top_n: int) -> str:
    lines = []
    lines.append(f"# BWE Loop Results Analysis ({time.strftime('%Y-%m-%d %H:%M:%S')})")
    lines.append("")
    lines.append(f"- Total rows: {agg['n_rows']:,}")
    lines.append(f"- Successful (keep/discard): {agg['n_succ']:,}")
    lines.append(f"- Crashes: {agg['n_crashes']:,}")
    lines.append(f"- Skips: {agg['n_skips']:,}")
    lines.append("")

    lines.append("## Per Channel × Side")
    lines.append("")
    lines.append("| Channel/Side | n | mean | median | p75 | max | n_pos |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for c in agg["by_channel_side"]:
        lines.append(
            f"| {c['channel_side']} | {c['n']:,} | "
            f"{c['mean']:+.4f} | {c['median']:+.4f} | "
            f"{c['p75']:+.4f} | {c['max']:+.4f} | {c['n_positive']} |"
        )
    lines.append("")

    lines.append("## Per Exit Family (kernel)")
    lines.append("")
    lines.append("| Exit family | n | mean | median | p75 | max | n_pos |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for c in agg["by_exit_family"]:
        lines.append(
            f"| {c['exit_family']} | {c['n']:,} | "
            f"{c['mean']:+.4f} | {c['median']:+.4f} | "
            f"{c['p75']:+.4f} | {c['max']:+.4f} | {c['n_positive']} |"
        )
    lines.append("")

    lines.append(f"## Top {top_n} Entry Archetypes (by best score across all exits)")
    lines.append("")
    lines.append("| # | id | archetype | ch/side | n_exits | best | best_exit (family) | best_tp | best_sl | trig |")
    lines.append("|---:|---|---|---|---:|---:|---|---:|---:|---:|")
    for i, e in enumerate(agg["by_entry_archetype"][:top_n], 1):
        lines.append(
            f"| {i} | {e['entry_id']} | {e['archetype'][:35]} | "
            f"{e['channel']}/{e['side']} | {e['n_exits_tested']} | "
            f"{e['best_score']:+.4f} | "
            f"{e['best_exit'][:25]} ({e['best_exit_family']}) | "
            f"{e['best_tp']:.2f} | {e['best_sl']:.2f} | {e['best_triggers']} |"
        )
    lines.append("")

    if agg["crashes"]:
        lines.append(f"## Top 20 crash sources (entries that filter to <30 events)")
        lines.append("")
        lines.append("| id | archetype | ch | n_crashes | novel_dim |")
        lines.append("|---|---|---|---:|---|")
        for c in agg["crashes"][:20]:
            lines.append(
                f"| {c['entry_id']} | {c['archetype'][:35]} | "
                f"{c['channel']} | {c['n_crashes']} | {c['novel_dim'][:80]} |"
            )
        lines.append("")

    return "\n".join(lines)


def write_csv(path: Path, rows: list[dict], cols: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write(",".join(cols) + "\n")
        for r in rows:
            f.write(",".join(str(r.get(c, "")).replace(",", ";") for c in cols) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top-n", type=int, default=50)
    ap.add_argument("--out-dir", type=str, default=None,
                    help="Override output directory (default: timestamped under H:/BWE/40_EXPERIMENTS/analysis)")
    args = ap.parse_args()

    rows = _read_results()
    if not rows:
        print(f"FATAL: no rows in {RESULTS_TSV}")
        return 1

    registry = _load_registry()
    agg = aggregate(rows, registry)

    if args.out_dir:
        out_dir = Path(args.out_dir)
    else:
        out_dir = OUTPUT_BASE / time.strftime("%Y%m%d_%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)

    # Write outputs
    (out_dir / "summary.md").write_text(render_summary_md(agg, args.top_n), encoding="utf-8")
    write_csv(
        out_dir / "by_channel_side.csv", agg["by_channel_side"],
        ["channel_side", "n", "mean", "median", "p75", "max", "min", "n_positive"],
    )
    write_csv(
        out_dir / "by_exit_family.csv", agg["by_exit_family"],
        ["exit_family", "n", "mean", "median", "p75", "max", "n_positive"],
    )
    write_csv(
        out_dir / "by_entry_archetype.csv", agg["by_entry_archetype"][:200],
        ["entry_id", "archetype", "channel", "side", "novel_dim", "n_exits_tested",
         "best_score", "median_score", "best_exit", "best_exit_family",
         "best_tp", "best_sl", "best_triggers"],
    )
    write_csv(
        out_dir / "crash_audit.csv", agg["crashes"],
        ["entry_id", "archetype", "channel", "n_crashes", "novel_dim", "sample_desc"],
    )

    # Pivot CSV: rows=exit_family, cols=top entries' best score
    top20 = [e["entry_id"] for e in agg["by_entry_archetype"][:20]]
    families = sorted({fam for (_, fam) in agg["pivot"].keys()})
    pivot_lines = ["exit_family," + ",".join(top20)]
    for fam in families:
        cells = []
        for eid in top20:
            r = agg["pivot"].get((eid, fam))
            cells.append(f"{r['val_score']:+.4f}" if r else "")
        pivot_lines.append(fam + "," + ",".join(cells))
    (out_dir / "pivot_exit_x_entry_top20.csv").write_text("\n".join(pivot_lines), encoding="utf-8")

    print(f"\nAnalysis written to: {out_dir}")
    print(f"  summary.md            ({len((out_dir / 'summary.md').read_text(encoding='utf-8').splitlines())} lines)")
    print(f"  by_channel_side.csv   ({len(agg['by_channel_side'])} rows)")
    print(f"  by_exit_family.csv    ({len(agg['by_exit_family'])} rows)")
    print(f"  by_entry_archetype.csv ({min(200, len(agg['by_entry_archetype']))} rows)")
    print(f"  crash_audit.csv       ({len(agg['crashes'])} rows)")
    print(f"  pivot_exit_x_entry_top20.csv")

    print("\n=== TOP 10 entries (preview) ===")
    for i, e in enumerate(agg["by_entry_archetype"][:10], 1):
        print(f"  {i:2d}. {e['entry_id']:6s} {e['archetype'][:30]:30s} "
              f"best={e['best_score']:+.4f} via {e['best_exit_family']:9s} "
              f"trig={e['best_triggers']:4d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
