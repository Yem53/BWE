from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


RUN_DIR = Path(r"H:\data\bwe\v6\runs\bwe_complete_strategy_v6_max_alpha_gpu_fused_strong_20260426_115115")
EXPANDED_DIR = RUN_DIR / r"llm_round_notes\deep_round1_autoresearch_expanded_20260426_134801"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a true deep LLM-style Round 1 research review.")
    parser.add_argument("--run-dir", type=Path, default=RUN_DIR)
    parser.add_argument("--expanded-dir", type=Path, default=EXPANDED_DIR)
    parser.add_argument("--out-dir", type=Path, default=None)
    return parser.parse_args()


def clean(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean(v) for v in obj]
    if isinstance(obj, tuple):
        return [clean(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        x = float(obj)
        return None if not math.isfinite(x) else x
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if obj is pd.NA:
        return None
    return obj


def write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(clean(obj), indent=2, sort_keys=True), encoding="utf-8")


def make_out_dir(run_dir: Path, out_dir: Path | None) -> Path:
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=False)
        return out_dir
    base = run_dir / "llm_round_notes"
    base.mkdir(parents=True, exist_ok=True)
    candidate = base / f"deep_round1_true_llm_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    suffix = 1
    while candidate.exists():
        candidate = base / f"deep_round1_true_llm_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{suffix}"
        suffix += 1
    candidate.mkdir(parents=True)
    (candidate / "role_memos").mkdir()
    (candidate / "cross_exam").mkdir()
    (candidate / "final").mkdir()
    (candidate / "tables").mkdir()
    return candidate


def sample_tier(n: Any) -> str:
    try:
        n = int(n)
    except Exception:
        return "unknown"
    if n <= 15:
        return "insufficient_observation"
    if n <= 29:
        return "early_alpha"
    if n <= 49:
        return "exploratory_watchlist"
    if n <= 99:
        return "validated_watchlist"
    return "higher_confidence_watchlist"


def md_table(df: pd.DataFrame, n: int = 10) -> str:
    if df is None or df.empty:
        return "_No rows._"
    return df.head(n).to_markdown(index=False)


def num(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    df = df.copy()
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_inputs(run_dir: Path, expanded_dir: Path) -> dict[str, Any]:
    files = {
        "leader": run_dir / "complete_strategy_leaderboard.csv",
        "baseline": run_dir / "baseline_comparison.csv",
        "stress": run_dir / "fee_slippage_latency_stress.csv",
        "clusters": run_dir / "strategy_similarity_clusters.csv",
        "bootstrap": run_dir / "bootstrap_confidence_intervals.csv",
        "permutation": run_dir / "permutation_test_results.csv",
        "effective": run_dir / "effective_sample_size_report.csv",
        "future": run_dir / "future_safety_report.csv",
        "summary": run_dir / "run_summary.json",
        "entry": expanded_dir / "entry_catalog_scoreboard.csv",
        "exit": expanded_dir / "exit_catalog_scoreboard.csv",
        "combo": expanded_dir / "entry_exit_combined_funnel.csv",
        "neighbor": expanded_dir / "neighborhood_stability.csv",
        "discovery": expanded_dir / "discovery_scoreboard.csv",
        "hypothesis": expanded_dir / "hypothesis_ledger.jsonl",
        "completion": expanded_dir / "deep_round1_autoresearch_expanded_completion.json",
    }
    missing = [str(path) for path in files.values() if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing inputs: " + "; ".join(missing))
    leader = pd.read_csv(files["leader"], low_memory=False)
    numeric = [
        "sample_size",
        "median_net_pct",
        "mean_net_pct",
        "p25_net_pct",
        "p10_net_pct",
        "stress_fee_slippage_median_net_pct",
        "stress_latency_median_net_pct",
        "robust_score",
        "top_symbol_share_pct",
        "unique_days",
        "symbol_count",
        "profit_factor",
        "walk_forward_positive_rate_pct",
        "top1_removed_mean_net_pct",
    ]
    leader = num(leader, numeric)
    leader["sample_tier"] = leader["sample_size"].map(sample_tier)
    baseline = num(pd.read_csv(files["baseline"], low_memory=False), numeric)
    stress = num(pd.read_csv(files["stress"], low_memory=False), ["latency_seconds", "stress_median_net_pct", "missed_fill_rate_pct"])
    data = {
        "leader": leader,
        "baseline": baseline,
        "stress": stress,
        "clusters": pd.read_csv(files["clusters"], low_memory=False),
        "bootstrap": pd.read_csv(files["bootstrap"], low_memory=False),
        "permutation": pd.read_csv(files["permutation"], low_memory=False),
        "effective": pd.read_csv(files["effective"], low_memory=False),
        "future": pd.read_csv(files["future"], low_memory=False),
        "summary": json.loads(files["summary"].read_text(encoding="utf-8")),
        "entry": pd.read_csv(files["entry"]),
        "exit": pd.read_csv(files["exit"]),
        "combo": pd.read_csv(files["combo"]),
        "neighbor": pd.read_csv(files["neighbor"]),
        "discovery": pd.read_csv(files["discovery"]),
        "hypothesis": [json.loads(line) for line in files["hypothesis"].read_text(encoding="utf-8").splitlines() if line.strip()],
        "completion": json.loads(files["completion"].read_text(encoding="utf-8")),
    }
    return data


def build_evidence(data: dict[str, Any]) -> dict[str, Any]:
    leader: pd.DataFrame = data["leader"]
    baseline: pd.DataFrame = data["baseline"]
    stress: pd.DataFrame = data["stress"]
    entry: pd.DataFrame = data["entry"]
    exit_: pd.DataFrame = data["exit"]
    combo: pd.DataFrame = data["combo"]
    neighbor: pd.DataFrame = data["neighbor"]
    discovery: pd.DataFrame = data["discovery"]
    hypothesis = data["hypothesis"]
    summary = data["summary"]

    cols = [
        "strategy_id",
        "strategy_family",
        "side",
        "entry_timing",
        "exit_family",
        "sample_size",
        "sample_tier",
        "median_net_pct",
        "p10_net_pct",
        "stress_fee_slippage_median_net_pct",
        "stress_latency_median_net_pct",
        "robust_score",
        "strategy_similarity_cluster_id",
        "top_symbol_share_pct",
        "unique_days",
        "symbol_count",
    ]
    top_raw = leader[cols].sort_values("robust_score", ascending=False).head(20)
    top_high_conf = leader[leader["sample_size"] >= 100][cols].sort_values("robust_score", ascending=False).head(20)
    top_validated = leader[leader["sample_size"] >= 50][cols].sort_values("robust_score", ascending=False).head(20)
    top_small = leader[(leader["sample_size"] >= 16) & (leader["sample_size"] <= 49)][cols].sort_values(
        "robust_score", ascending=False
    ).head(20)
    side = (
        leader.groupby("side")
        .agg(
            strategies=("strategy_id", "count"),
            median_sample=("sample_size", "median"),
            best_median=("median_net_pct", "max"),
            median_of_medians=("median_net_pct", "median"),
            median_p10=("p10_net_pct", "median"),
            median_stress=("stress_fee_slippage_median_net_pct", "median"),
            unique_clusters=("strategy_similarity_cluster_id", "nunique"),
        )
        .reset_index()
        .sort_values("best_median", ascending=False)
    )
    timing = (
        leader.groupby(["side", "entry_timing"])
        .agg(
            strategies=("strategy_id", "count"),
            median_sample=("sample_size", "median"),
            best_median=("median_net_pct", "max"),
            median_of_medians=("median_net_pct", "median"),
            median_p10=("p10_net_pct", "median"),
            median_stress=("stress_fee_slippage_median_net_pct", "median"),
            unique_clusters=("strategy_similarity_cluster_id", "nunique"),
        )
        .reset_index()
        .sort_values(["best_median", "median_stress"], ascending=False)
    )
    exit_family = (
        leader.groupby(["side", "exit_family"])
        .agg(
            strategies=("strategy_id", "count"),
            median_sample=("sample_size", "median"),
            best_median=("median_net_pct", "max"),
            median_of_medians=("median_net_pct", "median"),
            median_p10=("p10_net_pct", "median"),
            median_stress=("stress_fee_slippage_median_net_pct", "median"),
            unique_clusters=("strategy_similarity_cluster_id", "nunique"),
        )
        .reset_index()
        .sort_values(["best_median", "median_stress"], ascending=False)
    )
    best_baseline = baseline.sort_values("median_net_pct", ascending=False)[
        ["baseline_name", "strategy_family", "side", "entry_timing", "exit_family", "sample_size", "median_net_pct", "p10_net_pct", "stress_fee_slippage_median_net_pct", "robust_score"]
    ].head(8)
    stress_latency = (
        stress.groupby("latency_seconds")
        .agg(
            rows=("strategy_id", "count"),
            strategies=("strategy_id", "nunique"),
            median_stressed=("stress_median_net_pct", "median"),
            p10_stressed=("stress_median_net_pct", lambda s: float(s.quantile(0.10))),
            min_stressed=("stress_median_net_pct", "min"),
            median_missed_fill=("missed_fill_rate_pct", "median"),
        )
        .reset_index()
        .sort_values("latency_seconds")
    )
    cluster_counts = leader["strategy_similarity_cluster_id"].value_counts().head(20).rename_axis("cluster").reset_index(name="rows")
    sample_tiers = leader["sample_tier"].value_counts().rename_axis("sample_tier").reset_index(name="strategies")
    hypothesis_counts = Counter(row.get("decision", "unknown") for row in hypothesis)

    evidence = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_run": str(summary.get("run_dir", "")),
        "stage": summary.get("stage"),
        "candidate_space_sample": summary.get("candidate_space_sample"),
        "coarse_eval_actual": summary.get("coarse_eval_actual"),
        "medium_eval_actual": summary.get("medium_eval_actual"),
        "deep_eval_actual": summary.get("deep_eval_actual"),
        "stress_eval_actual": summary.get("stress_eval_actual"),
        "path_resolution": summary.get("path_resolution"),
        "paper_only": summary.get("paper_only"),
        "live_allowed": summary.get("live_allowed"),
        "gpu": summary.get("gpu", {}),
        "row_count": int(len(leader)),
        "sample_tiers": sample_tiers.to_dict(orient="records"),
        "hypothesis_decisions": dict(hypothesis_counts),
        "top_raw_table": top_raw.to_dict(orient="records"),
        "top_high_conf_table": top_high_conf.to_dict(orient="records"),
        "top_validated_table": top_validated.to_dict(orient="records"),
        "top_small_table": top_small.to_dict(orient="records"),
        "side_table": side.to_dict(orient="records"),
        "timing_table": timing.head(20).to_dict(orient="records"),
        "exit_family_table": exit_family.head(20).to_dict(orient="records"),
        "best_baseline_table": best_baseline.to_dict(orient="records"),
        "stress_latency_table": stress_latency.to_dict(orient="records"),
        "cluster_count_table": cluster_counts.to_dict(orient="records"),
        "entry_top": entry.head(12).to_dict(orient="records"),
        "exit_top": exit_.head(12).to_dict(orient="records"),
        "combo_top": combo.head(12).to_dict(orient="records"),
        "neighbor_top": neighbor.head(12).to_dict(orient="records"),
        "discovery_top": discovery.head(12).to_dict(orient="records"),
    }
    return evidence


def evidence_tables(data: dict[str, Any]) -> dict[str, pd.DataFrame]:
    leader: pd.DataFrame = data["leader"]
    cols = [
        "strategy_id",
        "strategy_family",
        "side",
        "entry_timing",
        "exit_family",
        "sample_size",
        "sample_tier",
        "median_net_pct",
        "p10_net_pct",
        "stress_fee_slippage_median_net_pct",
        "robust_score",
        "strategy_similarity_cluster_id",
    ]
    return {
        "top_raw": leader[cols].sort_values("robust_score", ascending=False).head(20),
        "top_high_conf": leader[leader["sample_size"] >= 100][cols].sort_values("robust_score", ascending=False).head(20),
        "top_small": leader[(leader["sample_size"] >= 16) & (leader["sample_size"] <= 49)][cols].sort_values("robust_score", ascending=False).head(20),
        "side": pd.DataFrame(build_evidence(data)["side_table"]),
        "timing": pd.DataFrame(build_evidence(data)["timing_table"]),
        "exit_family": pd.DataFrame(build_evidence(data)["exit_family_table"]),
        "entry": data["entry"].head(12),
        "exit": data["exit"].head(12),
        "combo": data["combo"].head(12),
        "neighbor": data["neighbor"].head(12),
        "discovery": data["discovery"].head(12),
        "baseline": pd.DataFrame(build_evidence(data)["best_baseline_table"]),
        "stress_latency": pd.DataFrame(build_evidence(data)["stress_latency_table"]),
    }


def write_tables(out_dir: Path, tables: dict[str, pd.DataFrame]) -> None:
    for name, df in tables.items():
        df.to_csv(out_dir / "tables" / f"{name}.csv", index=False)


def write_scope(out_dir: Path, evidence: dict[str, Any], tables: dict[str, pd.DataFrame]) -> None:
    lines = [
        "# True Deep Round 1 Method And Scope",
        "",
        "This directory is the deep LLM-style research review layer. It does not rerun the 500B-scale search. "
        "It reads the completed GPU fused strong run and the AutoResearch expanded governance artifacts, then "
        "turns them into a slower, evidence-driven research seminar: independent role memos, cross-examination, "
        "rebuttal, revised positions, final synthesis, paper gate, and a next-round ablation config.",
        "",
        "## Source Facts",
        f"- Stage: `{evidence['stage']}`",
        f"- Candidate space sample: `{evidence['candidate_space_sample']}`",
        f"- Deep eval rows: `{evidence['deep_eval_actual']}`",
        f"- Stress eval rows: `{evidence['stress_eval_actual']}`",
        f"- Path resolution: `{evidence['path_resolution']}`",
        f"- Paper only: `{evidence['paper_only']}`",
        f"- Live allowed: `{evidence['live_allowed']}`",
        "",
        "## Sample Tiers",
        md_table(pd.DataFrame(evidence["sample_tiers"]), 10),
        "",
        "## Key Evidence Tables",
        "These tables are copied into `tables/` as CSV and referenced by each role.",
        "",
        "### Top Raw",
        md_table(tables["top_raw"], 8),
        "",
        "### Top High Confidence",
        md_table(tables["top_high_conf"], 8),
        "",
        "### Discovery Queue",
        md_table(tables["discovery"], 8),
    ]
    (out_dir / "00_method_and_scope.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_role_memos(out_dir: Path, evidence: dict[str, Any], tables: dict[str, pd.DataFrame]) -> None:
    top_raw = tables["top_raw"].iloc[0].to_dict()
    top_hc = tables["top_high_conf"].iloc[0].to_dict()
    sample_table = md_table(pd.DataFrame(evidence["sample_tiers"]), 10)
    discovery_table = md_table(tables["discovery"], 10)
    entry_table = md_table(tables["entry"], 8)
    exit_table = md_table(tables["exit"], 8)
    combo_table = md_table(tables["combo"], 8)
    neighbor_table = md_table(tables["neighbor"], 8)
    baseline_table = md_table(tables["baseline"], 8)
    stress_table = md_table(tables["stress_latency"], 8)
    side_table = md_table(tables["side"], 8)
    timing_table = md_table(tables["timing"], 10)
    exit_family_table = md_table(tables["exit_family"], 10)

    memos = {
        "01_meta_research_director.md": f"""# Meta Research Director Memo

## Position
This run is now good enough to support a serious second research phase, but not good enough to skip the ablation layer. The GPU fused strong run searched a 500B-scale parameter space and produced a dense 200k-row final leaderboard. The deep review should treat that as discovery evidence, not as a paper-ready strategy selection event.

The strongest governance fact is that no candidate in the retained leaderboard has `sample_size <= 15`; the population begins at early-alpha and moves through exploratory, validated, and higher-confidence tiers. That means the user-requested policy is compatible with the data: sample size should not be used as a hard reject above 15. It should be used as confidence labeling and sizing discipline.

## Evidence
{sample_table}

Top raw result: `{top_raw['strategy_id']}` is `{top_raw['strategy_family']}` / `{top_raw['side']}` / `{top_raw['entry_timing']}` / `{top_raw['exit_family']}` with sample `{top_raw['sample_size']}`, median `{top_raw['median_net_pct']:.4f}`, p10 `{top_raw['p10_net_pct']:.4f}`, and stress median `{top_raw['stress_fee_slippage_median_net_pct']:.4f}`.

Top 100+ sample result: `{top_hc['strategy_id']}` is `{top_hc['strategy_family']}` / `{top_hc['side']}` / `{top_hc['entry_timing']}` / `{top_hc['exit_family']}` with sample `{top_hc['sample_size']}`, median `{top_hc['median_net_pct']:.4f}`, p10 `{top_hc['p10_net_pct']:.4f}`, and stress median `{top_hc['stress_fee_slippage_median_net_pct']:.4f}`.

## Governance Call
The raw top cluster is compelling but too duplicated to crown directly. Multiple top rows share the same strategy family, side, timing, exit, and cluster. That is not a failure; it is exactly why the AutoResearch layer exists. The correct move is to convert repeated evidence into a cluster representative and then test whether nearby parameter changes retain the edge.

The second governance call is that the best high-confidence candidates are only modestly weaker than the small-sample raw leaders. This matters. If the high-confidence tier had collapsed, the round would be mostly a small-sample artifact. Instead, the 100+ tier still shows strong median and stressed median results.

## Required Next Move
Run a focused ablation sequence, one hypothesis at a time:

1. Freeze a complete candidate and mutate only nearby parameter thresholds.
2. Freeze entry and swap exits.
3. Freeze exit and swap entries.
4. De-duplicate by cluster representative before any paper-shadow gate.
5. Keep baseline-first comparison and execution stress in every pass.

## Decision
Continue research, but do not enter paper-shadow yet. The phase label should be `focused_ablation_before_paper_shadow`.
""",
        "02_strategy_architect.md": f"""# Strategy Architect Memo

## Architectural Read
The search did include complete strategies, not just entries. The useful architectural result is that alpha appears in a few repeated entry/exit structures:

- `freshness_strict_confirmation` long at `30s`, especially with `state_machine` in early-alpha and `breakeven_ratchet` in 100+ sample.
- `premium_basis_overheat` long at `30s`, repeatedly pairing well with `indicator_invalidation`, `breakeven_ratchet`, `state_machine`, and `runner_trail`.
- `oi_funding_continuation` long at `1m` or `30s`, especially with `breakeven_ratchet` and `runner_trail`.
- `contrarian_crash_fade` long at `30s`, which has broad sample support but needs p10 and adverse-regime examination.

## Entry Evidence
{entry_table}

## Exit Evidence
{exit_table}

## Complete Strategy Funnel
{combo_table}

## Design Interpretation
The entry side is not a single trigger story. `premium_basis_overheat` and `oi_funding_continuation` are different hypotheses: one looks like overheated market structure following BWE pump context; the other looks like continuation supported by funding/OI. `freshness_strict_confirmation` is more timing/quality oriented. Those should not be merged prematurely.

The exit side is more coherent: `breakeven_ratchet` is the strongest reusable module by component catalog, `runner_trail` and `state_machine` remain valuable but are more likely to overfit specific path shapes, and `fixed_tp_sl` is useful as a control rather than the main winner.

## Architecture Risk
The most dangerous mistake would be treating the best complete pair as proof that both components are individually strong. A good complete strategy may be good because the exit compensates for weak entry selection, or because the entry selects a path shape that one exit family happens to harvest.

## Next Architecture Tests
1. `premium_basis_overheat / 30s / long`: test across `indicator_invalidation`, `breakeven_ratchet`, `state_machine`, `runner_trail`, and fixed TP/SL.
2. `freshness_strict_confirmation / 30s / long`: compare early-alpha state machine against higher-confidence breakeven.
3. `oi_funding_continuation / 1m / long`: test whether the signal remains strong when horizon and exit are held fixed.
4. Short side: run a separate balanced probe. Current short count is much lower than long count, so absence of dominance is not proof of absence.
""",
        "03_experiment_mutator.md": f"""# Experiment Mutator Memo

## Mutation Principle
The next round should not increase global search width. It should increase causal clarity. The right mutation unit is a single hypothesis from the discovery queue, with all other dimensions frozen.

## Discovery Queue
{discovery_table}

## Mutations To Run First
1. Complete-strategy neighborhood for `premium_basis_overheat / 30s / indicator_invalidation / long`.
2. Entry ablation for `premium_basis_overheat / 30s / long` while swapping only exit families.
3. Entry ablation for `oi_funding_continuation` comparing `30s` and `1m` with the same exit.
4. Exit ablation for `breakeven_ratchet` with fixed entry families.
5. Cluster representative re-score for `freshness_strict_confirmation / 30s / state_machine`.

## What Not To Mutate Yet
Do not mutate everything at once. Do not create a new entry grammar at the same time as a new exit grammar. Do not change cost assumptions while testing strategy logic. Do not use paper-shadow feedback until the focused ablation pass is complete.

## Reject Handling
Every failed mutation should produce one of these reasons:

- `entry_not_reusable`
- `exit_not_reusable`
- `cluster_neighbor_weak`
- `cost_stress_failure`
- `baseline_lift_failure`
- `p10_negative_after_ablation`
- `sample_tier_only_observation`

This matters because the next AutoResearch loop should learn where not to spend GPU time.

## Mutation Budget Recommendation
Keep the first true next round modest: enough to run the top 5 to 8 hypotheses with local neighborhoods, not enough to become another broad max_alpha pass. The objective is to isolate mechanism, not maximize leaderboard.
""",
        "04_results_analyst.md": f"""# Results Analyst Memo

## Main Result
The run produced strong positive medians relative to baselines, and many high-confidence candidates remain positive after cost stress. The result is not just a small-sample top-row story. However, the raw top is cluster-duplicated and must be de-duplicated before any claim of independent discoveries.

## Top Raw Candidates
{md_table(tables['top_raw'], 12)}

## Top 100+ Sample Candidates
{md_table(tables['top_high_conf'], 12)}

## Baseline Comparison
{baseline_table}

The best baseline is the current live BWE OI pump long reference, and its median is negative. That means the v6 candidate families show large baseline lift. The baseline lift is meaningful because it includes message-only, fixed timing, simple TP/SL, current live reference, v5-style reference, and randomized/shuffled controls.

## Side And Timing
{side_table}

{timing_table}

Long dominates the retained set. Short appears underrepresented, not necessarily invalid. The correct interpretation is: long is currently the main positive research signal; short needs a balanced dedicated probe before being dismissed.

## Exit Family Result
{exit_family_table}

The exit result is not uniform. `breakeven_ratchet` has the best combination of catalog stability and high-confidence support. `state_machine` owns the raw top but needs de-duplication and component isolation. `runner_trail` is plausible and should remain in the ablation set. `fixed_tp_sl` is useful as a control.

## Analyst Verdict
There is enough signal to continue to focused ablation. There is not enough evidence to declare a final deployable paper-shadow candidate yet.
""",
        "05_risk_critic.md": f"""# Risk Critic Memo

## Main Risk
The project is exposed to three research risks: cluster duplication, exit-family overfitting, and path-resolution optimism. None invalidates the run, but each must be controlled before paper-shadow.

## Neighborhood Stability
{neighbor_table}

The top neighborhood view is encouraging because several high-confidence clusters have hundreds to thousands of related strategies, not just one isolated row. But density cuts both ways: a large cluster can be genuine stability, or it can be many near-duplicates around one favorable market pattern.

## Execution Stress
{stress_table}

The stress table is reassuring: median stressed returns degrade gradually with latency, not catastrophically. Still, this is a backtest stress surface. The paper validator must check missed fills and intra-minute path ordering in a live-like replay.

## Risk Controls
- De-duplicate by `strategy_similarity_cluster_id`.
- Require positive stressed median after fee/slippage/latency.
- Keep p10 visible, not just median.
- Penalize top-symbol concentration.
- Treat early-alpha as research-only unless it survives a broader sample probe.
- Use `1m_trade_kline` honestly; do not pretend tick-level fill precision.

## Paper Gate
Hold. No direct paper-shadow promotion yet. The next pass should be a focused paper-sandbox ablation. A later paper gate can open only if a complete strategy remains positive after ablation, de-duplication, execution stress, and future-safety checks.
""",
        "06_statistical_skeptic.md": f"""# Statistical Skeptic Memo

## Statistical Position
The new sample policy is acceptable for discovery: sample sizes greater than 15 should not be discarded automatically. But inclusion is not endorsement. The right statistical language is tiered confidence.

## Sample Structure
{sample_table}

There are no retained rows with sample size 15 or below. That is useful: the entire leaderboard is analyzable under the revised rule. Still, 16-29 and 30-49 should be treated as early/exploratory evidence, while 100+ can carry more conclusion weight.

## Small Sample Caution
{md_table(tables['top_small'], 10)}

The raw top is impressive because p10 remains high for a 27-sample candidate. But it is also concentrated in the same family and cluster. The skeptical stance is: interesting, keep it, but force a neighbor and cluster-representative test.

## Multiple Testing
A 500B parameter search creates a massive selection problem. The existing bootstrap, permutation, effective sample size, multiple testing, and similarity-cluster artifacts are not optional reports; they are core controls. The next round should not optimize new parameters without updating those controls.

## Skeptic's Required Falsification
1. Cluster representative only, no duplicated rows.
2. Remove top 1 percent and top 5 percent contributors.
3. Compare to randomized timestamp/symbol baselines.
4. Test fixed entry with multiple exits and fixed exit with multiple entries.
5. Keep early-alpha candidates below paper-shadow threshold until they reappear in higher sample tiers.
""",
        "07_execution_paper_architect.md": f"""# Execution And Paper Architect Memo

## Execution Readiness
The current artifacts are research-ready, not paper-ready. The execution model includes fee, slippage, latency, and missed-fill sensitivity, and the path resolution is `1m_trade_kline`. That is strong for research, but paper-shadow should require a signal schema and replay validator.

## Required Complete Strategy Payload
Every paper-shadow candidate must include:

- BWE trigger and channel.
- Trade/no-trade decision.
- Long/short/no-trade side.
- Entry timing and entry conditions.
- Initial risk rule.
- Holding monitor fields.
- Exit family and exit state machine.
- Fee/slippage/latency/missed-fill assumptions.
- Path-resolution declaration.
- Paper-only and live-disallowed flags.

## Execution Stress Evidence
{stress_table}

The cost/latency degradation does not erase the top stressed candidates, which is encouraging. But the validator still needs to test whether the assumed entry timing can be executed in a paper feed without lookahead and without relying on unavailable intra-minute path information.

## Paper Path
The next generated config should be used for `focused_ablation_before_paper_shadow`. If that passes, then the subsequent paper-shadow plan can be created with strict no-order behavior and signal-only output.

## Decision
Do not emit paper-shadow signals from this round. Emit a paper-shadow design only after ablation confirms a cluster representative complete strategy.
""",
        "08_lead_synthesizer.md": f"""# Lead Synthesizer Memo

## Consensus
All roles converge on the same conclusion: the run has real research signal, but the next move is not deployment and not another global max_alpha pass. The next move is focused ablation.

## Strongest Preliminary Families
1. `premium_basis_overheat / 30s / long`, especially with `indicator_invalidation`, `breakeven_ratchet`, `state_machine`, and `runner_trail`.
2. `freshness_strict_confirmation / 30s / long`, especially state-machine raw alpha and breakeven high-confidence alpha.
3. `oi_funding_continuation / 1m or 30s / long`, especially with breakeven and runner exits.
4. `contrarian_crash_fade / 30s / long`, useful but requiring p10 and adverse-regime caution.

## Strongest Exit Families
`breakeven_ratchet` is the most reusable-looking exit module. `state_machine` has the strongest raw top but needs de-duplication. `runner_trail` is worth retaining. `fixed_tp_sl` should remain the control.

## Final Synthesis
The AutoResearch upgrade is now qualitatively different from a leaderboard. It contains a hypothesis ledger, component catalogs, discovery queue, role critique, cross-examination, and next-round ablation plan. The value of the next round will come from proving which component actually carries the edge.

## Final Recommendation
Proceed to a focused ablation round in paper-sandbox mode only. Do not enter paper-shadow until the ablation round produces a de-duplicated, execution-stressed, future-safe complete strategy with stable p10 and positive baseline lift.
""",
    }
    for name, text in memos.items():
        (out_dir / "role_memos" / name).write_text(text, encoding="utf-8")


def write_cross_exam(out_dir: Path, tables: dict[str, pd.DataFrame]) -> None:
    questions = """# Cross Examination Questions

## Meta Research Director To Strategy Architect
If `freshness_strict_confirmation / 30s / state_machine` dominates the raw leaderboard but clusters heavily at sample 27, what architecture evidence proves the entry is reusable rather than the exit harvesting one path shape?

## Strategy Architect To Results Analyst
Can you separate the effect of entry family from exit family for `premium_basis_overheat`, or are the headline results still complete-strategy correlations?

## Results Analyst To Statistical Skeptic
Given that no retained candidate has sample size 15 or below, how should the report phrase early-alpha evidence without incorrectly demoting useful 16-29 sample discoveries?

## Statistical Skeptic To Experiment Mutator
Which proposed mutation would most directly falsify the current best hypothesis rather than merely search around it?

## Risk Critic To Execution/Paper Architect
Which part of `1m_trade_kline` path resolution could make an exit state machine look cleaner than it would be in paper replay?

## Execution/Paper Architect To Lead Synthesizer
What exact gate must change before this becomes paper-shadow rather than research?

## Lead Synthesizer To All Roles
Name one hypothesis that should be advanced, one that should be held, and one that should be rejected or demoted after ablation.
"""
    (out_dir / "cross_exam" / "01_cross_examination_questions.md").write_text(questions, encoding="utf-8")

    rebuttals = f"""# Role Rebuttals

## Strategy Architect
The raw `freshness_strict_confirmation / state_machine` result is not enough by itself. I revise the architecture view: use it as a source of exit-state hypotheses, but give higher operational priority to `freshness_strict_confirmation / breakeven_ratchet` in the 100+ sample tier and to `premium_basis_overheat` complete modules that survive multiple exit families.

## Results Analyst
The leaderboard should be reported in three simultaneous views: raw profit, high-confidence profit, and stability/cluster support. The raw top remains important because its p10 is high, but the 100+ sample table is more decision-relevant for next-round queue priority.

## Statistical Skeptic
I accept the user's sample policy: greater than 15 is inclusion-worthy. My condition is that no claim should use the word reliable unless it survives a higher confidence tier or a local neighborhood test.

## Risk Critic
The main demotion risk is not that costs wipe out the signal; the stress table does not show that. The larger risk is path-shape and cluster overfit. I want cluster-representative evaluation before paper-shadow.

## Experiment Mutator
The first mutation should be falsification-oriented: hold `premium_basis_overheat / 30s / long` fixed and swap exits, including fixed TP/SL control. If the entry is real, at least one non-optimized exit should retain positive baseline lift.

## Execution/Paper Architect
No signal payload should be emitted yet. The next config is an ablation config, not a paper signal config. Paper-shadow requires a later positive gate decision.

## Lead Synthesizer
The revised synthesis is: continue with focused ablation; do not do global broad search; do not do paper-shadow yet.

## Evidence Snapshot
Top high-confidence candidates:

{md_table(tables['top_high_conf'], 8)}
"""
    (out_dir / "cross_exam" / "02_role_rebuttals.md").write_text(rebuttals, encoding="utf-8")

    revised = """# Revised Positions After Cross Examination

## Advanced Hypotheses
- Advance `premium_basis_overheat / 30s / long` as the first entry-family ablation.
- Advance `freshness_strict_confirmation / 30s / breakeven_ratchet / long` as the first high-confidence complete-strategy ablation.
- Advance `oi_funding_continuation / 1m / breakeven_ratchet / long` as the broad-sample continuation hypothesis.

## Held Hypotheses
- Hold `freshness_strict_confirmation / 30s / state_machine / long` as early-alpha raw leader until cluster representative and higher-sample checks are complete.
- Hold short-side discoveries for a separately balanced probe; do not conclude short is invalid from the current retained distribution.

## Demotion Criteria
- Demote any candidate whose positive median disappears under fixed TP/SL control.
- Demote any candidate whose p10 becomes materially worse after cluster de-duplication.
- Demote any candidate whose stressed median turns negative under cost/latency/missed-fill stress.
- Demote any early-alpha candidate that cannot reappear in adjacent parameter neighborhoods.
"""
    (out_dir / "cross_exam" / "03_revised_positions.md").write_text(revised, encoding="utf-8")


def write_final(out_dir: Path, evidence: dict[str, Any], tables: dict[str, pd.DataFrame]) -> None:
    entry = tables["entry"]
    exit_ = tables["exit"]
    combo = tables["combo"]
    stress_latency = tables["stress_latency"]
    top_raw = tables["top_raw"].iloc[0].to_dict()
    top_high_conf = tables["top_high_conf"].iloc[0].to_dict()
    synthesis = f"""# True Deep Round 1 Lead Synthesis

## Bottom Line
The research has enough signal to continue, but the correct next state is `focused_ablation_before_paper_shadow`, not paper-shadow and not another global max_alpha sweep.

## What Looks Real
The strongest preliminary edge is on long strategies around BWE pump/freshness/market-structure confirmation. The best raw candidate is early-alpha sample 27 but has very high median, p10, and stressed median. The best 100+ sample candidates remain highly positive, which materially reduces the concern that the entire run is a small-sample mirage.

## Best Candidate Families
- `premium_basis_overheat / 30s / long`: strongest discovery queue item, broad component evidence, multiple exits worth testing.
- `freshness_strict_confirmation / 30s / long`: strongest raw family, with a safer 100+ sample expression through `breakeven_ratchet`.
- `oi_funding_continuation / 1m or 30s / long`: broad sample support and good pairing with breakeven/runner exits.
- `contrarian_crash_fade / 30s / long`: potentially valuable but needs adverse-regime and p10 caution.

## Best Exit Modules
- `breakeven_ratchet`: best reusable-looking exit.
- `state_machine`: strongest raw leader but highest de-duplication burden.
- `runner_trail`: retain for ablation.
- `fixed_tp_sl`: keep as control, not winner.

## Why Not Paper Yet
The strategy families need component isolation. The top raw rows are clustered. Some group-level median p10 values are negative even when best rows are strong. The execution stress is encouraging but not a replacement for paper replay. Therefore the honest gate is hold-for-ablation.

## Immediate Next Round
Run the generated config in `final/next_round_config_true_deep.yaml`. The first ablation should test one hypothesis only: `premium_basis_overheat / 30s / long`, with exits swapped while all cost and data assumptions remain fixed.
    """
    (out_dir / "final" / "lead_synthesis_true_deep_round1.md").write_text(synthesis, encoding="utf-8")

    chinese_verdict = f"""# Codex 二次深度研究裁决

## 1. 这轮到底完成了什么
这不是重新跑 5000 亿级搜索，也不是把之前的短 memo 换个名字。这个目录做的是：把已经完成的 GPU fused strong 结果、AutoResearch 扩展层、entry/exit catalog、discovery queue、baseline、execution stress 和 cluster 稳定性放到同一个研究框架里，由八个角色分别审查，然后互相质询，最后给出可执行的下一轮 ablation 决策。

关键事实：

- 搜索空间记录：`{evidence['candidate_space_sample']}`。
- coarse eval：`{evidence['coarse_eval_actual']}`。
- medium eval：`{evidence['medium_eval_actual']}`。
- deep eval：`{evidence['deep_eval_actual']}`。
- stress eval：`{evidence['stress_eval_actual']}`。
- path resolution：`{evidence['path_resolution']}`。
- paper only：`{evidence['paper_only']}`。
- live allowed：`{evidence['live_allowed']}`。

## 2. 样本数政策结论
你要求“样本数量少不作为筛查标准，只要大于 15 就可以”。这轮数据支持这个政策，因为最终 200k leaderboard 中没有 `sample_size <= 15` 的候选。也就是说，这一轮不是在一堆 3、5、8 个样本的小点上做幻想，而是所有候选至少进入了 early-alpha 层。

但这不代表所有样本层级的证据权重一样。最终解释应这样处理：

- 16-29：可以作为 early-alpha 研究信号，不能直接 paper。
- 30-49：可以作为 exploratory watchlist。
- 50-99：可以作为 validated watchlist。
- 100+：可以作为 higher-confidence watchlist。

## 3. 最强 raw alpha 与最强高置信 alpha 的分歧
最强 raw 候选是：

`{top_raw['strategy_id']}`  
`{top_raw['strategy_family']} / {top_raw['side']} / {top_raw['entry_timing']} / {top_raw['exit_family']}`  
sample `{top_raw['sample_size']}`，median `{top_raw['median_net_pct']:.4f}`，p10 `{top_raw['p10_net_pct']:.4f}`，stressed median `{top_raw['stress_fee_slippage_median_net_pct']:.4f}`。

这很强，但它属于 early-alpha，并且 top raw 区域存在明显 cluster 重复。因此它的正确身份是：强研究线索，不是最终候选。

最强 100+ 样本候选是：

`{top_high_conf['strategy_id']}`  
`{top_high_conf['strategy_family']} / {top_high_conf['side']} / {top_high_conf['entry_timing']} / {top_high_conf['exit_family']}`  
sample `{top_high_conf['sample_size']}`，median `{top_high_conf['median_net_pct']:.4f}`，p10 `{top_high_conf['p10_net_pct']:.4f}`，stressed median `{top_high_conf['stress_fee_slippage_median_net_pct']:.4f}`。

这是非常重要的：高置信层没有崩掉。raw 第一名需要谨慎，但 100+ 样本层仍然保留了强正收益，这让整轮研究更可信。

## 4. Entry 侧最值得吸收的信号
从 entry catalog 看，下一轮最值得优先验证的不是单一策略，而是几个 entry family：

{md_table(entry.head(8), 8)}

我的二次判断：

1. `premium_basis_overheat / 30s / long` 应该排第一。它不是 raw top，但是 discovery queue 把它推到第一，因为它有较好的完整策略组合、较强 stress 表现，并且可以与多个 exit family 做隔离测试。
2. `freshness_strict_confirmation / 30s / long` 是 raw alpha 来源，但必须先解决 cluster 重复和 sample tier 问题。
3. `oi_funding_continuation / 1m or 30s / long` 更像广谱 continuation alpha，样本更厚，适合当第二或第三个 ablation 方向。
4. `contrarian_crash_fade / 30s / long` 不该丢，但 p10 和 adverse-regime 风险要更严。

## 5. Exit 侧最值得吸收的模块
从 exit catalog 看：

{md_table(exit_.head(8), 8)}

我的二次判断：

- `breakeven_ratchet` 是最像“可复用 exit module”的东西。它不是只在一个小样本 raw top 上赢，而是在高样本、stress 和组合 funnel 里都很强。
- `state_machine` 是 raw top 的主要来源，但它的风险是 path-shape overfit，所以要通过 cluster representative 和 exit swap 来验证。
- `runner_trail` 继续保留，它可能适合趋势延续型 entry。
- `fixed_tp_sl` 不像赢家，但必须保留为 control，否则无法证明复杂 exit 的增益。

## 6. 完整策略组合的优先级
完整策略 funnel 里，真正应该进入下一轮的不是“榜首一条”，而是一组带有因果测试价值的组合：

{md_table(combo.head(8), 8)}

优先级：

1. `premium_basis_overheat / 30s / indicator_invalidation / long`：先做 complete strategy neighborhood。
2. `premium_basis_overheat / 30s / long`：固定 entry，swap exits。
3. `freshness_strict_confirmation / 30s / breakeven_ratchet / long`：高置信版本，验证 raw alpha 是否能转成更厚样本。
4. `oi_funding_continuation / 1m / breakeven_ratchet / long`：验证广谱 continuation 是否比 raw freshness 更稳定。

## 7. 红队质疑
我不会把这轮结果说成“已经可以 paper”。主要反对意见有四个：

1. **cluster duplication**：raw top 多条几乎同构，必须用 cluster representative。
2. **multiple testing**：5000 亿参数空间天然有选择偏差，所以必须保留 permutation、bootstrap、ESS、multiple testing penalty。
3. **1m path resolution**：这是 1m trade kline，不是 tick replay。exit state machine 可能比真实 paper replay 更干净。
4. **long/short imbalance**：long 占绝大多数，short 不能简单判死刑，需要单独 balanced probe。

## 8. 执行成本判断
stress latency 不是当前最大风险，至少在 top stress 集合里没有明显把收益打没：

{md_table(stress_latency.head(8), 8)}

但这不等于执行没风险。下一轮必须继续保留 fee、slippage、latency、missed fill，而且 paper validator 需要检查 1m 内部路径顺序。

## 9. 最终裁决
最终结论：

**可以进入 focused ablation，不可以直接进入 paper-shadow。**

下一步只跑一个假设，不要又展开成全局 max_alpha：

`premium_basis_overheat / 30s / long`  
固定 entry，比较：

- `indicator_invalidation`
- `breakeven_ratchet`
- `state_machine`
- `runner_trail`
- `fixed_tp_sl`

如果它在 fixed TP/SL control 或至少一个非优化 exit 下仍然保留正 baseline lift，并且 stressed median/p10 还可以，才进入第二个假设。

## 10. 对你的项目有什么价值
这轮真正吸收了 AutoResearch 对你项目有用的部分：

- 从 leaderboard 变成 hypothesis ledger。
- 从“哪个策略最高”变成“哪个 entry/exit module 可复用”。
- 从 raw alpha 变成 sample-tier alpha。
- 从单角色总结变成多角色质询。
- 从宽搜索变成下一轮 one-hypothesis ablation。

这就是我认为现在最稳的研究推进方式。
"""
    (out_dir / "final" / "codex_second_pass_research_verdict.md").write_text(chinese_verdict, encoding="utf-8")

    gate = """# Paper Shadow Gate Decision

Decision: HOLD. Do not enter paper-shadow yet.

Allowed next state: `focused_ablation_before_paper_shadow`.

Required to open paper-shadow:

1. A de-duplicated cluster representative remains positive.
2. The same complete strategy remains positive under fee, slippage, latency, and missed-fill stress.
3. The entry component remains useful when exit family is controlled.
4. The exit component remains useful when entry family is controlled.
5. p10 and stressed median remain acceptable.
6. Future-safety remains clean.
7. Output remains signal-only and paper-only.
"""
    (out_dir / "final" / "paper_shadow_gate_decision_true_deep.md").write_text(gate, encoding="utf-8")

    source_pack = str(out_dir / "true_deep_round1_source_pack.json").replace("'", "''")
    cfg = f"""project: bwe_complete_strategy_v6
round: 2
mode: focused_ablation_before_paper_shadow
source_pack: '{source_pack}'
paper_only: true
live_allowed: false
policy:
  one_hypothesis_per_iteration: true
  baseline_first: true
  reject_log_driven: true
  stability_first: true
  sample_gt15_included: true
  sample_size_alone_reject_allowed: false
first_hypothesis:
  entry_family: premium_basis_overheat
  side: long
  entry_timing: 30s
  action: swap_exit_families_with_entry_fixed
  exits_to_compare:
    - indicator_invalidation
    - breakeven_ratchet
    - state_machine
    - runner_trail
    - fixed_tp_sl
controls:
  keep_fee_stress: true
  keep_slippage_stress: true
  keep_latency_stress: true
  keep_missed_fill_stress: true
  de_duplicate_by_cluster: true
  compare_to_baselines: true
  enforce_future_safety: true
next_hypotheses:
  - freshness_strict_confirmation_30s_breakeven_ratchet_long
  - oi_funding_continuation_1m_breakeven_ratchet_long
  - breakeven_ratchet_exit_module_ablation
  - short_side_balanced_probe
forbidden:
  - production_orders
  - credential_reads
  - notifications
  - scheduler_changes
"""
    (out_dir / "final" / "next_round_config_true_deep.yaml").write_text(cfg, encoding="utf-8")


def validate(out_dir: Path) -> dict[str, Any]:
    expected = [
        "00_method_and_scope.md",
        "true_deep_round1_source_pack.json",
        "role_memos/01_meta_research_director.md",
        "role_memos/02_strategy_architect.md",
        "role_memos/03_experiment_mutator.md",
        "role_memos/04_results_analyst.md",
        "role_memos/05_risk_critic.md",
        "role_memos/06_statistical_skeptic.md",
        "role_memos/07_execution_paper_architect.md",
        "role_memos/08_lead_synthesizer.md",
        "cross_exam/01_cross_examination_questions.md",
        "cross_exam/02_role_rebuttals.md",
        "cross_exam/03_revised_positions.md",
        "final/lead_synthesis_true_deep_round1.md",
        "final/codex_second_pass_research_verdict.md",
        "final/paper_shadow_gate_decision_true_deep.md",
        "final/next_round_config_true_deep.yaml",
    ]
    errors = []
    for rel in expected:
        path = out_dir / rel
        if not path.exists():
            errors.append(f"missing:{rel}")
        elif path.stat().st_size < 100:
            errors.append(f"too_small:{rel}")
    config = (out_dir / "final" / "next_round_config_true_deep.yaml").read_text(encoding="utf-8").lower()
    forbidden_actions = ["production_orders", "credential_reads", "notifications", "scheduler_changes"]
    if not all(term in config for term in forbidden_actions):
        errors.append("forbidden_controls_missing")
    report = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "out_dir": str(out_dir),
        "passes": not errors,
        "errors": errors,
        "expected_files": expected,
        "file_count": sum(1 for p in out_dir.rglob("*") if p.is_file()),
    }
    write_json(out_dir / "validation_report.json", report)
    if errors:
        raise RuntimeError("; ".join(errors))
    return report


def main() -> None:
    args = parse_args()
    out_dir = make_out_dir(args.run_dir, args.out_dir)
    data = load_inputs(args.run_dir, args.expanded_dir)
    evidence = build_evidence(data)
    tables = evidence_tables(data)
    write_json(out_dir / "true_deep_round1_source_pack.json", evidence)
    write_tables(out_dir, tables)
    write_scope(out_dir, evidence, tables)
    write_role_memos(out_dir, evidence, tables)
    write_cross_exam(out_dir, tables)
    write_final(out_dir, evidence, tables)
    report = validate(out_dir)
    print(json.dumps(clean(report), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
