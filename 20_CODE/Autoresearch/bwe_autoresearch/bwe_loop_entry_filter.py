"""Day 3 (Phase A): Entry archetype filter DSL.

Each archetype's `novel_dim` list is a set of conditions like:
    ["oi_change_pct>=15", "side_signal=pump", "liquidity_bucket=high"]

This module parses those conditions into polars filter expressions that get
applied to the events parquet to subset events to only those matching the
archetype's selectivity criteria.

Three classes of conditions:

1. SUPPORTED — direct mapping or trivial transform to events parquet columns.
   Examples: oi_change_pct, funding_rate, liquidity_bucket, marketcap_bucket,
   listing_age_days, taker_buy_sell_volume__buySellRatio, premium_bps (scaled
   from mark_minus_index_proxy_pct), event_type.

2. SKIP — not a filter condition, it's a parameter for downstream search.
   Examples: delay_seconds=30, fixed_hold_minutes=1, tp_pct=2, side_signal=pump.

3. NOT_YET_SUPPORTED — would require pre-processing or external data we
   don't have wired in for tonight's overnight run.
   Examples: pretrend_5m_pos (need rolling window), burst_count (need event
   chain analysis), btc_24h_pct (need BTC join), session=US (need timestamp
   derivation), basis_widening (need delta).

Skipped conditions are logged but treated as PASS — i.e., no narrowing. So
an archetype whose conditions are all skipped sees the full channel-side
event set (same as if no filter), which is the conservative default.

Usage:
    from bwe_loop_entry_filter import build_filter_expr
    expr, skipped = build_filter_expr(["oi_change_pct>=15", "side_signal=pump"])
    if expr is not None:
        df = pl.scan_parquet(events).filter(expr).collect()
"""

from __future__ import annotations

import re
from typing import Optional

try:
    import polars as pl
    HAS_POLARS = True
except ImportError:  # pragma: no cover
    pl = None  # type: ignore
    HAS_POLARS = False


# ---------------------------------------------------------------------------
# Field mappings: registry novel_dim field name -> events parquet column.
# Verified columns exist in:
#   H:/BWE/30_DATA/input/binance_event_features_20260425_30d/bwe_events_recent_binance_features.parquet
# ---------------------------------------------------------------------------

DIRECT_FIELD_MAP = {
    # Derived columns added by load_events_for_combo
    "hour_utc":               "hour_utc",
    "weekday":                "weekday",
    "session":                "session",
    # Real columns
    "oi_change_pct":          "oi_change_pct",
    "oi_usd":                 "oi_usd",
    "oi_ratio_pct":           "oi_ratio_pct",
    "funding":                "funding_rate",
    "funding_rate":           "funding_rate",
    "liquidity_bucket":       "liquidity_bucket",
    "marketcap":              "marketcap",
    "marketcap_bucket":       "marketcap_bucket",
    "market_cap_bucket":      "marketcap_bucket",
    "listing_age_days":       "listing_age_days",
    "taker_buy_ratio_5m":     "taker_buy_sell_volume__buySellRatio",
    "taker_buy_sell_ratio":   "taker_buy_sell_volume__buySellRatio",
    "day_change_pct":         "day_change_pct",
    "quote_volume_24h":       "quote_volume_24h",
    "move_pct":               "move_pct",
    "event_type":             "event_type",
    "event_family":           "event_family",
    "channel":                "channel",
    # Long-short ratios (commonly invoked as *_high / *_extreme via threshold)
    "top_trader_position_ratio":   "top_trader_long_short_position_ratio__longShortRatio",
    "top_trader_account_ratio":    "top_trader_long_short_account_ratio__longShortRatio",
    "global_long_short_ratio":     "global_long_short_account_ratio__longShortRatio",
    "global_long_ratio":           "global_long_short_account_ratio__longAccount",
    "global_short_ratio":          "global_long_short_account_ratio__shortAccount",
    # Basis & premium
    "basis":                  "basis_perpetual__basis",
    "basis_rate":             "basis_perpetual__basisRate",
    "premium_pct":            "mark_minus_index_proxy_pct",
}

# Some novel_dim use the unit "_bps" (basis points). 1 bp = 0.01 %.
# mark_minus_index_proxy_pct is in PERCENT, so to compare in bps we multiply by 100.
PCT_TO_BPS_FIELDS = {"premium_bps"}  # field name in registry → multiply parquet PCT col by 100

# R5 fix #2: categorical value aliases. R4 整夜发现 marketcap_bucket=small/mid/large
# 实际数据值是 <50m/50m-200m/200m-1b/>=1b/unknown — silent fall-through bug.
# Map LLM-friendly names to actual data values.
CATEGORICAL_VALUE_ALIAS: dict[str, dict[str, list[str]]] = {
    "marketcap_bucket": {
        "small":   ["<50m"],
        "smallcap":["<50m"],  # archetype 名常用 _smallcap_
        "mid":     ["50m-200m", "200m-1b"],
        "midcap":  ["50m-200m", "200m-1b"],
        "large":   [">=1b"],
        "largecap":[">=1b"],
        # Direct values pass through unchanged
        "<50m":     ["<50m"],
        "50m-200m": ["50m-200m"],
        "200m-1b":  ["200m-1b"],
        ">=1b":     [">=1b"],
        "unknown":  ["unknown"],
    },
}

# Event_type values: use these for side_* conditions if helpful. Side is normally
# encoded in the Combo.side, so we usually skip side_signal=/side_event=.

# Fields that are PARAMETERS, not filter conditions. Skip silently.
PARAM_PREFIXES = [
    "delay_seconds",
    "fixed_hold_minutes",
    "max_hold",
    "side_signal=",
    "side_event=",
    "side_change=",
    "tp_pct",
    "sl_pct",
    "tp1=",
    "tp2=",
    "trail=",
    "trail_pct=",
    "trail_atr=",
    "be_trigger=",
    "be_at_",
    "hard_stop=",
    "ladder",
    "size=",
    "max_open_positions=",
    "max_per_",
    "max_trades_per_day",
    "daily_loss_stop",
    "cooldown_",
    "burst_window=",
    "max_pct_per_symbol",
]

# Common phrasings we know about but can't filter on yet (need pre-processing).
# Listed for docs/audit; treated as skipped (pass-through).
NOT_YET_SUPPORTED_PREFIXES = [
    "pretrend_",
    "burst_count_",
    "burst_seq_",
    "burst_density_",
    "btc_24h_pct",
    "btc_correlation_30d",
    "btc_atr_",
    "btc_dom_",
    "btc_realized_vol_",
    "near_macro_event",
    "no_macro_",
    "no_fed_",
    "no_cpi_",
    "post_",
    "pre_",
    "volume_2x_avg",
    "volume_5x_baseline",
    "volume_below_baseline",
    "basis_widening",
    "basis_narrowing",
    "basis_align",
    "basis_diverge",
    "oi_change_5m_pos",
    "oi_change_5m_neg",
    "oi_change_5m_significant",
    "oi_continues_rising",
    "oi_recovers_within",
    "oi_pct_top_decile",
    "funding_pct_top_decile",
    "volume_pct_top_decile",
    "regime_",
    "alt_season",
    "eth_dominance_",
    "btc_dominance_",
    "ema_",
    "rsi_",
    "atr_",
    "book_imbalance_",
    "aggressive_buy_",
    "aggressive_sell_",
    "iceberg",
    "aggregator_",
    "spread_bps",
    "depth_rank",
    "sector",
    "symbol_blacklist",
    "symbol_rotation",
    "geographic_",
    "diversification",
    "balance_LS",
    "force_rotation",
    "alternate_LS",
    "skip_recent_",
    "no_repeat_",
    "diversify_",
    "skip_",
    "weight_",
    "decay_",
    "half_life_",
    "linear_to_zero",
    "step_decay",
    "exp_decay",
    "no_decay",
    "immediate_decay",
    "recency_",
    "applicable",
    # Cross-channel chain expressions — handled at orchestration layer, not events filter
    "pc_then_oi_",
    "oi_then_pc_",
    "pc_or_oi_",
    "all_three_",
    "r6_after_",
    "r6_then_",
    "pc_oi_",
    "pc_pump_",
    "pc_crash_",
    "pc_burst_",
    "oi_burst_",
    "no_opposite_",
    "no_recent_",
    "no_extreme_",
    "no_pretrend_",
    "btc_alignment_",
    "btc_align_",
    "confirm_within_",
    "three_channel_",
    "multi_signal_",
    "combined_weighted",
    "max_open_",
]


CONDITION_RE = re.compile(r"^(\w+(?:_\w+)*)\s*([<>=!]=?|==)\s*(.+)$")

# ---------------------------------------------------------------------------
# Percentile-threshold "flag" conditions: bare tokens like
# `top_trader_position_ratio_high` translate to (col > p75 of channel) etc.
# These need access to the cached events DataFrame to compute the threshold
# at runtime (per channel, not global).
# Format: { flag_name : (parquet_column, percentile_op) }
# percentile_op: "GT_P75" | "GT_P90" | "LT_P25" | "LT_P10" | "GT_P50" | etc.
# ---------------------------------------------------------------------------

FLAG_FIELDS = {
    # Smart-money / crowd ratios
    "top_trader_position_ratio_high":   ("top_trader_long_short_position_ratio__longShortRatio", "GT_P75"),
    "top_trader_position_ratio_low":    ("top_trader_long_short_position_ratio__longShortRatio", "LT_P25"),
    "top_trader_position_ratio_dec":    ("top_trader_long_short_position_ratio__longShortRatio", "LT_P25"),
    "top_trader_account_ratio_high":    ("top_trader_long_short_account_ratio__longShortRatio", "GT_P75"),
    "top_trader_account_ratio_low":     ("top_trader_long_short_account_ratio__longShortRatio", "LT_P25"),
    "global_long_short_ratio_high":     ("global_long_short_account_ratio__longShortRatio", "GT_P75"),
    "global_long_ratio_high":           ("global_long_short_account_ratio__longAccount", "GT_P75"),
    "global_long_ratio_extreme":        ("global_long_short_account_ratio__longAccount", "GT_P90"),
    "global_short_ratio_high":          ("global_long_short_account_ratio__shortAccount", "GT_P75"),
    "global_short_ratio_extreme":       ("global_long_short_account_ratio__shortAccount", "GT_P90"),
    # Volume / funding deciles
    "volume_pct_top_decile":            ("quote_volume_24h", "GT_P90"),
    "volume_pct_above_p75":             ("quote_volume_24h", "GT_P75"),
    "volume_pct_below_p25":             ("quote_volume_24h", "LT_P25"),
    "funding_pct_top_decile":           ("funding_rate", "GT_P90"),
    "oi_pct_top_decile":                ("oi_change_pct", "GT_P90"),
    # Funding magnitude
    "funding_abs_high":                 ("funding_rate", "ABS_GT_P75"),
    "funding_abs_extreme":              ("funding_rate", "ABS_GT_P90"),
    # Premium magnitude
    "premium_extreme":                  ("mark_minus_index_proxy_pct", "ABS_GT_P90"),
}

# Conditions that indicate "no specific filter, just fire normally" — pass-through.
PASSTHROUGH_TOKENS = {
    "first_only", "first_two_only", "no_burst_quiet",
    "premium_bps_in_-5_5", "btc_24h_pct in [-1,1]",  # range conditions we don't parse yet
}


def apply_flag_field(flag: str, events_df) -> Optional["pl.Expr"]:
    """Translate a flag token (e.g. 'top_trader_position_ratio_high') to a polars
    expression by computing the relevant percentile threshold on events_df."""
    if events_df is None or flag not in FLAG_FIELDS:
        return None
    col_name, op = FLAG_FIELDS[flag]
    if col_name not in events_df.columns:
        return None
    col_expr = pl.col(col_name)
    series = events_df[col_name].drop_nulls()
    if series.len() == 0:
        return None
    if op.startswith("ABS_"):
        abs_op = op[4:]  # GT_P75 etc.
        thresh = series.abs().quantile({"GT_P75": 0.75, "GT_P90": 0.90, "LT_P25": 0.25, "LT_P10": 0.10}[abs_op])
        if thresh is None:
            return None
        if abs_op.startswith("GT"):
            return col_expr.abs() >= thresh
        return col_expr.abs() <= thresh
    quantile_map = {"GT_P75": 0.75, "GT_P90": 0.90, "GT_P50": 0.50, "LT_P25": 0.25, "LT_P10": 0.10}
    if op not in quantile_map:
        return None
    thresh = series.quantile(quantile_map[op])
    if thresh is None:
        return None
    if op.startswith("GT"):
        return col_expr >= thresh
    return col_expr <= thresh


def _try_numeric(value: str) -> Optional[float]:
    s = value.strip()
    # Strip common suffixes
    for suf in ("pct", "%", "bps"):
        if s.endswith(suf):
            s = s[: -len(suf)].strip()
            break
    try:
        return float(s)
    except ValueError:
        return None


def parse_one_condition(cond: str, events_df=None) -> Optional["pl.Expr"]:
    """Parse a single novel_dim string into a polars filter expression.

    Args:
        cond: the condition string (e.g. "oi_change_pct>=15", "session=US",
              "top_trader_position_ratio_high")
        events_df: optional cached events DataFrame; needed to compute
              percentile thresholds for flag-style conditions.

    Returns None if:
      - It's a parameter (not a filter), or
      - Field is unmapped, or
      - Syntax is unrecognized.
    """
    if not HAS_POLARS:
        return None

    cond = cond.strip()
    if not cond:
        return None

    # Skip parameters
    for p in PARAM_PREFIXES:
        if cond.startswith(p):
            return None

    # Pass-through tokens (no filter, ride channel/side baseline)
    if cond in PASSTHROUGH_TOKENS:
        return None

    # Bare flag (no operator) — try percentile-threshold mapping
    if cond in FLAG_FIELDS:
        return apply_flag_field(cond, events_df)

    # Skip not-yet-supported PREFIXES (need pre-processing we don't have)
    for p in NOT_YET_SUPPORTED_PREFIXES:
        if cond.startswith(p):
            return None

    # Try the regex parse
    m = CONDITION_RE.match(cond)
    if not m:
        return None

    field, op, value = m.group(1), m.group(2), m.group(3).strip()

    # Determine column + scale
    if field in PCT_TO_BPS_FIELDS:
        col_expr = pl.col("mark_minus_index_proxy_pct") * 100  # convert pct -> bps
    else:
        col_name = DIRECT_FIELD_MAP.get(field)
        if col_name is None:
            return None  # unknown field
        col_expr = pl.col(col_name)

    # Numeric value
    val_f = _try_numeric(value)
    if val_f is not None:
        if op in (">=",):
            return col_expr >= val_f
        if op in ("<=",):
            return col_expr <= val_f
        if op in (">",):
            return col_expr > val_f
        if op in ("<",):
            return col_expr < val_f
        if op in ("=", "=="):
            return col_expr == val_f
        if op in ("!=",):
            return col_expr != val_f
        return None

    # Categorical (string) comparison
    # R5 fix #2: apply value alias if defined (e.g. marketcap_bucket=small → ["<50m"])
    if field in CATEGORICAL_VALUE_ALIAS:
        alias_map = CATEGORICAL_VALUE_ALIAS[field]
        if value in alias_map:
            actual_values = alias_map[value]
            if op in ("=", "=="):
                if len(actual_values) == 1:
                    return col_expr == actual_values[0]
                return col_expr.is_in(actual_values)
            if op in ("!=",):
                if len(actual_values) == 1:
                    return col_expr != actual_values[0]
                return ~col_expr.is_in(actual_values)
            return None
    # Direct string comparison (no alias)
    if op in ("=", "=="):
        return col_expr == value
    if op in ("!=",):
        return col_expr != value
    return None


def build_filter_expr(
    novel_dim: list[str], events_df=None,
) -> tuple[Optional["pl.Expr"], list[str], list[str]]:
    """Combine novel_dim conditions into a single AND polars filter expression.

    Args:
        novel_dim: list of condition strings.
        events_df: optional cached events DataFrame for percentile lookups
                   (used by flag-style conditions like *_high / *_extreme).
    """
    if not HAS_POLARS:
        return None, [], list(novel_dim)

    applied, skipped, exprs = [], [], []
    for cond in novel_dim:
        e = parse_one_condition(cond, events_df=events_df)
        if e is None:
            skipped.append(cond)
        else:
            exprs.append(e)
            applied.append(cond)

    if not exprs:
        return None, applied, skipped

    combined = exprs[0]
    for e in exprs[1:]:
        combined = combined & e
    return combined, applied, skipped


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _self_test() -> int:
    if not HAS_POLARS:
        print("SKIP: polars not available")
        return 0

    cases = [
        # (novel_dim, expected_applied_count, expected_skipped_count)
        (["oi_change_pct>=15"], 1, 0),
        (["oi_change_pct>=15", "funding>=0.05"], 2, 0),
        (["delay_seconds=0"], 0, 1),  # param
        (["pretrend_5m_pos"], 0, 1),  # not yet supported
        (["liquidity_bucket=high"], 1, 0),
        (["premium_bps>=20"], 1, 0),  # uses mark_minus_index_proxy_pct * 100
        (["oi_change_pct>=15", "delay_seconds=30", "session=US"], 1, 2),  # mixed
        (["taker_buy_ratio_5m>=0.6"], 1, 0),
        (["unknown_field>=42"], 0, 1),  # unknown
        (["event_type=pump"], 1, 0),  # categorical
        (["funding<=-0.1"], 1, 0),  # negative numeric
    ]

    failures = []
    for novel_dim, exp_applied, exp_skipped in cases:
        expr, applied, skipped = build_filter_expr(novel_dim)
        ok = (len(applied) == exp_applied) and (len(skipped) == exp_skipped)
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] novel_dim={novel_dim}")
        print(f"          applied={applied}  skipped={skipped}  expr={expr}")
        if not ok:
            failures.append((novel_dim, exp_applied, exp_skipped, len(applied), len(skipped)))

    if failures:
        print(f"\nFAILURES ({len(failures)}):")
        for f in failures:
            print(f"  {f}")
        return 1

    print("\nALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test())
