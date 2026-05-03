"""BWE Deep AutoResearch round-2 post analysis.

Sandbox/offline utilities for the user-requested second round after the broad
entry/exit search:

* adversarial stress tests for top entry and exit candidates
* cross-channel / lead-lag propagation search
* interpretable meta-router candidate construction
* execution-aware friction simulation
* paper experiment manifest generation

This module writes only research/paper-runtime artifacts.  It does not import or
modify live trading code, launchd files, order clients, tokens, or secrets.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from bwe_autoresearch import deep_autoresearch as da

DEFAULT_DEEP_RUN_DIR = Path("/Users/ye/Desktop/GitHub/Autoresearch/runs/bwe_deep_autoresearch_20260425_round2_full_exit")
DEFAULT_OUT_DIR = Path("/Users/ye/.hermes/research/bwe_deep_autoresearch_20260425/round2_post")
DEFAULT_PAPER_RUNTIME = Path("/Users/ye/.hermes/research/bwe_paper_multilot_observer_runtime")

LIVE_PATH_MARKERS = ("bwe_live_autotrader", "LaunchAgents/ai.hermes.bwe-live", "okx_order", "binance_order")


def refuse_live_path(path: Path) -> None:
    text = str(path)
    if any(marker in text for marker in LIVE_PATH_MARKERS):
        raise ValueError(f"refusing live/order path: {path}")


def ensure_out_dir(path: Path) -> Path:
    refuse_live_path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_read_parquet(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    return pd.read_parquet(path, columns=columns)


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        value = float(value)
        if math.isfinite(value):
            return value
    except Exception:
        pass
    return default


def profit_factor(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    gains = values[values > 0].sum()
    losses = -values[values < 0].sum()
    if losses <= 0:
        return float("inf") if gains > 0 else 0.0
    return float(gains / losses)


def longest_losing_streak(values: np.ndarray) -> int:
    longest = cur = 0
    for val in np.asarray(values, dtype=float):
        if val < 0:
            cur += 1
            longest = max(longest, cur)
        else:
            cur = 0
    return int(longest)


def max_drawdown(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    if values.size == 0:
        return 0.0
    equity = np.cumsum(values)
    peak = np.maximum.accumulate(equity)
    return float((equity - peak).min())


def metrics_from_values(values: Iterable[float], *, symbols: Iterable[Any] | None = None, months: Iterable[Any] | None = None) -> dict[str, Any]:
    arr = pd.to_numeric(pd.Series(list(values)), errors="coerce").replace([np.inf, -np.inf], np.nan).dropna().to_numpy(dtype=float)
    if arr.size == 0:
        return {
            "sample_size": 0,
            "win_rate_pct": 0.0,
            "mean_net_pct": 0.0,
            "median_net_pct": 0.0,
            "p10_net_pct": 0.0,
            "p25_net_pct": 0.0,
            "profit_factor": 0.0,
            "max_drawdown_pct": 0.0,
            "longest_losing_streak": 0,
            "top_symbol_share_pct": 0.0,
            "walk_forward_positive_rate_pct": 0.0,
        }
    out = {
        "sample_size": int(arr.size),
        "win_rate_pct": round(float((arr > 0).mean() * 100.0), 6),
        "mean_net_pct": round(float(arr.mean()), 6),
        "median_net_pct": round(float(np.median(arr)), 6),
        "p10_net_pct": round(float(np.quantile(arr, 0.10)), 6),
        "p25_net_pct": round(float(np.quantile(arr, 0.25)), 6),
        "profit_factor": round(profit_factor(arr), 6),
        "max_drawdown_pct": round(max_drawdown(arr), 6),
        "longest_losing_streak": longest_losing_streak(arr),
        "top_symbol_share_pct": 0.0,
        "walk_forward_positive_rate_pct": 0.0,
    }
    if symbols is not None:
        sy = pd.Series(list(symbols)).iloc[: arr.size]
        if len(sy):
            out["top_symbol_share_pct"] = round(float(sy.value_counts(normalize=True).iloc[0] * 100.0), 6)
    if months is not None:
        mo = pd.Series(list(months)).iloc[: arr.size]
        if len(mo):
            tmp = pd.DataFrame({"month": mo.to_numpy(), "value": arr})
            month_mean = tmp.groupby("month")["value"].mean()
            out["walk_forward_positive_rate_pct"] = round(float((month_mean > 0).mean() * 100.0), 6)
    return out


def cooldown_rows(df: pd.DataFrame, *, minutes: int = 60, symbol_col: str = "symbol", ts_col: str = "ts_ms") -> pd.DataFrame:
    if df.empty or symbol_col not in df.columns or ts_col not in df.columns:
        return df.copy()
    kept_idx: list[int] = []
    last_ts: dict[str, int] = {}
    gap = minutes * 60_000
    for idx, row in df.sort_values(ts_col).iterrows():
        sym = str(row[symbol_col])
        ts = int(row[ts_col])
        if sym not in last_ts or ts - last_ts[sym] >= gap:
            kept_idx.append(idx)
            last_ts[sym] = ts
    return df.loc[kept_idx].copy()


def load_forward(forward_path: Path, hourly_path: Path) -> pd.DataFrame:
    return da.prepare_forward_frame(forward_path, hourly_path)


def branch_entry_subset(forward: pd.DataFrame, branch: pd.Series) -> pd.DataFrame:
    rule = json.loads(str(branch.get("base_rule_json", "{}")))
    mask = da._series_mask(forward, rule)
    subset = forward.loc[mask].copy()
    for col in ["entry_delay_s", "liquidity_bucket", "marketcap_bucket_norm", "btc_regime", "trend_alignment"]:
        if col in subset.columns and col in branch.index:
            subset = subset[subset[col].astype(str) == str(branch[col])]
    return subset.sort_values("ts_ms")


def candidate_grade(metrics: dict[str, Any]) -> str:
    sample = int(metrics.get("sample_size", 0))
    med = safe_float(metrics.get("median_net_pct"))
    p25 = safe_float(metrics.get("p25_net_pct"))
    win = safe_float(metrics.get("win_rate_pct"))
    pf = safe_float(metrics.get("profit_factor"))
    if sample >= 40 and med > 0 and p25 > -0.75 and win >= 52 and pf >= 1.05:
        return "survive"
    if sample >= 25 and med > 0 and p25 > -1.50 and win >= 50:
        return "degrade"
    return "fail"


def stress_entry_candidates(deep_run_dir: Path, forward: pd.DataFrame, out_dir: Path, *, top_n: int = 80) -> tuple[pd.DataFrame, pd.DataFrame]:
    entry_scores = safe_read_parquet(deep_run_dir / "entry_scores.parquet")
    eligible = entry_scores[
        (entry_scores.get("decision", "") .isin(["watchlist", "promote_to_deep_exit"]))
        & (pd.to_numeric(entry_scores.get("sample_size", 0), errors="coerce").fillna(0) >= 25)
    ].copy()
    if eligible.empty:
        return pd.DataFrame(), pd.DataFrame()
    eligible = eligible.sort_values(["score_stability_first", "score_profit_first"], ascending=False).head(top_n)
    rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    rng = np.random.default_rng(20260425)

    for _, branch in eligible.iterrows():
        horizon = int(branch["holding_horizon_min"])
        net_col = f"net_{horizon}m"
        subset = branch_entry_subset(forward, branch)
        if net_col not in subset.columns:
            continue
        base_values = pd.to_numeric(subset[net_col], errors="coerce") * 100.0
        base_metrics = metrics_from_values(base_values, symbols=subset.get("symbol"), months=subset.get("month"))
        tests: dict[str, tuple[pd.DataFrame, np.ndarray]] = {}
        tests["baseline"] = (subset, base_values.to_numpy(dtype=float))
        if "symbol" in subset.columns and not subset.empty:
            top_symbols = subset["symbol"].value_counts().head(5).index.tolist()
            tests["top1_symbol_removed"] = (subset[~subset["symbol"].isin(top_symbols[:1])], pd.to_numeric(subset.loc[~subset["symbol"].isin(top_symbols[:1]), net_col], errors="coerce").to_numpy(dtype=float) * 100.0)
            tests["top5_symbols_removed"] = (subset[~subset["symbol"].isin(top_symbols)], pd.to_numeric(subset.loc[~subset["symbol"].isin(top_symbols), net_col], errors="coerce").to_numpy(dtype=float) * 100.0)
        cd = cooldown_rows(subset, minutes=60)
        tests["cooldown_60m_one_symbol"] = (cd, pd.to_numeric(cd[net_col], errors="coerce").to_numpy(dtype=float) * 100.0 if net_col in cd.columns else np.array([]))
        if not subset.empty:
            mid_ts = subset["ts_ms"].quantile(0.5)
            early = subset[subset["ts_ms"] <= mid_ts]
            late = subset[subset["ts_ms"] > mid_ts]
            tests["walk_forward_first_half"] = (early, pd.to_numeric(early[net_col], errors="coerce").to_numpy(dtype=float) * 100.0)
            tests["walk_forward_second_half"] = (late, pd.to_numeric(late[net_col], errors="coerce").to_numpy(dtype=float) * 100.0)
        for extra in (0.20, 0.50, 1.00):
            tests[f"fee_slippage_extra_{extra:.2f}pct"] = (subset, base_values.to_numpy(dtype=float) - extra)
        # Placebo: compare edge to random same-horizon events, not used as a trade signal.
        universe = pd.to_numeric(forward.get(net_col, pd.Series(dtype=float)), errors="coerce").dropna().to_numpy(dtype=float) * 100.0
        placebo_pctl = np.nan
        if universe.size and base_metrics["sample_size"] >= 5:
            means = []
            n = min(base_metrics["sample_size"], universe.size)
            for _ in range(200):
                means.append(float(np.mean(rng.choice(universe, size=n, replace=False))))
            placebo_pctl = round(float((np.array(means) < base_metrics["mean_net_pct"]).mean() * 100.0), 6)
        stress_grades: list[str] = []
        for test_name, (test_df, vals) in tests.items():
            m = metrics_from_values(vals, symbols=test_df.get("symbol") if not test_df.empty else None, months=test_df.get("month") if not test_df.empty else None)
            grade = candidate_grade(m)
            if test_name != "baseline":
                stress_grades.append(grade)
            rows.append({
                "candidate_type": "entry",
                "branch_id": branch["branch_id"],
                "family": branch["family"],
                "archetype_id": branch["archetype_id"],
                "side": branch.get("direction"),
                "horizon_min": horizon,
                "test_name": test_name,
                "stress_grade": grade,
                "placebo_mean_percentile": placebo_pctl if test_name == "baseline" else np.nan,
                **m,
            })
        non_fail = sum(1 for g in stress_grades if g != "fail")
        final_grade = "survive" if base_metrics["sample_size"] >= 25 and base_metrics["median_net_pct"] > 0 and non_fail >= max(4, int(0.6 * len(stress_grades))) and (math.isnan(placebo_pctl) or placebo_pctl >= 70) else "degrade"
        if any(g == "fail" for g in stress_grades) and non_fail < max(3, int(0.5 * len(stress_grades))):
            final_grade = "fail"
        summary_rows.append({
            "candidate_type": "entry",
            "branch_id": branch["branch_id"],
            "family": branch["family"],
            "archetype_id": branch["archetype_id"],
            "mapped_strategy": da._map_entry_to_strategy(branch),
            "side": branch.get("direction"),
            "entry_delay_s": int(branch.get("entry_delay_s", 0)),
            "horizon_min": horizon,
            "source_channel": branch.get("source_channel"),
            "base_score_stability_first": branch.get("score_stability_first"),
            "base_score_profit_first": branch.get("score_profit_first"),
            "base_sample_size": base_metrics["sample_size"],
            "base_median_net_pct": base_metrics["median_net_pct"],
            "base_p25_net_pct": base_metrics["p25_net_pct"],
            "placebo_mean_percentile": placebo_pctl,
            "non_fail_stress_tests": non_fail,
            "total_stress_tests": len(stress_grades),
            "stress_final_grade": final_grade,
            "base_rule_json": branch.get("base_rule_json"),
            "description": branch.get("description"),
        })
    detail = pd.DataFrame(rows)
    summary = pd.DataFrame(summary_rows).sort_values(["stress_final_grade", "base_score_stability_first"], ascending=[True, False]) if summary_rows else pd.DataFrame()
    detail.to_csv(out_dir / "adversarial_entry_stress_detail.csv", index=False)
    summary.to_csv(out_dir / "adversarial_entry_stress_summary.csv", index=False)
    return detail, summary


def build_active_strategy_context(forward: pd.DataFrame, path_5m_path: Path) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    strategy_rows = da._build_active_strategy_rows(forward)
    path_df = pd.read_parquet(
        path_5m_path,
        columns=["event_key", "channel", "post_id", "symbol", "exchange", "alias", "event_ts_ms", "bar_ts_ms", "open", "high", "low", "close", "volume", "quote_volume"],
    )
    return strategy_rows, path_df


def evaluate_exit_branch(branch: pd.Series, rows_df: pd.DataFrame, path_df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, dict[int, str], dict[str, Any]]:
    strategy_name = str(branch["strategy_name"])
    family = str(branch["family"])
    params = json.loads(str(branch.get("params_json", "{}")))
    bundle = da.build_strategy_bundle(rows_df, path_df[path_df["event_key"].isin(rows_df["event_key"])].copy(), da.ACTIVE_EXIT_STRATEGY_CONFIG[strategy_name])
    values, reasons, labels = da.FAST_EXIT_EVALUATORS[family](bundle, params)
    return values, reasons, labels, bundle


def stress_exit_candidates(deep_run_dir: Path, forward: pd.DataFrame, path_5m_path: Path, out_dir: Path, *, top_n: int = 80) -> tuple[pd.DataFrame, pd.DataFrame]:
    exit_top_path = deep_run_dir / "exit_top200.csv"
    if not exit_top_path.exists():
        return pd.DataFrame(), pd.DataFrame()
    exit_top = pd.read_csv(exit_top_path)
    exit_catalog = safe_read_parquet(deep_run_dir / "exit_catalog.parquet")
    if exit_top.empty:
        return pd.DataFrame(), pd.DataFrame()
    exit_top = exit_top.merge(exit_catalog[["branch_id", "params_json"]], on="branch_id", how="left")
    exit_top = exit_top.sort_values(["score_stability_first", "score_profit_first"], ascending=False).head(top_n)
    strategy_rows, path_df = build_active_strategy_context(forward, path_5m_path)
    rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    rng = np.random.default_rng(20260425)

    for _, branch in exit_top.iterrows():
        strategy_name = str(branch["strategy_name"])
        rows_df = strategy_rows.get(strategy_name, pd.DataFrame()).copy()
        if rows_df.empty:
            continue
        tests: dict[str, pd.DataFrame] = {"baseline": rows_df}
        if "symbol" in rows_df.columns:
            top_symbols = rows_df["symbol"].value_counts().head(5).index.tolist()
            tests["top1_symbol_removed"] = rows_df[~rows_df["symbol"].isin(top_symbols[:1])]
            tests["top5_symbols_removed"] = rows_df[~rows_df["symbol"].isin(top_symbols)]
        tests["cooldown_60m_one_symbol"] = cooldown_rows(rows_df, minutes=60, ts_col="entry_ts_ms" if "entry_ts_ms" in rows_df.columns else "ts_ms")
        mid = rows_df["entry_ts_ms"].quantile(0.5) if "entry_ts_ms" in rows_df.columns else rows_df["ts_ms"].quantile(0.5)
        ts_col = "entry_ts_ms" if "entry_ts_ms" in rows_df.columns else "ts_ms"
        tests["walk_forward_first_half"] = rows_df[rows_df[ts_col] <= mid]
        tests["walk_forward_second_half"] = rows_df[rows_df[ts_col] > mid]
        stress_grades: list[str] = []
        base_metrics: dict[str, Any] = {}
        placebo_pctl = np.nan
        for test_name, test_rows in tests.items():
            values, reasons, labels, bundle = evaluate_exit_branch(branch, test_rows, path_df)
            m = metrics_from_values(values, symbols=test_rows.get("symbol"), months=bundle.get("months"))
            grade = candidate_grade(m)
            if test_name != "baseline":
                stress_grades.append(grade)
            else:
                base_metrics = m
                universe_col = "net_60m" if "net_60m" in rows_df.columns else None
                if universe_col and m["sample_size"] >= 5:
                    universe = pd.to_numeric(forward[universe_col], errors="coerce").dropna().to_numpy(dtype=float) * 100.0
                    if universe.size:
                        n = min(m["sample_size"], universe.size)
                        means = [float(np.mean(rng.choice(universe, size=n, replace=False))) for _ in range(200)]
                        placebo_pctl = round(float((np.array(means) < m["mean_net_pct"]).mean() * 100.0), 6)
            rows.append({
                "candidate_type": "exit",
                "branch_id": branch["branch_id"],
                "strategy_name": strategy_name,
                "family": branch["family"],
                "variation": branch.get("variation"),
                "test_name": test_name,
                "stress_grade": grade,
                "placebo_mean_percentile": placebo_pctl if test_name == "baseline" else np.nan,
                **m,
            })
        for extra in (0.20, 0.50, 1.00):
            values, reasons, labels, bundle = evaluate_exit_branch(branch, rows_df, path_df)
            m = metrics_from_values(values - extra, symbols=rows_df.get("symbol"), months=bundle.get("months"))
            grade = candidate_grade(m)
            stress_grades.append(grade)
            rows.append({
                "candidate_type": "exit",
                "branch_id": branch["branch_id"],
                "strategy_name": strategy_name,
                "family": branch["family"],
                "variation": branch.get("variation"),
                "test_name": f"fee_slippage_extra_{extra:.2f}pct",
                "stress_grade": grade,
                "placebo_mean_percentile": np.nan,
                **m,
            })
        non_fail = sum(1 for g in stress_grades if g != "fail")
        final_grade = "survive" if base_metrics.get("sample_size", 0) >= 25 and base_metrics.get("median_net_pct", 0) > 0 and non_fail >= max(4, int(0.6 * len(stress_grades))) and (math.isnan(placebo_pctl) or placebo_pctl >= 70) else "degrade"
        if any(g == "fail" for g in stress_grades) and non_fail < max(3, int(0.5 * len(stress_grades))):
            final_grade = "fail"
        summary_rows.append({
            "candidate_type": "exit",
            "branch_id": branch["branch_id"],
            "strategy_name": strategy_name,
            "family": branch["family"],
            "variation": branch.get("variation"),
            "base_score_stability_first": branch.get("score_stability_first"),
            "base_score_profit_first": branch.get("score_profit_first"),
            "base_sample_size": base_metrics.get("sample_size", 0),
            "base_median_net_pct": base_metrics.get("median_net_pct", 0.0),
            "base_p25_net_pct": base_metrics.get("p25_net_pct", 0.0),
            "placebo_mean_percentile": placebo_pctl,
            "non_fail_stress_tests": non_fail,
            "total_stress_tests": len(stress_grades),
            "stress_final_grade": final_grade,
            "params_json": branch.get("params_json"),
        })
    detail = pd.DataFrame(rows)
    summary = pd.DataFrame(summary_rows).sort_values(["stress_final_grade", "base_score_stability_first"], ascending=[True, False]) if summary_rows else pd.DataFrame()
    detail.to_csv(out_dir / "adversarial_exit_stress_detail.csv", index=False)
    summary.to_csv(out_dir / "adversarial_exit_stress_summary.csv", index=False)
    return detail, summary


def cross_channel_propagation(forward: pd.DataFrame, out_dir: Path) -> pd.DataFrame:
    required = {"event_key", "symbol", "channel", "ts_ms", "event_type", "side"}
    if not required <= set(forward.columns):
        return pd.DataFrame()
    base = forward[list(required | {"net_5m", "net_10m", "net_30m", "net_60m", "move_pct", "oi_ratio_pct", "prev_hour_quote_volume", "marketcap_bucket_norm", "btc_regime", "trend_alignment"} & set(forward.columns))].copy()
    base = base.dropna(subset=["symbol", "ts_ms"]).sort_values(["symbol", "ts_ms"])
    candidates: list[dict[str, Any]] = []
    windows = [30_000, 60_000, 180_000, 300_000, 600_000, 1_800_000]
    horizons = [5, 10, 30, 60]
    for src_ch in sorted(base["channel"].dropna().unique()):
        src = base[base["channel"] == src_ch].sort_values("ts_ms")
        if src.empty:
            continue
        for tgt_ch in sorted(base["channel"].dropna().unique()):
            if tgt_ch == src_ch:
                continue
            tgt = base[base["channel"] == tgt_ch].sort_values("ts_ms")
            if tgt.empty:
                continue
            src2 = src.rename(columns={"ts_ms": "source_ts_ms"}).copy()
            src2["ts_ms"] = src2["source_ts_ms"]
            tgt2 = tgt.rename(columns={"ts_ms": "target_ts_ms"}).copy()
            tgt2["ts_ms"] = tgt2["target_ts_ms"]
            merged = pd.merge_asof(
                src2.sort_values("ts_ms"),
                tgt2.sort_values("ts_ms"),
                on="ts_ms",
                by="symbol",
                direction="forward",
                allow_exact_matches=False,
                suffixes=("_src", "_tgt"),
                tolerance=max(windows),
            ).dropna(subset=["event_key_tgt", "target_ts_ms"])
            if merged.empty:
                continue
            merged["lag_ms"] = pd.to_numeric(merged["target_ts_ms"], errors="coerce") - pd.to_numeric(merged["source_ts_ms"], errors="coerce")
            merged = merged[(merged["lag_ms"] > 0) & (merged["lag_ms"] <= max(windows))]
            if merged.empty:
                continue
            for window_ms in windows:
                windowed = merged[merged["lag_ms"] <= window_ms]
                if windowed.empty:
                    continue
                for horizon in horizons:
                    net_col = f"net_{horizon}m_tgt"
                    if net_col not in windowed.columns:
                        continue
                    group_cols = ["channel_src", "channel_tgt", "event_type_src", "event_type_tgt", "side_tgt"]
                    for keys, group in windowed.groupby(group_cols, dropna=False):
                        values = pd.to_numeric(group[net_col], errors="coerce") * 100.0
                        m = metrics_from_values(values, symbols=group.get("symbol"), months=None)
                        if m["sample_size"] < 20:
                            continue
                        candidates.append({
                            "source_channel": keys[0],
                            "target_channel": keys[1],
                            "source_event_type": keys[2],
                            "target_event_type": keys[3],
                            "target_side": keys[4],
                            "confirm_window_s": int(window_ms / 1000),
                            "median_lag_s": round(float(group["lag_ms"].median() / 1000.0), 3),
                            "trade_at": "target_confirmation_event",
                            "horizon_min": horizon,
                            "stress_grade": candidate_grade(m),
                            **m,
                        })
    out = pd.DataFrame(candidates)
    if not out.empty:
        out = out.sort_values(["stress_grade", "median_net_pct", "p25_net_pct", "sample_size"], ascending=[True, False, False, False])
    out.to_csv(out_dir / "cross_channel_leadlag_candidates.csv", index=False)
    return out


def build_meta_router(entry_summary: pd.DataFrame, exit_summary: pd.DataFrame, cross: pd.DataFrame, out_dir: Path) -> pd.DataFrame:
    rules: list[dict[str, Any]] = []
    if not entry_summary.empty:
        entries = entry_summary[entry_summary["stress_final_grade"].isin(["survive", "degrade"])].copy()
        exits = exit_summary[exit_summary["stress_final_grade"].isin(["survive", "degrade"])] if not exit_summary.empty else pd.DataFrame()
        for _, e in entries.sort_values(["stress_final_grade", "base_score_stability_first"], ascending=[True, False]).head(60).iterrows():
            strategy = e.get("mapped_strategy")
            ex = pd.DataFrame()
            if not exits.empty and pd.notna(strategy):
                ex = exits[exits["strategy_name"] == strategy].sort_values(["stress_final_grade", "base_score_stability_first"], ascending=[True, False]).head(1)
            exit_branch_id = ex.iloc[0]["branch_id"] if not ex.empty else "paper_filter_only"
            exit_family = ex.iloc[0]["family"] if not ex.empty else "paper_filter_only"
            risk_multiplier = 0.35 if e["stress_final_grade"] == "survive" else 0.20
            if not ex.empty and ex.iloc[0]["stress_final_grade"] == "survive":
                risk_multiplier += 0.10
            rules.append({
                "router_rule_id": f"R{len(rules)+1:03d}",
                "rule_source": "entry_exit_survivor",
                "action": "paper_trade" if exit_branch_id != "paper_filter_only" else "paper_filter_only",
                "strategy_name": strategy,
                "entry_branch_id": e["branch_id"],
                "entry_family": e["family"],
                "side": e.get("side"),
                "source_channel": e.get("source_channel"),
                "entry_delay_s": int(e.get("entry_delay_s", 0)),
                "holding_horizon_min": int(e.get("horizon_min", 0)),
                "exit_branch_id": exit_branch_id,
                "exit_family": exit_family,
                "risk_multiplier": round(float(min(risk_multiplier, 0.50)), 3),
                "rule_text": f"IF {e.get('source_channel')} / {e.get('family')} passes stress={e.get('stress_final_grade')} THEN {('paper trade with ' + str(exit_family)) if exit_branch_id != 'paper_filter_only' else 'paper filter only'}; no live.",
                "entry_stress_grade": e.get("stress_final_grade"),
                "exit_stress_grade": ex.iloc[0]["stress_final_grade"] if not ex.empty else "none",
                "base_sample_size": e.get("base_sample_size"),
                "base_median_net_pct": e.get("base_median_net_pct"),
                "base_p25_net_pct": e.get("base_p25_net_pct"),
            })
    if not exit_summary.empty:
        exit_only = exit_summary[exit_summary["stress_final_grade"].isin(["survive", "degrade"])].copy()
        for _, ex in exit_only.sort_values(["stress_final_grade", "base_score_stability_first"], ascending=[True, False]).head(30).iterrows():
            risk_multiplier = 0.30 if ex["stress_final_grade"] == "survive" else 0.18
            rules.append({
                "router_rule_id": f"R{len(rules)+1:03d}",
                "rule_source": "exit_survivor_existing_trigger",
                "action": "paper_trade",
                "strategy_name": ex.get("strategy_name"),
                "entry_branch_id": f"existing_trigger::{ex.get('strategy_name')}",
                "entry_family": ex.get("strategy_name"),
                "side": "short" if "short" in str(ex.get("strategy_name", "")) else "unknown",
                "source_channel": "existing_active_trigger",
                "entry_delay_s": 0,
                "holding_horizon_min": 0,
                "exit_branch_id": ex.get("branch_id"),
                "exit_family": ex.get("family"),
                "risk_multiplier": risk_multiplier,
                "rule_text": f"IF existing active paper trigger {ex.get('strategy_name')} fires THEN create paper-only A/B lot using exit {ex.get('branch_id')}; no live.",
                "entry_stress_grade": "existing_trigger_not_changed",
                "exit_stress_grade": ex.get("stress_final_grade"),
                "base_sample_size": ex.get("base_sample_size"),
                "base_median_net_pct": ex.get("base_median_net_pct"),
                "base_p25_net_pct": ex.get("base_p25_net_pct"),
                "exit_params_json": ex.get("params_json"),
            })
    if not cross.empty:
        cross_ok = cross[(cross["stress_grade"].isin(["survive", "degrade"])) & (cross["sample_size"] >= 25)].head(30)
        for _, c in cross_ok.iterrows():
            rules.append({
                "router_rule_id": f"R{len(rules)+1:03d}",
                "rule_source": "cross_channel_propagation",
                "action": "paper_filter_only",
                "strategy_name": "cross_channel_leadlag_candidate",
                "entry_branch_id": "cross_channel_generated",
                "entry_family": f"{c['source_channel']}→{c['target_channel']}",
                "side": c.get("target_side"),
                "source_channel": c.get("source_channel"),
                "entry_delay_s": 0,
                "holding_horizon_min": int(c.get("horizon_min", 0)),
                "exit_branch_id": "paper_filter_only",
                "exit_family": "paper_filter_only",
                "risk_multiplier": 0.15 if c["stress_grade"] == "survive" else 0.10,
                "rule_text": f"IF {c['source_channel']} is followed by {c['target_channel']} confirmation within {c['confirm_window_s']}s on same symbol THEN observe target-side {c['target_side']} in paper only.",
                "entry_stress_grade": c.get("stress_grade"),
                "exit_stress_grade": "none",
                "base_median_net_pct": c.get("median_net_pct"),
                "base_p25_net_pct": c.get("p25_net_pct"),
            })
    router = pd.DataFrame(rules)
    if not router.empty:
        router = router.sort_values(["action", "risk_multiplier", "base_median_net_pct"], ascending=[True, False, False])
    router.to_csv(out_dir / "meta_router_rules.csv", index=False)
    (out_dir / "meta_router_rules.json").write_text(json.dumps(router.to_dict("records"), ensure_ascii=False, indent=2), encoding="utf-8")
    return router


def execution_aware_simulation(router: pd.DataFrame, entry_summary: pd.DataFrame, out_dir: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if router.empty:
        return pd.DataFrame()
    entry_lookup = entry_summary.set_index("branch_id") if not entry_summary.empty else pd.DataFrame()
    for _, rule in router.iterrows():
        entry_branch = rule.get("entry_branch_id")
        base = entry_lookup.loc[entry_branch].to_dict() if isinstance(entry_lookup, pd.DataFrame) and not entry_lookup.empty and entry_branch in entry_lookup.index else {}
        base_median = safe_float(rule.get("base_median_net_pct", base.get("base_median_net_pct", 0.0)))
        base_p25 = safe_float(rule.get("base_p25_net_pct", base.get("base_p25_net_pct", 0.0)))
        sample = int(safe_float(rule.get("base_sample_size", base.get("base_sample_size", 0)), 0))
        liq_penalty = 0.12
        entry_family = str(rule.get("entry_family", ""))
        if "high" in entry_family:
            liq_penalty = 0.06
        elif "low" in entry_family or "mcap" in entry_family:
            liq_penalty = 0.22
        for delay_s, delay_penalty in [(0, 0.00), (3, 0.03), (10, 0.08), (30, 0.18), (60, 0.35)]:
            missing_price_penalty = 0.05 if delay_s <= 10 else 0.10
            adjusted_median = base_median - liq_penalty - delay_penalty - missing_price_penalty
            adjusted_p25 = base_p25 - liq_penalty - delay_penalty - missing_price_penalty
            status = "survive_execution" if sample >= 25 and adjusted_median > 0 and adjusted_p25 > -1.0 and rule.get("entry_stress_grade") != "fail" else "execution_watch_only"
            rows.append({
                **rule.to_dict(),
                "message_delay_s": delay_s,
                "liquidity_slippage_penalty_pct": liq_penalty,
                "delay_penalty_pct": delay_penalty,
                "missing_price_penalty_pct": missing_price_penalty,
                "adjusted_median_net_pct": round(float(adjusted_median), 6),
                "adjusted_p25_net_pct": round(float(adjusted_p25), 6),
                "execution_status": status,
            })
    out = pd.DataFrame(rows)
    if not out.empty:
        out["_execution_rank"] = out["execution_status"].map({"survive_execution": 0, "execution_watch_only": 1}).fillna(2)
        out["_action_rank"] = out["action"].map({"paper_trade": 0, "paper_filter_only": 1}).fillna(2)
        out = out.sort_values(["_execution_rank", "_action_rank", "adjusted_median_net_pct", "adjusted_p25_net_pct"], ascending=[True, True, False, False]).drop(columns=["_execution_rank", "_action_rank"])
    out.to_csv(out_dir / "execution_aware_candidates.csv", index=False)
    return out


def write_paper_experiment_manifest(execution_candidates: pd.DataFrame, out_dir: Path, paper_runtime: Path) -> dict[str, Any]:
    ensure_out_dir(paper_runtime)
    chosen = execution_candidates[
        (execution_candidates.get("execution_status") == "survive_execution")
        & (execution_candidates.get("message_delay_s") <= 10)
    ].copy() if not execution_candidates.empty else pd.DataFrame()
    chosen = chosen.head(30)
    experiments = []
    for idx, row in enumerate(chosen.to_dict("records"), 1):
        experiments.append({
            "experiment_id": f"round2_auto_{idx:03d}",
            "status": "paper_ready_manifest_only",
            "live_allowed": False,
            "paper_only": True,
            "required_clean_complete": 20,
            "entry_branch_id": row.get("entry_branch_id"),
            "entry_family": row.get("entry_family"),
            "exit_branch_id": row.get("exit_branch_id"),
            "exit_family": row.get("exit_family"),
            "strategy_name": row.get("strategy_name"),
            "side": row.get("side"),
            "risk_multiplier": row.get("risk_multiplier"),
            "message_delay_s": row.get("message_delay_s"),
            "adjusted_median_net_pct": row.get("adjusted_median_net_pct"),
            "adjusted_p25_net_pct": row.get("adjusted_p25_net_pct"),
            "notes": "Generated by round2_analysis; observer/live must not trade live from this manifest. Use for paper experiment tracking only.",
        })
    manifest = {
        "schema": "bwe_round2_paper_experiment_manifest_v1",
        "paper_only": True,
        "live_allowed": False,
        "required_clean_complete_per_strategy": 20,
        "experiments": experiments,
        "status_counters": {
            "paper_ready_manifest_only": len(experiments),
            "clean_complete_required": 20,
        },
    }
    text = json.dumps(manifest, ensure_ascii=False, indent=2)
    (out_dir / "paper_experiment_manifest_round2.json").write_text(text, encoding="utf-8")
    (paper_runtime / "paper_experiment_manifest_round2.json").write_text(text, encoding="utf-8")
    return manifest


def write_report(out_dir: Path, deep_run_dir: Path, entry_summary: pd.DataFrame, exit_summary: pd.DataFrame, cross: pd.DataFrame, router: pd.DataFrame, execution: pd.DataFrame, manifest: dict[str, Any]) -> None:
    def top_lines(df: pd.DataFrame, cols: list[str], n: int = 8) -> list[str]:
        if df.empty:
            return ["- 暂无"]
        lines = []
        for row in df.head(n)[cols].to_dict("records"):
            lines.append("- " + " | ".join(f"{k}={row.get(k)}" for k in cols))
        return lines

    entry_survive = int((entry_summary.get("stress_final_grade") == "survive").sum()) if not entry_summary.empty else 0
    exit_survive = int((exit_summary.get("stress_final_grade") == "survive").sum()) if not exit_summary.empty else 0
    exec_survive = int((execution.get("execution_status") == "survive_execution").sum()) if not execution.empty else 0
    lines = [
        "# BWE AutoResearch Round2 Post Analysis 报告",
        "",
        "## 总结",
        "",
        f"- deep run dir: `{deep_run_dir}`",
        f"- entry 反证 survive: `{entry_survive}`",
        f"- exit 反证 survive: `{exit_survive}`",
        f"- execution-aware survive rows: `{exec_survive}`",
        f"- paper manifest experiments: `{len(manifest.get('experiments', []))}`",
        "- 所有产物均为 sandbox / paper-only；未写 live、未下单。",
        "",
        "## Entry 反证压力测试 Top",
        *top_lines(entry_summary.sort_values(["stress_final_grade", "base_score_stability_first"], ascending=[True, False]) if not entry_summary.empty else entry_summary, ["branch_id", "family", "mapped_strategy", "stress_final_grade", "base_sample_size", "base_median_net_pct", "base_p25_net_pct", "placebo_mean_percentile"]),
        "",
        "## Exit 反证压力测试 Top",
        *top_lines(exit_summary.sort_values(["stress_final_grade", "base_score_stability_first"], ascending=[True, False]) if not exit_summary.empty else exit_summary, ["branch_id", "strategy_name", "family", "stress_final_grade", "base_sample_size", "base_median_net_pct", "base_p25_net_pct", "placebo_mean_percentile"]),
        "",
        "## Cross-channel 二阶传播候选 Top",
        *top_lines(cross.sort_values(["stress_grade", "median_net_pct", "sample_size"], ascending=[True, False, False]) if not cross.empty else cross, ["source_channel", "target_channel", "source_event_type", "target_event_type", "target_side", "confirm_window_s", "horizon_min", "stress_grade", "sample_size", "median_net_pct", "p25_net_pct"]),
        "",
        "## Meta-router 规则 Top",
        *top_lines(router, ["router_rule_id", "action", "strategy_name", "entry_family", "exit_family", "risk_multiplier", "entry_stress_grade", "exit_stress_grade"]),
        "",
        "## Execution-aware 通过项 Top",
        *top_lines(execution[execution.get("execution_status") == "survive_execution"] if not execution.empty else execution, ["router_rule_id", "message_delay_s", "execution_status", "adjusted_median_net_pct", "adjusted_p25_net_pct", "entry_family", "exit_family"]),
        "",
        "## 拦下/观察原因",
        "",
        "- stress_final_grade=fail：样本、左尾、去头部符号、walk-forward、费用压力或 placebo 不过。",
        "- execution_watch_only：研究上可能有 alpha，但实盘摩擦后中位数或 p25 不够稳，只能继续 paper 观察。",
        "- paper manifest 默认 `live_allowed=false`；达到每策略 20+ clean complete 后才允许复核，不自动切 live。",
    ]
    (out_dir / "round2_post_analysis_report_zh.md").write_text("\n".join(lines), encoding="utf-8")


def run(args: argparse.Namespace) -> dict[str, Any]:
    deep_run_dir = Path(args.deep_run_dir)
    out_dir = ensure_out_dir(Path(args.out_dir))
    paper_runtime = Path(args.paper_runtime)
    forward = load_forward(Path(args.forward_parquet), Path(args.hourly_parquet))
    entry_detail, entry_summary = stress_entry_candidates(deep_run_dir, forward, out_dir, top_n=args.top_n)
    exit_detail, exit_summary = stress_exit_candidates(deep_run_dir, forward, Path(args.path_5m_parquet), out_dir, top_n=args.top_n)
    cross = cross_channel_propagation(forward, out_dir)
    router = build_meta_router(entry_summary, exit_summary, cross, out_dir)
    execution = execution_aware_simulation(router, entry_summary, out_dir)
    manifest = write_paper_experiment_manifest(execution, out_dir, paper_runtime)
    write_report(out_dir, deep_run_dir, entry_summary, exit_summary, cross, router, execution, manifest)
    summary = {
        "out_dir": str(out_dir),
        "entry_stress_rows": int(entry_detail.shape[0]) if not entry_detail.empty else 0,
        "exit_stress_rows": int(exit_detail.shape[0]) if not exit_detail.empty else 0,
        "cross_channel_candidates": int(cross.shape[0]) if not cross.empty else 0,
        "router_rules": int(router.shape[0]) if not router.empty else 0,
        "execution_rows": int(execution.shape[0]) if not execution.empty else 0,
        "paper_manifest_experiments": len(manifest.get("experiments", [])),
        "report": str(out_dir / "round2_post_analysis_report_zh.md"),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run BWE round2 adversarial/cross-channel/router/execution/paper analysis")
    p.add_argument("--deep-run-dir", default=str(DEFAULT_DEEP_RUN_DIR))
    p.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    p.add_argument("--paper-runtime", default=str(DEFAULT_PAPER_RUNTIME))
    p.add_argument("--forward-parquet", default=str(da.DEFAULT_FORWARD))
    p.add_argument("--hourly-parquet", default=str(da.DEFAULT_HOURLY))
    p.add_argument("--path-5m-parquet", default=str(da.DEFAULT_PATH_5M))
    p.add_argument("--top-n", type=int, default=80)
    return p


def main() -> None:
    summary = run(build_parser().parse_args())
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
