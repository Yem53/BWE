"""Aggressive max-alpha runner for BWE v6 paper research.

The runner keeps the complete v6 strategy objects and validation outputs, but
parallelizes the expensive coarse stage across CPU workers and evaluates one
shared strong promotion pool. The base output is the prefix of that same pool,
so base and strong do not pay for duplicate 100M coarse searches.
"""

from __future__ import annotations

import argparse
import csv
import heapq
import json
import math
import os
import random
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bwe_autoresearch.v6_complete_strategy import (
    ENTRY_DELAYS_SECONDS,
    EXIT_FAMILIES,
    HORIZONS_MINUTES,
    SIDES,
    Candidate,
    SmokeContext,
    append_research_ledger,
    approximate_exit_returns,
    candidate_from_payload,
    candidate_mask,
    capture_giveback_estimates,
    clean_json,
    compute_metrics,
    ensure_dir,
    evaluate_baselines,
    generate_candidates,
    medium_heap_row,
    numeric_quantiles,
    portfolio_drawdown,
    resolve_root,
    simulate_exit_gpu,
    utc_now_iso,
    write_execution_outputs,
    write_future_safety_report,
    write_json,
    write_jsonl,
    write_markdown_summaries,
    write_medium_gate_report,
    write_similarity_outputs,
    write_statistical_outputs,
)


FIELDNAMES = [
    "strategy_id",
    "strategy_family",
    "channel",
    "event_type",
    "side",
    "entry_timing",
    "entry_delay_s",
    "entry_conditions_json",
    "exit_family",
    "exit_state_machine_json",
    "risk_rule_json",
    "portfolio_rule_json",
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
    "decision",
    "reject_reason",
    "path_resolution",
    "paper_only",
    "live_allowed",
    "strategy_fingerprint",
    "strategy_similarity_cluster_id",
    "robust_score",
    "stage",
    "candidate_seed",
    "strategy_payload_json",
]


SEED_SCORE_FIELDNAMES = ["robust_score", "candidate_seed"]


def build_candidate_space(ctx: SmokeContext) -> dict[str, Any]:
    q: dict[str, dict[float, float]] = {}
    for field in [
        "move_pct",
        "oi_ratio_pct",
        "oi_change_pct",
        "quote_volume_24h",
        "marketcap",
        "listing_age_days",
        "taker_buy_sell_volume__buySellRatio",
        "basis_perpetual__basisRate",
        "funding_rate",
        "global_long_short_account_ratio__longShortRatio",
        "top_trader_long_short_account_ratio__longShortRatio",
    ]:
        if field in ctx.features:
            q[field] = numeric_quantiles(ctx.features[field], [0.2, 0.35, 0.5, 0.65, 0.8])
    return {
        "channels": sorted(set(ctx.features["channel"])),
        "event_types": sorted(set(ctx.features["event_type"])),
        "strategy_families": [
            "message_context_breakout",
            "oi_funding_continuation",
            "taker_flow_reversal",
            "premium_basis_overheat",
            "liquidity_filtered_momentum",
            "freshness_strict_confirmation",
            "cross_channel_continuation",
            "contrarian_crash_fade",
            "no_trade_freshness_boundary",
            "state_machine_runner",
        ],
        "quantiles": q,
        "numeric_fields": list(q),
    }


def candidate_from_seed(space: dict[str, Any], seed: int) -> Candidate:
    rng = random.Random(int(seed))
    family = rng.choice(space["strategy_families"])
    channel = rng.choice(space["channels"] + ["ANY", "ANY"])
    event_type = rng.choice(space["event_types"] + ["ANY"])
    side = rng.choices(SIDES, weights=[0.45, 0.45, 0.10], k=1)[0]
    delay = rng.choice(ENTRY_DELAYS_SECONDS)
    horizon = rng.choice(HORIZONS_MINUTES)
    exit_family = rng.choice(EXIT_FAMILIES)
    tp = rng.choice([0.004, 0.006, 0.008, 0.01, 0.015, 0.02, 0.03, 0.05, 0.08])
    sl = rng.choice([0.004, 0.006, 0.008, 0.01, 0.015, 0.02, 0.03, 0.05])
    trail = rng.choice([0.003, 0.005, 0.008, 0.012, 0.02, 0.03])
    be = rng.choice([0.004, 0.006, 0.01, 0.015, 0.02, 0.03])
    conds: list[dict[str, Any]] = []
    max_conditions = rng.choices([0, 1, 2, 3, 4], weights=[0.10, 0.25, 0.35, 0.22, 0.08], k=1)[0]
    fields = rng.sample(space["numeric_fields"], k=min(max_conditions, len(space["numeric_fields"])))
    for field in fields:
        op = rng.choice([">=", "<="])
        quantile = rng.choice([0.2, 0.35, 0.5, 0.65, 0.8])
        threshold = space["quantiles"][field][quantile]
        conds.append({"field": field, "op": op, "threshold": threshold, "source": "entry_time_features"})
    if rng.random() < 0.35:
        bucket = rng.choice(["high", "mid", "low", "nan"])
        conds.append({"field": "liquidity_bucket", "op": "in", "values": [bucket], "source": "entry_time_features"})
    if rng.random() < 0.45:
        age_limit = rng.choice([5 * 60000, 10 * 60000])
        conds.append({"field": "mark_1m_age_ms", "op": "<=", "threshold": age_limit, "source": "entry_time_features"})
    portfolio_rule = {
        "shape": rng.choice(["cooldown30_max3", "cooldown60_max5", "cooldown120_max8"]),
        "one_position_per_symbol": True,
        "same_symbol_cooldown_minutes": rng.choice([30, 60, 120]),
        "max_concurrent_positions": rng.choice([3, 5, 8]),
    }
    risk_rule = {
        "shape": rng.choice(["balanced", "left_tail_strict", "stress_strict"]),
        "initial_stop_pct": sl,
        "position_sizing": "unit_notional_paper",
        "fee_model_id": "base_taker",
        "slippage_model_id": "liquidity_aware",
        "latency_model_id": "base_1s",
    }
    return Candidate(
        family,
        channel,
        event_type,
        side,
        delay,
        horizon,
        exit_family,
        tp,
        sl,
        trail,
        be,
        conds,
        portfolio_rule,
        risk_rule,
        int(seed),
    )


def mask_cache_key(cand: Any) -> str:
    return "|".join(
        [
            str(cand.channel),
            str(cand.event_type),
            json.dumps(clean_json(cand.conditions), ensure_ascii=False, sort_keys=True),
        ]
    )


def return_cache_key(cand: Any) -> tuple[Any, ...]:
    return (
        cand.side,
        cand.entry_delay_s,
        cand.horizon_min,
        cand.exit_family,
        cand.tp_pct,
        cand.sl_pct,
        cand.trail_pct,
        cand.be_trigger_pct,
    )


def worker_coarse(
    root_str: str,
    shared_dir_str: str,
    worker_id: int,
    count: int,
    seed: int,
    top_keep: int,
    checkpoint_every: int,
    ret_cache_max: int,
    mask_cache_max: int,
) -> dict[str, Any]:
    os.environ["BWE_V6_DISABLE_TORCH_PATH"] = "1"
    root = Path(root_str)
    shared_dir = ensure_dir(Path(shared_dir_str))
    checkpoints = ensure_dir(shared_dir / "checkpoints")
    ctx = SmokeContext(root, use_torch_path=False)
    space = build_candidate_space(ctx)
    component_cache: dict[tuple[str, int, int], tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    ret_cache: dict[tuple[Any, ...], np.ndarray] = {}
    mask_cache: dict[str, tuple[np.ndarray, str | None]] = {}
    heap: list[tuple[float, int, int]] = []
    reject_counts: Counter[str] = Counter()
    reject_cluster_counts: Counter[str] = Counter()
    reject_samples: list[dict[str, Any]] = []
    start = time.time()

    for seq in range(1, count + 1):
        candidate_seed = seed + seq - 1
        cand = candidate_from_seed(space, candidate_seed)
        mkey = mask_cache_key(cand)
        cached_mask = mask_cache.get(mkey)
        if cached_mask is None:
            cached_mask = candidate_mask(ctx, cand)
            if len(mask_cache) >= mask_cache_max:
                mask_cache.clear()
            mask_cache[mkey] = cached_mask
        mask, hint = cached_mask

        rkey = return_cache_key(cand)
        ret = ret_cache.get(rkey)
        if ret is None:
            ret = approximate_exit_returns(ctx, cand, component_cache)
            if len(ret_cache) >= ret_cache_max:
                ret_cache.clear()
            ret_cache[rkey] = ret

        metrics = compute_metrics(ctx, cand, ret, mask, hint, stage="coarse", path_resolution=ctx.path_resolution)
        score = float(metrics["robust_score"])
        if len(heap) < top_keep:
            heapq.heappush(heap, (score, seq, candidate_seed))
        elif score > heap[0][0]:
            heapq.heapreplace(heap, (score, seq, candidate_seed))

        if metrics["decision"] == "reject":
            reason = metrics.get("reject_reason") or "unknown"
            cluster = metrics.get("strategy_similarity_cluster_id") or "unknown"
            reject_counts[reason] += 1
            reject_cluster_counts[f"{reason}|{cluster}"] += 1
            if len(reject_samples) < 5000:
                reject_samples.append(
                    {
                        "strategy_id": metrics["strategy_id"],
                        "strategy_family": metrics["strategy_family"],
                        "side": metrics["side"],
                        "entry_timing": metrics["entry_timing"],
                        "exit_family": metrics["exit_family"],
                        "sample_size": metrics["sample_size"],
                        "reject_reason": reason,
                        "strategy_similarity_cluster_id": cluster,
                        "robust_score": metrics["robust_score"],
                    }
                )

        if seq % checkpoint_every == 0:
            write_json(
                checkpoints / f"worker_{worker_id:02d}_progress.json",
                {
                    "worker_id": worker_id,
                    "evaluated": seq,
                    "assigned_count": count,
                    "top_heap_size": len(heap),
                    "reject_counts": dict(reject_counts),
                    "elapsed_seconds": time.time() - start,
                    "path_resolution": ctx.path_resolution,
                    "ret_cache_size": len(ret_cache),
                    "mask_cache_size": len(mask_cache),
                },
            )

    top_rows = sorted(heap, key=lambda x: x[0], reverse=True)
    shard_path = shared_dir / f"worker_{worker_id:02d}_top.csv"
    with shard_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SEED_SCORE_FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        for score, _, candidate_seed in top_rows:
            writer.writerow({"robust_score": score, "candidate_seed": candidate_seed})

    reject_path = shared_dir / f"worker_{worker_id:02d}_reject_samples.csv"
    pd.DataFrame(reject_samples).to_csv(reject_path, index=False)
    summary = {
        "worker_id": worker_id,
        "assigned_count": count,
        "evaluated": count,
        "top_rows": len(top_rows),
        "reject_counts": dict(reject_counts),
        "reject_cluster_counts": dict(reject_cluster_counts),
        "shard_path": str(shard_path),
        "reject_sample_path": str(reject_path),
        "elapsed_seconds": time.time() - start,
        "path_resolution": ctx.path_resolution,
    }
    write_json(shared_dir / f"worker_{worker_id:02d}_summary.json", summary)
    return summary


def merge_sorted_shards(
    shard_paths: list[Path],
    strong_limit: int,
    base_limit: int,
    strong_csv: Path,
    base_csv: Path,
    strong_deep_limit: int,
) -> list[dict[str, Any]]:
    handles: list[Any] = []
    readers: list[csv.DictReader] = []
    heap: list[tuple[float, int, dict[str, Any]]] = []
    deep_rows: list[dict[str, Any]] = []
    try:
        for idx, path in enumerate(shard_paths):
            handle = path.open("r", newline="", encoding="utf-8")
            reader = csv.DictReader(handle)
            handles.append(handle)
            readers.append(reader)
            first = next(reader, None)
            if first is not None:
                heapq.heappush(heap, (-float(first["robust_score"]), idx, first))

        ensure_dir(strong_csv.parent)
        with strong_csv.open("w", newline="", encoding="utf-8") as strong_f, base_csv.open("w", newline="", encoding="utf-8") as base_f:
            strong_writer = csv.DictWriter(strong_f, fieldnames=SEED_SCORE_FIELDNAMES, extrasaction="ignore")
            base_writer = csv.DictWriter(base_f, fieldnames=SEED_SCORE_FIELDNAMES, extrasaction="ignore")
            strong_writer.writeheader()
            base_writer.writeheader()
            written = 0
            while heap and written < strong_limit:
                _, shard_idx, row = heapq.heappop(heap)
                written += 1
                seed_score = {"robust_score": row["robust_score"], "candidate_seed": row["candidate_seed"]}
                strong_writer.writerow(seed_score)
                if written <= base_limit:
                    base_writer.writerow(seed_score)
                if written <= strong_deep_limit:
                    deep_rows.append(seed_score)
                nxt = next(readers[shard_idx], None)
                if nxt is not None:
                    heapq.heappush(heap, (-float(nxt["robust_score"]), shard_idx, nxt))
    finally:
        for handle in handles:
            handle.close()
    return deep_rows


def materialize_seed_rows(
    root: Path,
    seed_rows: list[dict[str, Any]],
    out_csv: Path,
    stage_name: str,
) -> list[dict[str, Any]]:
    os.environ["BWE_V6_DISABLE_TORCH_PATH"] = "1"
    ctx = SmokeContext(root, use_torch_path=False)
    space = build_candidate_space(ctx)
    component_cache: dict[tuple[str, int, int], tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    ret_cache: dict[tuple[Any, ...], np.ndarray] = {}
    mask_cache: dict[str, tuple[np.ndarray, str | None]] = {}
    rows: list[dict[str, Any]] = []
    ensure_dir(out_csv.parent)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        for idx, seed_row in enumerate(seed_rows, start=1):
            candidate_seed = int(seed_row["candidate_seed"])
            cand = candidate_from_seed(space, candidate_seed)
            mkey = mask_cache_key(cand)
            cached_mask = mask_cache.get(mkey)
            if cached_mask is None:
                cached_mask = candidate_mask(ctx, cand)
                if len(mask_cache) >= 50_000:
                    mask_cache.clear()
                mask_cache[mkey] = cached_mask
            mask, hint = cached_mask
            rkey = return_cache_key(cand)
            ret = ret_cache.get(rkey)
            if ret is None:
                ret = approximate_exit_returns(ctx, cand, component_cache)
                if len(ret_cache) >= 4096:
                    ret_cache.clear()
                ret_cache[rkey] = ret
            metrics = compute_metrics(ctx, cand, ret, mask, hint, stage="coarse", path_resolution=ctx.path_resolution)
            row = medium_heap_row(metrics)
            rows.append(row)
            writer.writerow(row)
            if idx % 25_000 == 0:
                print(f"{stage_name} materialized {idx}/{len(seed_rows)} top candidates", flush=True)
    return rows


def load_reject_samples(shared_dir: Path) -> pd.DataFrame:
    frames = []
    for path in sorted(shared_dir.glob("worker_*_reject_samples.csv")):
        try:
            df = pd.read_csv(path)
            if not df.empty:
                frames.append(df)
        except Exception:
            continue
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def combine_reject_counts(summaries: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for summary in summaries:
        counts.update(summary.get("reject_counts", {}))
    return counts


def write_reject_cluster_counts(run_dir: Path, reject_log: pd.DataFrame) -> None:
    if reject_log.empty:
        pd.DataFrame().to_csv(run_dir / "reject_cluster_counts.csv", index=False)
        return
    (
        reject_log.groupby(["reject_reason", "strategy_similarity_cluster_id"])
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
        .to_csv(run_dir / "reject_cluster_counts.csv", index=False)
    )


def finalize_profile(
    root: Path,
    run_dir: Path,
    stage_name: str,
    medium_csv: Path,
    top_rows: list[dict[str, Any]],
    deep_eval: int,
    stress_eval: int,
    portfolio_eval: int,
    candidate_space_sample: int,
    coarse_eval_actual: int,
    medium_eval_actual: int,
    baselines: pd.DataFrame,
    reject_log: pd.DataFrame,
    reject_counts: Counter[str],
    aggressive_notes: dict[str, Any],
) -> None:
    start = time.time()
    ctx = SmokeContext(root, use_torch_path=True)
    component_cache: dict[tuple[str, int, int], tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    baselines.to_csv(run_dir / "baseline_comparison.csv", index=False)
    write_jsonl(run_dir / "baseline_catalog.jsonl", baselines.to_dict(orient="records"))
    reject_log.to_csv(run_dir / "reject_log.csv", index=False)
    write_reject_cluster_counts(run_dir, reject_log)

    deep_rows = []
    deep_source = top_rows[:deep_eval]
    for idx, row in enumerate(deep_source, start=1):
        payload = json.loads(row["strategy_payload_json"])
        cand = candidate_from_payload(payload)
        mask, hint = candidate_mask(ctx, cand)
        ret = simulate_exit_gpu(ctx, cand)
        metrics = compute_metrics(ctx, cand, ret, mask, hint, stage="deep", path_resolution=ctx.path_resolution)
        if np.isfinite(ret[mask]).any():
            metrics["mfe_capture_ratio"], metrics["giveback_ratio"] = capture_giveback_estimates(ctx, cand, ret, mask, component_cache)
            metrics["portfolio_drawdown_pct"] = portfolio_drawdown(ctx, ret, mask, cand) * 100.0
        deep_rows.append(metrics)
        if idx % 1000 == 0:
            print(f"{stage_name} aggressive deep GPU replay {idx}/{len(deep_source)}", flush=True)

    leaderboard = pd.DataFrame(deep_rows).sort_values("robust_score", ascending=False).reset_index(drop=True)
    leaderboard.to_csv(run_dir / "complete_strategy_leaderboard.csv", index=False)
    write_execution_outputs(ctx, run_dir, leaderboard.head(stress_eval))
    write_similarity_outputs(run_dir, leaderboard)
    payload_by_id = {row["strategy_id"]: row["strategy_payload_json"] for row in top_rows}
    write_statistical_outputs(ctx, run_dir, leaderboard.head(500), payload_by_id)
    write_future_safety_report(run_dir, leaderboard)
    write_markdown_summaries(root, run_dir, leaderboard, baselines, reject_log, {
        "candidate_space_sample": candidate_space_sample,
        "coarse_eval": coarse_eval_actual,
        "medium_eval": medium_eval_actual,
        "deep_eval": deep_eval,
        "stress_eval": stress_eval,
        "portfolio_eval": portfolio_eval,
        "aggressive_runner": True,
        **aggressive_notes,
    }, ctx.device_info)
    append_research_ledger(root, run_dir, leaderboard, baselines, reject_log, {
        "candidate_space_sample": candidate_space_sample,
        "coarse_eval": coarse_eval_actual,
        "medium_eval": medium_eval_actual,
        "deep_eval": deep_eval,
        "stress_eval": stress_eval,
        "portfolio_eval": portfolio_eval,
        "aggressive_runner": True,
        **aggressive_notes,
    }, ctx.device_info)
    write_medium_gate_report(root, run_dir, leaderboard, baselines, reject_counts, {
        "candidate_space_sample": candidate_space_sample,
        "coarse_eval": coarse_eval_actual,
        "medium_eval": medium_eval_actual,
        "deep_eval": deep_eval,
        "stress_eval": stress_eval,
        "portfolio_eval": portfolio_eval,
        "aggressive_runner": True,
    }, ctx, stage_name=stage_name)
    summary = {
        "project": "bwe_complete_strategy_v6",
        "stage": stage_name,
        "created_at": utc_now_iso(),
        "run_dir": str(run_dir),
        "medium_eval_top_candidates_csv": str(medium_csv),
        "candidate_space_sample": candidate_space_sample,
        "coarse_eval_actual": coarse_eval_actual,
        "medium_eval_actual": medium_eval_actual,
        "deep_eval_actual": int(len(leaderboard)),
        "stress_eval_actual": int(min(len(leaderboard), stress_eval)),
        "portfolio_eval_budget_recorded": portfolio_eval,
        "path_resolution": ctx.path_resolution,
        "paper_only": True,
        "live_allowed": False,
        "gpu": ctx.device_info,
        "aggressive_runner": aggressive_notes,
        "elapsed_seconds_finalize": time.time() - start,
        "outputs": sorted(p.name for p in run_dir.iterdir()),
    }
    write_json(run_dir / "run_summary.json", summary)
    print(f"{stage_name} aggressive complete: {run_dir}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run combined aggressive BWE v6 max-alpha base/strong search")
    parser.add_argument("--root", default=None)
    parser.add_argument("--workers", type=int, default=max(1, min(16, (os.cpu_count() or 4) - 2)))
    parser.add_argument("--coarse-eval", type=int, default=100_000_000)
    parser.add_argument("--candidate-space-sample", type=int, default=500_000_000_000)
    parser.add_argument("--base-medium-eval", type=int, default=1_000_000)
    parser.add_argument("--strong-medium-eval", type=int, default=5_000_000)
    parser.add_argument("--base-deep-eval", type=int, default=50_000)
    parser.add_argument("--strong-deep-eval", type=int, default=200_000)
    parser.add_argument("--base-stress-eval", type=int, default=5_000)
    parser.add_argument("--strong-stress-eval", type=int, default=20_000)
    parser.add_argument("--base-portfolio-eval", type=int, default=500)
    parser.add_argument("--strong-portfolio-eval", type=int, default=2_000)
    parser.add_argument("--overcollect", type=float, default=1.06)
    parser.add_argument("--checkpoint-every", type=int, default=100_000)
    parser.add_argument("--ret-cache-max", type=int, default=2048)
    parser.add_argument("--mask-cache-max", type=int, default=50_000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = resolve_root(args.root)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    runs = ensure_dir(root / "runs")
    shared_dir = ensure_dir(runs / f"bwe_complete_strategy_v6_max_alpha_aggressive_combined_{timestamp}")
    base_dir = ensure_dir(runs / f"bwe_complete_strategy_v6_max_alpha_aggressive_base_{timestamp}")
    strong_dir = ensure_dir(runs / f"bwe_complete_strategy_v6_max_alpha_aggressive_strong_{timestamp}")
    worker_count = max(1, int(args.workers))
    worker_top_keep = int(math.ceil(args.strong_medium_eval / worker_count * float(args.overcollect)))
    counts = [args.coarse_eval // worker_count] * worker_count
    for i in range(args.coarse_eval % worker_count):
        counts[i] += 1
    plan = {
        "paper_only": True,
        "live_allowed": False,
        "runner": "aggressive_combined_base_and_strong",
        "root": str(root),
        "shared_dir": str(shared_dir),
        "base_dir": str(base_dir),
        "strong_dir": str(strong_dir),
        "workers": worker_count,
        "coarse_eval": args.coarse_eval,
        "candidate_space_sample": args.candidate_space_sample,
        "worker_top_keep": worker_top_keep,
        "base_medium_eval": args.base_medium_eval,
        "strong_medium_eval": args.strong_medium_eval,
        "base_deep_eval": args.base_deep_eval,
        "strong_deep_eval": args.strong_deep_eval,
        "optimization_notes": [
            "shared strong coarse pass is reused for base and strong outputs",
            "coarse evaluation is split across CPU workers",
            "CUDA remains reserved for deep replay and final validation",
            "strategy universe, candidate object schema, execution cost, dedup, statistical checks, and paper-only constraints are preserved",
        ],
    }
    write_json(shared_dir / "aggressive_run_plan.json", plan)
    write_json(runs / "max_alpha_aggressive_current_plan.json", plan)

    main_ctx = SmokeContext(root, use_torch_path=True)
    baselines = evaluate_baselines(main_ctx, {})
    baselines.to_csv(shared_dir / "baseline_comparison.csv", index=False)
    write_jsonl(shared_dir / "baseline_catalog.jsonl", baselines.to_dict(orient="records"))

    start = time.time()
    summaries: list[dict[str, Any]] = []
    print(f"aggressive combined coarse started: workers={worker_count} top_keep/worker={worker_top_keep}", flush=True)
    with ProcessPoolExecutor(max_workers=worker_count) as pool:
        futures = []
        seed_stride = max(counts) + 10_000_019
        for worker_id, count in enumerate(counts):
            seed = 915_090 + worker_id * seed_stride
            futures.append(
                pool.submit(
                    worker_coarse,
                    str(root),
                    str(shared_dir),
                    worker_id,
                    count,
                    seed,
                    worker_top_keep,
                    int(args.checkpoint_every),
                    int(args.ret_cache_max),
                    int(args.mask_cache_max),
                )
            )
        for future in as_completed(futures):
            summary = future.result()
            summaries.append(summary)
            print(
                f"worker {summary['worker_id']} done evaluated={summary['evaluated']} top={summary['top_rows']} elapsed={summary['elapsed_seconds']:.1f}s",
                flush=True,
            )

    write_json(shared_dir / "worker_summaries.json", summaries)
    shard_paths = [Path(s["shard_path"]) for s in summaries]
    base_seed_csv = base_dir / "max_alpha_aggressive_base_eval_top_seed_scores.csv"
    strong_seed_csv = strong_dir / "max_alpha_aggressive_strong_eval_top_seed_scores.csv"
    base_medium_csv = base_dir / "max_alpha_aggressive_base_eval_top_candidates.csv"
    strong_medium_csv = strong_dir / "max_alpha_aggressive_strong_eval_top_candidates.csv"
    print("merging aggressive top shards", flush=True)
    strong_seed_rows = merge_sorted_shards(
        sorted(shard_paths),
        int(args.strong_medium_eval),
        int(args.base_medium_eval),
        strong_seed_csv,
        base_seed_csv,
        int(args.strong_deep_eval),
    )
    print("materializing aggressive base/strong deep candidate pools", flush=True)
    base_materialized_rows = materialize_seed_rows(
        root,
        strong_seed_rows[: int(args.base_deep_eval)],
        base_medium_csv,
        "max_alpha_aggressive_base",
    )
    strong_materialized_rows = materialize_seed_rows(
        root,
        strong_seed_rows,
        strong_medium_csv,
        "max_alpha_aggressive_strong",
    )
    write_json(
        shared_dir / "coarse_merge_summary.json",
        {
            "elapsed_seconds_coarse_and_merge": time.time() - start,
            "worker_summaries": summaries,
            "strong_seed_rows_for_deep": len(strong_seed_rows),
            "base_seed_scores_csv": str(base_seed_csv),
            "strong_seed_scores_csv": str(strong_seed_csv),
            "base_medium_csv": str(base_medium_csv),
            "strong_medium_csv": str(strong_medium_csv),
        },
    )

    reject_log = load_reject_samples(shared_dir)
    reject_counts = combine_reject_counts(summaries)
    notes = {
        "shared_aggressive_dir": str(shared_dir),
        "workers": worker_count,
        "worker_top_keep": worker_top_keep,
        "overcollect": args.overcollect,
        "base_full_top_pool_seed_scores": str(base_seed_csv),
        "strong_full_top_pool_seed_scores": str(strong_seed_csv),
        "materialized_candidate_rows_policy": "full candidate rows are materialized for the deep replay pool; full medium pools are retained as seed-score ledgers to avoid IO/memory dominating the search",
        "coarse_elapsed_seconds_before_finalize": time.time() - start,
    }
    finalize_profile(
        root,
        base_dir,
        "max_alpha_aggressive_base",
        base_medium_csv,
        base_materialized_rows,
        int(args.base_deep_eval),
        int(args.base_stress_eval),
        int(args.base_portfolio_eval),
        int(args.candidate_space_sample),
        int(args.coarse_eval),
        int(args.base_medium_eval),
        baselines,
        reject_log,
        reject_counts,
        notes,
    )
    finalize_profile(
        root,
        strong_dir,
        "max_alpha_aggressive_strong",
        strong_medium_csv,
        strong_materialized_rows,
        int(args.strong_deep_eval),
        int(args.strong_stress_eval),
        int(args.strong_portfolio_eval),
        int(args.candidate_space_sample),
        int(args.coarse_eval),
        int(args.strong_medium_eval),
        baselines,
        reject_log,
        reject_counts,
        notes,
    )
    write_json(
        shared_dir / "aggressive_combined_done.json",
        {
            "base_dir": str(base_dir),
            "strong_dir": str(strong_dir),
            "elapsed_seconds_total": time.time() - start,
            "paper_only": True,
            "live_allowed": False,
        },
    )


if __name__ == "__main__":
    main()
