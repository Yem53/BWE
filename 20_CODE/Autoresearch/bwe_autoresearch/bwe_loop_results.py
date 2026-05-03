"""Day 2.4: Results logger + git auto keep/discard.

Mirrors Karpathy autoresearch's results.tsv pattern:
    commit	val_score	triggers	status	description

Where:
    commit      git short hash (7 chars) at the time of the experiment
    val_score   the single metric value (oos_p25_net_pct_after_cost), 6 decimals
    triggers    number of unique triggers (>=10 expected; <30 likely noise)
    status      keep | discard | crash | skip
    description short human-readable summary (no tabs)

Decision logic:
    keep    : score > best_so_far (strict improvement)
    discard : score <= best_so_far
    crash   : exception or invalid (NaN) score
    skip    : pre-flight rejected (e.g. samples too small)

When status == keep: caller should `git add -A && git commit` to advance the
branch. When discard/crash: caller should `git reset --hard` to revert.

Best score is tracked in best_score.json (sibling of results.tsv) so we
survive process restarts.

Usage:
    from bwe_loop_results import ResultsLogger
    log = ResultsLogger(repo_root=Path("H:/BWE/20_CODE/Autoresearch"))
    decision = log.append(score=0.42, triggers=312, description="archetype=E001 ...")
    if decision.action == "commit":
        log.git_commit(decision.commit_message)
    elif decision.action == "reset":
        log.git_reset()
"""

from __future__ import annotations

import json
import math
import subprocess
from dataclasses import dataclass
from pathlib import Path

try:
    from bwe_autoresearch.bwe_paths import AUTORESEARCH_DIR
    DEFAULT_REPO = AUTORESEARCH_DIR
except ImportError:
    DEFAULT_REPO = Path("H:/BWE/20_CODE/Autoresearch")  # Windows fallback
RESULTS_TSV = "results.tsv"
BEST_SCORE_JSON = "best_score.json"
TSV_HEADER = "commit\tval_score\ttriggers\tstatus\tdescription\n"


@dataclass
class Decision:
    status: str           # keep | discard | crash | skip
    action: str           # commit | reset | nothing
    commit_message: str   # if action=commit
    reason: str           # short string explaining
    new_best: float | None  # only set when status=keep


class ResultsLogger:
    """Per-loop instance — manages results.tsv + best_score.json + git."""

    def __init__(self, repo_root: Path = DEFAULT_REPO) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.tsv_path = self.repo_root / RESULTS_TSV
        self.best_path = self.repo_root / BEST_SCORE_JSON
        self._ensure_tsv()

    # ----- TSV maintenance -----------------------------------------------------

    def _ensure_tsv(self) -> None:
        if not self.tsv_path.exists():
            self.tsv_path.write_text(TSV_HEADER, encoding="utf-8")

    def _current_commit(self) -> str:
        try:
            out = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=self.repo_root, capture_output=True, text=True, check=True,
            )
            return out.stdout.strip()[:7]
        except (subprocess.CalledProcessError, FileNotFoundError):
            return "0000000"

    def _read_best(self) -> float:
        if not self.best_path.exists():
            return float("-inf")
        try:
            return float(json.loads(self.best_path.read_text())["score"])
        except (KeyError, ValueError, json.JSONDecodeError):
            return float("-inf")

    def _write_best(self, score: float) -> None:
        self.best_path.write_text(
            json.dumps({"score": score}, indent=2), encoding="utf-8"
        )

    # ----- public API ---------------------------------------------------------

    def append(
        self,
        score: float,
        triggers: int,
        description: str,
        min_triggers: int = 30,
    ) -> Decision:
        """Append one experiment result, return keep/discard/crash decision."""
        # Normalize description (TSV-safe: no tabs/newlines)
        desc = description.replace("\t", " ").replace("\n", " ").strip()
        if not desc:
            desc = "(no description)"

        commit = self._current_commit()

        # Crash detection
        if score is None or (isinstance(score, float) and math.isnan(score)):
            status = "crash"
            reason = "score is NaN/None"
        elif triggers < min_triggers:
            status = "skip"
            reason = f"triggers {triggers} < min {min_triggers}"
        else:
            best = self._read_best()
            if score > best:
                status = "keep"
                reason = f"score {score:.6f} > best {best:.6f}"
            else:
                status = "discard"
                reason = f"score {score:.6f} <= best {best:.6f}"

        # Append to TSV
        score_str = "0.000000" if score is None or math.isnan(score) else f"{score:.6f}"
        line = f"{commit}\t{score_str}\t{triggers}\t{status}\t{desc}\n"
        with self.tsv_path.open("a", encoding="utf-8") as f:
            f.write(line)

        # Decide downstream action + update best
        action: str
        commit_message: str
        new_best: float | None
        if status == "keep":
            action = "commit"
            commit_message = f"[BWE-Loop] keep: score={score:.6f} triggers={triggers} {desc[:80]}"
            new_best = score
            self._write_best(score)
        elif status == "discard":
            action = "reset"
            commit_message = ""
            new_best = None
        else:  # crash / skip
            action = "reset"  # safe default — undo any working-tree changes
            commit_message = ""
            new_best = None

        return Decision(
            status=status,
            action=action,
            commit_message=commit_message,
            reason=reason,
            new_best=new_best,
        )

    # ----- git operations -----------------------------------------------------

    def git_commit(self, message: str, author: str = "BWE Loop <bwe@local>") -> bool:
        """Stage + commit current working tree. Returns True on success."""
        try:
            subprocess.run(
                ["git", "add", "-A"], cwd=self.repo_root, check=True,
                capture_output=True,
            )
            subprocess.run(
                [
                    "git", "-c", f"user.name={author.split('<')[0].strip()}",
                    "-c", f"user.email={author.split('<')[1].rstrip('>')}",
                    "-c", "commit.gpgsign=false",
                    "commit", "--allow-empty", "-m", message,
                ],
                cwd=self.repo_root, check=True, capture_output=True,
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def git_reset(self) -> bool:
        """Reset only loop-managed state files (results.tsv, best_score.json).

        Do NOT use `git reset --hard` here — that would clobber any unstaged
        source-code edits the user made while the loop was running. We only
        need to undo any partial state changes from the just-failed experiment.
        """
        # In practice, results.tsv and best_score.json are the only files the
        # loop writes per-experiment. Both are append-only or single-overwrite,
        # so a checkout is sufficient to restore the last-committed state.
        for state_file in [RESULTS_TSV, BEST_SCORE_JSON]:
            target = self.repo_root / state_file
            if not target.exists():
                continue
            try:
                subprocess.run(
                    ["git", "checkout", "HEAD", "--", str(state_file)],
                    cwd=self.repo_root, check=True, capture_output=True,
                )
            except subprocess.CalledProcessError:
                # File may be untracked or pre-first-commit; leave as-is
                pass
        return True

    def summary(self) -> dict:
        """Quick stats for monitor."""
        if not self.tsv_path.exists():
            return {"total": 0}
        lines = self.tsv_path.read_text(encoding="utf-8").splitlines()[1:]  # skip header
        counts = {"keep": 0, "discard": 0, "crash": 0, "skip": 0}
        for line in lines:
            parts = line.split("\t")
            if len(parts) >= 4:
                counts[parts[3]] = counts.get(parts[3], 0) + 1
        return {
            "total": len(lines),
            "by_status": counts,
            "best": self._read_best(),
        }


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _self_test() -> int:
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="bwe_results_test_"))
    # Make tmp into a git repo so commit/reset work
    subprocess.run(["git", "init"], cwd=tmp, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test"], cwd=tmp, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=tmp, check=True)
    (tmp / "seed.txt").write_text("init")
    subprocess.run(["git", "add", "-A"], cwd=tmp, check=True)
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "commit", "-m", "init"],
        cwd=tmp, check=True, capture_output=True,
    )

    log = ResultsLogger(repo_root=tmp)

    # 1. First result, baseline (should keep)
    d1 = log.append(score=0.10, triggers=100, description="baseline E001/X001")
    print(f"  first:  status={d1.status} action={d1.action} reason={d1.reason}")
    assert d1.status == "keep"
    assert d1.action == "commit"

    # 2. Better score (should keep)
    d2 = log.append(score=0.15, triggers=120, description="better X002")
    print(f"  better: status={d2.status} action={d2.action} reason={d2.reason}")
    assert d2.status == "keep"

    # 3. Worse score (should discard)
    d3 = log.append(score=0.08, triggers=80, description="worse X003")
    print(f"  worse:  status={d3.status} action={d3.action} reason={d3.reason}")
    assert d3.status == "discard"
    assert d3.action == "reset"

    # 4. NaN score (crash)
    d4 = log.append(score=float("nan"), triggers=50, description="bad eval")
    print(f"  crash:  status={d4.status} action={d4.action} reason={d4.reason}")
    assert d4.status == "crash"

    # 5. Too few triggers (skip)
    d5 = log.append(score=99.0, triggers=10, description="tiny sample")
    print(f"  skip:   status={d5.status} action={d5.action} reason={d5.reason}")
    assert d5.status == "skip"

    # 6. Summary
    sm = log.summary()
    print(f"  summary: total={sm['total']} by_status={sm['by_status']} best={sm['best']:.4f}")
    assert sm["total"] == 5
    assert sm["best"] == 0.15

    # 7. TSV contents
    print(f"\nTSV at {log.tsv_path}:")
    print(log.tsv_path.read_text())

    # cleanup
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)

    print("ALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test())
