"""Auto-pilot for Round 3: wait for loop → analyze → rescore → deep debate → merge.

This script blocks until the running BWE loop process exits (or a sentinel
`done.txt` appears), then runs the full Round 3 pipeline:

  1. analyze_results.py        — aggregate per-channel/exit-family stats
  2. rescore_with_v2.py        — recompute all 4 metrics + paper-shadow proxy
  3. bwe_loop_llm_team --deep  — full 5-role × per-proposal × Synthesizer
                                 (~50 LLM calls, ~$10-15 with Max subscription)
  4. merge_accepted_archetypes — auto-merge filtered/parseable archetypes

Output: a single timestamped directory with all artifacts + summary.md.

Usage:
    # Run after loop has stopped (loop_run.pid is dead):
    python scripts/round3_auto_launcher.py

    # Or wait for currently-running loop to finish:
    python scripts/round3_auto_launcher.py --wait-for-pid

    # Skip rescore (faster, slightly less rigorous):
    python scripts/round3_auto_launcher.py --skip-rescore

    # Use shallow debate (5 calls instead of 50):
    python scripts/round3_auto_launcher.py --shallow
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))  # so we can import bwe_autoresearch.bwe_paths
from bwe_autoresearch.bwe_paths import LOOP_PID_FILE, PIPELINE_LOG, ANALYSIS_DIR, MORNING_BRIEF_LATEST  # noqa: E402


def _resolve_python() -> str:
    """Pick a Python interpreter that works on Windows or Mac."""
    explicit = os.environ.get("BWE_PYTHON")
    if explicit:
        return explicit
    if sys.platform == "win32":
        # 5090 install path (legacy default)
        win_default = r"C:\Users\Admin\AppData\Local\Programs\Python\Python312\python.exe"
        if Path(win_default).exists():
            return win_default
    # Use the running interpreter (works on Mac, Linux, WSL)
    return sys.executable


PYTHON = _resolve_python()


def log(msg: str):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    PIPELINE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with PIPELINE_LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def run_step(label: str, cmd: list[str], cwd: Path = REPO_ROOT, env_extra: dict = None) -> int:
    log(f">>> START: {label}")
    log(f"    cmd: {' '.join(cmd)}")
    env = os.environ.copy()
    # PYTHONUSERBASE is for the Windows torch+CUDA install; only set it on Windows
    if sys.platform == "win32":
        env["PYTHONUSERBASE"] = env.get("PYTHONUSERBASE", "H:\\py312-userbase")
    if env_extra:
        env.update(env_extra)
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, cwd=cwd, env=env, encoding="utf-8")
        rc = proc.returncode
    except Exception as e:
        log(f"    EXCEPTION: {e}")
        return 1
    elapsed = time.time() - t0
    log(f"<<< DONE:  {label}  rc={rc}  elapsed={elapsed:.1f}s")
    return rc


def wait_for_loop_exit(check_interval: int = 60) -> None:
    """Poll until the loop PID dies."""
    if not LOOP_PID_FILE.exists():
        log("loop_run.pid does not exist — assuming loop already done")
        return
    try:
        loop_pid = int("".join(c for c in LOOP_PID_FILE.read_text(encoding="utf-8") if c.isdigit()))
    except (ValueError, OSError):
        log("loop_run.pid unreadable — assuming loop already done")
        return

    log(f"waiting for loop PID {loop_pid} to exit (poll every {check_interval}s)")
    while True:
        # Windows: tasklist + filter; cross-platform fallback via psutil if installed
        try:
            import psutil
            still_running = psutil.pid_exists(loop_pid)
        except ImportError:
            # Use tasklist on Windows
            r = subprocess.run(
                ["tasklist", "/FI", f"PID eq {loop_pid}"],
                capture_output=True, text=True,
            )
            still_running = str(loop_pid) in r.stdout

        if not still_running:
            log(f"loop PID {loop_pid} no longer running — proceeding")
            return
        time.sleep(check_interval)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wait-for-pid", action="store_true",
                    help="Block until loop PID is dead before starting pipeline")
    ap.add_argument("--skip-rescore", action="store_true")
    ap.add_argument("--skip-paper-sim", action="store_true")
    ap.add_argument("--shallow", action="store_true",
                    help="Use 5-call debate instead of 50-call deep")
    ap.add_argument("--debate-recent-n", type=int, default=50)
    ap.add_argument("--rescore-max", type=int, default=None,
                    help="Limit rescore to first N candidates (for fast testing)")
    args = ap.parse_args()

    log("=" * 70)
    log("BWE Round 3 auto-pilot starting")
    log("=" * 70)

    # 0. Optional: wait for loop
    if args.wait_for_pid:
        wait_for_loop_exit()

    # 1. Analyze results
    rc = run_step(
        "analyze_results",
        [PYTHON, "-u", "scripts/analyze_results.py", "--top-n", "50"],
    )
    if rc != 0:
        log(f"analyze_results failed rc={rc}; aborting")
        return rc

    # 2. Rescore with v2 metrics (optional)
    if not args.skip_rescore:
        cmd = [PYTHON, "-u", "scripts/rescore_with_v2.py", "--top-n", "30"]
        if args.rescore_max:
            cmd += ["--max-candidates", str(args.rescore_max)]
        rc = run_step("rescore_with_v2", cmd)
        if rc != 0:
            log(f"rescore_with_v2 failed rc={rc}; continuing (debate doesn't strictly need it)")

    # 3. Deep debate
    debate_reason = os.environ.get("BWE_DEBATE_REASON", "round_3_full_grid_complete")
    cmd = [
        PYTHON, "-u", "-m", "bwe_autoresearch.bwe_loop_llm_team",
        "--reason", debate_reason,
        "--recent-n", str(args.debate_recent_n),
    ]
    if not args.shallow:
        cmd.append("--deep")
    rc = run_step(
        f"debate ({'deep' if not args.shallow else 'shallow'})",
        cmd,
    )
    if rc != 0:
        log(f"debate failed rc={rc}; aborting before merge")
        return rc

    # 4. Auto-merge accepted archetypes (with dry-run first to check)
    log("merging accepted archetypes from latest debate...")
    rc = run_step(
        "merge_archetypes (dry run)",
        [PYTHON, "-u", "scripts/merge_accepted_archetypes.py", "--latest", "--dry-run"],
    )
    if rc == 0:
        log("dry-run OK; performing real merge")
        rc = run_step(
            "merge_archetypes (real)",
            [PYTHON, "-u", "scripts/merge_accepted_archetypes.py", "--latest"],
        )

    # 5. Optional: paper-shadow sim on top 5 candidates from rescore
    if not args.skip_paper_sim:
        # Find top 5 entry IDs by Kelly from latest rescore CSV
        analysis_dir = ANALYSIS_DIR
        rescore_dirs = sorted(
            [d for d in analysis_dir.iterdir() if d.is_dir() and d.name.startswith("rescore_")],
            reverse=True,
        )
        if rescore_dirs:
            csv_path = rescore_dirs[0] / "rescore_v2.csv"
            if csv_path.exists():
                top_ids = []
                lines = csv_path.read_text(encoding="utf-8").splitlines()
                if len(lines) > 1:
                    header = lines[0].split(",")
                    try:
                        kelly_idx = header.index("score_kelly_pct")
                        eid_idx = header.index("entry_id")
                    except ValueError:
                        kelly_idx = -1
                    if kelly_idx > 0:
                        rows = []
                        for line in lines[1:]:
                            parts = line.split(",")
                            if len(parts) > max(kelly_idx, eid_idx):
                                try:
                                    rows.append((parts[eid_idx], float(parts[kelly_idx])))
                                except ValueError:
                                    pass
                        rows.sort(key=lambda x: x[1], reverse=True)
                        top_ids = [r[0] for r in rows[:5]]
                for eid in top_ids:
                    run_step(f"paper_shadow_sim {eid}",
                             [PYTHON, "-u", "scripts/paper_shadow_sim.py", eid])

    # 6. Morning brief (Chinese summary) — final artifact for the user
    rc = run_step(
        "morning_brief_zh",
        [PYTHON, "-u", "scripts/morning_brief_zh.py"],
    )
    if rc != 0:
        log(f"morning_brief_zh failed rc={rc}; pipeline still considered done")

    brief_latest = MORNING_BRIEF_LATEST
    if brief_latest.exists():
        log(f"morning brief written to: {brief_latest}")

    log("=" * 70)
    log("BWE Round 3 auto-pilot DONE")
    log("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
