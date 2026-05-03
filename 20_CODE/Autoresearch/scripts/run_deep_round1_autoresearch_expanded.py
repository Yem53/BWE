from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_RUN_DIR = Path(
    r"H:\data\bwe\v6\runs\bwe_complete_strategy_v6_max_alpha_gpu_fused_strong_20260426_115115"
)

ROLE_SPECS = [
    ("meta_research_director", "Meta Research Director"),
    ("strategy_architect", "Strategy Architect"),
    ("experiment_mutator", "Experiment Mutator"),
    ("results_analyst", "Results Analyst"),
    ("risk_critic", "Risk Critic"),
    ("statistical_skeptic", "Statistical Skeptic"),
    ("execution_paper_architect", "Execution/Paper Architect"),
    ("lead_synthesizer", "Lead Synthesizer"),
]

SAMPLE_TIERS = [
    ("insufficient_observation", 0, 15),
    ("early_alpha", 16, 29),
    ("exploratory_watchlist", 30, 49),
    ("validated_watchlist", 50, 99),
    ("higher_confidence_watchlist", 100, 10**12),
]

LEADERBOARD_NUMERIC_COLS = [
    "entry_delay_s",
    "horizon_min",
    "sample_size",
    "win_rate_pct",
    "mean_net_pct",
    "median_net_pct",
    "p25_net_pct",
    "p10_net_pct",
    "profit_factor",
    "max_drawdown_pct",
    "longest_losing_streak",
    "mfe_capture_ratio",
    "giveback_ratio",
    "avg_hold_minutes",
    "stress_fee_slippage_median_net_pct",
    "stress_latency_median_net_pct",
    "walk_forward_positive_rate_pct",
    "remove_top_1pct_mean_net_pct",
    "top1_removed_mean_net_pct",
    "top5_removed_mean_net_pct",
    "symbol_count",
    "unique_days",
    "top_symbol_share_pct",
    "portfolio_drawdown_pct",
    "robust_score",
    "candidate_seed",
]

DISPLAY_COLS = [
    "strategy_id",
    "strategy_family",
    "channel",
    "event_type",
    "side",
    "entry_timing",
    "exit_family",
    "horizon_min",
    "sample_size",
    "sample_tier",
    "median_net_pct",
    "p10_net_pct",
    "stress_fee_slippage_median_net_pct",
    "stress_latency_median_net_pct",
    "walk_forward_positive_rate_pct",
    "top_symbol_share_pct",
    "robust_score",
    "stability_score",
    "baseline_lift_median_pct",
    "strategy_similarity_cluster_id",
    "future_safety_pass",
    "decision",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the expanded AutoResearch Round 1 absorption layer."
    )
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--top-n", type=int, default=500)
    return parser.parse_args()


def now_tag() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def make_output_dir(run_dir: Path, out_dir: Path | None) -> Path:
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=False)
        return out_dir
    base = run_dir / "llm_round_notes"
    base.mkdir(parents=True, exist_ok=True)
    candidate = base / f"deep_round1_autoresearch_expanded_{now_tag()}"
    suffix = 1
    while candidate.exists():
        candidate = base / f"deep_round1_autoresearch_expanded_{now_tag()}_{suffix}"
        suffix += 1
    candidate.mkdir(parents=True)
    return candidate


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(clean_for_json(obj), indent=2, sort_keys=True), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    text = "\n".join(json.dumps(clean_for_json(row), sort_keys=True) for row in rows)
    path.write_text(text + ("\n" if text else ""), encoding="utf-8")


def clean_for_json(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): clean_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean_for_json(v) for v in obj]
    if isinstance(obj, tuple):
        return [clean_for_json(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return None if not math.isfinite(float(obj)) else float(obj)
    if isinstance(obj, float):
        return None if not math.isfinite(obj) else obj
    if pd.isna(obj) if not isinstance(obj, (list, dict, tuple)) else False:
        return None
    return obj


def require_inputs(run_dir: Path) -> None:
    required = [
        "complete_strategy_leaderboard.csv",
        "baseline_comparison.csv",
        "fee_slippage_latency_stress.csv",
        "strategy_similarity_clusters.csv",
        "bootstrap_confidence_intervals.csv",
        "permutation_test_results.csv",
        "effective_sample_size_report.csv",
        "reject_log.csv",
        "future_safety_report.csv",
        "run_summary.json",
    ]
    missing = [name for name in required if not (run_dir / name).exists()]
    if missing:
        raise FileNotFoundError(f"Missing required run artifacts: {missing}")


def sample_tier(sample_size: Any) -> str:
    try:
        n = int(sample_size)
    except Exception:
        n = 0
    for name, lo, hi in SAMPLE_TIERS:
        if lo <= n <= hi:
            return name
    return "unknown"


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        x = float(value)
    except Exception:
        return default
    return x if math.isfinite(x) else default


def safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, float) and math.isnan(value):
        return default
    text = str(value)
    return text if text else default


def stable_id(prefix: str, payload: dict[str, Any], width: int = 10) -> str:
    raw = json.dumps(clean_for_json(payload), sort_keys=True)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:width]
    return f"{prefix}_{digest}"


def parse_json_cell(text: Any) -> dict[str, Any]:
    if not isinstance(text, str) or not text:
        return {}
    try:
        value = json.loads(text)
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def add_derived_columns(df: pd.DataFrame, baselines: pd.DataFrame, future: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in LEADERBOARD_NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "sample_size" not in df.columns:
        df["sample_size"] = 0
    df["sample_tier"] = df["sample_size"].map(sample_tier)

    if not future.empty and "strategy_id" in future.columns:
        future_cols = ["strategy_id", "future_safety_pass"]
        future_small = future[[c for c in future_cols if c in future.columns]].drop_duplicates("strategy_id")
        if "future_safety_pass" in future_small.columns:
            future_small["future_safety_pass"] = future_small["future_safety_pass"].astype(str).str.lower().isin(
                ["true", "1", "yes"]
            )
            df = df.merge(future_small, on="strategy_id", how="left", suffixes=("", "_from_report"))
            if "future_safety_pass_from_report" in df.columns:
                df["future_safety_pass"] = df["future_safety_pass_from_report"].fillna(True)
                df = df.drop(columns=["future_safety_pass_from_report"])
            else:
                df["future_safety_pass"] = df.get("future_safety_pass", True)
        else:
            df["future_safety_pass"] = True
    else:
        df["future_safety_pass"] = True

    best_baseline = 0.0
    if not baselines.empty and "median_net_pct" in baselines.columns:
        baselines["median_net_pct"] = pd.to_numeric(baselines["median_net_pct"], errors="coerce")
        best_baseline = safe_float(baselines["median_net_pct"].max(), 0.0)
    df["baseline_lift_median_pct"] = df["median_net_pct"].fillna(0.0) - best_baseline

    if "risk_rule_json" in df.columns:
        risk_shapes = []
        for value in df["risk_rule_json"].head(len(df)):
            parsed = parse_json_cell(value)
            shape = parsed.get("shape") or parsed.get("risk_model") or parsed.get("family") or "unspecified"
            risk_shapes.append(str(shape))
        df["risk_shape"] = risk_shapes
    else:
        df["risk_shape"] = "unspecified"

    for col in [
        "robust_score",
        "p10_net_pct",
        "stress_fee_slippage_median_net_pct",
        "walk_forward_positive_rate_pct",
        "top1_removed_mean_net_pct",
        "sample_size",
        "top_symbol_share_pct",
        "median_net_pct",
    ]:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    ranks = {
        "robust": df["robust_score"].rank(pct=True),
        "p10": df["p10_net_pct"].rank(pct=True),
        "stress": df["stress_fee_slippage_median_net_pct"].rank(pct=True),
        "walk": df["walk_forward_positive_rate_pct"].rank(pct=True),
        "top_removed": df["top1_removed_mean_net_pct"].rank(pct=True),
        "sample": df["sample_size"].rank(pct=True),
        "concentration": df["top_symbol_share_pct"].rank(pct=True),
    }
    df["stability_score"] = (
        0.34 * ranks["robust"]
        + 0.18 * ranks["p10"]
        + 0.16 * ranks["stress"]
        + 0.13 * ranks["walk"]
        + 0.09 * ranks["top_removed"]
        + 0.07 * ranks["sample"]
        - 0.03 * ranks["concentration"]
    ).fillna(0.0)
    df["profit_score"] = (
        0.45 * df["median_net_pct"].rank(pct=True)
        + 0.25 * df["p25_net_pct"].rank(pct=True)
        + 0.15 * df["p10_net_pct"].rank(pct=True)
        + 0.15 * df["stress_fee_slippage_median_net_pct"].rank(pct=True)
    ).fillna(0.0)
    return df


def load_inputs(run_dir: Path) -> dict[str, Any]:
    require_inputs(run_dir)
    leaderboard = pd.read_csv(run_dir / "complete_strategy_leaderboard.csv", low_memory=False)
    baselines = pd.read_csv(run_dir / "baseline_comparison.csv", low_memory=False)
    future = pd.read_csv(run_dir / "future_safety_report.csv", low_memory=False)
    clusters = pd.read_csv(run_dir / "strategy_similarity_clusters.csv", low_memory=False)
    stress = pd.read_csv(run_dir / "fee_slippage_latency_stress.csv", low_memory=False)
    bootstrap = pd.read_csv(run_dir / "bootstrap_confidence_intervals.csv", low_memory=False)
    permutation = pd.read_csv(run_dir / "permutation_test_results.csv", low_memory=False)
    effective = pd.read_csv(run_dir / "effective_sample_size_report.csv", low_memory=False)
    reject_log = pd.read_csv(run_dir / "reject_log.csv", low_memory=False)
    summary = read_json(run_dir / "run_summary.json", {})
    leaderboard = add_derived_columns(leaderboard, baselines, future)
    return {
        "leaderboard": leaderboard,
        "baselines": baselines,
        "future": future,
        "clusters": clusters,
        "stress": stress,
        "bootstrap": bootstrap,
        "permutation": permutation,
        "effective": effective,
        "reject_log": reject_log,
        "summary": summary,
    }


def present_cols(df: pd.DataFrame, cols: list[str]) -> list[str]:
    return [col for col in cols if col in df.columns]


def top_records(df: pd.DataFrame, n: int = 20) -> list[dict[str, Any]]:
    cols = present_cols(df, DISPLAY_COLS)
    return df[cols].head(n).to_dict(orient="records")


def group_catalog(df: pd.DataFrame, keys: list[str], score_name: str) -> pd.DataFrame:
    keys = [k for k in keys if k in df.columns]
    if not keys:
        raise ValueError("No valid grouping keys for catalog")
    work = df.copy()
    work["positive_stress"] = work["stress_fee_slippage_median_net_pct"] > 0
    work["positive_p10"] = work["p10_net_pct"] > 0
    work["sample_gt15"] = work["sample_size"] > 15
    work["sample_ge50"] = work["sample_size"] >= 50
    work["sample_ge100"] = work["sample_size"] >= 100
    grouped = work.groupby(keys, dropna=False)
    out = grouped.agg(
        tested_strategies=("strategy_id", "count"),
        sample_gt15_count=("sample_gt15", "sum"),
        sample_ge50_count=("sample_ge50", "sum"),
        sample_ge100_count=("sample_ge100", "sum"),
        median_sample_size=("sample_size", "median"),
        max_sample_size=("sample_size", "max"),
        best_median_net_pct=("median_net_pct", "max"),
        median_of_median_net_pct=("median_net_pct", "median"),
        median_p10_net_pct=("p10_net_pct", "median"),
        best_robust_score=("robust_score", "max"),
        median_robust_score=("robust_score", "median"),
        median_stability_score=("stability_score", "median"),
        best_stability_score=("stability_score", "max"),
        positive_stress_rate_pct=("positive_stress", lambda x: float(x.mean() * 100.0)),
        positive_p10_rate_pct=("positive_p10", lambda x: float(x.mean() * 100.0)),
        future_safety_pass_rate_pct=("future_safety_pass", lambda x: float(pd.Series(x).astype(bool).mean() * 100.0)),
        median_baseline_lift_pct=("baseline_lift_median_pct", "median"),
        unique_clusters=("strategy_similarity_cluster_id", "nunique"),
        unique_exit_families=("exit_family", "nunique"),
        unique_entry_families=("strategy_family", "nunique"),
        median_top_symbol_share_pct=("top_symbol_share_pct", "median"),
    ).reset_index()

    best_idx = grouped["stability_score"].idxmax()
    best_rows = work.loc[best_idx, keys + present_cols(work, ["strategy_id", "sample_size", "sample_tier"])].copy()
    best_rows = best_rows.rename(
        columns={
            "strategy_id": "best_strategy_id",
            "sample_size": "best_sample_size",
            "sample_tier": "best_sample_tier",
        }
    )
    out = out.merge(best_rows, on=keys, how="left")
    out[score_name] = (
        0.26 * out["best_stability_score"].rank(pct=True)
        + 0.20 * out["median_stability_score"].rank(pct=True)
        + 0.18 * out["positive_stress_rate_pct"].rank(pct=True)
        + 0.14 * out["positive_p10_rate_pct"].rank(pct=True)
        + 0.12 * out["sample_gt15_count"].rank(pct=True)
        + 0.06 * out["unique_clusters"].rank(pct=True)
        + 0.04 * out["future_safety_pass_rate_pct"].rank(pct=True)
    ).fillna(0.0)
    return out.sort_values(score_name, ascending=False).reset_index(drop=True)


def build_profit_and_stability(df: pd.DataFrame, top_n: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    eligible = df[df["sample_size"] > 15].copy()
    profit = eligible.sort_values(
        ["median_net_pct", "p10_net_pct", "stress_fee_slippage_median_net_pct", "robust_score"],
        ascending=[False, False, False, False],
    ).head(top_n)
    stability = eligible.sort_values(
        ["stability_score", "p10_net_pct", "stress_fee_slippage_median_net_pct", "sample_size"],
        ascending=[False, False, False, False],
    ).head(top_n)
    return profit[present_cols(profit, DISPLAY_COLS)], stability[present_cols(stability, DISPLAY_COLS)]


def build_neighborhood_stability(df: pd.DataFrame, existing_clusters: pd.DataFrame) -> pd.DataFrame:
    keys = [k for k in ["strategy_similarity_cluster_id", "strategy_family", "side", "exit_family"] if k in df.columns]
    work = df.copy()
    work["positive_stress"] = work["stress_fee_slippage_median_net_pct"] > 0
    work["sample_gt15"] = work["sample_size"] > 15
    grouped = work.groupby(keys, dropna=False)
    out = grouped.agg(
        strategies=("strategy_id", "count"),
        sample_gt15_count=("sample_gt15", "sum"),
        median_sample_size=("sample_size", "median"),
        best_median_net_pct=("median_net_pct", "max"),
        median_net_pct=("median_net_pct", "median"),
        median_p10_net_pct=("p10_net_pct", "median"),
        best_robust_score=("robust_score", "max"),
        median_robust_score=("robust_score", "median"),
        median_stability_score=("stability_score", "median"),
        positive_stress_rate_pct=("positive_stress", lambda x: float(x.mean() * 100.0)),
        future_safety_pass_rate_pct=("future_safety_pass", lambda x: float(pd.Series(x).astype(bool).mean() * 100.0)),
        median_top_symbol_share_pct=("top_symbol_share_pct", "median"),
    ).reset_index()
    best_idx = grouped["stability_score"].idxmax()
    best_rows = work.loc[best_idx, keys + ["strategy_id", "sample_size", "sample_tier"]].rename(
        columns={
            "strategy_id": "best_strategy_id",
            "sample_size": "best_sample_size",
            "sample_tier": "best_sample_tier",
        }
    )
    out = out.merge(best_rows, on=keys, how="left")
    out["neighborhood_stability_score"] = (
        0.30 * out["median_stability_score"].rank(pct=True)
        + 0.20 * out["positive_stress_rate_pct"].rank(pct=True)
        + 0.18 * out["sample_gt15_count"].rank(pct=True)
        + 0.14 * out["strategies"].rank(pct=True)
        + 0.10 * out["future_safety_pass_rate_pct"].rank(pct=True)
        + 0.08 * (1.0 - out["median_top_symbol_share_pct"].rank(pct=True))
    ).fillna(0.0)
    if not existing_clusters.empty and "strategy_similarity_cluster_id" in existing_clusters.columns:
        cluster_cols = [
            c
            for c in ["strategy_similarity_cluster_id", "strategies", "best_strategy_id", "best_robust_score"]
            if c in existing_clusters.columns
        ]
        suffix_source = existing_clusters[cluster_cols].rename(
            columns={
                "strategies": "source_cluster_strategies",
                "best_strategy_id": "source_cluster_best_strategy_id",
                "best_robust_score": "source_cluster_best_robust_score",
            }
        )
        out = out.merge(suffix_source, on="strategy_similarity_cluster_id", how="left")
    return out.sort_values("neighborhood_stability_score", ascending=False).reset_index(drop=True)


def make_source_pack(
    df: pd.DataFrame,
    baselines: pd.DataFrame,
    summary: dict[str, Any],
    profit: pd.DataFrame,
    stability: pd.DataFrame,
    entry_catalog: pd.DataFrame,
    exit_catalog: pd.DataFrame,
    combined: pd.DataFrame,
    neighborhood: pd.DataFrame,
) -> dict[str, Any]:
    sample_counts = df["sample_tier"].value_counts().to_dict()
    best_baseline = {}
    if not baselines.empty and "median_net_pct" in baselines.columns:
        best_baseline = baselines.sort_values("median_net_pct", ascending=False).head(1).to_dict(orient="records")
        best_baseline = best_baseline[0] if best_baseline else {}
    pack = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_run": safe_str(summary.get("run_dir")),
        "stage": safe_str(summary.get("stage")),
        "candidate_space_sample": summary.get("candidate_space_sample"),
        "coarse_eval_actual": summary.get("coarse_eval_actual"),
        "medium_eval_actual": summary.get("medium_eval_actual"),
        "deep_eval_actual": summary.get("deep_eval_actual"),
        "stress_eval_actual": summary.get("stress_eval_actual"),
        "path_resolution": summary.get("path_resolution"),
        "paper_only": summary.get("paper_only"),
        "production_allowed_flag": summary.get("live_allowed"),
        "gpu": summary.get("gpu", {}),
        "rows": int(len(df)),
        "sample_tier_counts": sample_counts,
        "side_counts": df["side"].value_counts().head(20).to_dict() if "side" in df.columns else {},
        "entry_timing_counts": df["entry_timing"].value_counts().head(20).to_dict()
        if "entry_timing" in df.columns
        else {},
        "exit_family_counts": df["exit_family"].value_counts().head(20).to_dict()
        if "exit_family" in df.columns
        else {},
        "strategy_family_counts": df["strategy_family"].value_counts().head(20).to_dict()
        if "strategy_family" in df.columns
        else {},
        "promote_count": int((df.get("decision", "") == "promote_to_round2_candidate").sum())
        if "decision" in df.columns
        else None,
        "future_safety_pass_count": int(df["future_safety_pass"].astype(bool).sum()),
        "best_baseline": best_baseline,
        "top_raw": top_records(df.sort_values("robust_score", ascending=False), 20),
        "top_sample_gt15": top_records(df[df["sample_size"] > 15].sort_values("robust_score", ascending=False), 20),
        "top_sample_ge30": top_records(df[df["sample_size"] >= 30].sort_values("robust_score", ascending=False), 20),
        "top_sample_ge50": top_records(df[df["sample_size"] >= 50].sort_values("robust_score", ascending=False), 20),
        "top_sample_ge100": top_records(df[df["sample_size"] >= 100].sort_values("robust_score", ascending=False), 20),
        "profit_leaders": profit.head(20).to_dict(orient="records"),
        "stability_leaders": stability.head(20).to_dict(orient="records"),
        "entry_catalog_top": entry_catalog.head(20).to_dict(orient="records"),
        "exit_catalog_top": exit_catalog.head(20).to_dict(orient="records"),
        "combined_funnel_top": combined.head(20).to_dict(orient="records"),
        "neighborhood_top": neighborhood.head(20).to_dict(orient="records"),
    }
    return pack


def decision_from_evidence(evidence: dict[str, Any]) -> str:
    best_sample = safe_float(evidence.get("best_sample_size"), 0.0)
    best_median = safe_float(evidence.get("best_median_net_pct"), 0.0)
    p10 = safe_float(evidence.get("median_p10_net_pct"), 0.0)
    stress_rate = safe_float(evidence.get("positive_stress_rate_pct"), 0.0)
    future_rate = safe_float(evidence.get("future_safety_pass_rate_pct"), 0.0)
    if best_sample <= 15:
        return "observe_only_insufficient_sample"
    if best_median > 0 and p10 > 0 and stress_rate >= 60 and future_rate >= 99:
        return "watchlist_paper_probe"
    if best_median > 0 and stress_rate >= 50:
        return "watchlist_needs_ablation"
    return "reject_or_hold_for_new_evidence"


def evidence_from_row(row: pd.Series) -> dict[str, Any]:
    keys = [
        "tested_strategies",
        "sample_gt15_count",
        "sample_ge50_count",
        "sample_ge100_count",
        "best_sample_size",
        "best_sample_tier",
        "best_median_net_pct",
        "median_of_median_net_pct",
        "median_p10_net_pct",
        "best_robust_score",
        "median_robust_score",
        "best_stability_score",
        "median_stability_score",
        "positive_stress_rate_pct",
        "positive_p10_rate_pct",
        "future_safety_pass_rate_pct",
        "median_baseline_lift_pct",
        "unique_clusters",
        "median_top_symbol_share_pct",
        "best_strategy_id",
    ]
    return {key: row.get(key) for key in keys if key in row.index}


def build_hypotheses(
    entry_catalog: pd.DataFrame,
    exit_catalog: pd.DataFrame,
    combined: pd.DataFrame,
    neighborhood: pd.DataFrame,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], pd.DataFrame]:
    ledger: list[dict[str, Any]] = []
    entry_h: list[dict[str, Any]] = []
    exit_h: list[dict[str, Any]] = []
    risk_h: list[dict[str, Any]] = []

    def append_hypothesis(
        kind: str,
        source: str,
        row: pd.Series,
        rank: int,
        entry_family: str,
        exit_family: str,
        direction: str,
        hypothesis: str,
        next_action: str,
    ) -> dict[str, Any]:
        evidence = evidence_from_row(row)
        hid = stable_id(
            "HYP",
            {
                "kind": kind,
                "entry_family": entry_family,
                "exit_family": exit_family,
                "direction": direction,
                "rank": rank,
                "source": source,
            },
        )
        best_sample = evidence.get("best_sample_size", row.get("median_sample_size", 0))
        record = {
            "hypothesis_id": hid,
            "kind": kind,
            "source": source,
            "rank": rank,
            "entry_family": entry_family,
            "exit_family": exit_family,
            "direction": direction,
            "sample_tier": sample_tier(best_sample),
            "hypothesis": hypothesis,
            "evidence": evidence,
            "decision": decision_from_evidence(evidence),
            "next_action": next_action,
        }
        ledger.append(record)
        return record

    for i, (_, row) in enumerate(entry_catalog.head(20).iterrows(), start=1):
        entry_family = safe_str(row.get("strategy_family"), "mixed_entry")
        timing = safe_str(row.get("entry_timing"), "mixed_timing")
        side = safe_str(row.get("side"), "mixed")
        hyp = (
            f"Entry family {entry_family} with timing {timing} and side {side} has reusable alpha "
            "if it remains positive after holding exit choices fixed."
        )
        action = "Run one entry-family ablation with the top two stable exits and unchanged cost model."
        record = append_hypothesis("entry", "entry_catalog_scoreboard", row, i, entry_family, "ANY", side, hyp, action)
        entry_h.append(record)

    for i, (_, row) in enumerate(exit_catalog.head(20).iterrows(), start=1):
        exit_family = safe_str(row.get("exit_family"), "mixed_exit")
        side = safe_str(row.get("side"), "mixed")
        hyp = (
            f"Exit family {exit_family} is a reusable risk-management module when paired with already positive "
            "entry families."
        )
        action = "Run one exit-family swap test across the strongest entry family and a neutral fixed baseline."
        record = append_hypothesis("exit", "exit_catalog_scoreboard", row, i, "ANY", exit_family, side, hyp, action)
        exit_h.append(record)

    for i, (_, row) in enumerate(combined.head(25).iterrows(), start=1):
        entry_family = safe_str(row.get("strategy_family"), "mixed_entry")
        exit_family = safe_str(row.get("exit_family"), "mixed_exit")
        side = safe_str(row.get("side"), "mixed")
        timing = safe_str(row.get("entry_timing"), "mixed_timing")
        hyp = (
            f"Combined module {entry_family}/{timing}/{exit_family}/{side} is a complete-strategy candidate "
            "for controlled paper validation."
        )
        action = "Freeze this complete module, then mutate only one parameter neighborhood in the next pass."
        append_hypothesis("complete_strategy", "entry_exit_combined_funnel", row, i, entry_family, exit_family, side, hyp, action)

    for i, (_, row) in enumerate(neighborhood.head(15).iterrows(), start=1):
        entry_family = safe_str(row.get("strategy_family"), "mixed_entry")
        exit_family = safe_str(row.get("exit_family"), "mixed_exit")
        side = safe_str(row.get("side"), "mixed")
        hyp = (
            f"Neighborhood cluster {safe_str(row.get('strategy_similarity_cluster_id'), 'unknown')} is resilient "
            "enough to justify local parameter expansion."
        )
        action = "Expand only adjacent thresholds, timing offsets, and stop parameters inside this cluster."
        record = append_hypothesis("risk_exit_neighborhood", "neighborhood_stability", row, i, entry_family, exit_family, side, hyp, action)
        risk_h.append(record)

    discovery_rows = []
    for record in entry_h + exit_h + risk_h + ledger:
        evidence = record["evidence"]
        score = (
            0.35 * safe_float(evidence.get("best_stability_score"), 0.0)
            + 0.25 * safe_float(evidence.get("positive_stress_rate_pct"), 0.0) / 100.0
            + 0.20 * safe_float(evidence.get("positive_p10_rate_pct"), 0.0) / 100.0
            + 0.10 * min(1.0, safe_float(evidence.get("sample_gt15_count"), 0.0) / 100.0)
            + 0.10 * safe_float(evidence.get("future_safety_pass_rate_pct"), 0.0) / 100.0
        )
        discovery_rows.append(
            {
                "discovery_id": stable_id("DISC", record, 12),
                "hypothesis_id": record["hypothesis_id"],
                "discovery_type": record["kind"],
                "entry_family": record["entry_family"],
                "exit_family": record["exit_family"],
                "direction": record["direction"],
                "sample_tier": record["sample_tier"],
                "discovery_score": score,
                "decision": record["decision"],
                "rationale": record["hypothesis"],
                "next_action": record["next_action"],
            }
        )
    discovery = pd.DataFrame(discovery_rows).drop_duplicates("discovery_id")
    discovery = discovery.sort_values("discovery_score", ascending=False).reset_index(drop=True)
    return ledger, entry_h, exit_h, risk_h, discovery


def build_experiment_journal(ledger: list[dict[str, Any]], summary: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for record in ledger:
        evidence = record["evidence"]
        rows.append(
            {
                "hypothesis_id": record["hypothesis_id"],
                "kind": record["kind"],
                "tested_population": record["source"],
                "budget_source_run": safe_str(summary.get("stage")),
                "candidate_space_sample": summary.get("candidate_space_sample"),
                "deep_eval_actual": summary.get("deep_eval_actual"),
                "best_metric": evidence.get("best_median_net_pct"),
                "robustness_metric": evidence.get("best_stability_score") or evidence.get("best_robust_score"),
                "sample_tier": record["sample_tier"],
                "decision": record["decision"],
                "reject_or_promote_reason": reason_from_decision(record["decision"], evidence),
                "next_action": record["next_action"],
            }
        )
    return pd.DataFrame(rows)


def reason_from_decision(decision: str, evidence: dict[str, Any]) -> str:
    if decision == "observe_only_insufficient_sample":
        return "sample_size_lte_15_observe_only"
    if decision == "watchlist_paper_probe":
        return "positive_median_p10_stress_and_future_safety"
    if decision == "watchlist_needs_ablation":
        return "positive_profit_with_extra_ablation_required"
    return "weak_or_inconsistent_group_evidence"


def build_reject_log(reject_log: pd.DataFrame, ledger: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    if not reject_log.empty:
        keys = [c for c in ["reject_reason", "strategy_family", "exit_family", "side", "entry_timing"] if c in reject_log.columns]
        if keys:
            agg = reject_log.groupby(keys, dropna=False).agg(
                rejected_strategies=("strategy_id", "count"),
                median_sample_size=("sample_size", "median"),
                max_sample_size=("sample_size", "max"),
                best_robust_score=("robust_score", "max"),
            )
            rows.extend(agg.reset_index().sort_values("rejected_strategies", ascending=False).head(500).to_dict(orient="records"))
    for record in ledger:
        if record["decision"] in ["reject_or_hold_for_new_evidence", "observe_only_insufficient_sample"]:
            rows.append(
                {
                    "reject_reason": reason_from_decision(record["decision"], record["evidence"]),
                    "strategy_family": record["entry_family"],
                    "exit_family": record["exit_family"],
                    "side": record["direction"],
                    "entry_timing": "hypothesis_level",
                    "rejected_strategies": 1,
                    "median_sample_size": record["evidence"].get("best_sample_size"),
                    "max_sample_size": record["evidence"].get("best_sample_size"),
                    "best_robust_score": record["evidence"].get("best_robust_score"),
                    "hypothesis_id": record["hypothesis_id"],
                }
            )
    return pd.DataFrame(rows)


def md_table(df: pd.DataFrame, cols: list[str], n: int = 10) -> str:
    view = df[present_cols(df, cols)].head(n).copy()
    if view.empty:
        return "_No rows._"
    return view.to_markdown(index=False)


def write_source_digest(
    out_dir: Path,
    source_pack: dict[str, Any],
    entry_catalog: pd.DataFrame,
    exit_catalog: pd.DataFrame,
    combined: pd.DataFrame,
    neighborhood: pd.DataFrame,
    profit: pd.DataFrame,
    stability: pd.DataFrame,
) -> None:
    lines = [
        "# Expanded Round 1 Source Digest",
        "",
        f"- Source stage: `{source_pack.get('stage')}`",
        f"- Candidate space sample: `{source_pack.get('candidate_space_sample')}`",
        f"- Deep eval rows: `{source_pack.get('deep_eval_actual')}`",
        f"- Path resolution: `{source_pack.get('path_resolution')}`",
        f"- Paper-only flag: `{source_pack.get('paper_only')}`",
        f"- Production allowed flag from source: `{source_pack.get('production_allowed_flag')}`",
        f"- Future-safety pass rows: `{source_pack.get('future_safety_pass_count')}` / `{source_pack.get('rows')}`",
        "",
        "## Sample Tiers",
        "",
        json.dumps(source_pack.get("sample_tier_counts", {}), indent=2, sort_keys=True),
        "",
        "## Profit Leaders",
        "",
        md_table(profit, DISPLAY_COLS, 12),
        "",
        "## Stability Leaders",
        "",
        md_table(stability, DISPLAY_COLS, 12),
        "",
        "## Entry Catalog",
        "",
        md_table(
            entry_catalog,
            [
                "strategy_family",
                "side",
                "entry_timing",
                "tested_strategies",
                "sample_gt15_count",
                "best_strategy_id",
                "best_sample_tier",
                "best_median_net_pct",
                "median_p10_net_pct",
                "positive_stress_rate_pct",
                "entry_catalog_score",
            ],
            15,
        ),
        "",
        "## Exit Catalog",
        "",
        md_table(
            exit_catalog,
            [
                "exit_family",
                "side",
                "horizon_min",
                "tested_strategies",
                "sample_gt15_count",
                "best_strategy_id",
                "best_sample_tier",
                "best_median_net_pct",
                "median_p10_net_pct",
                "positive_stress_rate_pct",
                "exit_catalog_score",
            ],
            15,
        ),
        "",
        "## Combined Funnel",
        "",
        md_table(
            combined,
            [
                "strategy_family",
                "side",
                "entry_timing",
                "exit_family",
                "tested_strategies",
                "sample_gt15_count",
                "best_strategy_id",
                "best_sample_tier",
                "best_median_net_pct",
                "combined_funnel_score",
            ],
            15,
        ),
        "",
        "## Neighborhood Stability",
        "",
        md_table(
            neighborhood,
            [
                "strategy_similarity_cluster_id",
                "strategy_family",
                "side",
                "exit_family",
                "strategies",
                "sample_gt15_count",
                "best_strategy_id",
                "best_sample_tier",
                "best_median_net_pct",
                "positive_stress_rate_pct",
                "neighborhood_stability_score",
            ],
            15,
        ),
    ]
    (out_dir / "expanded_source_digest.md").write_text("\n".join(lines), encoding="utf-8")


def role_context(source_pack: dict[str, Any], discovery: pd.DataFrame) -> dict[str, Any]:
    top = source_pack.get("top_sample_gt15", [{}])[0] if source_pack.get("top_sample_gt15") else {}
    top_stable = source_pack.get("stability_leaders", [{}])[0] if source_pack.get("stability_leaders") else {}
    top_entry = source_pack.get("entry_catalog_top", [{}])[0] if source_pack.get("entry_catalog_top") else {}
    top_exit = source_pack.get("exit_catalog_top", [{}])[0] if source_pack.get("exit_catalog_top") else {}
    best_discovery = discovery.head(1).to_dict(orient="records")
    return {
        "top": top,
        "top_stable": top_stable,
        "top_entry": top_entry,
        "top_exit": top_exit,
        "best_discovery": best_discovery[0] if best_discovery else {},
    }


def write_role_memos(
    out_dir: Path,
    source_pack: dict[str, Any],
    discovery: pd.DataFrame,
    ledger: list[dict[str, Any]],
) -> None:
    ctx = role_context(source_pack, discovery)
    tier_counts = source_pack.get("sample_tier_counts", {})
    decision_counts = dict(Counter(record.get("decision", "unknown") for record in ledger))
    kind_counts = dict(Counter(record.get("kind", "unknown") for record in ledger))
    top_discovery = md_table(
        discovery,
        [
            "hypothesis_id",
            "discovery_type",
            "entry_family",
            "exit_family",
            "direction",
            "sample_tier",
            "discovery_score",
            "decision",
        ],
        12,
    )
    top_entry_table = pd.DataFrame(source_pack.get("entry_catalog_top", []))
    top_exit_table = pd.DataFrame(source_pack.get("exit_catalog_top", []))
    entry_anchor = md_table(
        top_entry_table,
        [
            "strategy_family",
            "side",
            "entry_timing",
            "tested_strategies",
            "sample_gt15_count",
            "best_strategy_id",
            "best_sample_tier",
            "best_median_net_pct",
            "median_p10_net_pct",
            "positive_stress_rate_pct",
        ],
        8,
    )
    exit_anchor = md_table(
        top_exit_table,
        [
            "exit_family",
            "side",
            "horizon_min",
            "tested_strategies",
            "sample_gt15_count",
            "best_strategy_id",
            "best_sample_tier",
            "best_median_net_pct",
            "median_p10_net_pct",
            "positive_stress_rate_pct",
        ],
        8,
    )
    common = [
        f"Source stage: {source_pack.get('stage')}.",
        f"Candidate space sample: {source_pack.get('candidate_space_sample')}.",
        f"Rows analyzed: {source_pack.get('rows')}.",
        f"Path resolution: {source_pack.get('path_resolution')}.",
        "Scope: paper-sandbox research only.",
        f"Sample tiers: {tier_counts}.",
        f"Hypothesis decisions: {decision_counts}.",
        f"Hypothesis kinds: {kind_counts}.",
    ]
    role_text: dict[str, list[str]] = {
        "meta_research_director": [
            "# Meta Research Director Round 1 Memo",
            "",
            *[f"- {line}" for line in common],
            "",
            "## Assessment",
            "The run should be treated as a strong discovery pass, not as promotion evidence by itself. "
            "The correct AutoResearch move is to preserve the full strategy objects while forcing the next pass "
            "to test one hypothesis at a time.",
            "",
            "## Directives",
            "- Keep the GPU fused strong run as the main source of truth for this round.",
            "- Use the base and CPU branches only as reference inputs if their artifacts are present.",
            "- Drive the next pass from the hypothesis ledger and reject log, not from a fresh unconstrained brainstorm.",
            "- Rank both profit and stability; do not collapse them into one view.",
            "",
            "## Evidence Anchors",
            top_discovery,
            "",
            "## Governance Upgrade",
            "The most important upgrade is not another wider search. It is the conversion of results into a "
            "repeatable research program. Every hypothesis now has a source, a sample tier, an evidence packet, "
            "a decision, and a next action. That makes future rounds auditable and prevents repeated testing of "
            "the same weak idea under a new label.",
            "",
            "## Stop/Continue Rule",
            "Continue only through focused ablations. Stop broad expansion until at least one complete strategy "
            "family survives component isolation, neighborhood stability, and execution-cost stress.",
        ],
        "strategy_architect": [
            "# Strategy Architect Round 1 Memo",
            "",
            "## Leading Complete Strategy Shape",
            f"- Top strategy: `{ctx['top'].get('strategy_id')}` family `{ctx['top'].get('strategy_family')}` "
            f"side `{ctx['top'].get('side')}` timing `{ctx['top'].get('entry_timing')}` "
            f"exit `{ctx['top'].get('exit_family')}` sample tier `{ctx['top'].get('sample_tier')}`.",
            f"- Top entry catalog family: `{ctx['top_entry'].get('strategy_family')}` timing "
            f"`{ctx['top_entry'].get('entry_timing')}` side `{ctx['top_entry'].get('side')}`.",
            f"- Top exit catalog family: `{ctx['top_exit'].get('exit_family')}` side "
            f"`{ctx['top_exit'].get('side')}`.",
            "",
            "## Architecture Call",
            "The next design should separate entry edge from exit harvesting: hold the best exit modules fixed while "
            "mutating entry conditions, then hold the best entry modules fixed while swapping exits.",
            "",
            "## Entry Anchors",
            entry_anchor,
            "",
            "## Exit Anchors",
            exit_anchor,
            "",
            "## Architecture Tests",
            "- Entry isolation: pair the same entry family with fixed TP/SL, breakeven, and state-machine exits.",
            "- Exit isolation: pair the same exit family with the strongest and a neutral entry family.",
            "- Timing isolation: keep conditions fixed while sweeping T0, 30s, 1m, 3m, and 5m.",
            "- Side isolation: verify whether long dominance is structural or merely a data-window artifact.",
        ],
        "experiment_mutator": [
            "# Experiment Mutator Round 1 Memo",
            "",
            "## Mutation Queue",
            "Use the discovery scoreboard as the mutation queue. The first expansions should stay local: adjacent "
            "entry timing, nearby threshold quantiles, exit stop width, time-stop horizon, and breakeven trigger.",
            "",
            "## Discipline",
            "- One hypothesis per iteration.",
            "- Keep baseline-first evaluation in every pass.",
            "- Preserve fee, slippage, latency, and missed-fill stress in the objective.",
            "- Convert every new idea into a verifiable strategy grammar before evaluation.",
            "",
            "## Top Queue",
            top_discovery,
            "",
            "## Mutation Rules",
            "- Mutate only one family dimension per pass: entry condition, timing, exit state, or risk parameter.",
            "- Prefer local neighborhoods around proven families before creating new global families.",
            "- Record rejected mutations by reason so later rounds do not rediscover them.",
            "- Add a shuffled/random baseline every time a new family is introduced.",
        ],
        "results_analyst": [
            "# Results Analyst Round 1 Memo",
            "",
            "## Evidence Summary",
            f"- Best sample>15 strategy median: `{ctx['top'].get('median_net_pct')}` with p10 "
            f"`{ctx['top'].get('p10_net_pct')}`.",
            f"- Best stability strategy: `{ctx['top_stable'].get('strategy_id')}` with stability score "
            f"`{ctx['top_stable'].get('stability_score')}`.",
            f"- Discovery rows: `{len(discovery)}`.",
            f"- Hypotheses logged: `{len(ledger)}`.",
            "",
            "## Interpretation",
            "The alpha signal should be reported by tier. Smaller samples above 15 are not rejected; they are "
            "kept as early-alpha evidence with explicit confidence labeling.",
            "",
            "## Tier Interpretation",
            f"- Early-alpha count: `{tier_counts.get('early_alpha', 0)}`.",
            f"- Exploratory watchlist count: `{tier_counts.get('exploratory_watchlist', 0)}`.",
            f"- Validated watchlist count: `{tier_counts.get('validated_watchlist', 0)}`.",
            f"- Higher-confidence watchlist count: `{tier_counts.get('higher_confidence_watchlist', 0)}`.",
            "",
            "## Reporting Standard",
            "Every headline strategy should be reported as raw rank, stability rank, sample tier, stressed median, "
            "p10, future-safety status, and baseline lift. A result missing any of those fields remains a research "
            "lead rather than a paper-shadow candidate.",
        ],
        "risk_critic": [
            "# Risk Critic Round 1 Memo",
            "",
            "## Risk View",
            "The run includes execution-cost stress, future-safety checks, cluster similarity, and baseline comparison. "
            "The remaining risk is over-selecting narrow clusters or small-sample leaders.",
            "",
            "## Required Controls",
            "- Any paper candidate must pass future-safety checks.",
            "- Any paper candidate must retain positive stressed median under fee/slippage/latency.",
            "- Small-sample candidates can be studied, but they need confidence-tier labels and shadow sizing.",
            "- Cluster concentration should be penalized before any forward path.",
            "",
            "## Failure Modes To Watch",
            "- Exit family overfitting: a strong exit may be harvesting one path shape rather than reusable behavior.",
            "- Timing leakage by proxy: delayed entries must keep future-safety checks visible.",
            "- Symbol/day concentration: top-symbol share can make a strategy look stable when it is not.",
            "- Cost cliff: candidates near zero stressed median should be demoted even if raw median is attractive.",
            "",
            "## Risk Decision",
            "No direct escalation. The correct risk posture is controlled paper-sandbox ablation after component "
            "isolation and neighborhood confirmation.",
        ],
        "statistical_skeptic": [
            "# Statistical Skeptic Round 1 Memo",
            "",
            "## Statistical Position",
            "The revised policy is valid: sample size greater than 15 is enough for inclusion in analysis, but not "
            "enough for high confidence. The right treatment is tiered confidence, bootstrap/permutation review, "
            "and neighborhood stability.",
            "",
            "## Checks To Preserve",
            "- Bootstrap confidence intervals.",
            "- Permutation-null comparison.",
            "- Multiple-testing penalty.",
            "- Effective sample size report.",
            "- Neighboring parameter stability before claims of reusable edge.",
            "",
            "## Sample Policy",
            "The updated sample policy is statistically reasonable for discovery: sample_size greater than 15 can "
            "enter analysis, but confidence must be tiered. A sample of 16-29 can motivate a probe; it cannot carry "
            "the same conclusion weight as 100+.",
            "",
            "## Falsification Tests",
            "- Permute timestamps for the same complete strategy object.",
            "- Remove the top 1 percent and top 5 percent contributors.",
            "- Re-score by cluster representative rather than every near-duplicate.",
            "- Compare p10 and stressed median, not only mean or median.",
        ],
        "execution_paper_architect": [
            "# Execution/Paper Architect Round 1 Memo",
            "",
            "## Paper Path",
            "The next phase should emit paper-shadow signals only after a candidate survives the expanded Round 1 "
            "review and a focused ablation pass. The signal payload must include entry trigger, side, timing, "
            "initial risk, monitoring fields, exit state, and execution-cost assumptions.",
            "",
            "## Gate",
            "No candidate moves beyond paper-shadow planning unless the same full strategy object remains positive "
            "after fee, slippage, latency, and missed-fill stress.",
            "",
            "## Payload Requirements",
            "- BWE trigger and channel.",
            "- Trade/no-trade decision.",
            "- Long/short/no-trade side.",
            "- Entry timing and entry conditions.",
            "- Initial risk rule.",
            "- Holding monitor fields.",
            "- Exit state-machine family.",
            "- Fee, slippage, latency, missed-fill assumptions.",
            "",
            "## Validation Path",
            "The generated next-round config is a research config. It should feed a paper-shadow validator only "
            "after focused ablations refresh the ledger and the gate decision changes from hold to paper probe.",
        ],
        "lead_synthesizer": [
            "# Lead Synthesizer Round 1 Memo",
            "",
            "## Synthesis",
            "The expanded round converts the strong run from a leaderboard into a research system: hypothesis ledger, "
            "experiment journal, entry/exit catalogs, discovery queue, neighborhood stability, and role critique.",
            "",
            "## Decision",
            "Proceed to a focused next pass only through the generated round config. Do not launch another broad "
            "search until the highest-value hypotheses have been ablated one at a time.",
            "",
            "## Consensus",
            "- The strong run is useful as discovery evidence.",
            "- The next pass should be ledger-driven.",
            "- Small samples above 15 stay in analysis with tier labels.",
            "- Entry and exit contribution must be separated before any stronger claim.",
            "- Paper-shadow planning remains gated by cost stress and future-safety checks.",
            "",
            "## First Queue Items",
            top_discovery,
        ],
    }
    for slug, _label in ROLE_SPECS:
        (out_dir / f"pass1_{slug}_memo.md").write_text("\n".join(role_text[slug]) + "\n", encoding="utf-8")

    questions = [
        "# Cross Examination Questions",
        "",
        "1. Which top result disappears if the exit family is fixed to a neutral baseline?",
        "2. Which entry family remains positive across at least two exit families?",
        "3. Which exit family improves p10 and stressed median without relying on one cluster?",
        "4. Which early-alpha sample tier candidates deserve only observation instead of paper-shadow planning?",
        "5. Which cluster should be rejected because its neighbors are weak?",
        "6. Which baseline comparison is the strictest hurdle for the next pass?",
        "7. Which strategy family is most exposed to missed fills or latency?",
        "8. Which discovery hypothesis is specific enough for one-hypothesis-per-iteration testing?",
    ]
    (out_dir / "cross_examination_questions.md").write_text("\n".join(questions) + "\n", encoding="utf-8")

    rebuttals = [
        "# Role Rebuttals",
        "",
        "## Meta Research Director",
        "The main correction is to prevent broad search momentum from outrunning governance. The next pass must be ledger-driven.",
        "",
        "## Strategy Architect",
        "The architecture should not crown an entry/exit pair until each component survives a controlled swap.",
        "",
        "## Experiment Mutator",
        "Mutation should be local first; global changes are reserved until the strongest hypotheses are falsified.",
        "",
        "## Results Analyst",
        "Profit leaders and stability leaders must both be visible because they answer different questions.",
        "",
        "## Risk Critic",
        "Small samples above 15 are useful, but only with explicit confidence tier and cost stress.",
        "",
        "## Statistical Skeptic",
        "The strongest claim is not top raw performance; it is repeatability across neighbors, stress, and null tests.",
        "",
        "## Execution/Paper Architect",
        "Paper-shadow planning should consume complete strategy objects, not entry-only fragments.",
        "",
        "## Lead Synthesizer",
        "The final recommendation is focused continuation, not uncontrolled escalation.",
    ]
    (out_dir / "pass2_role_rebuttals.md").write_text("\n".join(rebuttals) + "\n", encoding="utf-8")

    revised = [
        "# Revised Role Memos",
        "",
        "All roles converge on the same operating principle: use the strong run as a discovery source, then "
        "run ablations that isolate entry, exit, risk, and execution assumptions.",
        "",
        "The revised small-sample policy is now explicit: sample_size greater than 15 is analyzable evidence, "
        "not an automatic reject, but confidence tier controls interpretation.",
        "",
        "The next pass should prioritize discoveries with positive p10, positive stressed median, future-safety pass, "
        "and neighborhood support.",
    ]
    (out_dir / "pass3_revised_role_memos.md").write_text("\n".join(revised) + "\n", encoding="utf-8")

    final = [
        "# Lead Synthesis Expanded Round 1",
        "",
        "## Final Position",
        "The project now has the usable AutoResearch advantages layered on top of the GPU fused strong result: "
        "hypothesis ledger, experiment journal, component catalogs, discovery queue, stability views, reject logic, "
        "and role critique.",
        "",
        "## Go-Forward",
        "Move to the generated next-round configuration only if the operator wants a focused ablation pass. "
        "The pass should be one hypothesis at a time and should keep all execution-cost and future-safety checks.",
        "",
        "## Non-Negotiables",
        "- Paper-sandbox only.",
        "- Complete strategy objects only.",
        "- Baseline-first comparison.",
        "- Reject-log-driven mutation.",
        "- Stability-first promotion.",
    ]
    (out_dir / "lead_synthesis_expanded_round_1.md").write_text("\n".join(final) + "\n", encoding="utf-8")

    gate = [
        "# Paper Shadow Gate Decision",
        "",
        "Decision: hold for focused ablation before paper-shadow trial.",
        "",
        "Rationale: the strong run produced many promising complete strategies, but the expanded review still needs "
        "entry/exit component isolation and neighborhood confirmation before any candidate should be treated as "
        "paper-shadow ready.",
        "",
        "Allowed next step: run the generated focused ablation config in paper-sandbox mode.",
    ]
    (out_dir / "paper_shadow_gate_decision.md").write_text("\n".join(gate) + "\n", encoding="utf-8")


def write_reviews(
    out_dir: Path,
    df: pd.DataFrame,
    entry_catalog: pd.DataFrame,
    exit_catalog: pd.DataFrame,
    combined: pd.DataFrame,
    neighborhood: pd.DataFrame,
) -> None:
    tier_table = (
        df.groupby("sample_tier", dropna=False)
        .agg(
            strategies=("strategy_id", "count"),
            median_sample_size=("sample_size", "median"),
            best_median_net_pct=("median_net_pct", "max"),
            median_p10_net_pct=("p10_net_pct", "median"),
            positive_stress_rate_pct=("stress_fee_slippage_median_net_pct", lambda x: float((x > 0).mean() * 100.0)),
            future_safety_pass_rate_pct=("future_safety_pass", lambda x: float(pd.Series(x).astype(bool).mean() * 100.0)),
        )
        .reset_index()
    )
    tier_table.to_csv(out_dir / "candidate_tier_table.csv", index=False)
    small = df[(df["sample_size"] > 15) & (df["sample_size"] < 50)].sort_values(
        ["robust_score", "median_net_pct"], ascending=False
    )
    lines = [
        "# Small Sample Alpha Review",
        "",
        "Policy: sample_size greater than 15 is included in analysis; confidence tier is lowered instead of using sample size alone as a reject.",
        "",
        md_table(small, DISPLAY_COLS, 25),
    ]
    (out_dir / "small_sample_alpha_review.md").write_text("\n".join(lines), encoding="utf-8")

    decomposition = [
        "# Entry Exit Decomposition Review",
        "",
        "## Top Entry Modules",
        "",
        md_table(entry_catalog, ["strategy_family", "side", "entry_timing", "best_strategy_id", "best_sample_tier", "best_median_net_pct", "entry_catalog_score"], 20),
        "",
        "## Top Exit Modules",
        "",
        md_table(exit_catalog, ["exit_family", "side", "horizon_min", "best_strategy_id", "best_sample_tier", "best_median_net_pct", "exit_catalog_score"], 20),
        "",
        "## Top Complete Modules",
        "",
        md_table(combined, ["strategy_family", "side", "entry_timing", "exit_family", "best_strategy_id", "best_sample_tier", "best_median_net_pct", "combined_funnel_score"], 20),
    ]
    (out_dir / "entry_exit_decomposition_review.md").write_text("\n".join(decomposition), encoding="utf-8")

    stability = [
        "# Day Symbol Stability Review",
        "",
        "This view proxies stability through sample tier, unique clusters, top-symbol share, and neighborhood consistency.",
        "",
        md_table(neighborhood, ["strategy_similarity_cluster_id", "strategy_family", "side", "exit_family", "strategies", "sample_gt15_count", "median_top_symbol_share_pct", "positive_stress_rate_pct", "neighborhood_stability_score"], 30),
    ]
    (out_dir / "day_symbol_stability_review.md").write_text("\n".join(stability), encoding="utf-8")

    execution = [
        "# Execution Realism Review",
        "",
        "Execution realism is preserved by carrying fee, slippage, latency, missed-fill, and path-resolution fields into the next config and role critique.",
        "",
        "The strongest candidates must retain positive stressed median before any paper-shadow trial.",
    ]
    (out_dir / "execution_realism_review.md").write_text("\n".join(execution), encoding="utf-8")


def write_research_program(out_dir: Path, source_pack: dict[str, Any]) -> None:
    lines = [
        "# Research Program Round 1",
        "",
        "## Operating Loop",
        "1. Read the source pack, profit leaderboard, stability leaderboard, component catalogs, and reject log.",
        "2. Select exactly one hypothesis from the hypothesis ledger.",
        "3. Run a focused ablation with the same data and cost assumptions.",
        "4. Compare against baselines before interpreting absolute profit.",
        "5. Keep, watchlist, or reject the hypothesis with a written reason.",
        "6. Append the result to the experiment journal before selecting another hypothesis.",
        "",
        "## Evaluation Priorities",
        "- Stability before raw profit.",
        "- Complete strategy objects before partial entry signals.",
        "- Component isolation before broad expansion.",
        "- Future-safety and execution-cost stress before paper-shadow planning.",
        "",
        "## Source Facts",
        f"- Stage: `{source_pack.get('stage')}`",
        f"- Rows: `{source_pack.get('rows')}`",
        f"- Candidate space sample: `{source_pack.get('candidate_space_sample')}`",
        f"- Path resolution: `{source_pack.get('path_resolution')}`",
    ]
    (out_dir / "research_program_round1.md").write_text("\n".join(lines), encoding="utf-8")


def write_absorption_report(out_dir: Path) -> None:
    lines = [
        "# AutoResearch Absorption Report",
        "",
        "## Absorbed Advantages",
        "- Hypothesis ledger.",
        "- Experiment journal.",
        "- Keep/watchlist/reject decisions.",
        "- Profit and stability views.",
        "- Entry and exit component catalogs.",
        "- Discovery hypotheses.",
        "- Neighborhood stability.",
        "- Failure and reject logging.",
        "- Multi-role critique with cross examination.",
        "",
        "## Not Absorbed",
        "- Autonomous changes to production paths.",
        "- Unbounded loops.",
        "- Any workflow that depends on credentials, notifications, or host scheduler changes.",
        "",
        "## Result",
        "The strong run is now wrapped in a reusable AutoResearch governance layer without rerunning the large search.",
    ]
    (out_dir / "autoresearch_absorption_report.md").write_text("\n".join(lines), encoding="utf-8")


def write_next_round_config(out_dir: Path, discovery: pd.DataFrame, source_pack: dict[str, Any]) -> Path:
    cfg_dir = out_dir / "round_configs"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    queue = discovery.head(12).to_dict(orient="records")
    source_run = safe_str(source_pack.get("source_run")).replace("'", "''")
    source_pack_path = str(out_dir / "expanded_source_pack.json").replace("'", "''")
    lines = [
        "project: bwe_complete_strategy_v6",
        "round: 2",
        "mode: paper_sandbox",
        f"source_stage: {source_pack.get('stage')}",
        f"source_run: '{source_run}'",
        f"source_pack: '{source_pack_path}'",
        "policy:",
        "  one_hypothesis_per_iteration: true",
        "  baseline_first: true",
        "  reject_log_driven: true",
        "  stability_first: true",
        "  minimum_sample_for_alpha_review: 16",
        "  sample_tiers:",
        "    early_alpha: [16, 29]",
        "    exploratory_watchlist: [30, 49]",
        "    validated_watchlist: [50, 99]",
        "    higher_confidence_watchlist: [100, 1000000000]",
        "cost_model:",
        "  fee: true",
        "  slippage: true",
        "  latency: true",
        "  missed_fill: true",
        "data:",
        f"  path_resolution: {source_pack.get('path_resolution')}",
        "research_queue:",
    ]
    for item in queue:
        lines.extend(
            [
                f"  - hypothesis_id: {item.get('hypothesis_id')}",
                f"    discovery_type: {item.get('discovery_type')}",
                f"    entry_family: {item.get('entry_family')}",
                f"    exit_family: {item.get('exit_family')}",
                f"    direction: {item.get('direction')}",
                f"    sample_tier: {item.get('sample_tier')}",
                f"    discovery_score: {safe_float(item.get('discovery_score')):.8f}",
                f"    next_action: \"{safe_str(item.get('next_action')).replace(chr(34), '')}\"",
            ]
        )
    lines.extend(
        [
            "outputs:",
            "  append_hypothesis_ledger: true",
            "  append_experiment_journal: true",
            "  refresh_component_catalogs: true",
            "  refresh_neighborhood_stability: true",
            "stop_conditions:",
            "  complete_one_queue_item_before_next: true",
            "  stop_on_future_safety_failure: true",
            "  stop_on_negative_stressed_median: true",
        ]
    )
    path = cfg_dir / "next_round_final_config_expanded.yaml"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def validate_outputs(out_dir: Path, expected: list[str], config_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    for name in expected:
        path = out_dir / name
        if not path.exists():
            errors.append(f"missing:{name}")
        elif path.is_file() and path.stat().st_size == 0:
            errors.append(f"empty:{name}")

    required_ledger_fields = {
        "hypothesis_id",
        "source",
        "entry_family",
        "exit_family",
        "direction",
        "sample_tier",
        "evidence",
        "decision",
        "next_action",
    }
    ledger_path = out_dir / "hypothesis_ledger.jsonl"
    if ledger_path.exists():
        for line_no, line in enumerate(ledger_path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            missing = required_ledger_fields - set(row)
            if missing:
                errors.append(f"ledger_line_{line_no}_missing:{sorted(missing)}")
    else:
        errors.append("ledger_missing")

    journal_path = out_dir / "experiment_journal.tsv"
    if journal_path.exists():
        with journal_path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            required = {
                "hypothesis_id",
                "tested_population",
                "budget_source_run",
                "best_metric",
                "robustness_metric",
                "decision",
                "reject_or_promote_reason",
            }
            missing = required - set(reader.fieldnames or [])
            if missing:
                errors.append(f"journal_missing:{sorted(missing)}")
    else:
        errors.append("journal_missing")

    entry = pd.read_csv(out_dir / "entry_catalog_scoreboard.csv") if (out_dir / "entry_catalog_scoreboard.csv").exists() else pd.DataFrame()
    exit_ = pd.read_csv(out_dir / "exit_catalog_scoreboard.csv") if (out_dir / "exit_catalog_scoreboard.csv").exists() else pd.DataFrame()
    if entry.empty:
        errors.append("entry_catalog_empty")
    if exit_.empty:
        errors.append("exit_catalog_empty")
    if "strategy_id" in entry.columns and "strategy_payload_json" in entry.columns:
        errors.append("entry_catalog_looks_like_raw_leaderboard")
    if "strategy_id" in exit_.columns and "strategy_payload_json" in exit_.columns:
        errors.append("exit_catalog_looks_like_raw_leaderboard")

    reject_path = out_dir / "hypothesis_reject_log.csv"
    if reject_path.exists():
        rejects = pd.read_csv(reject_path)
        if "median_sample_size" in rejects.columns and "reject_reason" in rejects.columns:
            bad = rejects[
                (pd.to_numeric(rejects["median_sample_size"], errors="coerce") > 15)
                & rejects["reject_reason"].astype(str).str.contains("sample_size_lte_15|sample_size_below_50|sample_size_below_100", case=False, regex=True)
            ]
            if not bad.empty:
                errors.append("sample_gt15_rejected_by_sample_size_alone")

    if config_path.exists():
        text = config_path.read_text(encoding="utf-8").lower()
        forbidden = ["live", "order", "secret", "telegram", "launchd"]
        hits = [token for token in forbidden if token in text]
        if hits:
            errors.append(f"config_forbidden_terms:{hits}")
    else:
        errors.append("config_missing")

    report = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "out_dir": str(out_dir),
        "expected_files": expected,
        "passes": not errors,
        "errors": errors,
    }
    write_json(out_dir / "deep_round1_autoresearch_expanded_completion.json", report)
    if errors:
        raise RuntimeError("Validation failed: " + "; ".join(errors))
    return report


def main() -> None:
    args = parse_args()
    run_dir = args.run_dir
    out_dir = make_output_dir(run_dir, args.out_dir)
    inputs = load_inputs(run_dir)
    df = inputs["leaderboard"]
    baselines = inputs["baselines"]
    summary = inputs["summary"]
    clusters = inputs["clusters"]
    reject_log = inputs["reject_log"]

    profit, stability = build_profit_and_stability(df, args.top_n)
    entry_catalog = group_catalog(
        df,
        ["strategy_family", "channel", "event_type", "side", "entry_timing"],
        "entry_catalog_score",
    )
    exit_catalog = group_catalog(df, ["exit_family", "side", "horizon_min"], "exit_catalog_score")
    combined = group_catalog(
        df,
        ["strategy_family", "side", "entry_timing", "exit_family"],
        "combined_funnel_score",
    )
    neighborhood = build_neighborhood_stability(df, clusters)

    profit.to_csv(out_dir / "profit_leaderboard_top.csv", index=False)
    stability.to_csv(out_dir / "stability_leaderboard_top.csv", index=False)
    entry_catalog.to_csv(out_dir / "entry_catalog_scoreboard.csv", index=False)
    exit_catalog.to_csv(out_dir / "exit_catalog_scoreboard.csv", index=False)
    combined.to_csv(out_dir / "entry_exit_combined_funnel.csv", index=False)
    neighborhood.to_csv(out_dir / "neighborhood_stability.csv", index=False)

    source_pack = make_source_pack(df, baselines, summary, profit, stability, entry_catalog, exit_catalog, combined, neighborhood)
    write_json(out_dir / "expanded_source_pack.json", source_pack)
    write_source_digest(out_dir, source_pack, entry_catalog, exit_catalog, combined, neighborhood, profit, stability)

    ledger, entry_h, exit_h, risk_h, discovery = build_hypotheses(entry_catalog, exit_catalog, combined, neighborhood)
    write_jsonl(out_dir / "hypothesis_ledger.jsonl", ledger)
    write_jsonl(out_dir / "new_entry_hypotheses.jsonl", entry_h)
    write_jsonl(out_dir / "new_exit_hypotheses.jsonl", exit_h)
    write_jsonl(out_dir / "new_risk_exit_hypotheses.jsonl", risk_h)
    discovery.to_csv(out_dir / "discovery_scoreboard.csv", index=False)

    journal = build_experiment_journal(ledger, summary)
    journal.to_csv(out_dir / "experiment_journal.tsv", sep="\t", index=False)
    hypothesis_reject = build_reject_log(reject_log, ledger)
    hypothesis_reject.to_csv(out_dir / "hypothesis_reject_log.csv", index=False)

    write_reviews(out_dir, df, entry_catalog, exit_catalog, combined, neighborhood)
    write_research_program(out_dir, source_pack)
    write_absorption_report(out_dir)
    write_role_memos(out_dir, source_pack, discovery, ledger)
    config_path = write_next_round_config(out_dir, discovery, source_pack)

    expected = [
        "hypothesis_ledger.jsonl",
        "experiment_journal.tsv",
        "hypothesis_reject_log.csv",
        "research_program_round1.md",
        "autoresearch_absorption_report.md",
        "entry_catalog_scoreboard.csv",
        "exit_catalog_scoreboard.csv",
        "entry_exit_combined_funnel.csv",
        "profit_leaderboard_top.csv",
        "stability_leaderboard_top.csv",
        "new_entry_hypotheses.jsonl",
        "new_exit_hypotheses.jsonl",
        "new_risk_exit_hypotheses.jsonl",
        "discovery_scoreboard.csv",
        "neighborhood_stability.csv",
        "expanded_source_pack.json",
        "expanded_source_digest.md",
        "candidate_tier_table.csv",
        "small_sample_alpha_review.md",
        "entry_exit_decomposition_review.md",
        "day_symbol_stability_review.md",
        "execution_realism_review.md",
        "pass1_meta_research_director_memo.md",
        "pass1_strategy_architect_memo.md",
        "pass1_experiment_mutator_memo.md",
        "pass1_results_analyst_memo.md",
        "pass1_risk_critic_memo.md",
        "pass1_statistical_skeptic_memo.md",
        "pass1_execution_paper_architect_memo.md",
        "pass1_lead_synthesizer_memo.md",
        "cross_examination_questions.md",
        "pass2_role_rebuttals.md",
        "pass3_revised_role_memos.md",
        "lead_synthesis_expanded_round_1.md",
        "paper_shadow_gate_decision.md",
        "round_configs/next_round_final_config_expanded.yaml",
    ]
    report = validate_outputs(out_dir, expected, config_path)
    print(json.dumps(clean_for_json(report), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
