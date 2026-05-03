"""Verify 5 different exits give 5 different scores for the same entry."""
import sys
sys.path.insert(0, "H:/BWE/20_CODE/Autoresearch")
from bwe_autoresearch.bwe_loop import (
    Combo, expand_variant_grid, load_events_for_combo, load_registry, run_one_experiment,
)
from bwe_autoresearch.bwe_loop_gpu_eval import get_device
from bwe_autoresearch.bwe_loop_exit_kernels import classify_exit_family

device = get_device()
print(f"device={device}", flush=True)

reg = load_registry()
e126 = next(r for r in reg if r["id"] == "E126")  # the top entry from overnight

# Pick 5 exits from different families
test_exits = [
    "X001",  # fixed_tp1_sl1_symmetric → fixed
    "X041",  # time_1m_hard → time_only
    "X027",  # be_at_1r_then_hold → breakeven (note: actual id may differ)
    "X017",  # trail_atr_2 → trail
    "X011",  # ladder_5_steps_pct → multi_tp
]

# Look up each by id, find representative
for xid in test_exits:
    x = next((r for r in reg if r["id"] == xid), None)
    if x is None:
        print(f"  {xid}: NOT FOUND")
        continue
    fam = classify_exit_family(x["archetype"])
    combo = Combo(
        entry_id=e126["id"], exit_id=x["id"],
        entry_archetype=e126["archetype"], exit_archetype=x["archetype"],
        channel=e126["channel"], side=e126["side"],
        novel_dim=tuple(e126.get("novel_dim", [])),
    )
    events = load_events_for_combo(combo)
    if events is None:
        print(f"  {xid}: NO EVENTS")
        continue
    variants = expand_variant_grid()
    result = run_one_experiment(combo, variants, events, cost_pct=0.08, device=device)
    print(f"  {xid:5s}  {x['archetype']:35s}  family={fam:10s}  score={result.score:+.4f}  best_tp={result.best_variant_tp:.2f} sl={result.best_variant_sl:.2f}  err={result.error}")

print("DONE", flush=True)
