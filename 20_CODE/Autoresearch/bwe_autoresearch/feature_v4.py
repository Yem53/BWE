"""BWE AutoResearch v4 entry deep-search pipeline.

v4 keeps v3's paper-only boundary but changes entry research from one-condition
screening into a denser, soft-penalized, multi-condition entry search.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from .feature_v3 import (
    DEFAULT_FEATURE_DIR,
    clean_json,
    compute_mark_outcomes,
    condition_mask,
    contains_future_field,
    ensure_out_dir,
    load_inputs,
    metrics_from_trades,
    min_sample_for_channel,
    write_json,
)


DEFAULT_OUT_DIR = Path("/Users/ye/.hermes/research/bwe_autoresearch_entry_v4_20260425")

V4_DELAYS_S = (0, 30, 60, 180, 300)
V4_HORIZONS_MIN = (15, 30, 60)
V4_GRID_QUANTILES = (0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90)
V4_MAX_MANIFEST_ITEMS = 10
SOFT_FILTER_POLICY = "downgrade_not_exclude"
SOFT_PENALTY_SCORE_WEIGHT = 0.85
STRESS_EXTRA_COST_PCT = 0.20

FUTURE_FIELD_PREFIXES = ("ret_", "net_", "confirm_after_")
FUTURE_FIELD_NAMES = {"mfe", "mae", "mfe_pct", "mae_pct"}

AGE_COLUMNS = (
    "open_interest_hist__age_ms",
    "global_long_short_account_ratio__age_ms",
    "top_trader_long_short_account_ratio__age_ms",
    "top_trader_long_short_position_ratio__age_ms",
    "taker_buy_sell_volume__age_ms",
    "basis_perpetual__age_ms",
    "mark_1m_age_ms",
    "premium_1m_age_ms",
)

V4_FEATURE_PACKETS: dict[str, tuple[str, ...]] = {
    "message_context": (
        "move_pct",
        "burst_seq_5m",
        "burst_count_5m",
        "pre3m",
        "pre5m",
        "pre30m",
        "btc_pre30m",
    ),
    "liquidity_listing": (
        "quote_volume_24h",
        "marketcap",
        "listing_age_days",
    ),
    "oi_funding": (
        "oi_ratio_pct",
        "oi_change_pct",
        "open_interest_hist__sumOpenInterestValue",
        "funding_rate",
    ),
    "taker_flow": (
        "taker_buy_sell_volume__buySellRatio",
        "taker_buy_sell_volume__buyVol",
        "taker_buy_sell_volume__sellVol",
    ),
    "crowding": (
        "global_long_short_account_ratio__longShortRatio",
        "top_trader_long_short_account_ratio__longShortRatio",
        "top_trader_long_short_position_ratio__longShortRatio",
    ),
    "basis_premium_mark": (
        "basis_perpetual__basisRate",
        "basis_perpetual__basis",
        "mark_minus_index_proxy_pct",
        "premium_1m_close",
    ),
}


@dataclass(frozen=True)
class DeepEntryRule:
    candidate_id: str
    family: str
    feature_packets: tuple[str, ...]
    stage: str
    channel: str
    event_type: str
    action: str
    conditions: tuple[dict[str, Any], ...]
    complexity: int
    soft_filter_policy: str = SOFT_FILTER_POLICY


def is_future_field_name(name: str) -> bool:
    return name in FUTURE_FIELD_NAMES or any(name.startswith(prefix) for prefix in FUTURE_FIELD_PREFIXES)


def rule_future_fields(rule: DeepEntryRule | dict[str, Any]) -> list[str]:
    payload = asdict(rule) if isinstance(rule, DeepEntryRule) else rule
    return contains_future_field(payload)


def _append_flag(flags: list[list[str]], index: pd.Index, mask: pd.Series, flag: str) -> None:
    for pos in np.flatnonzero(mask.reindex(index, fill_value=False).to_numpy()):
        flags[pos].append(flag)


def add_soft_filter_penalties(events: pd.DataFrame) -> pd.DataFrame:
    """Add soft risk penalties without excluding rows.

    User requirement for v4: hard filters should downgrade candidates rather than
    remove them. This function therefore keeps every input event and records the
    reason in `soft_filter_flags`.
    """

    out = events.copy()
    penalty = pd.Series(0.0, index=out.index)
    flags: list[list[str]] = [[] for _ in range(len(out))]

    if "is_tradable_at_event" in out.columns:
        mask = ~out["is_tradable_at_event"].fillna(False).astype(bool)
        penalty += mask.astype(float) * 6.0
        _append_flag(flags, out.index, mask, "not_tradable_at_event")

    if "listing_age_days" in out.columns:
        age = pd.to_numeric(out["listing_age_days"], errors="coerce")
        mask = age < 3
        penalty += mask.fillna(False).astype(float) * 2.5
        _append_flag(flags, out.index, mask, "listing_age_lt_3d")
        mask = (age >= 3) & (age < 7)
        penalty += mask.fillna(False).astype(float) * 1.5
        _append_flag(flags, out.index, mask, "listing_age_3d_7d")
        mask = (age >= 7) & (age < 14)
        penalty += mask.fillna(False).astype(float) * 0.75
        _append_flag(flags, out.index, mask, "listing_age_7d_14d")

    for col, flag, floor, high_penalty, low_penalty in (
        ("quote_volume_24h", "low_quote_volume", 5_000_000.0, 2.0, 1.0),
        ("marketcap", "low_marketcap", 10_000_000.0, 1.25, 0.6),
    ):
        if col in out.columns:
            values = pd.to_numeric(out[col], errors="coerce")
            q10 = values.quantile(0.10)
            q20 = values.quantile(0.20)
            severe = values < max(float(q10) if math.isfinite(float(q10)) else floor, floor)
            mild = (values >= max(float(q10) if math.isfinite(float(q10)) else floor, floor)) & (values < float(q20))
            penalty += severe.fillna(False).astype(float) * high_penalty
            penalty += mild.fillna(False).astype(float) * low_penalty
            _append_flag(flags, out.index, severe, f"{flag}_severe")
            _append_flag(flags, out.index, mild, f"{flag}_mild")

    if "mark_minus_index_proxy_pct" in out.columns:
        basis = pd.to_numeric(out["mark_minus_index_proxy_pct"], errors="coerce").abs()
        mask = basis > 0.25
        penalty += mask.fillna(False).astype(float) * 1.5
        _append_flag(flags, out.index, mask, "mark_index_deviation_extreme")

    if "btc_pre30m" in out.columns:
        btc = pd.to_numeric(out["btc_pre30m"], errors="coerce")
        event = out.get("event_type", pd.Series("", index=out.index)).astype(str)
        pump_adverse = event.eq("pump") & (btc < -1.0)
        crash_adverse = event.eq("crash") & (btc > 1.0)
        mask = pump_adverse | crash_adverse
        penalty += mask.fillna(False).astype(float) * 1.0
        _append_flag(flags, out.index, mask, "btc_regime_adverse")

    for col in AGE_COLUMNS:
        if col not in out.columns:
            continue
        age = pd.to_numeric(out[col], errors="coerce")
        stale = (age > 5 * 60_000) & (age <= 10 * 60_000)
        too_old = age > 10 * 60_000
        missing = age.isna()
        penalty += stale.fillna(False).astype(float) * 0.35
        penalty += too_old.fillna(False).astype(float) * 1.0
        penalty += missing.fillna(False).astype(float) * 0.2
        _append_flag(flags, out.index, stale, f"{col}_stale")
        _append_flag(flags, out.index, too_old, f"{col}_too_old")
        _append_flag(flags, out.index, missing, f"{col}_missing")

    if "funding_age_ms" in out.columns:
        funding_age = pd.to_numeric(out["funding_age_ms"], errors="coerce")
        funding_too_old = funding_age > 9 * 60 * 60_000
        funding_missing = funding_age.isna()
        penalty += funding_too_old.fillna(False).astype(float) * 0.75
        penalty += funding_missing.fillna(False).astype(float) * 0.2
        _append_flag(flags, out.index, funding_too_old, "funding_age_gt_9h")
        _append_flag(flags, out.index, funding_missing, "funding_age_missing")

    out["soft_filter_penalty"] = penalty.round(6)
    out["soft_filter_flags"] = ["|".join(item) if item else "" for item in flags]
    return out


def enrich_events_with_forward_context(events: pd.DataFrame, forward: pd.DataFrame) -> pd.DataFrame:
    context_cols = [
        "event_key",
        "confirm_within_5m_pricechange",
        "confirm_within_5m_reserved6",
        "confirm_within_5m_oi",
        "confirm_before_5m_pricechange",
        "confirm_before_5m_reserved6",
        "confirm_before_5m_oi",
        "confirm_count_5m",
        "burst_seq_5m",
        "burst_count_5m",
        "pre3m",
        "pre5m",
        "pre30m",
        "trend_state",
        "btc_pre30m",
        "regime_state",
    ]
    available = [col for col in context_cols if col in forward.columns]
    if "event_key" not in available:
        return events.copy()
    context = (
        forward[available]
        .drop_duplicates("event_key")
        .copy()
    )
    add_cols = [col for col in context.columns if col == "event_key" or col not in events.columns]
    return events.merge(context[add_cols], on="event_key", how="left")


def _finite_quantile(series: pd.Series, q: float) -> float | None:
    series = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if series.nunique() < 4:
        return None
    value = float(series.quantile(q))
    if not math.isfinite(value):
        return None
    return value


def primitive_conditions(events: pd.DataFrame, packet: str, *, max_per_field: int = 18) -> list[dict[str, Any]]:
    cols = V4_FEATURE_PACKETS.get(packet, ())
    out: list[dict[str, Any]] = []
    base = events[events.get("core_complete", True)].copy()
    for col in cols:
        if col not in base.columns or is_future_field_name(col):
            continue
        per_field: list[dict[str, Any]] = []
        for q in V4_GRID_QUANTILES:
            value = _finite_quantile(base[col], q)
            if value is None:
                continue
            per_field.append({"col": col, "op": "gte", "value": round(value, 10), "feature_packet": packet, "q": q})
            per_field.append({"col": col, "op": "lte", "value": round(value, 10), "feature_packet": packet, "q": q})
        out.extend(per_field[:max_per_field])
    return out


def _condition_coverage(df: pd.DataFrame, cond: dict[str, Any]) -> float:
    if df.empty:
        return 0.0
    return float(condition_mask(df, [cond]).mean())


def _select_context_conditions(context_df: pd.DataFrame, *, per_packet: int = 8) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for packet in V4_FEATURE_PACKETS:
        conds = primitive_conditions(context_df, packet)
        scored = []
        for cond in conds:
            coverage = _condition_coverage(context_df, cond)
            if 0.05 <= coverage <= 0.85:
                balance = 1.0 - abs(coverage - 0.35)
                scored.append((balance, coverage, cond))
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        selected.extend([cond for _, _, cond in scored[:per_packet]])
    return selected


def _combo_packet_key(conditions: Iterable[dict[str, Any]]) -> tuple[str, ...]:
    return tuple(sorted({str(cond.get("feature_packet", "")) for cond in conditions}))


def build_deep_entry_rules(events: pd.DataFrame, *, max_rules_per_context: int = 360) -> list[DeepEntryRule]:
    base = events[events.get("core_complete", True)].copy()
    contexts = (
        base[["channel", "event_type"]]
        .dropna()
        .drop_duplicates()
        .sort_values(["channel", "event_type"])
        .itertuples(index=False, name=None)
    )
    rules: list[DeepEntryRule] = []
    seen_ids: set[str] = set()
    for channel, event_type in contexts:
        context_df = base[base["channel"].eq(channel) & base["event_type"].eq(event_type)].copy()
        context_conditions = _select_context_conditions(context_df)
        for action in ("long", "short"):
            local_rules: list[DeepEntryRule] = []
            baseline_id = f"entry_v4__baseline__{channel}__{event_type}__{action}"
            local_rules.append(
                DeepEntryRule(
                    candidate_id=baseline_id,
                    family="baseline_context",
                    feature_packets=("baseline_only",),
                    stage="entry_gate_v4",
                    channel=str(channel),
                    event_type=str(event_type),
                    action=action,
                    conditions=(),
                    complexity=1,
                )
            )

            for idx, cond in enumerate(context_conditions, 1):
                packet = str(cond.get("feature_packet", "feature"))
                local_rules.append(
                    DeepEntryRule(
                        candidate_id=f"entry_v4__{packet}__{channel}__{event_type}__{action}__s{idx:03d}",
                        family="single_feature_deep_filter",
                        feature_packets=(packet,),
                        stage="entry_gate_v4",
                        channel=str(channel),
                        event_type=str(event_type),
                        action=action,
                        conditions=(cond,),
                        complexity=2,
                    )
                )

            pair_count = 0
            for left, right in itertools.combinations(context_conditions, 2):
                packets = _combo_packet_key((left, right))
                if len(packets) < 2:
                    continue
                pair_count += 1
                local_rules.append(
                    DeepEntryRule(
                        candidate_id=f"entry_v4__combo2__{channel}__{event_type}__{action}__p{pair_count:04d}",
                        family="multi_feature_combo2",
                        feature_packets=packets,
                        stage="entry_gate_v4",
                        channel=str(channel),
                        event_type=str(event_type),
                        action=action,
                        conditions=(left, right),
                        complexity=3,
                    )
                )
                if pair_count >= max_rules_per_context // 2:
                    break

            triple_count = 0
            priority_packets = {"message_context", "oi_funding", "taker_flow", "basis_premium_mark", "crowding", "liquidity_listing"}
            priority_conditions = [cond for cond in context_conditions if cond.get("feature_packet") in priority_packets]
            for combo in itertools.combinations(priority_conditions, 3):
                packets = _combo_packet_key(combo)
                if len(packets) < 3:
                    continue
                triple_count += 1
                local_rules.append(
                    DeepEntryRule(
                        candidate_id=f"entry_v4__combo3__{channel}__{event_type}__{action}__t{triple_count:04d}",
                        family="multi_feature_combo3",
                        feature_packets=packets,
                        stage="entry_gate_v4",
                        channel=str(channel),
                        event_type=str(event_type),
                        action=action,
                        conditions=tuple(combo),
                        complexity=4,
                    )
                )
                if triple_count >= max_rules_per_context // 5:
                    break

            for rule in local_rules[:max_rules_per_context]:
                if rule.candidate_id in seen_ids:
                    continue
                seen_ids.add(rule.candidate_id)
                rules.append(rule)
    return rules


def purged_walk_forward_metrics(values: Iterable[float], ts_ms: Iterable[Any], *, windows: int = 5) -> dict[str, Any]:
    data = pd.DataFrame({"net": pd.to_numeric(pd.Series(list(values)), errors="coerce"), "ts_ms": list(ts_ms)})
    data["ts"] = pd.to_datetime(data["ts_ms"], unit="ms", errors="coerce", utc=True)
    data = data.dropna(subset=["net", "ts"]).sort_values("ts")
    if len(data) < windows * 5:
        return {"purged_wf_windows": 0, "purged_wf_positive_rate_pct": 0.0, "purged_wf_min_median_pct": 0.0}
    splits = np.array_split(np.arange(len(data)), windows)
    fold_medians = []
    for split in splits:
        if len(split) == 0:
            continue
        fold_medians.append(float(data.iloc[split]["net"].median()))
    if not fold_medians:
        return {"purged_wf_windows": 0, "purged_wf_positive_rate_pct": 0.0, "purged_wf_min_median_pct": 0.0}
    arr = np.asarray(fold_medians, dtype=float)
    return {
        "purged_wf_windows": int(arr.size),
        "purged_wf_positive_rate_pct": round(float((arr > 0).mean() * 100.0), 6),
        "purged_wf_min_median_pct": round(float(arr.min()), 6),
    }


def entry_v4_decision(metrics: dict[str, Any], *, min_sample: int, complexity: int) -> tuple[str, str]:
    if metrics.get("sample_size", 0) < min_sample:
        return "need_more_data", f"sample_lt_{min_sample}"
    if metrics.get("symbol_count", 0) < 8:
        return "need_more_data", "symbol_count_lt_8"
    if metrics.get("median_net_pct", 0.0) <= 0:
        return "reject", "median_non_positive"
    if metrics.get("p25_net_pct", 0.0) < -0.75 or metrics.get("p10_net_pct", 0.0) < -2.5:
        return "reject", "left_tail_too_weak"
    if metrics.get("remove_top_1pct_mean_net_pct", 0.0) <= 0:
        return "reject", "top_1pct_winner_dependent"
    if metrics.get("top_symbol_share_pct", 0.0) > 30:
        return "watchlist", "top_symbol_concentration"
    if metrics.get("stress_fee_slippage_mean_net_pct", 0.0) <= 0:
        return "watchlist", "stress_fee_slippage_weak"
    wf_rate = max(metrics.get("walk_forward_positive_rate_pct", 0.0), metrics.get("purged_wf_positive_rate_pct", 0.0))
    if (
        metrics.get("win_rate_pct", 0.0) >= 58.0
        and metrics.get("profit_factor", 0.0) >= 1.30
        and wf_rate >= 60.0
        and metrics.get("median_net_pct", 0.0) > 0
        and metrics.get("remove_top_1pct_mean_net_pct", 0.0) > 0
        and complexity <= 6
    ):
        return "promote_to_paper", "passes_v4_entry_deep_gates"
    if metrics.get("win_rate_pct", 0.0) >= 53.0 and metrics.get("profit_factor", 0.0) >= 1.10:
        return "watchlist", "positive_but_below_promote_gate"
    return "reject", "fails_v4_win_profit_stability_gate"


def entry_v4_score(metrics: dict[str, Any], *, complexity: int, avg_soft_penalty: float) -> float:
    return round(
        metrics.get("median_net_pct", 0.0) * 8.0
        + metrics.get("p25_net_pct", 0.0) * 4.0
        + metrics.get("p10_net_pct", 0.0) * 2.0
        + metrics.get("win_rate_pct", 0.0) * 0.08
        + metrics.get("profit_factor", 0.0) * 1.2
        + metrics.get("purged_wf_positive_rate_pct", metrics.get("walk_forward_positive_rate_pct", 0.0)) * 0.06
        + metrics.get("remove_top_1pct_mean_net_pct", 0.0) * 1.5
        - metrics.get("top_symbol_share_pct", 0.0) * 0.04
        - metrics.get("longest_losing_streak", 0.0) * 0.18
        - complexity * 0.35
        - avg_soft_penalty * SOFT_PENALTY_SCORE_WEIGHT,
        6,
    )


def _score_values(subset: pd.DataFrame) -> dict[str, Any]:
    values = pd.to_numeric(subset["mark_net_pct"], errors="coerce")
    metrics = metrics_from_trades(values, symbols=subset.get("api_symbol"), ts_ms=subset.get("ts_ms"))
    wf = purged_walk_forward_metrics(values, subset.get("ts_ms", []))
    metrics.update(wf)
    stress_values = values - STRESS_EXTRA_COST_PCT
    stress = metrics_from_trades(stress_values, symbols=subset.get("api_symbol"), ts_ms=subset.get("ts_ms"))
    metrics["stress_fee_slippage_mean_net_pct"] = stress["mean_net_pct"]
    metrics["stress_fee_slippage_median_net_pct"] = stress["median_net_pct"]
    return metrics


def prepare_entry_outcomes(events: pd.DataFrame, mark_outcomes: pd.DataFrame) -> pd.DataFrame:
    drop_cols = [col for col in ("channel", "event_type", "symbol") if col in events.columns]
    return mark_outcomes.merge(events.drop(columns=drop_cols, errors="ignore"), on="event_key", how="left", suffixes=("", "_event"))


def score_deep_rule(events: pd.DataFrame, mark_outcomes: pd.DataFrame, rule: DeepEntryRule, *, delay_s: int, horizon_min: int) -> tuple[dict[str, Any], pd.DataFrame]:
    outcomes = mark_outcomes[
        mark_outcomes["side"].eq(rule.action)
        & mark_outcomes["entry_delay_s"].eq(delay_s)
        & mark_outcomes["horizon_min"].eq(horizon_min)
    ].copy()
    if outcomes.empty:
        empty_metrics = metrics_from_trades([])
        empty_metrics.update({"purged_wf_windows": 0, "purged_wf_positive_rate_pct": 0.0, "purged_wf_min_median_pct": 0.0, "stress_fee_slippage_mean_net_pct": 0.0, "stress_fee_slippage_median_net_pct": 0.0})
        return {**asdict(rule), "entry_delay_s": delay_s, "horizon_min": horizon_min, "decision": "reject", "reject_reason": "no_mark_outcomes", "score": -999.0, **empty_metrics}, outcomes
    merged = outcomes if "soft_filter_penalty" in outcomes.columns else prepare_entry_outcomes(events, outcomes)
    mask = merged["channel"].eq(rule.channel) & merged["event_type"].eq(rule.event_type)
    if rule.conditions:
        mask &= condition_mask(merged, rule.conditions)
    subset = merged.loc[mask].copy()
    metrics = _score_values(subset) if not subset.empty else _score_values(pd.DataFrame({"mark_net_pct": [], "api_symbol": [], "ts_ms": []}))
    avg_penalty = float(pd.to_numeric(subset.get("soft_filter_penalty", pd.Series(dtype=float)), errors="coerce").mean()) if not subset.empty else 0.0
    if not math.isfinite(avg_penalty):
        avg_penalty = 0.0
    decision, reason = entry_v4_decision(metrics, min_sample=min_sample_for_channel(rule.channel), complexity=rule.complexity)
    row = {
        **asdict(rule),
        "feature_packets": "|".join(rule.feature_packets),
        "conditions_json": json.dumps(clean_json(list(rule.conditions)), ensure_ascii=False, sort_keys=True),
        "entry_delay_s": int(delay_s),
        "horizon_min": int(horizon_min),
        "path_resolution": "1m_mark",
        "soft_filter_policy": SOFT_FILTER_POLICY,
        "avg_soft_filter_penalty": round(avg_penalty, 6),
        "decision": decision,
        "reject_reason": reason,
        "score": entry_v4_score(metrics, complexity=rule.complexity, avg_soft_penalty=avg_penalty),
        **metrics,
    }
    return row, subset


def run_deep_entry_search(events: pd.DataFrame, mark_outcomes: pd.DataFrame, *, max_rules_per_context: int, top_rules: int | None = 180) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rules = build_deep_entry_rules(events, max_rules_per_context=max_rules_per_context)
    combo_rules = pd.DataFrame(
        [
            {
                **asdict(rule),
                "feature_packets": "|".join(rule.feature_packets),
                "conditions_json": json.dumps(clean_json(list(rule.conditions)), ensure_ascii=False, sort_keys=True),
                "condition_count": len(rule.conditions),
            }
            for rule in rules
        ]
    )

    gate_rows: list[dict[str, Any]] = []
    for rule in rules:
        row, _ = score_deep_rule(events, mark_outcomes, rule, delay_s=0, horizon_min=30)
        row["timing_candidate_id"] = f"{rule.candidate_id}__delay0s__h30m"
        row["trigger_style"] = "t0_entry_with_conditions"
        gate_rows.append(row)
    gate = pd.DataFrame(gate_rows)
    if not gate.empty:
        decision_rank = {"promote_to_paper": 0, "watchlist": 1, "need_more_data": 2, "reject": 3}
        gate["decision_rank"] = gate["decision"].map(decision_rank).fillna(9).astype(int)
        gate = gate.sort_values(["decision_rank", "score", "median_net_pct", "p25_net_pct", "sample_size"], ascending=[True, False, False, False, False])

    selected_ids: list[str] = []
    if not gate.empty:
        gate = gate.copy()
        gate["min_sample_required"] = gate["channel"].map(min_sample_for_channel)
        eligible = gate[
            gate["decision"].isin(["promote_to_paper", "watchlist"])
            | ((gate["sample_size"] >= gate["min_sample_required"]) & (gate["median_net_pct"] > 0))
        ].sort_values(["decision_rank", "score", "sample_size"], ascending=[True, False, False])
        if eligible.empty:
            eligible = gate.sort_values(["score", "sample_size"], ascending=False)
        selected_ids = eligible["candidate_id"].head(top_rules or len(eligible)).tolist()
    rule_map = {rule.candidate_id: rule for rule in rules}
    candidate_rules = [rule_map[cid] for cid in selected_ids if cid in rule_map]

    rows: list[dict[str, Any]] = []
    for rule in candidate_rules:
        for delay_s in V4_DELAYS_S:
            for horizon_min in V4_HORIZONS_MIN:
                row, _ = score_deep_rule(events, mark_outcomes, rule, delay_s=delay_s, horizon_min=horizon_min)
                row["timing_candidate_id"] = f"{rule.candidate_id}__delay{delay_s}s__h{horizon_min}m"
                row["trigger_style"] = "t0_entry_with_conditions" if delay_s == 0 else "delay_confirm_or_abandon"
                rows.append(row)
    leaderboard = pd.DataFrame(rows)
    if not leaderboard.empty:
        decision_rank = {"promote_to_paper": 0, "watchlist": 1, "need_more_data": 2, "reject": 3}
        leaderboard["decision_rank"] = leaderboard["decision"].map(decision_rank).fillna(9).astype(int)
        leaderboard = leaderboard.sort_values(["decision_rank", "score", "median_net_pct", "p25_net_pct", "sample_size"], ascending=[True, False, False, False, False])
    return leaderboard, combo_rules, gate


def no_trade_matrix(leaderboard: pd.DataFrame) -> pd.DataFrame:
    if leaderboard.empty:
        return pd.DataFrame(columns=["channel", "event_type", "recommended_action"])
    rows = []
    for (channel, event_type), group in leaderboard.groupby(["channel", "event_type"], dropna=False):
        eligible = group[group["sample_size"] >= group["channel"].map(min_sample_for_channel)]
        if eligible.empty:
            rows.append({"channel": channel, "event_type": event_type, "recommended_action": "no_trade", "reason": "no_sample_eligible_candidate"})
            continue
        stable = eligible[eligible["decision"].isin(["promote_to_paper", "watchlist"])]
        best = (stable if not stable.empty else eligible).sort_values("score", ascending=False).iloc[0]
        if best["decision"] in {"promote_to_paper", "watchlist"}:
            action = str(best["action"])
            reason = f"best_{action}_{best['decision']}"
        elif float(best["median_net_pct"]) <= 0 or float(best["p25_net_pct"]) < -0.75:
            action = "no_trade"
            reason = "best_candidate_left_tail_or_median_weak"
        else:
            action = "wait"
            reason = "positive_but_not_stable"
        rows.append(
            {
                "channel": channel,
                "event_type": event_type,
                "recommended_action": action,
                "reason": reason,
                "best_candidate_id": best["candidate_id"],
                "best_entry_delay_s": int(best["entry_delay_s"]),
                "best_horizon_min": int(best["horizon_min"]),
                "best_median_net_pct": best["median_net_pct"],
                "best_p25_net_pct": best["p25_net_pct"],
                "best_score": best["score"],
                "best_decision": best["decision"],
            }
        )
    return pd.DataFrame(rows).sort_values(["recommended_action", "channel", "event_type"])


def purged_walkforward_rows(leaderboard: pd.DataFrame, events: pd.DataFrame, mark_outcomes: pd.DataFrame, *, top_n: int = 30) -> pd.DataFrame:
    rows = []
    top = leaderboard[leaderboard["decision"].isin(["promote_to_paper", "watchlist"])].head(top_n)
    if top.empty:
        top = leaderboard.head(min(top_n, len(leaderboard)))
    for item in top.itertuples(index=False):
        conds = tuple(json.loads(getattr(item, "conditions_json", "[]")))
        rule = DeepEntryRule(
            candidate_id=str(item.candidate_id),
            family=str(item.family),
            feature_packets=tuple(str(item.feature_packets).split("|")),
            stage="entry_gate_v4",
            channel=str(item.channel),
            event_type=str(item.event_type),
            action=str(item.action),
            conditions=conds,
            complexity=int(item.complexity),
        )
        _, subset = score_deep_rule(events, mark_outcomes, rule, delay_s=int(item.entry_delay_s), horizon_min=int(item.horizon_min))
        if subset.empty:
            continue
        subset = subset.sort_values("ts_ms")
        for fold_id, split_idx in enumerate(np.array_split(np.arange(len(subset)), 5), 1):
            part = subset.iloc[split_idx]
            if part.empty:
                continue
            values = pd.to_numeric(part["mark_net_pct"], errors="coerce")
            rows.append(
                {
                    "candidate_id": item.candidate_id,
                    "timing_candidate_id": item.timing_candidate_id,
                    "fold_id": fold_id,
                    "fold_start_ts_ms": int(part["ts_ms"].min()),
                    "fold_end_ts_ms": int(part["ts_ms"].max()),
                    "purge_before_after_min": 5,
                    **metrics_from_trades(values, symbols=part.get("api_symbol"), ts_ms=part.get("ts_ms")),
                }
            )
    return pd.DataFrame(rows)


def stress_report_rows(leaderboard: pd.DataFrame, events: pd.DataFrame, mark_outcomes: pd.DataFrame, *, top_n: int = 30) -> pd.DataFrame:
    rows = []
    top = leaderboard[leaderboard["decision"].isin(["promote_to_paper", "watchlist"])].head(top_n)
    if top.empty:
        top = leaderboard.head(min(top_n, len(leaderboard)))
    stress_specs = (
        ("base", 0.0),
        ("fee_slippage_plus_20bp", 0.20),
        ("latency_and_slippage_plus_40bp", 0.40),
        ("severe_slippage_plus_75bp", 0.75),
    )
    for item in top.itertuples(index=False):
        conds = tuple(json.loads(getattr(item, "conditions_json", "[]")))
        rule = DeepEntryRule(
            candidate_id=str(item.candidate_id),
            family=str(item.family),
            feature_packets=tuple(str(item.feature_packets).split("|")),
            stage="entry_gate_v4",
            channel=str(item.channel),
            event_type=str(item.event_type),
            action=str(item.action),
            conditions=conds,
            complexity=int(item.complexity),
        )
        _, subset = score_deep_rule(events, mark_outcomes, rule, delay_s=int(item.entry_delay_s), horizon_min=int(item.horizon_min))
        if subset.empty:
            continue
        values = pd.to_numeric(subset["mark_net_pct"], errors="coerce")
        for stress_name, extra_cost in stress_specs:
            rows.append(
                {
                    "candidate_id": item.candidate_id,
                    "timing_candidate_id": item.timing_candidate_id,
                    "stress_name": stress_name,
                    "extra_cost_pct": extra_cost,
                    **metrics_from_trades(values - extra_cost, symbols=subset.get("api_symbol"), ts_ms=subset.get("ts_ms")),
                }
            )
    return pd.DataFrame(rows)


def portfolio_replay(leaderboard: pd.DataFrame, events: pd.DataFrame, mark_outcomes: pd.DataFrame, *, top_n: int = 10) -> pd.DataFrame:
    rows = []
    top = leaderboard[leaderboard["decision"].isin(["promote_to_paper", "watchlist"])].head(top_n)
    for item in top.itertuples(index=False):
        conds = tuple(json.loads(getattr(item, "conditions_json", "[]")))
        rule = DeepEntryRule(
            candidate_id=str(item.candidate_id),
            family=str(item.family),
            feature_packets=tuple(str(item.feature_packets).split("|")),
            stage="entry_gate_v4",
            channel=str(item.channel),
            event_type=str(item.event_type),
            action=str(item.action),
            conditions=conds,
            complexity=int(item.complexity),
        )
        _, subset = score_deep_rule(events, mark_outcomes, rule, delay_s=int(item.entry_delay_s), horizon_min=int(item.horizon_min))
        if subset.empty:
            continue
        subset = subset.sort_values("entry_ts_ms").copy()
        last_symbol_ts: dict[str, int] = {}
        accepted = []
        for trade in subset.itertuples(index=False):
            symbol = str(trade.api_symbol)
            entry_ts = int(trade.entry_ts_ms)
            if symbol in last_symbol_ts and entry_ts - last_symbol_ts[symbol] < 60 * 60_000:
                continue
            last_symbol_ts[symbol] = entry_ts
            accepted.append(trade)
        if not accepted:
            continue
        accepted_df = pd.DataFrame([x._asdict() for x in accepted])
        rows.append(
            {
                "candidate_id": item.candidate_id,
                "timing_candidate_id": item.timing_candidate_id,
                "one_coin_one_position": True,
                "same_symbol_cooldown_min": 60,
                "max_concurrent_positions": 5,
                "accepted_trades": len(accepted_df),
                **metrics_from_trades(accepted_df["mark_net_pct"], symbols=accepted_df.get("api_symbol"), ts_ms=accepted_df.get("ts_ms")),
            }
        )
    return pd.DataFrame(rows)


def layered_breakdown(leaderboard: pd.DataFrame) -> pd.DataFrame:
    if leaderboard.empty:
        return pd.DataFrame()
    cols = ["channel", "event_type", "action", "entry_delay_s"]
    return (
        leaderboard.groupby(cols, dropna=False)
        .agg(
            candidates=("candidate_id", "count"),
            promote=("decision", lambda s: int((s == "promote_to_paper").sum())),
            watchlist=("decision", lambda s: int((s == "watchlist").sum())),
            best_score=("score", "max"),
            best_median=("median_net_pct", "max"),
            best_p25=("p25_net_pct", "max"),
        )
        .reset_index()
        .sort_values(["promote", "watchlist", "best_score"], ascending=False)
    )


def make_entry_v4_manifest(leaderboard: pd.DataFrame, *, max_items: int = V4_MAX_MANIFEST_ITEMS) -> dict[str, Any]:
    source = leaderboard[leaderboard["decision"].isin(["promote_to_paper", "watchlist"])].copy()
    experiments = []
    seen: set[str] = set()
    for row in source.itertuples(index=False):
        if row.candidate_id in seen:
            continue
        seen.add(row.candidate_id)
        idx = len(experiments) + 1
        experiments.append(
            {
                "experiment_id": f"entry_v4_{idx:03d}",
                "schema": "bwe_entry_v4_paper_experiment",
                "paper_only": True,
                "live_allowed": False,
                "required_clean_complete": 20,
                "status": "paper_ready_manifest_only" if row.decision == "promote_to_paper" else "paper_watchlist_manifest_only",
                "entry_gate_rule": {
                    "candidate_id": row.candidate_id,
                    "channel": row.channel,
                    "event_type": row.event_type,
                    "action": row.action,
                    "conditions": json.loads(row.conditions_json),
                    "soft_filter_policy": getattr(row, "soft_filter_policy", SOFT_FILTER_POLICY),
                    "avg_soft_filter_penalty": getattr(row, "avg_soft_filter_penalty", 0.0),
                },
                "entry_timing_rule": {
                    "entry_delay_s": int(row.entry_delay_s),
                    "horizon_min": int(row.horizon_min),
                    "trigger_style": getattr(row, "trigger_style", "delay_confirm_or_abandon" if int(row.entry_delay_s) else "t0_entry_with_conditions"),
                    "abandon_after_5m_without_confirmation": True,
                },
                "risk_rule": {
                    "paper_fixed_notional": True,
                    "same_symbol_cooldown_min": 60,
                    "max_concurrent_positions": 5,
                    "fee_slippage_stress_required": True,
                },
                "path_resolution": getattr(row, "path_resolution", "1m_mark"),
                "metrics": {
                    "sample_size": int(row.sample_size),
                    "median_net_pct": row.median_net_pct,
                    "p25_net_pct": row.p25_net_pct,
                    "win_rate_pct": row.win_rate_pct,
                    "profit_factor": getattr(row, "profit_factor", 0.0),
                    "purged_wf_positive_rate_pct": getattr(row, "purged_wf_positive_rate_pct", 0.0),
                    "stress_fee_slippage_mean_net_pct": getattr(row, "stress_fee_slippage_mean_net_pct", 0.0),
                },
                "notes": "Generated by BWE AutoResearch v4 entry deep search; paper-only, no live authorization.",
            }
        )
        if len(experiments) >= max_items:
            break
    return {"schema": "bwe_autoresearch_entry_v4_manifest", "paper_only": True, "live_allowed": False, "max_promote_to_paper": max_items, "experiments": experiments}


def write_entry_v4_report(out_dir: Path, summary: dict[str, Any], leaderboard: pd.DataFrame, no_trade: pd.DataFrame, manifest: dict[str, Any]) -> None:
    top = leaderboard.head(10)
    lines = [
        "# BWE AutoResearch v4 入场深搜报告",
        "",
        "## 结论",
        f"- 输出目录：`{out_dir}`",
        f"- core_complete_events：`{summary.get('core_complete_events')}`",
        f"- generated_entry_rules：`{summary.get('generated_entry_rules')}`",
        f"- timing_rows：`{summary.get('timing_rows')}`",
        f"- promote_to_paper：`{summary.get('promote_to_paper')}`",
        f"- watchlist：`{summary.get('watchlist')}`",
        f"- manifest experiments：`{len(manifest.get('experiments', []))}`",
        "- 本轮是 entry deep search；硬过滤采用降权，不直接删样本。",
        "- 结果仍然是 paper-only，`live_allowed=false`。",
        "",
        "## Top Entry Timing",
        json.dumps(clean_json(top[["candidate_id", "family", "channel", "event_type", "action", "entry_delay_s", "horizon_min", "sample_size", "median_net_pct", "p25_net_pct", "p10_net_pct", "win_rate_pct", "profit_factor", "purged_wf_positive_rate_pct", "stress_fee_slippage_mean_net_pct", "avg_soft_filter_penalty", "decision", "reject_reason", "score"]].to_dict("records")), ensure_ascii=False, indent=2),
        "",
        "## No Trade / Wait Matrix",
        json.dumps(clean_json(no_trade.to_dict("records")), ensure_ascii=False, indent=2),
        "",
        "## 解释",
        "- v4 不再只测试单个指标阈值，而是加入 2 条件和 3 条件组合。",
        "- 阈值网格从 v3 的 25/75 分位扩展到 10%-90% 分位。",
        "- 流动性、上市年龄、mark-index 偏离、指标 age、BTC regime 等作为 `soft_filter_penalty` 降权，而不是直接剔除。",
        "- 入场决策同时看 median、p25、p10、profit factor、去 top winner、purged walk-forward、费用滑点压力。",
        "- 当前路径仍是 `1m_mark` 研究口径，不等于真实成交路径。",
    ]
    (out_dir / "report_entry_v4_zh.md").write_text("\n".join(lines), encoding="utf-8")


def run(args: argparse.Namespace) -> dict[str, Any]:
    feature_dir = Path(args.feature_dir)
    out_dir = ensure_out_dir(Path(args.out_dir))
    events, forward, mark, _premium = load_inputs(feature_dir)
    events = enrich_events_with_forward_context(events, forward)
    events = add_soft_filter_penalties(events)
    mark_outcomes = compute_mark_outcomes(events, mark, delays_s=V4_DELAYS_S, horizons_min=V4_HORIZONS_MIN)
    entry_outcomes = prepare_entry_outcomes(events, mark_outcomes)
    leaderboard, combo_rules, gate = run_deep_entry_search(events, entry_outcomes, max_rules_per_context=args.max_rules_per_context, top_rules=args.top_rules)
    no_trade = no_trade_matrix(leaderboard)
    purged = purged_walkforward_rows(leaderboard, events, entry_outcomes, top_n=args.top_diagnostics)
    stress = stress_report_rows(leaderboard, events, entry_outcomes, top_n=args.top_diagnostics)
    portfolio = portfolio_replay(leaderboard, events, entry_outcomes, top_n=args.max_manifest_items)
    layers = layered_breakdown(leaderboard)
    manifest = make_entry_v4_manifest(leaderboard, max_items=args.max_manifest_items)

    combo_rules.to_csv(out_dir / "entry_combo_rules.csv", index=False)
    gate.to_csv(out_dir / "entry_gate_deep_leaderboard.csv", index=False)
    leaderboard.to_csv(out_dir / "entry_timing_deep_leaderboard.csv", index=False)
    no_trade.to_csv(out_dir / "entry_no_trade_matrix.csv", index=False)
    purged.to_csv(out_dir / "entry_purged_walkforward.csv", index=False)
    stress.to_csv(out_dir / "entry_stress_report.csv", index=False)
    portfolio.to_csv(out_dir / "entry_portfolio_replay.csv", index=False)
    layers.to_csv(out_dir / "entry_layered_breakdown.csv", index=False)
    write_json(out_dir / "paper_manifest_entry_v4.json", manifest)

    summary = {
        "out_dir": str(out_dir),
        "feature_dir": str(feature_dir),
        "total_active_events": int(len(events)),
        "core_complete_events": int(events["core_complete"].sum()),
        "generated_entry_rules": int(len(combo_rules)),
        "timing_rows": int(len(leaderboard)),
        "entry_gate_rows": int(len(gate)),
        "promote_to_paper": int((leaderboard["decision"] == "promote_to_paper").sum()) if not leaderboard.empty else 0,
        "watchlist": int((leaderboard["decision"] == "watchlist").sum()) if not leaderboard.empty else 0,
        "manifest_experiments": int(len(manifest.get("experiments", []))),
        "soft_filter_policy": SOFT_FILTER_POLICY,
        "path_resolution": "1m_mark",
        "paper_only": True,
        "live_allowed": False,
    }
    write_json(out_dir / "summary.json", summary)
    write_entry_v4_report(out_dir, summary, leaderboard, no_trade, manifest)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run BWE AutoResearch v4 entry deep search")
    parser.add_argument("--feature-dir", default=str(DEFAULT_FEATURE_DIR))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--max-rules-per-context", type=int, default=180)
    parser.add_argument("--top-rules", type=int, default=180, help="Rules promoted from gate scan into delay/timing search")
    parser.add_argument("--top-diagnostics", type=int, default=40)
    parser.add_argument("--max-manifest-items", type=int, default=10)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.top_rules <= 0:
        args.top_rules = None
    summary = run(args)
    print(json.dumps(clean_json(summary), ensure_ascii=False, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
