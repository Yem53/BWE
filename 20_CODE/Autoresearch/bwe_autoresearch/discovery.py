"""BWE three-channel AutoResearch discovery runner.

Sandbox-only strategy discovery utilities for OI&Price, pricechange, and Reserved6.
This module intentionally reads historical research artifacts and writes sandbox outputs only.
It does not import live autotrader code, credentials, order clients, or launchd controls.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


LIVE_PATH_MARKERS = (
    "bwe_live_autotrader",
    "live_autotrader",
    "okx_trade",
    "binance_order",
    "launchagents",
    "launchdaemons",
)


@dataclass(frozen=True)
class CandidateSpec:
    candidate_id: str
    hypothesis: str
    source_channel: str
    family: str
    discovery_layer: str
    direction: str
    entry_rule: dict[str, Any]
    filters: dict[str, Any]
    exit_rule: dict[str, Any]
    risk_rule: dict[str, Any]
    novelty_reason: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, sort_keys=True)


def _normalize_exit_signature(exit_rule: dict[str, Any]) -> tuple[Any, ...]:
    """Return a signature that treats fixed-horizon delay/horizon tweaks as non-novel."""
    typ = exit_rule.get("type", "fixed_horizon")
    if typ == "fixed_horizon":
        return ("fixed_horizon",)
    return (typ, tuple(sorted((k, str(v)) for k, v in exit_rule.items() if k not in {"entry_delay_s", "holding_horizon_min", "fallback_horizon_min"})))


def is_new_strategy(candidate: CandidateSpec, baseline: CandidateSpec) -> bool:
    """A new strategy needs new alpha/entry logic or material exit/risk logic, not only params."""
    if candidate.source_channel != baseline.source_channel:
        return True
    if candidate.family != baseline.family:
        return True
    if candidate.discovery_layer in {"controlled_new_strategy_discovery", "contrarian_exploratory"}:
        if candidate.entry_rule != baseline.entry_rule or candidate.filters != baseline.filters:
            return True
    if _normalize_exit_signature(candidate.exit_rule) != _normalize_exit_signature(baseline.exit_rule):
        return True
    material_risk_keys = {"position_scale", "left_tail_guard", "max_loss_cluster", "cooldown_minutes"}
    if any(k in candidate.risk_rule and candidate.risk_rule.get(k) != baseline.risk_rule.get(k) for k in material_risk_keys):
        return True
    return False


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


def _holding_horizon(exit_rule: dict[str, Any]) -> int:
    return int(exit_rule.get("holding_horizon_min") or exit_rule.get("fallback_horizon_min") or 5)


def _longest_losing_streak(values: Iterable[float]) -> int:
    longest = cur = 0
    for value in values:
        if value <= 0:
            cur += 1
            longest = max(longest, cur)
        else:
            cur = 0
    return longest


def _profit_factor(values: pd.Series) -> float:
    gains = values[values > 0].sum()
    losses = -values[values < 0].sum()
    if losses <= 0:
        return float("inf") if gains > 0 else 0.0
    return float(gains / losses)


def _walk_forward_stats(df: pd.DataFrame, values: pd.Series) -> dict[str, Any]:
    if "ts_ms" not in df.columns or values.empty:
        return {"walk_forward_windows": 0, "walk_forward_positive_windows": 0, "walk_forward_positive_rate_pct": 0.0}
    tmp = pd.DataFrame({"ts_ms": df.loc[values.index, "ts_ms"], "net": values})
    tmp["month"] = pd.to_datetime(tmp["ts_ms"], unit="ms", errors="coerce").dt.to_period("M").astype(str)
    grouped = tmp.dropna(subset=["month"]).groupby("month")["net"].mean()
    if grouped.empty:
        return {"walk_forward_windows": 0, "walk_forward_positive_windows": 0, "walk_forward_positive_rate_pct": 0.0}
    pos = int((grouped > 0).sum())
    return {
        "walk_forward_windows": int(grouped.shape[0]),
        "walk_forward_positive_windows": pos,
        "walk_forward_positive_rate_pct": round(pos / grouped.shape[0] * 100, 4),
    }


def _decision(row: dict[str, Any], min_sample: int) -> tuple[str, str]:
    sample = row["sample_size"]
    if sample < min_sample:
        return "need_more_data", f"sample {sample} < min_sample {min_sample}"
    if row["symbol_count"] < 5:
        return "need_more_data", "symbol_count < 5"
    if row["median_net_pct"] <= 0:
        return "reject", "median_net_pct <= 0"
    if row["p25_net_pct"] < -1.0:
        return "reject", "p25_net_pct below -1%"
    if row["top_symbol_share_pct"] > 35:
        return "watchlist", "symbol concentration high"
    if row["top1_removed_mean_net_pct"] <= 0:
        return "watchlist", "depends on top outlier winners"
    if row["win_rate_pct"] >= 60 and row["median_net_pct"] > 0 and row["profit_factor"] >= 1.35 and row["walk_forward_positive_rate_pct"] >= 55:
        return "promote_to_paper", "passes high-win/high-median historical gates"
    if row["win_rate_pct"] >= 52 and row["median_net_pct"] > 0 and row["profit_factor"] >= 1.1:
        return "watchlist", "positive but below champion gate"
    return "reject", "fails win/profit/stability gate"


def score_candidate(forward: pd.DataFrame, candidate: CandidateSpec, min_sample: int = 60) -> dict[str, Any]:
    horizon = _holding_horizon(candidate.exit_rule)
    net_col = f"net_{horizon}m"
    if net_col not in forward.columns:
        raise ValueError(f"missing {net_col} in forward dataframe")

    mask = pd.Series(True, index=forward.index)
    if "channel" in forward.columns:
        mask &= forward["channel"] == candidate.source_channel
    if "side" in forward.columns:
        mask &= forward["side"] == candidate.direction
    if "entry_delay_s" in forward.columns and "entry_delay_s" in candidate.exit_rule:
        mask &= forward["entry_delay_s"] == int(candidate.exit_rule["entry_delay_s"])
    mask &= _series_mask(forward, candidate.entry_rule)
    mask &= _series_mask(forward, candidate.filters)

    subset = forward.loc[mask].copy()
    values = pd.to_numeric(subset[net_col], errors="coerce").dropna()
    values = values.replace([math.inf, -math.inf], pd.NA).dropna()
    values_pct = values * 100.0

    if values_pct.empty:
        row = {
            "candidate_id": candidate.candidate_id,
            "family": candidate.family,
            "discovery_layer": candidate.discovery_layer,
            "source_channel": candidate.source_channel,
            "direction": candidate.direction,
            "entry_delay_s": int(candidate.exit_rule.get("entry_delay_s", 0)),
            "holding_horizon_min": horizon,
            "sample_size": 0,
            "win_rate_pct": 0.0,
            "mean_net_pct": 0.0,
            "median_net_pct": 0.0,
            "p10_net_pct": 0.0,
            "p25_net_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "longest_losing_streak": 0,
            "profit_factor": 0.0,
            "symbol_count": 0,
            "top_symbol_share_pct": 0.0,
            "top1_removed_mean_net_pct": 0.0,
            "walk_forward_windows": 0,
            "walk_forward_positive_windows": 0,
            "walk_forward_positive_rate_pct": 0.0,
            "score": -999.0,
        }
        row["decision"], row["reject_reason"] = _decision(row, min_sample)
        row["hypothesis"] = candidate.hypothesis
        row["novelty_reason"] = candidate.novelty_reason
        return row

    equity = values_pct.cumsum()
    drawdown = equity - equity.cummax()
    if "symbol" in subset.columns:
        symbol_counts = subset.loc[values.index, "symbol"].value_counts(dropna=True)
        symbol_count = int(symbol_counts.shape[0])
        top_symbol_share_pct = round(float(symbol_counts.iloc[0] / len(values) * 100), 4) if not symbol_counts.empty else 0.0
    else:
        symbol_count = 0
        top_symbol_share_pct = 0.0
    cutoff = values_pct.quantile(0.99) if len(values_pct) >= 100 else values_pct.max() + 1
    top1_removed = values_pct[values_pct < cutoff]
    wf = _walk_forward_stats(subset, values)

    row = {
        "candidate_id": candidate.candidate_id,
        "family": candidate.family,
        "discovery_layer": candidate.discovery_layer,
        "source_channel": candidate.source_channel,
        "direction": candidate.direction,
        "entry_delay_s": int(candidate.exit_rule.get("entry_delay_s", 0)),
        "holding_horizon_min": horizon,
        "sample_size": int(values_pct.shape[0]),
        "win_rate_pct": round(float((values_pct > 0).mean() * 100), 4),
        "mean_net_pct": round(float(values_pct.mean()), 6),
        "median_net_pct": round(float(values_pct.median()), 6),
        "p10_net_pct": round(float(values_pct.quantile(0.10)), 6),
        "p25_net_pct": round(float(values_pct.quantile(0.25)), 6),
        "max_drawdown_pct": round(float(drawdown.min()), 6),
        "longest_losing_streak": int(_longest_losing_streak(values_pct)),
        "profit_factor": round(_profit_factor(values_pct), 6),
        "symbol_count": symbol_count,
        "top_symbol_share_pct": top_symbol_share_pct,
        "top1_removed_mean_net_pct": round(float(top1_removed.mean()), 6) if not top1_removed.empty else 0.0,
        **wf,
    }
    dd_penalty = min(abs(row["max_drawdown_pct"]) / 25.0, 15.0)
    concentration_penalty = max(0.0, row["top_symbol_share_pct"] - 20.0) / 5.0
    losing_penalty = min(row["longest_losing_streak"] / 4.0, 10.0)
    row["score"] = round(
        row["median_net_pct"] * 5.0
        + row["mean_net_pct"] * 1.5
        + row["p25_net_pct"] * 2.0
        + (row["win_rate_pct"] - 50.0) / 5.0
        + row["walk_forward_positive_rate_pct"] / 20.0
        - dd_penalty
        - concentration_penalty
        - losing_penalty,
        6,
    )
    row["decision"], row["reject_reason"] = _decision(row, min_sample)
    row["hypothesis"] = candidate.hypothesis
    row["novelty_reason"] = candidate.novelty_reason
    return row


def _candidate(
    idx: int,
    *,
    source_channel: str,
    family: str,
    layer: str,
    direction: str,
    hypothesis: str,
    entry_rule: dict[str, Any],
    filters: dict[str, Any] | None = None,
    exit_type: str = "fixed_horizon",
    delay: int = 0,
    horizon: int = 5,
    novelty_reason: str,
    max_position_frac: float = 0.5,
) -> CandidateSpec:
    prefix = {"known_family_refinement": "K", "controlled_new_strategy_discovery": "D", "contrarian_exploratory": "X"}.get(layer, "C")
    exit_rule: dict[str, Any] = {"type": exit_type, "entry_delay_s": delay}
    if exit_type == "fixed_horizon":
        exit_rule["holding_horizon_min"] = horizon
    else:
        exit_rule["fallback_horizon_min"] = horizon
    return CandidateSpec(
        candidate_id=f"{prefix}{idx:04d}_{family}_{direction}_{delay}s_{horizon}m",
        hypothesis=hypothesis,
        source_channel=source_channel,
        family=family,
        discovery_layer=layer,
        direction=direction,
        entry_rule=entry_rule,
        filters=filters or {},
        exit_rule=exit_rule,
        risk_rule={"max_position_frac": max_position_frac, "paper_only": True},
        novelty_reason=novelty_reason,
    )


def generate_hypotheses(max_hypotheses: int = 120) -> list[CandidateSpec]:
    """Generate a bounded 70/20/10 mix of known, discovery, and contrarian candidates."""
    candidates: list[CandidateSpec] = []
    i = 1

    def add(**kwargs: Any) -> None:
        nonlocal i
        if len(candidates) < max_hypotheses:
            candidates.append(_candidate(i, **kwargs))
            i += 1

    # Known-family refinement: OI shorts, pricechange filters, Reserved6 extremes.
    for oi_ratio in [8, 10, 15, 20]:
        for day in [0, 10, 20]:
            for delay, horizon in [(60, 15), (60, 60), (180, 60)]:
                add(
                    source_channel="BWE_OI_Price_monitor",
                    family="oi_overcrowded_pump_reversal_short",
                    layer="known_family_refinement",
                    direction="short",
                    hypothesis="OI&Price pump with high OI/marketcap is crowded and tends to mean-revert after delayed entry.",
                    entry_rule={"event_type": "pump", "oi_ratio_pct_gte": oi_ratio, "day_change_pct_gte": day},
                    delay=delay,
                    horizon=horizon,
                    novelty_reason="known OI short family; threshold/delay/hold refinement",
                    max_position_frac=0.5,
                )
    for oi_ratio in [8, 10, 15]:
        for day_down in [-5, -10, -15]:
            for delay, horizon in [(0, 60), (10, 60), (30, 60), (60, 60), (180, 60)]:
                add(
                    source_channel="BWE_OI_Price_monitor",
                    family="oi_overcrowded_crash_follow_short",
                    layer="known_family_refinement",
                    direction="short",
                    hypothesis="OI/Marketcap remains crowded during a down move; liquidation pressure can continue after the event.",
                    entry_rule={"event_type": "crash", "oi_ratio_pct_gte": oi_ratio, "day_change_pct_lte": day_down},
                    delay=delay,
                    horizon=horizon,
                    novelty_reason="known OI crash-follow family refinement matching prior fullrun winners",
                    max_position_frac=0.5,
                )
    for delay, horizon in [(0, 60), (10, 60), (30, 60), (60, 60), (180, 60)]:
        add(
            source_channel="BWE_OI_Price_monitor",
            family="oi_negative_oi_pump_reversal_short",
            layer="known_family_refinement",
            direction="short",
            hypothesis="OI falls while price pumps, suggesting spot/short-covering exhaustion rather than durable leverage demand; fade the pump.",
            entry_rule={"event_type": "pump", "oi_change_pct_lt": 0, "move_pct_gte": 8},
            delay=delay,
            horizon=horizon,
            novelty_reason="known OI negative-OI pump reversal family from fullrun winners",
            max_position_frac=0.5,
        )
    for move in [5, 8, 10, 15]:
        for delay, horizon in [(0, 15), (0, 60), (10, 60)]:
            add(
                source_channel="BWE_Reserved6",
                family="r6_bigmove_pump_fade_short",
                layer="known_family_refinement",
                direction="short",
                hypothesis="Reserved6 extreme pump marks short-term liquidity exhaustion; fade after extreme move.",
                entry_rule={"event_type": "pump", "move_pct_gte": move},
                delay=delay,
                horizon=horizon,
                novelty_reason="known Reserved6 pump-fade family refinement",
                max_position_frac=0.35,
            )
            add(
                source_channel="BWE_Reserved6",
                family="r6_bigmove_crash_cont_short",
                layer="known_family_refinement",
                direction="short",
                hypothesis="Reserved6 extreme crash can continue as liquidation cascade; short continuation.",
                entry_rule={"event_type": "crash", "move_pct_lte": -move},
                delay=delay,
                horizon=horizon,
                novelty_reason="known Reserved6 crash-continuation family refinement",
                max_position_frac=0.35,
            )

    # Controlled new discovery.
    for delay, horizon in [(0, 5), (10, 5), (30, 15), (60, 30)]:
        add(
            source_channel="BWE_pricechange_monitor",
            family="pc_second_signal_cont_long",
            layer="controlled_new_strategy_discovery",
            direction="long",
            hypothesis="A second same-symbol pricechange pump is evidence of propagation, making continuation long more stable than first signal chase.",
            entry_rule={"event_type": "pump", "burst_seq_5m_eq": 2},
            filters={"liquidity_bucket_in": ["mid", "high"]},
            delay=delay,
            horizon=horizon,
            novelty_reason="new repeat-trigger/burst-state entry alpha",
            max_position_frac=0.25,
        )
        add(
            source_channel="BWE_pricechange_monitor",
            family="pc_third_plus_overheat_short",
            layer="controlled_new_strategy_discovery",
            direction="short",
            hypothesis="Third-plus same-symbol pump in a 5m burst indicates overheat/exhaustion rather than safe continuation.",
            entry_rule={"event_type": "pump", "burst_seq_5m_gte": 3},
            filters={"liquidity_bucket_in": ["mid", "high"]},
            delay=delay,
            horizon=horizon,
            novelty_reason="new burst exhaustion entry alpha",
            max_position_frac=0.25,
        )
    for delay, horizon in [(0, 15), (30, 30), (60, 60)]:
        add(
            source_channel="BWE_Reserved6",
            family="r6_oi_confirm_pump_fade_short",
            layer="controlled_new_strategy_discovery",
            direction="short",
            hypothesis="Reserved6 pump followed by OI confirmation is a crowded blow-off, suitable for fade short.",
            entry_rule={"event_type": "pump", "move_pct_gte": 8, "confirm_after_5m_oi": True},
            filters={"liquidity_bucket_in": ["mid", "high"]},
            exit_type="channel_invalidated_exit",
            delay=delay,
            horizon=horizon,
            novelty_reason="new cross-channel alpha plus channel-invalidated exit family",
            max_position_frac=0.25,
        )
        add(
            source_channel="BWE_pricechange_monitor",
            family="pc_reserved6_confirm_fade_short",
            layer="controlled_new_strategy_discovery",
            direction="short",
            hypothesis="Pricechange pump that also triggers Reserved6 is more likely an exhaustion spike than ordinary continuation.",
            entry_rule={"event_type": "pump", "confirm_after_5m_reserved6": True},
            filters={"liquidity_bucket_in": ["mid", "high"]},
            exit_type="prove_then_exit",
            delay=delay,
            horizon=horizon,
            novelty_reason="new cross-channel confirmation fade entry",
            max_position_frac=0.25,
        )
    for trend in ["trend_up_all", "short_up_long_down"]:
        for delay, horizon in [(30, 15), (60, 30)]:
            add(
                source_channel="BWE_OI_Price_monitor",
                family="oi_trend_up_all_reversal_short",
                layer="controlled_new_strategy_discovery",
                direction="short",
                hypothesis="OI pump after already extended pre-trend has worse chase asymmetry and better reversal potential.",
                entry_rule={"event_type": "pump", "trend_state": trend, "oi_ratio_pct_gte": 8},
                delay=delay,
                horizon=horizon,
                novelty_reason="new pre-trend state-machine entry alpha",
                max_position_frac=0.35,
            )

    # Contrarian/exploratory: lower budget, stricter by downstream validation.
    for delay, horizon in [(10, 3), (30, 5), (60, 15)]:
        add(
            source_channel="BWE_pricechange_monitor",
            family="pc_crash_cont_short_highliq",
            layer="contrarian_exploratory",
            direction="short",
            hypothesis="High-liquidity pricechange crashes may continue briefly as momentum/liquidation, contrary to default bounce-long instinct.",
            entry_rule={"event_type": "crash"},
            filters={"liquidity_bucket_in": ["high"]},
            delay=delay,
            horizon=horizon,
            novelty_reason="contrarian continuation after crash in high-liquidity bucket",
            max_position_frac=0.15,
        )
        add(
            source_channel="BWE_Reserved6",
            family="r6_bigmove_crash_bounce_long",
            layer="contrarian_exploratory",
            direction="long",
            hypothesis="Some Reserved6 extreme crashes may be capitulation bounces; test as watchlist-only contrarian long.",
            entry_rule={"event_type": "crash", "move_pct_lte": -10},
            filters={"liquidity_bucket_in": ["mid", "high"]},
            delay=delay,
            horizon=horizon,
            novelty_reason="contrarian crash-bounce hypothesis, paper/watchlist only unless very strong",
            max_position_frac=0.10,
        )
    result = candidates[:max_hypotheses]
    if max_hypotheses >= 20 and "pc_second_signal_cont_long" not in {c.family for c in result}:
        result[-3] = _candidate(
            9997,
            source_channel="BWE_pricechange_monitor",
            family="pc_second_signal_cont_long",
            layer="controlled_new_strategy_discovery",
            direction="long",
            hypothesis="A second same-symbol pricechange pump is evidence of propagation, making continuation long more stable than first signal chase.",
            entry_rule={"event_type": "pump", "burst_seq_5m_eq": 2},
            filters={"liquidity_bucket_in": ["mid", "high"]},
            delay=30,
            horizon=15,
            novelty_reason="new repeat-trigger/burst-state entry alpha",
            max_position_frac=0.25,
        )
    if max_hypotheses >= 20 and "r6_oi_confirm_pump_fade_short" not in {c.family for c in result}:
        result[-2] = _candidate(
            9998,
            source_channel="BWE_Reserved6",
            family="r6_oi_confirm_pump_fade_short",
            layer="controlled_new_strategy_discovery",
            direction="short",
            hypothesis="Reserved6 pump followed by OI confirmation is a crowded blow-off, suitable for fade short.",
            entry_rule={"event_type": "pump", "move_pct_gte": 8, "confirm_after_5m_oi": True},
            filters={"liquidity_bucket_in": ["mid", "high"]},
            exit_type="channel_invalidated_exit",
            delay=30,
            horizon=30,
            novelty_reason="new cross-channel alpha plus channel-invalidated exit family",
            max_position_frac=0.25,
        )
    if max_hypotheses >= 20 and not any(c.discovery_layer == "contrarian_exploratory" for c in result):
        result[-1] = _candidate(
            9999,
            source_channel="BWE_pricechange_monitor",
            family="pc_crash_cont_short_highliq",
            layer="contrarian_exploratory",
            direction="short",
            hypothesis="High-liquidity pricechange crashes may continue briefly as momentum/liquidation, contrary to default bounce-long instinct.",
            entry_rule={"event_type": "crash"},
            filters={"liquidity_bucket_in": ["high"]},
            delay=30,
            horizon=5,
            novelty_reason="contrarian continuation after crash in high-liquidity bucket",
            max_position_frac=0.15,
        )
    return result


def neighborhood_stability(scoreboard: pd.DataFrame) -> pd.DataFrame:
    if scoreboard.empty:
        return pd.DataFrame(columns=["family", "candidate_count", "median_score", "positive_median_share_pct", "promote_count", "watchlist_count"])
    grouped = []
    for family, g in scoreboard.groupby("family"):
        grouped.append(
            {
                "family": family,
                "candidate_count": int(g.shape[0]),
                "median_score": round(float(g["score"].median()), 6) if "score" in g else 0.0,
                "positive_median_share_pct": round(float((g["median_net_pct"] > 0).mean() * 100), 4) if "median_net_pct" in g else 0.0,
                "promote_count": int((g["decision"] == "promote_to_paper").sum()) if "decision" in g else 0,
                "watchlist_count": int((g["decision"] == "watchlist").sum()) if "decision" in g else 0,
            }
        )
    return pd.DataFrame(grouped).sort_values(["promote_count", "median_score"], ascending=[False, False])


def write_outputs(out_dir: str | Path, candidates: list[CandidateSpec], scoreboard: pd.DataFrame, stability: pd.DataFrame) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "new_hypotheses.jsonl").write_text("\n".join(c.to_json() for c in candidates) + "\n", encoding="utf-8")
    scoreboard = scoreboard.copy()
    if not scoreboard.empty and "score" in scoreboard.columns:
        scoreboard = scoreboard.sort_values(["decision", "score", "median_net_pct"], ascending=[True, False, False])
    scoreboard.to_csv(out / "discovery_scoreboard.csv", index=False)
    stability.to_csv(out / "neighborhood_stability.csv", index=False)

    top = scoreboard[scoreboard.get("decision", pd.Series(dtype=str)).isin(["promote_to_paper", "watchlist"])].head(50) if not scoreboard.empty else pd.DataFrame()
    entries = []
    exits = []
    cand_map = {c.candidate_id: c for c in candidates}
    for _, row in top.iterrows():
        c = cand_map.get(row["candidate_id"])
        if not c:
            continue
        d = asdict(c)
        d["metrics"] = {k: row[k] for k in row.index if k not in {"hypothesis", "novelty_reason"}}
        entries.append(d)
        exits.append({"candidate_id": c.candidate_id, "family": c.family, "exit_rule": c.exit_rule, "metrics": d["metrics"]})
    (out / "new_entry_candidates.jsonl").write_text("\n".join(json.dumps(x, ensure_ascii=False, sort_keys=True) for x in entries) + ("\n" if entries else ""), encoding="utf-8")
    (out / "new_exit_candidates.jsonl").write_text("\n".join(json.dumps(x, ensure_ascii=False, sort_keys=True) for x in exits) + ("\n" if exits else ""), encoding="utf-8")

    reject = scoreboard[scoreboard.get("decision", pd.Series(dtype=str)).isin(["reject", "need_more_data"])] if not scoreboard.empty else pd.DataFrame()
    reject.to_csv(out / "hypothesis_reject_log.csv", index=False)

    counts = scoreboard["decision"].value_counts().to_dict() if not scoreboard.empty and "decision" in scoreboard else {}

    def _lines(df: pd.DataFrame, limit: int = 10) -> list[str]:
        lines = []
        for _, r in df.head(limit).iterrows() if not df.empty else []:
            p25 = float(r.get("p25_net_pct", 0.0))
            lines.append(
                f"- `{r['candidate_id']}` {r['decision']} score={float(r.get('score', 0.0)):.2f} "
                f"n={int(r.get('sample_size', 0))} win={float(r.get('win_rate_pct', 0.0)):.1f}% "
                f"median={float(r.get('median_net_pct', 0.0)):.2f}% mean={float(r.get('mean_net_pct', 0.0)):.2f}% "
                f"p25={p25:.2f}% wf+={float(r.get('walk_forward_positive_rate_pct', 0.0)):.1f}% family={r['family']} "
                f"reason={r.get('reject_reason', '')}"
            )
        return lines

    promote_df = scoreboard[scoreboard.get("decision", pd.Series(dtype=str)) == "promote_to_paper"] if not scoreboard.empty else pd.DataFrame()
    watch_df = scoreboard[scoreboard.get("decision", pd.Series(dtype=str)) == "watchlist"] if not scoreboard.empty else pd.DataFrame()
    reject_df = scoreboard[scoreboard.get("decision", pd.Series(dtype=str)) == "reject"] if not scoreboard.empty else pd.DataFrame()
    promote_lines = _lines(promote_df, 10)
    watch_lines = _lines(watch_df, 15)
    reject_lines = _lines(reject_df, 8)

    report = f"""# BWE 三频道 AutoResearch Round 1 Discovery 报告

## 范围
- 数据：历史三频道 forward parquet。
- 频道：OI&Price、pricechange、Reserved6。
- 模式：70/20/10 known refinement / controlled discovery / contrarian exploratory。
- 边界：sandbox only；未触碰 live；未读取 secrets；未下单；未改 live config。

## 结果计数
```json
{json.dumps(counts, ensure_ascii=False, indent=2)}
```

## Promote to paper
{chr(10).join(promote_lines) if promote_lines else '- 本轮没有直接晋级 paper 的候选。'}

## Watchlist（下一轮优先复核）
{chr(10).join(watch_lines) if watch_lines else '- 本轮没有 watchlist 候选。'}

## Top rejects（被左尾/稳定性拦下）
{chr(10).join(reject_lines) if reject_lines else '- 暂无 reject。'}

## 解释
`promote_to_paper` 只代表历史数据通过初筛；仍需 paper shadow 20+ clean complete 后才可考虑 live。
`watchlist` 是有潜力但还不够强；`need_more_data` 通常是样本不足；`reject` 是 median/左尾/稳定性不过关。
"""
    (out / "round1_discovery_report_zh.md").write_text(report, encoding="utf-8")


def refuse_if_live_path(path: str | Path) -> None:
    p = str(path).lower()
    if any(marker in p for marker in LIVE_PATH_MARKERS):
        raise ValueError(f"refusing live/order/autotrader path: {path}")


def run_discovery(forward_parquet: str | Path, out_dir: str | Path, max_hypotheses: int = 120, min_sample: int = 60) -> pd.DataFrame:
    refuse_if_live_path(forward_parquet)
    refuse_if_live_path(out_dir)
    forward = pd.read_parquet(forward_parquet)
    candidates = generate_hypotheses(max_hypotheses=max_hypotheses)
    rows = []
    for c in candidates:
        candidate_min_sample = min_sample
        if c.source_channel == "BWE_Reserved6":
            candidate_min_sample = min(min_sample, 20)
        rows.append(score_candidate(forward, c, min_sample=candidate_min_sample))
    scoreboard = pd.DataFrame(rows).sort_values(["score", "median_net_pct"], ascending=[False, False])
    stability = neighborhood_stability(scoreboard)
    write_outputs(out_dir, candidates, scoreboard, stability)
    return scoreboard


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run BWE three-channel sandbox AutoResearch discovery")
    parser.add_argument("--forward-parquet", default="/Users/ye/.hermes/research/bwe_three_channel_fullrun3/forward.parquet")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--max-hypotheses", type=int, default=120)
    parser.add_argument("--min-sample", type=int, default=60)
    args = parser.parse_args(argv)
    scoreboard = run_discovery(args.forward_parquet, args.out_dir, args.max_hypotheses, args.min_sample)
    print(json.dumps({"rows": int(scoreboard.shape[0]), "decisions": scoreboard["decision"].value_counts().to_dict()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
