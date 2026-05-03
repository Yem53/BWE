"""Rescore the 20K loop's results with the new v2 metrics.

The loop stored only the LEGACY p25 score in results.tsv. To find the TRUE
winners, we need to re-evaluate each (entry_id, best_tp, best_sl, exit_family)
candidate and compute all 4 metrics on the same net_returns tensor.

For each unique (entry, exit_family) pair, re-run a single-variant eval at
the recorded best_tp/best_sl/hold, then compute legacy p25 + mean + Kelly +
p25_capped_tail. Sort by Kelly to find archetypes that would actually
compound capital positively.

Output: H:/BWE/40_EXPERIMENTS/analysis/rescore_<ts>/
  - rescore_v2.csv (one row per candidate, all 4 metrics + paper-shadow proxy)
  - top_by_metric.md (top 20 ranked by each of the 4 metrics, side-by-side)

Runtime: ~1 sec per candidate × ~2000 candidates ≈ 30 min. Run once after loop.

Usage:
    python scripts/rescore_with_v2.py
    python scripts/rescore_with_v2.py --top-n 30  # show top 30 per metric
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import torch

from bwe_autoresearch.bwe_loop import (
    Combo, load_events_for_combo, load_registry,
)
from bwe_autoresearch.bwe_loop_gpu_eval import (
    EventBatch, VariantGrid, batch_eval, get_device,
)
from bwe_autoresearch.bwe_loop_exit_kernels import (
    classify_exit_family,
    eval_breakeven, eval_multi_tp_50_50, eval_time_only, eval_trailing_pct,
)
from bwe_autoresearch.bwe_loop_score_metric import batch_score_oos_p25_pct
from bwe_autoresearch.bwe_loop_score_v2 import (
    batch_score_mean_net_pct,
    batch_score_kelly_fraction_pct,
    batch_score_p25_capped_tail,
)


from bwe_autoresearch.bwe_paths import (  # noqa: E402
    ANALYSIS_DIR as ANALYSIS_BASE,
    RESULTS_TSV,
)


def _route_eval(family: str, events, variants, cost_pct, device):
    if family == "time_only":
        return eval_time_only(events.to(device), variants.to(device), cost_pct, variant_chunk=8192)
    if family == "breakeven":
        return eval_breakeven(events.to(device), variants.to(device), cost_pct, variant_chunk=8192)
    if family == "trail":
        return eval_trailing_pct(events.to(device), variants.to(device), cost_pct, variant_chunk=8192)
    if family == "multi_tp":
        return eval_multi_tp_50_50(events.to(device), variants.to(device), cost_pct, variant_chunk=8192)
    return batch_eval(events, variants, cost_pct=cost_pct, device=device, variant_chunk=8192)


def _read_results():
    rows = []
    if not RESULTS_TSV.exists():
        return rows
    text = RESULTS_TSV.read_text(encoding="utf-8")
    ENT = re.compile(r"E=(\w+)/")
    EXT = re.compile(r"X=(\w+)/(\S+)")
    TP = re.compile(r"best_tp=([\d.]+)")
    SL = re.compile(r"best_sl=([\d.]+)")
    for line in text.splitlines()[1:]:
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        try:
            score_legacy = float(parts[1])
            triggers = int(parts[2])
        except ValueError:
            continue
        if parts[3] not in ("keep", "discard"):
            continue
        em = ENT.search(parts[4])
        xm = EXT.search(parts[4])
        if not em or not xm:
            continue
        m_tp = TP.search(parts[4])
        m_sl = SL.search(parts[4])
        if not m_tp or not m_sl:
            continue
        rows.append({
            "entry_id": em.group(1),
            "exit_id": xm.group(1),
            "exit_archetype": xm.group(2).rstrip("|").rstrip(),
            "exit_family": classify_exit_family(xm.group(2).rstrip("|").rstrip()),
            "best_tp": float(m_tp.group(1)),
            "best_sl": float(m_sl.group(1)),
            "triggers": triggers,
            "score_legacy_p25": score_legacy,
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top-n", type=int, default=20)
    ap.add_argument("--max-candidates", type=int, default=None,
                    help="Limit how many to rescore (default: all)")
    ap.add_argument("--cost-pct", type=float, default=0.08)
    ap.add_argument("--hold", type=int, default=15)
    args = ap.parse_args()

    rows = _read_results()
    if not rows:
        print(f"FATAL: no rows in {RESULTS_TSV}")
        return 1
    if args.max_candidates:
        rows = rows[: args.max_candidates]
    print(f"Read {len(rows)} candidate rows from results.tsv")

    registry_list = load_registry()
    registry = {r["id"]: r for r in registry_list}
    device = get_device()
    print(f"Device: {device}")

    out_rows = []
    t0 = time.time()
    for i, r in enumerate(rows):
        if i % 50 == 0:
            elapsed = time.time() - t0
            rate = i / max(elapsed, 0.001)
            eta_s = (len(rows) - i) / max(rate, 0.001)
            print(f"  [{i}/{len(rows)}] rate={rate:.1f}/s eta={eta_s/60:.1f}min", flush=True)

        e = registry.get(r["entry_id"])
        if e is None:
            continue
        combo = Combo(
            entry_id=r["entry_id"], exit_id=r["exit_id"],
            entry_archetype=e["archetype"], exit_archetype=r["exit_archetype"],
            channel=e["channel"], side=e["side"],
            novel_dim=tuple(e.get("novel_dim", [])),
        )
        events = load_events_for_combo(combo)
        if events is None:
            continue

        variants = VariantGrid.from_numpy(
            np.array([r["best_tp"]], dtype=np.float32),
            np.array([r["best_sl"]], dtype=np.float32),
            np.array([args.hold], dtype=np.int16),
        )

        try:
            net_returns = _route_eval(r["exit_family"], events, variants, args.cost_pct, device)
            # net_returns: [N_events, 1]
            score_legacy = float(batch_score_oos_p25_pct(net_returns).cpu().numpy()[0])
            score_mean = float(batch_score_mean_net_pct(net_returns).cpu().numpy()[0])
            score_kelly = float(batch_score_kelly_fraction_pct(net_returns).cpu().numpy()[0])
            score_p25c = float(batch_score_p25_capped_tail(net_returns).cpu().numpy()[0])

            # Quick paper-shadow proxy: walk through trades, compound 7.5% capital
            rets = net_returns.cpu().numpy().ravel()
            rets = rets[~np.isnan(rets)]
            cap = 1000.0
            peak = cap
            max_dd = 0.0
            wins = (rets > 0).sum()
            for ret in rets:
                size = cap * 0.075
                cap += size * (ret / 100.0)
                peak = max(peak, cap)
                dd = (peak - cap) / peak
                max_dd = max(max_dd, dd)
            paper_final_pct = (cap / 1000.0 - 1) * 100
            paper_max_dd_pct = max_dd * 100
        except Exception as ex:
            print(f"  ERROR rescoring {r['entry_id']}/{r['exit_id']}: {ex}")
            continue

        out_rows.append({
            **r,
            "channel": e["channel"],
            "side": e["side"],
            "entry_archetype": e["archetype"],
            "novel_dim": "; ".join(e.get("novel_dim", []))[:140],
            "score_legacy_p25_v2": score_legacy,  # recomputed (should match results.tsv)
            "score_mean": score_mean,
            "score_kelly_pct": score_kelly,
            "score_p25_capped_tail": score_p25c,
            "paper_final_pct": paper_final_pct,
            "paper_max_dd_pct": paper_max_dd_pct,
            "paper_win_rate": wins / max(len(rets), 1) * 100,
        })

    elapsed = time.time() - t0
    print(f"Rescored {len(out_rows)} candidates in {elapsed/60:.1f} min")

    if not out_rows:
        print("No candidates successfully rescored.")
        return 1

    # Output dir
    out_dir = ANALYSIS_BASE / f"rescore_{time.strftime('%Y%m%d_%H%M%S')}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # CSV
    cols = [
        "entry_id", "entry_archetype", "channel", "side", "novel_dim",
        "exit_id", "exit_archetype", "exit_family", "best_tp", "best_sl", "triggers",
        "score_legacy_p25", "score_legacy_p25_v2", "score_mean", "score_kelly_pct",
        "score_p25_capped_tail", "paper_final_pct", "paper_max_dd_pct", "paper_win_rate",
    ]
    with (out_dir / "rescore_v2.csv").open("w", encoding="utf-8") as f:
        f.write(",".join(cols) + "\n")
        for r in out_rows:
            f.write(",".join(str(r.get(c, "")).replace(",", ";") for c in cols) + "\n")
    print(f"Saved CSV: {out_dir / 'rescore_v2.csv'}")

    # MD report: top N by each metric, side-by-side
    metrics = [
        ("score_legacy_p25", "p25 (legacy, BUGGY — selects TRAP)"),
        ("score_mean",       "mean per-trade %"),
        ("score_kelly_pct",  "Kelly fraction % (capped 10)"),
        ("score_p25_capped_tail", "p25 with tail penalty"),
        ("paper_final_pct",  "PAPER REPLAY final % ($1000 → ?)"),
    ]
    md = [f"# Rescore (v2) — {time.strftime('%Y-%m-%d %H:%M:%S')}\n"]
    md.append(f"- Rescored: {len(out_rows)} candidates")
    md.append(f"- Elapsed: {elapsed/60:.1f} min on {device}\n")
    for col, label in metrics:
        sorted_rows = sorted(out_rows, key=lambda x: x.get(col, -1e9), reverse=True)
        md.append(f"\n## Top {args.top_n} by {label}\n")
        md.append("| # | entry_id | archetype | exit_family | TP | SL | trig | metric | paper% | paperDD% | win% |")
        md.append("|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|")
        for i, r in enumerate(sorted_rows[: args.top_n], 1):
            md.append(
                f"| {i} | {r['entry_id']} | {r['entry_archetype'][:30]} | "
                f"{r['exit_family']} | {r['best_tp']:.2f} | {r['best_sl']:.2f} | "
                f"{r['triggers']} | {r.get(col, 0):+.4f} | "
                f"{r['paper_final_pct']:+.2f} | {r['paper_max_dd_pct']:.2f} | "
                f"{r['paper_win_rate']:.1f} |"
            )
    md_path = out_dir / "top_by_metric.md"
    md_path.write_text("\n".join(md), encoding="utf-8")
    print(f"Saved MD:  {md_path}")

    # Quick console summary: top 5 by Kelly
    print("\n=== TOP 5 by Kelly (probably the most actionable) ===")
    kelly_sorted = sorted(out_rows, key=lambda x: x["score_kelly_pct"], reverse=True)
    for i, r in enumerate(kelly_sorted[:5], 1):
        print(f"  {i}. {r['entry_id']:6s} {r['entry_archetype'][:30]:30s} "
              f"{r['exit_family']:9s} TP={r['best_tp']:.2f} SL={r['best_sl']:.2f} "
              f"kelly={r['score_kelly_pct']:.2f}% paper={r['paper_final_pct']:+.2f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
