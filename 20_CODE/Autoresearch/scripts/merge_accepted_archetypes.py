"""Merge a debate run's `new_archetypes.jsonl` into the main registry.

Validates each accepted archetype before merging:
  - Required fields present (id, type, archetype, channel, side, novel_dim, notes)
  - id doesn't collide with existing registry IDs
  - novel_dim filter parses (at least 1 condition is supported)
  - notes is non-trivial (>=10 chars)

If any new archetype's novel_dim has zero supported conditions, it gets
quarantined to `quarantine_archetypes.jsonl` (would fall through filter
and produce duplicate baselines — bad for the loop).

Usage:
    python scripts/merge_accepted_archetypes.py <debate_run_dir>
    python scripts/merge_accepted_archetypes.py H:/BWE/40_EXPERIMENTS/debates/debate_20260427_xxxxxx
    python scripts/merge_accepted_archetypes.py --latest    # pick newest debate
    python scripts/merge_accepted_archetypes.py --dry-run <dir>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from bwe_autoresearch.bwe_loop_entry_filter import build_filter_expr

from bwe_autoresearch.bwe_paths import (  # noqa: E402
    REGISTRY_JSONL as REGISTRY_PATH,
    DEBATES_DIR as DEBATES_BASE,
    REGISTRY_BACKUPS_DIR as REGISTRY_BACKUP_DIR,
)

REQUIRED_FIELDS = {"id", "type", "archetype", "channel", "side", "novel_dim", "notes"}
VALID_TYPES = {"entry", "exit", "filter", "risk", "cross_channel"}
VALID_CHANNELS = {"OI_Price", "pricechange", "Reserved6", "*", "NA"}
VALID_SIDES = {"long", "short", "both", "NA"}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def validate_archetype(arch: dict, existing_ids: set, registry_size_by_type: dict) -> tuple[bool, list[str]]:
    """Return (is_valid, list_of_errors)."""
    errors = []
    missing = REQUIRED_FIELDS - set(arch.keys())
    if missing:
        errors.append(f"missing fields: {sorted(missing)}")
        return False, errors

    if arch["type"] not in VALID_TYPES:
        errors.append(f"invalid type: {arch['type']}")
    if arch["channel"] not in VALID_CHANNELS:
        errors.append(f"invalid channel: {arch['channel']}")
    if arch["side"] not in VALID_SIDES:
        errors.append(f"invalid side: {arch['side']}")
    if not isinstance(arch["novel_dim"], list) or not arch["novel_dim"]:
        errors.append("novel_dim must be non-empty list")
    if len(arch.get("notes", "")) < 10:
        errors.append(f"notes too short: {arch.get('notes', '')!r}")
    if arch["id"] in existing_ids:
        errors.append(f"id collision: {arch['id']} already exists")

    return (len(errors) == 0), errors


def check_filter_coverage(novel_dim: list[str]) -> tuple[int, int, list[str]]:
    """Returns (n_supported, n_total, list_of_skipped).

    Calls build_filter_expr without events_df; flag-style conditions
    that need a DataFrame to evaluate count as supported (they will be
    properly evaluated at loop runtime).
    """
    expr, applied, skipped = build_filter_expr(novel_dim, events_df=None)
    return len(applied), len(novel_dim), skipped


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dir", nargs="?", default=None, help="debate run directory")
    ap.add_argument("--latest", action="store_true", help="use newest debate")
    ap.add_argument("--dry-run", action="store_true", help="validate but don't write")
    args = ap.parse_args()

    if args.latest:
        if not DEBATES_BASE.exists():
            print(f"FATAL: {DEBATES_BASE} doesn't exist")
            return 1
        runs = sorted([d for d in DEBATES_BASE.iterdir() if d.is_dir()], reverse=True)
        if not runs:
            print(f"FATAL: no debate runs in {DEBATES_BASE}")
            return 1
        debate_dir = runs[0]
    elif args.dir:
        debate_dir = Path(args.dir)
    else:
        print("FATAL: pass <dir> or --latest")
        return 1

    new_arch_file = debate_dir / "new_archetypes.jsonl"
    if not new_arch_file.exists():
        print(f"FATAL: {new_arch_file} doesn't exist (no accepted archetypes from this debate)")
        return 1

    print(f"Reading: {new_arch_file}")
    new_archs = load_jsonl(new_arch_file)
    print(f"  {len(new_archs)} accepted archetypes")

    print(f"Reading existing registry: {REGISTRY_PATH}")
    existing = load_jsonl(REGISTRY_PATH)
    existing_ids = {r["id"] for r in existing}
    existing_archetypes = {r["archetype"] for r in existing}

    by_type = {}
    for r in existing:
        by_type[r["type"]] = by_type.get(r["type"], 0) + 1
    print(f"  existing: total={len(existing)} by_type={by_type}")

    # Validate each new archetype
    to_merge = []
    quarantined = []
    rejected = []
    for arch in new_archs:
        ok, errors = validate_archetype(arch, existing_ids, by_type)
        # Strip non-schema fields (synthesizer_note etc.)
        clean = {k: arch[k] for k in arch if k in REQUIRED_FIELDS or k == "expected_distinct"}
        clean["expected_distinct"] = clean.get("expected_distinct", True)

        if arch["archetype"] in existing_archetypes:
            rejected.append((arch, ["archetype name already in registry"]))
            continue

        if not ok:
            rejected.append((arch, errors))
            continue

        # Filter coverage check
        n_supp, n_total, skipped = check_filter_coverage(arch["novel_dim"])
        if n_supp == 0 and arch["type"] == "entry":
            quarantined.append((clean, n_supp, n_total, skipped))
            continue
        if n_supp == 0 and arch["type"] in ("filter", "cross_channel"):
            quarantined.append((clean, n_supp, n_total, skipped))
            continue

        to_merge.append(clean)

    print(f"\nValidation:")
    print(f"  to merge:       {len(to_merge)}")
    print(f"  quarantined:    {len(quarantined)} (no supported novel_dim conditions)")
    print(f"  rejected:       {len(rejected)} (schema/dup errors)")

    for arch, errs in rejected:
        print(f"  [REJECT] {arch.get('id', '?')} {arch.get('archetype', '?')}: {errs}")
    for clean, n_supp, n_total, skipped in quarantined:
        print(f"  [QUARANTINE] {clean['id']} {clean['archetype']}: 0/{n_total} supported, all skipped: {skipped[:3]}...")

    if args.dry_run:
        print("\nDRY RUN — no changes written")
        return 0

    if not to_merge:
        print("\nNo archetypes to merge.")
        return 0

    # Backup registry
    REGISTRY_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    import time
    backup_path = REGISTRY_BACKUP_DIR / f"hypothesis_registry_pre_{time.strftime('%Y%m%d_%H%M%S')}.jsonl"
    backup_path.write_text(REGISTRY_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"\nBacked up registry to: {backup_path}")

    # Append new archetypes
    with REGISTRY_PATH.open("a", encoding="utf-8") as f:
        for a in to_merge:
            f.write(json.dumps(a, ensure_ascii=False) + "\n")
    print(f"Appended {len(to_merge)} archetypes to {REGISTRY_PATH}")
    new_total = len(existing) + len(to_merge)
    print(f"Registry now: {new_total} archetypes")

    # Save quarantined to debate dir for review
    if quarantined:
        q_path = debate_dir / "quarantined_archetypes.jsonl"
        with q_path.open("w", encoding="utf-8") as f:
            for clean, n_supp, n_total, skipped in quarantined:
                rec = dict(clean)
                rec["_quarantine_reason"] = f"0/{n_total} supported novel_dim conditions"
                rec["_skipped_conditions"] = skipped
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"Quarantined archetypes saved to: {q_path} (re-propose with supported fields)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
