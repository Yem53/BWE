"""GPU-fused max-alpha runner for BWE v6 paper research.

This runner accelerates the coarse stage only. Promotion and final leaderboard
rows are recomputed with the canonical v6 Candidate, simulate_exit_gpu, and
compute_metrics functions so the paper-only validation surface stays aligned
with the original runner.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import torch

from bwe_autoresearch.v6_complete_strategy import (
    ENTRY_DELAYS_SECONDS,
    EXIT_FAMILIES,
    HORIZONS_MINUTES,
    SIDES,
    Candidate,
    SmokeContext,
    append_research_ledger,
    approximate_exit_returns,
    candidate_mask,
    capture_giveback_estimates,
    clean_json,
    compute_metrics,
    ensure_dir,
    evaluate_baselines,
    numeric_quantiles,
    path_return_components,
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
HASH_A = 6364136223846793005
HASH_B = 1442695040888963407
HASH_SALT_STEP = 1000003
MASK64 = (1 << 64) - 1
MAX_CONDITIONS = 6
QUANTILE_LEVELS = [0.2, 0.35, 0.5, 0.65, 0.8]
TP_GRID = [0.004, 0.006, 0.008, 0.01, 0.015, 0.02, 0.03, 0.05, 0.08]
SL_GRID = [0.004, 0.006, 0.008, 0.01, 0.015, 0.02, 0.03, 0.05]
TRAIL_GRID = [0.003, 0.005, 0.008, 0.012, 0.02, 0.03]
BE_GRID = [0.004, 0.006, 0.01, 0.015, 0.02, 0.03]
NUMERIC_FIELDS = [
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
]


@dataclass
class FusedSpace:
    channels: list[str]
    event_types: list[str]
    strategy_families: list[str]
    numeric_fields: list[str]
    thresholds: dict[str, dict[float, float]]


@dataclass
class FusedState:
    space: FusedSpace
    device: str
    n: int
    channel_codes: torch.Tensor
    event_type_codes: torch.Tensor
    tradable: torch.Tensor
    feature_tensor: torch.Tensor
    threshold_tensor: torch.Tensor
    liquidity_codes: torch.Tensor
    mark_age: torch.Tensor
    taker: torch.Tensor
    final_components: torch.Tensor
    mfe_components: torch.Tensor
    mae_components: torch.Tensor
    symbol_onehot: torch.Tensor
    time_order: torch.Tensor
    base_cost: float
    stress_extra: float
    path_resolution: str


def signed64_from_uint(value: int) -> int:
    value &= MASK64
    return value - (1 << 64) if value >= (1 << 63) else value


def hash_abs(seed: int, salt: int) -> int:
    value = ((int(seed) + salt * HASH_SALT_STEP) & MASK64)
    value = (value * HASH_A + HASH_B) & MASK64
    signed = signed64_from_uint(value)
    return abs(signed)


def choice(seed: int, salt: int, modulo: int) -> int:
    return int(hash_abs(seed, salt) % modulo)


def hash_mod(seeds: torch.Tensor, salt: int, modulo: int) -> torch.Tensor:
    mixed = (seeds + int(salt * HASH_SALT_STEP)) * HASH_A + HASH_B
    return torch.remainder(torch.abs(mixed), int(modulo)).to(torch.long)


def build_space(ctx: SmokeContext) -> FusedSpace:
    thresholds: dict[str, dict[float, float]] = {}
    for field in NUMERIC_FIELDS:
        if field in ctx.features:
            thresholds[field] = numeric_quantiles(ctx.features[field], QUANTILE_LEVELS)
    return FusedSpace(
        channels=sorted(set(ctx.features["channel"])),
        event_types=sorted(set(ctx.features["event_type"])),
        strategy_families=[
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
        numeric_fields=list(thresholds),
        thresholds=thresholds,
    )


def candidate_from_fused_seed(space: FusedSpace, seed: int) -> Candidate:
    channel_options = space.channels + ["ANY", "ANY"]
    event_options = space.event_types + ["ANY"]
    side_roll = choice(seed, 3, 100)
    side = "long" if side_roll < 45 else ("short" if side_roll < 90 else "no_trade")
    cond_depth = choice(seed, 12, MAX_CONDITIONS + 1)
    conds: list[dict[str, Any]] = []
    for slot in range(cond_depth):
        field = space.numeric_fields[choice(seed, 20 + slot * 3, len(space.numeric_fields))]
        op = ">=" if choice(seed, 21 + slot * 3, 2) == 0 else "<="
        q_idx = choice(seed, 22 + slot * 3, len(QUANTILE_LEVELS))
        q = QUANTILE_LEVELS[q_idx]
        conds.append({"field": field, "op": op, "threshold": space.thresholds[field][q], "source": "entry_time_features"})
    if choice(seed, 60, 100) < 35:
        bucket = ["high", "mid", "low", "nan"][choice(seed, 61, 4)]
        conds.append({"field": "liquidity_bucket", "op": "in", "values": [bucket], "source": "entry_time_features"})
    if choice(seed, 62, 100) < 45:
        age_limit = [5 * 60000, 10 * 60000][choice(seed, 63, 2)]
        conds.append({"field": "mark_1m_age_ms", "op": "<=", "threshold": age_limit, "source": "entry_time_features"})
    sl = SL_GRID[choice(seed, 8, len(SL_GRID))]
    portfolio_rule = {
        "shape": ["cooldown30_max3", "cooldown60_max5", "cooldown120_max8"][choice(seed, 70, 3)],
        "one_position_per_symbol": True,
        "same_symbol_cooldown_minutes": [30, 60, 120][choice(seed, 71, 3)],
        "max_concurrent_positions": [3, 5, 8][choice(seed, 72, 3)],
    }
    risk_rule = {
        "shape": ["balanced", "left_tail_strict", "stress_strict"][choice(seed, 73, 3)],
        "initial_stop_pct": sl,
        "position_sizing": "unit_notional_paper",
        "fee_model_id": "base_taker",
        "slippage_model_id": "liquidity_aware",
        "latency_model_id": "base_1s",
    }
    return Candidate(
        strategy_family=space.strategy_families[choice(seed, 0, len(space.strategy_families))],
        channel=channel_options[choice(seed, 1, len(channel_options))],
        event_type=event_options[choice(seed, 2, len(event_options))],
        side=side,
        entry_delay_s=ENTRY_DELAYS_SECONDS[choice(seed, 4, len(ENTRY_DELAYS_SECONDS))],
        horizon_min=HORIZONS_MINUTES[choice(seed, 5, len(HORIZONS_MINUTES))],
        exit_family=EXIT_FAMILIES[choice(seed, 6, len(EXIT_FAMILIES))],
        tp_pct=TP_GRID[choice(seed, 7, len(TP_GRID))],
        sl_pct=sl,
        trail_pct=TRAIL_GRID[choice(seed, 9, len(TRAIL_GRID))],
        be_trigger_pct=BE_GRID[choice(seed, 10, len(BE_GRID))],
        conditions=conds,
        portfolio_rule=portfolio_rule,
        risk_rule=risk_rule,
        seed=int(seed),
    )


def build_state(ctx: SmokeContext, device: str) -> FusedState:
    space = build_space(ctx)
    channel_map = {v: i for i, v in enumerate(space.channels)}
    event_map = {v: i for i, v in enumerate(space.event_types)}
    channel_codes = torch.tensor([channel_map[str(x)] for x in ctx.features["channel"]], dtype=torch.long, device=device)
    event_type_codes = torch.tensor([event_map[str(x)] for x in ctx.features["event_type"]], dtype=torch.long, device=device)
    tradable = torch.tensor(ctx.features["is_tradable_at_event"], dtype=torch.bool, device=device)
    feature_tensor = torch.tensor(np.stack([ctx.features[f].astype(np.float32) for f in space.numeric_fields]), dtype=torch.float32, device=device)
    threshold_tensor = torch.tensor(
        [[space.thresholds[f][q] for q in QUANTILE_LEVELS] for f in space.numeric_fields],
        dtype=torch.float32,
        device=device,
    )
    liquidity_map = {"high": 0, "mid": 1, "low": 2, "nan": 3}
    liquidity = torch.tensor([liquidity_map.get(str(x), 3) for x in ctx.features["liquidity_bucket"]], dtype=torch.long, device=device)
    mark_age = torch.tensor(ctx.features.get("mark_1m_age_ms", np.full(ctx.n, np.nan, dtype=np.float32)), dtype=torch.float32, device=device)
    taker = torch.tensor(ctx.features.get("taker_buy_sell_volume__buySellRatio", np.full(ctx.n, np.nan, dtype=np.float32)), dtype=torch.float32, device=device)

    final_rows = []
    mfe_rows = []
    mae_rows = []
    for side in ["long", "short"]:
        for delay in ENTRY_DELAYS_SECONDS:
            for horizon in HORIZONS_MINUTES:
                final, mfe, mae = path_return_components(ctx, side, delay, horizon)
                final_rows.append(final)
                mfe_rows.append(mfe)
                mae_rows.append(mae)
    final_components = torch.tensor(np.stack(final_rows), dtype=torch.float32, device=device)
    mfe_components = torch.tensor(np.stack(mfe_rows), dtype=torch.float32, device=device)
    mae_components = torch.tensor(np.stack(mae_rows), dtype=torch.float32, device=device)

    symbols = pd.Series(ctx.features["api_symbol"].astype(str))
    symbol_codes = torch.tensor(pd.Categorical(symbols).codes.astype(np.int64), dtype=torch.long, device=device)
    symbol_onehot = torch.nn.functional.one_hot(symbol_codes, num_classes=int(symbol_codes.max().item()) + 1).to(torch.float32)
    order = torch.tensor(np.argsort(ctx.features["ts_ms"]), dtype=torch.long, device=device)
    base_cost = (2 * 4.0 + 2 * (5.0 + 2.0) + 0.6 * math.log1p(1)) / 10000.0
    stress_cost = (2 * 6.0 + 2 * (16.0 + 2.0) + 1.8 * math.log1p(1)) / 10000.0
    return FusedState(
        space=space,
        device=device,
        n=ctx.n,
        channel_codes=channel_codes,
        event_type_codes=event_type_codes,
        tradable=tradable,
        feature_tensor=feature_tensor,
        threshold_tensor=threshold_tensor,
        liquidity_codes=liquidity,
        mark_age=mark_age,
        taker=taker,
        final_components=final_components,
        mfe_components=mfe_components,
        mae_components=mae_components,
        symbol_onehot=symbol_onehot,
        time_order=order,
        base_cost=base_cost,
        stress_extra=stress_cost - base_cost,
        path_resolution=ctx.path_resolution,
    )


def masked_quantile(values: torch.Tensor, valid: torch.Tensor, q: float) -> torch.Tensor:
    inf = torch.tensor(float("inf"), dtype=values.dtype, device=values.device)
    masked = torch.where(valid, values, inf)
    sorted_vals = torch.sort(masked, dim=1).values
    counts = valid.sum(dim=1)
    pos = (counts.to(torch.float32) - 1.0) * float(q)
    lo = torch.floor(pos).to(torch.long).clamp(min=0, max=values.shape[1] - 1)
    hi = torch.ceil(pos).to(torch.long).clamp(min=0, max=values.shape[1] - 1)
    weight = (pos - lo.to(torch.float32)).clamp(min=0.0, max=1.0)
    lo_v = sorted_vals.gather(1, lo.view(-1, 1)).squeeze(1)
    hi_v = sorted_vals.gather(1, hi.view(-1, 1)).squeeze(1)
    out = lo_v * (1.0 - weight) + hi_v * weight
    return torch.where(counts > 0, out, torch.zeros_like(out))


def decode_indices(state: FusedState, seeds: torch.Tensor) -> dict[str, torch.Tensor]:
    side_roll = hash_mod(seeds, 3, 100)
    side_idx = torch.where(side_roll < 45, torch.zeros_like(side_roll), torch.where(side_roll < 90, torch.ones_like(side_roll), torch.full_like(side_roll, 2)))
    return {
        "family_idx": hash_mod(seeds, 0, len(state.space.strategy_families)),
        "channel_idx": hash_mod(seeds, 1, len(state.space.channels) + 2),
        "event_idx": hash_mod(seeds, 2, len(state.space.event_types) + 1),
        "side_idx": side_idx,
        "delay_idx": hash_mod(seeds, 4, len(ENTRY_DELAYS_SECONDS)),
        "horizon_idx": hash_mod(seeds, 5, len(HORIZONS_MINUTES)),
        "exit_idx": hash_mod(seeds, 6, len(EXIT_FAMILIES)),
        "tp_idx": hash_mod(seeds, 7, len(TP_GRID)),
        "sl_idx": hash_mod(seeds, 8, len(SL_GRID)),
        "trail_idx": hash_mod(seeds, 9, len(TRAIL_GRID)),
        "be_idx": hash_mod(seeds, 10, len(BE_GRID)),
        "cond_depth": hash_mod(seeds, 12, MAX_CONDITIONS + 1),
        "liq_active": hash_mod(seeds, 60, 100) < 35,
        "liq_bucket": hash_mod(seeds, 61, 4),
        "age_active": hash_mod(seeds, 62, 100) < 45,
        "age_limit_idx": hash_mod(seeds, 63, 2),
    }


def fused_batch_scores(state: FusedState, seeds: torch.Tensor, details: bool = False) -> dict[str, torch.Tensor]:
    idx = decode_indices(state, seeds)
    batch = seeds.shape[0]
    mask = state.tradable.view(1, -1).expand(batch, state.n).clone()
    channel_any = idx["channel_idx"] >= len(state.space.channels)
    channel_match = state.channel_codes.view(1, -1) == idx["channel_idx"].view(-1, 1)
    mask &= channel_any.view(-1, 1) | channel_match
    event_any = idx["event_idx"] >= len(state.space.event_types)
    event_match = state.event_type_codes.view(1, -1) == idx["event_idx"].view(-1, 1)
    mask &= event_any.view(-1, 1) | event_match

    for slot in range(MAX_CONDITIONS):
        active = idx["cond_depth"] > slot
        field_idx = hash_mod(seeds, 20 + slot * 3, len(state.space.numeric_fields))
        op_idx = hash_mod(seeds, 21 + slot * 3, 2)
        q_idx = hash_mod(seeds, 22 + slot * 3, len(QUANTILE_LEVELS))
        vals = state.feature_tensor[field_idx]
        thresholds = state.threshold_tensor[field_idx, q_idx].view(-1, 1)
        finite = torch.isfinite(vals)
        cond = torch.where(op_idx.view(-1, 1) == 0, vals >= thresholds, vals <= thresholds)
        mask &= (~active).view(-1, 1) | (finite & cond)

    liq_cond = state.liquidity_codes.view(1, -1) == idx["liq_bucket"].view(-1, 1)
    mask &= (~idx["liq_active"]).view(-1, 1) | liq_cond
    age_limit = torch.where(idx["age_limit_idx"] == 0, torch.full_like(idx["age_limit_idx"], 5 * 60000), torch.full_like(idx["age_limit_idx"], 10 * 60000)).to(torch.float32)
    age_cond = torch.isfinite(state.mark_age).view(1, -1) & (state.mark_age.view(1, -1) <= age_limit.view(-1, 1))
    mask &= (~idx["age_active"]).view(-1, 1) | age_cond

    side_for_path = torch.minimum(idx["side_idx"], torch.ones_like(idx["side_idx"]))
    combo_idx = side_for_path * (len(ENTRY_DELAYS_SECONDS) * len(HORIZONS_MINUTES)) + idx["delay_idx"] * len(HORIZONS_MINUTES) + idx["horizon_idx"]
    final = state.final_components[combo_idx]
    mfe = state.mfe_components[combo_idx]
    mae = state.mae_components[combo_idx]
    tp = torch.tensor(TP_GRID, dtype=torch.float32, device=state.device)[idx["tp_idx"]].view(-1, 1)
    sl = torch.tensor(SL_GRID, dtype=torch.float32, device=state.device)[idx["sl_idx"]].view(-1, 1)
    trail = torch.tensor(TRAIL_GRID, dtype=torch.float32, device=state.device)[idx["trail_idx"]].view(-1, 1)
    be = torch.tensor(BE_GRID, dtype=torch.float32, device=state.device)[idx["be_idx"]].view(-1, 1)
    exit_idx = idx["exit_idx"].view(-1, 1)
    ret = final
    ret = torch.where(exit_idx == 0, torch.where(mae <= -sl, -sl, torch.where(mfe >= tp, tp, final)), ret)
    ret = torch.where(exit_idx == 1, torch.where(mae <= -sl, -sl, torch.where(mfe >= tp * 2.0, 1.5 * tp, torch.where(mfe >= tp, 0.5 * tp + 0.5 * final, final))), ret)
    ret = torch.where(exit_idx == 2, torch.where(mae <= -sl, -sl, torch.where(mfe >= tp * 1.6, 0.35 * tp + 0.35 * tp * 1.6 + 0.30 * final, torch.where(mfe >= tp, 0.5 * tp + 0.5 * final, final))), ret)
    ret = torch.where(exit_idx == 3, torch.where(mae <= -sl, -sl, torch.maximum(final, mfe - trail)), ret)
    ret = torch.where(exit_idx == 4, torch.where(mae <= -sl, -sl, torch.where(mfe >= tp, 0.4 * tp + 0.6 * torch.maximum(final, mfe - trail), final)), ret)
    ret = torch.where(exit_idx == 5, torch.where(mae <= -sl, -sl, torch.where((mfe >= be) & (final < 0), torch.zeros_like(final), final)), ret)
    ret = torch.where(exit_idx == 6, torch.where(mae <= -sl * 0.8, -sl * 0.8, final * 0.85), ret)

    combo_5 = side_for_path * (len(ENTRY_DELAYS_SECONDS) * len(HORIZONS_MINUTES)) + idx["delay_idx"] * len(HORIZONS_MINUTES)
    prove = state.final_components[combo_5]
    ret = torch.where(exit_idx == 7, torch.where(prove < 0, prove - 0.0004, torch.where(mae <= -sl, -sl, torch.maximum(final, mfe - trail))), ret)
    h10 = torch.where(idx["horizon_idx"] == 0, torch.zeros_like(idx["horizon_idx"]), torch.ones_like(idx["horizon_idx"]))
    combo_10 = side_for_path * (len(ENTRY_DELAYS_SECONDS) * len(HORIZONS_MINUTES)) + idx["delay_idx"] * len(HORIZONS_MINUTES) + h10
    early = state.final_components[combo_10]
    ret = torch.where(exit_idx == 8, torch.where(early < -sl * 0.35, early, torch.where(mae <= -sl, -sl, final)), ret)
    adverse = ((idx["side_idx"].view(-1, 1) == 0) & torch.isfinite(state.taker).view(1, -1) & (state.taker.view(1, -1) < 0.9)) | (
        (idx["side_idx"].view(-1, 1) == 1) & torch.isfinite(state.taker).view(1, -1) & (state.taker.view(1, -1) > 1.1)
    )
    ret = torch.where(exit_idx == 9, torch.where(adverse, torch.minimum(final, torch.zeros_like(final)) - 0.0005, torch.where(mae <= -sl, -sl, final)), ret)
    ret = torch.where(exit_idx == 10, torch.where(mae <= -sl, -sl, torch.where(mfe >= tp, 0.35 * tp + 0.65 * torch.maximum(final, mfe - trail), torch.where(final < -sl * 0.5, final, final * 0.9))), ret)
    trade_side = idx["side_idx"] != 2
    ret = torch.where(trade_side.view(-1, 1), ret - state.base_cost, torch.zeros_like(ret))

    valid = mask & torch.isfinite(ret)
    count = valid.sum(dim=1)
    median = masked_quantile(ret, valid, 0.5)
    p25 = masked_quantile(ret, valid, 0.25)
    p10 = masked_quantile(ret, valid, 0.10)
    pos = torch.where(valid & (ret > 0), ret, torch.zeros_like(ret)).sum(dim=1)
    neg = torch.where(valid & (ret < 0), -ret, torch.zeros_like(ret)).sum(dim=1)
    pf = torch.where(neg > 0, pos / neg, torch.where(pos > 0, torch.full_like(pos, 99.0), torch.zeros_like(pos)))
    stress_median = torch.where(count > 0, median - state.stress_extra, torch.zeros_like(median))
    symbol_counts = valid.to(torch.float32) @ state.symbol_onehot
    top_symbol_share = torch.where(count > 0, symbol_counts.max(dim=1).values / count.to(torch.float32), torch.zeros_like(median))

    valid_time = valid[:, state.time_order]
    ret_time = ret[:, state.time_order]
    ranks = torch.cumsum(valid_time.to(torch.long), dim=1) - 1
    q = torch.div(count, 5, rounding_mode="floor")
    r = torch.remainder(count, 5)
    positive_chunks = torch.zeros(batch, dtype=torch.float32, device=state.device)
    for window in range(5):
        start = window * q + torch.minimum(r, torch.full_like(r, window))
        length = q + (r > window).to(torch.long)
        end = start + length
        chunk_mask = valid_time & (ranks >= start.view(-1, 1)) & (ranks < end.view(-1, 1)) & (length > 0).view(-1, 1)
        chunk_median = masked_quantile(ret_time, chunk_mask, 0.5)
        positive_chunks += ((chunk_median > 0) & (length > 0)).to(torch.float32)
    wf = torch.where(count >= 25, positive_chunks / 5.0, torch.zeros_like(positive_chunks))

    total_conditions = idx["cond_depth"] + idx["liq_active"].to(torch.long) + idx["age_active"].to(torch.long)
    complexity = (total_conditions.to(torch.float32) * 0.03 + torch.where(idx["exit_idx"] == 10, torch.full_like(median, 0.10), torch.full_like(median, 0.04))) / 100.0
    robust = median * 0.35 + p25 * 0.20 + p10 * 0.10 + torch.minimum(pf, torch.full_like(pf, 5.0)) * 0.0005 + wf * 0.0008
    robust = robust - complexity - torch.clamp(top_symbol_share - 0.35, min=0.0) * 0.002
    initial_reject = (idx["side_idx"] == 2) | (count < 20)
    robust = torch.where(initial_reject, robust - 10.0, robust)

    reject = (idx["side_idx"] != 2) & ((count < 20) | (median <= 0) | (stress_median <= 0) | (pf < 1.2))
    if not details:
        return {"robust_score": robust, "candidate_seed": seeds, "reject": reject}
    return {
        "robust_score": robust,
        "candidate_seed": seeds,
        "reject": reject,
        "sample_size": count,
        "median": median,
        "p25": p25,
        "p10": p10,
        "profit_factor": pf,
        "stress_median": stress_median,
        "top_symbol_share": top_symbol_share,
        "walk_forward": wf,
    }


def append_and_prune(
    top_scores: np.ndarray,
    top_seeds: np.ndarray,
    new_scores: np.ndarray,
    new_seeds: np.ndarray,
    limit: int,
    prune_margin: int,
) -> tuple[np.ndarray, np.ndarray]:
    if top_scores.size == 0:
        scores = new_scores.astype(np.float32, copy=False)
        seeds = new_seeds.astype(np.int64, copy=False)
    else:
        scores = np.concatenate([top_scores, new_scores.astype(np.float32, copy=False)])
        seeds = np.concatenate([top_seeds, new_seeds.astype(np.int64, copy=False)])
    if scores.size > limit + prune_margin:
        idx = np.argpartition(scores, -limit)[-limit:]
        scores = scores[idx]
        seeds = seeds[idx]
    return scores, seeds


def write_seed_scores(path: Path, scores: np.ndarray, seeds: np.ndarray, limit: int) -> tuple[np.ndarray, np.ndarray]:
    order = np.argsort(scores)[::-1][:limit]
    sorted_scores = scores[order]
    sorted_seeds = seeds[order]
    ensure_dir(path.parent)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SEED_SCORE_FIELDNAMES)
        writer.writeheader()
        for score, seed in zip(sorted_scores, sorted_seeds):
            writer.writerow({"robust_score": float(score), "candidate_seed": int(seed)})
    return sorted_scores, sorted_seeds


def materialize_rows(root: Path, space: FusedSpace, seeds: np.ndarray, out_csv: Path, stage_name: str) -> list[dict[str, Any]]:
    os.environ["BWE_V6_DISABLE_TORCH_PATH"] = "1"
    ctx = SmokeContext(root, use_torch_path=False)
    component_cache: dict[tuple[str, int, int], tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    rows: list[dict[str, Any]] = []
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        for idx, seed in enumerate(seeds, start=1):
            cand = candidate_from_fused_seed(space, int(seed))
            mask, hint = candidate_mask(ctx, cand)
            ret = approximate_exit_returns(ctx, cand, component_cache)
            metrics = compute_metrics(ctx, cand, ret, mask, hint, stage="coarse", path_resolution=ctx.path_resolution)
            row = {k: metrics.get(k) for k in FIELDNAMES}
            rows.append(row)
            writer.writerow(row)
            if idx % 25000 == 0:
                print(f"{stage_name} materialized {idx}/{len(seeds)} candidates", flush=True)
    return rows


def materialize_rejects(root: Path, space: FusedSpace, seeds: list[int], limit: int) -> pd.DataFrame:
    if not seeds:
        return pd.DataFrame()
    ctx = SmokeContext(root, use_torch_path=False)
    component_cache: dict[tuple[str, int, int], tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    rows = []
    for seed in seeds[:limit]:
        cand = candidate_from_fused_seed(space, int(seed))
        mask, hint = candidate_mask(ctx, cand)
        ret = approximate_exit_returns(ctx, cand, component_cache)
        metrics = compute_metrics(ctx, cand, ret, mask, hint, stage="coarse", path_resolution=ctx.path_resolution)
        if metrics.get("decision") == "reject":
            rows.append(
                {
                    "strategy_id": metrics["strategy_id"],
                    "strategy_family": metrics["strategy_family"],
                    "side": metrics["side"],
                    "entry_timing": metrics["entry_timing"],
                    "exit_family": metrics["exit_family"],
                    "sample_size": metrics["sample_size"],
                    "reject_reason": metrics.get("reject_reason") or "unknown",
                    "strategy_similarity_cluster_id": metrics["strategy_similarity_cluster_id"],
                    "robust_score": metrics["robust_score"],
                }
            )
    return pd.DataFrame(rows)


def finalize_profile(
    root: Path,
    run_dir: Path,
    stage_name: str,
    medium_csv: Path,
    top_rows: list[dict[str, Any]],
    candidate_space_sample: int,
    coarse_eval_actual: int,
    medium_eval_actual: int,
    deep_eval: int,
    stress_eval: int,
    portfolio_eval: int,
    baselines: pd.DataFrame,
    reject_log: pd.DataFrame,
    reject_counts: Counter[str],
    notes: dict[str, Any],
) -> None:
    start = time.time()
    ctx = SmokeContext(root, use_torch_path=True)
    component_cache: dict[tuple[str, int, int], tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    baselines.to_csv(run_dir / "baseline_comparison.csv", index=False)
    write_jsonl(run_dir / "baseline_catalog.jsonl", baselines.to_dict(orient="records"))
    reject_log.to_csv(run_dir / "reject_log.csv", index=False)
    if reject_log.empty:
        pd.DataFrame().to_csv(run_dir / "reject_cluster_counts.csv", index=False)
    else:
        (
            reject_log.groupby(["reject_reason", "strategy_similarity_cluster_id"])
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
            .to_csv(run_dir / "reject_cluster_counts.csv", index=False)
        )
    deep_rows = []
    for idx, row in enumerate(top_rows[:deep_eval], start=1):
        payload = json.loads(row["strategy_payload_json"])
        cand = Candidate(
            strategy_family=payload["strategy_family"],
            channel=payload["channel"],
            event_type=payload["event_type"],
            side=payload["side"],
            entry_delay_s={"T0": 0, "30s": 30, "1m": 60, "3m": 180, "5m": 300}[payload["entry_timing"]],
            horizon_min=int(payload["exit_state_machine"]["max_hold_min"]),
            exit_family=payload["exit_family"],
            tp_pct=float(payload["exit_state_machine"]["tp_pct"]),
            sl_pct=float(payload["exit_state_machine"]["sl_pct"]),
            trail_pct=float(payload["exit_state_machine"]["trail_pct"]),
            be_trigger_pct=float(payload["exit_state_machine"]["breakeven_trigger_pct"]),
            conditions=list(payload["entry_conditions"]),
            portfolio_rule=dict(payload["portfolio_rule"]),
            risk_rule=dict(payload["risk_rule"]),
            seed=int(payload["seed"]),
        )
        mask, hint = candidate_mask(ctx, cand)
        ret = simulate_exit_gpu(ctx, cand)
        metrics = compute_metrics(ctx, cand, ret, mask, hint, stage="deep", path_resolution=ctx.path_resolution)
        if np.isfinite(ret[mask]).any():
            metrics["mfe_capture_ratio"], metrics["giveback_ratio"] = capture_giveback_estimates(ctx, cand, ret, mask, component_cache)
            metrics["portfolio_drawdown_pct"] = portfolio_drawdown(ctx, ret, mask, cand) * 100.0
        deep_rows.append(metrics)
        if idx % 1000 == 0:
            print(f"{stage_name} fused deep replay {idx}/{min(deep_eval, len(top_rows))}", flush=True)
    leaderboard = pd.DataFrame(deep_rows).sort_values("robust_score", ascending=False).reset_index(drop=True)
    leaderboard.to_csv(run_dir / "complete_strategy_leaderboard.csv", index=False)
    write_execution_outputs(ctx, run_dir, leaderboard.head(stress_eval))
    write_similarity_outputs(run_dir, leaderboard)
    payload_by_id = {row["strategy_id"]: row["strategy_payload_json"] for row in top_rows}
    write_statistical_outputs(ctx, run_dir, leaderboard.head(500), payload_by_id)
    write_future_safety_report(run_dir, leaderboard)
    budget = {
        "candidate_space_sample": candidate_space_sample,
        "coarse_eval": coarse_eval_actual,
        "medium_eval": medium_eval_actual,
        "deep_eval": deep_eval,
        "stress_eval": stress_eval,
        "portfolio_eval": portfolio_eval,
        "gpu_fused_runner": True,
        **notes,
    }
    write_markdown_summaries(root, run_dir, leaderboard, baselines, reject_log, budget, ctx.device_info)
    append_research_ledger(root, run_dir, leaderboard, baselines, reject_log, budget, ctx.device_info)
    write_medium_gate_report(root, run_dir, leaderboard, baselines, reject_counts, budget, ctx, stage_name=stage_name)
    write_json(
        run_dir / "run_summary.json",
        {
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
            "gpu_fused_runner": notes,
            "elapsed_seconds_finalize": time.time() - start,
            "outputs": sorted(p.name for p in run_dir.iterdir()),
        },
    )
    print(f"{stage_name} gpu fused complete: {run_dir}", flush=True)


def run_parity(root: Path, batch_size: int, seed_offset: int, out_dir: Path) -> dict[str, Any]:
    ctx = SmokeContext(root, use_torch_path=False)
    state = build_state(ctx, "cuda")
    seeds = torch.arange(seed_offset, seed_offset + batch_size, dtype=torch.long, device="cuda")
    gpu = fused_batch_scores(state, seeds, details=True)
    gpu_scores = gpu["robust_score"].detach().cpu().numpy()
    cpu_scores = []
    component_cache: dict[tuple[str, int, int], tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    for seed in range(seed_offset, seed_offset + batch_size):
        cand = candidate_from_fused_seed(state.space, seed)
        mask, hint = candidate_mask(ctx, cand)
        ret = approximate_exit_returns(ctx, cand, component_cache)
        metrics = compute_metrics(ctx, cand, ret, mask, hint, stage="coarse", path_resolution=ctx.path_resolution)
        cpu_scores.append(float(metrics["robust_score"]))
    cpu_scores_arr = np.array(cpu_scores, dtype=np.float64)
    diff = np.abs(cpu_scores_arr - gpu_scores.astype(np.float64))
    report = {
        "checked": batch_size,
        "max_abs_robust_score_diff": float(diff.max()) if diff.size else 0.0,
        "mean_abs_robust_score_diff": float(diff.mean()) if diff.size else 0.0,
        "passes": bool(diff.max() < 1e-4) if diff.size else True,
        "path_resolution": ctx.path_resolution,
    }
    write_json(out_dir / "gpu_fused_parity_report.json", report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run GPU-fused BWE v6 max-alpha base/strong search")
    parser.add_argument("--root", default=None)
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
    parser.add_argument("--batch-size", type=int, default=8192)
    parser.add_argument("--checkpoint-every", type=int, default=1_000_000)
    parser.add_argument("--seed-offset", type=int, default=7_509_000_000)
    parser.add_argument("--prune-margin", type=int, default=500_000)
    parser.add_argument("--reject-sample-limit", type=int, default=50_000)
    parser.add_argument("--parity-size", type=int, default=1024)
    parser.add_argument("--parity-only", action="store_true")
    parser.add_argument("--skip-parity", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not torch.cuda.is_available():
        raise SystemExit("CUDA is required for gpu-fused runner")
    root = resolve_root(args.root)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    shared_dir = ensure_dir(root / "runs" / f"bwe_complete_strategy_v6_max_alpha_gpu_fused_combined_{timestamp}")
    base_dir = ensure_dir(root / "runs" / f"bwe_complete_strategy_v6_max_alpha_gpu_fused_base_{timestamp}")
    strong_dir = ensure_dir(root / "runs" / f"bwe_complete_strategy_v6_max_alpha_gpu_fused_strong_{timestamp}")
    checkpoints = ensure_dir(shared_dir / "checkpoints")
    write_json(
        shared_dir / "gpu_fused_run_plan.json",
        {
            "paper_only": True,
            "live_allowed": False,
            "runner": "gpu_fused_combined_base_and_strong",
            "coarse_eval": args.coarse_eval,
            "candidate_space_sample": args.candidate_space_sample,
            "base_dir": str(base_dir),
            "strong_dir": str(strong_dir),
            "batch_size": args.batch_size,
            "quality_guard": "parity check against canonical CPU coarse metrics before full run unless --skip-parity is set",
        },
    )
    if not args.skip_parity:
        parity = run_parity(root, int(args.parity_size), int(args.seed_offset), shared_dir)
        if not parity["passes"]:
            raise SystemExit(f"gpu fused parity failed: {parity}")
    if args.parity_only:
        print(f"parity-only complete: {shared_dir}", flush=True)
        return

    ctx = SmokeContext(root, use_torch_path=False)
    state = build_state(ctx, "cuda")
    baselines = evaluate_baselines(ctx, {})
    baselines.to_csv(shared_dir / "baseline_comparison.csv", index=False)
    write_jsonl(shared_dir / "baseline_catalog.jsonl", baselines.to_dict(orient="records"))

    top_scores = np.empty(0, dtype=np.float32)
    top_seeds = np.empty(0, dtype=np.int64)
    reject_counts: Counter[str] = Counter()
    reject_seed_samples: list[int] = []
    start = time.time()
    evaluated = 0
    print(f"gpu fused coarse started batch={args.batch_size} eval={args.coarse_eval}", flush=True)
    while evaluated < args.coarse_eval:
        batch = min(int(args.batch_size), int(args.coarse_eval - evaluated))
        seed_start = int(args.seed_offset + evaluated)
        seeds = torch.arange(seed_start, seed_start + batch, dtype=torch.long, device="cuda")
        with torch.no_grad():
            out = fused_batch_scores(state, seeds, details=False)
        scores = out["robust_score"].detach().cpu().numpy()
        seed_np = out["candidate_seed"].detach().cpu().numpy()
        top_scores, top_seeds = append_and_prune(top_scores, top_seeds, scores, seed_np, int(args.strong_medium_eval), int(args.prune_margin))
        reject_np = out["reject"].detach().cpu().numpy()
        reject_counts["gpu_fused_reject"] += int(reject_np.sum())
        if len(reject_seed_samples) < args.reject_sample_limit and reject_np.any():
            remaining = int(args.reject_sample_limit - len(reject_seed_samples))
            reject_seed_samples.extend(seed_np[reject_np][:remaining].astype(np.int64).tolist())
        evaluated += batch
        if evaluated % int(args.checkpoint_every) < batch or evaluated == args.coarse_eval:
            elapsed = time.time() - start
            write_json(
                checkpoints / "gpu_fused_progress.json",
                {
                    "stage": "gpu_fused_coarse",
                    "evaluated": evaluated,
                    "coarse_eval": int(args.coarse_eval),
                    "top_pool_size": int(top_scores.size),
                    "reject_counts": dict(reject_counts),
                    "elapsed_seconds": elapsed,
                    "rate_candidates_per_second": evaluated / elapsed if elapsed > 0 else 0,
                    "path_resolution": state.path_resolution,
                    "cuda_memory_allocated_bytes": int(torch.cuda.memory_allocated()),
                    "cuda_memory_reserved_bytes": int(torch.cuda.memory_reserved()),
                },
            )
            print(f"gpu fused coarse evaluated {evaluated}/{args.coarse_eval}; pool={top_scores.size}; elapsed={elapsed:.1f}s", flush=True)

    if top_scores.size > int(args.strong_medium_eval):
        idx = np.argpartition(top_scores, -int(args.strong_medium_eval))[-int(args.strong_medium_eval) :]
        top_scores = top_scores[idx]
        top_seeds = top_seeds[idx]
    strong_seed_csv = strong_dir / "max_alpha_gpu_fused_strong_eval_top_seed_scores.csv"
    base_seed_csv = base_dir / "max_alpha_gpu_fused_base_eval_top_seed_scores.csv"
    sorted_scores, sorted_seeds = write_seed_scores(strong_seed_csv, top_scores, top_seeds, int(args.strong_medium_eval))
    write_seed_scores(base_seed_csv, sorted_scores, sorted_seeds, int(args.base_medium_eval))
    write_json(
        shared_dir / "gpu_fused_coarse_done.json",
        {
            "evaluated": evaluated,
            "strong_seed_scores_csv": str(strong_seed_csv),
            "base_seed_scores_csv": str(base_seed_csv),
            "elapsed_seconds": time.time() - start,
            "reject_counts": dict(reject_counts),
        },
    )

    reject_log = materialize_rejects(root, state.space, reject_seed_samples, int(args.reject_sample_limit))
    base_medium_csv = base_dir / "max_alpha_gpu_fused_base_eval_top_candidates.csv"
    strong_medium_csv = strong_dir / "max_alpha_gpu_fused_strong_eval_top_candidates.csv"
    base_rows = materialize_rows(root, state.space, sorted_seeds[: int(args.base_deep_eval)], base_medium_csv, "max_alpha_gpu_fused_base")
    strong_rows = materialize_rows(root, state.space, sorted_seeds[: int(args.strong_deep_eval)], strong_medium_csv, "max_alpha_gpu_fused_strong")
    notes = {
        "shared_gpu_fused_dir": str(shared_dir),
        "base_full_top_pool_seed_scores": str(base_seed_csv),
        "strong_full_top_pool_seed_scores": str(strong_seed_csv),
        "coarse_elapsed_seconds_before_finalize": time.time() - start,
        "coarse_fused_on_cuda": True,
        "final_deep_uses_canonical_v6_metrics": True,
    }
    finalize_profile(
        root,
        base_dir,
        "max_alpha_gpu_fused_base",
        base_medium_csv,
        base_rows,
        int(args.candidate_space_sample),
        int(args.coarse_eval),
        int(args.base_medium_eval),
        int(args.base_deep_eval),
        int(args.base_stress_eval),
        int(args.base_portfolio_eval),
        baselines,
        reject_log,
        reject_counts,
        notes,
    )
    finalize_profile(
        root,
        strong_dir,
        "max_alpha_gpu_fused_strong",
        strong_medium_csv,
        strong_rows,
        int(args.candidate_space_sample),
        int(args.coarse_eval),
        int(args.strong_medium_eval),
        int(args.strong_deep_eval),
        int(args.strong_stress_eval),
        int(args.strong_portfolio_eval),
        baselines,
        reject_log,
        reject_counts,
        notes,
    )
    write_json(
        shared_dir / "gpu_fused_combined_done.json",
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
