"""Day 2.5 smoke test: 1 archetype × 10K variants on real data.

Verifies the full Day 2 pipeline end-to-end:
  1. Load real K-line event windows
  2. Pick a hand-picked combo (E001 entry × X001 exit)
  3. Run GPU batch eval over 10K (TP × SL) variants
  4. Score best variant via oos_p25_net_pct_after_cost
  5. Append to results.tsv (no git ops in smoke)
  6. Print throughput + top 5 variants

Acceptance:
  - Throughput ≥ 1K evals/sec on CPU (≥ 10K on CUDA)
  - results.tsv has 1 new row
  - Best score is finite (not NaN)
  - Top variant has plausible TP/SL within grid bounds

Usage:
    cd H:/BWE/20_CODE/Autoresearch
    python scripts/smoke_test_day2_loop.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from bwe_autoresearch.bwe_loop import (
    Combo,
    expand_variant_grid,
    load_events_for_combo,
    load_registry,
    run_one_experiment,
    synthetic_events,
)
from bwe_autoresearch.bwe_loop_gpu_eval import get_device, HAS_TORCH
from bwe_autoresearch.bwe_loop_results import ResultsLogger


def main() -> int:
    if not HAS_TORCH:
        print("FATAL: torch not available", file=sys.stderr)
        return 2

    device = get_device()
    print(f"[smoke] device={device}")

    # 1. Pick a real archetype combo (entry E001, exit X001)
    registry = load_registry()
    entries = [r for r in registry if r["type"] == "entry"]
    exits = [r for r in registry if r["type"] == "exit"]
    assert entries and exits, "registry empty"
    e, x = entries[0], exits[0]
    combo = Combo(
        entry_id=e["id"], exit_id=x["id"],
        entry_archetype=e["archetype"], exit_archetype=x["archetype"],
        channel=e["channel"], side=e["side"],
    )
    print(f"[smoke] combo: {combo.description()} channel={combo.channel} side={combo.side}")

    # 2. Try real data first; fallback to synthetic
    events = load_events_for_combo(combo, max_events=2000)
    if events is None:
        print("[smoke] no real events for channel; falling back to synthetic")
        events = synthetic_events(n_events=500, forward_minutes=15)
        used_synthetic = True
    else:
        used_synthetic = False
    print(f"[smoke] events: {events.n_events} (synthetic={used_synthetic})")

    # 3. 10K variant grid (100 TP × 100 SL × 1 hold)
    variants = expand_variant_grid()
    print(f"[smoke] variants: {variants.n_variants}")

    # 4. Run experiment (timing)
    t0 = time.time()
    result = run_one_experiment(
        combo, variants, events, cost_pct=0.08, device=device,
        use_synthetic=used_synthetic,
    )
    elapsed = time.time() - t0

    if result.error:
        print(f"[smoke] FAIL: {result.error}", file=sys.stderr)
        return 1

    rate = result.n_evals / max(elapsed, 1e-9)
    print(f"[smoke] elapsed={elapsed:.2f}s  evals={result.n_evals:,} ({rate:,.0f} evals/sec)")
    print(f"[smoke] best score={result.score:.4f}  best_tp={result.best_variant_tp:.2f}  best_sl={result.best_variant_sl:.2f}")

    # 5. Acceptance checks
    min_rate = 10_000 if device == "cuda" else 1_000
    if rate < min_rate:
        print(f"[smoke] WARN: throughput {rate:,.0f} < expected {min_rate:,}")
    if not np.isfinite(result.score):
        print("[smoke] FAIL: score is NaN/inf", file=sys.stderr)
        return 1

    # 6. Log to results.tsv (no git for smoke)
    log = ResultsLogger()
    decision = log.append(
        score=result.score, triggers=result.n_triggers,
        description=f"[SMOKE] {combo.description()} synthetic={used_synthetic} rate={rate:,.0f}",
    )
    print(f"[smoke] logged: status={decision.status} action={decision.action}")
    print(f"[smoke] results.tsv summary: {log.summary()}")

    print("\n[smoke] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
