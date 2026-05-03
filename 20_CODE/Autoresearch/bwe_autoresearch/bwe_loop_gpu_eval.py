"""Day 2.2: GPU batch evaluation kernel for first-touch backtests.

Vectorized "first-touch" exit: for each (event, variant) pair, find the first
minute where TP or SL is hit, otherwise exit at hold-window close. All on GPU
via torch broadcasting.

Performance target on RTX 5090:
  - 10K variants × 7K events × 60 minute bars = 4.2B comparisons
  - Expect ~1-3 seconds per such batch (well within 10-min experiment budget)

Memory model:
  - K-line tensors: [N_events, N_minutes] float32 (small, persistent)
  - Per-variant comparison masks: chunked to keep <4GB peak

Fallback: if CUDA unavailable, runs on CPU (slower but correct).

Schema:
    EventBatch:
        entry_prices [N_events] f32
        sides        [N_events] int8 (+1 long, -1 short)
        highs        [N_events, N_minutes] f32
        lows         [N_events, N_minutes] f32
        closes       [N_events, N_minutes] f32

    VariantGrid:
        tp_pct       [N_variants] f32
        sl_pct       [N_variants] f32
        hold_minutes [N_variants] int16

    Returns:
        net_returns_pct [N_events, N_variants] f32

Cost is applied as a single round-trip percentage (e.g. 0.08 for 8 bps).

Usage:
    from bwe_loop_gpu_eval import EventBatch, VariantGrid, batch_eval
    out = batch_eval(events, variants, cost_pct=0.08)
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import numpy as np

try:
    import torch
    HAS_TORCH = True
except ImportError:  # pragma: no cover
    torch = None  # type: ignore
    HAS_TORCH = False


SENTINEL_NO_HIT = 1_000_000  # impossible large index


def get_device() -> str:
    if HAS_TORCH and torch.cuda.is_available():
        return "cuda"
    return "cpu"


@dataclass
class EventBatch:
    """K-line windows for a batch of events (T0 to T0+N_minutes)."""

    entry_prices: "torch.Tensor"   # [N_events] f32
    sides: "torch.Tensor"          # [N_events] int8 (+1 long, -1 short)
    highs: "torch.Tensor"          # [N_events, N_minutes] f32
    lows: "torch.Tensor"           # [N_events, N_minutes] f32
    closes: "torch.Tensor"         # [N_events, N_minutes] f32

    @property
    def n_events(self) -> int:
        return int(self.entry_prices.shape[0])

    @property
    def n_minutes(self) -> int:
        return int(self.highs.shape[1])

    def to(self, device: str) -> "EventBatch":
        return EventBatch(
            entry_prices=self.entry_prices.to(device),
            sides=self.sides.to(device),
            highs=self.highs.to(device),
            lows=self.lows.to(device),
            closes=self.closes.to(device),
        )

    @classmethod
    def from_numpy(
        cls,
        entry_prices: np.ndarray,
        sides: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
    ) -> "EventBatch":
        return cls(
            entry_prices=torch.tensor(entry_prices, dtype=torch.float32),
            sides=torch.tensor(sides, dtype=torch.int8),
            highs=torch.tensor(highs, dtype=torch.float32),
            lows=torch.tensor(lows, dtype=torch.float32),
            closes=torch.tensor(closes, dtype=torch.float32),
        )


@dataclass
class VariantGrid:
    """Parameter grid expanded into 1D arrays of equal length."""

    tp_pct: "torch.Tensor"        # [N_variants] f32
    sl_pct: "torch.Tensor"        # [N_variants] f32
    hold_minutes: "torch.Tensor"  # [N_variants] int16

    @property
    def n_variants(self) -> int:
        return int(self.tp_pct.shape[0])

    def to(self, device: str) -> "VariantGrid":
        return VariantGrid(
            tp_pct=self.tp_pct.to(device),
            sl_pct=self.sl_pct.to(device),
            hold_minutes=self.hold_minutes.to(device),
        )

    @classmethod
    def from_numpy(
        cls, tp_pct: np.ndarray, sl_pct: np.ndarray, hold_minutes: np.ndarray
    ) -> "VariantGrid":
        return cls(
            tp_pct=torch.tensor(tp_pct, dtype=torch.float32),
            sl_pct=torch.tensor(sl_pct, dtype=torch.float32),
            hold_minutes=torch.tensor(hold_minutes, dtype=torch.int16),
        )


def _first_true_index(mask: "torch.Tensor", fill: int = SENTINEL_NO_HIT) -> "torch.Tensor":
    """Index of first True along last dim; `fill` if no True.

    mask: [..., T] bool
    returns: [...] int64
    """
    has_any = mask.any(dim=-1)
    first_idx = mask.float().argmax(dim=-1)
    return torch.where(has_any, first_idx, torch.full_like(first_idx, fill))


def _eval_chunk(
    events: EventBatch,
    variants: VariantGrid,
    cost_pct: float,
) -> "torch.Tensor":
    """Evaluate one variant chunk against all events. Returns [N_events, N_variants] f32."""
    device = events.entry_prices.device
    N_e = events.n_events
    N_v = variants.n_variants
    T = events.n_minutes

    # Compute per-event, per-bar PnL deltas in PERCENT.
    # For long: fav = (high - entry)/entry*100, adv = (low - entry)/entry*100
    # For short: fav = (entry - low)/entry*100, adv = (entry - high)/entry*100
    inv_entry = (100.0 / events.entry_prices).unsqueeze(1)  # [N_e, 1]
    side_long = (events.sides == 1).unsqueeze(1)            # [N_e, 1] bool

    long_fav = (events.highs - events.entry_prices.unsqueeze(1)) * inv_entry   # [N_e, T]
    long_adv = (events.lows - events.entry_prices.unsqueeze(1)) * inv_entry
    short_fav = (events.entry_prices.unsqueeze(1) - events.lows) * inv_entry
    short_adv = (events.entry_prices.unsqueeze(1) - events.highs) * inv_entry

    fav_pct = torch.where(side_long, long_fav, short_fav)   # [N_e, T] favorable PnL
    adv_pct = torch.where(side_long, long_adv, short_adv)   # [N_e, T] adverse PnL

    # Same for close PnL (used when no first-touch within hold window)
    close_pnl_pct = torch.where(
        side_long,
        (events.closes - events.entry_prices.unsqueeze(1)) * inv_entry,
        (events.entry_prices.unsqueeze(1) - events.closes) * inv_entry,
    )  # [N_e, T]

    # Broadcast to [N_e, N_v, T]
    # tp_hit[e, v, t] = fav_pct[e, t] >= tp[v]
    fav_eT = fav_pct.unsqueeze(1)   # [N_e, 1, T]
    adv_eT = adv_pct.unsqueeze(1)   # [N_e, 1, T]
    tp_v = variants.tp_pct.view(1, N_v, 1)   # [1, N_v, 1]
    sl_v = variants.sl_pct.view(1, N_v, 1)

    tp_hit = fav_eT >= tp_v        # [N_e, N_v, T]
    sl_hit = adv_eT <= -sl_v       # [N_e, N_v, T]

    first_tp = _first_true_index(tp_hit)   # [N_e, N_v]
    first_sl = _first_true_index(sl_hit)

    # Hold cap per variant (clamped to T-1)
    hold = variants.hold_minutes.to(torch.int64).view(1, N_v).clamp_max(T - 1)  # [1, N_v]
    # First-touch index = min(tp, sl), capped at hold
    first_touch = torch.minimum(first_tp, first_sl)
    # If first-touch > hold, exit at hold (use close PnL)
    capped_first = torch.minimum(first_touch, hold.expand_as(first_touch))

    # Determine outcome:
    #   if first_tp < first_sl AND first_tp <= hold -> TP hit, gross = +tp_pct
    #   if first_sl < first_tp AND first_sl <= hold -> SL hit, gross = -sl_pct
    #   if first_sl == first_tp (rare) -> conservative SL
    #   else (no touch within hold) -> exit at close[hold]
    tp_first = (first_tp < first_sl) & (first_tp <= hold)
    sl_first = (first_sl <= first_tp) & (first_sl <= hold)
    no_touch = ~(tp_first | sl_first)

    # Close PnL at the hold index for each variant: gather along T
    # close_pnl_pct[e, t]; we want [e, v] where t=hold[v]
    hold_idx = hold.expand(N_e, N_v).long()  # [N_e, N_v]
    close_at_hold = close_pnl_pct.gather(1, hold_idx)  # [N_e, N_v]

    gross_tp = variants.tp_pct.view(1, N_v).expand(N_e, N_v)
    gross_sl = -variants.sl_pct.view(1, N_v).expand(N_e, N_v)

    gross = torch.where(tp_first, gross_tp, torch.where(sl_first, gross_sl, close_at_hold))
    net = gross - cost_pct  # cost in same percent units

    return net.float()


def batch_eval(
    events: EventBatch,
    variants: VariantGrid,
    cost_pct: float = 0.08,
    variant_chunk: int = 1024,
    device: Optional[str] = None,
) -> "torch.Tensor":
    """Main API: run first-touch backtest, return net return % per (event, variant).

    Args:
        events: EventBatch with k-line windows.
        variants: VariantGrid with parameter combinations.
        cost_pct: round-trip cost in PERCENT (default 0.08 = 8 bps).
        variant_chunk: variants per chunk (memory-bounded).
        device: "cuda" or "cpu" or None for auto.

    Returns:
        net_returns_pct: [N_events, N_variants] f32 tensor on the chosen device.
    """
    if not HAS_TORCH:
        raise RuntimeError("PyTorch not available")
    if device is None:
        device = get_device()

    events = events.to(device)
    variants = variants.to(device)

    chunks = []
    for v_start in range(0, variants.n_variants, variant_chunk):
        v_end = min(v_start + variant_chunk, variants.n_variants)
        chunk = VariantGrid(
            tp_pct=variants.tp_pct[v_start:v_end],
            sl_pct=variants.sl_pct[v_start:v_end],
            hold_minutes=variants.hold_minutes[v_start:v_end],
        )
        out_chunk = _eval_chunk(events, chunk, cost_pct)
        chunks.append(out_chunk)
    return torch.cat(chunks, dim=1)


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _self_test() -> int:
    if not HAS_TORCH:
        print("SKIP: PyTorch not available")
        return 0

    rng = np.random.default_rng(0)
    device = get_device()
    print(f"  device: {device}")

    # Synthetic dataset: 100 events, 30 minutes, prices around 100
    N_e, T = 100, 30
    entry = rng.uniform(50, 200, size=N_e).astype(np.float32)
    sides = rng.choice([-1, 1], size=N_e).astype(np.int8)
    # generate paths: random walk with drift
    drift = rng.normal(0, 0.005, size=(N_e, T)).cumsum(axis=1)
    mid = entry[:, None] * (1 + drift)
    range_pct = rng.uniform(0.001, 0.005, size=(N_e, T))
    highs = (mid * (1 + range_pct)).astype(np.float32)
    lows = (mid * (1 - range_pct)).astype(np.float32)
    closes = mid.astype(np.float32)

    events = EventBatch.from_numpy(entry, sides, highs, lows, closes)

    # 256 variants on a small grid
    tp_grid = np.linspace(0.5, 3.0, 16, dtype=np.float32)
    sl_grid = np.linspace(0.5, 3.0, 16, dtype=np.float32)
    tps, sls = np.meshgrid(tp_grid, sl_grid)
    tps = tps.ravel()
    sls = sls.ravel()
    holds = np.full(tps.shape, 20, dtype=np.int16)
    variants = VariantGrid.from_numpy(tps, sls, holds)
    print(f"  {N_e} events × {variants.n_variants} variants × {T} minutes")

    t0 = time.time()
    out = batch_eval(events, variants, cost_pct=0.08, variant_chunk=256, device=device)
    elapsed = time.time() - t0
    n_evals = N_e * variants.n_variants
    rate = n_evals / max(elapsed, 1e-9)
    print(f"  shape: {tuple(out.shape)} dtype={out.dtype} device={out.device}")
    print(f"  elapsed: {elapsed*1000:.1f}ms ({rate:,.0f} evals/sec)")

    # Sanity: net returns should be in plausible range
    out_np = out.cpu().numpy()
    print(f"  net pct: min={out_np.min():.3f} median={np.median(out_np):.3f} max={out_np.max():.3f}")
    assert out_np.min() >= -10.0, "min net should be bounded by SL+cost"
    assert out_np.max() <= 10.0, "max net should be bounded by TP+cost"
    assert not np.any(np.isnan(out_np)), "no NaNs allowed"

    # Test 2: TP hits should give exactly tp_pct - cost
    # Make a deterministic event: long, entry=100, hi=200 always (TP always hits at t=0)
    entry2 = np.array([100.0], dtype=np.float32)
    sides2 = np.array([1], dtype=np.int8)  # long
    highs2 = np.full((1, 5), 200.0, dtype=np.float32)
    lows2 = np.full((1, 5), 99.0, dtype=np.float32)
    closes2 = np.full((1, 5), 150.0, dtype=np.float32)
    ev2 = EventBatch.from_numpy(entry2, sides2, highs2, lows2, closes2)
    var2 = VariantGrid.from_numpy(
        np.array([1.0], dtype=np.float32),
        np.array([2.0], dtype=np.float32),
        np.array([5], dtype=np.int16),
    )
    out2 = batch_eval(ev2, var2, cost_pct=0.08).cpu().numpy()
    print(f"  TP-always test: net={out2[0,0]:.4f} (expect 1.0 - 0.08 = 0.92)")
    assert abs(out2[0, 0] - 0.92) < 1e-3, f"expected 0.92, got {out2[0, 0]}"

    # Test 3: SL hits should give -sl_pct - cost
    highs3 = np.full((1, 5), 100.5, dtype=np.float32)
    lows3 = np.full((1, 5), 95.0, dtype=np.float32)  # -5% drop, hits 2% SL
    closes3 = np.full((1, 5), 95.0, dtype=np.float32)
    ev3 = EventBatch.from_numpy(entry2, sides2, highs3, lows3, closes3)
    var3 = VariantGrid.from_numpy(
        np.array([1.0], dtype=np.float32),
        np.array([2.0], dtype=np.float32),
        np.array([5], dtype=np.int16),
    )
    out3 = batch_eval(ev3, var3, cost_pct=0.08).cpu().numpy()
    print(f"  SL-always test: net={out3[0,0]:.4f} (expect -2.0 - 0.08 = -2.08)")
    assert abs(out3[0, 0] - (-2.08)) < 1e-3, f"expected -2.08, got {out3[0, 0]}"

    print("\nALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test())
