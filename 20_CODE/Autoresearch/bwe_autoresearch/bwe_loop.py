"""Day 2.1: Karpathy-faithful NEVER STOP loop wrapper.

The orchestrator. Each iteration:
  1. Pick next archetype combo (entry × exit) from hypothesis_registry.jsonl
  2. Expand variant grid (TP × SL × hold)
  3. Load event K-line windows
  4. Run GPU batch eval -> per-(event, variant) net returns
  5. Take best variant (highest oos_p25_net_pct_after_cost)
  6. Append to results.tsv via ResultsLogger
  7. If keep: git auto-commit; if discard: git auto-reset
  8. Repeat

Controls:
  --target-evals N       Stop after N total evaluations (default: 1e9)
  --max-experiments N    Stop after N experiments (no default)
  --max-runtime-hours H  Stop after H hours (no default)
  --combo-cursor PATH    JSON file tracking which combo to try next
  --device cuda|cpu      Force device (default: auto)

Signal handling:
  SIGINT / SIGTERM       Finish current experiment, then exit cleanly

For smoke testing without real data, pass --synthetic.

Usage:
    python -m bwe_autoresearch.bwe_loop --max-experiments 1
    python -m bwe_autoresearch.bwe_loop --target-evals 1e9 --max-runtime-hours 28
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

import numpy as np

from bwe_autoresearch.bwe_loop_gpu_eval import (
    EventBatch,
    VariantGrid,
    batch_eval,
    get_device,
    HAS_TORCH,
)
from bwe_autoresearch.bwe_loop_results import ResultsLogger
from bwe_autoresearch.bwe_loop_score_metric import batch_score_oos_p25_pct, score_with_report
from bwe_autoresearch.bwe_loop_exit_kernels import (
    classify_exit_family,
    eval_breakeven,
    eval_multi_tp_50_50,
    eval_time_only,
    eval_trailing_pct,
)

import functools

from bwe_autoresearch.bwe_paths import (  # noqa: E402
    REGISTRY_JSONL as REGISTRY_PATH,
    COMBO_CURSOR as COMBO_CURSOR_PATH,
    KLINE_PARQUET, EVENTS_PARQUET,
)

# Cost in PERCENT (round-trip 8 bps = 0.08%)
DEFAULT_COST_PCT = 0.08

# Per-experiment time budget (Karpathy: 5min training; we allow 10min for backtests)
DEFAULT_EXPERIMENT_BUDGET_S = 600

# Variant grid defaults — Round 4 妖币 regime (2026-04-28 7d-extended)
# R3 used linspace(0.2, 6.0, 150) → fee trap. R4 widens TP/SL/hold per 妖币 thesis.
# Hold range now extends to 168h (7d) when BWE_HOLD_MAX_MIN env var enables long
# range AND 7d event_windows parquet is loaded (BWE_KLINE_PARQUET_FILE=trade_kline_1m_event_windows_7d.parquet).
# The kernel transparently clamps to T-1 if data forward window is shorter than max hold.
# R5 fix #1: TP lower bound configurable via env. Default 0.5% for backward compat,
# but R5 妖币 mode should use 5.0% (BWE_TP_LOWER=5.0) to skip fee-trap region.
# R4 整夜 found best_tp dist dominated by 0.50 (121,756×) — lower bound 5%
# eliminates this grid-edge artifact.
_TP_LOWER = float(os.environ.get("BWE_TP_LOWER", "0.5"))
_TP_UPPER = float(os.environ.get("BWE_TP_UPPER", "500.0"))
_TP_N = int(os.environ.get("BWE_TP_N", "60"))
DEFAULT_TP_GRID = np.geomspace(_TP_LOWER, _TP_UPPER, _TP_N, dtype=np.float32)
DEFAULT_SL_GRID = np.array([3.0, 5.0, 7.0, 10.0], dtype=np.float32)

_HOLD_RANGE = os.environ.get("BWE_HOLD_RANGE", "5h")
if _HOLD_RANGE == "7d":
    # Full 妖币 long-hold grid (requires 7d event_windows parquet)
    DEFAULT_HOLD_MINUTES = [30, 60, 120, 300, 720, 1440, 2160, 2880, 4320, 10080]
    # 30m, 1h, 2h, 5h, 12h, 24h, 36h, 48h, 72h, 168h
elif _HOLD_RANGE == "3d":
    DEFAULT_HOLD_MINUTES = [30, 60, 120, 300, 720, 1440, 2880, 4320]
    # 30m, 1h, 2h, 5h, 12h, 24h, 48h, 72h
else:
    # Default 5h (event_windows.parquet physical max — works without 7d rebuild)
    DEFAULT_HOLD_MINUTES = [30, 60, 120, 180, 240, 300]


# ---------------------------------------------------------------------------
# Combo selection
# ---------------------------------------------------------------------------

@dataclass
class Combo:
    """A (entry, exit) pair from the registry."""
    entry_id: str
    exit_id: str
    entry_archetype: str
    exit_archetype: str
    channel: str
    side: str
    novel_dim: tuple = ()  # entry archetype's novel_dim conditions (tuple for hashability)

    def description(self) -> str:
        return f"E={self.entry_id}/{self.entry_archetype} X={self.exit_id}/{self.exit_archetype}"


def load_registry(path: Path = REGISTRY_PATH) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _id_num(r: dict) -> int:
    """Extract numeric part of an archetype id like E300 / X42 / C062."""
    try:
        return int(r["id"][1:])
    except (KeyError, ValueError, IndexError):
        return 0


def _is_r4(r: dict) -> bool:
    """R4 archetype: id numeric part >= 300 (E300+, X300+, etc.)."""
    return _id_num(r) >= 300


def iter_combos(
    registry: list[dict], cursor: int = 0, order: str = "entry_first"
) -> Iterator[tuple[int, Combo]]:
    """Yield (cursor_index, Combo) starting from `cursor`.

    order:
      - "entry_first" (R3 default): cycle ALL entries with X001 before X002.
        Cursor 0..N_entries-1 covers all entries with one exit each.
        Best for first-pass entry diversity sweeping.
      - "exit_first": cycle ALL exits for E001 before moving to E002.
        Cursor 0..N_exits-1 covers all exits for one entry.
        Use after a winner entry is found, to scan exit space.
      - "smart_priority" (R4 default): R4 archetypes (id >= 300) cycle first
        in BOTH entries and exits, then R3 archetypes after. Within each
        priority tier, uses exit_first ordering so R4×R4 covers the full
        cartesian R4 entries × R4 exits in the very first
        (n_R4_entries × n_R4_exits) cursors. Designed to surface R4 winners
        before sinking time into the long R3 × R3 tail.
    """
    entries = [r for r in registry if r["type"] == "entry"]
    exits = [r for r in registry if r["type"] == "exit"]

    if order == "smart_priority":
        # Sort: R4 first (id >= 300), then R3 (id < 300); each tier sorted by id.
        # With exit_first iteration on the resorted lists, the first
        # n_R4_e × n_R4_x cursors cover R4 × R4 fully.
        entries = sorted(entries, key=lambda r: (not _is_r4(r), _id_num(r)))
        exits = sorted(exits, key=lambda r: (not _is_r4(r), _id_num(r)))
        order = "exit_first"

    n_e = len(entries)
    n_x = len(exits)
    n = n_e * n_x
    idx = cursor
    while idx < n:
        if order == "entry_first":
            # rotation: each entry once with x_i=0, then second pass with x_i=1, ...
            x_i = idx // n_e
            e_i = idx % n_e
        else:  # exit_first (legacy + smart_priority underlying)
            e_i = idx // n_x
            x_i = idx % n_x
        e = entries[e_i]
        x = exits[x_i]
        yield idx, Combo(
            entry_id=e["id"], exit_id=x["id"],
            entry_archetype=e["archetype"], exit_archetype=x["archetype"],
            channel=e["channel"], side=e["side"],
            novel_dim=tuple(e.get("novel_dim", [])),
        )
        idx += 1


def read_cursor() -> int:
    if COMBO_CURSOR_PATH.exists():
        try:
            return int(json.loads(COMBO_CURSOR_PATH.read_text())["cursor"])
        except (KeyError, ValueError):
            return 0
    return 0


def write_cursor(idx: int) -> None:
    COMBO_CURSOR_PATH.parent.mkdir(parents=True, exist_ok=True)
    COMBO_CURSOR_PATH.write_text(json.dumps({"cursor": idx}, indent=2))


# ---------------------------------------------------------------------------
# Variant grid expansion
# ---------------------------------------------------------------------------

def expand_variant_grid(
    tp_grid: np.ndarray = DEFAULT_TP_GRID,
    sl_grid: np.ndarray = DEFAULT_SL_GRID,
    hold_minutes_list: list[int] = DEFAULT_HOLD_MINUTES,
) -> VariantGrid:
    """Cartesian product of TP × SL × hold."""
    tps_mesh, sls_mesh, holds_mesh = np.meshgrid(
        tp_grid, sl_grid, np.array(hold_minutes_list, dtype=np.int16),
        indexing="ij",
    )
    tps = tps_mesh.ravel().astype(np.float32)
    sls = sls_mesh.ravel().astype(np.float32)
    holds = holds_mesh.ravel().astype(np.int16)
    return VariantGrid.from_numpy(tps, sls, holds)


# ---------------------------------------------------------------------------
# Event loading
# ---------------------------------------------------------------------------

# Registry channel slug -> actual parquet channel label.
# Verified in H:/BWE/30_DATA/cache/normalized/trade_kline_1m_event_windows.parquet
# unique channels: BWE_OI_Price_monitor, BWE_pricechange_monitor, BWE_Reserved6
CHANNEL_LABEL_MAP = {
    "OI_Price":   "BWE_OI_Price_monitor",
    "pricechange": "BWE_pricechange_monitor",
    "Reserved6":  "BWE_Reserved6",
}


@functools.lru_cache(maxsize=8)
def _load_channel_klines_cached(
    channel: str, kline_parquet_str: str, forward_minutes: int, max_events: int,
):
    """Cache (event_ids, OHLC arrays) per (channel, parquet, forward_minutes, max_events)."""
    import polars as pl

    kline_parquet = Path(kline_parquet_str)
    if not kline_parquet.exists():
        return None

    pf = pl.scan_parquet(kline_parquet).filter(
        (pl.col("minute_offset") >= 0) & (pl.col("minute_offset") < forward_minutes)
    )
    if channel not in ("*", "NA"):
        actual_label = CHANNEL_LABEL_MAP.get(channel, channel)
        pf = pf.filter(pl.col("channel") == actual_label)
    df = pf.select([
        "event_id", "api_symbol", "event_ts_ms", "minute_offset",
        "trade_open", "trade_high", "trade_low", "trade_close",
        "trade_kline_available",
    ]).collect()
    if df.is_empty():
        return None
    df = df.filter(pl.col("trade_kline_available") == True)
    if df.is_empty():
        return None
    grouped = df.group_by("event_id").agg([
        pl.col("api_symbol").first(),
        pl.col("event_ts_ms").first(),
        pl.col("minute_offset"),
        pl.col("trade_open"),
        pl.col("trade_high"),
        pl.col("trade_low"),
        pl.col("trade_close"),
    ])
    grouped = grouped.filter(
        pl.col("minute_offset").list.len() == forward_minutes
    ).head(max_events)
    if grouped.is_empty():
        return None
    api_symbols = grouped["api_symbol"].to_list()
    event_ts_mss = grouped["event_ts_ms"].to_list()
    highs = np.array(grouped["trade_high"].to_list(), dtype=np.float32)
    lows = np.array(grouped["trade_low"].to_list(), dtype=np.float32)
    closes = np.array(grouped["trade_close"].to_list(), dtype=np.float32)
    opens = np.array(grouped["trade_open"].to_list(), dtype=np.float32)
    entry_prices = opens[:, 0].copy()
    return api_symbols, event_ts_mss, entry_prices, highs, lows, closes


@functools.lru_cache(maxsize=8)
def _load_channel_events_features_cached(
    channel: str, events_parquet_str: str, max_events: int,
):
    """Cache events feature table per channel + add derived columns
    (hour_utc, weekday, session) for filter use."""
    import polars as pl

    events_parquet = Path(events_parquet_str)
    if not events_parquet.exists():
        return None
    pf = pl.scan_parquet(events_parquet)
    if channel not in ("*", "NA"):
        actual_label = CHANNEL_LABEL_MAP.get(channel, channel)
        pf = pf.filter(pl.col("channel") == actual_label)
    df = pf.collect().head(max_events)
    if df.is_empty():
        return None

    # Derived columns from event timestamp (ts_ms = unix ms)
    # hour_utc: 0-23
    # weekday: Mon..Sun strings (epoch ms 0 was Thu, so offset +4 for ISO Mon=0)
    weekday_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    df = df.with_columns([
        ((pl.col("ts_ms") // 3_600_000) % 24).cast(pl.Int32).alias("hour_utc"),
        (((pl.col("ts_ms") // 86_400_000) + 3) % 7).cast(pl.Int32).alias("_weekday_idx"),
    ])
    df = df.with_columns([
        pl.col("_weekday_idx").map_elements(lambda i: weekday_names[i], return_dtype=pl.Utf8).alias("weekday"),
        pl.when((pl.col("hour_utc") >= 13) & (pl.col("hour_utc") < 21)).then(pl.lit("US"))
          .when((pl.col("hour_utc") >= 0) & (pl.col("hour_utc") < 8)).then(pl.lit("Asian"))
          .when((pl.col("hour_utc") >= 7) & (pl.col("hour_utc") < 15)).then(pl.lit("European"))
          .otherwise(pl.lit("Other")).alias("session"),
    ])
    return df


# Minimum trigger count after filter. Below this, the experiment skips with NaN.
MIN_FILTERED_EVENTS = 30


def load_events_for_combo(
    combo: Combo,
    kline_parquet: Path = KLINE_PARQUET,
    events_parquet: Path = EVENTS_PARQUET,
    forward_minutes: int = 15,
    max_events: int = 5000,
) -> EventBatch | None:
    """Load events matching combo's channel + side + novel_dim filter.

    Flow:
      1. Cached channel klines (event_ids + OHLC).
      2. Cached channel events features (for filter).
      3. Build filter expression from combo.novel_dim.
      4. If filter applies, intersect the kline event_ids with the
         filter-passing event_ids and subset OHLC arrays.
      5. Return EventBatch or None if too few events remain.
    """
    cached_klines = _load_channel_klines_cached(
        combo.channel, str(kline_parquet), forward_minutes, max_events,
    )
    if cached_klines is None:
        return None
    api_symbols_kline, event_ts_mss_kline, entry_prices, highs, lows, closes = cached_klines

    # Apply novel_dim filter if available
    n_applied = 0
    if combo.novel_dim:
        from bwe_autoresearch.bwe_loop_entry_filter import build_filter_expr
        events_df = _load_channel_events_features_cached(
            combo.channel, str(events_parquet), max_events,
        )
        if events_df is not None:
            expr, applied, _skipped = build_filter_expr(list(combo.novel_dim), events_df=events_df)
            n_applied = len(applied)
            if expr is not None:
                filtered = events_df.filter(expr)
                if filtered.is_empty():
                    return None
                # Match klines via (api_symbol, ts_ms) tuple — events parquet
                # column is `ts_ms`, kline's per-event timestamp is `event_ts_ms`.
                allowed_keys = set(zip(
                    filtered["api_symbol"].to_list(),
                    filtered["ts_ms"].to_list(),
                ))
                mask = np.array(
                    [(s, t) in allowed_keys for s, t in zip(api_symbols_kline, event_ts_mss_kline)],
                    dtype=bool,
                )
                if mask.sum() < MIN_FILTERED_EVENTS:
                    return None
                entry_prices = entry_prices[mask]
                highs = highs[mask]
                lows = lows[mask]
                closes = closes[mask]

    n_events = len(entry_prices)
    if n_events < MIN_FILTERED_EVENTS:
        return None

    side_val = -1 if combo.side == "short" else 1
    sides = np.full(n_events, side_val, dtype=np.int8)
    batch = EventBatch.from_numpy(entry_prices, sides, highs, lows, closes)
    # Stash diagnostics on the batch for the loop's logging
    batch._n_applied_filters = n_applied  # type: ignore[attr-defined]
    return batch


def synthetic_events(n_events: int = 500, forward_minutes: int = 15, seed: int = 0) -> EventBatch:
    """Produce synthetic EventBatch for smoke tests when real data unavailable."""
    rng = np.random.default_rng(seed)
    entry = rng.uniform(50, 200, size=n_events).astype(np.float32)
    sides = rng.choice([-1, 1], size=n_events).astype(np.int8)
    drift = rng.normal(0, 0.005, size=(n_events, forward_minutes)).cumsum(axis=1)
    mid = entry[:, None] * (1 + drift)
    range_pct = rng.uniform(0.001, 0.005, size=(n_events, forward_minutes))
    highs = (mid * (1 + range_pct)).astype(np.float32)
    lows = (mid * (1 - range_pct)).astype(np.float32)
    closes = mid.astype(np.float32)
    return EventBatch.from_numpy(entry, sides, highs, lows, closes)


# ---------------------------------------------------------------------------
# Single experiment
# ---------------------------------------------------------------------------

@dataclass
class ExperimentResult:
    combo: Combo
    score: float
    n_triggers: int
    n_variants: int
    best_variant_tp: float
    best_variant_sl: float
    elapsed_s: float
    n_evals: int
    error: Optional[str] = None


def run_one_experiment(
    combo: Combo,
    variants: VariantGrid,
    events: EventBatch | None,
    cost_pct: float,
    device: str,
    use_synthetic: bool = False,
) -> ExperimentResult:
    t0 = time.time()
    if events is None:
        if use_synthetic:
            events = synthetic_events(n_events=500)
        else:
            return ExperimentResult(
                combo=combo, score=float("nan"), n_triggers=0,
                n_variants=variants.n_variants,
                best_variant_tp=float("nan"), best_variant_sl=float("nan"),
                elapsed_s=time.time() - t0, n_evals=0,
                error="no_events_for_channel",
            )

    n_evals = events.n_events * variants.n_variants
    # Dispatch to exit-family-specific kernel
    exit_family = classify_exit_family(combo.exit_archetype)
    try:
        if exit_family == "time_only":
            events_gpu = events.to(device)
            variants_gpu = variants.to(device)
            net_returns = eval_time_only(events_gpu, variants_gpu, cost_pct=cost_pct, variant_chunk=8192)
        elif exit_family == "breakeven":
            events_gpu = events.to(device)
            variants_gpu = variants.to(device)
            net_returns = eval_breakeven(events_gpu, variants_gpu, cost_pct=cost_pct, variant_chunk=8192)
        elif exit_family == "trail":
            events_gpu = events.to(device)
            variants_gpu = variants.to(device)
            net_returns = eval_trailing_pct(events_gpu, variants_gpu, cost_pct=cost_pct, variant_chunk=8192)
        elif exit_family == "multi_tp":
            events_gpu = events.to(device)
            variants_gpu = variants.to(device)
            net_returns = eval_multi_tp_50_50(events_gpu, variants_gpu, cost_pct=cost_pct, variant_chunk=8192)
        else:  # "fixed" — first-touch TP/SL
            net_returns = batch_eval(
                events, variants, cost_pct=cost_pct, device=device, variant_chunk=8192,
            )
    except Exception as e:
        return ExperimentResult(
            combo=combo, score=float("nan"), n_triggers=events.n_events,
            n_variants=variants.n_variants,
            best_variant_tp=float("nan"), best_variant_sl=float("nan"),
            elapsed_s=time.time() - t0, n_evals=0,
            error=f"batch_eval_exception[{exit_family}]: {type(e).__name__}: {e}",
        )

    # GPU-vectorized score: replaces 90K-iteration Python loop
    try:
        scores_t = batch_score_oos_p25_pct(net_returns)
        scores = scores_t.cpu().numpy().astype(np.float64)
    except Exception as e:
        return ExperimentResult(
            combo=combo, score=float("nan"), n_triggers=events.n_events,
            n_variants=variants.n_variants,
            best_variant_tp=float("nan"), best_variant_sl=float("nan"),
            elapsed_s=time.time() - t0, n_evals=n_evals,
            error=f"batch_score_exception: {type(e).__name__}: {e}",
        )

    valid_mask = ~np.isnan(scores)
    if not valid_mask.any():
        return ExperimentResult(
            combo=combo, score=float("nan"), n_triggers=events.n_events,
            n_variants=variants.n_variants,
            best_variant_tp=float("nan"), best_variant_sl=float("nan"),
            elapsed_s=time.time() - t0, n_evals=n_evals,
            error="all_variants_nan",
        )
    masked_scores = np.where(valid_mask, scores, -np.inf)
    best_v = int(np.argmax(masked_scores))
    best_score = float(scores[best_v])
    best_tp = float(variants.tp_pct[best_v].cpu())
    best_sl = float(variants.sl_pct[best_v].cpu())

    return ExperimentResult(
        combo=combo, score=best_score, n_triggers=events.n_events,
        n_variants=variants.n_variants,
        best_variant_tp=best_tp, best_variant_sl=best_sl,
        elapsed_s=time.time() - t0, n_evals=n_evals,
    )


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

class StopRequested(Exception):
    pass


def install_signal_handlers() -> None:
    def handler(signum, frame):
        print(f"\n[bwe_loop] received signal {signum}, finishing current experiment...")
        raise StopRequested()
    signal.signal(signal.SIGINT, handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, handler)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-evals", type=float, default=1e11,
                    help="Stop after N total evaluations (default 100B = ~10h on 5090 with optimized loop).")
    ap.add_argument("--max-experiments", type=int, default=None)
    ap.add_argument("--max-runtime-hours", type=float, default=None)
    ap.add_argument("--cost-pct", type=float, default=DEFAULT_COST_PCT)
    ap.add_argument("--device", type=str, default=None, choices=["cuda", "cpu", None])
    ap.add_argument("--registry", type=str, default=str(REGISTRY_PATH))
    ap.add_argument("--synthetic", action="store_true",
                    help="Use synthetic events (smoke testing without real data).")
    ap.add_argument("--no-git", action="store_true",
                    help="Skip git commit/reset (for fast smoke tests).")
    ap.add_argument("--order", type=str, default="smart_priority",
                    choices=["entry_first", "exit_first", "smart_priority"],
                    help="Combo iteration order. smart_priority (R4 default) puts R4 archetypes (id>=300) "
                         "first in both entries and exits, exit_first within tiers — first ~800 cursors "
                         "cover the full R4 entries × R4 exits cartesian. entry_first is R3 default.")
    ap.add_argument("--reset-cursor", action="store_true",
                    help="Start from cursor 0 regardless of saved state.")
    args = ap.parse_args()

    if not HAS_TORCH:
        print("FATAL: PyTorch not available", file=sys.stderr)
        return 2

    device = args.device or get_device()
    print(f"[bwe_loop] starting; device={device}, target_evals={args.target_evals:.2e}")

    registry = load_registry(Path(args.registry))
    print(f"[bwe_loop] loaded {len(registry)} archetypes")

    variants = expand_variant_grid()
    print(f"[bwe_loop] variant grid: {variants.n_variants:,} variants per experiment")

    log = ResultsLogger()
    cursor = 0 if args.reset_cursor else read_cursor()
    print(f"[bwe_loop] starting at combo cursor {cursor} order={args.order}")

    install_signal_handlers()
    t_start = time.time()
    total_evals = 0
    n_exp = 0

    try:
        for idx, combo in iter_combos(registry, cursor, order=args.order):
            # Stop conditions
            if total_evals >= args.target_evals:
                print(f"[bwe_loop] reached target evals {args.target_evals:.2e}")
                break
            if args.max_experiments and n_exp >= args.max_experiments:
                print(f"[bwe_loop] reached max experiments {args.max_experiments}")
                break
            if args.max_runtime_hours and (time.time() - t_start) / 3600 >= args.max_runtime_hours:
                print(f"[bwe_loop] reached max runtime {args.max_runtime_hours}h")
                break

            print(f"\n[exp {n_exp+1}] cursor={idx} {combo.description()}")
            events = (
                synthetic_events()
                if args.synthetic
                else load_events_for_combo(combo)
            )
            n_events = 0 if events is None else events.n_events
            print(f"  events: {n_events}")

            result = run_one_experiment(
                combo, variants, events, cost_pct=args.cost_pct, device=device,
                use_synthetic=args.synthetic,
            )
            total_evals += result.n_evals
            n_exp += 1

            if result.error:
                print(f"  ERROR: {result.error}")
                desc = f"{combo.description()} | error={result.error}"
                decision = log.append(score=float("nan"), triggers=result.n_triggers,
                                      description=desc)
            else:
                desc = (f"{combo.description()} | n_var={result.n_variants} "
                        f"best_tp={result.best_variant_tp:.2f} best_sl={result.best_variant_sl:.2f} "
                        f"elapsed={result.elapsed_s:.1f}s")
                print(f"  score={result.score:.4f}  best_tp={result.best_variant_tp:.2f} "
                      f"best_sl={result.best_variant_sl:.2f}  "
                      f"elapsed={result.elapsed_s:.1f}s ({result.n_evals/result.elapsed_s:,.0f} evals/s)")
                decision = log.append(
                    score=result.score, triggers=result.n_triggers, description=desc,
                )

            print(f"  decision: status={decision.status} action={decision.action} reason={decision.reason}")
            if not args.no_git:
                if decision.action == "commit":
                    log.git_commit(decision.commit_message)
                elif decision.action == "reset":
                    log.git_reset()

            write_cursor(idx + 1)

    except StopRequested:
        print("[bwe_loop] graceful stop requested")
    except Exception as e:
        print(f"[bwe_loop] FATAL: {type(e).__name__}: {e}")
        import traceback; traceback.print_exc()
        return 1

    sm = log.summary()
    print(f"\n[bwe_loop] done; experiments={n_exp} total_evals={total_evals:,} "
          f"elapsed={(time.time()-t_start)/60:.1f}min")
    print(f"[bwe_loop] summary: {sm}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
