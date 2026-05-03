"""Salvage 4 accepted archetypes from Round 2 synthesizer raw output.

The call_claude parser failed to extract JSON (a parser bug, separate
issue). The synthesizer's raw text DOES contain valid JSON. Re-parse
it directly and write new_archetypes.jsonl manually.
"""

import json
import re
from pathlib import Path

DEBATE = Path("H:/BWE/40_EXPERIMENTS/debates/debate_20260427_091138")
RAW = DEBATE / "_synthesizer_raw.txt"
OUT_NEW = DEBATE / "new_archetypes.jsonl"
OUT_REJ = DEBATE / "rejected_archetypes.jsonl"

# The wrapper has structure:
# {"type":"result", ..., "result":"<json string>", ...}
wrapper = json.loads(RAW.read_text(encoding="utf-8"))
inner = wrapper["result"]

# Synthesizer truncated the closing '}' — patch and retry
if not inner.rstrip().endswith("}"):
    inner = inner.rstrip() + "}"
    print("[salvage] patched missing closing brace")

# inner is the JSON string the LLM output
data = json.loads(inner)
print(f"summary: {data['summary'][:300]}...")
print()
print(f"accepted: {len(data.get('accepted_archetypes', []))}")
print(f"revised:  {len(data.get('revised_archetypes', []))}")
print(f"rejected: {len(data.get('rejected_archetypes', []))}")

# Strip synthesizer-only fields when writing to registry-format jsonl
KEEP = {"id", "type", "archetype", "channel", "side", "novel_dim",
        "expected_distinct", "notes", "synthesizer_note"}
with OUT_NEW.open("w", encoding="utf-8") as f:
    for a in data["accepted_archetypes"]:
        clean = {k: a[k] for k in KEEP if k in a}
        f.write(json.dumps(clean, ensure_ascii=False) + "\n")
print(f"\nWrote: {OUT_NEW}")

with OUT_REJ.open("w", encoding="utf-8") as f:
    for r in data["rejected_archetypes"]:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"Wrote: {OUT_REJ}")

print(f"\nNext-round-focus from synthesizer:")
print(f"  {data.get('next_round_focus', '(none)')}")
