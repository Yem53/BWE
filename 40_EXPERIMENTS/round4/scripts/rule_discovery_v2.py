"""Data-driven rule discovery — let the data tell us what rules should exist.

NO pre-committed rules. We:
  1. Collect all 281 waves with their features
  2. For each feature individually, find which value-buckets best predict win
  3. For each pair of features, find conjunctions that strongly predict win
  4. Try sklearn decision tree (if available) for global structure
  5. Output the top discovered rules sorted by lift × support

The goal is rules that emerge from the data, not rules I imagined.
"""
from __future__ import annotations

import json
import sys
from itertools import combinations
from pathlib import Path

DIVE_PATH = Path("/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits/yaobi_per_symbol_dive_v1_30d.json")
OUT_PATH = Path("/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits/rule_discovery_v1_30d.json")


def collect_waves(data):
    """Each wave becomes a labeled row.

    Features (categorical):  lifecycle, reaction, peak_sign, score_bucket,
                             pre_vol_bucket, duration_bucket, magnitude_bucket
    Labels:                  fade_win (bool), follow_win (bool),
                             fade_pnl, follow_pnl
    """
    rows = []
    for r in data["results"]:
        score = r["score"]
        lifecycle = r["lifecycle"]
        reaction = r["reaction"]
        for w in r["waves"]:
            if w["fade_v2"] is None or w["follow_v2"] is None:
                continue
            peak = w["peak_ret"]
            row = {
                "symbol": r["symbol"],
                # Continuous features → bucketed
                "score_bucket": bucket(score, [50, 60, 70, 80]),
                "pre_vol_bucket": bucket(w["pre_vol_x"], [1.5, 2.5, 4.0, 7.0]),
                "duration_bucket": bucket(w["duration_min"], [3, 6, 10, 20]),
                "magnitude_bucket": bucket(abs(peak), [10, 15, 20, 30]),
                # Categorical features
                "lifecycle": lifecycle,
                "reaction": reaction,
                "peak_sign": "pump" if peak > 0 else "dump",
                # Outcomes
                "fade_pnl": w["fade_v2"],
                "follow_pnl": w["follow_v2"],
                "fade_win": w["fade_v2"] > 0,
                "follow_win": w["follow_v2"] > 0,
            }
            rows.append(row)
    return rows


def bucket(v, edges):
    """Map value to a bucket label like '<10', '10-20', '20-30', '>=30'."""
    if v < edges[0]:
        return f"<{edges[0]}"
    for i in range(len(edges) - 1):
        if edges[i] <= v < edges[i + 1]:
            return f"{edges[i]}-{edges[i+1]}"
    return f">={edges[-1]}"


def metric(rows, label_field):
    n = len(rows)
    if n == 0:
        return None
    wins = sum(1 for r in rows if r[label_field])
    pnls = [r["fade_pnl" if label_field == "fade_win" else "follow_pnl"] for r in rows]
    return {
        "n": n,
        "win_rate": wins / n * 100,
        "mean_pnl": sum(pnls) / n,
        "total_pnl": sum(pnls),
    }


def lift(sub_metric, baseline_metric):
    """How much better is this subset vs baseline?"""
    if sub_metric is None or baseline_metric is None or baseline_metric["win_rate"] == 0:
        return 0
    return sub_metric["win_rate"] / baseline_metric["win_rate"]


def discover_single_feature(rows, feature, target):
    baseline = metric(rows, target)
    print(f"\n  baseline ({target}): n={baseline['n']}  win={baseline['win_rate']:.1f}%  "
          f"mean_pnl={baseline['mean_pnl']:+.2f}%")

    values = sorted(set(r[feature] for r in rows))
    discovered = []
    for v in values:
        sub = [r for r in rows if r[feature] == v]
        m = metric(sub, target)
        if m["n"] < 5:
            continue
        L = lift(m, baseline)
        discovered.append({
            "rule": f"{feature} == '{v}'",
            "n": m["n"], "win_rate": m["win_rate"],
            "mean_pnl": m["mean_pnl"], "lift": L,
            "delta_winrate_vs_baseline": m["win_rate"] - baseline["win_rate"],
        })
    discovered.sort(key=lambda x: -x["delta_winrate_vs_baseline"])
    return discovered


def discover_pair_features(rows, features, target, min_n=5):
    baseline = metric(rows, target)
    discovered = []
    for f1, f2 in combinations(features, 2):
        v1s = sorted(set(r[f1] for r in rows))
        v2s = sorted(set(r[f2] for r in rows))
        for v1 in v1s:
            for v2 in v2s:
                sub = [r for r in rows if r[f1] == v1 and r[f2] == v2]
                m = metric(sub, target)
                if m is None or m["n"] < min_n:
                    continue
                discovered.append({
                    "rule": f"{f1}=='{v1}' AND {f2}=='{v2}'",
                    "n": m["n"], "win_rate": m["win_rate"],
                    "mean_pnl": m["mean_pnl"],
                    "delta_winrate_vs_baseline": m["win_rate"] - baseline["win_rate"],
                })
    discovered.sort(key=lambda x: -x["delta_winrate_vs_baseline"])
    return discovered


def try_decision_tree(rows, target):
    try:
        from sklearn.tree import DecisionTreeClassifier, export_text
        from sklearn.preprocessing import LabelEncoder
    except ImportError:
        return None

    features = ["score_bucket", "pre_vol_bucket", "duration_bucket",
                "magnitude_bucket", "lifecycle", "reaction", "peak_sign"]
    encoders = {f: LabelEncoder() for f in features}
    X = []
    for r in rows:
        encoded = []
        for f in features:
            encoders[f].fit([row[f] for row in rows])
            encoded.append(encoders[f].transform([r[f]])[0])
        X.append(encoded)
    y = [1 if r[target] else 0 for r in rows]

    tree = DecisionTreeClassifier(max_depth=4, min_samples_leaf=10,
                                   class_weight="balanced", random_state=42)
    tree.fit(X, y)

    # Export with feature names
    feat_names = features
    text = export_text(tree, feature_names=feat_names, max_depth=4)
    return text


def main():
    data = json.loads(DIVE_PATH.read_text())
    rows = collect_waves(data)
    print(f"Collected {len(rows)} waves with full feature + outcome data")

    features = ["score_bucket", "pre_vol_bucket", "duration_bucket",
                "magnitude_bucket", "lifecycle", "reaction", "peak_sign"]

    # Q1: Should we fade or follow? Single-feature scan
    print()
    print("=" * 100)
    print("DISCOVERY 1 — single-feature predictors of FADE win")
    print("=" * 100)
    for f in features:
        print(f"\n  >>> feature: {f}")
        d = discover_single_feature(rows, f, "fade_win")
        for x in d[:6]:
            print(f"    {x['rule']:50s}  n={x['n']:>3d}  win={x['win_rate']:>5.1f}%  "
                  f"Δwin={x['delta_winrate_vs_baseline']:+5.1f}pp  mean_pnl={x['mean_pnl']:+5.2f}%")

    print()
    print("=" * 100)
    print("DISCOVERY 2 — single-feature predictors of FOLLOW win")
    print("=" * 100)
    for f in features:
        print(f"\n  >>> feature: {f}")
        d = discover_single_feature(rows, f, "follow_win")
        for x in d[:6]:
            print(f"    {x['rule']:50s}  n={x['n']:>3d}  win={x['win_rate']:>5.1f}%  "
                  f"Δwin={x['delta_winrate_vs_baseline']:+5.1f}pp  mean_pnl={x['mean_pnl']:+5.2f}%")

    # Q2: pair-feature scan
    print()
    print("=" * 100)
    print("DISCOVERY 3 — TOP 15 pair-feature conjunctions for FADE win (n≥10)")
    print("=" * 100)
    d = discover_pair_features(rows, features, "fade_win", min_n=10)
    baseline_fade = metric(rows, "fade_win")
    print(f"\n  baseline fade_win = {baseline_fade['win_rate']:.1f}%, mean_pnl = {baseline_fade['mean_pnl']:+.2f}%")
    for x in d[:15]:
        print(f"  {x['rule']:60s}  n={x['n']:>3d}  win={x['win_rate']:>5.1f}%  "
              f"Δwin={x['delta_winrate_vs_baseline']:+5.1f}pp  mean_pnl={x['mean_pnl']:+5.2f}%")

    print()
    print("=" * 100)
    print("DISCOVERY 4 — TOP 15 pair-feature conjunctions for FOLLOW win (n≥5)")
    print("=" * 100)
    d2 = discover_pair_features(rows, features, "follow_win", min_n=5)
    baseline_follow = metric(rows, "follow_win")
    print(f"\n  baseline follow_win = {baseline_follow['win_rate']:.1f}%, mean_pnl = {baseline_follow['mean_pnl']:+.2f}%")
    for x in d2[:15]:
        print(f"  {x['rule']:60s}  n={x['n']:>3d}  win={x['win_rate']:>5.1f}%  "
              f"Δwin={x['delta_winrate_vs_baseline']:+5.1f}pp  mean_pnl={x['mean_pnl']:+5.2f}%")

    # Decision tree
    print()
    print("=" * 100)
    print("DISCOVERY 5 — sklearn decision tree (FADE win)")
    print("=" * 100)
    tree_text = try_decision_tree(rows, "fade_win")
    if tree_text:
        print(tree_text)
    else:
        print("  (sklearn not available, skipping)")

    print()
    print("=" * 100)
    print("DISCOVERY 6 — sklearn decision tree (FOLLOW win)")
    print("=" * 100)
    tree_text2 = try_decision_tree(rows, "follow_win")
    if tree_text2:
        print(tree_text2)

    OUT_PATH.write_text(json.dumps({
        "n_waves": len(rows),
        "baseline_fade_win": baseline_fade["win_rate"],
        "baseline_follow_win": baseline_follow["win_rate"],
        "single_fade": discover_single_feature(rows, "lifecycle", "fade_win"),
    }, indent=2, default=str))
    print(f"\n  saved: {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
