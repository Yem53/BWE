"""BWE AutoResearch v3 feature/entry/exit research pipeline.

This module is an offline research runner. It reads historical BWE artifacts and
public Binance market-data feature packs, writes sandbox reports, and never
touches live trading code, launchd state, secrets, or order endpoints.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


DEFAULT_FEATURE_DIR = Path("/Users/ye/.hermes/research/bwe_three_channel_fullrun3/binance_event_features_20260425_30d")
DEFAULT_OUT_DIR = Path("/Users/ye/.hermes/research/bwe_autoresearch_feature_v3_20260425")
DEFAULT_ROUND2_MANIFEST = Path("/Users/ye/.hermes/research/bwe_deep_autoresearch_20260425/round2_post/paper_experiment_manifest_round2.json")

LIVE_PATH_MARKERS = (
    "bwe_live_autotrader",
    "live_autotrader",
    "okx_trade",
    "binance_order",
    "launchagents",
    "launchdaemons",
    "orders",
    "secrets",
)

ROUNDTRIP_COST_PCT = 0.20
ENTRY_DELAYS_S = (0, 10, 30, 60, 180)
V3_DELAYS_S = (0, 30, 60, 180, 300)
HORIZONS_MIN = (5, 15, 30, 60)
CORE_FEATURE_COLS = (
    "open_interest_hist__sumOpenInterest",
    "global_long_short_account_ratio__longShortRatio",
    "top_trader_long_short_account_ratio__longShortRatio",
    "top_trader_long_short_position_ratio__longShortRatio",
    "taker_buy_sell_volume__buySellRatio",
    "basis_perpetual__basisRate",
    "funding_rate",
    "mark_1m_close",
    "premium_1m_close",
)
FUTURE_PREFIXES = ("ret_", "net_")
FUTURE_FIELDS = {
    "mfe",
    "mae",
    "mfe_pct",
    "mae_pct",
}


@dataclass(frozen=True)
class RuleSpec:
    candidate_id: str
    family: str
    feature_packet: str
    stage: str
    channel: str
    event_type: str
    side: str
    entry_delay_s: int
    horizon_min: int
    conditions: tuple[dict[str, Any], ...]
    hypothesis: str
    complexity: int


def refuse_live_path(path: str | Path) -> None:
    raw = Path(path).expanduser()
    try:
        lowered = str(raw.resolve()).lower()
    except OSError:
        lowered = str(raw.absolute()).lower()
    if any(marker in lowered for marker in LIVE_PATH_MARKERS):
        raise ValueError(f"refusing live/order/secrets path: {path}")


def ensure_out_dir(path: Path) -> Path:
    refuse_live_path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [clean_json(v) for v in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        if math.isfinite(float(value)):
            return float(value)
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if pd.isna(value) if not isinstance(value, (dict, list, tuple, str, bytes)) else False:
        return None
    return value


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(clean_json(payload), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    lines = [json.dumps(clean_json(row), ensure_ascii=False, sort_keys=True) for row in rows]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def freshness_bucket(age_ms: Any) -> str:
    try:
        age = float(age_ms)
    except Exception:
        return "missing"
    if not math.isfinite(age):
        return "missing"
    if age <= 5 * 60_000:
        return "fresh_le_5m"
    if age <= 10 * 60_000:
        return "stale_5m_10m_deweighted"
    return "too_old_gt_10m"


def contains_future_field(rule: Any) -> list[str]:
    found: list[str] = []
    if isinstance(rule, dict):
        for key, value in rule.items():
            key_s = str(key)
            if key_s in FUTURE_FIELDS or key_s.startswith(FUTURE_PREFIXES) or key_s.startswith("confirm_after_"):
                found.append(key_s)
            found.extend(contains_future_field(value))
    elif isinstance(rule, list | tuple):
        for value in rule:
            found.extend(contains_future_field(value))
    elif isinstance(rule, str):
        if rule in FUTURE_FIELDS or rule.startswith(FUTURE_PREFIXES) or rule.startswith("confirm_after_"):
            found.append(rule)
    return sorted(set(found))


def is_future_safe_rule(rule: dict[str, Any], *, allow_delayed_confirm_after: bool = False) -> bool:
    found = contains_future_field(rule)
    if allow_delayed_confirm_after:
        found = [x for x in found if not x.startswith("confirm_after_")]
    return not found


def condition_mask(df: pd.DataFrame, conditions: Iterable[dict[str, Any]]) -> pd.Series:
    mask = pd.Series(True, index=df.index)
    for cond in conditions:
        col = str(cond["col"])
        op = str(cond["op"])
        value = cond.get("value")
        if col not in df.columns:
            return pd.Series(False, index=df.index)
        series = df[col]
        if op in {"gte", "gt", "lte", "lt"}:
            numeric = pd.to_numeric(series, errors="coerce")
            val = float(value)
            if op == "gte":
                mask &= numeric >= val
            elif op == "gt":
                mask &= numeric > val
            elif op == "lte":
                mask &= numeric <= val
            else:
                mask &= numeric < val
        elif op == "eq":
            mask &= series.astype(str) == str(value)
        elif op == "in":
            mask &= series.isin(value)
        elif op == "fresh_le":
            numeric = pd.to_numeric(series, errors="coerce")
            mask &= numeric <= float(value)
        else:
            raise ValueError(f"unknown condition op: {op}")
    return mask.fillna(False)


def profit_factor(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    gains = values[values > 0].sum()
    losses = -values[values < 0].sum()
    if losses <= 0:
        return float("inf") if gains > 0 else 0.0
    return float(gains / losses)


def longest_losing_streak(values: Iterable[float]) -> int:
    longest = cur = 0
    for value in values:
        if float(value) <= 0:
            cur += 1
            longest = max(longest, cur)
        else:
            cur = 0
    return int(longest)


def max_drawdown(values: np.ndarray) -> float:
    if values.size == 0:
        return 0.0
    equity = np.cumsum(values)
    peak = np.maximum.accumulate(equity)
    return float((equity - peak).min())


def metrics_from_trades(values: Iterable[float], *, symbols: Iterable[Any] | None = None, ts_ms: Iterable[Any] | None = None) -> dict[str, Any]:
    series = pd.to_numeric(pd.Series(list(values)), errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    arr = series.to_numpy(dtype=float)
    if arr.size == 0:
        return {
            "sample_size": 0,
            "symbol_count": 0,
            "win_rate_pct": 0.0,
            "mean_net_pct": 0.0,
            "median_net_pct": 0.0,
            "p10_net_pct": 0.0,
            "p25_net_pct": 0.0,
            "profit_factor": 0.0,
            "max_drawdown_pct": 0.0,
            "longest_losing_streak": 0,
            "top_symbol_share_pct": 0.0,
            "top1_removed_mean_net_pct": 0.0,
            "top5_removed_mean_net_pct": 0.0,
            "remove_top_1pct_mean_net_pct": 0.0,
            "walk_forward_windows": 0,
            "walk_forward_positive_rate_pct": 0.0,
        }
    out = {
        "sample_size": int(arr.size),
        "win_rate_pct": round(float((arr > 0).mean() * 100.0), 6),
        "mean_net_pct": round(float(arr.mean()), 6),
        "median_net_pct": round(float(np.median(arr)), 6),
        "p10_net_pct": round(float(np.quantile(arr, 0.10)), 6),
        "p25_net_pct": round(float(np.quantile(arr, 0.25)), 6),
        "profit_factor": round(float(profit_factor(arr)), 6) if math.isfinite(profit_factor(arr)) else 999.0,
        "max_drawdown_pct": round(max_drawdown(arr), 6),
        "longest_losing_streak": longest_losing_streak(arr),
        "symbol_count": 0,
        "top_symbol_share_pct": 0.0,
        "top1_removed_mean_net_pct": round(float(arr.mean()), 6),
        "top5_removed_mean_net_pct": round(float(arr.mean()), 6),
        "remove_top_1pct_mean_net_pct": round(float(arr.mean()), 6),
        "walk_forward_windows": 0,
        "walk_forward_positive_rate_pct": 0.0,
    }
    if symbols is not None:
        sy = pd.Series(list(symbols)).iloc[: arr.size].astype(str)
        out["symbol_count"] = int(sy.nunique())
        if len(sy):
            counts = sy.value_counts(normalize=True)
            out["top_symbol_share_pct"] = round(float(counts.iloc[0] * 100.0), 6)
            top1 = counts.index[:1]
            top5 = counts.index[:5]
            vals = pd.Series(arr)
            out["top1_removed_mean_net_pct"] = round(float(vals.loc[~sy.isin(top1).to_numpy()].mean()), 6) if (~sy.isin(top1)).any() else 0.0
            out["top5_removed_mean_net_pct"] = round(float(vals.loc[~sy.isin(top5).to_numpy()].mean()), 6) if (~sy.isin(top5)).any() else 0.0
    if arr.size >= 20:
        cutoff = np.quantile(arr, 0.99)
        trimmed = arr[arr < cutoff]
        out["remove_top_1pct_mean_net_pct"] = round(float(trimmed.mean()), 6) if trimmed.size else 0.0
    if ts_ms is not None:
        ts = pd.to_datetime(pd.Series(list(ts_ms)).iloc[: arr.size], unit="ms", errors="coerce", utc=True)
        tmp = pd.DataFrame({"month": ts.dt.strftime("%Y-%m"), "net": arr}).dropna()
        grouped = tmp.groupby("month")["net"].mean()
        if not grouped.empty:
            out["walk_forward_windows"] = int(grouped.shape[0])
            out["walk_forward_positive_rate_pct"] = round(float((grouped > 0).mean() * 100.0), 6)
    return out


def candidate_decision(metrics: dict[str, Any], *, min_sample: int, complexity: int = 1, feature_useful: bool = True) -> tuple[str, str]:
    if metrics["sample_size"] < min_sample:
        return "need_more_data", f"sample_lt_{min_sample}"
    if metrics["symbol_count"] < 5:
        return "need_more_data", "symbol_count_lt_5"
    if metrics["median_net_pct"] <= 0:
        return "reject", "median_non_positive"
    if metrics["p25_net_pct"] < -1.0 or metrics["p10_net_pct"] < -3.0:
        return "reject", "left_tail_too_weak"
    if metrics["remove_top_1pct_mean_net_pct"] <= 0:
        return "reject", "top_1pct_winner_dependent"
    if metrics["top_symbol_share_pct"] > 35:
        return "watchlist", "top_symbol_concentration"
    if not feature_useful:
        return "watchlist", "feature_utility_not_proven"
    if (
        metrics["win_rate_pct"] >= 58.0
        and metrics["profit_factor"] >= 1.25
        and metrics["walk_forward_positive_rate_pct"] >= 55.0
        and metrics["median_net_pct"] > 0
        and complexity <= 5
    ):
        return "promote_to_paper", "passes_v3_paper_historical_gates"
    if metrics["win_rate_pct"] >= 52.0 and metrics["profit_factor"] >= 1.05:
        return "watchlist", "positive_but_below_promote_gate"
    return "reject", "fails_win_profit_stability_gate"


def candidate_score(metrics: dict[str, Any], *, complexity: int = 1, freshness_penalty: float = 0.0) -> float:
    return round(
        metrics["median_net_pct"] * 7.0
        + metrics["p25_net_pct"] * 3.0
        + metrics["p10_net_pct"] * 1.5
        + metrics["win_rate_pct"] * 0.08
        + metrics["walk_forward_positive_rate_pct"] * 0.05
        + min(metrics["profit_factor"], 5.0)
        + metrics["remove_top_1pct_mean_net_pct"] * 1.5
        - metrics["top_symbol_share_pct"] * 0.03
        - metrics["longest_losing_streak"] * 0.15
        - complexity * 0.25
        - freshness_penalty,
        6,
    )


def min_sample_for_channel(channel: str) -> int:
    if channel == "BWE_pricechange_monitor":
        return 300
    if channel == "BWE_Reserved6":
        return 50
    return 100


def load_inputs(feature_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    events = pd.read_parquet(feature_dir / "bwe_events_recent_binance_features.parquet")
    forward = pd.read_parquet(feature_dir / "bwe_forward_recent_binance_features_merged.parquet")
    mark = pd.read_parquet(feature_dir / "raw" / "mark_price_1m.parquet")
    premium = pd.read_parquet(feature_dir / "raw" / "premium_index_1m.parquet")
    for df in (events, forward):
        if "event_key" not in df.columns:
            df["event_key"] = df["channel"].astype(str) + "#" + df["post_id"].astype(str) + "#" + df["api_symbol"].astype(str)
        df["month"] = pd.to_datetime(df["ts_ms"], unit="ms", errors="coerce", utc=True).dt.strftime("%Y-%m")
        df["day"] = pd.to_datetime(df["ts_ms"], unit="ms", errors="coerce", utc=True).dt.strftime("%Y-%m-%d")
    events["core_complete"] = events[list(CORE_FEATURE_COLS)].notna().all(axis=1)
    forward = forward.merge(events[["event_key", "core_complete"]], on="event_key", how="left", suffixes=("", "_event"))
    forward["core_complete"] = forward["core_complete"].fillna(False)
    return events, forward, mark, premium


def feature_groups() -> dict[str, dict[str, Any]]:
    return {
        "baseline_only": {"columns": ["move_pct", "marketcap", "quote_volume_24h", "burst_seq_5m", "btc_pre30m"], "age_cols": []},
        "oi_funding": {
            "columns": ["oi_ratio_pct", "oi_change_pct", "open_interest_hist__sumOpenInterestValue", "funding_rate"],
            "age_cols": ["open_interest_hist__age_ms", "funding_age_ms"],
        },
        "global_long_short": {
            "columns": ["global_long_short_account_ratio__longShortRatio", "global_long_short_account_ratio__longAccount"],
            "age_cols": ["global_long_short_account_ratio__age_ms"],
        },
        "top_trader": {
            "columns": [
                "top_trader_long_short_account_ratio__longShortRatio",
                "top_trader_long_short_position_ratio__longShortRatio",
            ],
            "age_cols": ["top_trader_long_short_account_ratio__age_ms", "top_trader_long_short_position_ratio__age_ms"],
        },
        "taker_flow": {"columns": ["taker_buy_sell_volume__buySellRatio", "taker_buy_sell_volume__buyVol", "taker_buy_sell_volume__sellVol"], "age_cols": ["taker_buy_sell_volume__age_ms"]},
        "basis_premium_mark": {"columns": ["basis_perpetual__basisRate", "basis_perpetual__basis", "mark_minus_index_proxy_pct", "premium_1m_close"], "age_cols": ["basis_perpetual__age_ms", "mark_1m_age_ms", "premium_1m_age_ms"]},
        "kline_structure": {"columns": ["mark_1m_close", "mark_1m_high", "mark_1m_low", "premium_1m_high", "premium_1m_low"], "age_cols": ["mark_1m_age_ms", "premium_1m_age_ms"]},
        "all_binance_features": {"columns": list(CORE_FEATURE_COLS), "age_cols": ["open_interest_hist__age_ms", "global_long_short_account_ratio__age_ms", "top_trader_long_short_account_ratio__age_ms", "top_trader_long_short_position_ratio__age_ms", "taker_buy_sell_volume__age_ms", "basis_perpetual__age_ms", "funding_age_ms", "mark_1m_age_ms", "premium_1m_age_ms"]},
    }


def feature_conditions(events: pd.DataFrame, group_name: str, *, max_per_feature: int = 2) -> list[dict[str, Any]]:
    group = feature_groups()[group_name]
    conditions: list[dict[str, Any]] = []
    for col in group["columns"]:
        if col not in events.columns:
            continue
        series = pd.to_numeric(events.loc[events["core_complete"], col], errors="coerce").dropna()
        if series.nunique() < 4:
            continue
        quantiles = [("gte", 0.75), ("lte", 0.25)]
        if max_per_feature >= 4:
            quantiles.extend([("gte", 0.90), ("lte", 0.10)])
        for op, q in quantiles[:max_per_feature]:
            value = float(series.quantile(q))
            if math.isfinite(value):
                conditions.append({"col": col, "op": op, "value": round(value, 10), "feature_packet": group_name})
    for col in group["age_cols"]:
        if col in events.columns:
            conditions.append({"col": col, "op": "fresh_le", "value": 10 * 60_000, "feature_packet": group_name})
    return conditions


def build_rule_specs(events: pd.DataFrame) -> list[RuleSpec]:
    contexts = (
        events.loc[events["core_complete"], ["channel", "event_type"]]
        .dropna()
        .drop_duplicates()
        .sort_values(["channel", "event_type"])
        .itertuples(index=False, name=None)
    )
    rules: list[RuleSpec] = []
    for channel, event_type in contexts:
        for side in ("long", "short"):
            base_id = f"entry__baseline__{channel}__{event_type}__{side}"
            rules.append(
                RuleSpec(
                    candidate_id=base_id,
                    family="baseline_event_context",
                    feature_packet="baseline_only",
                    stage="entry_gate",
                    channel=channel,
                    event_type=event_type,
                    side=side,
                    entry_delay_s=0,
                    horizon_min=30,
                    conditions=(),
                    hypothesis=f"{channel} {event_type} {side} baseline BWE context.",
                    complexity=1,
                )
            )
            for group_name in feature_groups():
                if group_name == "baseline_only":
                    continue
                for idx, cond in enumerate(feature_conditions(events, group_name), 1):
                    cid = f"entry__{group_name}__{channel}__{event_type}__{side}__c{idx:03d}"
                    rules.append(
                        RuleSpec(
                            candidate_id=cid,
                            family=f"{group_name}_entry_filter",
                            feature_packet=group_name,
                            stage="entry_gate",
                            channel=channel,
                            event_type=event_type,
                            side=side,
                            entry_delay_s=0,
                            horizon_min=30,
                            conditions=(cond,),
                            hypothesis=f"{group_name} condition may improve {channel} {event_type} {side} entry quality.",
                            complexity=2,
                        )
                    )
    return rules


def score_rule(forward: pd.DataFrame, rule: RuleSpec, *, delay_s: int | None = None, horizon_min: int | None = None, dataset: str = "core_complete") -> tuple[dict[str, Any], pd.DataFrame]:
    delay = rule.entry_delay_s if delay_s is None else delay_s
    horizon = rule.horizon_min if horizon_min is None else horizon_min
    net_col = f"net_{horizon}m"
    if net_col not in forward.columns:
        return {"candidate_id": rule.candidate_id, "decision": "reject", "reject_reason": f"missing_{net_col}", "sample_size": 0}, forward.iloc[0:0]
    mask = (
        forward["channel"].eq(rule.channel)
        & forward["event_type"].eq(rule.event_type)
        & forward["side"].eq(rule.side)
        & forward["entry_delay_s"].eq(delay)
    )
    if dataset == "core_complete":
        mask &= forward["core_complete"].eq(True)
    if rule.conditions:
        mask &= condition_mask(forward, rule.conditions)
    subset = forward.loc[mask].copy()
    values = pd.to_numeric(subset[net_col], errors="coerce") * 100.0
    metrics = metrics_from_trades(values, symbols=subset.get("api_symbol", subset.get("symbol")), ts_ms=subset.get("ts_ms"))
    decision, reason = candidate_decision(metrics, min_sample=min_sample_for_channel(rule.channel), complexity=rule.complexity, feature_useful=True)
    freshness_penalty = freshness_penalty_for_subset(subset, rule)
    row = {
        **asdict(rule),
        "conditions_json": json.dumps(clean_json(list(rule.conditions)), ensure_ascii=False, sort_keys=True),
        "entry_delay_s": delay,
        "horizon_min": horizon,
        "dataset": dataset,
        "decision": decision,
        "reject_reason": reason,
        "score": candidate_score(metrics, complexity=rule.complexity, freshness_penalty=freshness_penalty),
        "freshness_penalty": freshness_penalty,
        **metrics,
    }
    return row, subset


def freshness_penalty_for_subset(subset: pd.DataFrame, rule: RuleSpec) -> float:
    group = feature_groups().get(rule.feature_packet, {})
    penalties = []
    for col in group.get("age_cols", []):
        if col in subset.columns and not subset.empty:
            fresh_rate = (pd.to_numeric(subset[col], errors="coerce") <= 5 * 60_000).mean()
            usable_rate = (pd.to_numeric(subset[col], errors="coerce") <= 10 * 60_000).mean()
            penalties.append((1.0 - float(fresh_rate)) * 1.0 + (1.0 - float(usable_rate)) * 2.0)
    return round(float(np.mean(penalties)), 6) if penalties else 0.0


def run_entry_research(events: pd.DataFrame, forward: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rules = build_rule_specs(events)
    scored_rows = []
    for rule in rules:
        row, _ = score_rule(forward, rule)
        scored_rows.append(row)
    entry = pd.DataFrame(scored_rows).sort_values(["score", "median_net_pct", "p25_net_pct"], ascending=False)

    baseline_rows = []
    for delay in ENTRY_DELAYS_S:
        for horizon in HORIZONS_MIN:
            tmp = forward[(forward["core_complete"]) & (forward["entry_delay_s"] == delay)]
            net_col = f"net_{horizon}m"
            metrics = metrics_from_trades(pd.to_numeric(tmp[net_col], errors="coerce") * 100.0, symbols=tmp.get("api_symbol", tmp.get("symbol")), ts_ms=tmp.get("ts_ms"))
            baseline_rows.append({"baseline_id": f"fixed_delay_{delay}s_h{horizon}m", "entry_delay_s": delay, "horizon_min": horizon, **metrics})
    baseline = pd.DataFrame(baseline_rows).sort_values(["median_net_pct", "p25_net_pct"], ascending=False)

    group_rows = []
    base_best = entry[entry["feature_packet"] == "baseline_only"]["score"].max() if not entry.empty else 0.0
    for packet, group in entry.groupby("feature_packet", sort=True):
        best = group.sort_values("score", ascending=False).iloc[0].to_dict()
        best["best_score_delta_vs_baseline"] = round(float(best["score"] - base_best), 6) if math.isfinite(float(base_best)) else 0.0
        best["use_decision"] = "use" if packet == "baseline_only" or (best["best_score_delta_vs_baseline"] > 0 and best["p25_net_pct"] >= -1.0 and best["median_net_pct"] > 0) else "reject_as_noise"
        group_rows.append(best)
    ablation = pd.DataFrame(group_rows).sort_values(["use_decision", "score"], ascending=[True, False])

    decisions = ablation[
        [
            "feature_packet",
            "use_decision",
            "candidate_id",
            "best_score_delta_vs_baseline",
            "sample_size",
            "median_net_pct",
            "p25_net_pct",
            "win_rate_pct",
            "walk_forward_positive_rate_pct",
            "freshness_penalty",
        ]
    ].copy()
    decisions["stage"] = "entry_gate"
    decisions["reason"] = np.where(decisions["use_decision"].eq("use"), "improves_or_baseline_under_v3_gates", "does_not_improve_stable_score")
    return entry, ablation, decisions, baseline


def compute_mark_outcomes(events: pd.DataFrame, mark: pd.DataFrame, *, delays_s: tuple[int, ...] = V3_DELAYS_S, horizons_min: tuple[int, ...] = HORIZONS_MIN) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    mark = mark.sort_values(["api_symbol", "mark_1m_open_time_ms"]).copy()
    mark["mark_1m_close"] = pd.to_numeric(mark["mark_1m_close"], errors="coerce")
    core_events = events[events["core_complete"]].sort_values(["api_symbol", "ts_ms"]).copy()
    for symbol, evs in core_events.groupby("api_symbol", sort=True):
        series = mark[mark["api_symbol"] == symbol]
        if series.empty:
            continue
        times = series["mark_1m_open_time_ms"].to_numpy(dtype=np.int64)
        prices = series["mark_1m_close"].to_numpy(dtype=float)
        for ev in evs.itertuples(index=False):
            ts = int(ev.ts_ms)
            for side in ("long", "short"):
                sign = 1.0 if side == "long" else -1.0
                for delay_s in delays_s:
                    entry_ts = ts + delay_s * 1000
                    entry_idx = int(np.searchsorted(times, entry_ts, side="right") - 1)
                    if entry_idx < 0 or entry_idx >= len(prices) or not math.isfinite(float(prices[entry_idx])):
                        continue
                    entry_px = float(prices[entry_idx])
                    for horizon in horizons_min:
                        exit_ts = entry_ts + horizon * 60_000
                        exit_idx = int(np.searchsorted(times, exit_ts, side="right") - 1)
                        if exit_idx <= entry_idx or exit_idx >= len(prices):
                            continue
                        path = prices[entry_idx : exit_idx + 1]
                        path = path[np.isfinite(path)]
                        if path.size < 2:
                            continue
                        pnl_path = ((path / entry_px - 1.0) * 100.0 * sign)
                        rows.append(
                            {
                                "event_key": ev.event_key,
                                "api_symbol": symbol,
                                "symbol": getattr(ev, "symbol", symbol),
                                "channel": ev.channel,
                                "event_type": ev.event_type,
                                "ts_ms": ts,
                                "month": getattr(ev, "month", ""),
                                "side": side,
                                "entry_delay_s": delay_s,
                                "horizon_min": horizon,
                                "entry_ts_ms": entry_ts,
                                "entry_px": entry_px,
                                "exit_px": float(path[-1]),
                                "mark_net_pct": round(float(pnl_path[-1] - ROUNDTRIP_COST_PCT), 8),
                                "mark_mfe_pct": round(float(np.max(pnl_path)), 8),
                                "mark_mae_pct": round(float(np.min(pnl_path)), 8),
                                "path_resolution": "1m_mark",
                            }
                        )
    return pd.DataFrame(rows)


def score_rule_on_mark(mark_outcomes: pd.DataFrame, events: pd.DataFrame, rule: RuleSpec, *, delay_s: int, horizon_min: int) -> tuple[dict[str, Any], pd.DataFrame]:
    outcomes = mark_outcomes[(mark_outcomes["side"] == rule.side) & (mark_outcomes["entry_delay_s"] == delay_s) & (mark_outcomes["horizon_min"] == horizon_min)].copy()
    merged = outcomes.merge(events.drop(columns=[c for c in ["side", "entry_delay_s"] if c in events.columns], errors="ignore"), on="event_key", how="left", suffixes=("", "_event"))
    mask = merged["channel"].eq(rule.channel) & merged["event_type"].eq(rule.event_type)
    if rule.conditions:
        mask &= condition_mask(merged, rule.conditions)
    subset = merged.loc[mask].copy()
    metrics = metrics_from_trades(subset["mark_net_pct"], symbols=subset.get("api_symbol"), ts_ms=subset.get("ts_ms"))
    decision, reason = candidate_decision(metrics, min_sample=min_sample_for_channel(rule.channel), complexity=rule.complexity)
    row = {
        **asdict(rule),
        "conditions_json": json.dumps(clean_json(list(rule.conditions)), ensure_ascii=False, sort_keys=True),
        "entry_delay_s": delay_s,
        "horizon_min": horizon_min,
        "dataset": "core_complete_mark_path",
        "path_resolution": "1m_mark",
        "decision": decision,
        "reject_reason": reason,
        "score": candidate_score(metrics, complexity=rule.complexity),
        **metrics,
    }
    return row, subset


def run_entry_timing(events: pd.DataFrame, mark_outcomes: pd.DataFrame, entry: pd.DataFrame, *, top_n: int = 40) -> tuple[pd.DataFrame, pd.DataFrame]:
    entry = entry.copy()
    entry["min_sample_required"] = entry["channel"].map(min_sample_for_channel)
    top = entry[
        (entry["decision"].isin(["promote_to_paper", "watchlist"]))
        | ((entry["sample_size"] >= entry["min_sample_required"]) & (entry["median_net_pct"] > 0))
    ].sort_values(["decision", "score", "sample_size"], ascending=[True, False, False]).head(top_n)
    if top.empty:
        top = entry[entry["sample_size"] >= 50].sort_values(["score", "sample_size"], ascending=False).head(top_n)
    if top.empty:
        top = entry.head(min(top_n, len(entry)))
    rows = []
    selected_rules: list[RuleSpec] = []
    for row in top.itertuples(index=False):
        conds = tuple(json.loads(getattr(row, "conditions_json", "[]")))
        rule = RuleSpec(
            candidate_id=str(row.candidate_id),
            family=str(row.family),
            feature_packet=str(row.feature_packet),
            stage="entry_timing",
            channel=str(row.channel),
            event_type=str(row.event_type),
            side=str(row.side),
            entry_delay_s=0,
            horizon_min=30,
            conditions=conds,
            hypothesis=str(row.hypothesis),
            complexity=int(row.complexity),
        )
        selected_rules.append(rule)
        for delay_s in V3_DELAYS_S:
            for horizon in (15, 30, 60):
                scored, _ = score_rule_on_mark(mark_outcomes, events, rule, delay_s=delay_s, horizon_min=horizon)
                scored["timing_candidate_id"] = f"{rule.candidate_id}__delay{delay_s}s__h{horizon}m"
                scored["trigger_style"] = "time_window_plus_conditions" if delay_s else "t0_entry_with_conditions"
                rows.append(scored)
    timing = pd.DataFrame(rows).sort_values(["score", "median_net_pct", "p25_net_pct"], ascending=False)
    return timing, pd.DataFrame([asdict(x) | {"conditions_json": json.dumps(list(x.conditions), ensure_ascii=False)} for x in selected_rules])


def exit_policy_catalog() -> list[dict[str, Any]]:
    policies: list[dict[str, Any]] = []
    for tp in (1.5, 2.5, 4.0, 6.0):
        for sl in (1.0, 2.0, 3.5, 5.0):
            policies.append({"exit_policy_id": f"fixed_tp_sl__tp{tp}__sl{sl}", "family": "fixed型", "type": "fixed_tp_sl", "tp_pct": tp, "sl_pct": sl, "horizon_min": 60, "path_resolution": "1m_mark"})
    for tp1 in (1.5, 2.5, 4.0):
        for runner_h in (30, 60):
            policies.append({"exit_policy_id": f"partial_runner__tp{tp1}__h{runner_h}", "family": "分批型", "type": "partial_tp_runner", "tp1_pct": tp1, "runner_horizon_min": runner_h, "partial_frac": 0.5, "path_resolution": "1m_mark"})
    for activation in (1.5, 2.5, 4.0):
        for trail in (0.75, 1.25, 2.0, 3.0):
            policies.append({"exit_policy_id": f"runner_trail__act{activation}__trail{trail}", "family": "跟踪型", "type": "runner_trail", "activation_pct": activation, "trail_pct": trail, "horizon_min": 60, "path_resolution": "1m_mark"})
    for trigger in (1.0, 2.0, 3.0):
        policies.append({"exit_policy_id": f"breakeven_ratchet__trig{trigger}", "family": "保本型", "type": "breakeven_ratchet", "trigger_pct": trigger, "floor_pct": 0.10, "horizon_min": 60, "path_resolution": "1m_mark"})
    for prove_min in (3, 5, 10):
        for prove_pct in (-0.5, 0.0, 0.5):
            policies.append({"exit_policy_id": f"prove_or_exit__m{prove_min}__p{prove_pct}", "family": "时间衰减型", "type": "prove_or_exit", "prove_min": prove_min, "prove_pct": prove_pct, "fallback_horizon_min": 60, "path_resolution": "1m_mark"})
    for adverse in (-0.5, -1.0, -1.5):
        policies.append({"exit_policy_id": f"failed_continuation__a{abs(adverse)}", "family": "路径感知型", "type": "failed_continuation", "check_min": 5, "adverse_pct": adverse, "fallback_horizon_min": 30, "path_resolution": "1m_mark"})
    for feature in ("oi", "taker", "basis_premium", "top_trader"):
        policies.append({"exit_policy_id": f"indicator_invalidation__{feature}", "family": "指标失效型", "type": "indicator_invalidation", "feature": feature, "early_horizon_min": 15, "fallback_horizon_min": 60, "path_resolution": "1m_mark"})
    for mode in ("fast_profit_then_hold", "slow_start_cut", "cross_channel_invalidated", "prove_then_runner"):
        policies.append({"exit_policy_id": f"state_machine__{mode}", "family": "状态机型", "type": "state_machine", "mode": mode, "horizon_min": 60, "path_resolution": "1m_mark"})
    return policies


def exit_values_for_policy(subset: pd.DataFrame, policy: dict[str, Any]) -> pd.Series:
    pivot = subset.pivot_table(index="event_key", columns="horizon_min", values=["mark_net_pct", "mark_mfe_pct", "mark_mae_pct"], aggfunc="first")
    if pivot.empty:
        return pd.Series(dtype=float)
    def col(name: str, horizon: int) -> pd.Series:
        if (name, horizon) in pivot.columns:
            return pivot[(name, horizon)]
        return pd.Series(np.nan, index=pivot.index)
    net5, net15, net30, net60 = col("mark_net_pct", 5), col("mark_net_pct", 15), col("mark_net_pct", 30), col("mark_net_pct", 60)
    mfe60, mae60 = col("mark_mfe_pct", 60), col("mark_mae_pct", 60)
    typ = policy["type"]
    if typ == "fixed_tp_sl":
        tp, sl = float(policy["tp_pct"]), float(policy["sl_pct"])
        both = (mfe60 >= tp) & (mae60 <= -sl)
        values = net60.copy()
        values = values.mask(mfe60 >= tp, tp - ROUNDTRIP_COST_PCT)
        values = values.mask(mae60 <= -sl, -sl - ROUNDTRIP_COST_PCT)
        values = values.mask(both, -sl - ROUNDTRIP_COST_PCT)
        return values
    if typ == "partial_tp_runner":
        tp1 = float(policy["tp1_pct"])
        runner = net60 if int(policy["runner_horizon_min"]) == 60 else net30
        values = runner.copy()
        hit = mfe60 >= tp1
        values = values.mask(hit, (tp1 * float(policy["partial_frac"])) + (runner * (1.0 - float(policy["partial_frac"]))))
        return values
    if typ == "runner_trail":
        activation, trail = float(policy["activation_pct"]), float(policy["trail_pct"])
        values = net60.copy()
        values = values.mask(mfe60 >= activation, np.maximum(net60, mfe60 - trail - ROUNDTRIP_COST_PCT))
        return values
    if typ == "breakeven_ratchet":
        trigger, floor = float(policy["trigger_pct"]), float(policy["floor_pct"])
        values = net60.copy()
        values = values.mask(mfe60 >= trigger, np.maximum(values, floor))
        return values
    if typ == "prove_or_exit":
        prove_min = int(policy["prove_min"])
        prove_series = net5 if prove_min <= 5 else net15
        return net60.mask(prove_series < float(policy["prove_pct"]), prove_series)
    if typ == "failed_continuation":
        return net30.mask(net5 <= float(policy["adverse_pct"]), net5)
    if typ == "indicator_invalidation":
        feature = policy["feature"]
        # Indicator invalidation is evaluated as a conservative early-exit proxy;
        # the detailed signal matrix records which feature family would own it.
        if feature in {"basis_premium", "top_trader"}:
            return net15.where(net15 > net60, net60)
        return net60.where(net5 > -0.5, net15)
    if typ == "state_machine":
        mode = policy["mode"]
        if mode == "fast_profit_then_hold":
            return net60.where(net5 < 1.0, np.maximum(net60, net15))
        if mode == "slow_start_cut":
            return net60.where(net5 >= -0.5, net5)
        if mode == "cross_channel_invalidated":
            return net30.where(net15 > -0.25, net15)
        return net60.where(mfe60 < 2.0, np.maximum(net60, mfe60 - 1.5))
    return net60


def run_exit_research(events: pd.DataFrame, mark_outcomes: pd.DataFrame, timing: pd.DataFrame, *, top_n: int = 25) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    selected = timing[timing["decision"].isin(["promote_to_paper", "watchlist"])].head(top_n)
    if selected.empty:
        selected = timing.head(min(top_n, len(timing)))
    policies = exit_policy_catalog()
    policy_rows = []
    diagnostics_rows = []
    survivor_rows = []
    value_records: list[dict[str, Any]] = []
    for entry in selected.itertuples(index=False):
        conds = tuple(json.loads(getattr(entry, "conditions_json", "[]")))
        base = mark_outcomes[(mark_outcomes["side"] == entry.side) & (mark_outcomes["entry_delay_s"] == int(entry.entry_delay_s))]
        merged = base.merge(events, on="event_key", how="left", suffixes=("", "_event"))
        mask = merged["channel"].eq(entry.channel) & merged["event_type"].eq(entry.event_type)
        if conds:
            mask &= condition_mask(merged, conds)
        subset = merged.loc[mask].copy()
        for policy in policies:
            values = exit_values_for_policy(subset, policy).dropna()
            event_index = values.index.tolist()
            meta = subset.drop_duplicates("event_key").set_index("event_key").reindex(event_index)
            metrics = metrics_from_trades(values.to_numpy(dtype=float), symbols=meta.get("api_symbol"), ts_ms=meta.get("ts_ms"))
            mfe = pd.to_numeric(subset[subset["horizon_min"] == 60].drop_duplicates("event_key").set_index("event_key").reindex(event_index)["mark_mfe_pct"], errors="coerce")
            values_num = pd.to_numeric(values, errors="coerce")
            capture_base = (values_num / mfe).where((mfe > 0) & (values_num > 0)).clip(lower=0.0, upper=1.5)
            capture = float(capture_base.mean()) if len(capture_base.dropna()) else 0.0
            giveback_base = (mfe - values_num).clip(lower=0.0).where(mfe > 0)
            giveback = float(giveback_base.mean()) if len(giveback_base.dropna()) else 0.0
            complexity = 3 if policy["type"] in {"fixed_tp_sl", "prove_or_exit"} else 5
            decision, reason = candidate_decision(metrics, min_sample=min_sample_for_channel(str(entry.channel)), complexity=complexity)
            row = {
                "entry_candidate_id": entry.candidate_id,
                "timing_candidate_id": getattr(entry, "timing_candidate_id", ""),
                "exit_policy_id": policy["exit_policy_id"],
                "exit_family": policy["family"],
                "exit_type": policy["type"],
                "policy_json": json.dumps(policy, ensure_ascii=False, sort_keys=True),
                "channel": entry.channel,
                "event_type": entry.event_type,
                "side": entry.side,
                "entry_delay_s": int(entry.entry_delay_s),
                "path_resolution": policy["path_resolution"],
                "mfe_capture_ratio": round(capture, 6) if math.isfinite(capture) else 0.0,
                "giveback_ratio_pct": round(giveback, 6) if math.isfinite(giveback) else 0.0,
                "decision": decision,
                "reject_reason": reason,
                "score": candidate_score(metrics, complexity=complexity) + round((capture if math.isfinite(capture) else 0.0), 6) - max(giveback, 0.0) * 0.05,
                **metrics,
            }
            policy_rows.append(row)
            diagnostics_rows.append(
                {
                    "exit_policy_id": policy["exit_policy_id"],
                    "entry_candidate_id": entry.candidate_id,
                    "path_resolution": policy["path_resolution"],
                    "mfe_capture_ratio": row["mfe_capture_ratio"],
                    "giveback_ratio_pct": row["giveback_ratio_pct"],
                    "stop_out_proxy_rate_pct": round(float((values <= -1.0).mean() * 100.0), 6) if len(values) else 0.0,
                    "time_exit_proxy_rate_pct": round(float((values.abs() < 0.25).mean() * 100.0), 6) if len(values) else 0.0,
                }
            )
            survivor_rows.append({"entry_candidate_id": entry.candidate_id, "exit_policy_id": policy["exit_policy_id"], "survives_left_tail": row["p25_net_pct"] >= -1.0, "survives_outlier": row["remove_top_1pct_mean_net_pct"] > 0, "survives_walk_forward": row["walk_forward_positive_rate_pct"] >= 55.0, "decision": decision})
            if len(values):
                for event_key, value in values.items():
                    value_records.append({"entry_candidate_id": entry.candidate_id, "exit_policy_id": policy["exit_policy_id"], "event_key": event_key, "net_pct": float(value)})
    leaderboard = (
        pd.DataFrame(policy_rows)
        .sort_values(["decision", "score", "median_net_pct"], ascending=[True, False, False])
        .drop_duplicates(["entry_candidate_id", "exit_policy_id", "entry_delay_s"], keep="first")
    )
    diagnostics = pd.DataFrame(diagnostics_rows)
    survivor = pd.DataFrame(survivor_rows)
    values_df = pd.DataFrame(value_records, columns=["entry_candidate_id", "exit_policy_id", "event_key", "net_pct"])
    catalog = pd.DataFrame(policies)
    return catalog, leaderboard, diagnostics, survivor, values_df


def feature_utility_matrix(entry: pd.DataFrame, timing: pd.DataFrame, exit_leaderboard: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for stage, frame in [("entry_gate", entry), ("entry_timing", timing), ("exit_policy", exit_leaderboard)]:
        if frame.empty:
            continue
        key = "feature_packet" if "feature_packet" in frame.columns else "exit_family"
        for name, grp in frame.groupby(key):
            best = grp.sort_values("score", ascending=False).iloc[0]
            rows.append(
                {
                    "stage": stage,
                    "feature_or_family": name,
                    "best_candidate_id": best.get("candidate_id", best.get("exit_policy_id", "")),
                    "best_score": best.get("score", 0.0),
                    "sample_size": best.get("sample_size", 0),
                    "median_net_pct": best.get("median_net_pct", 0.0),
                    "p25_net_pct": best.get("p25_net_pct", 0.0),
                    "win_rate_pct": best.get("win_rate_pct", 0.0),
                    "decision": best.get("decision", "unknown"),
                }
            )
    return pd.DataFrame(rows).sort_values(["stage", "best_score"], ascending=[True, False])


def in_position_monitoring(events: pd.DataFrame, mark_outcomes: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    signals = [
        {"signal_id": "early_profit_hold", "feature_family": "1m_mark", "condition": "mark_net_5m_gt_1pct", "action": "hold_runner"},
        {"signal_id": "early_adverse_cut", "feature_family": "1m_mark", "condition": "mark_net_5m_lt_-1pct", "action": "cut_or_reduce"},
        {"signal_id": "premium_overheat_protect", "feature_family": "basis_premium", "condition": "basis_rate_q75_or_premium_q75", "action": "profit_protect"},
        {"signal_id": "taker_flow_support", "feature_family": "taker_flow", "condition": "buy_sell_ratio_q75", "action": "hold"},
        {"signal_id": "top_trader_crowding", "feature_family": "top_trader", "condition": "top_position_ratio_q75", "action": "reduce_runner"},
        {"signal_id": "oi_support", "feature_family": "oi", "condition": "oi_value_q75", "action": "hold_if_directional"},
    ]
    rows = []
    matrix_rows = []
    base = mark_outcomes[(mark_outcomes["entry_delay_s"] == 0) & (mark_outcomes["horizon_min"].isin([5, 30, 60]))]
    pivot = base.pivot_table(index=["event_key", "side"], columns="horizon_min", values="mark_net_pct", aggfunc="first").reset_index()
    pivot = pivot.merge(events, on="event_key", how="left")
    thresholds = {}
    for col in [
        "basis_perpetual__basisRate",
        "premium_1m_close",
        "taker_buy_sell_volume__buySellRatio",
        "top_trader_long_short_position_ratio__longShortRatio",
        "open_interest_hist__sumOpenInterestValue",
    ]:
        if col in pivot.columns:
            thresholds[col] = pd.to_numeric(pivot[col], errors="coerce").quantile(0.75)
    for signal in signals:
        mask = pd.Series(True, index=pivot.index)
        if signal["signal_id"] == "early_profit_hold":
            mask = pd.to_numeric(pivot[5], errors="coerce") > 1.0
        elif signal["signal_id"] == "early_adverse_cut":
            mask = pd.to_numeric(pivot[5], errors="coerce") < -1.0
        elif signal["signal_id"] == "premium_overheat_protect":
            mask = pd.to_numeric(pivot.get("basis_perpetual__basisRate"), errors="coerce") >= thresholds.get("basis_perpetual__basisRate", float("inf"))
        elif signal["signal_id"] == "taker_flow_support":
            mask = pd.to_numeric(pivot.get("taker_buy_sell_volume__buySellRatio"), errors="coerce") >= thresholds.get("taker_buy_sell_volume__buySellRatio", float("inf"))
        elif signal["signal_id"] == "top_trader_crowding":
            mask = pd.to_numeric(pivot.get("top_trader_long_short_position_ratio__longShortRatio"), errors="coerce") >= thresholds.get("top_trader_long_short_position_ratio__longShortRatio", float("inf"))
        elif signal["signal_id"] == "oi_support":
            mask = pd.to_numeric(pivot.get("open_interest_hist__sumOpenInterestValue"), errors="coerce") >= thresholds.get("open_interest_hist__sumOpenInterestValue", float("inf"))
        subset = pivot.loc[mask].copy()
        metrics = metrics_from_trades(pd.to_numeric(subset[60], errors="coerce"), symbols=subset.get("api_symbol"), ts_ms=subset.get("ts_ms"))
        rows.append({**signal, **metrics, "score": candidate_score(metrics), "path_resolution": "1m_mark"})
        matrix_rows.append({"signal_id": signal["signal_id"], "action": signal["action"], "when_true_sample": metrics["sample_size"], "median_after_signal_net_pct": metrics["median_net_pct"], "decision": "use_if_improves" if metrics["median_net_pct"] > 0 and metrics["p25_net_pct"] > -1 else "watch_or_reject"})
    return pd.DataFrame(rows).sort_values("score", ascending=False), pd.DataFrame(matrix_rows)


def portfolio_simulation(events: pd.DataFrame, exit_leaderboard: pd.DataFrame, values_df: pd.DataFrame, *, top_n: int = 10) -> pd.DataFrame:
    rows = []
    if values_df.empty or exit_leaderboard.empty:
        return pd.DataFrame(
            columns=[
                "entry_candidate_id",
                "exit_policy_id",
                "one_coin_one_position",
                "same_symbol_cooldown_min",
                "daily_max_loss_pct",
                "losing_streak_pause_after",
                "portfolio_level_drawdown_pct",
            ]
        )
    top = exit_leaderboard[exit_leaderboard["decision"].isin(["promote_to_paper", "watchlist"])].head(top_n)
    event_meta = events.set_index("event_key")
    for item in top.itertuples(index=False):
        vals = values_df[(values_df["entry_candidate_id"] == item.entry_candidate_id) & (values_df["exit_policy_id"] == item.exit_policy_id)].copy()
        if vals.empty:
            continue
        vals = vals.join(event_meta[["api_symbol", "ts_ms", "day"]], on="event_key", how="left").sort_values("ts_ms")
        kept = []
        last_symbol_ts: dict[str, int] = {}
        daily_pnl: dict[str, float] = {}
        losing_streak = 0
        pause_until = -1
        for row in vals.itertuples(index=False):
            ts = int(row.ts_ms)
            sym = str(row.api_symbol)
            day = str(row.day)
            if ts < pause_until:
                continue
            if sym in last_symbol_ts and ts - last_symbol_ts[sym] < 60 * 60_000:
                continue
            if daily_pnl.get(day, 0.0) <= -5.0:
                continue
            kept.append(float(row.net_pct))
            daily_pnl[day] = daily_pnl.get(day, 0.0) + float(row.net_pct)
            last_symbol_ts[sym] = ts
            if float(row.net_pct) <= 0:
                losing_streak += 1
                if losing_streak >= 4:
                    pause_until = ts + 6 * 60 * 60_000
                    losing_streak = 0
            else:
                losing_streak = 0
        metrics = metrics_from_trades(kept)
        rows.append(
            {
                "entry_candidate_id": item.entry_candidate_id,
                "exit_policy_id": item.exit_policy_id,
                "one_coin_one_position": True,
                "same_symbol_cooldown_min": 60,
                "daily_max_loss_pct": -5.0,
                "losing_streak_pause_after": 4,
                "portfolio_level_drawdown_pct": metrics["max_drawdown_pct"],
                **metrics,
            }
        )
    if rows:
        return pd.DataFrame(rows).sort_values(["median_net_pct", "p25_net_pct"], ascending=False)
    return pd.DataFrame(
        columns=[
            "entry_candidate_id",
            "exit_policy_id",
            "one_coin_one_position",
            "same_symbol_cooldown_min",
            "daily_max_loss_pct",
            "losing_streak_pause_after",
            "portfolio_level_drawdown_pct",
            "sample_size",
            "median_net_pct",
            "p25_net_pct",
        ]
    )


def overfit_reports(events: pd.DataFrame, exit_leaderboard: pd.DataFrame, values_df: pd.DataFrame, *, top_n: int = 25) -> tuple[pd.DataFrame, pd.DataFrame]:
    event_meta = events.set_index("event_key")
    stress_rows = []
    neighborhood_rows = []
    if values_df.empty or exit_leaderboard.empty:
        return (
            pd.DataFrame(columns=["entry_candidate_id", "exit_policy_id", "stress_name"]),
            pd.DataFrame(columns=["entry_candidate_id", "exit_policy_id", "parameter_multiplier", "stability_proxy_score", "neighborhood_decision"]),
        )
    for item in exit_leaderboard.head(top_n).itertuples(index=False):
        vals = values_df[(values_df["entry_candidate_id"] == item.entry_candidate_id) & (values_df["exit_policy_id"] == item.exit_policy_id)].copy()
        if vals.empty:
            continue
        vals = vals.join(event_meta[["api_symbol", "ts_ms"]], on="event_key", how="left")
        base = pd.to_numeric(vals["net_pct"], errors="coerce")
        stresses = {
            "baseline": base,
            "fee_slippage_extra_0_50pct": base - 0.50,
            "remove_top_1pct_winners": base[base < base.quantile(0.99)],
            "remove_top_symbol": base[~vals["api_symbol"].isin(vals["api_symbol"].value_counts().head(1).index)],
            "remove_top5_symbols": base[~vals["api_symbol"].isin(vals["api_symbol"].value_counts().head(5).index)],
        }
        for stress_name, series in stresses.items():
            m = metrics_from_trades(series)
            stress_rows.append({"entry_candidate_id": item.entry_candidate_id, "exit_policy_id": item.exit_policy_id, "stress_name": stress_name, **m})
        for mult in (0.9, 1.0, 1.1):
            neighborhood_rows.append(
                {
                    "entry_candidate_id": item.entry_candidate_id,
                    "exit_policy_id": item.exit_policy_id,
                    "parameter_multiplier": mult,
                    "stability_proxy_score": round(float(item.score) * mult, 6),
                    "neighborhood_decision": "stable" if item.p25_net_pct >= -1.0 and item.median_net_pct > 0 else "unstable",
                }
            )
    return pd.DataFrame(stress_rows), pd.DataFrame(neighborhood_rows)


def write_contract_artifacts(out_dir: Path, events: pd.DataFrame) -> None:
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "BWE AutoResearch V3 Candidate",
        "type": "object",
        "required": ["candidate_id", "entry_gate_rule", "entry_timing_rule", "binance_feature_use_decision", "in_position_monitoring_rule", "exit_state_machine", "fallback_exit", "risk_rule", "portfolio_rule", "paper_only", "live_allowed"],
        "properties": {
            "candidate_id": {"type": "string"},
            "entry_gate_rule": {"type": "object"},
            "entry_timing_rule": {"type": "object"},
            "binance_feature_use_decision": {"type": "object"},
            "in_position_monitoring_rule": {"type": "object"},
            "exit_state_machine": {"type": "object"},
            "fallback_exit": {"type": "object"},
            "risk_rule": {"type": "object"},
            "portfolio_rule": {"type": "object"},
            "path_resolution": {"enum": ["1m_mark", "5m_trade", "forward_label_only"]},
            "paper_only": {"const": True},
            "live_allowed": {"const": False},
        },
        "additionalProperties": True,
    }
    metric_contract = {
        "version": "2026-04-25-v3",
        "primary_objective": "robust_entry_timing_exit_with_binance_feature_utility",
        "ranking_order": [
            "median_net_pct",
            "p25_net_pct",
            "p10_net_pct",
            "win_rate_pct",
            "walk_forward_positive_rate_pct",
            "mfe_capture_ratio",
            "giveback_ratio_pct",
            "fee_slippage_stress",
            "portfolio_level_drawdown_pct",
            "feature_freshness",
            "complexity_penalty",
            "mean_net_pct",
        ],
        "freshness_rules": {"fresh_le_ms": 300000, "deweight_le_ms": 600000, "too_old_gt_ms": 600000},
        "future_fields_forbidden_in_rules": sorted(FUTURE_FIELDS | {"ret_*", "net_*", "confirm_after_*"}),
        "paper_gate": {"paper_only": True, "live_allowed": False, "max_promote_to_paper": 10},
    }
    write_json(out_dir / "v3_candidate_schema.json", schema)
    write_json(out_dir / "v3_metric_contract.json", metric_contract)
    lines = [
        "# BWE AutoResearch v3 数据合同",
        "",
        "## 数据集",
        f"- total_active_events: `{len(events)}`",
        f"- core_complete_events: `{int(events['core_complete'].sum())}`",
        "",
        "## entry_time_features",
        "- BWE channel/event_type/symbol/liquidity/marketcap/burst/pretrend/BTC regime",
        "- Binance OI/funding/global long-short/top trader/taker flow/basis/premium/mark-index",
        "- 所有 5m 统计指标必须检查 `*_age_ms`。",
        "",
        "## delayed_entry_features",
        "- T0+30s/T0+1m/T0+3m/T0+5m 已经发生的 mark 1m path、premium 1m、confirmation。",
        "- `confirm_after_*` 只能在对应延迟入场实验中使用。",
        "",
        "## in_position_features",
        "- 持仓后 1m mark path、premium path、5m 统计指标的新鲜度与失效信号。",
        "",
        "## future_labels",
        "- `ret_*`, `net_*`, `mfe`, `mae`, `mfe_pct`, `mae_pct` 只能评估，不能触发入场或退出。",
        "",
        "## path_resolution",
        "- `1m_mark`: 用 Binance mark 1m path 近似 first-touch/exit。",
        "  - 当前 v3 输入包只有 mark/premium 1m，没有实际成交价、volume、trade_count。",
        "  - 因此 `1m_mark` 是研究口径，不等价于成交口径。",
        "- `5m_trade`: 保留给后续真实 5m trade path。",
        "- `forward_label_only`: 只能做标签评估，不能声称精确 first-touch。",
        "",
        "## 已知数据缺口",
        "- `local_kline_rows=0`：本轮 30d 包没有接上本地 trade kline。",
        "- `binance_status_active_now` 是采集时状态，只能作过滤痕迹，不能作为 T0 alpha 特征。",
        "- mark/premium 覆盖完整，但原 feature_registry 未登记，v3 合同显式纳入治理。",
    ]
    (out_dir / "data_contract.md").write_text("\n".join(lines), encoding="utf-8")


def round2_baseline_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text())
    except Exception:
        return []
    rows = []
    for item in payload.get("experiments", []):
        rows.append(
            {
                "baseline_id": f"round2_manifest::{item.get('experiment_id')}",
                "entry_delay_s": item.get("message_delay_s", 0),
                "horizon_min": None,
                "sample_size": None,
                "median_net_pct": item.get("adjusted_median_net_pct"),
                "p25_net_pct": item.get("adjusted_p25_net_pct"),
                "source": "round2_paper_manifest_reference",
                "live_allowed": item.get("live_allowed", False),
                "paper_only": item.get("paper_only", True),
            }
        )
    return rows


def make_manifest(exit_leaderboard: pd.DataFrame, portfolio: pd.DataFrame, feature_decisions: pd.DataFrame, *, max_items: int = 10) -> dict[str, Any]:
    allowed_features = feature_decisions[feature_decisions["use_decision"].eq("use")]["feature_packet"].dropna().unique().tolist() if not feature_decisions.empty else []
    portfolio_keys = set()
    if not portfolio.empty:
        portfolio_keys = set((portfolio["entry_candidate_id"] + "||" + portfolio["exit_policy_id"]).head(max_items).tolist())
    experiments = []
    source = exit_leaderboard[exit_leaderboard["decision"].isin(["promote_to_paper", "watchlist"])].copy()
    if not portfolio_keys and not source.empty:
        portfolio_keys = set((source["entry_candidate_id"] + "||" + source["exit_policy_id"]).head(max_items).tolist())
    for idx, row in enumerate(source.itertuples(index=False), 1):
        key = f"{row.entry_candidate_id}||{row.exit_policy_id}"
        if key not in portfolio_keys:
            continue
        strategy_id = f"{row.entry_candidate_id}__{row.exit_policy_id}"
        if any(x.get("strategy_id") == strategy_id for x in experiments):
            continue
        experiments.append(
            {
                "experiment_id": f"v3_auto_{idx:03d}",
                "paper_only": True,
                "live_allowed": False,
                "required_clean_complete": 20,
                "status": "paper_ready_manifest_only" if row.decision == "promote_to_paper" else "paper_watchlist_manifest_only",
                "strategy_id": strategy_id,
                "channel": row.channel,
                "event_type": row.event_type,
                "direction": row.side,
                "entry_gate": {"candidate_id": row.entry_candidate_id},
                "entry_timing_rule": {"entry_delay_s": int(row.entry_delay_s), "trigger_style": "time_window_plus_conditions"},
                "binance_feature_use_decision": {"allowed_feature_packets": allowed_features},
                "in_position_monitoring_rule": {"source": "hold_or_exit_signal_matrix.csv"},
                "exit_state_machine": {"exit_policy_id": row.exit_policy_id, "family": row.exit_family, "policy": json.loads(row.policy_json)},
                "fallback_exit": {"type": "time_stop", "max_hold_min": 60},
                "risk_rule": {"paper_fixed_notional": True, "one_coin_one_position": True, "max_concurrent_positions": 5},
                "portfolio_rule": {"same_symbol_cooldown_min": 60, "daily_max_loss_pct": -5.0, "losing_streak_pause_after": 4},
                "path_resolution": row.path_resolution,
                "metrics": {"sample_size": int(row.sample_size), "median_net_pct": row.median_net_pct, "p25_net_pct": row.p25_net_pct, "win_rate_pct": row.win_rate_pct, "mfe_capture_ratio": row.mfe_capture_ratio, "giveback_ratio_pct": row.giveback_ratio_pct},
                "notes": "Generated by BWE AutoResearch v3; paper-only tracking, no live authorization.",
            }
        )
        if len(experiments) >= max_items:
            break
    return {"schema": "bwe_autoresearch_v3_paper_manifest", "paper_only": True, "live_allowed": False, "max_promote_to_paper": max_items, "experiments": experiments}


def write_report(out_dir: Path, summary: dict[str, Any], manifest: dict[str, Any], entry: pd.DataFrame, timing: pd.DataFrame, exit_leaderboard: pd.DataFrame) -> None:
    entry_view = entry.copy()
    if not entry_view.empty:
        entry_view["min_sample_required"] = entry_view["channel"].map(min_sample_for_channel)
        eligible_entry = entry_view[(entry_view["sample_size"] >= entry_view["min_sample_required"]) & (entry_view["median_net_pct"] > 0)]
        entry_view = eligible_entry.sort_values(["median_net_pct", "p25_net_pct", "sample_size"], ascending=False) if not eligible_entry.empty else entry_view
    timing_view = timing.copy()
    if not timing_view.empty:
        timing_view = timing_view.sort_values(["decision", "median_net_pct", "p25_net_pct", "sample_size"], ascending=[True, False, False, False])
    top_entry = entry_view.head(5)[["candidate_id", "feature_packet", "channel", "event_type", "side", "sample_size", "median_net_pct", "p25_net_pct", "win_rate_pct", "decision"]].to_dict("records") if not entry_view.empty else []
    top_timing = timing_view.head(5)[["timing_candidate_id", "entry_delay_s", "horizon_min", "sample_size", "median_net_pct", "p25_net_pct", "decision"]].to_dict("records") if not timing_view.empty else []
    top_exit = exit_leaderboard.head(8)[["entry_candidate_id", "exit_policy_id", "exit_family", "sample_size", "median_net_pct", "p25_net_pct", "mfe_capture_ratio", "giveback_ratio_pct", "decision"]].to_dict("records") if not exit_leaderboard.empty else []
    lines = [
        "# BWE AutoResearch v3 中文报告",
        "",
        "## 结论",
        f"- 输出目录：`{out_dir}`",
        f"- core_complete_events：`{summary.get('core_complete_events')}`",
        f"- entry candidates：`{summary.get('entry_candidates')}`",
        f"- timing candidates：`{summary.get('timing_candidates')}`",
        f"- exit candidates：`{summary.get('exit_candidates')}`",
        f"- paper manifest experiments：`{len(manifest.get('experiments', []))}`",
        "- 本轮只输出 paper 候选，`live_allowed=false`。",
        "",
        "## Top Entry",
        json.dumps(clean_json(top_entry), ensure_ascii=False, indent=2),
        "",
        "## Top Timing",
        json.dumps(clean_json(top_timing), ensure_ascii=False, indent=2),
        "",
        "## Top Exit",
        json.dumps(clean_json(top_exit), ensure_ascii=False, indent=2),
        "",
        "## 风险边界",
        "- Binance 5m 统计指标按 `age_ms` 进行新鲜度检查。",
        "- `ret_* / net_* / mfe / mae` 只作为标签和路径评估，不作为即时入场条件。",
        "- 最终 manifest 不是 live 授权；需要 paper clean complete 后人工复核。",
    ]
    (out_dir / "report_zh.md").write_text("\n".join(lines), encoding="utf-8")


def run(args: argparse.Namespace) -> dict[str, Any]:
    feature_dir = Path(args.feature_dir)
    out_dir = ensure_out_dir(Path(args.out_dir))
    events, forward, mark, premium = load_inputs(feature_dir)
    write_contract_artifacts(out_dir, events)

    entry, ablation, feature_decisions, baseline = run_entry_research(events, forward)
    baseline = pd.concat([baseline, pd.DataFrame(round2_baseline_rows(Path(args.round2_manifest)))], ignore_index=True, sort=False)
    mark_outcomes = compute_mark_outcomes(events, mark)
    timing, selected_entry_rules = run_entry_timing(events, mark_outcomes, entry, top_n=args.top_entry_for_timing)
    in_position, hold_matrix = in_position_monitoring(events, mark_outcomes)
    exit_catalog, exit_leaderboard, exit_diag, exit_survivor, exit_values = run_exit_research(events, mark_outcomes, timing, top_n=args.top_timing_for_exit)
    utility = feature_utility_matrix(entry, timing, exit_leaderboard)
    portfolio = portfolio_simulation(events, exit_leaderboard, exit_values)
    overfit, neighborhood = overfit_reports(events, exit_leaderboard, exit_values)
    reject_log = pd.concat(
        [
            entry[entry["decision"].ne("promote_to_paper")][["candidate_id", "stage", "decision", "reject_reason", "sample_size", "median_net_pct", "p25_net_pct"]],
            timing[timing["decision"].ne("promote_to_paper")][["candidate_id", "stage", "decision", "reject_reason", "sample_size", "median_net_pct", "p25_net_pct"]],
        ],
        ignore_index=True,
        sort=False,
    )
    if not exit_leaderboard.empty:
        reject_log = pd.concat(
            [
                reject_log,
                exit_leaderboard[exit_leaderboard["decision"].ne("promote_to_paper")][["exit_policy_id", "decision", "reject_reason", "sample_size", "median_net_pct", "p25_net_pct"]].rename(columns={"exit_policy_id": "candidate_id"}),
            ],
            ignore_index=True,
            sort=False,
        )
    manifest = make_manifest(exit_leaderboard, portfolio, feature_decisions, max_items=args.max_manifest_items)

    entry.to_csv(out_dir / "entry_gate_leaderboard.csv", index=False)
    ablation.to_csv(out_dir / "feature_ablation.csv", index=False)
    utility.to_csv(out_dir / "binance_feature_utility_matrix.csv", index=False)
    feature_decisions.to_csv(out_dir / "feature_use_decisions.csv", index=False)
    baseline.to_csv(out_dir / "baseline_comparison.csv", index=False)
    timing.to_csv(out_dir / "entry_timing_leaderboard.csv", index=False)
    in_position.to_csv(out_dir / "in_position_feature_leaderboard.csv", index=False)
    hold_matrix.to_csv(out_dir / "hold_or_exit_signal_matrix.csv", index=False)
    write_jsonl(out_dir / "exit_family_catalog.jsonl", exit_catalog.to_dict("records"))
    exit_leaderboard.to_csv(out_dir / "exit_policy_leaderboard.csv", index=False)
    exit_diag.to_csv(out_dir / "exit_path_diagnostics.csv", index=False)
    exit_survivor.to_csv(out_dir / "exit_survivor_matrix.csv", index=False)
    portfolio.to_csv(out_dir / "portfolio_simulation_summary.csv", index=False)
    overfit.to_csv(out_dir / "overfit_stress_report.csv", index=False)
    neighborhood.to_csv(out_dir / "parameter_neighborhood_stability.csv", index=False)
    reject_log.to_csv(out_dir / "reject_log.csv", index=False)
    selected_entry_rules.to_csv(out_dir / "selected_entry_rules_for_timing.csv", index=False)
    write_json(out_dir / "paper_manifest_v3.json", manifest)

    summary = {
        "out_dir": str(out_dir),
        "feature_dir": str(feature_dir),
        "total_active_events": int(len(events)),
        "core_complete_events": int(events["core_complete"].sum()),
        "forward_rows": int(len(forward)),
        "mark_outcome_rows": int(len(mark_outcomes)),
        "entry_candidates": int(len(entry)),
        "timing_candidates": int(len(timing)),
        "exit_candidates": int(len(exit_leaderboard)),
        "paper_manifest_experiments": int(len(manifest.get("experiments", []))),
        "live_allowed": False,
        "paper_only": True,
    }
    write_json(out_dir / "summary.json", summary)
    write_report(out_dir, summary, manifest, entry, timing, exit_leaderboard)
    return summary


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run BWE AutoResearch v3 feature/entry/timing/exit research")
    p.add_argument("--feature-dir", default=str(DEFAULT_FEATURE_DIR))
    p.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    p.add_argument("--round2-manifest", default=str(DEFAULT_ROUND2_MANIFEST))
    p.add_argument("--top-entry-for-timing", type=int, default=40)
    p.add_argument("--top-timing-for-exit", type=int, default=25)
    p.add_argument("--max-manifest-items", type=int, default=10)
    return p


def main() -> None:
    summary = run(build_parser().parse_args())
    print(json.dumps(clean_json(summary), ensure_ascii=False, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
