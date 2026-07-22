#!/usr/bin/env python3
"""
Task A — Core Long/Short performance of the radar score panel.

Codename: ls_core

Construction (IRON RULES, see task brief):
  1. Each day rank tradable names by a score; LONG top tercile, SHORT bottom
     tercile, equal-weight, dollar-neutral.
       LS daily return = mean(long fwd) - mean(short fwd)   (already mkt-neutral)
  2. Cost: perp round-trip 0.10%/leg (taker 0.04%*2 + spread). BOTH legs charged.
     For an LS book that is 1x long notional + 1x short notional, each rebalance
     pays 0.10% (long RT) + 0.10% (short RT) = 0.20% charged against the LS
     spread. Cost is charged per rebalance event (full-turnover assumption).
  3. Effective sample is tiny (18 days, 5d overlap -> ~3-4 indep obs). Everything
     is EXPLORATORY. We report BOTH daily-rebal (overlapping, many but correlated
     obs) AND non-overlapping (rebalance every h days).
  4. SHORT leg uses MEAN, not median (guard left tail). (mean is used throughout.)
  5. Honest negatives are fine. No statistical power -> say so.

Forward returns fN and mkt_fN are in PERCENT (e.g. 3.04 == +3.04%).
fN nulls = clean end-of-window truncation; a day is usable for horizon h only
if every tradable name that day has a non-null fN. (Verified: nulls are
all-or-nothing per (day,horizon).)

numpy only (no scipy). Spearman + permutation hand-written.
"""
import json, math, os
import numpy as np

PANEL = "/Volumes/T9/BWE/40_EXPERIMENTS/round25_stockusbinance/radar_panel.jsonl"
OUTDIR = "/Volumes/T9/BWE/40_EXPERIMENTS/round25_stockusbinance/radar_backtest/ls_core"

COST_LEG_RT = 0.10        # % round-trip per leg
COST_LS = 2 * COST_LEG_RT # % charged against LS spread per rebalance (0.20)
COST_LONG_ONLY = COST_LEG_RT  # long-only beta book pays one leg RT

HORIZONS = ["f1", "f2", "f3", "f5"]
HDAYS = {"f1": 1, "f2": 2, "f3": 3, "f5": 5}

rng = np.random.default_rng(20260616)


# ----------------------------------------------------------------------------
# load
# ----------------------------------------------------------------------------
def load():
    rows = [json.loads(l) for l in open(PANEL)]
    by_date = {}
    for r in rows:
        by_date.setdefault(r["date"], []).append(r)
    return by_date


def usable_days(by_date, h):
    """Days where every tradable name has non-null fN and mkt_fN."""
    out = []
    for d in sorted(by_date):
        rs = by_date[d]
        if all(r.get(h) is not None and r.get("mkt_" + h) is not None for r in rs):
            out.append(d)
    return out


# ----------------------------------------------------------------------------
# per-day LS spread (gross) for a given score key + horizon
# ----------------------------------------------------------------------------
def day_ls(rs, score_key, h):
    """Return (gross_ls_pct, n_long, n_short, mean_long, mean_short) or None."""
    items = [(r[score_key], r[h]) for r in rs if r.get(h) is not None]
    n = len(items)
    if n < 3:
        return None  # need >=3 to form distinct terciles
    # sort by score descending; ties broken by original order (stable)
    items_sorted = sorted(items, key=lambda x: x[0], reverse=True)
    k = n // 3
    if k < 1:
        return None
    long_leg = items_sorted[:k]
    short_leg = items_sorted[-k:]
    ml = float(np.mean([x[1] for x in long_leg]))
    ms = float(np.mean([x[1] for x in short_leg]))  # MEAN not median
    return (ml - ms, k, k, ml, ms)


def day_longonly(rs, h):
    """Equal-weight long the WHOLE tradable universe that day (pure beta)."""
    vals = [r[h] for r in rs if r.get(h) is not None]
    if not vals:
        return None
    return float(np.mean(vals)), len(vals)


# ----------------------------------------------------------------------------
# stats helpers (hand-written)
# ----------------------------------------------------------------------------
def spearman(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    if len(x) < 3:
        return float("nan")
    def rank(a):
        order = np.argsort(a, kind="mergesort")
        r = np.empty(len(a), float)
        r[order] = np.arange(len(a))
        # average ties
        _, inv, cnt = np.unique(a, return_inverse=True, return_counts=True)
        sr = np.zeros(len(cnt));
        # compute mean rank per unique value
        sums = np.zeros(len(cnt))
        np.add.at(sums, inv, r)
        meanr = sums / cnt
        return meanr[inv]
    rx, ry = rank(x), rank(y)
    rx -= rx.mean(); ry -= ry.mean()
    denom = math.sqrt((rx*rx).sum() * (ry*ry).sum())
    return float((rx*ry).sum()/denom) if denom > 0 else float("nan")


def perm_pvalue_mean_pos(series, n_perm=20000):
    """Two-sided permutation/sign test that mean(series) != 0 via random sign
    flips (each daily obs sign-flipped). Returns p for |mean|."""
    s = np.asarray(series, float)
    if len(s) < 2:
        return float("nan")
    obs = abs(s.mean())
    cnt = 0
    for _ in range(n_perm):
        signs = rng.choice([-1.0, 1.0], size=len(s))
        if abs((s*signs).mean()) >= obs - 1e-15:
            cnt += 1
    return (cnt + 1) / (n_perm + 1)


def block_summary(series_total, h, label, charge_cost):
    """series_total: list of per-day GROSS LS total-horizon returns (%).
    Returns dict with gross/net, per-day, winrate, p-value."""
    s = np.asarray(series_total, float)
    n = len(s)
    if n == 0:
        return None
    cost = COST_LS if charge_cost else 0.0
    net = s - cost
    perday_net = net / h
    perday_gross = s / h
    out = {
        "label": label,
        "n_obs": int(n),
        "gross_ls_total_pct_mean": round(float(s.mean()), 4),
        "net_ls_total_pct_mean": round(float(net.mean()), 4),
        "gross_ls_perday_pct": round(float(perday_gross.mean()), 4),
        "net_ls_perday_pct": round(float(perday_net.mean()), 4),
        "net_ls_total_std": round(float(net.std(ddof=1)) if n > 1 else float("nan"), 4),
        "winrate_pos_net_days": round(float(np.mean(net > 0)), 3),
        "perm_p_two_sided_gross": round(perm_pvalue_mean_pos(s), 4),
        "perm_p_two_sided_net": round(perm_pvalue_mean_pos(net), 4),
        "daily_net_total_series": [round(float(x), 4) for x in net],
    }
    # simple t-stat (descriptive only)
    if n > 1 and net.std(ddof=1) > 0:
        out["t_stat_net"] = round(float(net.mean()/(net.std(ddof=1)/math.sqrt(n))), 3)
    else:
        out["t_stat_net"] = float("nan")
    return out


# ----------------------------------------------------------------------------
# main engine
# ----------------------------------------------------------------------------
def run_score(by_date, score_key):
    res = {}
    for h in HORIZONS:
        hd = HDAYS[h]
        days = usable_days(by_date, h)

        # ---- daily-rebal (overlapping): every usable day is a rebalance ----
        ls_over = []
        legdetail = []
        for d in days:
            r = day_ls(by_date[d], score_key, h)
            if r is None:
                continue
            ls_over.append(r[0])
            legdetail.append({"date": d, "n_leg": r[1], "mean_long": round(r[3], 3),
                              "mean_short": round(r[4], 3), "gross_ls": round(r[0], 3)})
        over = block_summary(ls_over, hd, "daily_rebal_overlap", charge_cost=True)
        if over is not None:
            over["n_usable_days"] = len(days)
            over["leg_detail"] = legdetail

        # ---- non-overlapping: rebalance every hd-th usable day (index walk) -
        no_idx = list(range(0, len(days), hd))
        ls_no = []
        no_dates = []
        for i in no_idx:
            d = days[i]
            r = day_ls(by_date[d], score_key, h)
            if r is None:
                continue
            ls_no.append(r[0])
            no_dates.append(d)
        nonover = block_summary(ls_no, hd, "non_overlap_every_h", charge_cost=True)
        if nonover is not None:
            nonover["rebalance_dates"] = no_dates

        res[h] = {"daily_rebal_overlap": over, "non_overlap_every_h": nonover}
    return res


def run_longonly(by_date):
    res = {}
    for h in HORIZONS:
        hd = HDAYS[h]
        days = usable_days(by_date, h)
        # overlapping
        series = []
        for d in days:
            r = day_longonly(by_date[d], h)
            if r:
                series.append(r[0])
        s = np.asarray(series, float)
        net = s - COST_LONG_ONLY
        over = {
            "label": "longonly_universe_overlap",
            "n_obs": int(len(s)),
            "gross_long_total_pct_mean": round(float(s.mean()), 4),
            "net_long_total_pct_mean": round(float(net.mean()), 4),
            "gross_long_perday_pct": round(float((s/hd).mean()), 4),
            "net_long_perday_pct": round(float((net/hd).mean()), 4),
            "winrate_pos_net_days": round(float(np.mean(net > 0)), 3),
        }
        # non-overlapping
        nidx = list(range(0, len(days), hd))
        ns = []
        for i in nidx:
            r = day_longonly(by_date[days[i]], h)
            if r:
                ns.append(r[0])
        ns = np.asarray(ns, float)
        nnet = ns - COST_LONG_ONLY
        nonover = {
            "label": "longonly_universe_non_overlap",
            "n_obs": int(len(ns)),
            "net_long_total_pct_mean": round(float(nnet.mean()), 4),
            "net_long_perday_pct": round(float((nnet/hd).mean()), 4),
            "winrate_pos_net_days": round(float(np.mean(nnet > 0)), 3),
        }
        res[h] = {"overlap": over, "non_overlap": nonover}
    return res


def daily_rank_ic(by_date, score_key, h):
    """Pooled Spearman IC: per-day spearman(score, fN) averaged across days,
    plus pooled (cross-sectionally demeaned). Descriptive."""
    days = usable_days(by_date, h)
    per_day = []
    for d in days:
        rs = by_date[d]
        xs = [r[score_key] for r in rs if r.get(h) is not None]
        ys = [r[h] for r in rs if r.get(h) is not None]
        if len(xs) >= 4:
            rho = spearman(xs, ys)
            if not math.isnan(rho):
                per_day.append(rho)
    if not per_day:
        return None
    arr = np.asarray(per_day)
    return {
        "n_days": len(per_day),
        "mean_daily_rank_ic": round(float(arr.mean()), 4),
        "std_daily_rank_ic": round(float(arr.std(ddof=1)) if len(arr) > 1 else float("nan"), 4),
        "t_stat": round(float(arr.mean()/(arr.std(ddof=1)/math.sqrt(len(arr)))), 3) if len(arr) > 1 and arr.std(ddof=1) > 0 else float("nan"),
        "winrate_pos_ic_days": round(float(np.mean(arr > 0)), 3),
    }


def main():
    by_date = load()
    out = {
        "meta": {
            "panel": PANEL,
            "n_rows": sum(len(v) for v in by_date.values()),
            "n_dates": len(by_date),
            "cost_leg_round_trip_pct": COST_LEG_RT,
            "cost_ls_per_rebalance_pct": COST_LS,
            "cost_longonly_per_rebalance_pct": COST_LONG_ONLY,
            "tercile_rule": "long top n//3 by score, short bottom n//3, equal-weight dollar-neutral; short uses MEAN",
            "horizon_usable_days": {h: len(usable_days(by_date, h)) for h in HORIZONS},
            "WARNING": "EXPLORATORY ONLY. 18 days, 5d overlap -> effective indep obs ~3-4. No statistical power. Mechanism direction at best.",
        },
        "combined_score_LS": run_score(by_date, "combined_score"),
        "tech_score_LS": run_score(by_date, "tech_score"),
        "sentiment_LS": run_score(by_date, "sentiment"),
        "longonly_beta_benchmark": run_longonly(by_date),
        "rank_IC": {
            "combined_score": {h: daily_rank_ic(by_date, "combined_score", h) for h in HORIZONS},
            "tech_score": {h: daily_rank_ic(by_date, "tech_score", h) for h in HORIZONS},
            "sentiment": {h: daily_rank_ic(by_date, "sentiment", h) for h in HORIZONS},
        },
    }
    os.makedirs(OUTDIR, exist_ok=True)
    with open(os.path.join(OUTDIR, "ls_core_results.json"), "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
