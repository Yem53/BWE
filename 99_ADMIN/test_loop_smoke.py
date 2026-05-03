"""End-to-end smoke: 1 experiment with filter + GPU score, verify result."""
import sys, time
sys.path.insert(0, "H:/BWE/20_CODE/Autoresearch")

from bwe_autoresearch.bwe_loop import (
    Combo, expand_variant_grid, load_events_for_combo, load_registry, run_one_experiment,
)
from bwe_autoresearch.bwe_loop_gpu_eval import get_device

device = get_device()
print(f"device={device}", flush=True)

reg = load_registry()
e = next(r for r in reg if r["id"] == "E001")
x = next(r for r in reg if r["id"] == "X001")
combo = Combo(
    entry_id=e["id"], exit_id=x["id"],
    entry_archetype=e["archetype"], exit_archetype=x["archetype"],
    channel=e["channel"], side=e["side"],
    novel_dim=tuple(e.get("novel_dim", [])),
)
print(f"combo: {combo.description()} novel_dim={list(combo.novel_dim)}", flush=True)

variants = expand_variant_grid()
print(f"variants: {variants.n_variants}", flush=True)

events = load_events_for_combo(combo)
n_evt = events.n_events if events else 0
print(f"events after filter: {n_evt}", flush=True)

t0 = time.time()
result = run_one_experiment(combo, variants, events, cost_pct=0.08, device=device)
elapsed = time.time() - t0
print(f"elapsed: {elapsed:.2f}s  evals: {result.n_evals:,} ({result.n_evals/max(elapsed,1e-9):,.0f} eval/s)", flush=True)
print(f"score: {result.score:.4f}  best_tp={result.best_variant_tp:.2f}  best_sl={result.best_variant_sl:.2f}", flush=True)
print(f"error: {result.error}", flush=True)
print("SMOKE_OK" if not result.error else "SMOKE_FAIL", flush=True)
