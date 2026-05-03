"""Day 4: Exit family kernels — make exit archetypes actually different.

Bug fix: previously, all 100 exit archetypes routed to the SAME first-touch
TP/SL kernel. Result: E126 × X001 == E126 × X012 (identical scores). Made
the 100 exits effectively meaningless metadata.

This module implements 5 distinct exit logics. Each takes the same
(events, variants, cost_pct) inputs as the fixed kernel and returns the
same [N_events, N_variants] f32 net_returns tensor. The dispatcher in
bwe_loop.classify_exit_family() picks one kernel per archetype slug.

Kernels:
  1. fixed_tp_sl      — current first-touch (TP / SL / close-at-hold) [in gpu_eval.py]
  2. time_only        — exit at close[hold-1] regardless (no early TP/SL)
  3. breakeven_ratchet— TP1 hit → SL moves to BE → ride to close[hold]
                        but exit at 0 if low touches entry post-TP1
  4. trailing_stop_pct— SL trails by SL_pct from running high-water-mark
  5. multi_tp_50_50   — 50% off at TP/2, 50% at TP (or close at hold), full SL

Param re-use (variants are still (TP, SL, hold)):
  - fixed:    TP=target,        SL=stop,           hold=time-cap
  - time:     ignored,           ignored,           hold=time-cap
  - breakeven:TP=BE_trigger,    SL=initial_stop,   hold=time-cap
  - trail:    TP=initial_target,SL=trail_distance, hold=time-cap
  - multi_tp: TP=upper_target,  SL=stop,           hold=time-cap (TP1 = TP/2 implicit)

All kernels chunk by variant_chunk to bound VRAM (default 8192).
"""

from __future__ import annotations

from typing import Optional

import numpy as np

try:
    import torch
    HAS_TORCH = True
except ImportError:  # pragma: no cover
    torch = None  # type: ignore
    HAS_TORCH = False


SENTINEL_NO_HIT = 1_000_000


def _first_true_index(mask: "torch.Tensor", fill: int = SENTINEL_NO_HIT) -> "torch.Tensor":
    has_any = mask.any(dim=-1)
    first_idx = mask.float().argmax(dim=-1)
    return torch.where(has_any, first_idx, torch.full_like(first_idx, fill))


def _compute_pnl_tensors(events) -> tuple["torch.Tensor", "torch.Tensor", "torch.Tensor"]:
    """Compute fav_pct, adv_pct, close_pnl_pct: all [N_events, N_minutes]."""
    inv_entry = (100.0 / events.entry_prices).unsqueeze(1)  # [N_e, 1]
    side_long = (events.sides == 1).unsqueeze(1)            # [N_e, 1] bool

    long_fav = (events.highs - events.entry_prices.unsqueeze(1)) * inv_entry
    long_adv = (events.lows - events.entry_prices.unsqueeze(1)) * inv_entry
    short_fav = (events.entry_prices.unsqueeze(1) - events.lows) * inv_entry
    short_adv = (events.entry_prices.unsqueeze(1) - events.highs) * inv_entry

    fav_pct = torch.where(side_long, long_fav, short_fav)
    adv_pct = torch.where(side_long, long_adv, short_adv)
    close_pnl_pct = torch.where(
        side_long,
        (events.closes - events.entry_prices.unsqueeze(1)) * inv_entry,
        (events.entry_prices.unsqueeze(1) - events.closes) * inv_entry,
    )
    return fav_pct, adv_pct, close_pnl_pct


# ---------------------------------------------------------------------------
# Kernel 2: time_only
# ---------------------------------------------------------------------------

def eval_time_only(events, variants, cost_pct: float, variant_chunk: int = 8192) -> "torch.Tensor":
    """Exit at close[hold-1] regardless of any intermediate TP/SL hit.

    PnL = close_pnl_pct[hold_idx] - cost_pct.
    """
    n_e, T = events.highs.shape
    n_v = variants.n_variants
    device = events.entry_prices.device

    _, _, close_pnl_pct = _compute_pnl_tensors(events)

    out = torch.empty((n_e, n_v), device=device, dtype=torch.float32)
    for v_start in range(0, n_v, variant_chunk):
        v_end = min(v_start + variant_chunk, n_v)
        v_size = v_end - v_start
        hold = variants.hold_minutes[v_start:v_end].to(torch.int64).clamp_max(T - 1)
        hold_idx = hold.view(1, v_size).expand(n_e, v_size)
        close_at_hold = close_pnl_pct.gather(1, hold_idx)
        out[:, v_start:v_end] = (close_at_hold - cost_pct).float()
    return out


# ---------------------------------------------------------------------------
# Kernel 3: breakeven_ratchet
# ---------------------------------------------------------------------------

def eval_breakeven(events, variants, cost_pct: float, variant_chunk: int = 8192) -> "torch.Tensor":
    """TP triggers BE move (SL → entry); ride remaining to close[hold].
    Exit at 0 if low touches entry post-TP1; else close_at_hold.
    Pre-TP: standard SL exit.
    """
    n_e, T = events.highs.shape
    n_v = variants.n_variants
    device = events.entry_prices.device

    fav_pct, adv_pct, close_pnl_pct = _compute_pnl_tensors(events)
    # Suffix-min of adv_pct per event: min over [t, T-1] of adv_pct[e, .]
    # adv_suffix_min[e, t] = min(adv_pct[e, t:T])
    rev = torch.flip(adv_pct, dims=[1])
    rev_cummin = torch.cummin(rev, dim=1).values
    adv_suffix_min = torch.flip(rev_cummin, dims=[1])

    out = torch.empty((n_e, n_v), device=device, dtype=torch.float32)
    for v_start in range(0, n_v, variant_chunk):
        v_end = min(v_start + variant_chunk, n_v)
        v_size = v_end - v_start

        tp_v = variants.tp_pct[v_start:v_end].view(1, v_size, 1)
        sl_v = variants.sl_pct[v_start:v_end].view(1, v_size, 1)
        hold = variants.hold_minutes[v_start:v_end].to(torch.int64).clamp_max(T - 1)

        fav_eT = fav_pct.unsqueeze(1)
        adv_eT = adv_pct.unsqueeze(1)
        tp_hit = fav_eT >= tp_v       # [N_e, v_size, T]
        sl_hit = adv_eT <= -sl_v
        first_tp = _first_true_index(tp_hit)   # [N_e, v_size]
        first_sl = _first_true_index(sl_hit)
        hold_b = hold.view(1, v_size).expand(n_e, v_size)
        tp_first = (first_tp < first_sl) & (first_tp <= hold_b)
        sl_first = (first_sl <= first_tp) & (first_sl <= hold_b)

        # Close at hold
        hold_idx = hold_b.long()
        close_at_hold = close_pnl_pct.gather(1, hold_idx)

        # Did adv go ≤ 0 AFTER tp?  Look at suffix-min from tp_idx+1.
        next_idx = (first_tp + 1).clamp_max(T - 1).long()
        post_tp_min = adv_suffix_min.gather(1, next_idx)
        post_tp_violated = post_tp_min <= 0

        # Outcome:
        #   sl_first: -SL
        #   tp_first AND post_tp_violated: 0 (BE triggered)
        #   tp_first AND NOT violated: close_at_hold
        #   neither: close_at_hold
        gross_sl = -variants.sl_pct[v_start:v_end].view(1, v_size).expand(n_e, v_size)
        gross_be = torch.zeros((n_e, v_size), device=device)
        gross_close = close_at_hold

        gross = torch.where(
            sl_first, gross_sl,
            torch.where(
                tp_first,
                torch.where(post_tp_violated, gross_be, gross_close),
                gross_close,
            ),
        )
        out[:, v_start:v_end] = (gross - cost_pct).float()
    return out


# ---------------------------------------------------------------------------
# Kernel 4: trailing_stop_pct
# ---------------------------------------------------------------------------

def eval_trailing_pct(events, variants, cost_pct: float, variant_chunk: int = 8192) -> "torch.Tensor":
    """SL trails by SL_pct from running max of fav_pct.

    Logic:
      - At each minute t, hwm[t] = max(fav_pct[0..t])
      - trail_floor[v, t] = hwm[t] - sl_pct[v]
      - Exit when adv_pct[t] <= trail_floor[t]
      - Exit PnL = trail_floor at exit time (so if HWM was 2% and SL=0.5, exit at 1.5%)
      - If never trips trail and never goes positive (HWM<=0), behaves like fixed -SL stop
      - If hits hold without trip: exit at close_at_hold
    """
    n_e, T = events.highs.shape
    n_v = variants.n_variants
    device = events.entry_prices.device

    fav_pct, adv_pct, close_pnl_pct = _compute_pnl_tensors(events)
    hwm_pct = torch.cummax(fav_pct, dim=1).values  # [N_e, T]

    out = torch.empty((n_e, n_v), device=device, dtype=torch.float32)
    for v_start in range(0, n_v, variant_chunk):
        v_end = min(v_start + variant_chunk, n_v)
        v_size = v_end - v_start

        sl_v = variants.sl_pct[v_start:v_end].view(1, v_size, 1)
        hold = variants.hold_minutes[v_start:v_end].to(torch.int64).clamp_max(T - 1)

        # trail_floor[e, v, t] = hwm[e, t] - sl[v]
        trail_floor = hwm_pct.unsqueeze(1) - sl_v  # [N_e, v_size, T]
        # Exit when adv_pct <= trail_floor (note: at t=0 hwm=fav[0], so trail_floor=fav[0]-sl;
        # adv[0]=adv[0]; if adv[0]<=fav[0]-sl → adv[0]+sl<=fav[0]; for tight fav-adv this can fire on bar 0)
        adv_eT = adv_pct.unsqueeze(1)
        trail_hit = adv_eT <= trail_floor    # [N_e, v_size, T]

        # Mask out t > hold (don't exit beyond hold)
        t_idx = torch.arange(T, device=device).view(1, 1, T)
        hold_b = hold.view(1, v_size, 1)
        in_window = t_idx <= hold_b
        trail_hit = trail_hit & in_window

        first_exit = _first_true_index(trail_hit)  # [N_e, v_size]
        any_exit = first_exit < SENTINEL_NO_HIT

        # Exit PnL at trail_floor of exit minute (gather along T)
        first_exit_safe = first_exit.clamp_max(T - 1).long()
        exit_pnl_trail = trail_floor.gather(2, first_exit_safe.unsqueeze(-1)).squeeze(-1)

        # Close at hold (for non-exit case)
        hold_idx_2d = hold.view(1, v_size).expand(n_e, v_size).long()
        close_at_hold = close_pnl_pct.gather(1, hold_idx_2d)

        gross = torch.where(any_exit, exit_pnl_trail, close_at_hold)
        out[:, v_start:v_end] = (gross - cost_pct).float()
    return out


# ---------------------------------------------------------------------------
# Kernel 5: multi_tp_50_50
# ---------------------------------------------------------------------------

def eval_multi_tp_50_50(events, variants, cost_pct: float, variant_chunk: int = 8192) -> "torch.Tensor":
    """50% closed at TP1=TP/2, 50% at TP2=TP (or close at hold), full SL stop.

    Rules:
      - If SL hits before TP1 (within hold): full -SL
      - If TP1 hits first: 50% locked at +TP1.
        Then 50% runner: rides until TP2 (full +TP) or SL or close-at-hold.
        Cost subtracted twice (each leg incurs cost) for realism.
      - If neither TP1 nor SL hits within hold: 100% at close_at_hold
    """
    n_e, T = events.highs.shape
    n_v = variants.n_variants
    device = events.entry_prices.device

    fav_pct, adv_pct, close_pnl_pct = _compute_pnl_tensors(events)

    out = torch.empty((n_e, n_v), device=device, dtype=torch.float32)
    for v_start in range(0, n_v, variant_chunk):
        v_end = min(v_start + variant_chunk, n_v)
        v_size = v_end - v_start

        tp = variants.tp_pct[v_start:v_end]              # [v_size]
        tp1 = tp / 2.0
        tp2 = tp
        sl = variants.sl_pct[v_start:v_end]              # [v_size]
        hold = variants.hold_minutes[v_start:v_end].to(torch.int64).clamp_max(T - 1)

        fav_eT = fav_pct.unsqueeze(1)
        adv_eT = adv_pct.unsqueeze(1)
        tp1_hit = fav_eT >= tp1.view(1, v_size, 1)
        tp2_hit = fav_eT >= tp2.view(1, v_size, 1)
        sl_hit = adv_eT <= -sl.view(1, v_size, 1)

        first_tp1 = _first_true_index(tp1_hit)
        first_tp2 = _first_true_index(tp2_hit)
        first_sl = _first_true_index(sl_hit)
        hold_b = hold.view(1, v_size).expand(n_e, v_size)

        sl_first = (first_sl < first_tp1) & (first_sl <= hold_b)
        tp1_first = (first_tp1 <= first_sl) & (first_tp1 <= hold_b)
        # Within "tp1_first" sub-tree, classify 50% runner outcome:
        #   - SL after tp1: needs first_sl > first_tp1 AND first_sl <= hold AND first_sl < first_tp2
        #   - TP2 after tp1: first_tp2 > first_tp1 AND first_tp2 <= hold AND first_tp2 < first_sl
        #   - else: close_at_hold

        runner_sl = (first_sl > first_tp1) & (first_sl <= hold_b) & (first_sl < first_tp2)
        runner_tp2 = (first_tp2 > first_tp1) & (first_tp2 <= hold_b) & (first_tp2 <= first_sl)
        # else: runner closes at hold

        hold_idx_2d = hold_b.long()
        close_at_hold = close_pnl_pct.gather(1, hold_idx_2d)

        gross_sl_full = -sl.view(1, v_size).expand(n_e, v_size)
        tp1_b = tp1.view(1, v_size).expand(n_e, v_size)
        tp2_b = tp2.view(1, v_size).expand(n_e, v_size)
        sl_b = sl.view(1, v_size).expand(n_e, v_size)

        # Runner pnl (50% of position)
        runner_pnl = torch.where(
            runner_sl, -sl_b,
            torch.where(runner_tp2, tp2_b, close_at_hold),
        )
        # Combined (50/50 split)
        combined_tp1 = 0.5 * tp1_b + 0.5 * runner_pnl

        gross = torch.where(
            sl_first, gross_sl_full,
            torch.where(
                tp1_first, combined_tp1,
                close_at_hold,
            ),
        )
        # Two-leg cost approximation when tp1 hit (close + later close = 2x cost)
        cost_factor = torch.where(tp1_first, torch.tensor(2.0, device=device), torch.tensor(1.0, device=device))
        out[:, v_start:v_end] = (gross - cost_pct * cost_factor).float()
    return out


# ---------------------------------------------------------------------------
# Family classifier: archetype slug → kernel name
# ---------------------------------------------------------------------------

def classify_exit_family(exit_archetype: str) -> str:
    """Map exit archetype slug to kernel family.

    Returns one of:
      "fixed"       — first-touch TP/SL (default; bwe_loop_gpu_eval.batch_eval)
      "time_only"   — close at hold
      "breakeven"   — BE ratchet
      "trail"       — trailing stop pct
      "multi_tp"    — 50/50 split at TP/2 and TP
    """
    s = exit_archetype.lower()

    # Time-based
    if (s.startswith("time_") or "_hard_stop" in s
        or s.startswith("event_hold") or "short_event_hold" in s):
        return "time_only"

    # Breakeven
    if s.startswith("be_") or "_be_" in s or "breakeven" in s or s.startswith("composite_exit_be"):
        return "breakeven"

    # Trailing
    if (s.startswith("trail_") or "trailing" in s or s.startswith("runner_")
        or "_trail" in s or s == "trail_chandelier"):
        return "trail"

    # Multi-TP / partial-ladder
    if (s.startswith("multi_tp_") or s.startswith("partial_ladder")
        or s.startswith("ladder_")):
        return "multi_tp"

    # Indicator / state machine — fallback to fixed for now (would need real
    # indicator computation; flagged for future work)
    if s.startswith("exit_on_") or s.startswith("sm_") or s.startswith("state_machine"):
        return "fixed"

    if s.startswith("adaptive_exit"):
        return "fixed"

    if s.startswith("indicator_invalidation"):
        return "fixed"

    # Default fixed
    return "fixed"


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _self_test() -> int:
    if not HAS_TORCH:
        print("SKIP: PyTorch not available")
        return 0

    from bwe_autoresearch.bwe_loop_gpu_eval import EventBatch, VariantGrid, batch_eval, get_device

    device = get_device()
    print(f"  device: {device}")

    # Synthetic dataset: 200 events, 30 minutes, drifting random walks
    rng = np.random.default_rng(42)
    n_e, T = 200, 30
    entry = rng.uniform(50, 200, size=n_e).astype(np.float32)
    sides = rng.choice([-1, 1], size=n_e).astype(np.int8)
    drift = rng.normal(0, 0.005, size=(n_e, T)).cumsum(axis=1)
    mid = entry[:, None] * (1 + drift)
    range_pct = rng.uniform(0.001, 0.005, size=(n_e, T))
    highs = (mid * (1 + range_pct)).astype(np.float32)
    lows = (mid * (1 - range_pct)).astype(np.float32)
    closes = mid.astype(np.float32)

    events = EventBatch.from_numpy(entry, sides, highs, lows, closes)
    # 256 variants on a small grid
    tp_grid = np.linspace(0.5, 3.0, 16, dtype=np.float32)
    sl_grid = np.linspace(0.5, 3.0, 16, dtype=np.float32)
    tps, sls = np.meshgrid(tp_grid, sl_grid)
    holds = np.full(tps.size, 20, dtype=np.int16)
    variants = VariantGrid.from_numpy(tps.ravel(), sls.ravel(), holds)
    events = events.to(device)
    variants = variants.to(device)

    fixed = batch_eval(events, variants, cost_pct=0.08, variant_chunk=512, device=device).cpu().numpy()
    time_o = eval_time_only(events, variants, 0.08).cpu().numpy()
    be = eval_breakeven(events, variants, 0.08).cpu().numpy()
    trail = eval_trailing_pct(events, variants, 0.08).cpu().numpy()
    mtp = eval_multi_tp_50_50(events, variants, 0.08).cpu().numpy()

    means = {
        "fixed":  float(fixed.mean()),
        "time":   float(time_o.mean()),
        "be":     float(be.mean()),
        "trail":  float(trail.mean()),
        "mtp":    float(mtp.mean()),
    }
    print(f"  mean returns by kernel: {means}")
    # Distinctness: assert at least 3 of 5 are pairwise distinct
    distinct_count = len(set(round(v, 4) for v in means.values()))
    print(f"  distinct mean values: {distinct_count} / 5")
    assert distinct_count >= 4, f"expected >=4 distinct, got {distinct_count}"

    # Spot check: time_only should not have the same as fixed (fixed cuts early on TP/SL)
    assert abs(means["fixed"] - means["time"]) > 0.01, "fixed and time_only too similar"
    # Spot check: trailing should differ from fixed
    assert abs(means["fixed"] - means["trail"]) > 0.005, "fixed and trail too similar"

    # Classifier checks
    assert classify_exit_family("time_1m_hard") == "time_only"
    assert classify_exit_family("be_at_1r_then_hold") == "breakeven"
    assert classify_exit_family("trail_atr_2") == "trail"
    assert classify_exit_family("multi_tp_50at1_50at2_sl1") == "multi_tp"
    assert classify_exit_family("partial_ladder_5tp_decay") == "multi_tp"
    assert classify_exit_family("fixed_tp1_sl1_symmetric") == "fixed"
    assert classify_exit_family("event_hold_then_close") == "time_only"
    assert classify_exit_family("breakeven_then_aggressive_trail") == "breakeven"
    assert classify_exit_family("runner_50pct_trail2atr") == "trail"

    print("\nALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test())
