"""Day 3.1: LLM team debate subprocess chain.

5 roles in sequence, each as a fresh `claude -p` subprocess (independent
context to prevent collusion):

    Generator (sonnet) -> Devil (opus) -> Quant (sonnet) -> Risk (opus) -> Synthesizer (opus)

Trigger: every N archetypes (default 25), or on demand.

Inputs (assembled by `gather_context`):
  - results.tsv tail (recent N experiments)
  - hypothesis_registry.jsonl (current archetypes)
  - coverage_map summary (per-type counts + cluster gaps)

Outputs (per debate cycle in `H:/BWE/40_EXPERIMENTS/debates/<run_id>/`):
  - 0_inputs.json          : context bundle fed to all roles
  - 1_generator.json       : 5-10 proposed new archetypes (each with archetype/notes/novel_dim)
  - 2_devil.json           : 3 reasons each proposal will fail
  - 3_quant.json           : structural distinctness check + expected sample size
  - 4_risk.json            : overfit/leakage/future-function risks
  - 5_synthesizer.json     : final accept/revise/reject decision per proposal
  - debate_log.md          : human-readable transcript
  - new_archetypes.jsonl   : accepted entries (ready to append to registry)
  - llm_usage.csv          : token usage per role (for Max budget tracking)

Each role's prompt template lives in `prompts/role_*.md` (Day 3.2).

Usage:
    from bwe_autoresearch.bwe_loop_llm_team import run_debate
    new_archetypes = run_debate(trigger="manual")

CLI:
    python -m bwe_autoresearch.bwe_loop_llm_team --reason "manual smoke"
    python -m bwe_autoresearch.bwe_loop_llm_team --reason auto --recent-n 30
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
from bwe_autoresearch.bwe_paths import REGISTRY_JSONL as REGISTRY_PATH  # noqa: E402
RESULTS_TSV = REPO_ROOT / "results.tsv"
from bwe_autoresearch.bwe_paths import DEBATES_DIR  # noqa: E402
PROMPTS_DIR = REPO_ROOT / "prompts"  # role_*.md live here

# Default model assignments (overridable via env)
# Default to Opus-4-7 for ALL roles — user has Max subscription with abundant tokens.
ROLE_MODELS = {
    "pattern_miner":          os.environ.get("BWE_LLM_PATTERN_MINER_MODEL",          "claude-opus-4-7"),
    "generator":              os.environ.get("BWE_LLM_GENERATOR_MODEL",              "claude-opus-4-7"),
    "steelman":               os.environ.get("BWE_LLM_STEELMAN_MODEL",               "claude-opus-4-7"),
    "devil":                  os.environ.get("BWE_LLM_DEVIL_MODEL",                  "claude-opus-4-7"),
    "quant":                  os.environ.get("BWE_LLM_QUANT_MODEL",                  "claude-opus-4-7"),
    "risk":                   os.environ.get("BWE_LLM_RISK_MODEL",                   "claude-opus-4-7"),
    "metric_critic":          os.environ.get("BWE_LLM_METRIC_CRITIC_MODEL",          "claude-opus-4-7"),
    "synthesizer":            os.environ.get("BWE_LLM_SYNTHESIZER_MODEL",            "claude-opus-4-7"),
    "self_reflection":        os.environ.get("BWE_LLM_SELF_REFLECTION_MODEL",        "claude-opus-4-7"),
    "behavior_annotator":     os.environ.get("BWE_LLM_BEHAVIOR_ANNOTATOR_MODEL",     "claude-opus-4-7"),
    "cross_pair_recommender": os.environ.get("BWE_LLM_CROSS_PAIR_RECOMMENDER_MODEL", "claude-opus-4-7"),
}

ROLE_ORDER = ["generator", "devil", "quant", "risk", "synthesizer"]
PER_PROPOSAL_ROLES = ["steelman", "devil", "quant", "risk", "metric_critic"]

# Each role gets these many tokens of output budget (rough cap; Claude Code respects subscriber limits)
ROLE_MAX_TOKENS = {
    "pattern_miner":          8000,
    "generator":              12000,
    "steelman":               4000,
    "devil":                  8000,
    "quant":                  4000,
    "risk":                   6000,
    "metric_critic":          4000,
    "synthesizer":            16000,
    "self_reflection":        8000,
    "behavior_annotator":     4000,
    "cross_pair_recommender": 8000,
}

def _find_claude_bin() -> str:
    """Resolve the most direct claude executable.
    Priority on Windows:
      1. claude.exe inside npm node_modules (bypasses cmd.exe AND bash.exe)
      2. claude.cmd (cmd.exe wrapper)
      3. claude POSIX script (Git Bash wrapper — spawns console)
    Direct .exe is the only path that fully respects CREATE_NO_WINDOW.
    """
    if sys.platform == "win32":
        # Search common npm install locations for the bundled claude.exe
        npm_candidates = [
            Path(os.environ.get("APPDATA", "")) / "npm" / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe",
            Path("C:/Program Files/nodejs/node_modules/@anthropic-ai/claude-code/bin/claude.exe"),
        ]
        for cand in npm_candidates:
            if cand.exists():
                return str(cand)
        cmd_path = shutil.which("claude.cmd")
        if cmd_path:
            return cmd_path
    return shutil.which("claude") or "claude"


CLAUDE_BIN = _find_claude_bin()


def _parse_assistant_json(assistant_text: str) -> dict:
    """Robust JSON extraction from LLM assistant text.

    Tries in order:
    1. Direct json.loads on full text
    2. Patch missing closing brace (LLMs sometimes truncate at output cap)
    3. Extract from ```json ... ``` markdown fence
    4. Find first '{' and try parsing to end with brace patches
    Returns {"_error": ..., "_raw_tail": ...} only when all attempts fail.
    """
    if not assistant_text:
        return {"_error": "empty assistant text", "_raw_tail": ""}

    text = assistant_text.strip()

    # 1. Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. Patch missing closing braces/brackets (truncation)
    for n_braces in range(1, 6):
        candidate = text + ("}" * n_braces)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
    for n_brackets in range(1, 4):
        candidate = text + ("]" * n_brackets)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
    # combined
    for nb in range(1, 4):
        for nk in range(1, 4):
            try:
                return json.loads(text + ("]" * nb) + ("}" * nk))
            except json.JSONDecodeError:
                pass

    # 3. Markdown fence
    import re
    for m in re.finditer(r"```(?:json)?\s*(\{[\s\S]*?\}|\[[\s\S]*?\])\s*```", text):
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # 4. Find first '{' and try truncation-patch from there
    first_brace = text.find("{")
    if first_brace >= 0:
        snippet = text[first_brace:]
        try:
            return json.loads(snippet)
        except json.JSONDecodeError:
            pass
        for n in range(1, 6):
            try:
                return json.loads(snippet + ("}" * n))
            except json.JSONDecodeError:
                pass

    return {"_error": "could not parse JSON from assistant text",
            "_raw_tail": text[-500:],
            "_text_length": len(text)}

# Windows-only: claude CLI requires a git-bash path env var. Auto-detect a
# few common locations; user can override via env.
def _detect_git_bash() -> str | None:
    if "CLAUDE_CODE_GIT_BASH_PATH" in os.environ:
        return os.environ["CLAUDE_CODE_GIT_BASH_PATH"]
    candidates = [
        r"E:\Git\usr\bin\bash.exe",
        r"E:\Git\bin\bash.exe",
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files\Git\usr\bin\bash.exe",
        r"C:\Program Files (x86)\Git\bin\bash.exe",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    return None

GIT_BASH_PATH = _detect_git_bash()


# ---------------------------------------------------------------------------
# Context assembly
# ---------------------------------------------------------------------------

@dataclass
class DebateContext:
    """All inputs handed to every role."""

    run_id: str
    trigger: str
    registry_summary: dict
    coverage_summary: dict
    results_summary: dict
    recent_experiments: list[dict]
    existing_archetype_ids: list[str]


def _load_registry() -> list[dict]:
    if not REGISTRY_PATH.exists():
        return []
    rows = []
    with REGISTRY_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _summarize_registry(registry: list[dict]) -> dict:
    by_type = Counter(r["type"] for r in registry)
    by_channel = Counter(r["channel"] for r in registry if r["type"] == "entry")
    by_side = Counter(r["side"] for r in registry if r["type"] == "entry")
    return {
        "total": len(registry),
        "by_type": dict(by_type),
        "entry_by_channel": dict(by_channel),
        "entry_by_side": dict(by_side),
    }


def _summarize_results(recent_n: int) -> tuple[dict, list[dict]]:
    if not RESULTS_TSV.exists():
        return {"total": 0, "note": "results.tsv missing"}, []

    lines = RESULTS_TSV.read_text(encoding="utf-8").splitlines()
    if len(lines) < 2:
        return {"total": 0, "note": "results.tsv has header only"}, []

    header = lines[0].split("\t")
    rows = []
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        try:
            rows.append({
                "commit": parts[0],
                "val_score": float(parts[1]),
                "triggers": int(parts[2]),
                "status": parts[3],
                "description": parts[4] if len(parts) > 4 else "",
            })
        except (ValueError, IndexError):
            continue

    status_counts = Counter(r["status"] for r in rows)
    keeps = [r for r in rows if r["status"] == "keep"]
    summary = {
        "total": len(rows),
        "by_status": dict(status_counts),
        "best_score": max((r["val_score"] for r in keeps), default=None),
        "n_keeps": len(keeps),
    }
    return summary, rows[-recent_n:]


def _aggregate_top_entries(rows: list[dict], registry: list[dict], top_n: int = 30) -> list[dict]:
    """For each entry archetype, find best score across all exits tested."""
    import re
    ENT = re.compile(r"E=(\w+)/")
    EXT = re.compile(r"X=(\w+)/(\S+)")
    by_id = {r["id"]: r for r in registry}
    by_entry = {}
    for r in rows:
        if r["status"] not in ("keep", "discard"):
            continue
        em = ENT.search(r["description"])
        xm = EXT.search(r["description"])
        if not em or not xm:
            continue
        eid = em.group(1)
        by_entry.setdefault(eid, []).append({
            "score": r["val_score"],
            "triggers": r["triggers"],
            "exit_archetype": xm.group(2).rstrip("|").rstrip(),
        })
    out = []
    for eid, rs in by_entry.items():
        e = by_id.get(eid, {})
        best = max(rs, key=lambda x: x["score"])
        scores = [r["score"] for r in rs]
        scores_sorted = sorted(scores)
        median = scores_sorted[len(scores) // 2]
        out.append({
            "entry_id": eid,
            "archetype": e.get("archetype", "?"),
            "channel": e.get("channel", "?"),
            "side": e.get("side", "?"),
            "novel_dim": e.get("novel_dim", []),
            "best_score": best["score"],
            "best_exit": best["exit_archetype"],
            "median_score": median,
            "lift_vs_median": best["score"] - median,
            "triggers": best["triggers"],
            "n_exits_tested": len(rs),
        })
    out.sort(key=lambda x: x["best_score"], reverse=True)
    return out[:top_n]


def _aggregate_by_exit_family(rows: list[dict]) -> list[dict]:
    """Per exit-family stats."""
    import re
    EXT = re.compile(r"X=(\w+)/(\S+)")
    try:
        from bwe_autoresearch.bwe_loop_exit_kernels import classify_exit_family
    except ImportError:
        return []
    by_fam = {}
    for r in rows:
        if r["status"] not in ("keep", "discard"):
            continue
        m = EXT.search(r["description"])
        if not m:
            continue
        fam = classify_exit_family(m.group(2).rstrip("|").rstrip())
        by_fam.setdefault(fam, []).append(r["val_score"])
    out = []
    for fam, scores in by_fam.items():
        scores_sorted = sorted(scores)
        n = len(scores)
        out.append({
            "exit_family": fam,
            "n": n,
            "mean": sum(scores) / n if n else 0,
            "median": scores_sorted[n // 2] if n else 0,
            "max": max(scores) if scores else 0,
            "n_positive": sum(1 for s in scores if s > 0),
        })
    out.sort(key=lambda x: -x["n"])
    return out


def gather_context(trigger: str, recent_n: int = 30, top_n: int = 30) -> DebateContext:
    """Gather rich context for the debate: registry summary + results stats +
    top entries + per-exit-family breakdown + Round 1+2 lessons."""
    run_id = time.strftime("debate_%Y%m%d_%H%M%S")
    registry = _load_registry()
    reg_summary = _summarize_registry(registry)
    res_summary, recent = _summarize_results(recent_n=recent_n)

    # Pull all rows for richer aggregations (not just last N)
    all_rows = []
    if RESULTS_TSV.exists():
        text = RESULTS_TSV.read_text(encoding="utf-8")
        for line in text.splitlines()[1:]:
            parts = line.split("\t")
            if len(parts) < 5:
                continue
            try:
                all_rows.append({
                    "commit": parts[0], "val_score": float(parts[1]),
                    "triggers": int(parts[2]), "status": parts[3],
                    "description": parts[4],
                })
            except (ValueError, IndexError):
                continue

    top_entries = _aggregate_top_entries(all_rows, registry, top_n=top_n)
    by_exit_fam = _aggregate_by_exit_family(all_rows)

    coverage_summary = {
        "n_total_results": len(all_rows),
        "top_entries_preview": [
            f"{e['entry_id']} {e['archetype'][:30]} ch={e['channel']}/{e['side']} "
            f"best={e['best_score']:+.3f} lift_vs_median={e['lift_vs_median']:+.3f} trig={e['triggers']}"
            for e in top_entries[:10]
        ],
        "by_exit_family": by_exit_fam,
        "lessons_from_r1_r2": [
            "R1 bug: ~50% of LLM-output novel_dim used unsupported fields (pretrend_*, "
            "burst_count_*, btc_*) — silently fell through filter, archetype became "
            "duplicate of channel/side baseline. FIXED by enforcing SUPPORTED_FIELDS.",
            "R2 finding (E126 paper): backtest score 0.3946 on E126 pc_pump_taker_buy_extreme_long "
            "(TP=0.51 SL=6.00 win=80%) compounded to -13.5% on $1000 paper account. "
            "Asymmetric TP/SL TRAP: legacy p25 metric blind to left tail. "
            "New metrics (mean, kelly_capped, p25_capped_tail) correctly penalize.",
            "R2 synthesizer self-identified gap: X101+ exit-side archetype pipeline starved "
            "relative to entry pipeline. Generator should propose more EXIT archetypes "
            "leveraging the 5 real exit kernels (fixed/time_only/breakeven/trail/multi_tp).",
        ],
    }

    return DebateContext(
        run_id=run_id,
        trigger=trigger,
        registry_summary=reg_summary,
        coverage_summary=coverage_summary,
        results_summary=res_summary,
        recent_experiments=recent,
        existing_archetype_ids=[r["id"] for r in registry],
    )


# ---------------------------------------------------------------------------
# Subprocess invocation
# ---------------------------------------------------------------------------

def _read_role_prompt(role: str) -> str:
    path = PROMPTS_DIR / f"role_{role}.md"
    if not path.exists():
        raise FileNotFoundError(
            f"Role prompt not found: {path}. Run Day 3.2 to write it."
        )
    return path.read_text(encoding="utf-8")


def call_claude(role: str, full_prompt: str, run_dir: Path, model: str | None = None) -> dict:
    """Invoke `claude -p` as subprocess; return parsed JSON output.

    The role prompt should instruct Claude to emit valid JSON as its only
    output. We attempt to parse stdout as JSON; on failure we save the raw
    text and return a minimal error-flag dict.
    """
    model = model or ROLE_MODELS.get(role, "claude-sonnet-4-6")
    # Windows command line limit is ~8192 chars. Long role prompts (~5K+)
    # get silently truncated when passed via `-p "<prompt>"`. Pass the
    # prompt via stdin and use `-p` without a positional argument.
    #
    # `--bare` disables plugin sync, hooks, auto-memory, CLAUDE.md discovery
    # `--disallowedTools` prevents file investigation
    # `--no-session-persistence` skips disk session state
    # `--effort max` enables maximum extended-thinking budget (Round 4+)
    # `--exclude-dynamic-system-prompt-sections` improves cross-call cache reuse
    effort = os.environ.get("BWE_LLM_EFFORT", "max")  # default: max thinking
    cmd = [
        CLAUDE_BIN,
        "-p",
        "--output-format", "json",
        "--max-turns", "1",
        "--model", model,
        "--effort", effort,
        "--exclude-dynamic-system-prompt-sections",
        "--disallowedTools", "Bash,Edit,Write,Read,Grep,Glob,NotebookEdit,WebFetch,WebSearch",
        "--no-session-persistence",
        "--append-system-prompt",
        "You are a strict role-playing JSON agent. The user message contains your role spec and inputs. Execute it directly and output ONLY a single JSON object as instructed. Do NOT ask clarifying questions, do NOT explain, do NOT use markdown fences, do NOT call any tools. Your response must be parseable as JSON.",
    ]
    raw_out_path = run_dir / f"_{role}_raw.txt"
    err_path = run_dir / f"_{role}_stderr.txt"

    env = os.environ.copy()
    if GIT_BASH_PATH and "CLAUDE_CODE_GIT_BASH_PATH" not in env:
        env["CLAUDE_CODE_GIT_BASH_PATH"] = GIT_BASH_PATH

    # Suppress Windows console window flash for each subprocess call
    # Triple-layer defense: CREATE_NO_WINDOW + DETACHED_PROCESS + STARTUPINFO/SW_HIDE.
    # Combined with claude.cmd preference (avoiding Git Bash POSIX wrapper),
    # this fully silences the spawn chain on Windows.
    creationflags = 0
    startupinfo = None
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE  # 0

    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300, encoding="utf-8",
            env=env, input=full_prompt,
            creationflags=creationflags, startupinfo=startupinfo,
        )
    except subprocess.TimeoutExpired:
        return {"_error": "timeout", "_role": role, "_elapsed_s": time.time() - t0}
    except FileNotFoundError:
        return {"_error": f"claude binary not found at {CLAUDE_BIN}", "_role": role}

    raw_out_path.write_text(proc.stdout or "", encoding="utf-8")
    err_path.write_text(proc.stderr or "", encoding="utf-8")
    elapsed = time.time() - t0

    if proc.returncode != 0:
        return {
            "_error": f"claude exit {proc.returncode}",
            "_stderr_tail": (proc.stderr or "")[-500:],
            "_role": role, "_elapsed_s": elapsed,
        }

    # Claude --output-format json returns a wrapper; extract result content.
    # Format: {"type": "result", "result": "<assistant text>", ...}
    raw = proc.stdout.strip()
    try:
        wrapper = json.loads(raw)
        # Extract assistant text — schema differs by Claude Code version
        assistant_text = wrapper.get("result") or wrapper.get("response") or ""
        if isinstance(wrapper.get("messages"), list):
            for msg in wrapper["messages"]:
                if msg.get("role") == "assistant":
                    if isinstance(msg.get("content"), list):
                        for c in msg["content"]:
                            if c.get("type") == "text":
                                assistant_text = c.get("text", assistant_text)
                    elif isinstance(msg.get("content"), str):
                        assistant_text = msg["content"]

        payload = _parse_assistant_json(assistant_text)
    except json.JSONDecodeError:
        payload = {"_error": "stdout is not JSON wrapper", "_raw_tail": raw[-500:]}

    payload["_role"] = role
    payload["_model"] = model
    payload["_elapsed_s"] = round(elapsed, 2)
    return payload


# ---------------------------------------------------------------------------
# Debate orchestration
# ---------------------------------------------------------------------------

def _build_role_prompt(role: str, context: DebateContext, prior_outputs: dict) -> str:
    """Render the role's template + JSON inputs into a single prompt string."""
    template = _read_role_prompt(role)
    inputs_block = json.dumps(
        {
            "context": {
                "trigger": context.trigger,
                "registry_summary": context.registry_summary,
                "coverage_summary": context.coverage_summary,
                "results_summary": context.results_summary,
                "recent_experiments": context.recent_experiments,
                "n_existing_archetypes": len(context.existing_archetype_ids),
            },
            "prior_outputs": prior_outputs,
        },
        ensure_ascii=False, indent=2,
    )
    return f"{template}\n\n# Inputs\n\n```json\n{inputs_block}\n```\n"


def _build_per_proposal_prompt(role: str, context: DebateContext, proposal: dict) -> str:
    """For per-proposal deep analysis: role gets ONE proposal to scrutinize.

    Same role template (devil/quant/risk/metric_critic), but inputs block
    contains only context + this single proposal (not all of them).
    """
    template = _read_role_prompt(role)
    inputs_block = json.dumps(
        {
            "context": {
                "trigger": context.trigger,
                "registry_summary": context.registry_summary,
                "coverage_summary": context.coverage_summary,
                "results_summary": context.results_summary,
                "n_existing_archetypes": len(context.existing_archetype_ids),
            },
            "proposal": proposal,
            "mode": "per_proposal_deep_analysis",
            "instructions": (
                "Focus ENTIRELY on this single proposal. Do not list multiple "
                "archetype reviews — your output JSON should reference only "
                "this one archetype's slug. Maximum reasoning depth on this "
                "single case."
            ),
        },
        ensure_ascii=False, indent=2,
    )
    return f"{template}\n\n# Inputs (per-proposal deep mode)\n\n```json\n{inputs_block}\n```\n"


def run_debate(
    trigger: str = "manual",
    recent_n: int = 30,
    dry_run: bool = False,
    deep: bool = False,
) -> dict:
    """Run the multi-role debate. Returns the synthesizer's output.

    Args:
        deep: if True, run per-proposal deep mode:
            Generator (1 call) → for each proposal:
              Devil (1 call) + Quant (1 call) + Risk (1 call) + MetricCritic (1 call)
            → Synthesizer (1 call sees per_proposal_critiques aggregate).
            Total calls: 2 + 4*N proposals (typically 50-60).
            If False (default), use legacy 5-role single-pass mode.
    """
    context = gather_context(trigger=trigger, recent_n=recent_n)
    run_dir = DEBATES_DIR / context.run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Save inputs
    (run_dir / "0_inputs.json").write_text(
        json.dumps(
            {
                "run_id": context.run_id, "trigger": context.trigger,
                "registry_summary": context.registry_summary,
                "coverage_summary": context.coverage_summary,
                "results_summary": context.results_summary,
                "recent_experiments": context.recent_experiments,
                "existing_archetype_ids_sample": context.existing_archetype_ids[:20],
                "models": ROLE_MODELS,
                "mode": "deep" if deep else "shallow",
            }, ensure_ascii=False, indent=2,
        ), encoding="utf-8",
    )

    if dry_run:
        print(f"[debate] DRY RUN — context saved to {run_dir / '0_inputs.json'}")
        return {"dry_run": True, "run_dir": str(run_dir)}

    if deep:
        return _run_debate_deep(context, run_dir)

    # Shallow (legacy) mode
    prior_outputs: dict = {}
    usage_rows = ["role,model,elapsed_s,error"]

    for i, role in enumerate(ROLE_ORDER, 1):
        print(f"[debate] role {i}/{len(ROLE_ORDER)}: {role} (model={ROLE_MODELS[role]})")
        prompt = _build_role_prompt(role, context, prior_outputs)
        out = call_claude(role, prompt, run_dir)
        out_path = run_dir / f"{i}_{role}.json"
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        prior_outputs[role] = out
        err = out.get("_error", "")
        usage_rows.append(f"{role},{out.get('_model', '')},{out.get('_elapsed_s', '')},{err}")
        if err:
            print(f"  ERROR in {role}: {err}")

    (run_dir / "llm_usage.csv").write_text("\n".join(usage_rows), encoding="utf-8")

    # Extract accepted archetypes from synthesizer output
    syn = prior_outputs.get("synthesizer", {})
    accepted = syn.get("accepted_archetypes", []) or syn.get("accept", [])
    rejected = syn.get("rejected_archetypes", []) or syn.get("reject", [])

    # Append accepted to a side-file (do NOT auto-write to main registry; user reviews)
    if accepted:
        new_path = run_dir / "new_archetypes.jsonl"
        with new_path.open("w", encoding="utf-8") as f:
            for a in accepted:
                f.write(json.dumps(a, ensure_ascii=False) + "\n")
        print(f"[debate] {len(accepted)} accepted archetypes -> {new_path}")
    if rejected:
        rej_path = run_dir / "rejected_archetypes.jsonl"
        with rej_path.open("w", encoding="utf-8") as f:
            for r in rejected:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"[debate] {len(rejected)} rejected -> {rej_path}")

    _write_transcript(run_dir, context, prior_outputs)
    print(f"[debate] complete -> {run_dir}")
    return {
        "run_dir": str(run_dir),
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "synthesizer_summary": syn.get("summary") or syn.get("_error", ""),
    }


def _validate_proposals_python(proposals: list[dict], existing_ids: set, existing_slugs: set) -> tuple[list[dict], list[dict]]:
    """Pre-submission Validator (E): Python rule-based filter on Generator output.
    Drops proposals that would clearly fail downstream (no LLM call needed).

    Returns (validated, skipped) where skipped contains a `_skip_reason`.
    """
    try:
        from bwe_autoresearch.bwe_loop_entry_filter import build_filter_expr
    except ImportError:
        # If filter module unavailable, skip validation
        return list(proposals), []

    validated, skipped = [], []
    for p in proposals:
        slug = p.get("archetype", "?")
        nd = p.get("novel_dim", [])
        ptype = p.get("type", "entry")

        # Duplicate name check
        if slug in existing_slugs:
            p["_skip_reason"] = f"duplicate name: {slug} already in registry"
            skipped.append(p)
            continue

        # Filter parseability check (entry / filter / cross_channel must
        # have at least 1 supported condition)
        if ptype in ("entry", "filter", "cross_channel") and isinstance(nd, list) and nd:
            try:
                expr, applied, _skipped_conds = build_filter_expr(nd, events_df=None)
                if len(applied) == 0:
                    p["_skip_reason"] = (
                        f"all {len(nd)} novel_dim conditions fall through filter "
                        f"(would equal channel/side baseline)"
                    )
                    skipped.append(p)
                    continue
            except Exception as e:
                # If filter check fails, let it through — better safe than over-strict
                pass

        validated.append(p)

    return validated, skipped


def _run_debate_deep(context: DebateContext, run_dir: Path) -> dict:
    """Per-proposal deep analysis mode with full Round 3 enhancements (A-E):
      0. Pattern Miner: orient generator (B)
      1. Generator: 15-20 proposals
      2. Pre-submission Validator: drop fall-through-only / duplicates (E)
      3. Per validated proposal: Steel-Man + Devil + Quant + Risk + MetricCritic (A)
      4. Synthesizer
      5. Self-Reflection: re-promote borderline rejects
      6. Behavior Annotator: per ACCEPTED archetype (C)
      7. Cross-Pair Recommender: top-10 (entry, exit) pairs (D)
    Total: 1 + 1 + 0 + 5N + 1 + 1 + N_accepted + 1 ≈ ~80 calls.
    """
    print(f"[debate] DEEP mode (Round 3 full) — pattern_miner + per-proposal critic stack")

    usage_rows = ["role,proposal_idx,model,elapsed_s,error"]
    deep_dir = run_dir / "per_proposal"
    deep_dir.mkdir(parents=True, exist_ok=True)

    # 0. Pattern Miner — orient Generator with real-data themes
    print(f"[debate] [0] pattern_miner (model={ROLE_MODELS['pattern_miner']})")
    pm_prompt = _build_role_prompt("pattern_miner", context, {})
    pm_out = call_claude("pattern_miner", pm_prompt, run_dir)
    (run_dir / "0_pattern_miner.json").write_text(
        json.dumps(pm_out, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    usage_rows.append(
        f"pattern_miner,-,{pm_out.get('_model', '')},{pm_out.get('_elapsed_s', '')},{pm_out.get('_error', '')}"
    )

    # 1. Generator (single call, sees pattern_miner output, asks for 15-20 proposals)
    print(f"[debate] [1] generator (model={ROLE_MODELS['generator']})")
    gen_prompt = _build_role_prompt("generator", context, {"pattern_miner": pm_out})
    gen_out = call_claude("generator", gen_prompt, run_dir)
    (run_dir / "1_generator.json").write_text(
        json.dumps(gen_out, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    usage_rows.append(
        f"generator,-,{gen_out.get('_model', '')},{gen_out.get('_elapsed_s', '')},{gen_out.get('_error', '')}"
    )
    if gen_out.get("_error"):
        print(f"  GENERATOR FAILED: {gen_out['_error']}")
        return {"run_dir": str(run_dir), "accepted_count": 0, "rejected_count": 0,
                "synthesizer_summary": f"generator failed: {gen_out['_error']}"}

    proposals = gen_out.get("proposals", [])
    print(f"[debate] generator output: {len(proposals)} proposals")
    if not proposals:
        return {"run_dir": str(run_dir), "accepted_count": 0, "rejected_count": 0,
                "synthesizer_summary": "no proposals from generator"}

    # 2. Pre-submission Validator (Python rule-based; saves wasted critic calls)
    registry = _load_registry()
    existing_ids = {r["id"] for r in registry}
    existing_slugs = {r["archetype"] for r in registry}
    validated, presub_skipped = _validate_proposals_python(proposals, existing_ids, existing_slugs)
    print(f"[debate] [2] pre-submission validator: {len(validated)}/{len(proposals)} pass; "
          f"{len(presub_skipped)} skipped (no critic calls wasted)")
    if presub_skipped:
        skip_path = run_dir / "presub_skipped.jsonl"
        with skip_path.open("w", encoding="utf-8") as f:
            for p in presub_skipped:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")
    proposals = validated

    if not proposals:
        return {"run_dir": str(run_dir), "accepted_count": 0, "rejected_count": 0,
                "synthesizer_summary": "all proposals filtered by pre-submission validator"}

    # 3. For each proposal, run 5 critics (steelman, devil, quant, risk, metric_critic)
    per_proposal_critiques: dict = {}
    for p_idx, prop in enumerate(proposals):
        slug = prop.get("archetype", f"prop_{p_idx}")
        print(f"\n[debate] === proposal {p_idx + 1}/{len(proposals)}: {slug} ===")
        per_proposal_critiques[p_idx] = {"proposal": prop}
        for role in PER_PROPOSAL_ROLES:
            print(f"  [{role}] (model={ROLE_MODELS[role]})")
            prompt = _build_per_proposal_prompt(role, context, prop)
            out = call_claude(role, prompt, run_dir)
            crit_path = deep_dir / f"prop{p_idx:02d}_{role}.json"
            crit_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
            per_proposal_critiques[p_idx][role] = out
            err = out.get("_error", "")
            usage_rows.append(
                f"{role},{p_idx},{out.get('_model', '')},{out.get('_elapsed_s', '')},{err}"
            )
            if err:
                print(f"    ERROR: {err}")

    # Save aggregate per-proposal data for synthesizer input
    (run_dir / "2_per_proposal_critiques.json").write_text(
        json.dumps(per_proposal_critiques, ensure_ascii=False, indent=2), encoding="utf-8",
    )

    # 3. Synthesizer (single call, sees full per-proposal aggregate)
    print(f"\n[debate] [final] synthesizer (model={ROLE_MODELS['synthesizer']})")
    syn_inputs = {
        "generator": gen_out,
        "per_proposal_critiques": per_proposal_critiques,
        "_note": (
            "DEEP MODE: each of the proposals above was reviewed by 4 specialist "
            "critics (devil, quant, risk, metric_critic) — see per_proposal_critiques. "
            "Make accept/revise/reject decisions based on the FULL critic stack per "
            "proposal, not just summary stats."
        ),
    }
    syn_prompt = _build_role_prompt("synthesizer", context, syn_inputs)
    syn_out = call_claude("synthesizer", syn_prompt, run_dir)
    (run_dir / "3_synthesizer.json").write_text(
        json.dumps(syn_out, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    usage_rows.append(
        f"synthesizer,-,{syn_out.get('_model', '')},{syn_out.get('_elapsed_s', '')},{syn_out.get('_error', '')}"
    )
    (run_dir / "llm_usage.csv").write_text("\n".join(usage_rows), encoding="utf-8")

    # Extract accepted from synthesizer
    accepted = syn_out.get("accepted_archetypes", []) or syn_out.get("accept", [])
    rejected = syn_out.get("rejected_archetypes", []) or syn_out.get("reject", [])

    # 4. Self-reflection pass — second-guess only in the inclusive direction
    print(f"\n[debate] [self-reflection] reviewing rejects for missed alpha")
    reflection_inputs = {
        "synthesizer_output": syn_out,
        "proposals_reference": [pp.get("proposal") for pp in per_proposal_critiques.values()],
    }
    refl_prompt = _build_role_prompt("self_reflection", context, reflection_inputs)
    refl_out = call_claude("self_reflection", refl_prompt, run_dir)
    (run_dir / "4_self_reflection.json").write_text(
        json.dumps(refl_out, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    usage_rows.append(
        f"self_reflection,-,{refl_out.get('_model', '')},{refl_out.get('_elapsed_s', '')},{refl_out.get('_error', '')}"
    )

    promotions = refl_out.get("promotions", [])
    if promotions:
        print(f"[debate] self-reflection promoted {len(promotions)} rejected proposals back to accept")

    (run_dir / "llm_usage.csv").write_text("\n".join(usage_rows), encoding="utf-8")

    # Combine accepted + promotions for final acceptance set
    final_accepted = list(accepted) + list(promotions)

    if final_accepted:
        new_path = run_dir / "new_archetypes.jsonl"
        KEEP = {"id", "type", "archetype", "channel", "side", "novel_dim",
                "expected_distinct", "notes", "synthesizer_note",
                "constraint_recommendation"}
        with new_path.open("w", encoding="utf-8") as f:
            for a in final_accepted:
                clean = {k: a[k] for k in KEEP if k in a}
                f.write(json.dumps(clean, ensure_ascii=False) + "\n")
        print(f"\n[debate] {len(final_accepted)} accepted (incl. {len(promotions)} promotions) -> {new_path}")
    if rejected:
        promoted_slugs = {p.get("archetype") for p in promotions}
        final_rejected = [r for r in rejected
                          if r.get("archetype_ref") not in promoted_slugs
                          and r.get("archetype") not in promoted_slugs]
        if final_rejected:
            rej_path = run_dir / "rejected_archetypes.jsonl"
            with rej_path.open("w", encoding="utf-8") as f:
                for r in final_rejected:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
            print(f"[debate] {len(final_rejected)} final rejected -> {rej_path}")

    # 6. Behavior Annotator — for each ACCEPTED archetype, predict trading behavior
    annotations = []
    if final_accepted:
        print(f"\n[debate] [6] behavior_annotator x {len(final_accepted)} accepted archetypes")
        annot_dir = run_dir / "annotations"
        annot_dir.mkdir(parents=True, exist_ok=True)
        for i, arch in enumerate(final_accepted):
            slug = arch.get("archetype", f"prop_{i}")
            ann_prompt = _build_per_proposal_prompt("behavior_annotator", context, arch)
            ann_out = call_claude("behavior_annotator", ann_prompt, run_dir)
            (annot_dir / f"accepted{i:02d}_{slug[:30]}.json").write_text(
                json.dumps(ann_out, ensure_ascii=False, indent=2), encoding="utf-8",
            )
            annotations.append({"archetype": arch, "annotation": ann_out})
            usage_rows.append(
                f"behavior_annotator,{i},{ann_out.get('_model', '')},{ann_out.get('_elapsed_s', '')},{ann_out.get('_error', '')}"
            )

    # 7. Cross-Pair Recommender — top 10 (entry, exit) pairs to test
    print(f"\n[debate] [7] cross_pair_recommender (final ranking step)")
    cpr_inputs = {
        "accepted_archetypes": final_accepted,
        "annotations": annotations,
        "current_top_winners_preview": context.coverage_summary.get("top_entries_preview", []),
    }
    cpr_prompt = _build_role_prompt("cross_pair_recommender", context, cpr_inputs)
    cpr_out = call_claude("cross_pair_recommender", cpr_prompt, run_dir)
    (run_dir / "5_cross_pair_recommender.json").write_text(
        json.dumps(cpr_out, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    usage_rows.append(
        f"cross_pair_recommender,-,{cpr_out.get('_model', '')},{cpr_out.get('_elapsed_s', '')},{cpr_out.get('_error', '')}"
    )

    # Write final usage CSV (overwrites earlier stub)
    (run_dir / "llm_usage.csv").write_text("\n".join(usage_rows), encoding="utf-8")

    _write_transcript_deep(run_dir, context, gen_out, per_proposal_critiques, syn_out)
    print(f"[debate] complete -> {run_dir}")
    n_calls = 2 + len(PER_PROPOSAL_ROLES) * len(proposals) + 1 + 1 + len(final_accepted) + 1
    return {
        "run_dir": str(run_dir),
        "accepted_count": len(final_accepted),
        "promotions_count": len(promotions),
        "rejected_count": max(0, len(rejected) - len(promotions)),
        "presub_skipped": len(presub_skipped),
        "n_proposals_after_validation": len(proposals),
        "n_proposals_original": len(gen_out.get("proposals", [])),
        "n_annotations": len(annotations),
        "n_calls": n_calls,
        "pattern_miner_summary": pm_out.get("summary") or pm_out.get("_error", ""),
        "synthesizer_summary": syn_out.get("summary") or syn_out.get("_error", ""),
        "self_reflection_summary": refl_out.get("summary") or refl_out.get("_error", ""),
        "cross_pair_summary": cpr_out.get("summary") or cpr_out.get("_error", ""),
    }


def _write_transcript_deep(run_dir, context, gen_out, per_proposal_critiques, syn_out):
    lines = [
        f"# DEEP Debate transcript: {context.run_id}",
        "",
        f"- Trigger: `{context.trigger}`",
        f"- Mode: per-proposal deep analysis ({2 + 4 * len(per_proposal_critiques)} LLM calls)",
        f"- Models: {ROLE_MODELS}",
        f"- Existing archetypes: {context.registry_summary['total']} total",
        "",
        "## Generator output",
        "",
    ]
    clean_gen = {k: v for k, v in gen_out.items() if not k.startswith("_")}
    lines += ["```json", json.dumps(clean_gen, ensure_ascii=False, indent=2), "```", ""]

    for p_idx, data in per_proposal_critiques.items():
        prop = data.get("proposal", {})
        slug = prop.get("archetype", f"prop_{p_idx}")
        lines += [f"## Proposal {p_idx + 1}: `{slug}`", ""]
        lines += ["### proposal", "```json",
                  json.dumps(prop, ensure_ascii=False, indent=2), "```", ""]
        for role in PER_PROPOSAL_ROLES:
            crit = {k: v for k, v in data.get(role, {}).items() if not k.startswith("_")}
            lines += [f"### {role}", "```json",
                      json.dumps(crit, ensure_ascii=False, indent=2), "```", ""]

    lines += ["## Synthesizer", "```json",
              json.dumps({k: v for k, v in syn_out.items() if not k.startswith("_")},
                         ensure_ascii=False, indent=2),
              "```"]
    (run_dir / "debate_log.md").write_text("\n".join(lines), encoding="utf-8")


def _write_transcript(run_dir: Path, context: DebateContext, outputs: dict) -> None:
    """Human-readable markdown transcript."""
    lines = [
        f"# Debate transcript: {context.run_id}",
        "",
        f"- Trigger: `{context.trigger}`",
        f"- Models: {ROLE_MODELS}",
        f"- Existing archetypes: {context.registry_summary['total']} total",
        f"- Results so far: {context.results_summary}",
        "",
    ]
    for i, role in enumerate(ROLE_ORDER, 1):
        out = outputs.get(role, {})
        lines += [
            f"## {i}. {role.capitalize()} (model={out.get('_model', '?')}, {out.get('_elapsed_s', '?')}s)",
            "",
        ]
        if out.get("_error"):
            lines += [f"**ERROR**: `{out['_error']}`", ""]
        # Render whatever fields the role produced
        clean = {k: v for k, v in out.items() if not k.startswith("_")}
        lines += ["```json", json.dumps(clean, ensure_ascii=False, indent=2), "```", ""]

    (run_dir / "debate_log.md").write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reason", type=str, default="manual",
                    help="Trigger reason logged with the debate.")
    ap.add_argument("--recent-n", type=int, default=30,
                    help="How many recent results.tsv rows to include.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Save context only, do not call Claude.")
    ap.add_argument("--deep", action="store_true",
                    help="Per-proposal deep mode: ~50 LLM calls instead of 5. "
                         "Each Generator proposal gets reviewed individually by "
                         "Devil/Quant/Risk/MetricCritic before Synthesizer decides.")
    args = ap.parse_args()

    res = run_debate(trigger=args.reason, recent_n=args.recent_n, dry_run=args.dry_run,
                     deep=args.deep)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
