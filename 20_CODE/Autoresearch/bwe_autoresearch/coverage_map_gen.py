"""Day 1.4: Coverage map generator.

Reads H:/BWE/40_EXPERIMENTS/hypothesis_registry.jsonl and renders a self-
contained HTML dashboard at H:/BWE/40_EXPERIMENTS/coverage_map.html.

Initial state: every archetype is "untested" (gray). When Phase 3 starts
running experiments, a combo_registry.parquet will live alongside, and this
generator can be re-run to color cells by status (passed=green, failed=red,
crashed=yellow).

The page contains:
  1. Per-type counts (entry/exit/filter/risk/cross_channel)
  2. Channel × side breakdown for entries
  3. Combo-space cardinality estimate (entry × timing × filter × exit × risk)
  4. Two 2D heatmaps:
       - entry × exit (the most important pair)
       - entry × filter (sample of filter coverage)
  5. Full archetype list (collapsible)

Usage:
    python -m bwe_autoresearch.coverage_map_gen
    # then open H:/BWE/40_EXPERIMENTS/coverage_map.html in a browser
"""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from bwe_autoresearch.bwe_paths import (  # noqa: E402
    REGISTRY_JSONL as REGISTRY_PATH,
    EXPERIMENTS_DIR,
    COVERAGE_HTML as OUTPUT_PATH,
)
COMBO_REGISTRY_PATH = EXPERIMENTS_DIR / "combo_registry.parquet"  # Phase 2 output

TIMING_DELAYS = [0, 30, 60, 180, 300]  # seconds — Phase 3 explores all per combo


def load_registry(path: Path = REGISTRY_PATH) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def load_combo_status(path: Path = COMBO_REGISTRY_PATH) -> dict[tuple[str, str], str]:
    """Return {(entry_id, exit_id): status} from combo_registry if exists."""
    if not path.exists():
        return {}
    try:
        import polars as pl
        df = pl.read_parquet(path)
        # Expect columns: entry_id, exit_id, status
        out: dict[tuple[str, str], str] = {}
        for row in df.iter_rows(named=True):
            out[(row["entry_id"], row["exit_id"])] = row.get("status", "untested")
        return out
    except Exception:
        return {}


def cell_color(status: str) -> str:
    return {
        "passed": "#7be07b",
        "deep_passed": "#4caf50",
        "quick_passed": "#a5d6a7",
        "failed": "#ef9a9a",
        "crashed": "#ffd54f",
        "untested": "#eeeeee",
    }.get(status, "#dddddd")


def render_2d_heatmap(
    rows: list[dict], col_type: str, row_type: str, status_map: dict
) -> str:
    cols = [r for r in rows if r["type"] == col_type]
    rws = [r for r in rows if r["type"] == row_type]

    th = "".join(
        f'<th title="{html.escape(c["notes"])}" '
        f'style="writing-mode:vertical-rl;font-size:9px;padding:2px;">'
        f'{html.escape(c["id"])}</th>'
        for c in cols
    )
    body_rows = []
    for r in rws:
        cells = []
        for c in cols:
            status = status_map.get((r["id"], c["id"]), "untested")
            cells.append(
                f'<td style="background:{cell_color(status)};width:10px;height:10px;" '
                f'title="{html.escape(r["id"])} × {html.escape(c["id"])}: {status}"></td>'
            )
        body_rows.append(
            f'<tr><th title="{html.escape(r["notes"])}" '
            f'style="font-size:10px;text-align:right;padding:2px;">'
            f'{html.escape(r["id"])}</th>{"".join(cells)}</tr>'
        )

    n_combos = len(cols) * len(rws)
    n_passed = sum(
        1 for c in cols for r in rws
        if status_map.get((r["id"], c["id"]), "untested") in {"passed", "deep_passed", "quick_passed"}
    )
    coverage_pct = (n_passed / n_combos * 100) if n_combos else 0.0

    return f"""
    <h3>{row_type.title()} × {col_type.title()} ({n_combos:,} combos, {coverage_pct:.1f}% passed)</h3>
    <table style="border-collapse:collapse;border:1px solid #ccc;">
      <tr><th></th>{th}</tr>
      {"".join(body_rows)}
    </table>
    """


def render_per_type_summary(rows: list[dict]) -> str:
    counts = Counter(r["type"] for r in rows)
    items = "".join(
        f'<tr><td>{html.escape(k)}</td><td style="text-align:right;">{v}</td></tr>'
        for k, v in sorted(counts.items())
    )
    return f"""
    <h3>Per-type counts (total {len(rows)})</h3>
    <table border="1" cellpadding="4" style="border-collapse:collapse;">
      <tr><th>Type</th><th>Count</th></tr>
      {items}
    </table>
    """


def render_channel_side_breakdown(rows: list[dict]) -> str:
    by_chan: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        if r["type"] != "entry":
            continue
        by_chan[r["channel"]][r["side"]] += 1

    sides = sorted({s for c in by_chan.values() for s in c})
    th = "".join(f"<th>{html.escape(s)}</th>" for s in sides)
    body = []
    for chan, sc in sorted(by_chan.items()):
        cells = "".join(f'<td style="text-align:right;">{sc.get(s, 0)}</td>' for s in sides)
        body.append(f'<tr><td>{html.escape(chan)}</td>{cells}</tr>')
    return f"""
    <h3>Entry breakdown: channel × side</h3>
    <table border="1" cellpadding="4" style="border-collapse:collapse;">
      <tr><th>Channel</th>{th}</tr>
      {"".join(body)}
    </table>
    """


def render_combo_space_estimate(rows: list[dict]) -> str:
    by_type = Counter(r["type"] for r in rows)
    n_e = by_type["entry"]
    n_x = by_type["exit"]
    n_f = by_type["filter"]
    n_r = by_type["risk"]
    n_c = by_type["cross_channel"]
    n_t = len(TIMING_DELAYS)

    # Realistic combo: entry × timing × (1 filter) × exit × (1 risk)
    # Ignore cross_channel (it's an entry-replacement, not a stack).
    combos_min = n_e * n_t * 1 * n_x * 1
    combos_one_filter_one_risk = n_e * n_t * n_f * n_x * n_r
    combos_with_cc = combos_one_filter_one_risk + (n_c * n_t * n_f * n_x * n_r)

    return f"""
    <h3>Strategy combo-space cardinality estimate</h3>
    <ul>
      <li>Base (entry × timing × exit, no filter/risk variation): <b>{combos_min:,}</b></li>
      <li>Full single-pick (1 filter × 1 risk): <b>{combos_one_filter_one_risk:,}</b></li>
      <li>Plus cross-channel as alt entries: <b>{combos_with_cc:,}</b></li>
      <li>With multi-filter stacking (2 filters): <b>{combos_one_filter_one_risk * n_f:,}</b></li>
    </ul>
    <p>Phase 3 target: <b>1B total evaluations</b> across ~100K well-evaluated unique combos
    × ~100 triggers × ~100 bootstrap. Combo-space is large enough that we never need to
    enumerate all combinations — the loop walks the registry guided by LLM team.</p>
    """


def render_full_table(rows: list[dict]) -> str:
    th = "<tr><th>id</th><th>type</th><th>archetype</th><th>channel</th><th>side</th><th>novel_dim</th><th>notes</th></tr>"
    body = []
    for r in rows:
        body.append(
            "<tr>"
            f"<td>{html.escape(r['id'])}</td>"
            f"<td>{html.escape(r['type'])}</td>"
            f"<td>{html.escape(r['archetype'])}</td>"
            f"<td>{html.escape(r['channel'])}</td>"
            f"<td>{html.escape(r['side'])}</td>"
            f"<td><code>{html.escape(', '.join(r['novel_dim']))}</code></td>"
            f"<td>{html.escape(r['notes'])}</td>"
            "</tr>"
        )
    return f"""
    <details><summary><b>Full archetype list ({len(rows)} entries) — click to expand</b></summary>
    <table border="1" cellpadding="3" style="border-collapse:collapse;font-size:11px;margin-top:8px;">
      {th}
      {"".join(body)}
    </table>
    </details>
    """


def render_html(rows: list[dict], status_map: dict) -> str:
    legend = """
    <p><b>Legend:</b>
      <span style="background:#eeeeee;padding:2px 8px;">untested</span>
      <span style="background:#a5d6a7;padding:2px 8px;">quick_passed</span>
      <span style="background:#4caf50;padding:2px 8px;color:white;">deep_passed</span>
      <span style="background:#ef9a9a;padding:2px 8px;">failed</span>
      <span style="background:#ffd54f;padding:2px 8px;">crashed</span>
    </p>
    """

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>BWE Hypothesis Registry — Coverage Map</title>
<style>
  body {{ font-family: -apple-system, system-ui, sans-serif; margin: 24px; max-width: 1400px; }}
  h1 {{ border-bottom: 2px solid #333; padding-bottom: 6px; }}
  h2 {{ color: #2c5aa0; margin-top: 32px; }}
  h3 {{ color: #555; }}
  table {{ font-size: 12px; }}
  td, th {{ border: 1px solid #ccc; }}
  details summary {{ cursor: pointer; padding: 6px; background: #f0f0f0; }}
</style>
</head>
<body>
  <h1>BWE Hypothesis Registry — Coverage Map</h1>
  <p>Source: <code>{REGISTRY_PATH}</code> | Combo status: <code>{COMBO_REGISTRY_PATH if COMBO_REGISTRY_PATH.exists() else "(not yet generated — Phase 2 will populate)"}</code></p>
  {legend}

  <h2>1. Summary</h2>
  {render_per_type_summary(rows)}

  <h2>2. Entry channel × side breakdown</h2>
  {render_channel_side_breakdown(rows)}

  <h2>3. Combo-space cardinality</h2>
  {render_combo_space_estimate(rows)}

  <h2>4. Coverage heatmaps</h2>
  {render_2d_heatmap(rows, col_type="exit", row_type="entry", status_map=status_map)}
  {render_2d_heatmap(rows, col_type="filter", row_type="entry", status_map=status_map)}

  <h2>5. Full archetype list</h2>
  {render_full_table(rows)}
</body>
</html>"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry", type=str, default=str(REGISTRY_PATH))
    ap.add_argument("--output", type=str, default=str(OUTPUT_PATH))
    ap.add_argument("--combo-registry", type=str, default=str(COMBO_REGISTRY_PATH))
    args = ap.parse_args()

    rows = load_registry(Path(args.registry))
    status_map = load_combo_status(Path(args.combo_registry))
    page = render_html(rows, status_map)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print(f"Wrote {out} ({len(page):,} bytes)")
    print(f"  archetypes:        {len(rows)}")
    print(f"  combo statuses:    {len(status_map)} (0 = Phase 2 not run yet)")
    print(f"Open in browser: file:///{out.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
