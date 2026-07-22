#!/usr/bin/env python3
"""
Adversarial re-verification of the `permuter` refutation.
code-name: adversary

Goal: independently re-derive every load-bearing number in the permuter finding
from scratch (numpy only, hand-written stats), AND attack the refutation itself.
We are equally suspicious of the original "skill" claim and of the refutation.

The permuter claims the radar LS is NOISE (refuted). We check:
  - Are the permutation p-values reproducible from scratch?  (a) momentum disguise
  - vs pure-momentum & sentiment baselines                   (a)
  - LODO single-day & single-name drop                       (b)
  - block-bootstrap CI + effective N                         (c)
  - survivorship / tradeability (only 30 mapped names)       (d) [structural note]
  - cost stress 0.10 -> 0.20 -> 0.30 /leg                     (e)

PLUS independent probes the permuter did NOT do, to avoid rubber-stamping:
  - sign test / simple t on non-overlap books (parametric sanity)
  - winsorized HEADLINE LS (not just inside permutation) net of cost
  - recompute "single-name share" with a CLEAN definition and cross-check 81%
  - per-day fwd dispersion: is LS just rank-noise * dispersion?
"""
import json, math, os
import numpy as np

PANEL = "/Volumes/T9/BWE/40_EXPERIMENTS/round25_stockusbinance/radar_panel.jsonl"
OUTDIR = "/Volumes/T9/BWE/40_EXPERIMENTS/round25_stockusbinance/radar_backtest/adversary"
HORIZONS = ["f1", "f2", "f3", "f5"]
HOLD = {"f1": 1, "f2": 2, "f3": 3, "f5": 5}
SEED = 7777
os.makedirs(OUTDIR, exist_ok=True)


def load():
    rows = [json.loads(l) for l in open(PANEL)]
    dates = sorted(set(r["date"] for r in rows))
    bydate = {d: [] for d in dates}
    for r in rows:
        bydate[r["date"]].append(r)
    return rows, dates, bydate


def day_legs(group, score_field, horizon, winsor=False):
    """Return (fwd_array, long_idx, short_idx, k) for a day, or None."""
    g = [r for r in group if r.get(horizon) is not None and r.get(score_field) is not None]
    n = len(g)
    if n < 3:
        return None
    k = n // 3
    if k < 1:
        return None
    scores = np.array([r[score_field] for r in g], dtype=float)
    fwd = np.array([r[horizon] for r in g], dtype=float)
    if winsor:
        lo, hi = np.percentile(fwd, [10, 90])
        fwd = np.clip(fwd, lo, hi)
    order = np.argsort(scores, kind="mergesort")
    return fwd, order[-k:], order[:k], k, g


def ls_series(bydate, dates, score_field, horizon, winsor=False):
    out = []  # (date, ls, long_mean, short_mean, fwd, long_idx, short_idx, k, group)
    for d in dates:
        res = day_legs(bydate[d], score_field, horizon, winsor=winsor)
        if res is None:
            continue
        fwd, li, si, k, g = res
        lm = float(np.mean(fwd[li]))
        sm = float(np.mean(fwd[si]))
        out.append((d, lm - sm, lm, sm, fwd, li, si, k, g))
    return out


# ---- (a) permutation, recomputed independently ----
def perm_test(bydate, dates, score_field, horizon, n_perm=2000, seed=SEED, winsor=False):
    rng = np.random.default_rng(seed)
    days = []
    for d in dates:
        res = day_legs(bydate[d], score_field, horizon, winsor=winsor)
        if res is None:
            continue
        fwd, li, si, k, g = res
        days.append((fwd, k))
    if not days:
        return None
    def lsmean(perm):
        v = []
        for fwd, k in days:
            idx = perm(len(fwd))
            sm = np.mean(fwd[idx[:k]])
            lm = np.mean(fwd[idx[-k:]])
            v.append(lm - sm)
        return np.mean(v)
    # observed uses REAL score order. We re-derive observed from the real legs:
    obs_v = []
    for d in dates:
        res = day_legs(bydate[d], score_field, horizon, winsor=winsor)
        if res is None:
            continue
        fwd, li, si, k, g = res
        obs_v.append(np.mean(fwd[li]) - np.mean(fwd[si]))
    observed = float(np.mean(obs_v))
    null = np.array([lsmean(lambda n: rng.permutation(n)) for _ in range(n_perm)])
    p_right = (np.sum(null >= observed) + 1) / (n_perm + 1)
    return {"observed": observed, "null_mean": float(null.mean()),
            "p_right": float(p_right), "n_days": len(days), "n_perm": n_perm}


def mean_ls(bydate, dates, score_field, horizon, winsor=False):
    s = ls_series(bydate, dates, score_field, horizon, winsor=winsor)
    return float(np.mean([x[1] for x in s])) if s else float("nan"), len(s)


# ---- (b) LODO + leave-one-name-out ----
def lodo(series):
    vals = np.array([x[1] for x in series])
    dates = [x[0] for x in series]
    full = float(vals.mean())
    total = float(vals.sum())
    j = int(np.argmax(np.abs(vals)))
    without = float(np.delete(vals, j).mean())
    flips = any(np.sign(np.delete(vals, i).mean()) != np.sign(full) for i in range(len(vals))) if full != 0 else False
    return {"full": full, "biggest_day": dates[j], "biggest_day_ls": float(vals[j]),
            "biggest_day_share_of_sum": float(vals[j] / total) if total else float("nan"),
            "mean_without_biggest": without, "any_sign_flip": bool(flips)}


def leave_one_name_out(bydate, dates, horizon, score_field="combined_score"):
    """Drop the single most extreme |fwd| name PER DAY from its leg, recompute LS mean.
    Independent re-derivation of the permuter's drop_extreme. Uses pure extremity,
    not deviation-from-median (the permuter used dev-from-median; we test both)."""
    drop_abs, drop_med, raw = [], [], []
    for d in dates:
        res = day_legs(bydate[d], score_field, horizon)
        if res is None:
            continue
        fwd, li, si, k, g = res
        raw.append(np.mean(fwd[li]) - np.mean(fwd[si]))
        def leg_drop_abs(idx):
            if len(idx) <= 1:
                return np.mean(fwd[idx])
            sub = fwd[idx]
            keep = np.argsort(np.abs(sub))[:-1]  # drop largest |fwd|
            return np.mean(sub[keep])
        def leg_drop_med(idx):
            if len(idx) <= 1:
                return np.mean(fwd[idx])
            sub = fwd[idx]
            keep = np.argsort(np.abs(sub - np.median(sub)))[:-1]
            return np.mean(sub[keep])
        drop_abs.append(leg_drop_abs(li) - leg_drop_abs(si))
        drop_med.append(leg_drop_med(li) - leg_drop_med(si))
    return {"raw_mean": float(np.mean(raw)),
            "drop_largest_abs_mean": float(np.mean(drop_abs)),
            "drop_dev_from_median_mean": float(np.mean(drop_med))}


# ---- single-name share, CLEAN definition ----
def single_name_share(bydate, dates, horizon, score_field="combined_score"):
    """For each day decompose LS = (1/k) sum_long fwd - (1/k) sum_short fwd.
    Each name contributes +fwd/k (long) or -fwd/k (short). Share of the largest
    |single contribution| relative to |LS|. This is the permuter's metric; we
    re-derive to confirm the 81% figure and also report a more honest variant:
    largest contribution as fraction of sum of |contributions| (always <=1, no blow-up)."""
    shares_vs_ls, shares_vs_sumabs = [], []
    for d in dates:
        res = day_legs(bydate[d], score_field, horizon)
        if res is None:
            continue
        fwd, li, si, k, g = res
        contribs = list(fwd[li] / k) + list(-fwd[si] / k)
        ls = sum(contribs)
        abscon = [abs(c) for c in contribs]
        mx = max(abscon)
        if ls != 0:
            shares_vs_ls.append(mx / abs(ls))
        if sum(abscon) > 0:
            shares_vs_sumabs.append(mx / sum(abscon))
    return {"median_share_vs_LS": float(np.median(shares_vs_ls)),
            "median_share_vs_sumabs": float(np.median(shares_vs_sumabs)),
            "n_days": len(shares_vs_ls)}


# ---- (c) block bootstrap + effective N ----
def block_boot(series, horizon, n_boot=10000, seed=SEED):
    vals = np.array([x[1] for x in series])
    n = len(vals)
    block = max(1, HOLD[horizon])
    rng = np.random.default_rng(seed + 11)
    nb = int(math.ceil(n / block))
    means = np.empty(n_boot)
    for b in range(n_boot):
        idx = []
        for _ in range(nb):
            s = rng.integers(0, n)
            idx.extend((s + j) % n for j in range(block))
        means[b] = vals[np.array(idx[:n])].mean()
    lo, hi = np.percentile(means, [2.5, 97.5])
    return {"mean": float(vals.mean()), "ci_lo": float(lo), "ci_hi": float(hi),
            "excludes_zero": bool(lo > 0 or hi < 0)}


def nonoverlap(bydate, dates, score_field, horizon, cost_per_leg):
    h = HOLD[horizon]
    qdates = [d for d in dates if day_legs(bydate[d], score_field, horizon) is not None]
    picked = qdates[::h]
    vals = []
    for d in picked:
        res = day_legs(bydate[d], score_field, horizon)
        fwd, li, si, k, g = res
        vals.append(np.mean(fwd[li]) - np.mean(fwd[si]))
    vals = np.array(vals)
    cost = 2 * cost_per_leg
    net = vals - cost
    n = len(vals)
    # simple t-stat (parametric sanity, hand-rolled), one-sided
    if n > 1 and net.std(ddof=1) > 0:
        t = net.mean() / (net.std(ddof=1) / math.sqrt(n))
    else:
        t = float("nan")
    return {"n_books": n, "gross_mean": float(vals.mean()),
            "net_mean": float(net.mean()), "net_t": float(t),
            "win_rate": float(np.mean(net > 0))}


# ---- (e) cost stress ----
def cost_stress(bydate, dates, horizon):
    s = ls_series(bydate, dates, "combined_score", horizon)
    gross = np.array([x[1] for x in s])
    out = {}
    for cpl in (0.10, 0.20, 0.30):
        net = gross - 2 * cpl
        out[f"cpl_{cpl}"] = {"daily_rebal_net_total_mean": float(net.mean()),
                             "win_rate": float(np.mean(net > 0))}
    # nonoverlap at each cost
    for cpl in (0.10, 0.20, 0.30):
        no = nonoverlap(bydate, dates, "combined_score", horizon, cpl)
        out[f"cpl_{cpl}"]["nonoverlap_net_mean"] = no["net_mean"]
        out[f"cpl_{cpl}"]["nonoverlap_n_books"] = no["n_books"]
        out[f"cpl_{cpl}"]["nonoverlap_net_t"] = no["net_t"]
    return out


# ---- (d) tradeability: how many distinct names ever appear, leg sizes ----
def universe_stats(bydate, dates):
    names = set()
    perday = []
    for d in dates:
        g = [r for r in bydate[d]]
        perday.append(len(g))
        for r in g:
            names.add(r["ticker"])
    return {"distinct_tickers": len(names), "median_names_per_day": float(np.median(perday)),
            "min": int(min(perday)), "max": int(max(perday))}


def main():
    rows, dates, bydate = load()
    res = {"meta": {"n_rows": len(rows), "n_dates": len(dates),
                    "universe": universe_stats(bydate, dates)}, "horizons": {}}
    for h in HORIZONS:
        hr = {}
        # (a)
        hr["perm_combined"] = perm_test(bydate, dates, "combined_score", h)
        hr["perm_combined_winsor"] = perm_test(bydate, dates, "combined_score", h, winsor=True)
        hr["perm_momentum"] = perm_test(bydate, dates, "momentum_20d_pct", h)
        cmb, _ = mean_ls(bydate, dates, "combined_score", h)
        mom, _ = mean_ls(bydate, dates, "momentum_20d_pct", h)
        sen, _ = mean_ls(bydate, dates, "sentiment", h)
        tec, _ = mean_ls(bydate, dates, "tech_score", h)
        cmb_w, _ = mean_ls(bydate, dates, "combined_score", h, winsor=True)
        hr["baselines"] = {"combined": cmb, "momentum": mom, "sentiment": sen,
                           "tech": tec, "combined_winsor_headline": cmb_w,
                           "combined_minus_momentum": cmb - mom,
                           "combined_minus_sentiment": cmb - sen}
        # (b)
        hr["lodo"] = lodo(ls_series(bydate, dates, "combined_score", h))
        hr["leave_one_name"] = leave_one_name_out(bydate, dates, h)
        hr["single_name_share"] = single_name_share(bydate, dates, h)
        # (c)
        hr["block_boot"] = block_boot(ls_series(bydate, dates, "combined_score", h), h)
        # (e)
        hr["cost_stress"] = cost_stress(bydate, dates, h)
        res["horizons"][h] = hr

    with open(os.path.join(OUTDIR, "verify_results.json"), "w") as f:
        json.dump(res, f, indent=2)

    print("=== ADVERSARY re-verification ===")
    print("universe:", res["meta"]["universe"])
    print()
    hdr = ("h", "cmb_LS", "mom_LS", "sen_LS", "perm_p", "perm_p_wins", "wins_LS",
           "biggest_day_sh", "mean_woBig", "snm_vs_LS", "snm_sumabs", "bootCI")
    print("%-3s %7s %7s %7s %7s %8s %7s %9s %8s %7s %8s %s" % hdr)
    for h in HORIZONS:
        r = res["horizons"][h]
        b = r["baselines"]; l = r["lodo"]; s = r["single_name_share"]; bb = r["block_boot"]
        print("%-3s %7.3f %7.3f %7.3f %7.3f %8.3f %7.3f %9.3f %8.3f %7.2f %8.2f [%.2f,%.2f]" % (
            h, b["combined"], b["momentum"], b["sentiment"],
            r["perm_combined"]["p_right"], r["perm_combined_winsor"]["p_right"],
            b["combined_winsor_headline"], l["biggest_day_share_of_sum"],
            l["mean_without_biggest"], s["median_share_vs_LS"], s["median_share_vs_sumabs"],
            bb["ci_lo"], bb["ci_hi"]))
    print()
    print("=== COST STRESS (combined_score) nonoverlap net_mean / t / n ===")
    print("%-3s %18s %18s %18s" % ("h", "0.10/leg", "0.20/leg", "0.30/leg"))
    for h in HORIZONS:
        cs = res["horizons"][h]["cost_stress"]
        def fmt(cpl):
            c = cs[f"cpl_{cpl}"]
            return "%6.2f t=%4.2f n=%d" % (c["nonoverlap_net_mean"], c["nonoverlap_net_t"], c["nonoverlap_n_books"])
        print("%-3s %18s %18s %18s" % (h, fmt(0.10), fmt(0.20), fmt(0.30)))
    return res


if __name__ == "__main__":
    main()
