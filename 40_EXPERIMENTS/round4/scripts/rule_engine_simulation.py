"""Simulate the 7-rule engine on historical 281 waves.

Compare:
  1. Rule Engine v1 (7 rules, FADE 5/8% + FOLLOW 5%)
  2. Always FADE 5% (current default)
  3. Always FADE 8% (aggressive baseline)
  4. Always FOLLOW 5%
  5. No-skip rules (rule engine without A/E/F skips)
  6. Per-rule contribution breakdown

Output: total capital PnL, win rate, trade rate, rule trigger distribution.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

DIVE = Path("/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits/yaobi_per_symbol_dive.json")


def collect_waves(data):
    rows = []
    for r in data["results"]:
        for w in r["waves"]:
            if w["fade_v2"] is None or w["follow_v2"] is None:
                continue
            rows.append({
                "symbol": r["symbol"],
                "score": r["score"],
                "lifecycle": r["lifecycle"],
                "reaction": r["reaction"],
                "n_waves_14d": r["n_waves"],
                "duration": w["duration_min"],
                "pre_vol": w["pre_vol_x"],
                "magnitude": abs(w["peak_ret"]),
                "peak_sign": "pump" if w["peak_ret"] > 0 else "dump",
                "fade_pnl": w["fade_v2"],
                "follow_pnl": w["follow_v2"],
            })
    return rows


def apply_rules(w):
    """v1.1 — Rule F conditional (only FOLLOW if late_burst, else SKIP)."""
    if w["n_waves_14d"] < 3:
        return ("SKIP", 0, "A", "insufficient_history")
    if w["reaction"] == "trend_continue" and 3 <= w["duration"] <= 20:
        return ("FOLLOW", 5, "B", "trend_continue_window")
    if w["reaction"] == "mean_revert" and w["lifecycle"] in ("sustained", "single_burst"):
        return ("FADE", 8, "C", "prime_fade")
    if w["score"] >= 80 and w["pre_vol"] < 2.5:
        return ("FADE", 8, "D", "high_score_low_prevol")
    if 3 <= w["duration"] <= 6:
        return ("SKIP", 0, "E", "fade_dead_zone")
    # Rule F (v1.1 conditional)
    if w["pre_vol"] >= 7.0:
        if w["lifecycle"] == "late_burst":
            return ("FOLLOW", 5, "F1", "high_prevol_late_burst_follow")
        return ("SKIP", 0, "F2", "high_prevol_uncertain_skip")
    return ("FADE", 5, "G", "default_fade")


def apply_rules_v1_old(w):
    """v1 — Rule F unconditional FOLLOW (the original)."""
    if w["n_waves_14d"] < 3:
        return ("SKIP", 0, "A", "insufficient_history")
    if w["reaction"] == "trend_continue" and 3 <= w["duration"] <= 20:
        return ("FOLLOW", 5, "B", "trend_continue_window")
    if w["reaction"] == "mean_revert" and w["lifecycle"] in ("sustained", "single_burst"):
        return ("FADE", 8, "C", "prime_fade")
    if w["score"] >= 80 and w["pre_vol"] < 2.5:
        return ("FADE", 8, "D", "high_score_low_prevol")
    if 3 <= w["duration"] <= 6:
        return ("SKIP", 0, "E", "fade_dead_zone")
    if w["pre_vol"] >= 7.0:
        return ("FOLLOW", 5, "F", "high_prevol_follow")
    return ("FADE", 5, "G", "default_fade")


def apply_rules_v1_skip(w):
    """v1-skip variant — Rule F skip everything (the safe original baseline)."""
    if w["n_waves_14d"] < 3:
        return ("SKIP", 0, "A", "insufficient_history")
    if w["reaction"] == "trend_continue" and 3 <= w["duration"] <= 20:
        return ("FOLLOW", 5, "B", "trend_continue_window")
    if w["reaction"] == "mean_revert" and w["lifecycle"] in ("sustained", "single_burst"):
        return ("FADE", 8, "C", "prime_fade")
    if w["score"] >= 80 and w["pre_vol"] < 2.5:
        return ("FADE", 8, "D", "high_score_low_prevol")
    if 3 <= w["duration"] <= 6:
        return ("SKIP", 0, "E", "fade_dead_zone")
    if w["pre_vol"] >= 7.0:
        return ("SKIP", 0, "F", "high_prevol_skip")
    return ("FADE", 5, "G", "default_fade")


def simulate(rows, decision_fn, label):
    decisions = []
    for w in rows:
        action, pct, rid, reason = decision_fn(w)
        if action == "SKIP":
            raw_pnl = 0
            cap_pnl = 0
        else:
            raw_pnl = w["fade_pnl"] if action == "FADE" else w["follow_pnl"]
            cap_pnl = raw_pnl * pct / 100
        decisions.append({
            "wave": w, "action": action, "pos_pct": pct, "rule": rid,
            "reason": reason, "raw_pnl": raw_pnl, "cap_pnl": cap_pnl,
        })
    return label, decisions


def aggregate(label, decisions):
    n = len(decisions)
    n_skip = sum(1 for d in decisions if d["action"] == "SKIP")
    n_trade = n - n_skip
    cap_pnls = [d["cap_pnl"] for d in decisions]
    raw_pnls_traded = [d["raw_pnl"] for d in decisions if d["action"] != "SKIP"]
    wins = sum(1 for p in raw_pnls_traded if p > 0)
    big_wins = sum(1 for p in raw_pnls_traded if p >= 10)
    catastrophes = sum(1 for p in raw_pnls_traded if p <= -15)

    return {
        "label": label,
        "total_waves": n,
        "n_skip": n_skip,
        "n_trade": n_trade,
        "trade_rate_pct": n_trade / n * 100 if n else 0,
        "total_capital_pnl_pct": sum(cap_pnls),
        "mean_cap_pnl_per_trade": sum(cap_pnls) / n_trade if n_trade else 0,
        "win_rate_traded": wins / n_trade * 100 if n_trade else 0,
        "mean_raw_pnl_traded": sum(raw_pnls_traded) / n_trade if n_trade else 0,
        "best_raw": max(raw_pnls_traded) if raw_pnls_traded else 0,
        "worst_raw": min(raw_pnls_traded) if raw_pnls_traded else 0,
        "big_wins_10pct": big_wins,
        "catastrophes_15pct": catastrophes,
    }


def main():
    data = json.loads(DIVE.read_text())
    rows = collect_waves(data)
    print(f"Total waves with full data: {len(rows)}")
    print()

    sims = []
    sims.append(simulate(rows, apply_rules, "Rule Engine v1.1 (F cond)"))
    sims.append(simulate(rows, apply_rules_v1_old, "Rule Engine v1 (F=FOLLOW)"))
    sims.append(simulate(rows, apply_rules_v1_skip, "Rule Engine v1 (F=SKIP)"))
    sims.append(simulate(rows, lambda w: ("FADE", 5, "X", "always_fade_5"),
                         "Always FADE 5%"))
    sims.append(simulate(rows, lambda w: ("FADE", 8, "X", "always_fade_8"),
                         "Always FADE 8%"))
    sims.append(simulate(rows, lambda w: ("FOLLOW", 5, "X", "always_follow_5"),
                         "Always FOLLOW 5%"))

    # No-skip variant: apply rule engine but don't skip (force fade if A/E/F triggered)
    def no_skip_rules(w):
        action, pct, rid, reason = apply_rules(w)
        if action == "SKIP":
            return ("FADE", 5, rid + "_forced", "forced_fade_no_skip")
        return action, pct, rid, reason
    sims.append(simulate(rows, no_skip_rules, "Rule Engine (no SKIPs)"))

    # Random control: skip 50% randomly
    import random
    random.seed(42)
    def rand_skip(w):
        if random.random() < 0.5:
            return ("SKIP", 0, "X", "random_skip")
        return ("FADE", 5, "X", "random_fade")
    sims.append(simulate(rows, rand_skip, "Random skip 50% + FADE"))

    # Print summary table
    print("=" * 130)
    print(f"{'strategy':30s} {'waves':>6s} {'skip':>5s} {'trade':>6s} {'trade%':>7s} "
          f"{'tot_cap':>10s} {'mean_cap':>10s} {'win%':>6s} {'best_raw':>9s} {'worst_raw':>10s} "
          f"{'big_w':>6s} {'cat':>4s}")
    print("-" * 130)
    for label, decisions in sims:
        agg = aggregate(label, decisions)
        print(f"  {agg['label']:28s} {agg['total_waves']:>6d} {agg['n_skip']:>5d} "
              f"{agg['n_trade']:>6d} {agg['trade_rate_pct']:>6.1f}% "
              f"{agg['total_capital_pnl_pct']:>+9.2f}% "
              f"{agg['mean_cap_pnl_per_trade']:>+9.3f}% "
              f"{agg['win_rate_traded']:>5.1f}% "
              f"{agg['best_raw']:>+8.1f}% {agg['worst_raw']:>+9.1f}% "
              f"{agg['big_wins_10pct']:>6d} {agg['catastrophes_15pct']:>4d}")

    # Per-rule breakdown for Rule Engine v1
    print()
    print("=" * 100)
    print("Rule Engine v1 — per-rule contribution")
    print("=" * 100)
    rule_eng_decisions = sims[0][1]
    by_rule = defaultdict(list)
    for d in rule_eng_decisions:
        by_rule[d["rule"]].append(d)

    rule_descriptions = {
        "A": "n_waves<3 → SKIP",
        "B": "trend_continue+dur 3-20 → FOLLOW 5%",
        "C": "mean_revert+sustained/single_burst → FADE 8%",
        "D": "score≥80+pre_vol<2.5 → FADE 8%",
        "E": "duration 3-6 → SKIP (dead zone)",
        "F": "pre_vol≥7x → FOLLOW 5%",
        "G": "default → FADE 5%",
    }

    print(f"{'rule':5s} {'n':>4s} {'%':>5s} {'action':>7s} {'tot_cap':>9s} "
          f"{'mean_raw':>9s} {'win%':>6s}  desc")
    print("-" * 100)
    total_n = len(rule_eng_decisions)
    total_cap = 0
    for rid in "ABCDEFG":
        sub = by_rule.get(rid, [])
        if not sub:
            print(f"  {rid:3s} {0:>4d} {0:>4.1f}% (rule did not trigger)")
            continue
        n = len(sub)
        action = sub[0]["action"]
        pos_pct = sub[0]["pos_pct"]
        cap_total = sum(d["cap_pnl"] for d in sub)
        total_cap += cap_total
        traded = [d for d in sub if d["action"] != "SKIP"]
        if traded:
            wins = sum(1 for d in traded if d["raw_pnl"] > 0)
            wr = wins / len(traded) * 100
            mean_raw = sum(d["raw_pnl"] for d in traded) / len(traded)
        else:
            wr = 0; mean_raw = 0
        print(f"  {rid:3s} {n:>4d} {n/total_n*100:>4.1f}% {action+'/'+str(pos_pct)+'%':>9s} "
              f"{cap_total:>+8.2f}% {mean_raw:>+8.2f}% {wr:>5.1f}%  {rule_descriptions[rid]}")
    print(f"  {'TOTAL':5s} {total_n:>4d} 100.0% {'':>9s} {total_cap:>+8.2f}%")

    # By symbol — show top winning + losing symbols
    print()
    print("=" * 90)
    print("Per-symbol Rule Engine v1 PnL (top 20 win / bottom 10 lose)")
    print("=" * 90)
    by_sym = defaultdict(list)
    for d in rule_eng_decisions:
        by_sym[d["wave"]["symbol"]].append(d)
    sym_summary = []
    for sym, ds in by_sym.items():
        n = len(ds)
        n_trade = sum(1 for d in ds if d["action"] != "SKIP")
        cap_total = sum(d["cap_pnl"] for d in ds)
        sym_summary.append({
            "symbol": sym, "n": n, "n_trade": n_trade,
            "cap_pnl": cap_total,
            "rules_used": Counter(d["rule"] for d in ds),
        })
    sym_summary.sort(key=lambda x: -x["cap_pnl"])
    print(f"{'symbol':14s} {'n_waves':>8s} {'n_trade':>8s} {'cap_pnl':>9s}  rule_mix")
    for s in sym_summary[:20]:
        print(f"  {s['symbol']:12s} {s['n']:>8d} {s['n_trade']:>8d} "
              f"{s['cap_pnl']:>+8.2f}%  {dict(s['rules_used'])}")
    print(f"\n  ... bottom 10 (losers):")
    for s in sym_summary[-10:]:
        print(f"  {s['symbol']:12s} {s['n']:>8d} {s['n_trade']:>8d} "
              f"{s['cap_pnl']:>+8.2f}%  {dict(s['rules_used'])}")

    # Save
    out = Path("/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits/rule_engine_simulation.json")
    out.write_text(json.dumps({
        "comparison": {label: aggregate(label, decisions)
                        for label, decisions in sims},
        "by_symbol": sym_summary[:50],
    }, indent=2, default=str))
    print(f"\n  saved: {out}")


if __name__ == "__main__":
    main()
