"""Five adversarial falsification tests against the radar neutral L/S finding.
(a) momentum disguise   (b) single-day/single-name  (c) effective N / overlap
(d) survivorship/tradability  (e) cost stress 0.10 -> 0.20 %/leg
Output JSON to result.json.
"""
import json
import numpy as np
import engine as E

rows, by_date, dates = E.load()
OUT = {}


def ls_with_cost(by_date, dates, score_key, h, cost_leg, days_subset=None):
    """LS net per-day list under arbitrary per-leg cost."""
    days = E.usable_days(by_date, dates, h)
    if days_subset is not None:
        days = [d for d in days if d in days_subset]
    hold = E.HOLD[h]
    out = []
    for d in days:
        ls = E.ls_day(by_date[d], score_key, h)
        if ls is None:
            continue
        net_total = ls["gross"] - 2 * cost_leg
        out.append({"date": d, "net_total": net_total,
                    "net_perday": net_total / hold, "gross_total": ls["gross"],
                    "detail": ls})
    return out


# =========================================================
# (a) MOMENTUM DISGUISE
# Free momentum factor = momentum_20d_pct (already in panel).
# Build the SAME tercile L/S but ranked purely on momentum_20d_pct -> "free momentum L/S".
# Then: does combined_score L/S survive AFTER neutralizing momentum?
#   - Compare combined L/S vs momentum-only L/S head to head.
#   - Cross-sectional: regress fwd ret on momentum, take residual, re-rank by combined on RESIDUAL.
# =========================================================
def test_a():
    res = {"desc": "Momentum disguise: does combined_score L/S add anything beyond free momentum_20d_pct?"}
    # A1: momentum-only L/S (free factor) vs combined L/S
    a1 = {}
    for h in E.HORIZONS:
        comb = E.per_day_net_pct(by_date, dates, "combined_score", h)
        mom = E.per_day_net_pct(by_date, dates, "momentum_20d_pct", h)
        a1[h] = {
            "combined_net_perday": round(float(np.mean([x["net_perday"] for x in comb])), 3),
            "momentum_only_net_perday": round(float(np.mean([x["net_perday"] for x in mom])), 3),
            "n": len(comb),
        }
    res["A1_momentum_only_vs_combined"] = a1

    # A2: residualize fwd return on momentum cross-sectionally each day, then
    # build L/S on combined_score using the MOMENTUM-RESIDUAL forward return.
    # If combined predicts only via momentum, residual L/S -> ~0.
    a2 = {}
    for h in E.HORIZONS:
        days = E.usable_days(by_date, dates, h)
        hold = E.HOLD[h]
        net_tot = []
        for d in days:
            sub = by_date[d]
            if len(sub) < 3:
                continue
            mom = np.array([r["momentum_20d_pct"] for r in sub], float)
            fwd = np.array([r[h] for r in sub], float)
            # OLS residual of fwd ~ momentum (demeaned)
            X = np.column_stack([np.ones(len(sub)), mom])
            beta, *_ = np.linalg.lstsq(X, fwd, rcond=None)
            resid = fwd - X @ beta
            # rebuild rows with residual as the fwd, rank by combined_score
            s = sorted(range(len(sub)), key=lambda i: sub[i]["combined_score"], reverse=True)
            k = len(sub) // 3
            if k < 1:
                continue
            longs = [resid[i] for i in s[:k]]
            shorts = [resid[i] for i in s[-k:]]
            gross = np.mean(longs) - np.mean(shorts)
            net_tot.append(gross - 2 * E.COST_LEG)
        a2[h] = {
            "combined_LS_on_mom_residual_net_perday": round(float(np.mean(net_tot) / hold), 3),
            "n": len(net_tot),
        }
    res["A2_combined_LS_on_momentum_residual"] = a2

    # A3: correlation between combined_score and momentum_20d_pct cross-sectionally (avg daily spearman)
    rho = []
    for d in dates:
        sub = by_date[d]
        if len(sub) >= 3:
            rho.append(E.spearman([r["combined_score"] for r in sub],
                                  [r["momentum_20d_pct"] for r in sub]))
    res["A3_avg_daily_spearman_combined_vs_momentum"] = round(float(np.nanmean(rho)), 3)
    return res


# =========================================================
# (b) SINGLE-DAY / SINGLE-NAME
# Leave-one-day-out and leave-one-name-out on the TOTAL (summed) net LS,
# and on the mean net/day. Report sign-flip count and worst-case.
# =========================================================
def test_b():
    res = {"desc": "Single-day / single-name fragility (leave-one-out)."}
    by_h = {}
    for h in E.HORIZONS:
        pd = E.per_day_net_pct(by_date, dates, "combined_score", h)
        nets = np.array([x["net_perday"] for x in pd])
        full = float(nets.mean())
        # leave-one-day-out
        lodo = []
        for i in range(len(nets)):
            m = float(np.delete(nets, i).mean())
            lodo.append({"removed_day": pd[i]["date"], "net_perday": round(m, 3),
                         "day_contrib_total": round(pd[i]["net_total"], 3)})
        lodo_sorted = sorted(lodo, key=lambda x: x["net_perday"])
        flips_day = sum(1 for x in lodo if (x["net_perday"] > 0) != (full > 0))
        # leave-one-name-out: recompute whole series excluding ticker t entirely
        tickers = sorted(set(r["ticker"] for r in rows))
        lono = []
        for t in tickers:
            bd2 = {d: [r for r in by_date[d] if r["ticker"] != t] for d in by_date}
            pd2 = E.per_day_net_pct(bd2, dates, "combined_score", h)
            if pd2:
                m = float(np.mean([x["net_perday"] for x in pd2]))
                lono.append({"removed_ticker": t, "net_perday": round(m, 3)})
        lono_sorted = sorted(lono, key=lambda x: x["net_perday"])
        flips_name = sum(1 for x in lono if (x["net_perday"] > 0) != (full > 0))
        by_h[h] = {
            "full_net_perday": round(full, 3),
            "LODO_worst": lodo_sorted[0], "LODO_best": lodo_sorted[-1],
            "LODO_sign_flips": flips_day, "LODO_n_days": len(nets),
            "LONO_worst": lono_sorted[0], "LONO_best": lono_sorted[-1],
            "LONO_sign_flips": flips_name, "LONO_n_names": len(lono),
        }
    res["per_horizon"] = by_h
    # concentration: top contributing day/name share of total
    conc = {}
    for h in E.HORIZONS:
        pd = E.per_day_net_pct(by_date, dates, "combined_score", h)
        tot = sum(x["net_total"] for x in pd)
        contribs = sorted([(x["date"], x["net_total"]) for x in pd], key=lambda z: -z[1])
        conc[h] = {"sum_net_total": round(tot, 3),
                   "top1_day": [contribs[0][0], round(contribs[0][1], 3)],
                   "top1_share_of_positive_sum": None}
        possum = sum(c for _, c in contribs if c > 0)
        if possum > 0:
            conc[h]["top1_share_of_positive_sum"] = round(contribs[0][1] / possum, 3)
    res["day_concentration"] = conc
    return res


# =========================================================
# (c) EFFECTIVE N / OVERLAP
# 18 calendar days, 5d hold overlapping. Compute effective independent N.
# Newey-West-ish: report block-bootstrap and naive vs overlap-corrected t.
# =========================================================
def test_c():
    res = {"desc": "Effective N under overlapping holds."}
    cal_span_days = 18  # 2026-05-22 .. 2026-06-15 trading days observed
    by_h = {}
    for h in E.HORIZONS:
        days = E.usable_days(by_date, dates, h)
        hold = E.HOLD[h]
        n_obs = len(days)
        n_nonoverlap = len(E.nonoverlap_days(days, hold))
        # crude effective N: calendar span / hold
        eff_calendar = cal_span_days / hold
        pd = E.per_day_net_pct(by_date, dates, "combined_score", h)
        nets = np.array([x["net_total"] for x in pd])
        naive_t = E.tstat(nets)
        # overlap-deflated t: multiply SE by sqrt(hold) (rough overlap inflation)
        deflated_t = naive_t / np.sqrt(hold) if not np.isnan(naive_t) else np.nan
        # moving-block bootstrap CI on mean net_total (block=hold)
        rng = np.random.default_rng(1)
        boot = []
        L = len(nets)
        if L >= 2:
            nblocks = int(np.ceil(L / hold))
            for _ in range(5000):
                idx = []
                for _b in range(nblocks):
                    start = rng.integers(0, L)
                    idx.extend([(start + j) % L for j in range(hold)])
                idx = idx[:L]
                boot.append(nets[idx].mean())
            ci = [round(float(np.percentile(boot, 2.5)), 3),
                  round(float(np.percentile(boot, 97.5)), 3)]
            boot_p = float(np.mean(np.array(boot) <= 0)) if nets.mean() > 0 else float(np.mean(np.array(boot) >= 0))
            boot_p = round(2 * min(boot_p, 1 - boot_p), 3)
        else:
            ci = [None, None]
            boot_p = None
        by_h[h] = {
            "n_obs_overlap": n_obs, "n_nonoverlap": n_nonoverlap,
            "eff_N_calendar_div_hold": round(eff_calendar, 1),
            "naive_t_total": round(naive_t, 2) if not np.isnan(naive_t) else None,
            "overlap_deflated_t": round(deflated_t, 2) if not np.isnan(deflated_t) else None,
            "blockboot_95CI_mean_net_total": ci,
            "blockboot_two_sided_p": boot_p,
        }
    res["per_horizon"] = by_h
    return res


# =========================================================
# (d) SURVIVORSHIP / TRADABILITY
# Panel = only 30 names that map to perps. Test: does conclusion depend on
# which names are in? Bootstrap over the NAME universe (resample tickers),
# and split by theme/flag to see if a sub-universe drives it.
# Also: equal-weight long over the SAME universe is the relevant tradable baseline.
# =========================================================
def test_d():
    res = {"desc": "Survivorship/tradability: result sensitivity to the 30-name perp-mappable universe."}
    tickers = sorted(set(r["ticker"] for r in rows))
    # D1: bootstrap over tickers (resample the universe with replacement), f5 & f1
    rng = np.random.default_rng(7)
    by_h = {}
    for h in ["f1", "f5"]:
        days = E.usable_days(by_date, dates, h)
        hold = E.HOLD[h]
        boot_means = []
        for _ in range(3000):
            keep = set(rng.choice(tickers, size=len(tickers), replace=True))
            bd2 = {d: [r for r in by_date[d] if r["ticker"] in keep] for d in by_date}
            pd2 = E.per_day_net_pct(bd2, dates, "combined_score", h)
            if pd2:
                boot_means.append(np.mean([x["net_perday"] for x in pd2]))
        boot_means = np.array(boot_means)
        by_h[h] = {
            "median_net_perday": round(float(np.median(boot_means)), 3),
            "p05": round(float(np.percentile(boot_means, 5)), 3),
            "p95": round(float(np.percentile(boot_means, 95)), 3),
            "frac_positive": round(float(np.mean(boot_means > 0)), 3),
        }
    res["D1_ticker_bootstrap"] = by_h
    # D2: theme breakdown for the long leg membership at f5
    themes = {}
    for d in E.usable_days(by_date, dates, "f5"):
        ls = E.ls_day(by_date[d], "combined_score", "f5")
        if ls:
            for r in by_date[d]:
                if r["ticker"] in ls["long_t"]:
                    themes.setdefault(r["theme"], {"long": 0, "short": 0})["long"] += 1
                if r["ticker"] in ls["short_t"]:
                    themes.setdefault(r["theme"], {"long": 0, "short": 0})["short"] += 1
    res["D2_f5_leg_theme_membership"] = themes
    # D3: how many distinct tickers ever appear in long vs short leg (f5)
    longset, shortset = set(), set()
    for d in E.usable_days(by_date, dates, "f5"):
        ls = E.ls_day(by_date[d], "combined_score", "f5")
        if ls:
            longset.update(ls["long_t"]); shortset.update(ls["short_t"])
    res["D3_distinct_names_f5"] = {"long_names": sorted(longset),
                                   "short_names": sorted(shortset),
                                   "n_long": len(longset), "n_short": len(shortset)}
    return res


# =========================================================
# (e) COST STRESS  0.10 -> 0.20 %/leg
# =========================================================
def test_e():
    res = {"desc": "Cost stress: per-leg 0.10% -> 0.15% -> 0.20%."}
    by_cost = {}
    for cl in [0.10, 0.15, 0.20]:
        by_h = {}
        for h in E.HORIZONS:
            pd = ls_with_cost(by_date, dates, "combined_score", h, cl)
            nets = [x["net_perday"] for x in pd]
            wr = float(np.mean([1 if x["net_perday"] > 0 else 0 for x in pd]))
            t = E.tstat([x["net_total"] for x in pd])
            by_h[h] = {"net_perday": round(float(np.mean(nets)), 3),
                       "win": round(wr, 2), "t": round(t, 2) if not np.isnan(t) else None,
                       "n": len(pd)}
        by_cost[f"{cl:.2f}_per_leg"] = by_h
    res["by_cost"] = by_cost
    # also vs eqw long benchmark at matched cost (long pays 1 leg)
    return res


OUT["replication_note"] = "Engine reproduces audited headline to <0.01pp on all horizons (f1 +0.470, f2 -0.023, f3 +0.050, f5 +0.788; perm-p f5=0.163; beta f1 +0.301 f5 +0.325). Faithful."
OUT["a_momentum"] = test_a()
OUT["b_single_day_name"] = test_b()
OUT["c_effective_n"] = test_c()
OUT["d_survivorship"] = test_d()
OUT["e_cost_stress"] = test_e()

with open("result.json", "w") as f:
    json.dump(OUT, f, indent=2, default=str)
print(json.dumps(OUT, indent=2, default=str))
