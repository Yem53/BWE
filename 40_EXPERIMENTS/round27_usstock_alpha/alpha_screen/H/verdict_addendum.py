#!/usr/bin/env python3
"""Family H final verdict — appended to results_H.json after the single
pre-registered dev->val run (no re-fitting; this block only interprets)."""
import json

ROOT = "/Volumes/T9/BWE/40_EXPERIMENTS/round27_usstock_alpha"
o = json.load(open(f"{ROOT}/alpha_screen/H/results_H.json"))

o["diag_val_d1_by_batch"] = {
    "2026-06-01": 2.87, "2026-06-03": -0.56, "2026-06-08": -2.86,
    "2026-06-09": -1.66, "2026-06-10": 1.24, "2026-06-11": -1.47,
    "note": "val day1 raw mean -0.51%, 4/6 batches negative (dev: 14/17 negative)",
}

o["final_verdict"] = {
    "survivor": False,
    "reason": (
        "Permutation search-null kills the headline: best cell WIN|raw|e0|h1 "
        "|t_clust|=3.35 sits at p=0.246 in the null max-|t| distribution of the "
        "same 27-cell grid on placebo anchors (null median max-|t|=2.79, p90=4.00) "
        "— a grid this size 'finds' t=3.3 a quarter of the time. Caveat: null grid "
        "had only 10 batches vs 17 real (fewer clusters => fatter t) so the test is "
        "conservative, but family-E precedent (1/3 null prob => downgraded) applies. "
        "Val: day2-bounce candidates FLIPPED sign (dead); day1-short cells kept sign "
        "but val t only -0.6..-1.3 and val net at stress just +0.28%."
    ),
    "what_is_real": (
        "Direction-consistent structure worth a forward monitor: new equity perps "
        "list long-crowded (day0-2 funding +0.035%/8h = 5x mature +0.007%, sign not "
        "magnitude is the anomaly) and the day0-close premium decays on day1 "
        "(dev -1.73% raw, 14/17 batches negative; val -0.51%, 4/6 negative; resid "
        "version same sign both periods; short nets positive after 1.5x thin-book "
        "costs in BOTH periods: dev +1.51%, val +0.28%, funding tailwind included). "
        "No listing volume pump exists (day0 qv = 0.63x mature median — opposite of "
        "crypto listings); amplitude normalizes by day3."
    ),
    "frozen_forward_rule": {
        "name": "H_list_d1_short_v1",
        "status": "forward-monitor only (NOT tradable claim); same tier as E_afterhours_drift_v1",
        "event": "any new Binance US-stock perp listing (first kline day)",
        "entry": "short at day0 16:00 ET RTH close",
        "exit": "day1 16:00 ET RTH close (next trading day)",
        "costs": "0.18% RT (taker 0.08 + 5bp/side thin book); short collects the positive early funding",
        "forward_pass_gate": "n>=15 listings: net mean > 0 at 1.5x cost AND >=60% of listing batches day1-negative",
        "kill": "n>=10 and net <= 0, or early-funding sign regime flips negative",
        "first_forward_sample": "18 listings 2026-06-22..07-02 (3 batches) already in holdout — never touched here, evaluable by the forward recorder",
    },
}
json.dump(o, open(f"{ROOT}/alpha_screen/H/results_H.json", "w"), indent=1)
print("verdict appended: survivor =", o["final_verdict"]["survivor"])
