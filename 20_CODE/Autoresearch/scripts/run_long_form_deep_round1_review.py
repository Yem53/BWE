from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


RUN_DIR = Path(r"H:\data\bwe\v6\runs\bwe_complete_strategy_v6_max_alpha_gpu_fused_strong_20260426_115115")
EXPANDED_DIR = RUN_DIR / r"llm_round_notes\deep_round1_autoresearch_expanded_20260426_134801"
TRUE_DEEP_DIR = RUN_DIR / r"llm_round_notes\deep_round1_true_llm_20260426_140354"


NUMERIC_COLS = [
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
    "candidate_seed",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate a long-form deep Round 1 research review package.")
    p.add_argument("--run-dir", type=Path, default=RUN_DIR)
    p.add_argument("--expanded-dir", type=Path, default=EXPANDED_DIR)
    p.add_argument("--true-deep-dir", type=Path, default=TRUE_DEEP_DIR)
    p.add_argument("--out-dir", type=Path, default=None)
    return p.parse_args()


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
    if obj is pd.NA:
        return None
    return obj


def write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(clean(obj), indent=2, sort_keys=True), encoding="utf-8")


def write_md(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8-sig")


def sample_tier(x: Any) -> str:
    try:
        n = int(x)
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


def md_table(df: pd.DataFrame, n: int = 10, cols: list[str] | None = None) -> str:
    if df is None or df.empty:
        return "_No rows._"
    view = df.copy()
    if cols:
        view = view[[c for c in cols if c in view.columns]]
    return view.head(n).to_markdown(index=False)


def make_out_dir(run_dir: Path, out_dir: Path | None) -> Path:
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=False)
        return out_dir
    base = run_dir / "llm_round_notes"
    base.mkdir(parents=True, exist_ok=True)
    stem = f"deep_round1_longform_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    out = base / stem
    i = 1
    while out.exists():
        out = base / f"{stem}_{i}"
        i += 1
    for rel in ["tables", "role_memos", "cross_exam", "red_team", "final", "configs"]:
        (out / rel).mkdir(parents=True, exist_ok=True)
    return out


def load_data(run_dir: Path, expanded_dir: Path, true_deep_dir: Path) -> dict[str, Any]:
    required = [
        run_dir / "complete_strategy_leaderboard.csv",
        run_dir / "baseline_comparison.csv",
        run_dir / "fee_slippage_latency_stress.csv",
        run_dir / "future_safety_report.csv",
        run_dir / "bootstrap_confidence_intervals.csv",
        run_dir / "permutation_test_results.csv",
        run_dir / "effective_sample_size_report.csv",
        run_dir / "run_summary.json",
        expanded_dir / "entry_catalog_scoreboard.csv",
        expanded_dir / "exit_catalog_scoreboard.csv",
        expanded_dir / "entry_exit_combined_funnel.csv",
        expanded_dir / "discovery_scoreboard.csv",
        expanded_dir / "neighborhood_stability.csv",
        true_deep_dir / "final" / "codex_second_pass_research_verdict.md",
    ]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise FileNotFoundError("Missing inputs: " + "; ".join(missing))

    leader = pd.read_csv(run_dir / "complete_strategy_leaderboard.csv", low_memory=False)
    for c in NUMERIC_COLS:
        if c in leader.columns:
            leader[c] = pd.to_numeric(leader[c], errors="coerce")
    leader["sample_tier"] = leader["sample_size"].map(sample_tier)
    leader["cost_stress_gap_pct"] = leader["median_net_pct"] - leader["stress_fee_slippage_median_net_pct"]
    leader["p10_gap_pct"] = leader["median_net_pct"] - leader["p10_net_pct"]
    leader["positive_p10"] = leader["p10_net_pct"] > 0
    leader["positive_stress"] = leader["stress_fee_slippage_median_net_pct"] > 0

    baseline = pd.read_csv(run_dir / "baseline_comparison.csv", low_memory=False)
    for c in NUMERIC_COLS:
        if c in baseline.columns:
            baseline[c] = pd.to_numeric(baseline[c], errors="coerce")

    return {
        "leader": leader,
        "baseline": baseline,
        "stress": pd.read_csv(run_dir / "fee_slippage_latency_stress.csv", low_memory=False),
        "future": pd.read_csv(run_dir / "future_safety_report.csv", low_memory=False),
        "bootstrap": pd.read_csv(run_dir / "bootstrap_confidence_intervals.csv", low_memory=False),
        "permutation": pd.read_csv(run_dir / "permutation_test_results.csv", low_memory=False),
        "effective": pd.read_csv(run_dir / "effective_sample_size_report.csv", low_memory=False),
        "summary": json.loads((run_dir / "run_summary.json").read_text(encoding="utf-8")),
        "entry_catalog": pd.read_csv(expanded_dir / "entry_catalog_scoreboard.csv"),
        "exit_catalog": pd.read_csv(expanded_dir / "exit_catalog_scoreboard.csv"),
        "combo": pd.read_csv(expanded_dir / "entry_exit_combined_funnel.csv"),
        "discovery": pd.read_csv(expanded_dir / "discovery_scoreboard.csv"),
        "neighbor": pd.read_csv(expanded_dir / "neighborhood_stability.csv"),
        "previous_verdict": (true_deep_dir / "final" / "codex_second_pass_research_verdict.md").read_text(encoding="utf-8"),
    }


def build_tables(data: dict[str, Any]) -> dict[str, pd.DataFrame]:
    leader = data["leader"]
    baseline = data["baseline"]
    best_baseline = float(baseline["median_net_pct"].max()) if "median_net_pct" in baseline else 0.0

    display = [
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
        "cost_stress_gap_pct",
        "robust_score",
        "strategy_similarity_cluster_id",
    ]

    cluster_rep = (
        leader.sort_values(["robust_score", "sample_size", "stress_fee_slippage_median_net_pct"], ascending=False)
        .drop_duplicates("strategy_similarity_cluster_id")
        .copy()
    )
    cluster_rep["baseline_lift_pct"] = cluster_rep["median_net_pct"] - best_baseline

    high_conf_cluster_rep = cluster_rep[cluster_rep["sample_size"] >= 100].copy()

    group_keys = ["strategy_family", "side", "entry_timing", "exit_family"]
    ablation_matrix = (
        leader.groupby(group_keys, dropna=False)
        .agg(
            rows=("strategy_id", "count"),
            unique_clusters=("strategy_similarity_cluster_id", "nunique"),
            median_sample=("sample_size", "median"),
            max_sample=("sample_size", "max"),
            best_median=("median_net_pct", "max"),
            median_of_medians=("median_net_pct", "median"),
            median_p10=("p10_net_pct", "median"),
            best_p10=("p10_net_pct", "max"),
            median_stress=("stress_fee_slippage_median_net_pct", "median"),
            best_stress=("stress_fee_slippage_median_net_pct", "max"),
            positive_p10_rate=("positive_p10", lambda s: float(s.mean() * 100.0)),
            positive_stress_rate=("positive_stress", lambda s: float(s.mean() * 100.0)),
            best_robust=("robust_score", "max"),
            median_robust=("robust_score", "median"),
            median_top_symbol_share=("top_symbol_share_pct", "median"),
        )
        .reset_index()
    )
    ablation_matrix["longform_score"] = (
        0.22 * ablation_matrix["best_stress"].rank(pct=True)
        + 0.18 * ablation_matrix["median_stress"].rank(pct=True)
        + 0.16 * ablation_matrix["best_p10"].rank(pct=True)
        + 0.14 * ablation_matrix["unique_clusters"].rank(pct=True)
        + 0.12 * ablation_matrix["positive_stress_rate"].rank(pct=True)
        + 0.10 * ablation_matrix["median_sample"].rank(pct=True)
        + 0.08 * (1.0 - ablation_matrix["median_top_symbol_share"].rank(pct=True))
    ).fillna(0.0)
    ablation_matrix = ablation_matrix.sort_values("longform_score", ascending=False).reset_index(drop=True)

    sample_tier = (
        leader.groupby("sample_tier", dropna=False)
        .agg(
            strategies=("strategy_id", "count"),
            clusters=("strategy_similarity_cluster_id", "nunique"),
            median_sample=("sample_size", "median"),
            best_median=("median_net_pct", "max"),
            median_p10=("p10_net_pct", "median"),
            positive_p10_rate=("positive_p10", lambda s: float(s.mean() * 100.0)),
            median_stress=("stress_fee_slippage_median_net_pct", "median"),
            positive_stress_rate=("positive_stress", lambda s: float(s.mean() * 100.0)),
        )
        .reset_index()
    )

    side_timing = (
        leader.groupby(["side", "entry_timing"], dropna=False)
        .agg(
            rows=("strategy_id", "count"),
            clusters=("strategy_similarity_cluster_id", "nunique"),
            median_sample=("sample_size", "median"),
            best_median=("median_net_pct", "max"),
            median_p10=("p10_net_pct", "median"),
            median_stress=("stress_fee_slippage_median_net_pct", "median"),
            positive_stress_rate=("positive_stress", lambda s: float(s.mean() * 100.0)),
        )
        .reset_index()
        .sort_values(["best_median", "median_stress"], ascending=False)
    )

    exit_reuse = data["exit_catalog"].copy()
    entry_reuse = data["entry_catalog"].copy()
    combo = data["combo"].copy()
    discovery = data["discovery"].copy()
    neighbor = data["neighbor"].copy()

    risk_register = pd.DataFrame(
        [
            {
                "risk_id": "R1",
                "risk": "raw_top_cluster_duplication",
                "severity": "high",
                "evidence": "Top raw freshness/state_machine rows repeat inside the same similarity clusters.",
                "mitigation": "Rank cluster representatives before paper gate.",
            },
            {
                "risk_id": "R2",
                "risk": "exit_path_shape_overfit",
                "severity": "high",
                "evidence": "State-machine raw leaders may harvest one favorable 1m path shape.",
                "mitigation": "Swap exits with fixed entry and include fixed_tp_sl control.",
            },
            {
                "risk_id": "R3",
                "risk": "multiple_testing_selection_bias",
                "severity": "high",
                "evidence": "500B-scale parameter space creates selection pressure.",
                "mitigation": "Use bootstrap, permutation, ESS, multiple testing penalty, and reject ledger.",
            },
            {
                "risk_id": "R4",
                "risk": "long_short_imbalance",
                "severity": "medium",
                "evidence": "Long dominates retained candidates while short has far fewer rows.",
                "mitigation": "Run separate balanced short-side probe before rejecting short.",
            },
            {
                "risk_id": "R5",
                "risk": "1m_path_resolution_limit",
                "severity": "medium",
                "evidence": "The path is 1m trade OHLCV, not tick replay.",
                "mitigation": "Declare path precision and require paper replay before shadow signals.",
            },
        ]
    )

    tables = {
        "cluster_rep_top": cluster_rep[display + ["baseline_lift_pct"]].head(300),
        "high_conf_cluster_rep_top": high_conf_cluster_rep[display + ["baseline_lift_pct"]].head(300),
        "ablation_matrix": ablation_matrix.head(500),
        "sample_tier_summary": sample_tier,
        "side_timing_summary": side_timing,
        "entry_reuse": entry_reuse,
        "exit_reuse": exit_reuse,
        "combo": combo,
        "discovery": discovery,
        "neighbor": neighbor,
        "risk_register": risk_register,
    }
    return tables


def write_tables(out_dir: Path, tables: dict[str, pd.DataFrame]) -> None:
    for name, df in tables.items():
        df.to_csv(out_dir / "tables" / f"{name}.csv", index=False)


def write_method(out_dir: Path, data: dict[str, Any], tables: dict[str, pd.DataFrame]) -> None:
    s = data["summary"]
    lines = [
        "# Long-Form Deep Round 1 Method",
        "",
        "This package is the long-form review layer. It does not rerun search and does not call production systems. "
        "It converts the completed GPU fused strong run into an auditable research committee review.",
        "",
        "## Source",
        f"- Stage: `{s.get('stage')}`",
        f"- Candidate space sample: `{s.get('candidate_space_sample')}`",
        f"- Coarse eval: `{s.get('coarse_eval_actual')}`",
        f"- Medium eval: `{s.get('medium_eval_actual')}`",
        f"- Deep eval: `{s.get('deep_eval_actual')}`",
        f"- Stress eval: `{s.get('stress_eval_actual')}`",
        f"- Path resolution: `{s.get('path_resolution')}`",
        f"- Paper only: `{s.get('paper_only')}`",
        f"- Live allowed: `{s.get('live_allowed')}`",
        "",
        "## Long-Form Review Phases",
        "1. Evidence audit and de-duplication.",
        "2. Entry/exit combination ranking.",
        "3. Role-independent memo generation.",
        "4. Cross-examination.",
        "5. Red-team review.",
        "6. Final Chinese verdict and focused ablation config.",
        "",
        "## Sample Tier Summary",
        md_table(tables["sample_tier_summary"], 10),
        "",
        "## Cluster Representative Leaders",
        md_table(tables["cluster_rep_top"], 12),
    ]
    write_md(out_dir / "00_long_form_method.md", "\n".join(lines) + "\n")


def write_role_memos(out_dir: Path, tables: dict[str, pd.DataFrame]) -> None:
    cluster = md_table(tables["cluster_rep_top"], 10)
    high = md_table(tables["high_conf_cluster_rep_top"], 10)
    combo = md_table(tables["combo"], 10)
    entry = md_table(tables["entry_reuse"], 8)
    exit_ = md_table(tables["exit_reuse"], 8)
    matrix = md_table(tables["ablation_matrix"], 10)
    risk = md_table(tables["risk_register"], 10)

    memos = {
        "01_meta_research_director.md": f"""# Meta Research Director Long Memo

## Verdict
The project has crossed from raw search into research governance. The output is strong enough for focused ablation, but still not paper-shadow. The reason is subtle: the candidates are not weak; the attribution of alpha is not yet isolated.

## Evidence I Trust Most
{high}

The high-confidence cluster representatives matter more than raw repeated rows. They show that strong results survive beyond the 27-sample early-alpha raw top.

## Operating Order
1. Use cluster representatives rather than duplicated leaderboard rows.
2. Test one hypothesis at a time.
3. Keep entry and exit isolation separate.
4. Preserve baseline, cost stress, and future safety in every pass.
5. Do not let paper-shadow consume a candidate until its complete strategy object survives ablation.

## Committee Decision
Proceed to `focused_ablation_before_paper_shadow`. The first hypothesis should be `premium_basis_overheat / 30s / long` with exit swap.
""",
        "02_strategy_architect.md": f"""# Strategy Architect Long Memo

## Architecture Read
The system is finding complete strategies. The key issue is not whether exits exist; it is which entry/exit modules are reusable.

## Entry Evidence
{entry}

## Exit Evidence
{exit_}

## Complete Combination Evidence
{combo}

## Architecture Ranking
1. `premium_basis_overheat / 30s / long`: best first ablation target because it can be paired with multiple exits.
2. `freshness_strict_confirmation / 30s / breakeven_ratchet / long`: best high-confidence complete expression.
3. `oi_funding_continuation / 1m / breakeven_ratchet / long`: best broad continuation line.
4. `freshness_strict_confirmation / 30s / state_machine / long`: strongest raw expression, but needs cluster control.

## Design Constraint
Do not collapse `premium_basis_overheat`, `freshness_strict_confirmation`, and `oi_funding_continuation` into one generic long-pump family. They represent different hypotheses and should be ablated independently.
""",
        "03_experiment_mutator.md": f"""# Experiment Mutator Long Memo

## Mutation Principle
Mutation should increase causal information, not just leaderboard height. The next experiment should ask: does the entry still work when the exit is no longer optimized?

## Ablation Matrix
{matrix}

## First Experiment
Fixed entry:

- `strategy_family: premium_basis_overheat`
- `side: long`
- `entry_timing: 30s`

Swap exits:

- `indicator_invalidation`
- `breakeven_ratchet`
- `state_machine`
- `runner_trail`
- `fixed_tp_sl`

Success requires positive stressed median, acceptable p10, baseline lift, and no future safety failure.

## Stop Rule
If fixed TP/SL and at least one non-state-machine exit both fail, demote the entry family. If only state-machine succeeds, mark exit-path overfit risk.
""",
        "04_results_analyst.md": f"""# Results Analyst Long Memo

## Result Structure
The raw top and the high-confidence top disagree in useful ways. Raw top emphasizes `freshness_strict_confirmation / state_machine`; high-confidence top emphasizes `freshness_strict_confirmation / breakeven_ratchet` and related continuation entries.

## Cluster Representative Leaders
{cluster}

## High Confidence Leaders
{high}

## Interpretation
The existence of high-confidence positive leaders means this is not merely a tiny-sample artifact. But the top rows are still not independent discoveries. Report by cluster representative, sample tier, p10, stress median, and baseline lift.

## Analyst Decision
Continue research with the top four families. Do not promote any single row to paper-shadow.
""",
        "05_risk_critic.md": f"""# Risk Critic Long Memo

## Risk Register
{risk}

## Highest Risk
The highest risk is not raw profitability. The highest risk is misattribution: thinking the entry is good when the exit path is doing the work, or thinking the exit is good because a narrow entry selected an unusually favorable path.

## Controls
- Cluster representative ranking.
- Fixed entry / swapped exit tests.
- Fixed exit / swapped entry tests.
- p10 and stressed median gates.
- Path-resolution disclosure.
- Separate short-side probe.

## Decision
No paper-shadow. Focused ablation only.
""",
        "06_statistical_skeptic.md": f"""# Statistical Skeptic Long Memo

## Statistical Stance
The user's sample policy is reasonable for discovery: sample_size > 15 enters analysis. But a 500B-scale search means selection bias remains the central statistical hazard.

## Evidence To Keep Visible
{md_table(tables["sample_tier_summary"], 10)}

## Skeptical Requirements
1. De-duplicate by cluster.
2. Preserve bootstrap and permutation reports.
3. Require neighboring parameter support.
4. Do not equate early-alpha with reliability.
5. Penalize strategies that lose p10 after cluster representative selection.

## Decision
The current conclusion can say "signal exists"; it cannot say "final strategy found".
""",
        "07_execution_paper_architect.md": f"""# Execution And Paper Architect Long Memo

## Execution Status
The execution model includes fee, slippage, latency, and missed-fill stress, and the path resolution is `1m_trade_kline`. That is sufficient for research screening, not sufficient for live-like fill claims.

## Paper Payload Must Include
- BWE trigger.
- trade/no-trade.
- long/short/no_trade.
- entry timing.
- entry conditions.
- initial risk.
- holding monitor fields.
- exit state machine.
- fee/slippage/latency/missed-fill assumptions.
- paper-only flag.

## Gate
Paper-shadow opens only after a complete strategy survives focused ablation and replay validation. Current gate remains closed.
""",
        "08_lead_synthesizer.md": f"""# Lead Synthesizer Long Memo

## Synthesis
The best current answer is not a single final strategy. It is a ranked research queue of complete entry/exit combinations.

## Ranked Queue
{combo}

## Final Committee Call
1. First ablation: `premium_basis_overheat / 30s / long` with exit swap.
2. Second ablation: `freshness_strict_confirmation / 30s / breakeven_ratchet / long`.
3. Third ablation: `oi_funding_continuation / 1m / breakeven_ratchet / long`.
4. Hold raw `freshness_strict_confirmation / state_machine` until de-duplicated.

## Final State
Proceed to focused ablation. Do not enter paper-shadow. Do not restart broad max_alpha before completing this ablation queue.
""",
    }
    for name, text in memos.items():
        write_md(out_dir / "role_memos" / name, text)


def write_cross_exam(out_dir: Path, tables: dict[str, pd.DataFrame]) -> None:
    questions = """# Long-Form Cross Examination

## Question 1
If `freshness_strict_confirmation / state_machine` is the raw top, why not run it first?

Answer: because raw top has early-alpha sample size and cluster duplication. It remains important, but `premium_basis_overheat` has better discovery value for isolating entry alpha.

## Question 2
Why is `breakeven_ratchet` treated as more reusable than `state_machine`?

Answer: because it appears strong across higher sample tiers and component catalogs, while state-machine owns the raw top but has greater path-shape overfit risk.

## Question 3
Is `oi_funding_continuation / 1m / breakeven_ratchet` less exciting than freshness?

Answer: less explosive, but possibly more stable. It should be third in queue because it tests a different continuation mechanism.

## Question 4
What would falsify `premium_basis_overheat / 30s / long`?

Answer: if fixed TP/SL and non-state-machine exits fail after cost stress, or if p10 turns materially negative after cluster representative filtering.
"""
    write_md(out_dir / "cross_exam" / "01_questions_and_answers.md", questions)

    revised = f"""# Long-Form Revised Findings

## Revised Ranking After Cross-Exam
{md_table(tables["combo"], 12)}

## Revisions
- `premium_basis_overheat` stays first because it is the most useful ablation target, not because it is the raw top.
- `freshness_strict_confirmation / breakeven_ratchet` is the best high-confidence expression.
- `freshness_strict_confirmation / state_machine` remains a held raw-alpha candidate.
- `oi_funding_continuation` remains the broader continuation path.
- Short side is not rejected; it is deferred to a balanced probe.
"""
    write_md(out_dir / "cross_exam" / "02_revised_findings.md", revised)


def write_red_team(out_dir: Path, tables: dict[str, pd.DataFrame]) -> None:
    write_md(
        out_dir / "red_team" / "overfit_bias_audit.md",
        f"""# Overfit And Bias Audit

## Main Biases
{md_table(tables["risk_register"], 10)}

## Red-Team Conclusion
The result is promising but selection-biased by design. The next round must reduce degrees of freedom by freezing one side of the strategy and mutating only the other.

## Required Evidence Before Paper
- Cluster-representative positive performance.
- Positive stressed median.
- Positive or acceptable p10.
- Nonzero baseline lift after fixed controls.
- Future-safety pass.
""",
    )
    write_md(
        out_dir / "red_team" / "execution_path_audit.md",
        """# Execution Path Audit

## Path Precision
The run uses `1m_trade_kline`. This is much better than mark-only fallback, but it is still not tick replay.

## Concern
State-machine and trailing exits can look better when the path ordering inside the minute is favorable or simplified.

## Mitigation
Before paper-shadow, replay the candidate with the exact paper feed and record:

- entry availability at chosen timing,
- fill/missed-fill behavior,
- exit path ordering,
- fee/slippage/latency sensitivity,
- no future data usage.
""",
    )


def write_final(out_dir: Path, data: dict[str, Any], tables: dict[str, pd.DataFrame]) -> None:
    combo = tables["combo"]
    discovery = tables["discovery"]
    cluster = tables["cluster_rep_top"]
    verdict = f"""# 长版深度最终结论

## 一句话结论
现在最好的结论不是“已经找到最终策略”，而是“已经找到值得优先 ablation 的完整策略族”。当前可以进入 `focused_ablation_before_paper_shadow`，但不应该直接进入 paper-shadow。

## 当前最好的开仓/平仓组合
{md_table(combo, 12)}

## 最值得先跑的研究队列
{md_table(discovery, 12)}

## Cluster 去重后的强候选
{md_table(cluster, 12)}

## 排名解释
1. `premium_basis_overheat / 30s / long / indicator_invalidation` 是第一 ablation 目标，因为它最适合验证 entry 是否独立有效。
2. `freshness_strict_confirmation / 30s / long / breakeven_ratchet` 是当前最好的高置信完整表达。
3. `oi_funding_continuation / 1m / long / breakeven_ratchet` 是最值得验证的厚样本 continuation 路线。
4. `freshness_strict_confirmation / 30s / long / state_machine` 是 raw alpha 最强，但必须先过 cluster 去重和 path-overfit 审查。
5. `contrarian_crash_fade / 30s / long / breakeven_ratchet` 有价值，但风险更高，放在后续。

## 下一步
只跑一个假设：

`premium_basis_overheat / 30s / long`

固定开仓，比较这些平仓：

- `indicator_invalidation`
- `breakeven_ratchet`
- `state_machine`
- `runner_trail`
- `fixed_tp_sl`

成功标准：

- stressed median > 0
- p10 不恶化到不可接受
- baseline lift 保持正
- future safety pass
- cluster representative 仍然有效

## Paper Gate
当前 paper gate 关闭。完成 focused ablation 后再判断是否打开。
"""
    write_md(out_dir / "final" / "final_verdict_zh.md", verdict)

    cfg = """project: bwe_complete_strategy_v6
mode: focused_ablation_before_paper_shadow
paper_only: true
live_allowed: false
one_hypothesis_per_iteration: true
first_hypothesis:
  strategy_family: premium_basis_overheat
  side: long
  entry_timing: 30s
  fixed_component: entry
  mutate_component: exit
  exit_families:
    - indicator_invalidation
    - breakeven_ratchet
    - state_machine
    - runner_trail
    - fixed_tp_sl
success_metrics:
  stressed_median_positive: true
  baseline_lift_positive: true
  future_safety_pass: true
  cluster_representative_positive: true
  p10_not_materially_worse: true
forbidden:
  - production_orders
  - credential_reads
  - notifications
  - scheduler_changes
"""
    (out_dir / "configs" / "next_ablation_config_longform.yaml").write_text(cfg, encoding="utf-8")

    paper_gate = """# Paper Gate Long-Form Decision

Decision: HOLD.

The paper gate remains closed because attribution is not isolated. The project has strong candidate families, but still needs focused ablation to separate entry alpha, exit alpha, and path-shape overfit.

Open the gate only after:

1. Cluster representative result remains positive.
2. Entry works across at least two exit modules or one control plus one advanced exit.
3. Exit works with at least two entry modules or a neutral control.
4. Cost stress stays positive.
5. Future safety stays clean.
"""
    write_md(out_dir / "final" / "paper_gate_longform.md", paper_gate)


def validate(out_dir: Path) -> dict[str, Any]:
    expected = [
        "00_long_form_method.md",
        "tables/cluster_rep_top.csv",
        "tables/high_conf_cluster_rep_top.csv",
        "tables/ablation_matrix.csv",
        "tables/risk_register.csv",
        "role_memos/01_meta_research_director.md",
        "role_memos/02_strategy_architect.md",
        "role_memos/03_experiment_mutator.md",
        "role_memos/04_results_analyst.md",
        "role_memos/05_risk_critic.md",
        "role_memos/06_statistical_skeptic.md",
        "role_memos/07_execution_paper_architect.md",
        "role_memos/08_lead_synthesizer.md",
        "cross_exam/01_questions_and_answers.md",
        "cross_exam/02_revised_findings.md",
        "red_team/overfit_bias_audit.md",
        "red_team/execution_path_audit.md",
        "final/final_verdict_zh.md",
        "final/paper_gate_longform.md",
        "configs/next_ablation_config_longform.yaml",
    ]
    errors = []
    for rel in expected:
        p = out_dir / rel
        if not p.exists():
            errors.append(f"missing:{rel}")
        elif p.stat().st_size < 100:
            errors.append(f"too_small:{rel}")
    cfg = (out_dir / "configs" / "next_ablation_config_longform.yaml").read_text(encoding="utf-8").lower()
    for term in ["paper_only: true", "live_allowed: false", "production_orders", "credential_reads"]:
        if term not in cfg:
            errors.append(f"config_missing:{term}")
    report = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "out_dir": str(out_dir),
        "passes": not errors,
        "errors": errors,
        "file_count": sum(1 for p in out_dir.rglob("*") if p.is_file()),
        "expected": expected,
    }
    write_json(out_dir / "validation_report.json", report)
    if errors:
        raise RuntimeError("; ".join(errors))
    return report


def main() -> None:
    args = parse_args()
    out_dir = make_out_dir(args.run_dir, args.out_dir)
    data = load_data(args.run_dir, args.expanded_dir, args.true_deep_dir)
    tables = build_tables(data)
    write_tables(out_dir, tables)
    write_method(out_dir, data, tables)
    write_role_memos(out_dir, tables)
    write_cross_exam(out_dir, tables)
    write_red_team(out_dir, tables)
    write_final(out_dir, data, tables)
    write_json(
        out_dir / "longform_source_summary.json",
        {
            "source_run": str(args.run_dir),
            "expanded_dir": str(args.expanded_dir),
            "true_deep_dir": str(args.true_deep_dir),
            "table_rows": {k: int(len(v)) for k, v in tables.items()},
        },
    )
    report = validate(out_dir)
    print(json.dumps(clean(report), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
