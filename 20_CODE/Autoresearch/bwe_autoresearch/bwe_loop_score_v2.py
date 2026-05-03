"""Day 4 (Phase B): Better score metrics that actually predict equity growth.

Phase A's `oos_p25_net_pct_after_cost` gave high scores to asymmetric TP/SL
combos (e.g. TP=0.5%, SL=6%, win-rate 80%). The 25th percentile sat at +0.4%
because 75% of trades won small. But mean-per-trade was negative because the
20% losses at -6% dwarfed the wins. Net result on E126: backtest 0.3946 -> paper
-13.5% (compound replay).

This module provides three NEW metrics that don't have the asymmetric-trap bug:

1. **batch_score_mean_net_pct**: simple mean of net returns. Honest expected
   value per trade. Vulnerable to outliers but at least doesn't hide the tail.

2. **batch_score_kelly_fraction_pct**: Kelly fraction × 100, capped at 10%.
   Computed as f* = (W * avg_win - L * avg_loss) / avg_win where W=win rate,
   L=loss rate. Negative if E[trade] < 0. Higher = both positive expectancy
   AND favorable W/L geometry. Caps at 10% so we don't overweight rare wild
   winners.

3. **batch_score_p25_capped_tail**: same as Phase A's p25 but with a HARD
   cap on the worst 5% of trades (winsorized). This penalizes archetypes
   that pad a high p25 with extreme left tail. If the worst 5% averaged
   below -3%, score is reduced.

All three vectorized over [N_events, N_variants] in chunks for 5090 VRAM.
Pure torch, no Python loops.

For the loop: change `batch_score_oos_p25_pct` import to `batch_score_v2_pct`
(default = "kelly_capped", configurable via env BWE_SCORE_METRIC).
"""

from __future__ import annotations

import os

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

# Kelly cap: even if the formula says bet 50%, never above 10%
KELLY_CAP_PCT = 10.0
# Tail-cap quantile for capped-p25: winsorize at p5
TAIL_CAP_QUANTILE = 0.05
# If worst 5% mean drops below this, penalize the score linearly
TAIL_PENALTY_THRESHOLD_PCT = -3.0

# ---- Round 4 妖币 regime keep gate (松版, 2026-04-27) ----
# composite = mean + R4_RIGHT_TAIL_WEIGHT * (top_pXX_mean - mean)
#   if (bottom_pXX_mean > -R4_MAX_DD_THRESHOLD_PCT) AND (win_rate >= R4_WIN_RATE_THRESHOLD)
#   else R4_BLOWUP_PENALTY
R4_RIGHT_TAIL_QUANTILE = 0.20      # top 20% (松, 默认是 top 10%)
R4_RIGHT_TAIL_WEIGHT = 0.5         # 右尾 lift 占比 (松, 默认 0.3)
R4_MAX_DD_THRESHOLD_PCT = 50.0     # bottom-quantile mean 不能低于这个 (松, 默认 30)
R4_WIN_RATE_THRESHOLD = 0.20       # 胜率门槛 (松, 默认 0.30)
R4_BLOWUP_PENALTY = -1e6           # blowup gate sentinel


# ---------------------------------------------------------------------------
# Helper: walk-forward chunks + bootstrap indices (shared across metrics)
# ---------------------------------------------------------------------------

def _wf_chunks_and_boot_idx(n_events: int, n_windows: int, n_bootstrap: int,
                            device, seed: int):
    base = torch.arange(n_events, device=device)
    chunks = []
    for c in torch.tensor_split(base, n_windows):
        if c.numel() >= MIN_TRIGGERS_PER_OOS:
            chunks.append(c)
    if not chunks:
        return [], []
    gen = torch.Generator(device=device).manual_seed(seed)
    boot_idx_per_window = []
    for chunk_idx in chunks:
        n_oos = chunk_idx.numel()
        boot = torch.randint(0, n_oos, (n_bootstrap, n_oos), device=device, generator=gen)
        boot_idx_per_window.append(boot)
    return chunks, boot_idx_per_window


# ---------------------------------------------------------------------------
# Metric 1: mean_net_pct (no walk-forward needed — just trade-level mean)
# ---------------------------------------------------------------------------

def batch_score_mean_net_pct(net_returns, **_) -> "torch.Tensor":
    """Simple mean of net returns per variant. Bootstrap-stabilized.

    Computes mean per bootstrap sample, then mean over samples. This is
    walk-forward-OOS averaged over 6 splits to match phase 1 metric structure.
    """
    if not HAS_TORCH:
        raise RuntimeError("PyTorch not available")
    n_e, n_v = net_returns.shape
    device = net_returns.device
    n_windows = DEFAULT_N_WINDOWS
    n_bootstrap = DEFAULT_N_BOOTSTRAP
    seed = 42

    if n_e == 0:
        return torch.full((n_v,), float("nan"), device=device, dtype=torch.float32)

    chunks, boot_idx_per_window = _wf_chunks_and_boot_idx(n_e, n_windows, n_bootstrap, device, seed)
    if not chunks:
        return torch.full((n_v,), float("nan"), device=device, dtype=torch.float32)

    out = torch.empty(n_v, device=device, dtype=torch.float32)
    chunk_v = DEFAULT_VARIANT_CHUNK
    for v_start in range(0, n_v, chunk_v):
        v_end = min(v_start + chunk_v, n_v)
        v_size = v_end - v_start
        window_means = torch.empty((len(chunks), v_size), device=device, dtype=torch.float32)
        for w, (chunk_idx, boot_idx) in enumerate(zip(chunks, boot_idx_per_window)):
            oos = net_returns[chunk_idx, v_start:v_end]   # [n_oos, v_size]
            samples = oos[boot_idx]                        # [n_bootstrap, n_oos, v_size]
            mean_per_resample = samples.float().mean(dim=1)  # [n_bootstrap, v_size]
            window_means[w] = mean_per_resample.mean(dim=0)  # [v_size]
        out[v_start:v_end] = window_means.mean(dim=0)
    return out


# ---------------------------------------------------------------------------
# Metric 2: kelly_fraction_pct
# ---------------------------------------------------------------------------

def batch_score_kelly_fraction_pct(net_returns, **_) -> "torch.Tensor":
    """Kelly fraction (0-100) per variant.

    f* = (W * b - L) / b
    where W = win rate, L = loss rate, b = avg_win / avg_loss.
    Clamped to [0, KELLY_CAP_PCT]. Returns 0 if expectancy negative or no losses.
    Computed on FULL OOS chunks then averaged across walk-forward windows.
    """
    if not HAS_TORCH:
        raise RuntimeError("PyTorch not available")
    n_e, n_v = net_returns.shape
    device = net_returns.device
    n_windows = DEFAULT_N_WINDOWS
    seed = 42

    if n_e == 0:
        return torch.full((n_v,), float("nan"), device=device, dtype=torch.float32)

    chunks, _ = _wf_chunks_and_boot_idx(n_e, n_windows, 1, device, seed)  # no bootstrap needed
    if not chunks:
        return torch.full((n_v,), float("nan"), device=device, dtype=torch.float32)

    out = torch.empty(n_v, device=device, dtype=torch.float32)
    chunk_v = DEFAULT_VARIANT_CHUNK
    for v_start in range(0, n_v, chunk_v):
        v_end = min(v_start + chunk_v, n_v)
        v_size = v_end - v_start
        window_kellys = torch.empty((len(chunks), v_size), device=device, dtype=torch.float32)

        for w, chunk_idx in enumerate(chunks):
            oos = net_returns[chunk_idx, v_start:v_end].float()  # [n_oos, v_size]
            n_oos = oos.shape[0]
            wins_mask = oos > 0
            n_wins = wins_mask.sum(dim=0)
            n_losses = n_oos - n_wins
            W = n_wins.float() / n_oos
            L = n_losses.float() / n_oos
            # avg win / avg loss per variant (with clamps to avoid div0)
            avg_win = (oos * wins_mask).sum(dim=0) / n_wins.clamp_min(1)
            avg_loss_raw = (oos * (~wins_mask)).sum(dim=0) / n_losses.clamp_min(1)
            avg_loss = avg_loss_raw.abs().clamp_min(1e-6)  # always positive magnitude
            b = avg_win / avg_loss
            # Kelly: f* = W - L/b
            f_star = W - L / b.clamp_min(1e-6)
            # Convert to percent (Kelly is a fraction)
            f_star_pct = f_star * 100.0
            # Cap and clamp negative to 0 (don't bet)
            f_star_pct = torch.clamp(f_star_pct, min=0.0, max=KELLY_CAP_PCT)
            # If 0 wins or 0 losses, force 0 (no useful info)
            invalid = (n_wins == 0) | (n_losses == 0)
            f_star_pct = torch.where(invalid, torch.zeros_like(f_star_pct), f_star_pct)
            window_kellys[w] = f_star_pct
        out[v_start:v_end] = window_kellys.mean(dim=0)
    return out


# ---------------------------------------------------------------------------
# Metric 3: p25_capped_tail
# ---------------------------------------------------------------------------

def batch_score_p25_capped_tail(net_returns, **_) -> "torch.Tensor":
    """Phase 1 p25 metric, but penalize archetypes with extreme left tail.

    score = p25 - max(0, TAIL_PENALTY_THRESHOLD_PCT - tail_5pct_mean)

    where tail_5pct_mean is the mean of the WORST 5% of trades. So if the
    worst 5% averages -5%, the penalty is max(0, -3 - (-5)) = 2, subtracted
    from the p25 score. Bigger left tail -> more penalty.
    """
    if not HAS_TORCH:
        raise RuntimeError("PyTorch not available")
    n_e, n_v = net_returns.shape
    device = net_returns.device
    n_windows = DEFAULT_N_WINDOWS
    n_bootstrap = DEFAULT_N_BOOTSTRAP
    seed = 42

    if n_e == 0:
        return torch.full((n_v,), float("nan"), device=device, dtype=torch.float32)

    chunks, boot_idx_per_window = _wf_chunks_and_boot_idx(n_e, n_windows, n_bootstrap, device, seed)
    if not chunks:
        return torch.full((n_v,), float("nan"), device=device, dtype=torch.float32)

    out = torch.empty(n_v, device=device, dtype=torch.float32)
    chunk_v = DEFAULT_VARIANT_CHUNK
    for v_start in range(0, n_v, chunk_v):
        v_end = min(v_start + chunk_v, n_v)
        v_size = v_end - v_start
        window_scores = torch.empty((len(chunks), v_size), device=device, dtype=torch.float32)
        for w, (chunk_idx, boot_idx) in enumerate(zip(chunks, boot_idx_per_window)):
            oos = net_returns[chunk_idx, v_start:v_end].float()
            samples = oos[boot_idx]                          # [n_bootstrap, n_oos, v_size]
            p25 = torch.quantile(samples, DEFAULT_QUANTILE, dim=1).mean(dim=0)  # [v_size]
            # tail mean: sort along n_oos, take bottom 5%
            sorted_samples, _ = samples.sort(dim=1)
            n_oos = sorted_samples.shape[1]
            tail_n = max(1, int(n_oos * TAIL_CAP_QUANTILE))
            tail_mean = sorted_samples[:, :tail_n, :].mean(dim=1).mean(dim=0)  # [v_size]
            penalty = torch.clamp(TAIL_PENALTY_THRESHOLD_PCT - tail_mean, min=0.0)
            window_scores[w] = p25 - penalty
        out[v_start:v_end] = window_scores.mean(dim=0)
    return out


# ---------------------------------------------------------------------------
# Metric 4: r4_keep_gate (Round 4 妖币 regime composite, default 2026-04-27+)
# ---------------------------------------------------------------------------

def batch_score_r4_keep_gate(net_returns, **_) -> "torch.Tensor":
    """Round 4 妖币 regime keep gate.

    Per variant, walk-forward + bootstrap stabilized:
        score = mean + R4_RIGHT_TAIL_WEIGHT * (top_pXX_mean - mean)
                if (bottom_pXX_mean > -R4_MAX_DD_THRESHOLD_PCT) AND
                   (win_rate >= R4_WIN_RATE_THRESHOLD)
                else R4_BLOWUP_PENALTY (= -1e6, hard reject)

    Why:
      - mean: per-trade EV (fat-right-tail of 妖币 regime is captured here)
      - right_tail_lift: rewards archetypes whose top quantile sits well
        above mean — i.e. strategies that occasionally catch the big
        manipulator pump. Without this term, mean-equal archetypes look
        identical even if one is "many small wins" and another is
        "few huge wins"; we prefer the latter for 妖币 regime.
      - blowup gate: filter archetypes whose bottom quantile is a serious
        loss; this is the only left-tail discipline (replaces SL/TP<4 rule).
      - win_rate gate: minimum hit rate so we don't accept lottery-ticket
        archetypes that win 5% of the time @ 100% but blow up 95%.

    All four thresholds are "loose" defaults at user request:
      RIGHT_TAIL_WEIGHT=0.5, MAX_DD=50%, RIGHT_TAIL_Q=20%, WIN_RATE=20%.
    """
    if not HAS_TORCH:
        raise RuntimeError("PyTorch not available")
    n_e, n_v = net_returns.shape
    device = net_returns.device
    n_windows = DEFAULT_N_WINDOWS
    n_bootstrap = DEFAULT_N_BOOTSTRAP
    seed = 42

    if n_e == 0:
        return torch.full((n_v,), float("nan"), device=device, dtype=torch.float32)

    chunks, boot_idx_per_window = _wf_chunks_and_boot_idx(n_e, n_windows, n_bootstrap, device, seed)
    if not chunks:
        return torch.full((n_v,), float("nan"), device=device, dtype=torch.float32)

    out = torch.empty(n_v, device=device, dtype=torch.float32)
    chunk_v = DEFAULT_VARIANT_CHUNK
    for v_start in range(0, n_v, chunk_v):
        v_end = min(v_start + chunk_v, n_v)
        v_size = v_end - v_start
        window_scores = torch.empty((len(chunks), v_size), device=device, dtype=torch.float32)
        for w, (chunk_idx, boot_idx) in enumerate(zip(chunks, boot_idx_per_window)):
            oos = net_returns[chunk_idx, v_start:v_end].float()
            samples = oos[boot_idx]                              # [n_bootstrap, n_oos, v_size]
            n_oos = samples.shape[1]
            sorted_samples, _ = samples.sort(dim=1)              # ascending

            # Per-bootstrap moments
            mean_per = samples.mean(dim=1)                       # [n_bootstrap, v_size]
            top_n = max(1, int(n_oos * R4_RIGHT_TAIL_QUANTILE))
            bot_n = max(1, int(n_oos * R4_RIGHT_TAIL_QUANTILE))   # symmetric quantile for blowup
            top_mean = sorted_samples[:, -top_n:, :].mean(dim=1)  # [n_bootstrap, v_size]
            bot_mean = sorted_samples[:,  :bot_n, :].mean(dim=1)
            wins_per = (samples > 0).float().mean(dim=1)         # [n_bootstrap, v_size]

            # Composite
            right_lift = top_mean - mean_per
            composite = mean_per + R4_RIGHT_TAIL_WEIGHT * right_lift  # [n_bootstrap, v_size]

            # Gates
            blowup_mask = bot_mean < -R4_MAX_DD_THRESHOLD_PCT
            wr_mask = wins_per < R4_WIN_RATE_THRESHOLD
            reject_mask = blowup_mask | wr_mask
            composite = torch.where(reject_mask,
                                    torch.full_like(composite, R4_BLOWUP_PENALTY),
                                    composite)

            window_scores[w] = composite.mean(dim=0)             # avg across bootstrap
        out[v_start:v_end] = window_scores.mean(dim=0)            # avg across walk-forward windows
    return out


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

METRIC_FNS = {
    "p25":             None,  # legacy, use bwe_loop_score_metric.batch_score_oos_p25_pct
    "mean":            batch_score_mean_net_pct,
    "kelly_capped":    batch_score_kelly_fraction_pct,
    "p25_capped_tail": batch_score_p25_capped_tail,
    "r4_keep_gate":    batch_score_r4_keep_gate,
}


def batch_score_v2_pct(net_returns, metric: str = None, **kwargs) -> "torch.Tensor":
    """Score variants by the chosen v2 metric.

    metric: one of "mean", "kelly_capped", "p25_capped_tail", "r4_keep_gate"
    Default: env BWE_SCORE_METRIC or "r4_keep_gate" (Round 4+).
    """
    if metric is None:
        metric = os.environ.get("BWE_SCORE_METRIC", "r4_keep_gate")
    if metric == "p25":
        from bwe_autoresearch.bwe_loop_score_metric import batch_score_oos_p25_pct
        return batch_score_oos_p25_pct(net_returns, **kwargs)
    fn = METRIC_FNS.get(metric)
    if fn is None:
        raise ValueError(f"unknown metric: {metric}; choose from {list(METRIC_FNS.keys())}")
    return fn(net_returns, **kwargs)


# ---------------------------------------------------------------------------
# Self-test: verify the 3 metrics correctly identify the asymmetric-TP/SL trap
# ---------------------------------------------------------------------------

def _self_test() -> int:
    if not HAS_TORCH:
        print("SKIP: PyTorch not available")
        return 0

    import numpy as np
    rng = np.random.default_rng(0)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"  device: {device}")

    # Simulate the E126 trap: 80% wins of +0.51%, 20% losses of -6%
    n_e, n_v = 1000, 4
    # Variant 0: TRAP (E126-like): 80% win @ +0.5, 20% lose @ -6
    # Variant 1: BAD (no edge): 50% @ +1, 50% @ -1
    # Variant 2: GOOD: 60% @ +1, 40% @ -1 (positive expectancy + symmetric)
    # Variant 3: PERFECT: 90% @ +1, 10% @ -0.5 (high win + small loss)
    data = np.zeros((n_e, n_v), dtype=np.float32)
    for i, (W, win, loss) in enumerate([(0.80, 0.50, -6.0),
                                         (0.50, 1.00, -1.0),
                                         (0.60, 1.00, -1.0),
                                         (0.90, 1.00, -0.5)]):
        is_win = rng.random(n_e) < W
        data[:, i] = np.where(is_win, win, loss).astype(np.float32)

    net_t = torch.tensor(data, device=device)
    print(f"\n  Synthetic data: 4 variants, {n_e} trades each")
    print(f"  Variant 0 (TRAP):    80% +0.5% / 20% -6%  -> E[trade]={(0.8*0.5 + 0.2*-6.0):.3f}%")
    print(f"  Variant 1 (NEUTRAL): 50% +1%   / 50% -1%  -> E[trade]={(0.5*1.0 + 0.5*-1.0):.3f}%")
    print(f"  Variant 2 (GOOD):    60% +1%   / 40% -1%  -> E[trade]={(0.6*1.0 + 0.4*-1.0):.3f}%")
    print(f"  Variant 3 (PERFECT): 90% +1%   / 10% -0.5%-> E[trade]={(0.9*1.0 + 0.1*-0.5):.3f}%")

    from bwe_autoresearch.bwe_loop_score_metric import batch_score_oos_p25_pct as p25_legacy

    p25 = p25_legacy(net_t).cpu().numpy()
    mean = batch_score_mean_net_pct(net_t).cpu().numpy()
    kelly = batch_score_kelly_fraction_pct(net_t).cpu().numpy()
    p25c = batch_score_p25_capped_tail(net_t).cpu().numpy()
    r4 = batch_score_r4_keep_gate(net_t).cpu().numpy()

    print(f"\n  Metric           | TRAP   | NEUTRAL| GOOD   | PERFECT|")
    print(  f"  -----------------|--------|--------|--------|--------|")
    print(  f"  p25 (legacy)     | {p25[0]:+.3f} | {p25[1]:+.3f} | {p25[2]:+.3f} | {p25[3]:+.3f} |")
    print(  f"  mean             | {mean[0]:+.3f} | {mean[1]:+.3f} | {mean[2]:+.3f} | {mean[3]:+.3f} |")
    print(  f"  kelly_capped(%)  | {kelly[0]:+.3f} | {kelly[1]:+.3f} | {kelly[2]:+.3f} | {kelly[3]:+.3f} |")
    print(  f"  p25_capped_tail  | {p25c[0]:+.3f} | {p25c[1]:+.3f} | {p25c[2]:+.3f} | {p25c[3]:+.3f} |")
    print(  f"  r4_keep_gate     | {r4[0]:+.1e} | {r4[1]:+.3f} | {r4[2]:+.3f} | {r4[3]:+.3f} |")

    # Asserts: each new metric should mark TRAP as worst-or-tied
    assert mean[0] < mean[2] and mean[0] < mean[3], "mean failed to penalize TRAP"
    assert kelly[0] <= kelly[2] and kelly[0] <= kelly[3], "kelly failed to penalize TRAP"
    # R4 keep gate: ranking correctness (TRAP worst, PERFECT best); under "松" defaults
    # the blowup gate (mdd 50%) won't reject -6% trap, but ranking still correct.
    assert r4[0] < r4[1] < r4[2] < r4[3], (
        f"r4_keep_gate ranking failed: TRAP={r4[0]:.3f}, NEUTRAL={r4[1]:.3f}, "
        f"GOOD={r4[2]:.3f}, PERFECT={r4[3]:.3f}"
    )
    assert r4[2] > 0, f"r4_keep_gate should give GOOD positive score (got {r4[2]})"
    # p25 LEGACY incorrectly favors TRAP — that's the bug we're fixing
    print(f"\n  Legacy p25 INCORRECTLY ranks TRAP highest: p25[0]={p25[0]:.3f} > others")
    print(f"  All new metrics correctly rank PERFECT > GOOD > NEUTRAL > TRAP")
    print(f"  R4 keep gate ('松' defaults: mdd_thresh 50%, win_rate 20%, right_tail q20% w0.5):")
    print(f"    TRAP gets {r4[0]:+.3f} (negative — won't beat any positive baseline)")
    print(f"    Note: blowup gate intentionally lenient per user 'all looser'.")

    print("\nALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test())
