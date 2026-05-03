"""Day 2.3: Single optimization metric for the Karpathy-style loop.

Single source of truth: every experiment outputs ONE number that decides
keep/discard. Following Karpathy autoresearch philosophy.

Metric: oos_p25_net_pct_after_cost
  - 6-window walk-forward (rotate IS/OOS, take OOS p25 each rotation, average)
  - Within each OOS, bootstrap 100 resamples, take p25 each, average them
  - Returns ALREADY have cost subtracted upstream (cost handled in eval kernel)
  - Result expressed in PERCENT (so 0.5 = 0.5% net per trade at 25th percentile)

Why p25 (not median, not mean):
  - User has $1000 capital — drawdown matters more than headline avg
  - p25 = "if I'm in the bottom quartile of trades, am I still profitable?"
  - Mean is too easily inflated by 1-2 lucky trades on small sample

Why walk-forward (not random splits):
  - Time-ordered events; random splits leak future info
  - 6 windows = enough rotations for stability without slicing too thin

Why bootstrap p25 within OOS (not just raw p25):
  - Stabilizes estimate against outliers
  - 100 resamples: tradeoff for speed (full 1B target needs <0.1s/eval)

Usage:
    from bwe_loop_score_metric import oos_p25_net_pct_after_cost
    score = oos_p25_net_pct_after_cost(returns_array)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

try:
    import torch
    HAS_TORCH = True
except ImportError:  # pragma: no cover
    torch = None  # type: ignore
    HAS_TORCH = False

DEFAULT_N_WINDOWS = 6
DEFAULT_N_BOOTSTRAP = 100
DEFAULT_QUANTILE = 0.25
MIN_TRIGGERS_PER_OOS = 5
DEFAULT_VARIANT_CHUNK = 8192


def batch_score_oos_p25_pct(
    net_returns,
    n_windows: int = DEFAULT_N_WINDOWS,
    n_bootstrap: int = DEFAULT_N_BOOTSTRAP,
    seed: int = 42,
    variant_chunk: int = DEFAULT_VARIANT_CHUNK,
):
    """GPU-vectorized: compute oos_p25_net_pct_after_cost for all variants in parallel.

    Replaces 90K-iteration Python loop with one tensor op.
    Per-chunk peak: n_bootstrap × oos_size × variant_chunk × 4 bytes.
    100 × 233 × 8192 × 4 = 763 MB → safe on 32GB VRAM.

    Args:
        net_returns: torch.Tensor [N_events, N_variants] f32 (cost subtracted upstream).
    Returns:
        torch.Tensor [N_variants] f32 on same device.
    """
    if not HAS_TORCH:
        raise RuntimeError("PyTorch not available")
    if net_returns.dim() != 2:
        raise ValueError(f"expected 2D, got {net_returns.shape}")

    n_e, n_v = net_returns.shape
    device = net_returns.device

    if n_e == 0:
        return torch.full((n_v,), float("nan"), device=device, dtype=torch.float32)

    base = torch.arange(n_e, device=device)
    chunk_idx_list = []
    for c in torch.tensor_split(base, n_windows):
        if c.numel() >= MIN_TRIGGERS_PER_OOS:
            chunk_idx_list.append(c)
    if not chunk_idx_list:
        return torch.full((n_v,), float("nan"), device=device, dtype=torch.float32)

    gen = torch.Generator(device=device).manual_seed(seed)
    boot_idx_per_window = []
    for chunk_idx in chunk_idx_list:
        n_oos = chunk_idx.numel()
        boot = torch.randint(0, n_oos, (n_bootstrap, n_oos), device=device, generator=gen)
        boot_idx_per_window.append(boot)

    out = torch.empty(n_v, device=device, dtype=torch.float32)
    for v_start in range(0, n_v, variant_chunk):
        v_end = min(v_start + variant_chunk, n_v)
        v_size = v_end - v_start
        window_means = torch.empty((len(chunk_idx_list), v_size), device=device, dtype=torch.float32)
        for w, (chunk_idx, boot_idx) in enumerate(zip(chunk_idx_list, boot_idx_per_window)):
            oos = net_returns[chunk_idx, v_start:v_end]
            samples = oos[boot_idx]
            p25 = torch.quantile(samples.float(), DEFAULT_QUANTILE, dim=1)
            window_means[w] = p25.mean(dim=0)
        out[v_start:v_end] = window_means.mean(dim=0)

    return out


@dataclass(frozen=True)
class ScoreReport:
    """Detailed breakdown for diagnostics — main score is .score field."""

    score: float          # the single metric (percent net at p25)
    n_triggers: int       # total triggers across all events
    n_windows_used: int   # windows that had >= MIN_TRIGGERS_PER_OOS
    median_net_pct: float # for sanity check, NOT the optimization target
    mean_net_pct: float
    p10_net_pct: float    # tail risk
    raw_oos_p25_per_window: list[float]


def _bootstrap_p25(arr: np.ndarray, n_resamples: int, rng: np.random.Generator) -> float:
    """Mean of p25 across n_resamples bootstrap samples."""
    if arr.size == 0:
        return float("nan")
    n = arr.size
    # vectorized: sample indices [n_resamples, n], gather, take p25 per row
    idx = rng.integers(0, n, size=(n_resamples, n))
    samples = arr[idx]  # [n_resamples, n]
    p25_per_sample = np.quantile(samples, DEFAULT_QUANTILE, axis=1)
    return float(np.mean(p25_per_sample))


def oos_p25_net_pct_after_cost(
    net_returns_pct: np.ndarray,
    event_timestamps_ms: np.ndarray | None = None,
    n_windows: int = DEFAULT_N_WINDOWS,
    n_bootstrap: int = DEFAULT_N_BOOTSTRAP,
    seed: int = 42,
) -> float:
    """Compute the single metric.

    Args:
        net_returns_pct: shape [N_triggers], net return AFTER cost in PERCENT.
            (Cost subtraction happens in the eval kernel, not here.)
        event_timestamps_ms: shape [N_triggers], unix ms. Used for time-ordered
            walk-forward split. If None, assumes input is already time-sorted
            and splits by index.
        n_windows: number of walk-forward windows (default 6).
        n_bootstrap: bootstrap resamples per OOS window (default 100).
        seed: RNG seed for reproducibility.

    Returns:
        Single float score in PERCENT (negative = losing strategy).
    """
    rep = score_with_report(
        net_returns_pct, event_timestamps_ms, n_windows, n_bootstrap, seed
    )
    return rep.score


def score_with_report(
    net_returns_pct: np.ndarray,
    event_timestamps_ms: np.ndarray | None = None,
    n_windows: int = DEFAULT_N_WINDOWS,
    n_bootstrap: int = DEFAULT_N_BOOTSTRAP,
    seed: int = 42,
) -> ScoreReport:
    """Same as oos_p25_net_pct_after_cost but returns a detailed report."""
    arr = np.asarray(net_returns_pct, dtype=np.float64).ravel()
    n = arr.size
    rng = np.random.default_rng(seed)

    if n == 0:
        return ScoreReport(
            score=float("nan"), n_triggers=0, n_windows_used=0,
            median_net_pct=float("nan"), mean_net_pct=float("nan"),
            p10_net_pct=float("nan"), raw_oos_p25_per_window=[],
        )

    # Time-order if timestamps given
    if event_timestamps_ms is not None:
        ts = np.asarray(event_timestamps_ms, dtype=np.int64).ravel()
        if ts.size != n:
            raise ValueError(f"timestamps len {ts.size} != returns len {n}")
        order = np.argsort(ts, kind="stable")
        arr = arr[order]

    # Walk-forward: split into n_windows roughly equal chunks
    chunk_indices = np.array_split(np.arange(n), n_windows)
    raw_oos_p25 = []
    for w_idx in range(n_windows):
        oos_chunk = chunk_indices[w_idx]
        if len(oos_chunk) < MIN_TRIGGERS_PER_OOS:
            continue
        oos = arr[oos_chunk]
        raw_oos_p25.append(_bootstrap_p25(oos, n_bootstrap, rng))

    n_used = len(raw_oos_p25)
    if n_used == 0:
        score = float("nan")
    else:
        score = float(np.mean(raw_oos_p25))

    return ScoreReport(
        score=score,
        n_triggers=n,
        n_windows_used=n_used,
        median_net_pct=float(np.median(arr)),
        mean_net_pct=float(np.mean(arr)),
        p10_net_pct=float(np.quantile(arr, 0.10)),
        raw_oos_p25_per_window=raw_oos_p25,
    )


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _self_test() -> int:
    rng = np.random.default_rng(0)

    # Case 1: clearly profitable strategy
    profitable = rng.normal(loc=0.5, scale=1.0, size=1000)
    s1 = oos_p25_net_pct_after_cost(profitable)
    assert s1 > -0.5, f"profitable strategy should not give very negative score: {s1}"
    print(f"  profitable: score={s1:.3f} (expect > -0.5)")

    # Case 2: losing strategy
    losing = rng.normal(loc=-0.3, scale=1.0, size=1000)
    s2 = oos_p25_net_pct_after_cost(losing)
    assert s2 < 0, f"losing strategy should give negative score: {s2}"
    print(f"  losing:     score={s2:.3f} (expect < 0)")

    # Case 3: tiny sample (below MIN_TRIGGERS)
    tiny = np.array([1.0, 2.0])
    s3 = oos_p25_net_pct_after_cost(tiny)
    print(f"  tiny:       score={s3} (expect nan)")
    assert np.isnan(s3), "tiny sample should be nan"

    # Case 4: empty
    s4 = oos_p25_net_pct_after_cost(np.array([]))
    print(f"  empty:      score={s4} (expect nan)")
    assert np.isnan(s4)

    # Case 5: with timestamps (time-shuffled input should match sorted input)
    n = 600
    ts = np.arange(n)
    arr = rng.normal(0.2, 0.5, size=n)
    score_sorted = oos_p25_net_pct_after_cost(arr, ts)
    perm = rng.permutation(n)
    score_shuffled = oos_p25_net_pct_after_cost(arr[perm], ts[perm])
    print(f"  time-sort:  sorted={score_sorted:.3f} shuffled={score_shuffled:.3f}")
    assert abs(score_sorted - score_shuffled) < 0.05, "time-sort should be deterministic"

    # Case 6: detailed report
    rep = score_with_report(profitable)
    print(f"  report: score={rep.score:.3f} n={rep.n_triggers} "
          f"windows={rep.n_windows_used} median={rep.median_net_pct:.3f} "
          f"p10={rep.p10_net_pct:.3f}")
    assert rep.n_windows_used == DEFAULT_N_WINDOWS

    print("\nALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test())
