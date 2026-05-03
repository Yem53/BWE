"""Verify novel_dim filter actually subsets events differently per archetype."""
import sys
sys.path.insert(0, "H:/BWE/20_CODE/Autoresearch")

from bwe_autoresearch.bwe_loop import Combo, load_events_for_combo, load_registry

registry = load_registry()
entries = [r for r in registry if r["type"] == "entry"]
exits = [r for r in registry if r["type"] == "exit"]
x = exits[0]

# Pick a diverse set
test_ids = ["E001", "E005", "E017", "E007", "E018", "E021", "E044", "E142", "E201"]
print(f"Testing {len(test_ids)} entries (one exit X={x['id']}):\n")

for eid in test_ids:
    e = next((r for r in entries if r["id"] == eid), None)
    if e is None:
        print(f"  {eid}: NOT FOUND")
        continue
    combo = Combo(
        entry_id=e["id"], exit_id=x["id"],
        entry_archetype=e["archetype"], exit_archetype=x["archetype"],
        channel=e["channel"], side=e["side"],
        novel_dim=tuple(e.get("novel_dim", [])),
    )
    events = load_events_for_combo(combo, max_events=5000)
    n_events = events.n_events if events else 0
    n_applied = getattr(events, "_n_applied_filters", 0) if events else 0
    nd = list(combo.novel_dim)
    print(f"  {eid:5s} ch={combo.channel:12s} side={combo.side:5s}")
    print(f"        novel_dim={nd}")
    print(f"        n_filtered_events={n_events}  n_applied_filters={n_applied}")
    print()
