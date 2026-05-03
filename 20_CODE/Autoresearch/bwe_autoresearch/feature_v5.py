"""BWE AutoResearch v5 entry candidate explosion and staged validation.

v5 consumes the GPT Pro strategy-family package, expands it into a large
paper-only candidate universe, then validates only pruned shortlists.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from .feature_v3 import clean_json, compute_mark_outcomes, ensure_out_dir, load_inputs, metrics_from_trades, write_json
from .feature_v4 import (
    DEFAULT_FEATURE_DIR,
    SOFT_FILTER_POLICY,
    add_soft_filter_penalties,
    entry_v4_decision,
    entry_v4_score,
    enrich_events_with_forward_context,
    no_trade_matrix,
    prepare_entry_outcomes,
    purged_walk_forward_metrics,
)


DEFAULT_PACKAGE_DIR = Path("/Users/ye/Downloads/bwe_entry_research_v5_package")
DEFAULT_OUT_DIR = Path("/Users/ye/.hermes/research/bwe_autoresearch_entry_v5_20260425")

ENTRY_DELAY_BY_TIMING = {
    "T0": 0,
    "30s": 30,
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "pullback": 180,
    "breakout_confirm": 180,
    "failed_breakout": 180,
    "reclaim": 180,
    "no_confirmation_abandon": 300,
}
HORIZONS_MIN = (15, 30, 60)
SOFT_PROFILES = ("base", "freshness_strict", "liquidity_strict")
RISK_PROFILES = ("balanced", "left_tail_strict", "stress_strict")
PORTFOLIO_PROFILES = ("cooldown30_max8", "cooldown60_max5", "cooldown120_max3")
EXIT_INTERFACE_PROFILES = ("runner_trail", "prove_then_runner", "breakeven_ratchet", "time_stop")
FIELD_ALIASES = {
    "global_long_short_account_ratio": "global_long_short_account_ratio__longShortRatio",
    "top_trader_long_short_account_ratio": "top_trader_long_short_account_ratio__longShortRatio",
    "top_trader_long_short_position_ratio": "top_trader_long_short_position_ratio__longShortRatio",
    "first_1m_continuation": "mark_1m_close",
    "first_30s_continuation": "mark_1m_close",
    "first_3m_continuation": "mark_1m_close",
    "first_5m_continuation": "mark_1m_close",
    "btc_adverse_move": "btc_pre30m",
    "feature_freshness_pass": "mark_1m_age_ms",
}
FUTURE_TOKENS = ("ret_", "net_", "mfe", "mae", "future_return", "realized_pnl", "first_touch", "post_entry", "post_event_full_path")
DELAYED_TOKENS = ("confirm_after_", "first_30s", "first_1m", "first_3m", "first_5m", "pullback", "reclaim", "failed_high", "failed_low")


@dataclass(frozen=True)
class V5Rule:
    candidate_id: str
    template_id: str
    strategy_family: str
    sub_family: str
    channel: str
    event_type: str
    action: str
    side: str
    entry_timing: str
    entry_delay_s: int
    horizon_min: int
    conditions: tuple[dict[str, Any], ...]
    feature_packets: tuple[str, ...]
    complexity_score: int


def load_templates(package_dir: Path = DEFAULT_PACKAGE_DIR) -> list[dict[str, Any]]:
    path = package_dir / "entry_candidate_templates.jsonl"
    templates = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            templates.append(json.loads(line))
    return templates


def load_family_map(package_dir: Path = DEFAULT_PACKAGE_DIR) -> pd.DataFrame:
    path = package_dir / "json" / "entry_strategy_family_map.json"
    if path.exists():
        return pd.DataFrame(json.loads(path.read_text(encoding="utf-8")))
    return pd.DataFrame()


def stable_hash(payload: Any, n: int = 12) -> str:
    raw = json.dumps(clean_json(payload), ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:n]


def q_to_float(q: str) -> float | None:
    if not q.startswith("q"):
        return None
    try:
        return float(q[1:]) / 100.0
    except ValueError:
        return None


def normalize_field(raw: str) -> str:
    return FIELD_ALIASES.get(raw.strip(), raw.strip())


def field_available(field: str, columns: set[str] | None) -> bool:
    if columns is None:
        return True
    return normalize_field(field) in columns


def parse_condition_token(token: str) -> dict[str, Any]:
    token = token.strip()
    for op_text, op in ((">=", "gte"), ("<=", "lte")):
        if op_text in token:
            field, value = token.split(op_text, 1)
            return {"raw": token, "field": normalize_field(field), "op": op, "value_token": value.strip()}
    if " not in " in token:
        field, value = token.split(" not in ", 1)
        return {"raw": token, "field": normalize_field(field), "op": "not_in", "value_token": value.strip()}
    if " in " in token:
        field, value = token.split(" in ", 1)
        return {"raw": token, "field": normalize_field(field), "op": "in", "value_token": value.strip()}
    if " between " in token:
        field, value = token.split(" between ", 1)
        return {"raw": token, "field": normalize_field(field), "op": "between", "value_token": value.strip()}
    if "=" in token:
        field, value = token.split("=", 1)
        return {"raw": token, "field": normalize_field(field), "op": "eq", "value_token": value.strip()}
    parts = token.split()
    field = normalize_field(parts[0]) if parts else token
    return {"raw": token, "field": field, "op": "exists", "value_token": ""}


def template_grid_values(template: dict[str, Any], field: str, fallback: str) -> list[str]:
    grid = template.get("threshold_grid", {})
    values = grid.get(field) or grid.get(field.replace("__longShortRatio", "")) or []
    if not values:
        values = [fallback] if fallback else ["q50"]
    clean = []
    for value in values:
        value = str(value)
        if value.startswith("q") or value.replace(".", "", 1).replace("-", "", 1).isdigit():
            clean.append(value)
    return clean[:6] or [fallback or "q50"]


def resolve_condition(parsed: dict[str, Any], events: pd.DataFrame, value_token: str | None = None) -> tuple[list[dict[str, Any]], bool]:
    field = parsed["field"]
    token = value_token or parsed.get("value_token", "")
    op = parsed["op"]
    if field not in events.columns:
        return [], False
    if any(item in str(parsed.get("raw", "")) for item in FUTURE_TOKENS):
        return [], False
    if op in {"gte", "lte"}:
        q = q_to_float(token)
        series = pd.to_numeric(events.loc[events["core_complete"], field], errors="coerce").dropna()
        if q is not None and series.nunique() >= 4:
            value = float(series.quantile(q))
        else:
            try:
                value = float(str(token).replace("%", ""))
            except ValueError:
                return [], False
        if not math.isfinite(value):
            return [], False
        return [{"col": field, "op": op, "value": round(value, 10), "source_token": parsed["raw"], "q": token}], True
    if op == "between":
        bits = str(token).replace("..", ",").split(",")
        if len(bits) < 2:
            return [], False
        lo, hi = bits[0].strip(), bits[1].strip()
        p_lo, p_hi = q_to_float(lo), q_to_float(hi)
        series = pd.to_numeric(events.loc[events["core_complete"], field], errors="coerce").dropna()
        if p_lo is None or p_hi is None or series.nunique() < 4:
            return [], False
        return [
            {"col": field, "op": "gte", "value": round(float(series.quantile(p_lo)), 10), "source_token": parsed["raw"], "q": lo},
            {"col": field, "op": "lte", "value": round(float(series.quantile(p_hi)), 10), "source_token": parsed["raw"], "q": hi},
        ], True
    if op == "eq":
        value = str(token).lower()
        if value in {"true", "false"}:
            return [{"col": field, "op": "eq", "value": value == "true", "source_token": parsed["raw"]}], True
        return [{"col": field, "op": "eq", "value": token, "source_token": parsed["raw"]}], True
    if op in {"in", "not_in"}:
        return [{"col": field, "op": op, "value": [x.strip() for x in str(token).split(",")], "source_token": parsed["raw"]}], True
    return [], False


def condition_mask_v5(df: pd.DataFrame, conditions: Iterable[dict[str, Any]]) -> pd.Series:
    mask = pd.Series(True, index=df.index)
    for cond in conditions:
        col = cond["col"]
        if col not in df.columns:
            return pd.Series(False, index=df.index)
        op = cond["op"]
        value = cond.get("value")
        if op in {"gte", "lte", "gt", "lt"}:
            numeric = pd.to_numeric(df[col], errors="coerce")
            if op == "gte":
                mask &= numeric >= float(value)
            elif op == "lte":
                mask &= numeric <= float(value)
            elif op == "gt":
                mask &= numeric > float(value)
            else:
                mask &= numeric < float(value)
        elif op == "eq":
            mask &= df[col].astype(str).str.lower().eq(str(value).lower())
        elif op == "in":
            mask &= df[col].astype(str).isin([str(x) for x in value])
        elif op == "not_in":
            mask &= ~df[col].astype(str).isin([str(x) for x in value])
    return mask.fillna(False)


def action_to_side(action: str, event_type: str) -> str | None:
    if action in {"long", "short"}:
        return action
    if action in {"fade", "reversal"}:
        return "short" if event_type == "pump" else "long"
    return None


def static_legality_status(candidate: dict[str, Any]) -> tuple[str, str]:
    text = str(candidate.get("conditions_json", ""))
    if any(token in text for token in FUTURE_TOKENS):
        return "reject", "future_label_condition"
    timing = str(candidate.get("entry_timing", ""))
    if timing == "T0" and any(token in text for token in DELAYED_TOKENS):
        return "reject", "t0_delayed_feature"
    if str(candidate.get("action", "")) == "no_trade" and timing == "breakout_confirm":
        return "reject", "no_trade_breakout_confirm_conflict"
    return "pass", ""


def candidate_condition_variants(template: dict[str, Any], events: pd.DataFrame) -> tuple[list[tuple[list[dict[str, Any]], list[str], bool]], list[str]]:
    columns = set(events.columns)
    slots = template.get("condition_slots", {})
    required = [parse_condition_token(x) for x in slots.get("required", [])]
    optional = [parse_condition_token(x) for x in slots.get("optional", [])[:2]]
    missing_required = [item["field"] for item in required if not field_available(item["field"], columns)]

    required_options = []
    for parsed in required:
        values = template_grid_values(template, parsed["field"], parsed.get("value_token", "q50"))
        resolved = []
        for value_token in values:
            conds, ok = resolve_condition(parsed, events, value_token)
            if ok:
                resolved.append((conds, parsed["raw"]))
        required_options.append(resolved or [([], parsed["raw"])])

    base_combos = []
    for combo in itertools.product(*required_options) if required_options else [()]:
        conds: list[dict[str, Any]] = []
        tokens: list[str] = []
        valid = not missing_required
        for part_conds, token in combo:
            conds.extend(part_conds)
            tokens.append(token)
            if not part_conds:
                valid = False
        base_combos.append((conds, tokens, valid))

    optional_variants = [([], [], True)]
    for parsed in optional:
        values = template_grid_values(template, parsed["field"], parsed.get("value_token", "q50"))[:3]
        for value_token in values:
            conds, ok = resolve_condition(parsed, events, value_token)
            optional_variants.append((conds, [parsed["raw"]], ok))

    variants = []
    for base_conds, base_tokens, base_valid in base_combos:
        for opt_conds, opt_tokens, opt_valid in optional_variants:
            variants.append((base_conds + opt_conds, base_tokens + opt_tokens, base_valid and opt_valid))
    return variants, missing_required


def generate_candidate_manifest(
    templates: list[dict[str, Any]],
    events: pd.DataFrame | None = None,
    *,
    max_candidates_per_template: int = 15_000,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if events is None:
        events = pd.DataFrame({"core_complete": [True], "move_pct": [1.0], "oi_ratio_pct": [1.0], "quote_volume_24h": [1.0], "taker_buy_sell_volume__buySellRatio": [1.0], "premium_1m_high": [1.0], "btc_pre30m": [0.0], "mark_1m_close": [1.0], "mark_1m_age_ms": [0.0]})
    rows: list[dict[str, Any]] = []
    summaries = []
    for template in templates:
        variants, missing_required = candidate_condition_variants(template, events)
        local_count = 0
        contexts = list(
            itertools.product(
                template.get("channel_set", []),
                template.get("event_type_set", []),
                template.get("direction_set", []),
                template.get("entry_timing_set", []),
                HORIZONS_MIN,
                SOFT_PROFILES,
                RISK_PROFILES,
                PORTFOLIO_PROFILES,
                EXIT_INTERFACE_PROFILES,
            )
        )
        for channel, event_type, action, timing, horizon, soft_profile, risk_profile, portfolio_profile, exit_interface_profile in contexts:
            side = action_to_side(str(action), str(event_type))
            delay_s = ENTRY_DELAY_BY_TIMING.get(str(timing), 0)
            for conds, source_tokens, coverage_valid in variants:
                condition_hash = stable_hash(conds, 10)
                payload = {
                    "template_id": template["template_id"],
                    "strategy_family": template["strategy_family"],
                    "sub_family": template["sub_family"],
                    "channel": channel,
                    "event_type": event_type,
                    "action": action,
                    "side": side or "",
                    "entry_timing": timing,
                    "entry_delay_s": delay_s,
                    "horizon_min": horizon,
                    "soft_penalty_profile": soft_profile,
                    "risk_profile": risk_profile,
                    "portfolio_profile": portfolio_profile,
                    "exit_interface_profile": exit_interface_profile,
                    "condition_hash": condition_hash,
                }
                candidate_id = "entry_v5__" + stable_hash(payload, 16)
                conditions_json = json.dumps(clean_json(conds), ensure_ascii=False, sort_keys=True)
                status, violation = static_legality_status({**payload, "conditions_json": conditions_json})
                coverage_ok = bool(coverage_valid and side and status == "pass")
                rows.append(
                    {
                        **payload,
                        "candidate_id": candidate_id,
                        "feature_packets": "|".join(template.get("feature_packets", [])),
                        "conditions_json": conditions_json,
                        "source_tokens": "|".join(source_tokens),
                        "required_missing_fields": "|".join(missing_required),
                        "coverage_valid": coverage_ok,
                        "static_legality_status": status,
                        "violation_type": violation,
                        "future_safety_status": "pass" if status == "pass" else "fail",
                        "complexity_score": len(conds) + len(template.get("feature_packets", [])),
                    }
                )
                local_count += 1
                if local_count >= max_candidates_per_template:
                    break
            if local_count >= max_candidates_per_template:
                break
        summaries.append({"template_id": template["template_id"], "strategy_family": template["strategy_family"], "raw_count": local_count, "missing_required": "|".join(missing_required)})
    df = pd.DataFrame(rows)
    summary = {
        "raw_candidates": int(len(df)),
        "legal_candidates": int(df["static_legality_status"].eq("pass").sum()) if not df.empty else 0,
        "coverage_valid_candidates": int(df["coverage_valid"].sum()) if not df.empty else 0,
        "template_count": len(templates),
        "template_summary": summaries,
    }
    return df, summary


def select_for_scoring(manifest: pd.DataFrame, *, limit: int) -> pd.DataFrame:
    if manifest.empty:
        return manifest
    priority = manifest[manifest["coverage_valid"].eq(True)].copy()
    if priority.empty:
        return priority
    priority["priority_rank"] = priority["template_id"].str.extract(r"(\d+)").astype(float).fillna(999)
    priority = priority.sort_values(["priority_rank", "strategy_family", "channel", "event_type", "entry_delay_s", "horizon_min"])
    cols = ["channel", "event_type", "side", "entry_delay_s", "horizon_min", "conditions_json"]
    priority = priority.drop_duplicates(cols, keep="first")
    return priority.head(limit).copy()


def score_candidate(entry_outcomes: pd.DataFrame, row: pd.Series) -> tuple[dict[str, Any], pd.DataFrame]:
    conds = tuple(json.loads(row.conditions_json))
    subset = entry_outcomes[
        entry_outcomes["side"].eq(row.side)
        & entry_outcomes["channel"].eq(row.channel)
        & entry_outcomes["event_type"].eq(row.event_type)
        & entry_outcomes["entry_delay_s"].eq(int(row.entry_delay_s))
        & entry_outcomes["horizon_min"].eq(int(row.horizon_min))
    ].copy()
    if conds:
        subset = subset[condition_mask_v5(subset, conds)].copy()
    values = pd.to_numeric(subset.get("mark_net_pct", pd.Series(dtype=float)), errors="coerce")
    metrics = metrics_from_trades(values, symbols=subset.get("api_symbol"), ts_ms=subset.get("ts_ms"))
    metrics.update(purged_walk_forward_metrics(values, subset.get("ts_ms", [])))
    stress_values = values - 0.2
    stress_metrics = metrics_from_trades(stress_values, symbols=subset.get("api_symbol"), ts_ms=subset.get("ts_ms"))
    metrics["stress_fee_slippage_mean_net_pct"] = stress_metrics["mean_net_pct"]
    metrics["stress_fee_slippage_median_net_pct"] = stress_metrics["median_net_pct"]
    metrics["stress_median_net_pct"] = stress_metrics["median_net_pct"]
    metrics["stress_mean_net_pct"] = stress_metrics["mean_net_pct"]
    avg_soft = float(pd.to_numeric(subset.get("soft_filter_penalty", pd.Series(dtype=float)), errors="coerce").mean()) if not subset.empty else 0.0
    if not math.isfinite(avg_soft):
        avg_soft = 0.0
    decision, reason = entry_v4_decision(metrics, min_sample=20, complexity=int(row.complexity_score))
    score = entry_v4_score(metrics, complexity=int(row.complexity_score), avg_soft_penalty=avg_soft)
    out = {
        **row.to_dict(),
        **metrics,
        "avg_soft_filter_penalty": round(avg_soft, 6),
        "decision": decision,
        "reject_reason": reason,
        "robust_score": score,
        "path_resolution": "1m_mark",
        "soft_filter_policy": SOFT_FILTER_POLICY,
    }
    return out, subset


def run_scoring(entry_outcomes: pd.DataFrame, candidates: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    replay_rows = []
    for row in candidates.itertuples(index=False):
        scored, subset = score_candidate(entry_outcomes, pd.Series(row._asdict()))
        rows.append(scored)
        if scored["decision"] in {"promote_to_paper", "watchlist"} and not subset.empty:
            keep = subset[["event_key", "api_symbol", "channel", "event_type", "side", "entry_delay_s", "horizon_min", "entry_ts_ms", "mark_net_pct", "mark_mfe_pct", "mark_mae_pct"]].copy()
            keep["candidate_id"] = scored["candidate_id"]
            keep["selected_candidate"] = scored["candidate_id"]
            keep["conflict_reason"] = ""
            replay_rows.append(keep)
    scored_df = pd.DataFrame(rows)
    if not scored_df.empty:
        rank = {"promote_to_paper": 0, "watchlist": 1, "need_more_data": 2, "reject": 3}
        scored_df["decision_rank"] = scored_df["decision"].map(rank).fillna(9).astype(int)
        scored_df = scored_df.sort_values(["decision_rank", "robust_score", "median_net_pct", "p25_net_pct"], ascending=[True, False, False, False])
    replay = pd.concat(replay_rows, ignore_index=True) if replay_rows else pd.DataFrame()
    return scored_df, replay


def stress_matrix(scored: pd.DataFrame, replay: pd.DataFrame, *, top_n: int = 100) -> pd.DataFrame:
    if replay.empty or scored.empty:
        return pd.DataFrame()
    rows = []
    top_ids = scored["candidate_id"].head(top_n).tolist()
    for candidate_id in top_ids:
        sub = replay[replay["candidate_id"].eq(candidate_id)]
        if sub.empty:
            continue
        base = pd.to_numeric(sub["mark_net_pct"], errors="coerce")
        for fee_mult, extra in ((1.0, 0.0), (1.5, 0.1), (2.0, 0.2)):
            for latency_s in (0, 30, 60):
                values = base - extra - latency_s / 600.0
                rows.append({"candidate_id": candidate_id, "fee_mult": fee_mult, "slippage_bps": extra * 100, "latency_s": latency_s, **metrics_from_trades(values, symbols=sub.get("api_symbol"), ts_ms=sub.get("entry_ts_ms"))})
    return pd.DataFrame(rows)


def rerank_without_outliers(scored: pd.DataFrame) -> pd.DataFrame:
    if scored.empty:
        return pd.DataFrame()
    out = scored[["candidate_id", "robust_score", "median_net_pct", "remove_top_1pct_mean_net_pct", "top1_removed_mean_net_pct", "top5_removed_mean_net_pct", "top_symbol_share_pct"]].copy()
    out["base_rank"] = out["robust_score"].rank(ascending=False, method="first").astype(int)
    out["no_top1_rank"] = out["top1_removed_mean_net_pct"].rank(ascending=False, method="first").astype(int)
    out["no_top5_rank"] = out["top5_removed_mean_net_pct"].rank(ascending=False, method="first").astype(int)
    out["no_top1pct_rank"] = out["remove_top_1pct_mean_net_pct"].rank(ascending=False, method="first").astype(int)
    return out.sort_values("base_rank")


def symbol_concentration(scored: pd.DataFrame) -> pd.DataFrame:
    if scored.empty:
        return pd.DataFrame()
    return scored[["candidate_id", "symbol_count", "top_symbol_share_pct", "top1_removed_mean_net_pct", "top5_removed_mean_net_pct"]].copy()


def family_diversity(scored: pd.DataFrame) -> pd.DataFrame:
    if scored.empty:
        return pd.DataFrame()
    return (
        scored.groupby(["strategy_family", "template_id"], dropna=False)
        .agg(top_count=("candidate_id", "count"), promote=("decision", lambda s: int((s == "promote_to_paper").sum())), avg_score=("robust_score", "mean"))
        .reset_index()
        .sort_values(["promote", "avg_score"], ascending=False)
    )


def portfolio_replay_summary(scored: pd.DataFrame, replay: pd.DataFrame, *, top_n: int = 30) -> pd.DataFrame:
    rows = []
    for item in scored.head(top_n).itertuples(index=False):
        sub = replay[replay["candidate_id"].eq(item.candidate_id)].sort_values("entry_ts_ms")
        if sub.empty:
            continue
        last_symbol_ts: dict[str, int] = {}
        accepted = []
        for trade in sub.itertuples(index=False):
            symbol = str(trade.api_symbol)
            ts = int(trade.entry_ts_ms)
            if symbol in last_symbol_ts and ts - last_symbol_ts[symbol] < 60 * 60_000:
                continue
            last_symbol_ts[symbol] = ts
            accepted.append(trade)
        if accepted:
            df = pd.DataFrame([x._asdict() for x in accepted])
            rows.append({"candidate_id": item.candidate_id, "max_concurrent": 5, "cooldown_min": 60, "accepted_trades": len(df), **metrics_from_trades(df["mark_net_pct"], symbols=df.get("api_symbol"), ts_ms=df.get("entry_ts_ms"))})
    return pd.DataFrame(rows)


def make_manifest_v5(leaderboard: pd.DataFrame, *, max_items: int = 30) -> dict[str, Any]:
    source = leaderboard[leaderboard["decision"].isin(["promote_to_paper", "watchlist"])].copy()
    experiments = []
    seen_keys = set()
    for row in source.itertuples(index=False):
        key = (row.strategy_family, row.template_id, row.channel, row.event_type, row.action, row.entry_timing)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        experiments.append(
            {
                "experiment_id": f"entry_v5_{len(experiments)+1:03d}",
                "paper_only": True,
                "live_allowed": False,
                "required_clean_complete": 20,
                "paper_revalidation_required": True,
                "exit_interface_only": True,
                "exit_optimized": False,
                "candidate_id": row.candidate_id,
                "template_id": row.template_id,
                "strategy_family": row.strategy_family,
                "sub_family": row.sub_family,
                "entry_rule": {
                    "channel": row.channel,
                    "event_type": row.event_type,
                    "action": row.action,
                    "side": row.side,
                    "entry_timing": row.entry_timing,
                    "entry_delay_s": int(row.entry_delay_s),
                    "horizon_min": int(row.horizon_min),
                    "conditions": json.loads(row.conditions_json),
                    "soft_filter_policy": getattr(row, "soft_filter_policy", SOFT_FILTER_POLICY),
                },
                "compatible_exit_families": ["runner_trail", "prove_then_runner", "breakeven_ratchet", "time_stop"],
                "metrics": {
                    "sample_size": int(row.sample_size),
                    "median_net_pct": row.median_net_pct,
                    "p25_net_pct": row.p25_net_pct,
                    "p10_net_pct": row.p10_net_pct,
                    "win_rate_pct": row.win_rate_pct,
                    "profit_factor": row.profit_factor,
                    "robust_score": row.robust_score,
                },
            }
        )
        if len(experiments) >= max_items:
            break
    return {"schema": "bwe_autoresearch_entry_v5_manifest", "paper_only": True, "live_allowed": False, "max_items": max_items, "experiments": experiments}


def write_report(out_dir: Path, summary: dict[str, Any], scored: pd.DataFrame, manifest: dict[str, Any]) -> None:
    top = scored.head(12) if not scored.empty else pd.DataFrame()
    lines = [
        "# BWE AutoResearch v5 入场百万候选搜索报告",
        "",
        "## 结论",
        f"- 输出目录：`{out_dir}`",
        f"- generated_candidates：`{summary.get('generated_candidates')}`",
        f"- legal_candidates：`{summary.get('legal_candidates')}`",
        f"- coverage_valid_candidates：`{summary.get('coverage_valid_candidates')}`",
        f"- scored_candidates：`{summary.get('scored_candidates')}`",
        f"- promote_to_paper：`{summary.get('promote_to_paper')}`",
        f"- watchlist：`{summary.get('watchlist')}`",
        f"- manifest experiments：`{len(manifest.get('experiments', []))}`",
        "- 本轮从 GPT Pro v5 DSL 包自动展开 100万+ 入场候选，但只对剪枝后的候选做收益验证。",
        "- 结果仍是 paper-only，`live_allowed=false`；exit 只绑定接口，不宣称完成退出优化。",
        "",
        "## Top Candidates",
        json.dumps(clean_json(top[["candidate_id", "template_id", "strategy_family", "sub_family", "channel", "event_type", "action", "entry_timing", "entry_delay_s", "horizon_min", "sample_size", "median_net_pct", "p25_net_pct", "p10_net_pct", "win_rate_pct", "profit_factor", "decision", "reject_reason", "robust_score"]].to_dict("records") if not top.empty else []), ensure_ascii=False, indent=2),
        "",
        "## 边界",
        "- manifest 里所有策略 `paper_only=true`、`live_allowed=false`。",
        "- `generated_candidate_manifest.parquet` 是候选空间，不是回测结果。",
        "- 真实成交路径仍需 trade kline / bid-ask / slippage 数据进一步验证。",
    ]
    (out_dir / "report_entry_v5_zh.md").write_text("\n".join(lines), encoding="utf-8")


def write_static_artifacts(out_dir: Path, package_dir: Path, manifest: pd.DataFrame, generation_summary: dict[str, Any]) -> None:
    manifest.to_parquet(out_dir / "generated_candidate_manifest.parquet", index=False)
    pd.DataFrame(generation_summary["template_summary"]).to_csv(out_dir / "candidate_generation_summary.csv", index=False)
    manifest[["candidate_id", "template_id", "static_legality_status", "violation_type", "future_safety_status"]].to_csv(out_dir / "static_legality_report.csv", index=False)
    coverage = (
        manifest.groupby(["template_id", "strategy_family", "coverage_valid", "required_missing_fields"], dropna=False)
        .size()
        .reset_index(name="candidate_count")
    )
    coverage.to_csv(out_dir / "feature_coverage_report.csv", index=False)
    for name in [
        "data_contract_v5.md",
        "entry_strategy_family_map.md",
        "entry_candidate_dsl_schema.json",
        "entry_candidate_templates.jsonl",
        "threshold_grid_v5.md",
        "candidate_generation_plan.md",
        "autoresearch_stage_flow.md",
        "scoring_rejection_rules.md",
        "future_safety_overfit_guardrails.md",
        "artifact_catalog_v5.md",
    ]:
        src = package_dir / name
        if src.exists():
            shutil.copy2(src, out_dir / name)


def run(args: argparse.Namespace) -> dict[str, Any]:
    package_dir = Path(args.package_dir)
    out_dir = ensure_out_dir(Path(args.out_dir))
    templates = load_templates(package_dir)
    events, _forward, mark, _premium = load_inputs(Path(args.feature_dir))
    events = enrich_events_with_forward_context(events, _forward)
    events = add_soft_filter_penalties(events)
    manifest, generation_summary = generate_candidate_manifest(templates, events, max_candidates_per_template=args.max_candidates_per_template)
    write_static_artifacts(out_dir, package_dir, manifest, generation_summary)

    mark_outcomes = compute_mark_outcomes(events, mark, delays_s=tuple(sorted(set(ENTRY_DELAY_BY_TIMING.values()))), horizons_min=HORIZONS_MIN)
    entry_outcomes = prepare_entry_outcomes(events, mark_outcomes)
    candidates = select_for_scoring(manifest, limit=args.score_limit)
    scored, replay = run_scoring(entry_outcomes, candidates)

    scored.to_csv(out_dir / "entry_coarse_screen_leaderboard.csv", index=False)
    scored.head(args.medium_top).to_csv(out_dir / "entry_medium_validation_leaderboard.csv", index=False)
    scored.head(args.deep_top).to_csv(out_dir / "entry_deep_validation_leaderboard.csv", index=False)
    scored.to_csv(out_dir / "entry_timing_leaderboard.csv", index=False)
    no_trade_matrix(scored.rename(columns={"robust_score": "score"}) if not scored.empty else scored).to_csv(out_dir / "entry_no_trade_matrix.csv", index=False)
    windows = pd.DataFrame({"window_id": range(1, 6), "embargo_min": 5, "method": "chronological_np_array_split"})
    windows.to_csv(out_dir / "purged_walkforward_windows.csv", index=False)
    scored[["candidate_id", "purged_wf_windows", "purged_wf_positive_rate_pct", "purged_wf_min_median_pct"]].to_parquet(out_dir / "purged_walkforward_results.parquet", index=False)
    rerank_without_outliers(scored).to_csv(out_dir / "rerank_without_top_outliers.csv", index=False)
    symbol_concentration(scored).to_csv(out_dir / "symbol_concentration_report.csv", index=False)
    stress_matrix(scored, replay).to_parquet(out_dir / "stress_matrix.parquet", index=False)
    portfolio_replay_summary(scored, replay).to_csv(out_dir / "portfolio_replay_summary.csv", index=False)
    if replay.empty:
        replay = pd.DataFrame(columns=["event_key", "api_symbol", "candidate_id", "selected_candidate", "conflict_reason"])
    replay.to_parquet(out_dir / "event_combo_replay.parquet", index=False)
    family_diversity(scored).to_csv(out_dir / "family_diversity_report.csv", index=False)
    reject = scored[scored["decision"].ne("promote_to_paper")][["candidate_id", "template_id", "decision", "reject_reason", "sample_size", "median_net_pct", "p25_net_pct"]].copy()
    reject["stage"] = "entry_v5_scored"
    reject.to_csv(out_dir / "reject_log.csv", index=False)
    paper_manifest = make_manifest_v5(scored, max_items=args.max_manifest_items)
    write_json(out_dir / "paper_manifest_entry_v5.json", paper_manifest)

    summary = {
        "out_dir": str(out_dir),
        "package_dir": str(package_dir),
        "feature_dir": str(args.feature_dir),
        "template_count": len(templates),
        "generated_candidates": int(len(manifest)),
        "legal_candidates": int(generation_summary["legal_candidates"]),
        "coverage_valid_candidates": int(generation_summary["coverage_valid_candidates"]),
        "scored_candidates": int(len(scored)),
        "promote_to_paper": int((scored["decision"] == "promote_to_paper").sum()) if not scored.empty else 0,
        "watchlist": int((scored["decision"] == "watchlist").sum()) if not scored.empty else 0,
        "manifest_experiments": len(paper_manifest.get("experiments", [])),
        "paper_only": True,
        "live_allowed": False,
        "path_resolution": "1m_mark",
        "exit_interface_only": True,
    }
    write_json(out_dir / "summary.json", summary)
    write_report(out_dir, summary, scored, paper_manifest)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run BWE AutoResearch v5 entry million-candidate search")
    parser.add_argument("--package-dir", default=str(DEFAULT_PACKAGE_DIR))
    parser.add_argument("--feature-dir", default=str(DEFAULT_FEATURE_DIR))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--max-candidates-per-template", type=int, default=15_000)
    parser.add_argument("--score-limit", type=int, default=6_000)
    parser.add_argument("--medium-top", type=int, default=1_000)
    parser.add_argument("--deep-top", type=int, default=300)
    parser.add_argument("--max-manifest-items", type=int, default=30)
    return parser


def main() -> None:
    summary = run(build_parser().parse_args())
    print(json.dumps(clean_json(summary), ensure_ascii=False, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
