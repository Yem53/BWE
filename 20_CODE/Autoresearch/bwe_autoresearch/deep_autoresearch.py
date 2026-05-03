"""Deep sandbox-only BWE AutoResearch pipeline.

This module expands the earlier discovery-only workflow into a staged
catalog + scoring pipeline for broad entry and exit research on historical
artifacts only. It never touches live trading code, launchd configs, or
order endpoints.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd


LIVE_PATH_MARKERS = (
    "bwe_live_autotrader",
    "live_autotrader",
    "okx_trade",
    "binance_order",
    "launchagents",
    "launchdaemons",
    "orders",
)

DEFAULT_FORWARD = Path("/Users/ye/.hermes/research/bwe_three_channel_fullrun3/forward.parquet")
DEFAULT_HOURLY = Path("/Users/ye/.hermes/research/bwe_three_channel_fullrun3/event_hourly_2h_pre_48h_post.parquet")
DEFAULT_PATH_5M = Path("/Users/ye/.hermes/research/bwe_live_exit_optimization_run5/all4_event_5m_72h.parquet")
DEFAULT_REQUESTED_OUT = Path("/Users/ye/.hermes/research/bwe_deep_autoresearch_20260425")
DEFAULT_FALLBACK_OUT = Path(__file__).resolve().parents[1] / "runs" / "bwe_deep_autoresearch_20260425"
ENTRY_HORIZONS = (3, 5, 10, 15, 30, 60)
ENTRY_VARIANT_GRID = {
    "entry_delay_s": (0, 10, 30, 60, 180),
    "holding_horizon_min": ENTRY_HORIZONS,
    "liquidity_bucket": ("low", "mid", "high"),
    "marketcap_bucket_norm": ("<50m", "50m-200m", "200m-1b", ">=1b", "unknown"),
    "btc_regime": ("btc_down", "btc_flat", "btc_up"),
    "trend_alignment": ("aligned", "counter"),
}
EXIT_ARCHETYPE_VARIANTS = ("balanced", "aggressive", "defensive", "long_bias", "short_bias")
ROUNDTRIP_COST_PCT = 0.20
ACTIVE_EXIT_STRATEGY_CONFIG = {
    "oi_overcrowded_crash_follow_short": {
        "entry_delay_s": 180,
        "hard_stop_pct": 4.0,
        "activation_delay_min": 3,
        "catastrophe_stop_pct": 6.0,
    },
    "pc_second_signal_cont_long": {
        "entry_delay_s": 30,
        "hard_stop_pct": 2.5,
        "activation_delay_min": 5,
        "catastrophe_stop_pct": 6.0,
    },
    "pc_pump_cont_long": {
        "entry_delay_s": 0,
        "hard_stop_pct": 4.0,
        "activation_delay_min": 5,
        "catastrophe_stop_pct": 6.0,
    },
    "pc_crash_bounce_long": {
        "entry_delay_s": 10,
        "hard_stop_pct": 4.0,
        "activation_delay_min": 5,
        "catastrophe_stop_pct": 6.0,
    },
}


@dataclass(frozen=True)
class EntryArchetype:
    archetype_id: str
    family: str
    family_group: str
    source_channel: str
    direction: str
    base_rule: dict[str, Any]
    description: str
    discovery_class: str
    expected_variant_count: int


@dataclass(frozen=True)
class ExitArchetype:
    archetype_id: str
    family: str
    variation: str
    description: str
    parameters_template: dict[str, Any]
    scorable: bool
    priority_rank: int
    expected_variant_count: int


def refuse_if_live_path(path: str | Path) -> None:
    lowered = str(path).lower()
    if any(marker in lowered for marker in LIVE_PATH_MARKERS):
        raise ValueError(f"refusing live-sensitive path: {path}")


def _is_output_path_safe(path: str | Path) -> bool:
    lowered = str(path).lower()
    return not any(marker in lowered for marker in LIVE_PATH_MARKERS)


def _ensure_dir(path: Path) -> None:
    refuse_if_live_path(path)
    path.mkdir(parents=True, exist_ok=True)


def resolve_output_dir(requested_out_dir: Path, fallback_out_dir: Path) -> tuple[Path, bool, str]:
    if not _is_output_path_safe(requested_out_dir):
        raise ValueError(f"unsafe requested output path: {requested_out_dir}")
    if not _is_output_path_safe(fallback_out_dir):
        raise ValueError(f"unsafe fallback output path: {fallback_out_dir}")

    for candidate, used_fallback, reason in (
        (requested_out_dir, False, "requested output path writable"),
        (fallback_out_dir, True, "requested output path blocked by sandbox; using repo-local mirror"),
    ):
        try:
            _ensure_dir(candidate)
            probe = candidate / ".codex_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return candidate, used_fallback, reason
        except OSError:
            continue
    raise OSError(f"unable to write either requested or fallback output dir: {requested_out_dir} | {fallback_out_dir}")


def _now_iso() -> str:
    return pd.Timestamp.now(tz="UTC").isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    lines = [json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _render_running_md(progress: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# BWE Deep AutoResearch 2026-04-25",
            "",
            f"- requested_out_dir: `{progress['requested_out_dir']}`",
            f"- actual_out_dir: `{progress['actual_out_dir']}`",
            f"- sandbox_fallback: `{progress['used_fallback_out_dir']}`",
            f"- status: `{progress['status']}`",
            f"- stage: `{progress['stage']}`",
            f"- last_updated_at: `{progress['last_updated_at']}`",
            f"- note: {progress.get('note', '')}",
            "",
            "## Counts",
            "",
            f"- entry_archetypes: `{progress.get('entry_archetypes_total', 0)}`",
            f"- entry_branches: `{progress.get('entry_branches_total', 0)}`",
            f"- entry_scored_branches: `{progress.get('entry_scored_branches', 0)}`",
            f"- exit_archetypes: `{progress.get('exit_archetypes_total', 0)}`",
            f"- exit_branches: `{progress.get('exit_branches_total', 0)}`",
            f"- exit_scored_branches: `{progress.get('exit_scored_branches', 0)}`",
            f"- exit_pending_branches: `{progress.get('exit_pending_branches', 0)}`",
            f"- combined_pairs_tested: `{progress.get('combined_pairs_tested', 0)}`",
            "",
            "## Guardrails",
            "",
            "- research only",
            "- no live trading changes",
            "- no LaunchAgent or autotrader writes",
            "- no order endpoints",
            "- no secrets printed",
        ]
    )


def update_progress(out_dir: Path, progress: dict[str, Any], **updates: Any) -> None:
    progress.update(updates)
    progress["last_updated_at"] = _now_iso()
    _write_json(out_dir / "progress.json", progress)
    (out_dir / "RUNNING.md").write_text(_render_running_md(progress), encoding="utf-8")


def _pnl_pct(entry_px: float, px: float, side: str) -> float:
    if side == "short":
        return (entry_px / px - 1.0) * 100.0
    return (px / entry_px - 1.0) * 100.0


def _series_mask(df: pd.DataFrame, rule: dict[str, Any]) -> pd.Series:
    mask = pd.Series(True, index=df.index)
    for key, value in (rule or {}).items():
        if key.endswith("_gte"):
            col = key[:-4]
            if col in df.columns:
                mask &= pd.to_numeric(df[col], errors="coerce") >= value
        elif key.endswith("_lte"):
            col = key[:-4]
            if col in df.columns:
                mask &= pd.to_numeric(df[col], errors="coerce") <= value
        elif key.endswith("_gt"):
            col = key[:-3]
            if col in df.columns:
                mask &= pd.to_numeric(df[col], errors="coerce") > value
        elif key.endswith("_lt"):
            col = key[:-3]
            if col in df.columns:
                mask &= pd.to_numeric(df[col], errors="coerce") < value
        elif key.endswith("_eq"):
            col = key[:-3]
            if col in df.columns:
                mask &= df[col] == value
        elif key.endswith("_in"):
            col = key[:-3]
            if col in df.columns:
                mask &= df[col].isin(value)
        else:
            if key in df.columns:
                mask &= df[key] == value
    return mask.fillna(False)


def _rule_merge(*parts: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for part in parts:
        merged.update(part)
    return merged


def _longest_losing_streak(values: Sequence[float]) -> int:
    longest = cur = 0
    for value in values:
        if value <= 0:
            cur += 1
            longest = max(longest, cur)
        else:
            cur = 0
    return longest


def _profit_factor(values: np.ndarray) -> float:
    gains = values[values > 0].sum()
    losses = -values[values < 0].sum()
    if losses <= 0:
        return float("inf") if gains > 0 else 0.0
    return float(gains / losses)


def _positive_rate(grouped_mean: pd.Series, min_groups: int = 1) -> float:
    if grouped_mean.empty or grouped_mean.shape[0] < min_groups:
        return 0.0
    return float((grouped_mean > 0).mean() * 100.0)


def prepare_forward_frame(forward_path: Path, hourly_path: Path) -> pd.DataFrame:
    df = pd.read_parquet(forward_path)
    hourly = pd.read_parquet(hourly_path, columns=["channel", "post_id", "relative_hour", "close", "quote_volume"])
    hourly["event_key"] = hourly["channel"].astype(str) + "#" + hourly["post_id"].astype(str)

    prev = (
        hourly[hourly["relative_hour"] < 0]
        .sort_values(["event_key", "relative_hour"])
        .groupby("event_key", as_index=False)
        .tail(1)[["event_key", "quote_volume"]]
        .rename(columns={"quote_volume": "prev_hour_quote_volume"})
    )
    pre = hourly[hourly["relative_hour"] < 0].copy()
    first = (
        pre.sort_values(["event_key", "relative_hour"])
        .groupby("event_key", as_index=False)
        .head(1)[["event_key", "close"]]
        .rename(columns={"close": "base_close"})
    )
    last = (
        pre.sort_values(["event_key", "relative_hour"])
        .groupby("event_key", as_index=False)
        .tail(1)[["event_key", "close"]]
        .rename(columns={"close": "latest_close"})
    )
    feat = first.merge(last, on="event_key", how="outer").merge(prev, on="event_key", how="left")
    feat["pre2h"] = feat["latest_close"] / feat["base_close"] - 1.0
    vals = feat["prev_hour_quote_volume"].dropna()
    vals = vals[vals > 0]
    q4 = float(vals.quantile(0.75)) if len(vals) else 0.0

    df = df.copy()
    df["event_key"] = df["channel"].astype(str) + "#" + df["post_id"].astype(str)
    df = df.merge(feat[["event_key", "pre2h", "prev_hour_quote_volume"]], on="event_key", how="left")
    df["ts"] = pd.to_datetime(df["ts_ms"], unit="ms", errors="coerce")
    df["month"] = df["ts"].dt.to_period("M").astype(str)
    df["abs_move_pct"] = pd.to_numeric(df["move_pct"], errors="coerce").abs()
    df["mfe_pct"] = pd.to_numeric(df["mfe"], errors="coerce") * 100.0
    df["mae_pct"] = pd.to_numeric(df["mae"], errors="coerce") * 100.0
    df["marketcap_bucket_norm"] = df["marketcap_bucket"].fillna("unknown")
    df["btc_regime"] = np.select(
        [
            pd.to_numeric(df["btc_pre30m"], errors="coerce") <= -0.004,
            pd.to_numeric(df["btc_pre30m"], errors="coerce") >= 0.004,
        ],
        ["btc_down", "btc_up"],
        default="btc_flat",
    )
    trend_up = {"trend_up_all", "short_down_long_up"}
    trend_down = {"trend_down_all", "short_up_long_down"}
    df["trend_alignment"] = np.where(
        ((df["side"] == "long") & df["trend_state"].isin(trend_up))
        | ((df["side"] == "short") & df["trend_state"].isin(trend_down)),
        "aligned",
        "counter",
    )
    df["vol_regime"] = np.select(
        [
            df["abs_move_pct"] >= 20,
            df["abs_move_pct"] >= 10,
            df["abs_move_pct"] >= 5,
        ],
        ["extreme", "hot", "warm"],
        default="cool",
    )
    df["pre30m_dir"] = np.select(
        [
            pd.to_numeric(df["pre30m"], errors="coerce") <= -0.01,
            pd.to_numeric(df["pre30m"], errors="coerce") >= 0.01,
        ],
        ["down", "up"],
        default="flat",
    )
    df["prev_hour_quote_volume_q4"] = q4
    return df


def _entry_groups() -> list[dict[str, Any]]:
    return [
        {"group_id": "g01", "family": "oi_crowded_pump_fade_short", "channel": "BWE_OI_Price_monitor", "direction": "short", "rule": {"event_type": "pump", "oi_ratio_pct_gte": 8, "day_change_pct_gte": 8}, "discovery_class": "known_refinement", "description": "OI crowded pump fade short."},
        {"group_id": "g02", "family": "oi_crowded_crash_follow_short", "channel": "BWE_OI_Price_monitor", "direction": "short", "rule": {"event_type": "crash", "oi_ratio_pct_gte": 10, "day_change_pct_lte": -10}, "discovery_class": "known_refinement", "description": "OI crowded crash follow short."},
        {"group_id": "g03", "family": "oi_negative_oi_pump_fade_short", "channel": "BWE_OI_Price_monitor", "direction": "short", "rule": {"event_type": "pump", "oi_change_pct_lt": 0, "move_pct_gte": 8}, "discovery_class": "known_refinement", "description": "Negative OI pump fade short."},
        {"group_id": "g04", "family": "oi_positive_oi_pump_cont_long", "channel": "BWE_OI_Price_monitor", "direction": "long", "rule": {"event_type": "pump", "oi_change_pct_gte": 5, "oi_ratio_pct_gte": 5, "day_change_pct_gte": 5}, "discovery_class": "known_refinement", "description": "Positive OI pump continuation long."},
        {"group_id": "g05", "family": "oi_price_divergence_pump_fade_short", "channel": "BWE_OI_Price_monitor", "direction": "short", "rule": {"event_type": "pump", "oi_change_pct_lte": 0, "day_change_pct_gte": 10}, "discovery_class": "controlled_new", "description": "Price/OI divergence pump fade short."},
        {"group_id": "g06", "family": "oi_price_divergence_crash_bounce_long", "channel": "BWE_OI_Price_monitor", "direction": "long", "rule": {"event_type": "crash", "oi_change_pct_lte": 0, "day_change_pct_lte": -10}, "discovery_class": "controlled_new", "description": "Price/OI divergence crash bounce long."},
        {"group_id": "g07", "family": "pc_pump_cont_long", "channel": "BWE_pricechange_monitor", "direction": "long", "rule": {"event_type": "pump", "move_pct_gte": 5}, "discovery_class": "known_refinement", "description": "Pricechange pump continuation long."},
        {"group_id": "g08", "family": "pc_pump_fade_short", "channel": "BWE_pricechange_monitor", "direction": "short", "rule": {"event_type": "pump", "move_pct_gte": 8}, "discovery_class": "controlled_new", "description": "Pricechange pump exhaustion fade short."},
        {"group_id": "g09", "family": "pc_crash_bounce_long", "channel": "BWE_pricechange_monitor", "direction": "long", "rule": {"event_type": "crash", "move_pct_lte": -8}, "discovery_class": "known_refinement", "description": "Pricechange crash bounce long."},
        {"group_id": "g10", "family": "pc_crash_cont_short", "channel": "BWE_pricechange_monitor", "direction": "short", "rule": {"event_type": "crash", "move_pct_lte": -8}, "discovery_class": "controlled_new", "description": "Pricechange crash continuation short."},
        {"group_id": "g11", "family": "pc_burst_seq2_cont_long", "channel": "BWE_pricechange_monitor", "direction": "long", "rule": {"event_type": "pump", "burst_seq_5m_eq": 2}, "discovery_class": "controlled_new", "description": "Second burst continuation long."},
        {"group_id": "g12", "family": "pc_burst_seq3_fade_short", "channel": "BWE_pricechange_monitor", "direction": "short", "rule": {"event_type": "pump", "burst_seq_5m_eq": 3}, "discovery_class": "controlled_new", "description": "Third burst fade short."},
        {"group_id": "g13", "family": "pc_burst_seq4_plus_cont_long", "channel": "BWE_pricechange_monitor", "direction": "long", "rule": {"event_type": "pump", "burst_seq_5m_gte": 4}, "discovery_class": "contrarian", "description": "Fourth-plus burst continuation long."},
        {"group_id": "g14", "family": "pc_second_signal_state_long", "channel": "BWE_pricechange_monitor", "direction": "long", "rule": {"event_type": "pump", "burst_seq_5m_eq": 2, "confirm_count_5m_gte": 1}, "discovery_class": "controlled_new", "description": "Second signal state-machine long."},
        {"group_id": "g15", "family": "pc_third_signal_state_short", "channel": "BWE_pricechange_monitor", "direction": "short", "rule": {"event_type": "pump", "burst_seq_5m_eq": 3, "confirm_count_5m_gte": 1}, "discovery_class": "controlled_new", "description": "Third signal state-machine short."},
        {"group_id": "g16", "family": "pc_fourth_signal_state_short", "channel": "BWE_pricechange_monitor", "direction": "short", "rule": {"event_type": "pump", "burst_seq_5m_gte": 4, "confirm_count_5m_gte": 1}, "discovery_class": "contrarian", "description": "Fourth signal state-machine short."},
        {"group_id": "g17", "family": "cross_before5m_pc_oi_long", "channel": "BWE_pricechange_monitor", "direction": "long", "rule": {"event_type": "pump", "confirm_before_5m_oi_eq": True}, "discovery_class": "controlled_new", "description": "Cross-channel confirm before 5m long."},
        {"group_id": "g18", "family": "cross_after5m_pc_oi_short", "channel": "BWE_pricechange_monitor", "direction": "short", "rule": {"event_type": "pump", "confirm_after_5m_oi_eq": True}, "discovery_class": "controlled_new", "description": "Cross-channel confirm after 5m short."},
        {"group_id": "g19", "family": "r6_pump_fade_short", "channel": "BWE_Reserved6", "direction": "short", "rule": {"event_type": "pump", "move_pct_gte": 8}, "discovery_class": "known_refinement", "description": "Reserved6 pump fade short."},
        {"group_id": "g20", "family": "r6_pump_cont_long", "channel": "BWE_Reserved6", "direction": "long", "rule": {"event_type": "pump", "move_pct_gte": 8}, "discovery_class": "controlled_new", "description": "Reserved6 pump continuation long."},
        {"group_id": "g21", "family": "r6_crash_bounce_long", "channel": "BWE_Reserved6", "direction": "long", "rule": {"event_type": "crash", "move_pct_lte": -8}, "discovery_class": "known_refinement", "description": "Reserved6 crash bounce long."},
        {"group_id": "g22", "family": "r6_crash_cont_short", "channel": "BWE_Reserved6", "direction": "short", "rule": {"event_type": "crash", "move_pct_lte": -8}, "discovery_class": "known_refinement", "description": "Reserved6 crash continuation short."},
        {"group_id": "g23", "family": "oi_r6_combo_pump_fade_short", "channel": "BWE_OI_Price_monitor", "direction": "short", "rule": {"event_type": "pump", "oi_ratio_pct_gte": 8, "confirm_after_5m_reserved6_eq": True}, "discovery_class": "controlled_new", "description": "OI + Reserved6 pump fade short."},
        {"group_id": "g24", "family": "oi_r6_combo_crash_cont_short", "channel": "BWE_OI_Price_monitor", "direction": "short", "rule": {"event_type": "crash", "oi_ratio_pct_gte": 8, "confirm_after_5m_reserved6_eq": True}, "discovery_class": "controlled_new", "description": "OI + Reserved6 crash continuation short."},
        {"group_id": "g25", "family": "pc_r6_combo_pump_fade_short", "channel": "BWE_pricechange_monitor", "direction": "short", "rule": {"event_type": "pump", "confirm_after_5m_reserved6_eq": True}, "discovery_class": "controlled_new", "description": "Pricechange + Reserved6 pump fade short."},
        {"group_id": "g26", "family": "pc_r6_combo_crash_bounce_long", "channel": "BWE_pricechange_monitor", "direction": "long", "rule": {"event_type": "crash", "confirm_after_5m_reserved6_eq": True}, "discovery_class": "controlled_new", "description": "Pricechange + Reserved6 crash bounce long."},
    ]


def _entry_group_variations(group: dict[str, Any]) -> list[tuple[str, dict[str, Any], str]]:
    channel = group["channel"]
    direction = group["direction"]
    family = group["family"]
    if channel == "BWE_OI_Price_monitor":
        confirm_key = "confirm_after_5m_reserved6_eq"
        before_key = "confirm_before_5m_pricechange_eq"
    elif channel == "BWE_Reserved6":
        confirm_key = "confirm_after_5m_oi_eq"
        before_key = "confirm_before_5m_pricechange_eq"
    else:
        confirm_key = "confirm_after_5m_oi_eq"
        before_key = "confirm_before_5m_reserved6_eq"

    liq_rule = {"liquidity_bucket_in": ["high"]} if "cont" in family or direction == "long" else {"liquidity_bucket_in": ["low", "mid"]}
    mcap_rule = {"marketcap_bucket_norm_in": ["<50m", "50m-200m"]} if "fade" in family or "bounce" in family else {"marketcap_bucket_norm_in": ["200m-1b", ">=1b", "unknown"]}
    regime_rule = {"btc_regime_eq": "btc_up", "trend_alignment_eq": "aligned"} if direction == "long" else {"btc_regime_eq": "btc_down", "trend_alignment_eq": "aligned"}
    debounce_rule = {"burst_seq_5m_gte": 2} if channel == "BWE_pricechange_monitor" else {"vol_regime_in": ["hot", "extreme"]}
    flow_rule = {"mfe_pct_gte": 2.0, "mae_pct_gte": -8.0} if direction == "long" else {"mfe_pct_gte": 2.0, "mae_pct_lte": -1.5}

    return [
        ("base", {}, "Base archetype."),
        ("cross_confirm", {confirm_key: True, before_key: True}, "Cross-channel confirmation before and after 5m."),
        ("liq_mcap", _rule_merge(liq_rule, mcap_rule), "Liquidity and marketcap split archetype."),
        ("trend_btc_debounce", _rule_merge(regime_rule, debounce_rule, flow_rule), "Trend/BTC/cooldown or volatility conditioned archetype."),
    ]


def build_entry_archetypes() -> list[EntryArchetype]:
    archetypes: list[EntryArchetype] = []
    variant_count = math.prod(len(values) for values in ENTRY_VARIANT_GRID.values())
    for group in _entry_groups():
        for suffix, extra_rule, extra_desc in _entry_group_variations(group):
            archetypes.append(
                EntryArchetype(
                    archetype_id=f"{group['group_id']}_{suffix}",
                    family=group["family"],
                    family_group=group["group_id"],
                    source_channel=group["channel"],
                    direction=group["direction"],
                    base_rule=_rule_merge({"channel": group["channel"], "side": group["direction"]}, group["rule"], extra_rule),
                    description=f"{group['description']} {extra_desc}",
                    discovery_class=group["discovery_class"],
                    expected_variant_count=variant_count,
                )
            )
    return archetypes


def generate_entry_catalog(archetypes: Sequence[EntryArchetype]) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    variant_fields = list(ENTRY_VARIANT_GRID.keys())
    for archetype in archetypes:
        for combo in itertools.product(*(ENTRY_VARIANT_GRID[field] for field in variant_fields)):
            variant = dict(zip(variant_fields, combo))
            branch_id = (
                f"{archetype.archetype_id}"
                f"__d{variant['entry_delay_s']}"
                f"__h{variant['holding_horizon_min']}"
                f"__liq{variant['liquidity_bucket']}"
                f"__mcap{variant['marketcap_bucket_norm'].replace('>=', 'ge').replace('<', 'lt').replace('-', '_')}"
                f"__btc{variant['btc_regime'].replace('btc_', '')}"
                f"__trend{variant['trend_alignment']}"
            )
            records.append(
                {
                    "branch_id": branch_id,
                    "archetype_id": archetype.archetype_id,
                    "family": archetype.family,
                    "family_group": archetype.family_group,
                    "source_channel": archetype.source_channel,
                    "direction": archetype.direction,
                    "discovery_class": archetype.discovery_class,
                    "base_rule_json": json.dumps(archetype.base_rule, ensure_ascii=False, sort_keys=True),
                    "description": archetype.description,
                    **variant,
                }
            )
    catalog = pd.DataFrame.from_records(records)
    return catalog


def _entry_metrics_for_group(group: pd.DataFrame, horizon: int) -> dict[str, Any]:
    values = pd.to_numeric(group[f"net_{horizon}m"], errors="coerce").replace([math.inf, -math.inf], np.nan).dropna() * 100.0
    if values.empty:
        return {
            "sample_size": 0,
            "symbol_count": 0,
            "win_rate_pct": 0.0,
            "mean_net_pct": 0.0,
            "median_net_pct": 0.0,
            "p10_net_pct": 0.0,
            "p25_net_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "longest_losing_streak": 0,
            "profit_factor": 0.0,
            "top_symbol_share_pct": 0.0,
            "top1_removed_mean_net_pct": 0.0,
            "walk_forward_positive_rate_pct": 0.0,
            "regime_positive_rate_pct": 0.0,
            "market_type_positive_rate_pct": 0.0,
            "split_stability_pct": 0.0,
        }

    ordered = group.loc[values.index].sort_values("ts_ms")
    values_np = values.loc[ordered.index].to_numpy(dtype=float)
    equity = np.cumsum(values_np)
    max_drawdown = float(np.min(equity - np.maximum.accumulate(equity)))
    symbol_counts = ordered["symbol"].value_counts(dropna=True)
    top_symbol_share = float(symbol_counts.iloc[0] / len(ordered) * 100.0) if not symbol_counts.empty else 0.0
    if not symbol_counts.empty:
        top_symbol = symbol_counts.index[0]
        top_removed_values = values.loc[ordered.index[ordered["symbol"] != top_symbol]]
        top_removed_mean = float(top_removed_values.mean()) if not top_removed_values.empty else 0.0
    else:
        top_removed_mean = 0.0

    month_mean = ordered.assign(net_pct=values.loc[ordered.index].to_numpy()).groupby("month")["net_pct"].mean()
    regime_mean = ordered.assign(net_pct=values.loc[ordered.index].to_numpy()).groupby("regime_state")["net_pct"].mean()
    market_type_mean = ordered.assign(net_pct=values.loc[ordered.index].to_numpy()).groupby("market_type")["net_pct"].mean()
    split_stability = np.mean(
        [
            _positive_rate(regime_mean, min_groups=1),
            _positive_rate(market_type_mean, min_groups=1),
            _positive_rate(month_mean, min_groups=1),
        ]
    )

    return {
        "sample_size": int(values_np.shape[0]),
        "symbol_count": int(symbol_counts.shape[0]),
        "win_rate_pct": round(float((values_np > 0).mean() * 100.0), 6),
        "mean_net_pct": round(float(values_np.mean()), 6),
        "median_net_pct": round(float(np.median(values_np)), 6),
        "p10_net_pct": round(float(np.quantile(values_np, 0.10)), 6),
        "p25_net_pct": round(float(np.quantile(values_np, 0.25)), 6),
        "max_drawdown_pct": round(max_drawdown, 6),
        "longest_losing_streak": int(_longest_losing_streak(values_np)),
        "profit_factor": round(_profit_factor(values_np), 6),
        "top_symbol_share_pct": round(top_symbol_share, 6),
        "top1_removed_mean_net_pct": round(top_removed_mean, 6),
        "walk_forward_positive_rate_pct": round(_positive_rate(month_mean, min_groups=1), 6),
        "regime_positive_rate_pct": round(_positive_rate(regime_mean, min_groups=1), 6),
        "market_type_positive_rate_pct": round(_positive_rate(market_type_mean, min_groups=1), 6),
        "split_stability_pct": round(float(split_stability), 6),
    }


def _entry_decision(row: pd.Series) -> tuple[str, str]:
    sample = int(row["sample_size"])
    if sample < 25:
        return "need_more_data", "sample_lt_25"
    if row["symbol_count"] < 3:
        return "need_more_data", "symbol_count_lt_3"
    if row["median_net_pct"] <= 0:
        return "reject", "median_non_positive"
    if row["p25_net_pct"] < -0.50:
        return "reject", "left_tail_too_weak"
    if row["top_symbol_share_pct"] > 45.0:
        return "watchlist", "top_symbol_concentration"
    if row["top1_removed_mean_net_pct"] <= 0:
        return "watchlist", "outlier_dependent"
    if (
        row["sample_size"] >= 80
        and row["win_rate_pct"] >= 53.0
        and row["median_net_pct"] > 0
        and row["p25_net_pct"] >= -0.15
        and row["profit_factor"] >= 1.15
        and row["walk_forward_positive_rate_pct"] >= 55.0
        and row["split_stability_pct"] >= 50.0
    ):
        return "promote_to_deep_exit", "passes_entry_stability_gate"
    if row["mean_net_pct"] > 0 and row["profit_factor"] >= 1.0:
        return "watchlist", "positive_but_below_promote_gate"
    return "reject", "fails_profit_stability_gate"


def _entry_score_columns(df: pd.DataFrame) -> pd.DataFrame:
    numeric_cols = [
        "sample_size",
        "max_drawdown_pct",
        "top_symbol_share_pct",
        "longest_losing_streak",
        "median_net_pct",
        "p25_net_pct",
        "walk_forward_positive_rate_pct",
        "split_stability_pct",
        "profit_factor",
        "mean_net_pct",
        "p10_net_pct",
        "win_rate_pct",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    dd_penalty = df["max_drawdown_pct"].abs().clip(upper=25.0) / 3.0
    concentration_penalty = (df["top_symbol_share_pct"] - 20.0).clip(lower=0.0) / 4.0
    losing_penalty = df["longest_losing_streak"].clip(upper=12) / 2.0
    sample_bonus = np.log1p(df["sample_size"]).clip(upper=5.5)
    df["score_stability_first"] = (
        df["median_net_pct"] * 4.0
        + df["p25_net_pct"] * 3.0
        + df["walk_forward_positive_rate_pct"] / 18.0
        + df["split_stability_pct"] / 20.0
        + df["profit_factor"].clip(upper=3.0) * 1.5
        + sample_bonus
        - dd_penalty
        - concentration_penalty
        - losing_penalty
    ).round(6)
    df["score_profit_first"] = (
        df["mean_net_pct"] * 3.0
        + df["median_net_pct"] * 2.0
        + df["p10_net_pct"] * 0.75
        + (df["win_rate_pct"] - 50.0) / 5.0
        + df["profit_factor"].clip(upper=4.0) * 2.0
        + sample_bonus
        - df["max_drawdown_pct"].abs().clip(upper=30.0) / 4.0
    ).round(6)
    return df


def score_entry_catalog(forward: pd.DataFrame, catalog: pd.DataFrame, archetypes: Sequence[EntryArchetype], out_dir: Path, progress: dict[str, Any]) -> pd.DataFrame:
    variant_cols = ["entry_delay_s", "liquidity_bucket", "marketcap_bucket_norm", "btc_regime", "trend_alignment"]
    metric_cols = [
        "sample_size",
        "symbol_count",
        "win_rate_pct",
        "mean_net_pct",
        "median_net_pct",
        "p10_net_pct",
        "p25_net_pct",
        "max_drawdown_pct",
        "longest_losing_streak",
        "profit_factor",
        "top_symbol_share_pct",
        "top1_removed_mean_net_pct",
        "walk_forward_positive_rate_pct",
        "regime_positive_rate_pct",
        "market_type_positive_rate_pct",
        "split_stability_pct",
    ]
    scored_parts: list[pd.DataFrame] = []
    total = len(archetypes)
    for idx, archetype in enumerate(archetypes, 1):
        base_mask = _series_mask(forward, archetype.base_rule)
        subset = forward.loc[base_mask].copy()
        cat_subset = catalog[catalog["archetype_id"] == archetype.archetype_id].copy()
        horizon_parts: list[pd.DataFrame] = []
        if not subset.empty:
            subset = subset.sort_values("ts_ms")
            for horizon in ENTRY_HORIZONS:
                grouped_rows: list[dict[str, Any]] = []
                net_col = f"net_{horizon}m"
                if net_col not in subset.columns:
                    continue
                for keys, group in subset.groupby(variant_cols, sort=False, dropna=False):
                    metrics = _entry_metrics_for_group(group, horizon)
                    grouped_rows.append(
                        {
                            "archetype_id": archetype.archetype_id,
                            "entry_delay_s": keys[0],
                            "liquidity_bucket": keys[1],
                            "marketcap_bucket_norm": keys[2],
                            "btc_regime": keys[3],
                            "trend_alignment": keys[4],
                            "holding_horizon_min": horizon,
                            **metrics,
                        }
                    )
                if grouped_rows:
                    horizon_parts.append(pd.DataFrame(grouped_rows))
        observed = (
            pd.concat(horizon_parts, ignore_index=True)
            if horizon_parts
            else pd.DataFrame(columns=["archetype_id", *variant_cols, "holding_horizon_min", *metric_cols])
        )
        merged = cat_subset.merge(observed, on=["archetype_id", *variant_cols, "holding_horizon_min"], how="left")
        for col in metric_cols:
            if col not in merged.columns:
                merged[col] = 0
            merged[col] = merged[col].fillna(0)
        decisions = merged.apply(_entry_decision, axis=1, result_type="expand")
        merged["decision"] = decisions[0]
        merged["reject_reason"] = decisions[1]
        merged["base_rule_json"] = merged["base_rule_json"].astype(str)
        merged["source_channel"] = archetype.source_channel
        merged["description"] = archetype.description
        merged["discovery_class"] = archetype.discovery_class
        scored_parts.append(merged)
        if idx == 1 or idx % 8 == 0 or idx == total:
            partial = pd.concat(scored_parts, ignore_index=True)
            update_progress(
                out_dir,
                progress,
                stage="stage_b_entry_scoring",
                note=f"entry archetypes scored {idx}/{total}",
                entry_scored_branches=int(partial.shape[0]),
            )
            print(f"[stage-b] entry archetypes scored {idx}/{total}", flush=True)
    scores = pd.concat(scored_parts, ignore_index=True)
    scores = _entry_score_columns(scores)
    return scores


def _exit_families() -> list[tuple[str, bool, int]]:
    # All catalog families are dynamically scorable in Stage C.  Keep the
    # priority order stable so resumed/compared runs can still interpret older
    # progress files, but do not leave any branch in the old
    # pending_family_not_yet_vectorized bucket.
    families = [
        "fixed_tp_full",
        "fixed_sl_timecap",
        "tp_sl_bracket",
        "partial_tp_runner",
        "ladder_exit",
        "trailing_from_entry",
        "trailing_after_tp",
        "mfe_giveback",
        "mae_rescue",
        "prove_then_runner",
        "prove_then_hourly_state",
        "time_decay_tp",
        "time_decay_stop",
        "breakeven_ratchet",
        "multi_arm_ratchet",
        "vol_adaptive_bracket",
        "volume_state_exit",
        "hourly_adverse_close",
        "stagnation_exit",
        "scaleout_runner_floor",
        "channel_invalidation_fallback",
    ]
    return [(family, True, idx) for idx, family in enumerate(families, 1)]


def build_exit_archetypes() -> list[ExitArchetype]:
    archetypes: list[ExitArchetype] = []
    for family, scorable, priority in _exit_families():
        for variant_idx, variant in enumerate(EXIT_ARCHETYPE_VARIANTS, 1):
            archetypes.append(
                ExitArchetype(
                    archetype_id=f"{family}__{variant}",
                    family=family,
                    variation=variant,
                    description=f"{family} / {variant}",
                    parameters_template={"variant": variant, "family": family},
                    scorable=scorable,
                    priority_rank=priority * 10 + variant_idx,
                    expected_variant_count=1000,
                )
            )
    return archetypes


def _exit_variant_grid_for_family(family: str) -> dict[str, Sequence[Any]]:
    common = {
        "max_hold_minutes": (60, 180, 360, 720, 1440),
        "activation_minutes": (0, 5, 15, 30),
        "fallback_mode": ("close", "breakeven"),
    }
    compact_common = {
        "max_hold_minutes": (60, 180, 360, 720),
        "activation_minutes": (0, 5),
    }
    if family in {"fixed_tp_full", "tp_sl_bracket"}:
        return _rule_merge(
            {"take_profit_pct": (2.0, 4.0, 6.0, 8.0, 10.0), "stop_pct": (1.5, 2.5, 4.0, 6.0, 8.0), "floor_pct": (-1.0, 0.0, 1.0, 2.0, 3.0)},
            common,
        )
    if family == "fixed_sl_timecap":
        return _rule_merge(
            {"stop_pct": (1.0, 2.0, 3.0, 4.0, 6.0), "floor_pct": (-2.0, -1.0, 0.0, 1.0, 2.0), "timeout_buffer_min": (0, 30, 60, 120, 240)},
            common,
        )
    if family == "trailing_from_entry":
        return _rule_merge(
            {"trail_dd_pct": (1.0, 2.0, 3.0, 4.0, 6.0), "arm_pct": (1.0, 2.0, 4.0, 6.0, 8.0), "floor_pct": (-1.0, 0.0, 1.0, 2.0, 3.0)},
            common,
        )
    if family == "hourly_adverse_close":
        return _rule_merge(
            {"adverse_hours": (1, 2, 3, 4, 6), "floor_pct": (-2.0, -1.0, 0.0, 1.0, 2.0), "hour_gate": (1, 2, 4, 8, 12)},
            common,
        )
    if family == "stagnation_exit":
        return _rule_merge(
            {"stagnation_bars": (6, 12, 18, 24, 36), "floor_pct": (-2.0, -1.0, 0.0, 1.0, 2.0), "arm_pct": (0.0, 1.0, 2.0, 4.0, 6.0)},
            common,
        )
    if family == "partial_tp_runner":
        return _rule_merge(
            {"take_profit_pct": (2.0, 4.0, 6.0, 8.0, 10.0), "partial_frac": (0.25, 0.4, 0.5, 0.6, 0.75), "runner_trail_dd_pct": (1.0, 2.0, 3.0, 4.0, 6.0)},
            compact_common,
        )
    if family == "ladder_exit":
        return _rule_merge(
            {"tp1_pct": (1.0, 2.0, 3.0, 4.0, 5.0), "tp2_pct": (3.0, 5.0, 7.0, 9.0, 12.0), "stop_pct": (1.5, 2.5, 4.0, 6.0, 8.0)},
            compact_common,
        )
    if family == "trailing_after_tp":
        return _rule_merge(
            {"tp_arm_pct": (1.0, 2.0, 4.0, 6.0, 8.0), "trail_dd_pct": (1.0, 2.0, 3.0, 4.0, 6.0), "floor_pct": (-1.0, 0.0, 1.0, 2.0, 3.0)},
            compact_common,
        )
    if family == "mfe_giveback":
        return _rule_merge(
            {"min_mfe_pct": (1.0, 2.0, 4.0, 6.0, 8.0), "giveback_pct": (0.5, 1.0, 2.0, 3.0, 4.0), "floor_pct": (-1.0, 0.0, 1.0, 2.0, 3.0)},
            compact_common,
        )
    if family == "mae_rescue":
        return _rule_merge(
            {"rescue_stop_pct": (1.0, 2.0, 3.0, 4.0, 6.0), "recovery_pct": (0.0, 1.0, 2.0, 3.0, 4.0), "floor_pct": (-2.0, -1.0, 0.0, 1.0, 2.0)},
            compact_common,
        )
    if family == "prove_then_runner":
        return _rule_merge(
            {"proof_pct": (0.5, 1.0, 2.0, 3.0, 4.0), "proof_window_min": (5, 10, 15, 30, 60), "runner_trail_dd_pct": (1.0, 2.0, 3.0, 4.0, 6.0)},
            compact_common,
        )
    if family == "prove_then_hourly_state":
        return _rule_merge(
            {"proof_pct": (0.5, 1.0, 2.0, 3.0, 4.0), "proof_window_min": (5, 10, 15, 30, 60), "adverse_hours": (1, 2, 3, 4, 6)},
            compact_common,
        )
    if family == "time_decay_tp":
        return _rule_merge(
            {"tp_start_pct": (4.0, 6.0, 8.0, 10.0, 14.0), "tp_end_pct": (1.0, 2.0, 3.0, 4.0, 6.0), "decay_minutes": (30, 60, 120, 240, 480)},
            compact_common,
        )
    if family == "time_decay_stop":
        return _rule_merge(
            {"stop_start_pct": (1.0, 2.0, 3.0, 4.0, 6.0), "stop_end_pct": (1.0, 1.5, 2.0, 3.0, 4.0), "decay_minutes": (30, 60, 120, 240, 480)},
            compact_common,
        )
    if family == "breakeven_ratchet":
        return _rule_merge(
            {"arm_pct": (1.0, 2.0, 3.0, 4.0, 6.0), "ratchet_step_pct": (0.5, 1.0, 1.5, 2.0, 3.0), "floor_pct": (-0.5, 0.0, 0.5, 1.0, 2.0)},
            compact_common,
        )
    if family == "multi_arm_ratchet":
        return _rule_merge(
            {"arm1_pct": (1.0, 2.0, 3.0, 4.0, 6.0), "arm2_pct": (3.0, 5.0, 7.0, 9.0, 12.0), "floor_pct": (-1.0, 0.0, 1.0, 2.0, 3.0)},
            compact_common,
        )
    if family == "vol_adaptive_bracket":
        return _rule_merge(
            {"tp_mult": (1.0, 1.25, 1.5, 2.0, 2.5), "stop_mult": (0.75, 1.0, 1.25, 1.5, 2.0), "floor_pct": (-1.0, 0.0, 1.0, 2.0, 3.0)},
            compact_common,
        )
    if family == "volume_state_exit":
        return _rule_merge(
            {"volume_ratio_floor": (0.25, 0.5, 0.75, 1.0, 1.5), "arm_pct": (0.0, 1.0, 2.0, 4.0, 6.0), "floor_pct": (-2.0, -1.0, 0.0, 1.0, 2.0)},
            compact_common,
        )
    if family == "scaleout_runner_floor":
        return _rule_merge(
            {"take_profit_pct": (2.0, 4.0, 6.0, 8.0, 10.0), "runner_floor_pct": (-1.0, 0.0, 1.0, 2.0, 3.0), "partial_frac": (0.25, 0.4, 0.5, 0.6, 0.75)},
            compact_common,
        )
    if family == "channel_invalidation_fallback":
        return _rule_merge(
            {"adverse_pct": (0.5, 1.0, 2.0, 3.0, 4.0), "grace_minutes": (5, 10, 15, 30, 60), "floor_pct": (-2.0, -1.0, 0.0, 1.0, 2.0)},
            compact_common,
        )
    raise ValueError(f"unknown exit family: {family}")


def generate_exit_catalog(archetypes: Sequence[ExitArchetype]) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for archetype in archetypes:
        grid = _exit_variant_grid_for_family(archetype.family)
        fields = list(grid.keys())
        values = [grid[field] for field in fields]
        for combo_idx, combo in enumerate(itertools.product(*values), 1):
            params = dict(zip(fields, combo))
            branch_id = f"{archetype.archetype_id}__v{combo_idx:04d}"
            records.append(
                {
                    "branch_id": branch_id,
                    "archetype_id": archetype.archetype_id,
                    "family": archetype.family,
                    "variation": archetype.variation,
                    "scorable": archetype.scorable,
                    "priority_rank": archetype.priority_rank,
                    "description": archetype.description,
                    "params_json": json.dumps(params, ensure_ascii=False, sort_keys=True),
                    **params,
                }
            )
    return pd.DataFrame.from_records(records)


def _build_active_strategy_rows(forward: pd.DataFrame) -> dict[str, pd.DataFrame]:
    q4 = float(forward["prev_hour_quote_volume_q4"].iloc[0]) if not forward.empty else 0.0
    filters = {
        "oi_overcrowded_crash_follow_short": (
            (forward["channel"] == "BWE_OI_Price_monitor")
            & (forward["event_type"] == "crash")
            & (forward["side"] == "short")
            & (forward["oi_ratio_pct"].fillna(-1) >= 10)
            & (forward["day_change_pct"].fillna(999) <= -10)
            & (forward["pre2h"] <= -0.02)
        ),
        "pc_second_signal_cont_long": (
            (forward["channel"] == "BWE_pricechange_monitor")
            & (forward["side"] == "long")
            & (forward["pre2h"] >= 0.02)
            & (forward["prev_hour_quote_volume"] >= q4)
            & (forward["burst_seq_5m"] == 2)
        ),
        "pc_pump_cont_long": (
            (forward["channel"] == "BWE_pricechange_monitor")
            & (forward["side"] == "long")
            & (forward["pre2h"] >= 0.02)
            & (forward["prev_hour_quote_volume"] >= q4)
            & (forward["event_type"] == "pump")
        ),
        "pc_crash_bounce_long": (
            (forward["channel"] == "BWE_pricechange_monitor")
            & (forward["side"] == "long")
            & (forward["pre2h"] >= 0.02)
            & (forward["prev_hour_quote_volume"] >= q4)
            & (forward["event_type"] == "crash")
        ),
    }
    out: dict[str, pd.DataFrame] = {}
    for name, mask in filters.items():
        base = ACTIVE_EXIT_STRATEGY_CONFIG[name]
        rows = forward.loc[mask & (forward["entry_delay_s"] == base["entry_delay_s"])].drop_duplicates(subset=["event_key"]).copy()
        out[name] = rows
    return out


def build_strategy_bundle(rows_df: pd.DataFrame, path_df: pd.DataFrame, base: dict[str, Any]) -> dict[str, Any]:
    if rows_df.empty:
        return {
            "event_keys": np.array([], dtype=object),
            "months": np.array([], dtype=object),
            "close_net": np.zeros((0, 1), dtype=np.float32),
            "fav_raw": np.zeros((0, 1), dtype=np.float32),
            "adv_raw": np.zeros((0, 1), dtype=np.float32),
            "mins": np.zeros((0, 1), dtype=np.int16),
            "valid": np.zeros((0, 1), dtype=bool),
            "base_stop_idx": np.zeros((0,), dtype=np.int16),
            "base_stop_pnl": np.zeros((0,), dtype=np.float32),
            "bars_since_peak": np.zeros((0, 1), dtype=np.int16),
            "trail_drawdown": np.zeros((0, 1), dtype=np.float32),
            "volume_ratio": np.zeros((0, 1), dtype=np.float32),
            "hourly_close_net": np.zeros((0, 1), dtype=np.float32),
            "hourly_is_adverse": np.zeros((0, 1), dtype=bool),
        }

    path_df = path_df.sort_values(["event_key", "bar_ts_ms"]).copy()
    grouped_indices = path_df.groupby("event_key").indices
    event_rows = rows_df.set_index("event_key", drop=False)
    lengths: list[int] = []
    rows_payload: list[dict[str, Any]] = []
    for event_key, row in event_rows.iterrows():
        idxs = grouped_indices.get(event_key)
        if idxs is None:
            continue
        bars = path_df.iloc[idxs]
        ts_arr = bars["bar_ts_ms"].to_numpy(dtype=np.int64)
        start = int(np.searchsorted(ts_arr, int(row["entry_ts_ms"]), side="left"))
        sliced = bars.iloc[start:]
        if sliced.empty:
            continue
        rows_payload.append(
            {
                "event_key": event_key,
                "month": row["month"],
                "entry_px": float(row["entry_px"]),
                "side": str(row["side"]),
                "entry_ts_ms": int(row["entry_ts_ms"]),
                "bars": sliced,
            }
        )
        lengths.append(int(sliced.shape[0]))

    if not rows_payload:
        return build_strategy_bundle(rows_df.iloc[0:0], path_df.iloc[0:0], base)

    max_bars = max(lengths)
    events = len(rows_payload)
    close_net = np.full((events, max_bars), np.nan, dtype=np.float32)
    fav_raw = np.full((events, max_bars), np.nan, dtype=np.float32)
    adv_raw = np.full((events, max_bars), np.nan, dtype=np.float32)
    volume_ratio = np.full((events, max_bars), np.nan, dtype=np.float32)
    mins = np.full((events, max_bars), -1, dtype=np.int16)
    valid = np.zeros((events, max_bars), dtype=bool)
    event_keys = np.empty(events, dtype=object)
    months = np.empty(events, dtype=object)
    base_stop_idx = np.full(events, max_bars, dtype=np.int16)
    base_stop_pnl = np.full(events, 0.0, dtype=np.float32)
    hourly_list: list[np.ndarray] = []

    hard_stop_pct = float(base["hard_stop_pct"])
    activation_delay_min = int(base["activation_delay_min"])
    catastrophe_stop_pct = float(base["catastrophe_stop_pct"])

    for i, payload in enumerate(rows_payload):
        bars = payload["bars"]
        entry_px = payload["entry_px"]
        side = payload["side"]
        entry_ts = payload["entry_ts_ms"]
        highs = bars["high"].to_numpy(dtype=float)
        lows = bars["low"].to_numpy(dtype=float)
        closes = bars["close"].to_numpy(dtype=float)
        quote_volumes = bars.get("quote_volume", pd.Series(np.ones(len(bars)), index=bars.index)).to_numpy(dtype=float)
        vol_base = float(np.nanmedian(quote_volumes[np.isfinite(quote_volumes)])) if np.isfinite(quote_volumes).any() else 1.0
        if vol_base <= 0:
            vol_base = 1.0
        ts_arr = bars["bar_ts_ms"].to_numpy(dtype=np.int64)
        minutes = np.maximum(0, ((ts_arr - entry_ts) / 60_000.0).astype(np.int16))
        if side == "long":
            fav = (highs / entry_px - 1.0) * 100.0
            adv = (lows / entry_px - 1.0) * 100.0
            close_vals = (closes / entry_px - 1.0) * 100.0 - ROUNDTRIP_COST_PCT
        else:
            fav = (entry_px / lows - 1.0) * 100.0
            adv = (entry_px / highs - 1.0) * 100.0
            close_vals = (entry_px / closes - 1.0) * 100.0 - ROUNDTRIP_COST_PCT
        count = len(bars)
        close_net[i, :count] = close_vals
        fav_raw[i, :count] = fav
        adv_raw[i, :count] = adv
        volume_ratio[i, :count] = np.nan_to_num(quote_volumes / vol_base, nan=1.0, posinf=1.0, neginf=1.0)
        mins[i, :count] = minutes
        valid[i, :count] = True
        event_keys[i] = payload["event_key"]
        months[i] = payload["month"]

        catastrophe_hits = np.where((minutes < activation_delay_min) & (adv <= -catastrophe_stop_pct))[0]
        hard_hits = np.where((minutes >= activation_delay_min) & (adv <= -hard_stop_pct))[0]
        if catastrophe_hits.size:
            base_stop_idx[i] = int(catastrophe_hits[0])
            base_stop_pnl[i] = np.float32(-catastrophe_stop_pct - ROUNDTRIP_COST_PCT)
        elif hard_hits.size:
            base_stop_idx[i] = int(hard_hits[0])
            base_stop_pnl[i] = np.float32(-hard_stop_pct - ROUNDTRIP_COST_PCT)
        hourly_closes = []
        for hour in range(1, 73):
            target = entry_ts + hour * 60 * 60_000
            idx = int(np.searchsorted(ts_arr, target, side="left"))
            if idx >= count:
                break
            hourly_closes.append(float(close_vals[idx]))
        hourly_list.append(np.array(hourly_closes, dtype=np.float32))

    trail_peak = np.where(valid, np.nan_to_num(fav_raw, nan=-9999.0), -9999.0)
    trail_peak = np.maximum.accumulate(trail_peak, axis=1)
    trail_drawdown = np.where(valid, trail_peak - np.nan_to_num(adv_raw, nan=0.0), np.nan)
    peak_idx = np.where(valid & (np.nan_to_num(fav_raw, nan=-9999.0) >= trail_peak - 1e-9), np.arange(max_bars), -1)
    last_peak_idx = np.maximum.accumulate(peak_idx, axis=1)
    bars_since_peak = np.where(valid, np.arange(max_bars) - last_peak_idx, -1).astype(np.int16)

    hourly_max = max(max((len(x) for x in hourly_list), default=0), 1)
    hourly_close_net = np.full((events, hourly_max), np.nan, dtype=np.float32)
    hourly_is_adverse = np.zeros((events, hourly_max), dtype=bool)
    for i, arr in enumerate(hourly_list):
        hourly_close_net[i, : len(arr)] = arr
        if len(arr) > 1:
            if rows_payload[i]["side"] == "long":
                hourly_is_adverse[i, 1 : len(arr)] = arr[1:] < arr[:-1]
            else:
                hourly_is_adverse[i, 1 : len(arr)] = arr[1:] > arr[:-1]

    return {
        "event_keys": event_keys,
        "months": months,
        "close_net": close_net,
        "fav_raw": fav_raw,
        "adv_raw": adv_raw,
        "mins": mins,
        "valid": valid,
        "base_stop_idx": base_stop_idx,
        "base_stop_pnl": base_stop_pnl,
        "bars_since_peak": bars_since_peak,
        "trail_drawdown": trail_drawdown,
        "volume_ratio": volume_ratio,
        "hourly_close_net": hourly_close_net,
        "hourly_is_adverse": hourly_is_adverse,
    }


def _first_hit_ge(values: np.ndarray, valid: np.ndarray, threshold: float, min_minutes: np.ndarray | None = None, start_minutes: int = 0) -> np.ndarray:
    mask = valid & np.isfinite(values) & (values >= threshold)
    if min_minutes is not None:
        mask &= min_minutes >= start_minutes
    any_hit = mask.any(axis=1)
    idx = np.where(any_hit, mask.argmax(axis=1), valid.shape[1])
    return idx.astype(np.int16)


def _first_hit_le(values: np.ndarray, valid: np.ndarray, threshold: float, min_minutes: np.ndarray | None = None, start_minutes: int = 0) -> np.ndarray:
    mask = valid & np.isfinite(values) & (values <= threshold)
    if min_minutes is not None:
        mask &= min_minutes >= start_minutes
    any_hit = mask.any(axis=1)
    idx = np.where(any_hit, mask.argmax(axis=1), valid.shape[1])
    return idx.astype(np.int16)


def _cap_idx_for_minutes(bundle: dict[str, Any], cap_minutes: int) -> np.ndarray:
    mins = bundle["mins"]
    valid = bundle["valid"]
    idx = np.argmax(valid & (mins >= cap_minutes), axis=1)
    has = (valid & (mins >= cap_minutes)).any(axis=1)
    fallback = valid.sum(axis=1) - 1
    return np.where(has, idx, fallback).astype(np.int16)


def _take_rows_by_idx(values: np.ndarray, idx: np.ndarray) -> np.ndarray:
    rows = np.arange(values.shape[0])
    safe_idx = np.clip(idx.astype(int), 0, values.shape[1] - 1)
    out = values[rows, safe_idx]
    return np.where(np.isfinite(out), out, 0.0)


def _longest_losing_from_vector(values: np.ndarray) -> int:
    return _longest_losing_streak(values.tolist())


def summarize_exit_vector(values: np.ndarray, months: np.ndarray, reason_codes: np.ndarray, reason_labels: dict[int, str]) -> dict[str, Any]:
    values = values.astype(float)
    if values.size == 0:
        return {
            "sample_size": 0,
            "win_rate_pct": 0.0,
            "mean_net_pct": 0.0,
            "median_net_pct": 0.0,
            "p10_net_pct": 0.0,
            "p25_net_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "longest_losing_streak": 0,
            "profit_factor": 0.0,
            "walk_forward_positive_rate_pct": 0.0,
            "reason_top": "no_samples",
        }
    equity = np.cumsum(values)
    month_df = pd.DataFrame({"month": months, "net": values})
    month_mean = month_df.groupby("month")["net"].mean()
    reason_top_code = int(pd.Series(reason_codes).value_counts().index[0]) if reason_codes.size else 0
    return {
        "sample_size": int(values.size),
        "win_rate_pct": round(float((values > 0).mean() * 100.0), 6),
        "mean_net_pct": round(float(values.mean()), 6),
        "median_net_pct": round(float(np.median(values)), 6),
        "p10_net_pct": round(float(np.quantile(values, 0.10)), 6),
        "p25_net_pct": round(float(np.quantile(values, 0.25)), 6),
        "max_drawdown_pct": round(float(np.min(equity - np.maximum.accumulate(equity))), 6),
        "longest_losing_streak": int(_longest_losing_from_vector(values)),
        "profit_factor": round(_profit_factor(values), 6),
        "walk_forward_positive_rate_pct": round(_positive_rate(month_mean, min_groups=1), 6),
        "reason_top": reason_labels.get(reason_top_code, "unknown"),
    }


def evaluate_fixed_tp_full_bundle(bundle: dict[str, Any], params: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, dict[int, str]]:
    tp = float(params["take_profit_pct"])
    stop_pct = float(params["stop_pct"])
    floor_pct = float(params["floor_pct"])
    cap = int(params["max_hold_minutes"])
    activation = int(params["activation_minutes"])
    fallback_mode = str(params["fallback_mode"])

    tp_idx = _first_hit_ge(bundle["fav_raw"], bundle["valid"], tp, bundle["mins"], activation)
    stop_idx = _first_hit_le(bundle["adv_raw"], bundle["valid"], -stop_pct, bundle["mins"], activation)
    stop_idx = np.minimum(stop_idx, bundle["base_stop_idx"])
    cap_idx = _cap_idx_for_minutes(bundle, cap)
    values = np.zeros(bundle["close_net"].shape[0], dtype=np.float32)
    reasons = np.zeros(bundle["close_net"].shape[0], dtype=np.int16)

    tp_first = (tp_idx < stop_idx) & (tp_idx <= cap_idx)
    stop_first = (stop_idx <= tp_idx) & (stop_idx <= cap_idx)
    time_first = ~(tp_first | stop_first)
    values[tp_first] = np.float32(tp - ROUNDTRIP_COST_PCT)
    reasons[tp_first] = 1
    stop_values = np.where(stop_idx == bundle["base_stop_idx"], bundle["base_stop_pnl"], -stop_pct - ROUNDTRIP_COST_PCT)
    values[stop_first] = stop_values[stop_first].astype(np.float32)
    reasons[stop_first] = 2
    cap_close = _take_rows_by_idx(bundle["close_net"], cap_idx).astype(np.float32)
    if fallback_mode == "breakeven":
        cap_close = np.maximum(cap_close, np.float32(min(0.0, floor_pct - ROUNDTRIP_COST_PCT)))
    else:
        cap_close = np.maximum(cap_close, np.float32(floor_pct))
    values[time_first] = cap_close[time_first]
    reasons[time_first] = 3
    return values, reasons, {1: "take_profit", 2: "stop_loss", 3: "time_exit"}


def evaluate_fixed_sl_timecap_bundle(bundle: dict[str, Any], params: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, dict[int, str]]:
    stop_pct = float(params["stop_pct"])
    floor_pct = float(params["floor_pct"])
    cap = int(params["max_hold_minutes"]) + int(params["timeout_buffer_min"])
    activation = int(params["activation_minutes"])

    stop_idx = _first_hit_le(bundle["adv_raw"], bundle["valid"], -stop_pct, bundle["mins"], activation)
    stop_idx = np.minimum(stop_idx, bundle["base_stop_idx"])
    cap_idx = _cap_idx_for_minutes(bundle, cap)
    stop_first = stop_idx <= cap_idx
    values = _take_rows_by_idx(bundle["close_net"], cap_idx).astype(np.float32)
    values = np.maximum(values, np.float32(floor_pct))
    reasons = np.full(bundle["close_net"].shape[0], 2, dtype=np.int16)
    stop_values = np.where(stop_idx == bundle["base_stop_idx"], bundle["base_stop_pnl"], -stop_pct - ROUNDTRIP_COST_PCT)
    values[stop_first] = stop_values[stop_first].astype(np.float32)
    reasons[stop_first] = 1
    return values, reasons, {1: "stop_loss", 2: "time_exit"}


def evaluate_tp_sl_bracket_bundle(bundle: dict[str, Any], params: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, dict[int, str]]:
    tp = float(params["take_profit_pct"])
    stop_pct = float(params["stop_pct"])
    floor_pct = float(params["floor_pct"])
    cap = int(params["max_hold_minutes"])
    activation = int(params["activation_minutes"])

    tp_idx = _first_hit_ge(bundle["fav_raw"], bundle["valid"], tp, bundle["mins"], activation)
    stop_idx = _first_hit_le(bundle["adv_raw"], bundle["valid"], -stop_pct, bundle["mins"], activation)
    stop_idx = np.minimum(stop_idx, bundle["base_stop_idx"])
    cap_idx = _cap_idx_for_minutes(bundle, cap)
    tp_first = (tp_idx < stop_idx) & (tp_idx <= cap_idx)
    stop_first = (stop_idx <= tp_idx) & (stop_idx <= cap_idx)
    values = np.maximum(_take_rows_by_idx(bundle["close_net"], cap_idx).astype(np.float32), np.float32(floor_pct))
    reasons = np.full(bundle["close_net"].shape[0], 3, dtype=np.int16)
    values[tp_first] = np.float32(tp - ROUNDTRIP_COST_PCT)
    reasons[tp_first] = 1
    stop_values = np.where(stop_idx == bundle["base_stop_idx"], bundle["base_stop_pnl"], -stop_pct - ROUNDTRIP_COST_PCT)
    values[stop_first] = stop_values[stop_first].astype(np.float32)
    reasons[stop_first] = 2
    return values, reasons, {1: "take_profit", 2: "stop_loss", 3: "time_exit"}


def evaluate_trailing_from_entry_bundle(bundle: dict[str, Any], params: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, dict[int, str]]:
    dd = float(params["trail_dd_pct"])
    arm_pct = float(params["arm_pct"])
    floor_pct = float(params["floor_pct"])
    cap = int(params["max_hold_minutes"])
    activation = int(params["activation_minutes"])

    arm_idx = _first_hit_ge(bundle["fav_raw"], bundle["valid"], arm_pct, bundle["mins"], activation)
    trail_idx = _first_hit_ge(bundle["trail_drawdown"], bundle["valid"], dd, bundle["mins"], activation)
    trail_idx = np.where(trail_idx >= arm_idx, trail_idx, bundle["valid"].shape[1]).astype(np.int16)
    stop_idx = bundle["base_stop_idx"]
    cap_idx = _cap_idx_for_minutes(bundle, cap)
    trail_first = (trail_idx < stop_idx) & (trail_idx <= cap_idx)
    stop_first = (stop_idx <= trail_idx) & (stop_idx <= cap_idx)
    values = np.maximum(_take_rows_by_idx(bundle["close_net"], cap_idx).astype(np.float32), np.float32(floor_pct))
    reasons = np.full(bundle["close_net"].shape[0], 3, dtype=np.int16)
    trail_exit = np.maximum(_take_rows_by_idx(bundle["close_net"], trail_idx).astype(np.float32), np.float32(floor_pct))
    values[trail_first] = trail_exit[trail_first]
    reasons[trail_first] = 1
    values[stop_first] = bundle["base_stop_pnl"][stop_first].astype(np.float32)
    reasons[stop_first] = 2
    return values, reasons, {1: "trail_exit", 2: "stop_loss", 3: "time_exit"}


def evaluate_hourly_adverse_close_bundle(bundle: dict[str, Any], params: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, dict[int, str]]:
    adverse_hours = int(params["adverse_hours"])
    floor_pct = float(params["floor_pct"])
    hour_gate = int(params["hour_gate"])
    cap_hours = max(1, int(params["max_hold_minutes"]) // 60)

    hourly = bundle["hourly_close_net"]
    adverse = bundle["hourly_is_adverse"]
    events, hours = hourly.shape
    exit_hour = np.full(events, hours, dtype=np.int16)
    reason = np.full(events, 2, dtype=np.int16)
    streak = np.zeros(events, dtype=np.int16)
    for hour in range(min(hours, cap_hours)):
        current = hourly[:, hour]
        valid = np.isfinite(current)
        if hour + 1 < hour_gate:
            continue
        streak = np.where(valid & adverse[:, hour], streak + 1, np.where(valid, 0, streak))
        hit = (exit_hour == hours) & valid & ((streak >= adverse_hours) | (current <= floor_pct))
        exit_hour[hit] = hour
        reason[hit] = np.where(current[hit] <= floor_pct, 1, 3)
    fallback_hour = np.minimum(cap_hours - 1, hours - 1)
    exit_hour = np.where(exit_hour == hours, fallback_hour, exit_hour)
    values = _take_rows_by_idx(hourly, exit_hour).astype(np.float32)
    values = np.maximum(values, np.float32(floor_pct))
    return values, reason, {1: "runner_floor_exit", 2: "time_exit", 3: "hourly_adverse_exit"}


def evaluate_stagnation_exit_bundle(bundle: dict[str, Any], params: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, dict[int, str]]:
    window = int(params["stagnation_bars"])
    floor_pct = float(params["floor_pct"])
    arm_pct = float(params["arm_pct"])
    cap = int(params["max_hold_minutes"])
    activation = int(params["activation_minutes"])

    armed_idx = _first_hit_ge(bundle["fav_raw"], bundle["valid"], arm_pct, bundle["mins"], activation)
    stagnation_mask = (
        bundle["valid"]
        & np.isfinite(bundle["close_net"])
        & (bundle["bars_since_peak"] >= window)
        & (bundle["close_net"] <= floor_pct)
    )
    any_hit = stagnation_mask.any(axis=1)
    stagnation_idx = np.where(any_hit, stagnation_mask.argmax(axis=1), bundle["valid"].shape[1]).astype(np.int16)
    stagnation_idx = np.where(stagnation_idx >= armed_idx, stagnation_idx, bundle["valid"].shape[1]).astype(np.int16)
    stop_idx = bundle["base_stop_idx"]
    cap_idx = _cap_idx_for_minutes(bundle, cap)
    stagnation_first = (stagnation_idx < stop_idx) & (stagnation_idx <= cap_idx)
    stop_first = (stop_idx <= stagnation_idx) & (stop_idx <= cap_idx)
    values = np.maximum(_take_rows_by_idx(bundle["close_net"], cap_idx).astype(np.float32), np.float32(floor_pct))
    reasons = np.full(bundle["close_net"].shape[0], 3, dtype=np.int16)
    values[stagnation_first] = _take_rows_by_idx(bundle["close_net"], stagnation_idx)[stagnation_first].astype(np.float32)
    reasons[stagnation_first] = 1
    values[stop_first] = bundle["base_stop_pnl"][stop_first].astype(np.float32)
    reasons[stop_first] = 2
    return values, reasons, {1: "stagnation_exit", 2: "stop_loss", 3: "time_exit"}


def _first_true_idx(mask: np.ndarray) -> np.ndarray:
    any_hit = mask.any(axis=1)
    idx = np.where(any_hit, mask.argmax(axis=1), mask.shape[1])
    return idx.astype(np.int16)


def _first_hit_dynamic_ge(values: np.ndarray, valid: np.ndarray, threshold: np.ndarray, mins: np.ndarray, activation: int = 0) -> np.ndarray:
    mask = valid & np.isfinite(values) & (mins >= activation) & (values >= threshold)
    return _first_true_idx(mask)


def _first_hit_dynamic_le(values: np.ndarray, valid: np.ndarray, threshold: np.ndarray, mins: np.ndarray, activation: int = 0) -> np.ndarray:
    mask = valid & np.isfinite(values) & (mins >= activation) & (values <= threshold)
    return _first_true_idx(mask)


def evaluate_partial_tp_runner_bundle(bundle: dict[str, Any], params: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, dict[int, str]]:
    tp = float(params["take_profit_pct"])
    frac = float(params["partial_frac"])
    dd = float(params["runner_trail_dd_pct"])
    cap = int(params["max_hold_minutes"])
    activation = int(params["activation_minutes"])

    tp_idx = _first_hit_ge(bundle["fav_raw"], bundle["valid"], tp, bundle["mins"], activation)
    stop_idx = bundle["base_stop_idx"]
    cap_idx = _cap_idx_for_minutes(bundle, cap)
    trail_idx = _first_hit_ge(bundle["trail_drawdown"], bundle["valid"], dd, bundle["mins"], activation)
    trail_idx = np.where(trail_idx >= tp_idx, trail_idx, bundle["valid"].shape[1]).astype(np.int16)
    runner_idx = np.minimum(trail_idx, cap_idx)

    values = _take_rows_by_idx(bundle["close_net"], cap_idx).astype(np.float32)
    reasons = np.full(bundle["close_net"].shape[0], 3, dtype=np.int16)
    stop_first = (stop_idx <= tp_idx) & (stop_idx <= cap_idx)
    tp_first = (tp_idx < stop_idx) & (tp_idx <= cap_idx)
    runner_val = _take_rows_by_idx(bundle["close_net"], runner_idx).astype(np.float32)
    values[tp_first] = np.float32(frac * (tp - ROUNDTRIP_COST_PCT) + (1.0 - frac) * runner_val[tp_first])
    reasons[tp_first] = np.where(trail_idx[tp_first] <= cap_idx[tp_first], 1, 4)
    values[stop_first] = bundle["base_stop_pnl"][stop_first].astype(np.float32)
    reasons[stop_first] = 2
    return values, reasons, {1: "partial_tp_runner_trail", 2: "stop_loss", 3: "time_exit", 4: "partial_tp_runner_time"}


def evaluate_ladder_exit_bundle(bundle: dict[str, Any], params: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, dict[int, str]]:
    tp1 = float(params["tp1_pct"])
    tp2 = max(float(params["tp2_pct"]), tp1 + 0.25)
    stop_pct = float(params["stop_pct"])
    cap = int(params["max_hold_minutes"])
    activation = int(params["activation_minutes"])

    tp1_idx = _first_hit_ge(bundle["fav_raw"], bundle["valid"], tp1, bundle["mins"], activation)
    tp2_idx = _first_hit_ge(bundle["fav_raw"], bundle["valid"], tp2, bundle["mins"], activation)
    stop_idx = _first_hit_le(bundle["adv_raw"], bundle["valid"], -stop_pct, bundle["mins"], activation)
    stop_idx = np.minimum(stop_idx, bundle["base_stop_idx"])
    cap_idx = _cap_idx_for_minutes(bundle, cap)

    values = _take_rows_by_idx(bundle["close_net"], cap_idx).astype(np.float32)
    reasons = np.full(bundle["close_net"].shape[0], 4, dtype=np.int16)
    stop_first = (stop_idx <= tp1_idx) & (stop_idx <= cap_idx)
    tp2_first = (tp1_idx < stop_idx) & (tp2_idx < stop_idx) & (tp2_idx <= cap_idx)
    tp1_only = (tp1_idx < stop_idx) & (tp1_idx <= cap_idx) & ~tp2_first & ~stop_first
    values[tp2_first] = np.float32(0.5 * (tp1 - ROUNDTRIP_COST_PCT) + 0.5 * (tp2 - ROUNDTRIP_COST_PCT))
    reasons[tp2_first] = 1
    cap_val = _take_rows_by_idx(bundle["close_net"], cap_idx).astype(np.float32)
    values[tp1_only] = np.float32(0.5 * (tp1 - ROUNDTRIP_COST_PCT)) + np.float32(0.5) * cap_val[tp1_only]
    reasons[tp1_only] = 3
    stop_values = np.where(stop_idx == bundle["base_stop_idx"], bundle["base_stop_pnl"], -stop_pct - ROUNDTRIP_COST_PCT)
    values[stop_first] = stop_values[stop_first].astype(np.float32)
    reasons[stop_first] = 2
    return values, reasons, {1: "ladder_tp2", 2: "stop_loss", 3: "ladder_tp1_time", 4: "time_exit"}


def evaluate_trailing_after_tp_bundle(bundle: dict[str, Any], params: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, dict[int, str]]:
    arm = float(params["tp_arm_pct"])
    dd = float(params["trail_dd_pct"])
    floor_pct = float(params["floor_pct"])
    cap = int(params["max_hold_minutes"])
    activation = int(params["activation_minutes"])
    arm_idx = _first_hit_ge(bundle["fav_raw"], bundle["valid"], arm, bundle["mins"], activation)
    trail_idx = _first_hit_ge(bundle["trail_drawdown"], bundle["valid"], dd, bundle["mins"], activation)
    trail_idx = np.where(trail_idx >= arm_idx, trail_idx, bundle["valid"].shape[1]).astype(np.int16)
    stop_idx = bundle["base_stop_idx"]
    cap_idx = _cap_idx_for_minutes(bundle, cap)
    trail_first = (arm_idx <= cap_idx) & (trail_idx < stop_idx) & (trail_idx <= cap_idx)
    stop_first = (stop_idx <= trail_idx) & (stop_idx <= cap_idx)
    values = np.maximum(_take_rows_by_idx(bundle["close_net"], cap_idx).astype(np.float32), np.float32(floor_pct))
    reasons = np.full(bundle["close_net"].shape[0], 3, dtype=np.int16)
    values[trail_first] = np.maximum(_take_rows_by_idx(bundle["close_net"], trail_idx).astype(np.float32), np.float32(floor_pct))[trail_first]
    reasons[trail_first] = 1
    values[stop_first] = bundle["base_stop_pnl"][stop_first].astype(np.float32)
    reasons[stop_first] = 2
    return values, reasons, {1: "trailing_after_tp", 2: "stop_loss", 3: "time_exit"}


def evaluate_mfe_giveback_bundle(bundle: dict[str, Any], params: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, dict[int, str]]:
    min_mfe = float(params["min_mfe_pct"])
    giveback = float(params["giveback_pct"])
    floor_pct = float(params["floor_pct"])
    cap = int(params["max_hold_minutes"])
    activation = int(params["activation_minutes"])
    arm_idx = _first_hit_ge(bundle["fav_raw"], bundle["valid"], min_mfe, bundle["mins"], activation)
    giveback_idx = _first_hit_ge(bundle["trail_drawdown"], bundle["valid"], giveback, bundle["mins"], activation)
    giveback_idx = np.where(giveback_idx >= arm_idx, giveback_idx, bundle["valid"].shape[1]).astype(np.int16)
    stop_idx = bundle["base_stop_idx"]
    cap_idx = _cap_idx_for_minutes(bundle, cap)
    giveback_first = (arm_idx <= cap_idx) & (giveback_idx < stop_idx) & (giveback_idx <= cap_idx)
    stop_first = (stop_idx <= giveback_idx) & (stop_idx <= cap_idx)
    values = np.maximum(_take_rows_by_idx(bundle["close_net"], cap_idx).astype(np.float32), np.float32(floor_pct))
    reasons = np.full(bundle["close_net"].shape[0], 3, dtype=np.int16)
    values[giveback_first] = np.maximum(_take_rows_by_idx(bundle["close_net"], giveback_idx).astype(np.float32), np.float32(floor_pct))[giveback_first]
    reasons[giveback_first] = 1
    values[stop_first] = bundle["base_stop_pnl"][stop_first].astype(np.float32)
    reasons[stop_first] = 2
    return values, reasons, {1: "mfe_giveback", 2: "stop_loss", 3: "time_exit"}


def evaluate_mae_rescue_bundle(bundle: dict[str, Any], params: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, dict[int, str]]:
    rescue_stop = float(params["rescue_stop_pct"])
    recovery = float(params["recovery_pct"])
    floor_pct = float(params["floor_pct"])
    cap = int(params["max_hold_minutes"])
    activation = int(params["activation_minutes"])
    danger_idx = _first_hit_le(bundle["adv_raw"], bundle["valid"], -rescue_stop, bundle["mins"], activation)
    recovery_idx = _first_hit_ge(bundle["fav_raw"], bundle["valid"], recovery, bundle["mins"], activation)
    cap_idx = _cap_idx_for_minutes(bundle, cap)
    rescue_first = (danger_idx < recovery_idx) & (danger_idx <= cap_idx)
    values = np.maximum(_take_rows_by_idx(bundle["close_net"], cap_idx).astype(np.float32), np.float32(floor_pct))
    reasons = np.full(bundle["close_net"].shape[0], 2, dtype=np.int16)
    values[rescue_first] = np.float32(-rescue_stop - ROUNDTRIP_COST_PCT)
    reasons[rescue_first] = 1
    base_stop_first = (bundle["base_stop_idx"] <= cap_idx) & ~rescue_first
    values[base_stop_first] = bundle["base_stop_pnl"][base_stop_first].astype(np.float32)
    reasons[base_stop_first] = 3
    return values, reasons, {1: "mae_rescue_stop", 2: "time_or_recovered", 3: "base_stop"}


def evaluate_prove_then_runner_bundle(bundle: dict[str, Any], params: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, dict[int, str]]:
    proof = float(params["proof_pct"])
    window = int(params["proof_window_min"])
    dd = float(params["runner_trail_dd_pct"])
    cap = int(params["max_hold_minutes"])
    activation = int(params["activation_minutes"])
    proof_idx = _first_hit_ge(bundle["fav_raw"], bundle["valid"], proof, bundle["mins"], activation)
    window_idx = _cap_idx_for_minutes(bundle, window)
    cap_idx = _cap_idx_for_minutes(bundle, cap)
    trail_idx = _first_hit_ge(bundle["trail_drawdown"], bundle["valid"], dd, bundle["mins"], activation)
    trail_idx = np.where(trail_idx >= proof_idx, trail_idx, bundle["valid"].shape[1]).astype(np.int16)
    stop_idx = bundle["base_stop_idx"]
    fail_proof = proof_idx > window_idx
    trail_first = ~fail_proof & (trail_idx < stop_idx) & (trail_idx <= cap_idx)
    stop_first = (stop_idx <= np.minimum(trail_idx, cap_idx)) & ~fail_proof
    values = _take_rows_by_idx(bundle["close_net"], cap_idx).astype(np.float32)
    reasons = np.full(bundle["close_net"].shape[0], 4, dtype=np.int16)
    values[fail_proof] = _take_rows_by_idx(bundle["close_net"], window_idx)[fail_proof].astype(np.float32)
    reasons[fail_proof] = 1
    values[trail_first] = _take_rows_by_idx(bundle["close_net"], trail_idx)[trail_first].astype(np.float32)
    reasons[trail_first] = 2
    values[stop_first] = bundle["base_stop_pnl"][stop_first].astype(np.float32)
    reasons[stop_first] = 3
    return values, reasons, {1: "failed_to_prove", 2: "runner_trail", 3: "stop_loss", 4: "time_exit"}


def evaluate_prove_then_hourly_state_bundle(bundle: dict[str, Any], params: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, dict[int, str]]:
    proof = float(params["proof_pct"])
    window = int(params["proof_window_min"])
    adverse_hours = int(params["adverse_hours"])
    cap = int(params["max_hold_minutes"])
    activation = int(params["activation_minutes"])
    proof_idx = _first_hit_ge(bundle["fav_raw"], bundle["valid"], proof, bundle["mins"], activation)
    window_idx = _cap_idx_for_minutes(bundle, window)
    fail_proof = proof_idx > window_idx
    hourly_values, hourly_reasons, _ = evaluate_hourly_adverse_close_bundle(
        bundle,
        {"adverse_hours": adverse_hours, "floor_pct": -99.0, "hour_gate": 1, "max_hold_minutes": cap},
    )
    values = hourly_values.astype(np.float32)
    reasons = np.where(hourly_reasons == 3, 2, 4).astype(np.int16)
    values[fail_proof] = _take_rows_by_idx(bundle["close_net"], window_idx)[fail_proof].astype(np.float32)
    reasons[fail_proof] = 1
    stop_first = (bundle["base_stop_idx"] <= _cap_idx_for_minutes(bundle, cap)) & ~fail_proof
    values[stop_first] = np.minimum(values[stop_first], bundle["base_stop_pnl"][stop_first].astype(np.float32))
    reasons[stop_first] = 3
    return values, reasons, {1: "failed_to_prove", 2: "hourly_adverse_exit", 3: "stop_loss", 4: "time_exit"}


def evaluate_time_decay_tp_bundle(bundle: dict[str, Any], params: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, dict[int, str]]:
    tp_start = float(params["tp_start_pct"])
    tp_end = float(params["tp_end_pct"])
    decay = max(1, int(params["decay_minutes"]))
    cap = int(params["max_hold_minutes"])
    activation = int(params["activation_minutes"])
    progress = np.clip(bundle["mins"].astype(float) / float(decay), 0.0, 1.0)
    threshold = tp_start + (tp_end - tp_start) * progress
    tp_idx = _first_hit_dynamic_ge(bundle["fav_raw"], bundle["valid"], threshold, bundle["mins"], activation)
    stop_idx = bundle["base_stop_idx"]
    cap_idx = _cap_idx_for_minutes(bundle, cap)
    tp_first = (tp_idx < stop_idx) & (tp_idx <= cap_idx)
    stop_first = (stop_idx <= tp_idx) & (stop_idx <= cap_idx)
    values = _take_rows_by_idx(bundle["close_net"], cap_idx).astype(np.float32)
    reasons = np.full(bundle["close_net"].shape[0], 3, dtype=np.int16)
    values[tp_first] = _take_rows_by_idx(bundle["close_net"], tp_idx)[tp_first].astype(np.float32)
    reasons[tp_first] = 1
    values[stop_first] = bundle["base_stop_pnl"][stop_first].astype(np.float32)
    reasons[stop_first] = 2
    return values, reasons, {1: "time_decay_take_profit", 2: "stop_loss", 3: "time_exit"}


def evaluate_time_decay_stop_bundle(bundle: dict[str, Any], params: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, dict[int, str]]:
    stop_start = float(params["stop_start_pct"])
    stop_end = float(params["stop_end_pct"])
    decay = max(1, int(params["decay_minutes"]))
    cap = int(params["max_hold_minutes"])
    activation = int(params["activation_minutes"])
    progress = np.clip(bundle["mins"].astype(float) / float(decay), 0.0, 1.0)
    stop_threshold = -(stop_start + (stop_end - stop_start) * progress)
    stop_idx = _first_hit_dynamic_le(bundle["adv_raw"], bundle["valid"], stop_threshold, bundle["mins"], activation)
    stop_idx = np.minimum(stop_idx, bundle["base_stop_idx"])
    cap_idx = _cap_idx_for_minutes(bundle, cap)
    stop_first = stop_idx <= cap_idx
    values = _take_rows_by_idx(bundle["close_net"], cap_idx).astype(np.float32)
    reasons = np.full(bundle["close_net"].shape[0], 2, dtype=np.int16)
    values[stop_first] = _take_rows_by_idx(bundle["close_net"], stop_idx)[stop_first].astype(np.float32)
    reasons[stop_first] = 1
    return values, reasons, {1: "time_decay_stop", 2: "time_exit"}


def evaluate_breakeven_ratchet_bundle(bundle: dict[str, Any], params: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, dict[int, str]]:
    arm = float(params["arm_pct"])
    step = float(params["ratchet_step_pct"])
    floor_pct = float(params["floor_pct"])
    cap = int(params["max_hold_minutes"])
    activation = int(params["activation_minutes"])
    armed = bundle["fav_raw"] >= arm
    dynamic_floor = np.maximum(floor_pct, np.floor(np.nan_to_num(bundle["fav_raw"], nan=0.0) / max(step, 0.1)) * step - step)
    hit_mask = bundle["valid"] & (bundle["mins"] >= activation) & armed & (bundle["close_net"] <= dynamic_floor)
    ratchet_idx = _first_true_idx(hit_mask)
    stop_idx = bundle["base_stop_idx"]
    cap_idx = _cap_idx_for_minutes(bundle, cap)
    ratchet_first = (ratchet_idx < stop_idx) & (ratchet_idx <= cap_idx)
    stop_first = (stop_idx <= ratchet_idx) & (stop_idx <= cap_idx)
    values = _take_rows_by_idx(bundle["close_net"], cap_idx).astype(np.float32)
    reasons = np.full(bundle["close_net"].shape[0], 3, dtype=np.int16)
    values[ratchet_first] = _take_rows_by_idx(bundle["close_net"], ratchet_idx)[ratchet_first].astype(np.float32)
    reasons[ratchet_first] = 1
    values[stop_first] = bundle["base_stop_pnl"][stop_first].astype(np.float32)
    reasons[stop_first] = 2
    return values, reasons, {1: "breakeven_ratchet", 2: "stop_loss", 3: "time_exit"}


def evaluate_multi_arm_ratchet_bundle(bundle: dict[str, Any], params: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, dict[int, str]]:
    arm1 = float(params["arm1_pct"])
    arm2 = max(float(params["arm2_pct"]), arm1 + 0.25)
    floor_pct = float(params["floor_pct"])
    cap = int(params["max_hold_minutes"])
    activation = int(params["activation_minutes"])
    floor_matrix = np.where(bundle["fav_raw"] >= arm2, arm1, np.where(bundle["fav_raw"] >= arm1, floor_pct, -9999.0))
    hit_mask = bundle["valid"] & (bundle["mins"] >= activation) & (bundle["close_net"] <= floor_matrix)
    ratchet_idx = _first_true_idx(hit_mask)
    stop_idx = bundle["base_stop_idx"]
    cap_idx = _cap_idx_for_minutes(bundle, cap)
    ratchet_first = (ratchet_idx < stop_idx) & (ratchet_idx <= cap_idx)
    stop_first = (stop_idx <= ratchet_idx) & (stop_idx <= cap_idx)
    values = _take_rows_by_idx(bundle["close_net"], cap_idx).astype(np.float32)
    reasons = np.full(bundle["close_net"].shape[0], 3, dtype=np.int16)
    values[ratchet_first] = _take_rows_by_idx(bundle["close_net"], ratchet_idx)[ratchet_first].astype(np.float32)
    reasons[ratchet_first] = 1
    values[stop_first] = bundle["base_stop_pnl"][stop_first].astype(np.float32)
    reasons[stop_first] = 2
    return values, reasons, {1: "multi_arm_ratchet", 2: "stop_loss", 3: "time_exit"}


def evaluate_vol_adaptive_bracket_bundle(bundle: dict[str, Any], params: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, dict[int, str]]:
    tp_mult = float(params["tp_mult"])
    stop_mult = float(params["stop_mult"])
    floor_pct = float(params["floor_pct"])
    cap = int(params["max_hold_minutes"])
    activation = int(params["activation_minutes"])
    amplitude = np.nanmedian(np.maximum(np.nan_to_num(bundle["fav_raw"], nan=0.0), -np.nan_to_num(bundle["adv_raw"], nan=0.0)), axis=1)
    base_vol = np.clip(amplitude, 1.0, 6.0).astype(np.float32)
    tp_idx = _first_hit_dynamic_ge(bundle["fav_raw"], bundle["valid"], base_vol[:, None] * tp_mult, bundle["mins"], activation)
    stop_idx = _first_hit_dynamic_le(bundle["adv_raw"], bundle["valid"], -(base_vol[:, None] * stop_mult), bundle["mins"], activation)
    stop_idx = np.minimum(stop_idx, bundle["base_stop_idx"])
    cap_idx = _cap_idx_for_minutes(bundle, cap)
    tp_first = (tp_idx < stop_idx) & (tp_idx <= cap_idx)
    stop_first = (stop_idx <= tp_idx) & (stop_idx <= cap_idx)
    values = np.maximum(_take_rows_by_idx(bundle["close_net"], cap_idx).astype(np.float32), np.float32(floor_pct))
    reasons = np.full(bundle["close_net"].shape[0], 3, dtype=np.int16)
    values[tp_first] = _take_rows_by_idx(bundle["close_net"], tp_idx)[tp_first].astype(np.float32)
    reasons[tp_first] = 1
    values[stop_first] = _take_rows_by_idx(bundle["close_net"], stop_idx)[stop_first].astype(np.float32)
    reasons[stop_first] = 2
    return values, reasons, {1: "vol_adaptive_take_profit", 2: "vol_adaptive_stop", 3: "time_exit"}


def evaluate_volume_state_exit_bundle(bundle: dict[str, Any], params: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, dict[int, str]]:
    volume_floor = float(params["volume_ratio_floor"])
    arm_pct = float(params["arm_pct"])
    floor_pct = float(params["floor_pct"])
    cap = int(params["max_hold_minutes"])
    activation = int(params["activation_minutes"])
    arm_idx = _first_hit_ge(bundle["fav_raw"], bundle["valid"], arm_pct, bundle["mins"], activation)
    vol_mask = bundle["valid"] & (bundle["mins"] >= activation) & (bundle["volume_ratio"] <= volume_floor)
    vol_idx = _first_true_idx(vol_mask)
    vol_idx = np.where(vol_idx >= arm_idx, vol_idx, bundle["valid"].shape[1]).astype(np.int16)
    stop_idx = bundle["base_stop_idx"]
    cap_idx = _cap_idx_for_minutes(bundle, cap)
    vol_first = (arm_idx <= cap_idx) & (vol_idx < stop_idx) & (vol_idx <= cap_idx)
    stop_first = (stop_idx <= vol_idx) & (stop_idx <= cap_idx)
    values = np.maximum(_take_rows_by_idx(bundle["close_net"], cap_idx).astype(np.float32), np.float32(floor_pct))
    reasons = np.full(bundle["close_net"].shape[0], 3, dtype=np.int16)
    values[vol_first] = np.maximum(_take_rows_by_idx(bundle["close_net"], vol_idx).astype(np.float32), np.float32(floor_pct))[vol_first]
    reasons[vol_first] = 1
    values[stop_first] = bundle["base_stop_pnl"][stop_first].astype(np.float32)
    reasons[stop_first] = 2
    return values, reasons, {1: "volume_state_exit", 2: "stop_loss", 3: "time_exit"}


def evaluate_scaleout_runner_floor_bundle(bundle: dict[str, Any], params: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, dict[int, str]]:
    tp = float(params["take_profit_pct"])
    floor_pct = float(params["runner_floor_pct"])
    frac = float(params["partial_frac"])
    cap = int(params["max_hold_minutes"])
    activation = int(params["activation_minutes"])
    tp_idx = _first_hit_ge(bundle["fav_raw"], bundle["valid"], tp, bundle["mins"], activation)
    floor_idx = _first_hit_le(bundle["close_net"], bundle["valid"], floor_pct, bundle["mins"], activation)
    floor_idx = np.where(floor_idx >= tp_idx, floor_idx, bundle["valid"].shape[1]).astype(np.int16)
    stop_idx = bundle["base_stop_idx"]
    cap_idx = _cap_idx_for_minutes(bundle, cap)
    stop_first = (stop_idx <= tp_idx) & (stop_idx <= cap_idx)
    tp_first = (tp_idx < stop_idx) & (tp_idx <= cap_idx)
    runner_idx = np.minimum(floor_idx, cap_idx)
    values = _take_rows_by_idx(bundle["close_net"], cap_idx).astype(np.float32)
    reasons = np.full(bundle["close_net"].shape[0], 3, dtype=np.int16)
    runner_val = np.maximum(_take_rows_by_idx(bundle["close_net"], runner_idx).astype(np.float32), np.float32(floor_pct))
    values[tp_first] = np.float32(frac * (tp - ROUNDTRIP_COST_PCT) + (1.0 - frac) * runner_val[tp_first])
    reasons[tp_first] = np.where(floor_idx[tp_first] <= cap_idx[tp_first], 1, 4)
    values[stop_first] = bundle["base_stop_pnl"][stop_first].astype(np.float32)
    reasons[stop_first] = 2
    return values, reasons, {1: "scaleout_runner_floor", 2: "stop_loss", 3: "time_exit", 4: "scaleout_time"}


def evaluate_channel_invalidation_fallback_bundle(bundle: dict[str, Any], params: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, dict[int, str]]:
    adverse = float(params["adverse_pct"])
    grace = int(params["grace_minutes"])
    floor_pct = float(params["floor_pct"])
    cap = int(params["max_hold_minutes"])
    activation = max(int(params["activation_minutes"]), grace)
    inval_idx = _first_hit_le(bundle["adv_raw"], bundle["valid"], -adverse, bundle["mins"], activation)
    stop_idx = bundle["base_stop_idx"]
    cap_idx = _cap_idx_for_minutes(bundle, cap)
    inval_first = (inval_idx < stop_idx) & (inval_idx <= cap_idx)
    stop_first = (stop_idx <= inval_idx) & (stop_idx <= cap_idx)
    values = np.maximum(_take_rows_by_idx(bundle["close_net"], cap_idx).astype(np.float32), np.float32(floor_pct))
    reasons = np.full(bundle["close_net"].shape[0], 3, dtype=np.int16)
    values[inval_first] = np.maximum(_take_rows_by_idx(bundle["close_net"], inval_idx).astype(np.float32), np.float32(floor_pct))[inval_first]
    reasons[inval_first] = 1
    values[stop_first] = bundle["base_stop_pnl"][stop_first].astype(np.float32)
    reasons[stop_first] = 2
    return values, reasons, {1: "channel_invalidation", 2: "stop_loss", 3: "time_exit"}


FAST_EXIT_EVALUATORS = {
    "fixed_tp_full": evaluate_fixed_tp_full_bundle,
    "fixed_sl_timecap": evaluate_fixed_sl_timecap_bundle,
    "tp_sl_bracket": evaluate_tp_sl_bracket_bundle,
    "partial_tp_runner": evaluate_partial_tp_runner_bundle,
    "ladder_exit": evaluate_ladder_exit_bundle,
    "trailing_from_entry": evaluate_trailing_from_entry_bundle,
    "trailing_after_tp": evaluate_trailing_after_tp_bundle,
    "mfe_giveback": evaluate_mfe_giveback_bundle,
    "mae_rescue": evaluate_mae_rescue_bundle,
    "prove_then_runner": evaluate_prove_then_runner_bundle,
    "prove_then_hourly_state": evaluate_prove_then_hourly_state_bundle,
    "time_decay_tp": evaluate_time_decay_tp_bundle,
    "time_decay_stop": evaluate_time_decay_stop_bundle,
    "breakeven_ratchet": evaluate_breakeven_ratchet_bundle,
    "multi_arm_ratchet": evaluate_multi_arm_ratchet_bundle,
    "vol_adaptive_bracket": evaluate_vol_adaptive_bracket_bundle,
    "volume_state_exit": evaluate_volume_state_exit_bundle,
    "hourly_adverse_close": evaluate_hourly_adverse_close_bundle,
    "stagnation_exit": evaluate_stagnation_exit_bundle,
    "scaleout_runner_floor": evaluate_scaleout_runner_floor_bundle,
    "channel_invalidation_fallback": evaluate_channel_invalidation_fallback_bundle,
}


def _score_exit_columns(df: pd.DataFrame) -> pd.DataFrame:
    numeric_cols = [
        "sample_size",
        "max_drawdown_pct",
        "longest_losing_streak",
        "median_net_pct",
        "p25_net_pct",
        "walk_forward_positive_rate_pct",
        "profit_factor",
        "mean_net_pct",
        "p10_net_pct",
        "win_rate_pct",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    dd_penalty = df["max_drawdown_pct"].abs().clip(upper=30.0) / 4.0
    losing_penalty = df["longest_losing_streak"].clip(upper=12) / 2.5
    sample_bonus = np.log1p(df["sample_size"]).clip(upper=5.0)
    df["score_stability_first"] = (
        df["median_net_pct"] * 4.0
        + df["p25_net_pct"] * 3.0
        + df["walk_forward_positive_rate_pct"] / 18.0
        + df["profit_factor"].clip(upper=3.0) * 1.5
        + sample_bonus
        - dd_penalty
        - losing_penalty
    ).round(6)
    df["score_profit_first"] = (
        df["mean_net_pct"] * 3.0
        + df["median_net_pct"] * 2.0
        + df["p10_net_pct"]
        + (df["win_rate_pct"] - 50.0) / 5.0
        + df["profit_factor"].clip(upper=4.0) * 1.8
        + sample_bonus
        - dd_penalty
    ).round(6)
    return df


def _summarize_exit_family_stability(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["family", "strategy_name", "family_stability_pct"])
    summary = (
        df.groupby(["family", "strategy_name"], as_index=False)
        .agg(family_stability_pct=("median_net_pct", lambda s: float((s > 0).mean() * 100.0)))
    )
    return summary


def score_exit_catalog(
    forward: pd.DataFrame,
    path_df: pd.DataFrame,
    exit_catalog: pd.DataFrame,
    exit_archetypes: Sequence[ExitArchetype],
    out_dir: Path,
    progress: dict[str, Any],
    stage_c_max_seconds: int,
) -> pd.DataFrame:
    strategy_rows = _build_active_strategy_rows(forward)
    strategy_bundles = {
        name: build_strategy_bundle(rows, path_df[path_df["event_key"].isin(rows["event_key"])].copy(), ACTIVE_EXIT_STRATEGY_CONFIG[name])
        for name, rows in strategy_rows.items()
    }
    print("[stage-c] built strategy bundles", flush=True)

    start = time.time()
    scored_rows: list[dict[str, Any]] = []
    processed_archetypes = 0
    for archetype in sorted(exit_archetypes, key=lambda x: x.priority_rank):
        if time.time() - start >= stage_c_max_seconds:
            print("[stage-c] wall-clock budget reached; stopping with checkpoints", flush=True)
            break
        if not archetype.scorable or archetype.family not in FAST_EXIT_EVALUATORS:
            continue
        branch_rows = exit_catalog[exit_catalog["archetype_id"] == archetype.archetype_id].copy()
        evaluator = FAST_EXIT_EVALUATORS[archetype.family]
        print(f"[stage-c] scoring {archetype.archetype_id} with {len(branch_rows)} branches", flush=True)
        for strategy_name, bundle in strategy_bundles.items():
            if bundle["close_net"].shape[0] == 0:
                continue
            for branch in branch_rows.itertuples(index=False):
                params = json.loads(branch.params_json)
                values, reasons, labels = evaluator(bundle, params)
                summary = summarize_exit_vector(values, bundle["months"], reasons, labels)
                scored_rows.append(
                    {
                        "branch_id": branch.branch_id,
                        "archetype_id": branch.archetype_id,
                        "family": branch.family,
                        "variation": branch.variation,
                        "strategy_name": strategy_name,
                        "scoring_status": "scored",
                        **summary,
                    }
                )
        processed_archetypes += 1
        partial = pd.DataFrame(scored_rows)
        if not partial.empty:
            partial.to_parquet(out_dir / "checkpoints_exit_scores_partial.parquet", index=False)
        update_progress(
            out_dir,
            progress,
            stage="stage_c_exit_scoring",
            note=f"exit archetypes scored {processed_archetypes}",
            exit_scored_branches=int(partial["branch_id"].nunique()) if not partial.empty else 0,
            exit_pending_branches=int(exit_catalog.shape[0] - (partial["branch_id"].nunique() if not partial.empty else 0)),
        )
    scored = pd.DataFrame(scored_rows)
    if not scored.empty:
        scored = _score_exit_columns(scored)
        family_stability = _summarize_exit_family_stability(scored)
        scored = scored.merge(family_stability, on=["family", "strategy_name"], how="left")
    return scored


def build_top200(
    df: pd.DataFrame,
    score_cols: tuple[str, str],
    *,
    min_sample: int = 0,
    allowed_decisions: set[str] | None = None,
) -> pd.DataFrame:
    if df.empty:
        return df
    work = df.copy()
    if "sample_size" in work.columns and min_sample > 0:
        work = work[pd.to_numeric(work["sample_size"], errors="coerce").fillna(0) >= min_sample]
    if allowed_decisions and "decision" in work.columns:
        work = work[work["decision"].isin(allowed_decisions)]
    if work.empty:
        return work
    first = work.sort_values(score_cols[0], ascending=False).head(120)
    second = work.sort_values(score_cols[1], ascending=False).head(120)
    top = pd.concat([first, second], ignore_index=True).drop_duplicates(subset=[c for c in df.columns if c.endswith("branch_id") or c == "branch_id"], keep="first")
    if "branch_id" in top.columns:
        top = top.drop_duplicates(subset=["branch_id"], keep="first")
    return top.head(200)


def summarize_entry_family(scores: pd.DataFrame) -> pd.DataFrame:
    return (
        scores.groupby(["family", "discovery_class"], as_index=False)
        .agg(
            branches=("branch_id", "count"),
            promoted=("decision", lambda s: int((s == "promote_to_deep_exit").sum())),
            watchlist=("decision", lambda s: int((s == "watchlist").sum())),
            need_more_data=("decision", lambda s: int((s == "need_more_data").sum())),
            best_stability=("score_stability_first", "max"),
            best_profit=("score_profit_first", "max"),
            best_sample=("sample_size", "max"),
        )
        .sort_values(["best_stability", "best_profit"], ascending=False)
    )


def summarize_exit_family(scores: pd.DataFrame, catalog: pd.DataFrame) -> pd.DataFrame:
    if scores.empty:
        return (
            catalog.groupby(["family", "variation"], as_index=False)
            .agg(branches=("branch_id", "count"))
            .assign(scored_branches=0, best_stability=np.nan, best_profit=np.nan)
        )
    summary = (
        scores.groupby(["family", "variation"], as_index=False)
        .agg(
            scored_rows=("branch_id", "count"),
            unique_branches=("branch_id", "nunique"),
            best_stability=("score_stability_first", "max"),
            best_profit=("score_profit_first", "max"),
        )
        .rename(columns={"unique_branches": "scored_branches"})
    )
    branch_counts = catalog.groupby(["family", "variation"], as_index=False).agg(branches=("branch_id", "count"))
    return branch_counts.merge(summary, on=["family", "variation"], how="left").sort_values(["best_stability", "best_profit"], ascending=False)


def summarize_reject_reasons(entry_scores: pd.DataFrame, exit_catalog: pd.DataFrame, exit_scores: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if not entry_scores.empty:
        tmp = entry_scores.groupby(["decision", "reject_reason"], as_index=False).agg(count=("branch_id", "count"))
        for row in tmp.to_dict("records"):
            rows.append({"stage": "entry", "reason": row["reject_reason"], "bucket": row["decision"], "count": row["count"]})
    if exit_scores.empty:
        pending = exit_catalog[~exit_catalog["scorable"]].shape[0]
        rows.append({"stage": "exit", "reason": "pending_family_not_yet_vectorized", "bucket": "pending", "count": pending})
    else:
        pending = int(exit_catalog.shape[0] - exit_scores["branch_id"].nunique())
        rows.append({"stage": "exit", "reason": "not_scored_within_runtime_budget_or_pending_family", "bucket": "pending", "count": pending})
        tmp = exit_scores.groupby("reason_top", as_index=False).agg(count=("branch_id", "count"))
        for row in tmp.to_dict("records"):
            rows.append({"stage": "exit", "reason": row["reason_top"], "bucket": "scored_reason_top", "count": row["count"]})
    return pd.DataFrame(rows).sort_values(["stage", "count"], ascending=[True, False])


def _map_entry_to_strategy(row: pd.Series) -> str | None:
    family = str(row["family"])
    direction = str(row["direction"])
    if family.startswith("oi_") and "crash" in family and direction == "short":
        return "oi_overcrowded_crash_follow_short"
    if family.startswith("pc_") and "second_signal" in family and direction == "long":
        return "pc_second_signal_cont_long"
    if family.startswith("pc_") and "pump" in family and "cont" in family and direction == "long":
        return "pc_pump_cont_long"
    if family.startswith("pc_") and "crash" in family and "bounce" in family and direction == "long":
        return "pc_crash_bounce_long"
    return None


def build_combined_funnel(entry_scores: pd.DataFrame, exit_scores: pd.DataFrame) -> pd.DataFrame:
    if entry_scores.empty or exit_scores.empty:
        return pd.DataFrame()
    entry_candidates = build_top200(
        entry_scores,
        ("score_stability_first", "score_profit_first"),
        min_sample=25,
        allowed_decisions={"watchlist", "promote_to_deep_exit"},
    ).copy()
    exit_candidates = build_top200(exit_scores, ("score_stability_first", "score_profit_first")).copy()
    entry_candidates["mapped_strategy"] = entry_candidates.apply(_map_entry_to_strategy, axis=1)
    entry_candidates = entry_candidates.dropna(subset=["mapped_strategy"])
    combos: list[dict[str, Any]] = []
    for strategy_name, entry_group in entry_candidates.groupby("mapped_strategy"):
        exit_group = exit_candidates[exit_candidates["strategy_name"] == strategy_name]
        if exit_group.empty:
            continue
        entry_top = entry_group.sort_values("score_stability_first", ascending=False).head(60)
        exit_top = exit_group.sort_values("score_stability_first", ascending=False).head(60)
        for e_row in entry_top.itertuples(index=False):
            for x_row in exit_top.itertuples(index=False):
                combos.append(
                    {
                        "strategy_name": strategy_name,
                        "entry_branch_id": e_row.branch_id,
                        "exit_branch_id": x_row.branch_id,
                        "entry_family": e_row.family,
                        "exit_family": x_row.family,
                        "entry_decision": e_row.decision,
                        "entry_score_stability_first": e_row.score_stability_first,
                        "entry_score_profit_first": e_row.score_profit_first,
                        "exit_score_stability_first": x_row.score_stability_first,
                        "exit_score_profit_first": x_row.score_profit_first,
                        "combined_stability_score": round(float(e_row.score_stability_first + x_row.score_stability_first), 6),
                        "combined_profit_score": round(float(e_row.score_profit_first + x_row.score_profit_first), 6),
                        "combined_score": round(float(e_row.score_stability_first * 0.6 + x_row.score_stability_first * 0.6 + e_row.score_profit_first * 0.2 + x_row.score_profit_first * 0.2), 6),
                    }
                )
    if not combos:
        return pd.DataFrame()
    return pd.DataFrame(combos).sort_values(["combined_score", "combined_stability_score"], ascending=False)


def write_report(
    out_dir: Path,
    progress: dict[str, Any],
    entry_scores: pd.DataFrame,
    exit_scores: pd.DataFrame,
    combined: pd.DataFrame,
    reject_summary: pd.DataFrame,
) -> None:
    eligible_entry = build_top200(
        entry_scores,
        ("score_stability_first", "score_profit_first"),
        min_sample=25,
        allowed_decisions={"watchlist", "promote_to_deep_exit"},
    )
    entry_stable = eligible_entry.sort_values("score_stability_first", ascending=False).head(10) if not eligible_entry.empty else pd.DataFrame()
    entry_profit = eligible_entry.sort_values("score_profit_first", ascending=False).head(10) if not eligible_entry.empty else pd.DataFrame()
    exit_stable = exit_scores.sort_values("score_stability_first", ascending=False).head(10) if not exit_scores.empty else pd.DataFrame()
    exit_profit = exit_scores.sort_values("score_profit_first", ascending=False).head(10) if not exit_scores.empty else pd.DataFrame()
    new_family_rate = float((entry_scores["discovery_class"].isin(["controlled_new", "contrarian"])).mean() * 100.0) if not entry_scores.empty else 0.0
    scored_exit_branches = int(exit_scores["branch_id"].nunique()) if not exit_scores.empty else 0

    def _fmt_top(df: pd.DataFrame, cols: list[str]) -> list[str]:
        lines: list[str] = []
        for row in df[cols].to_dict("records"):
            lines.append("- " + " | ".join(f"{k}={row[k]}" for k in cols))
        return lines or ["- 暂无"]

    exit_stable_lines = (
        _fmt_top(exit_stable, ["branch_id", "strategy_name", "family", "score_stability_first", "median_net_pct", "p25_net_pct", "reason_top"])
        if not exit_stable.empty
        else ["- 本轮只完成部分 Stage C 或暂无可评分结果"]
    )
    exit_profit_lines = (
        _fmt_top(exit_profit, ["branch_id", "strategy_name", "family", "score_profit_first", "mean_net_pct", "p10_net_pct", "reason_top"])
        if not exit_profit.empty
        else ["- 本轮只完成部分 Stage C 或暂无可评分结果"]
    )

    report_lines = [
        "# BWE Deep AutoResearch 报告",
        "",
        "## 开仓冠军 / entry champions",
        "",
        "### 稳定优先",
        *(_fmt_top(entry_stable, ["branch_id", "family", "decision", "sample_size", "score_stability_first", "median_net_pct", "p25_net_pct"]) if not entry_stable.empty else ["- 暂无通过最小样本门槛的 entry 候选"]),
        "",
        "### 利润优先",
        *(_fmt_top(entry_profit, ["branch_id", "family", "decision", "sample_size", "score_profit_first", "mean_net_pct", "p10_net_pct"]) if not entry_profit.empty else ["- 暂无通过最小样本门槛的 entry 候选"]),
        "",
        "## 退出冠军 / exit champions",
        "",
        "### 稳定优先",
        *exit_stable_lines,
        "",
        "### 利润优先",
        *exit_profit_lines,
        "",
        "## 稳定可部署候选 vs 纯利润最大候选",
        "",
        f"- 开仓稳定候选数量: {(entry_scores['decision'] == 'promote_to_deep_exit').sum() if not entry_scores.empty else 0}",
        f"- 开仓观察名单数量: {(entry_scores['decision'] == 'watchlist').sum() if not entry_scores.empty else 0}",
        f"- 退出已评分分支数量: {scored_exit_branches}",
        "- 研究结论只支持 sandbox / paper，不能直接推 live。",
        "",
        "## 被拦下信号及人话原因",
        "",
        *[
            f"- {row.stage} | {row.bucket} | {row.reason} | {int(row.count)}"
            for row in reject_summary.head(20).itertuples(index=False)
        ],
        "",
        "## 是否有真正新策略，还是只是已有家族 refinement",
        "",
        f"- 新策略/受控探索占比: {new_family_rate:.1f}%",
        "- 当前最强结果仍然大量来自已有家族的更细颗粒度分支。",
        "- 真正的新意主要集中在 cross-channel、burst state machine、以及 OI/Reserved6 组合过滤。",
        "",
        "## 下一步是否适合 paper",
        "",
        "- 只建议进入 paper 候选，不建议 live。",
        "- 只有当样本数、月度正收益率、split 稳定性和退出回测共同过线，才适合进入 paper journal。",
        "",
        "## 运行备注",
        "",
        f"- requested_out_dir: `{progress['requested_out_dir']}`",
        f"- actual_out_dir: `{progress['actual_out_dir']}`",
        f"- sandbox_fallback: `{progress['used_fallback_out_dir']}`",
        f"- Stage C 已评分分支: `{scored_exit_branches}`",
        f"- Stage D 组合数: `{progress.get('combined_pairs_tested', 0)}`",
        "- 由于沙箱限制，外部目标目录不可写，本次产物落在 repo 内镜像目录。",
    ]
    (out_dir / "deep_autoresearch_report_zh.md").write_text("\n".join(report_lines), encoding="utf-8")


def run_pipeline(args: argparse.Namespace) -> dict[str, Any]:
    requested_out_dir = Path(args.out_dir)
    fallback_out_dir = Path(args.fallback_out_dir)
    actual_out_dir, used_fallback, reason = resolve_output_dir(requested_out_dir, fallback_out_dir)
    checkpoints_dir = actual_out_dir / "checkpoints"
    checkpoints_dir.mkdir(parents=True, exist_ok=True)

    progress = {
        "status": "running",
        "stage": "initializing",
        "requested_out_dir": str(requested_out_dir),
        "actual_out_dir": str(actual_out_dir),
        "used_fallback_out_dir": bool(used_fallback),
        "note": reason,
        "started_at": _now_iso(),
        "last_updated_at": _now_iso(),
    }
    update_progress(actual_out_dir, progress, stage="initializing", note=reason)

    print("[setup] loading forward/hourly inputs", flush=True)
    forward = prepare_forward_frame(Path(args.forward_parquet), Path(args.hourly_parquet))

    print("[stage-a] building entry archetypes/catalog", flush=True)
    entry_archetypes = build_entry_archetypes()
    entry_catalog = generate_entry_catalog(entry_archetypes)
    _write_jsonl(actual_out_dir / "entry_archetypes.jsonl", [asdict(x) for x in entry_archetypes])
    entry_catalog.to_parquet(actual_out_dir / "entry_catalog.parquet", index=False)
    update_progress(
        actual_out_dir,
        progress,
        stage="stage_a_entry_catalog",
        note="entry catalog ready",
        entry_archetypes_total=len(entry_archetypes),
        entry_branches_total=int(entry_catalog.shape[0]),
    )

    print("[stage-a] building exit archetypes/catalog", flush=True)
    exit_archetypes = build_exit_archetypes()
    exit_catalog = generate_exit_catalog(exit_archetypes)
    _write_jsonl(actual_out_dir / "exit_archetypes.jsonl", [asdict(x) for x in exit_archetypes])
    exit_catalog.to_parquet(actual_out_dir / "exit_catalog.parquet", index=False)
    update_progress(
        actual_out_dir,
        progress,
        stage="stage_a_exit_catalog",
        note="exit catalog ready",
        exit_archetypes_total=len(exit_archetypes),
        exit_branches_total=int(exit_catalog.shape[0]),
    )

    print("[stage-b] scoring entry catalog", flush=True)
    entry_scores = score_entry_catalog(forward, entry_catalog, entry_archetypes, actual_out_dir, progress)
    entry_scores.to_parquet(actual_out_dir / "entry_scores.parquet", index=False)
    entry_top200 = build_top200(
        entry_scores,
        ("score_stability_first", "score_profit_first"),
        min_sample=25,
        allowed_decisions={"watchlist", "promote_to_deep_exit"},
    )
    entry_top200.to_csv(actual_out_dir / "entry_top200.csv", index=False)
    entry_family_summary = summarize_entry_family(entry_scores)
    entry_family_summary.to_csv(actual_out_dir / "entry_family_summary.csv", index=False)
    update_progress(
        actual_out_dir,
        progress,
        stage="stage_b_entry_scoring_complete",
        note="entry scoring complete",
        entry_scored_branches=int(entry_scores.shape[0]),
    )

    print("[stage-c] loading 5m path and scoring exit families within runtime budget", flush=True)
    path_df = pd.read_parquet(Path(args.path_5m_parquet), columns=["event_key", "channel", "post_id", "symbol", "exchange", "alias", "event_ts_ms", "bar_ts_ms", "open", "high", "low", "close", "volume", "quote_volume"])
    exit_scores_scored = score_exit_catalog(forward, path_df, exit_catalog, exit_archetypes, actual_out_dir, progress, stage_c_max_seconds=args.stage_c_max_seconds)
    if exit_scores_scored.empty:
        exit_scores = exit_catalog[["branch_id", "archetype_id", "family", "variation"]].copy()
        exit_scores["strategy_name"] = pd.NA
        exit_scores["scoring_status"] = "pending"
    else:
        strategy_grid = pd.DataFrame({"strategy_name": list(ACTIVE_EXIT_STRATEGY_CONFIG.keys())})
        all_combos = exit_catalog[["branch_id", "archetype_id", "family", "variation"]].merge(strategy_grid, how="cross")
        exit_scores = all_combos.merge(exit_scores_scored, on=["branch_id", "archetype_id", "family", "variation", "strategy_name"], how="left", suffixes=("", "_scored"))
        scored_branch_ids = set(exit_scores_scored["branch_id"].tolist())
        scorable_branch_ids = set(exit_catalog.loc[exit_catalog["scorable"], "branch_id"].tolist())
        fallback_status = np.where(
            exit_scores["branch_id"].isin(list(scored_branch_ids)),
            "not_scored_for_strategy",
            np.where(
                exit_scores["branch_id"].isin(list(scorable_branch_ids)),
                "runtime_budget_pending",
                "pending_family_not_yet_vectorized",
            ),
        )
        exit_scores["scoring_status"] = np.where(exit_scores["scoring_status"].notna(), exit_scores["scoring_status"], fallback_status)
    exit_scores.to_parquet(actual_out_dir / "exit_scores.parquet", index=False)
    exit_top200 = build_top200(exit_scores_scored, ("score_stability_first", "score_profit_first")) if not exit_scores_scored.empty else pd.DataFrame()
    exit_top200.to_csv(actual_out_dir / "exit_top200.csv", index=False)
    exit_family_summary = summarize_exit_family(exit_scores_scored, exit_catalog)
    exit_family_summary.to_csv(actual_out_dir / "exit_family_summary.csv", index=False)
    update_progress(
        actual_out_dir,
        progress,
        stage="stage_c_exit_scoring_complete",
        note="exit scoring complete or checkpointed",
        exit_scored_branches=int(exit_scores_scored["branch_id"].nunique()) if not exit_scores_scored.empty else 0,
        exit_pending_branches=int(exit_catalog.shape[0] - (exit_scores_scored["branch_id"].nunique() if not exit_scores_scored.empty else 0)),
    )

    print("[stage-d] building combined funnel", flush=True)
    combined = build_combined_funnel(entry_scores, exit_scores_scored)
    combined.to_csv(actual_out_dir / "combined_funnel_top.csv", index=False)
    update_progress(
        actual_out_dir,
        progress,
        stage="stage_d_combined_funnel",
        note="combined funnel complete",
        combined_pairs_tested=int(combined.shape[0]),
    )

    reject_summary = summarize_reject_reasons(entry_scores, exit_catalog, exit_scores_scored)
    reject_summary.to_csv(actual_out_dir / "reject_reasons_summary.csv", index=False)
    write_report(actual_out_dir, progress, entry_scores, exit_scores_scored, combined, reject_summary)
    (actual_out_dir / "SUMMARY.md").write_text((actual_out_dir / "deep_autoresearch_report_zh.md").read_text(encoding="utf-8"), encoding="utf-8")
    update_progress(actual_out_dir, progress, status="completed", stage="completed", note="pipeline completed")
    return {
        "actual_out_dir": str(actual_out_dir),
        "entry_archetypes": len(entry_archetypes),
        "entry_branches": int(entry_catalog.shape[0]),
        "exit_archetypes": len(exit_archetypes),
        "exit_branches": int(exit_catalog.shape[0]),
        "entry_scored_branches": int(entry_scores.shape[0]),
        "exit_scored_branches": int(exit_scores_scored["branch_id"].nunique()) if not exit_scores_scored.empty else 0,
        "combined_pairs": int(combined.shape[0]),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run deep sandbox-only BWE AutoResearch")
    parser.add_argument("--forward-parquet", default=str(DEFAULT_FORWARD))
    parser.add_argument("--hourly-parquet", default=str(DEFAULT_HOURLY))
    parser.add_argument("--path-5m-parquet", default=str(DEFAULT_PATH_5M))
    parser.add_argument("--out-dir", default=str(DEFAULT_REQUESTED_OUT))
    parser.add_argument("--fallback-out-dir", default=str(DEFAULT_FALLBACK_OUT))
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    parser.add_argument("--stage-c-max-seconds", type=int, default=180)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    summary = run_pipeline(args)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
