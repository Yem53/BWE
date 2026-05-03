"""Day 3.5: Live monitor for the BWE autoresearch loop.

Tails results.tsv and shows:
  - Throughput estimate (evals/sec, rolling)
  - GPU utilization (via nvidia-smi)
  - Best score so far + recent winners
  - Status counts (keep / discard / crash / skip)
  - Recent debate runs (if any)
  - Project ETA to N total evaluations

Two display modes:
  1. one-shot   (default)   : print snapshot and exit
  2. live       (--watch)   : refresh every N seconds (default 10)

Usage:
    python -m bwe_autoresearch.bwe_loop_monitor                 # snapshot
    python -m bwe_autoresearch.bwe_loop_monitor --watch         # live, 10s refresh
    python -m bwe_autoresearch.bwe_loop_monitor --watch --interval 30
    python -m bwe_autoresearch.bwe_loop_monitor --target-evals 1e10
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from collections import Counter, deque
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_TSV = REPO_ROOT / "results.tsv"
BEST_SCORE_JSON = REPO_ROOT / "best_score.json"
from bwe_autoresearch.bwe_paths import DEBATES_DIR  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_results() -> list[dict]:
    if not RESULTS_TSV.exists():
        return []
    out = []
    for line in RESULTS_TSV.read_text(encoding="utf-8").splitlines()[1:]:
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        try:
            out.append({
                "commit": parts[0],
                "val_score": float(parts[1]),
                "triggers": int(parts[2]),
                "status": parts[3],
                "description": parts[4],
            })
        except (ValueError, IndexError):
            continue
    return out


def _read_best_score() -> float | None:
    if not BEST_SCORE_JSON.exists():
        return None
    try:
        return float(json.loads(BEST_SCORE_JSON.read_text())["score"])
    except (KeyError, ValueError, json.JSONDecodeError):
        return None


def _gpu_utilization() -> dict:
    """Return GPU stats via nvidia-smi. Empty dict if nvidia-smi missing."""
    nvsmi = shutil.which("nvidia-smi")
    if not nvsmi:
        return {}
    try:
        out = subprocess.run(
            [nvsmi, "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return {}
    if out.returncode != 0:
        return {}
    line = out.stdout.strip().splitlines()[0] if out.stdout.strip() else ""
    parts = [p.strip() for p in line.split(",")]
    if len(parts) < 6:
        return {"raw": line}
    return {
        "name": parts[0],
        "util_pct": _to_int(parts[1]),
        "mem_used_mb": _to_int(parts[2]),
        "mem_total_mb": _to_int(parts[3]),
        "temp_c": _to_int(parts[4]),
        "power_w": _to_float(parts[5]),
    }


def _to_int(s: str) -> int | None:
    try:
        return int(s)
    except ValueError:
        return None


def _to_float(s: str) -> float | None:
    try:
        return float(s)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Throughput estimation
# ---------------------------------------------------------------------------

_EVAL_RE = re.compile(r"n_var=(\d+).*?elapsed=([\d.]+)s")


def _evals_per_row(row: dict) -> tuple[int, float] | None:
    """Extract (n_evals, elapsed_s) from a results.tsv row's description.

    Description format (from bwe_loop.py):
        "<combo> | n_var=10000 best_tp=... elapsed=8.8s"
    """
    m = _EVAL_RE.search(row["description"])
    if not m:
        return None
    n_var = int(m.group(1))
    elapsed = float(m.group(2))
    n_evals = row["triggers"] * n_var  # events × variants
    return n_evals, elapsed


def _throughput_summary(rows: list[dict]) -> dict:
    """Compute total + recent throughput."""
    extracted = []
    for r in rows:
        e = _evals_per_row(r)
        if e:
            extracted.append(e)
    if not extracted:
        return {"total_evals": 0, "rate": None, "recent_rate": None}

    total_evals = sum(e[0] for e in extracted)
    total_time = sum(e[1] for e in extracted)
    rate = total_evals / total_time if total_time > 0 else None

    # Recent: last 20 experiments
    recent = extracted[-20:]
    recent_evals = sum(e[0] for e in recent)
    recent_time = sum(e[1] for e in recent)
    recent_rate = recent_evals / recent_time if recent_time > 0 else None

    return {
        "total_evals": total_evals,
        "total_time_s": total_time,
        "rate": rate,
        "recent_rate": recent_rate,
        "n_experiments": len(extracted),
    }


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

def _format_int(n: int | float | None) -> str:
    if n is None:
        return "—"
    if n >= 1_000_000_000:
        return f"{n/1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"{n/1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return f"{int(n)}"


def render_snapshot(target_evals: float | None) -> str:
    rows = _read_results()
    best = _read_best_score()
    gpu = _gpu_utilization()
    tput = _throughput_summary(rows)
    status_counts = Counter(r["status"] for r in rows)

    lines = []
    lines.append(f"=== BWE Loop Monitor  ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===")
    lines.append("")

    # GPU section
    lines.append("[GPU]")
    if gpu:
        lines.append(f"  {gpu.get('name', 'unknown')}  util={gpu.get('util_pct', '?')}%  "
                     f"mem={gpu.get('mem_used_mb', '?')}/{gpu.get('mem_total_mb', '?')} MB  "
                     f"temp={gpu.get('temp_c', '?')}°C  power={gpu.get('power_w', '?')}W")
    else:
        lines.append("  (nvidia-smi unavailable)")
    lines.append("")

    # Results section
    lines.append("[Results]")
    lines.append(f"  total experiments: {len(rows)}")
    lines.append(f"  by status: {dict(status_counts)}")
    lines.append(f"  best score (oos_p25_net_pct_after_cost): {best:.4f}" if best is not None else "  best score: —")
    lines.append("")

    # Throughput section
    lines.append("[Throughput]")
    lines.append(f"  total evals:    {_format_int(tput['total_evals'])}")
    lines.append(f"  total cpu time: {tput.get('total_time_s', 0):.0f}s")
    lines.append(f"  cumulative:     {_format_int(tput['rate'])} evals/sec" if tput.get('rate') else "  cumulative: —")
    lines.append(f"  recent (last 20): {_format_int(tput['recent_rate'])} evals/sec" if tput.get('recent_rate') else "  recent: —")
    if target_evals and tput.get('recent_rate'):
        remaining = max(0, target_evals - tput['total_evals'])
        eta_s = remaining / tput['recent_rate']
        lines.append(f"  ETA to {_format_int(target_evals)}: {eta_s/3600:.2f} hours ({eta_s/60:.0f} min)")
    lines.append("")

    # Recent winners
    keeps = [r for r in rows if r["status"] == "keep"]
    if keeps:
        lines.append(f"[Recent winners (last 5 of {len(keeps)})]")
        for r in keeps[-5:]:
            desc = r["description"][:90] + ("…" if len(r["description"]) > 90 else "")
            lines.append(f"  score={r['val_score']:.4f}  triggers={r['triggers']}  {desc}")
        lines.append("")

    # Crashes
    crashes = [r for r in rows if r["status"] == "crash"]
    if crashes:
        lines.append(f"[Recent crashes (last 3 of {len(crashes)})]")
        for r in crashes[-3:]:
            desc = r["description"][:90] + ("…" if len(r["description"]) > 90 else "")
            lines.append(f"  {desc}")
        lines.append("")

    # LLM debates
    if DEBATES_DIR.exists():
        runs = sorted([d for d in DEBATES_DIR.iterdir() if d.is_dir()], reverse=True)[:5]
        if runs:
            lines.append(f"[Recent LLM debates (last {len(runs)})]")
            for d in runs:
                accepted_path = d / "new_archetypes.jsonl"
                rejected_path = d / "rejected_archetypes.jsonl"
                accepted_n = sum(1 for _ in accepted_path.open(encoding="utf-8")) if accepted_path.exists() else 0
                rejected_n = sum(1 for _ in rejected_path.open(encoding="utf-8")) if rejected_path.exists() else 0
                lines.append(f"  {d.name}  accepted={accepted_n} rejected={rejected_n}")
            lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch", action="store_true", help="Refresh continuously")
    ap.add_argument("--interval", type=int, default=10, help="Refresh interval in seconds")
    ap.add_argument("--target-evals", type=float, default=1e10,
                    help="Target evals for ETA calculation (default 10B)")
    args = ap.parse_args()

    if not args.watch:
        print(render_snapshot(target_evals=args.target_evals))
        return 0

    try:
        while True:
            # Clear screen and render
            print("\x1b[H\x1b[J", end="")  # ANSI clear
            print(render_snapshot(target_evals=args.target_evals))
            print(f"\n(refreshing every {args.interval}s — Ctrl+C to exit)")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n[monitor] stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
