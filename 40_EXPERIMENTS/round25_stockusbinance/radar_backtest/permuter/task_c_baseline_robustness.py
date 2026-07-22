#!/usr/bin/env python3
"""
Task C — 随机基线 + 稳健性 (防噪声冒充技能)
=================================================
code-name: permuter

目标: 判断 round25 radar 的 18 天 LS 结果到底是「技能信号」还是
「随机 / 单日产物」。手写 permutation / spearman, 只用 numpy (no scipy)。

构造铁律:
1. 多空: 每天按分数排名 -> 多最高 tercile + 空最低 tercile, 等权 dollar-neutral.
   LS_day = mean(long fwd) - mean(short fwd). (本身即市场中性量)
2. 成本: 往返 0.10%/腿, 多空两腿都扣. daily-rebal 每天调仓都扣;
   非重叠每 h 天调仓扣一次.
3. 有效样本: 18 天, 5d 重叠 -> 有效独立观测 ~3-4. 探索性.
   报 daily-rebal(重叠) + 非重叠(每 h 天) 两口径.
4. 做空看均值(防左尾).
5. 诚实报负.

输出: task_c_results.json
"""
import json, math, os
import numpy as np

PANEL = "/Volumes/T9/BWE/40_EXPERIMENTS/round25_stockusbinance/radar_panel.jsonl"
OUTDIR = "/Volumes/T9/BWE/40_EXPERIMENTS/round25_stockusbinance/radar_backtest/permuter"
HORIZONS = ["f1", "f2", "f3", "f5"]
HOLD = {"f1": 1, "f2": 2, "f3": 3, "f5": 5}   # holding days per horizon
COST_PER_LEG = 0.10   # % round-trip per leg (taker 0.04*2 + spread)
# LS uses two legs (long + short), each leg costs COST_PER_LEG per rebalance.
COST_PER_REBAL = 2 * COST_PER_LEG   # = 0.20% deducted from LS gross per rebalance
N_PERM = 1000
N_BOOT = 5000
SEED = 20260616


# ----------------------------------------------------------------------------
# load
# ----------------------------------------------------------------------------
def load():
    rows = [json.loads(l) for l in open(PANEL)]
    dates = sorted(set(r["date"] for r in rows))
    bydate = {d: [] for d in dates}
    for r in rows:
        bydate[r["date"]].append(r)
    return rows, dates, bydate


# ----------------------------------------------------------------------------
# LS construction for one day, one score field, one horizon
# tercile: long = top third by score, short = bottom third by score.
# returns (ls_gross, n_long, n_short, long_mean, short_mean) or None if <3 names
# ----------------------------------------------------------------------------
def day_ls(group, score_field, horizon):
    # only names with a valid forward return for this horizon
    g = [r for r in group if r.get(horizon) is not None]
    n = len(g)
    if n < 3:
        return None
    scores = np.array([r[score_field] for r in g], dtype=float)
    fwd = np.array([r[horizon] for r in g], dtype=float)
    order = np.argsort(scores)           # ascending
    k = n // 3                           # tercile size (floor)
    if k < 1:
        return None
    short_idx = order[:k]                # lowest scores
    long_idx = order[-k:]                # highest scores
    long_mean = float(np.mean(fwd[long_idx]))
    short_mean = float(np.mean(fwd[short_idx]))   # mean not median (左尾防护)
    ls_gross = long_mean - short_mean
    return ls_gross, k, k, long_mean, short_mean


def daily_ls_series(bydate, dates, score_field, horizon):
    """Return list of (date, ls_gross, long_mean, short_mean) for days that qualify."""
    out = []
    for d in dates:
        res = day_ls(bydate[d], score_field, horizon)
        if res is None:
            continue
        ls_gross, nl, ns, lm, sm = res
        out.append((d, ls_gross, lm, sm))
    return out


# ----------------------------------------------------------------------------
# cost-adjusted aggregates
# ----------------------------------------------------------------------------
def daily_rebal_stats(series, horizon):
    """
    daily-rebal (重叠): every radar day opens a fresh LS book held `HOLD` days.
    LS_day is the *total* return over the holding period (f_h is cumulative
    return from entry, so it already spans HOLD[h] days). To express per-day,
    divide by holding days. Cost: one round-trip (open+close) per book = COST_PER_REBAL.
    """
    h = HOLD[horizon]
    gross_total = np.array([s[1] for s in series], dtype=float)   # % over holding period
    net_total = gross_total - COST_PER_REBAL
    # per-day (annualizable) figures
    gross_perday = gross_total / h
    net_perday = net_total / h
    return {
        "n_books": len(series),
        "gross_total_mean": float(np.mean(gross_total)),
        "net_total_mean": float(np.mean(net_total)),
        "gross_perday_mean": float(np.mean(gross_perday)),
        "net_perday_mean": float(np.mean(net_perday)),
        "gross_total_std": float(np.std(gross_total, ddof=1)) if len(gross_total) > 1 else float("nan"),
        "win_rate_net": float(np.mean(net_total > 0)),
        "series_total": gross_total.tolist(),
    }


def nonoverlap_stats(bydate, dates, score_field, horizon):
    """
    非重叠: only open a new book every HOLD[h] *radar days* (index stride),
    so holding periods don't overlap -> closer to independent obs.
    """
    h = HOLD[horizon]
    # qualifying dates (have horizon) in order
    qdates = [d for d in dates if day_ls(bydate[d], score_field, horizon) is not None]
    picked = qdates[::h]   # stride
    series = []
    for d in picked:
        res = day_ls(bydate[d], score_field, horizon)
        if res is None:
            continue
        series.append((d, res[0]))
    gross_total = np.array([s[1] for s in series], dtype=float)
    net_total = gross_total - COST_PER_REBAL
    return {
        "n_books": len(series),
        "picked_dates": picked,
        "gross_total_mean": float(np.mean(gross_total)) if len(gross_total) else float("nan"),
        "net_total_mean": float(np.mean(net_total)) if len(gross_total) else float("nan"),
        "gross_perday_mean": float(np.mean(gross_total / h)) if len(gross_total) else float("nan"),
        "net_perday_mean": float(np.mean(net_total / h)) if len(gross_total) else float("nan"),
        "win_rate_net": float(np.mean(net_total > 0)) if len(gross_total) else float("nan"),
        "series_total": gross_total.tolist(),
    }


# ----------------------------------------------------------------------------
# PERMUTATION null: each day shuffle scores among that day's names, recompute LS,
# 1000 reps. p = fraction of perms with mean-LS >= observed (one-sided, right).
# This destroys score->fwd mapping while keeping daily fwd cross-section intact.
# ----------------------------------------------------------------------------
def permutation_test(bydate, dates, score_field, horizon, n_perm=N_PERM, seed=SEED, winsor=False):
    rng = np.random.default_rng(seed)
    # precompute per-day fwd arrays + n + k for qualifying days
    days = []
    for d in dates:
        g = [r for r in bydate[d] if r.get(horizon) is not None]
        n = len(g)
        if n < 3:
            continue
        k = n // 3
        if k < 1:
            continue
        fwd = np.array([r[horizon] for r in g], dtype=float)
        if winsor:
            lo, hi = np.percentile(fwd, [10, 90])
            fwd = np.clip(fwd, lo, hi)
        scores = np.array([r[score_field] for r in g], dtype=float)
        days.append((fwd, scores, n, k))
    if not days:
        return None

    def ls_mean_from_perm(perm_fn):
        ls_vals = []
        for fwd, scores, n, k in days:
            s = perm_fn(scores)
            order = np.argsort(s)
            short_mean = np.mean(fwd[order[:k]])
            long_mean = np.mean(fwd[order[-k:]])
            ls_vals.append(long_mean - short_mean)
        return np.mean(ls_vals)

    observed = ls_mean_from_perm(lambda s: s)   # real scores
    null = np.empty(n_perm)
    for i in range(n_perm):
        null[i] = ls_mean_from_perm(lambda s: rng.permutation(s))
    # one-sided right-tail p (signal predicts positive LS); +1 smoothing
    p_right = (np.sum(null >= observed) + 1) / (n_perm + 1)
    p_left = (np.sum(null <= observed) + 1) / (n_perm + 1)
    pctile = float(np.mean(null < observed) * 100.0)   # percentile of observed in null
    return {
        "observed_ls_mean": float(observed),
        "null_mean": float(np.mean(null)),
        "null_std": float(np.std(null, ddof=1)),
        "p_right": float(p_right),
        "p_left": float(p_left),
        "percentile": pctile,
        "n_perm": n_perm,
        "n_days_used": len(days),
    }


# ----------------------------------------------------------------------------
# pure momentum baseline: same LS construction but rank by momentum_20d_pct.
# Does combined_score LS beat free momentum LS?
# ----------------------------------------------------------------------------
def momentum_vs_combined(bydate, dates, horizon):
    cs = daily_ls_series(bydate, dates, "combined_score", horizon)
    mo = daily_ls_series(bydate, dates, "momentum_20d_pct", horizon)
    se = daily_ls_series(bydate, dates, "sentiment", horizon)
    te = daily_ls_series(bydate, dates, "tech_score", horizon)
    def mean_ls(series):
        return float(np.mean([s[1] for s in series])) if series else float("nan")
    return {
        "combined_ls_gross_mean": mean_ls(cs),
        "momentum_ls_gross_mean": mean_ls(mo),
        "sentiment_ls_gross_mean": mean_ls(se),
        "tech_ls_gross_mean": mean_ls(te),
        "combined_beats_momentum": mean_ls(cs) > mean_ls(mo),
        "combined_minus_momentum": mean_ls(cs) - mean_ls(mo),
    }


# ----------------------------------------------------------------------------
# LODO (leave-one-day-out): drop each day, recompute mean LS. Detect single-day driver.
# ----------------------------------------------------------------------------
def lodo(series):
    vals = np.array([s[1] for s in series], dtype=float)
    dates = [s[0] for s in series]
    full = float(np.mean(vals))
    n = len(vals)
    out = []
    for i in range(n):
        rest = np.delete(vals, i)
        out.append({"dropped": dates[i], "ls_mean_without": float(np.mean(rest)),
                    "delta": float(np.mean(rest) - full), "this_day_ls": float(vals[i])})
    deltas = [o["delta"] for o in out]
    # most influential day = one whose removal moves the mean most
    worst = max(out, key=lambda o: abs(o["delta"]))
    # sign flip? does any single removal flip sign of mean?
    sign_flips = [o["dropped"] for o in out if (np.sign(o["ls_mean_without"]) != np.sign(full)) and full != 0]
    # contribution share of single best day to total sum
    total = float(np.sum(vals))
    max_day = dates[int(np.argmax(np.abs(vals)))]
    max_day_val = float(vals[int(np.argmax(np.abs(vals)))])
    share = (max_day_val / total) if total != 0 else float("nan")
    return {
        "full_ls_mean": full,
        "n_days": n,
        "most_influential_day": worst["dropped"],
        "ls_mean_without_most_influential": worst["ls_mean_without"],
        "max_delta_from_one_day": worst["delta"],
        "sign_flips_on_single_removal": sign_flips,
        "single_day_driven": bool(len(sign_flips) > 0),
        "largest_abs_day": max_day,
        "largest_abs_day_ls": max_day_val,
        "largest_day_share_of_sum": share,
        "per_day": out,
    }


# ----------------------------------------------------------------------------
# Block bootstrap: resample contiguous blocks of length=HOLD to respect overlap
# autocorrelation -> CI on mean LS + effective N estimate.
# Effective N via Neff = n / (1 + 2*sum_{k=1}^{L} rho_k) (Newey-West style, L=HOLD-1).
# ----------------------------------------------------------------------------
def block_bootstrap(series, horizon, n_boot=N_BOOT, seed=SEED):
    vals = np.array([s[1] for s in series], dtype=float)
    n = len(vals)
    h = HOLD[horizon]
    block = max(1, h)   # block length ~ holding period (overlap window)
    rng = np.random.default_rng(seed + 7)
    means = np.empty(n_boot)
    n_blocks = int(math.ceil(n / block))
    for b in range(n_boot):
        idxs = []
        for _ in range(n_blocks):
            start = rng.integers(0, n)   # circular block bootstrap
            for j in range(block):
                idxs.append((start + j) % n)
        idxs = idxs[:n]
        means[b] = np.mean(vals[idxs])
    ci_lo, ci_hi = np.percentile(means, [2.5, 97.5])

    # effective N (autocorrelation-deflated)
    def autocorr(x, k):
        if k == 0:
            return 1.0
        x = x - np.mean(x)
        denom = np.sum(x * x)
        if denom == 0:
            return 0.0
        return float(np.sum(x[:-k] * x[k:]) / denom)
    L = min(h - 1, n - 1)
    rho_sum = sum(autocorr(vals, k) * (1 - k / (L + 1)) for k in range(1, L + 1)) if L >= 1 else 0.0
    neff = n / (1 + 2 * rho_sum) if (1 + 2 * rho_sum) > 0 else float(n)
    # negative autocorr (anti-persistence) must not inflate effective N above raw count:
    # for risk-honesty we cap at n_obs. The theoretical floor for overlapping h-day
    # holds with 18 calendar days is ~n_calendar/h.
    neff = min(neff, float(n))
    return {
        "mean": float(np.mean(vals)),
        "ci95_lo": float(ci_lo),
        "ci95_hi": float(ci_hi),
        "ci_excludes_zero": bool(ci_lo > 0 or ci_hi < 0),
        "block_len": block,
        "n_obs": n,
        "n_eff_autocorr": float(neff),
        "rho_sum": float(rho_sum),
        "boot_p_two_sided": float(2 * min(np.mean(means <= 0), np.mean(means >= 0))),
    }


# ----------------------------------------------------------------------------
# single-name driver check: per day, identify the name with the largest |fwd|
# contribution to that day's LS. Then recompute LS series after (a) winsorizing
# fwd at the daily 10/90 pct and (b) dropping the single most extreme fwd name
# from whichever leg it sits in. If LS collapses -> it was one-name driven.
# ----------------------------------------------------------------------------
def single_name_robustness(bydate, dates, score_field, horizon):
    raw, wins, dropext = [], [], []
    worst_contrib = []   # per-day max single-name share of |LS|
    for d in dates:
        g = [r for r in bydate[d] if r.get(horizon) is not None]
        n = len(g)
        if n < 3:
            continue
        k = n // 3
        if k < 1:
            continue
        scores = np.array([r[score_field] for r in g], float)
        fwd = np.array([r[horizon] for r in g], float)
        order = np.argsort(scores)
        short_idx, long_idx = order[:k], order[-k:]

        lm, sm = np.mean(fwd[long_idx]), np.mean(fwd[short_idx])
        ls = lm - sm
        raw.append(ls)

        # winsorize this day's fwd at 10/90
        lo, hi = np.percentile(fwd, [10, 90])
        fw = np.clip(fwd, lo, hi)
        wins.append(np.mean(fw[long_idx]) - np.mean(fw[short_idx]))

        # drop single most extreme |fwd| name in each leg (if leg has >1)
        def leg_mean_drop(idx):
            if len(idx) <= 1:
                return np.mean(fwd[idx])
            sub = fwd[idx]
            keep = np.argsort(np.abs(sub - np.median(sub)))[:-1]  # drop the most extreme
            return np.mean(sub[keep])
        dropext.append(leg_mean_drop(long_idx) - leg_mean_drop(short_idx))

        # single-name contribution: which one name's fwd most affects LS?
        contrib = []
        for j in long_idx:
            contrib.append(abs(fwd[j] / k))
        for j in short_idx:
            contrib.append(abs(fwd[j] / k))
        if ls != 0:
            worst_contrib.append(max(contrib) / abs(ls))
    return {
        "raw_mean": float(np.mean(raw)) if raw else float("nan"),
        "winsorized_mean": float(np.mean(wins)) if wins else float("nan"),
        "drop_extreme_name_mean": float(np.mean(dropext)) if dropext else float("nan"),
        "median_single_name_share_of_LS": float(np.median(worst_contrib)) if worst_contrib else float("nan"),
        "max_single_name_share_of_LS": float(np.max(worst_contrib)) if worst_contrib else float("nan"),
    }


# ----------------------------------------------------------------------------
# spearman (hand-written, no scipy) — pooled cross-day rank IC of score vs fwd.
# Computed per day then averaged (Newey-West not applied; descriptive).
# ----------------------------------------------------------------------------
def rankdata(a):
    a = np.asarray(a, dtype=float)
    order = np.argsort(a, kind="mergesort")
    ranks = np.empty(len(a), dtype=float)
    ranks[order] = np.arange(1, len(a) + 1)
    # average ties
    sa = a[order]
    i = 0
    while i < len(sa):
        j = i
        while j + 1 < len(sa) and sa[j + 1] == sa[i]:
            j += 1
        if j > i:
            avg = np.mean(ranks[order[i:j + 1]])
            ranks[order[i:j + 1]] = avg
        i = j + 1
    return ranks

def spearman(x, y):
    rx, ry = rankdata(x), rankdata(y)
    rx = rx - rx.mean(); ry = ry - ry.mean()
    denom = math.sqrt(np.sum(rx * rx) * np.sum(ry * ry))
    if denom == 0:
        return float("nan")
    return float(np.sum(rx * ry) / denom)

def daily_rank_ic(bydate, dates, score_field, horizon):
    ics = []
    for d in dates:
        g = [r for r in bydate[d] if r.get(horizon) is not None]
        if len(g) < 4:
            continue
        s = [r[score_field] for r in g]
        f = [r[horizon] for r in g]
        ic = spearman(s, f)
        if not math.isnan(ic):
            ics.append(ic)
    if not ics:
        return None
    ics = np.array(ics)
    return {
        "mean_ic": float(np.mean(ics)),
        "std_ic": float(np.std(ics, ddof=1)) if len(ics) > 1 else float("nan"),
        "n_days": len(ics),
        "icir_naive": float(np.mean(ics) / np.std(ics, ddof=1) * math.sqrt(len(ics))) if len(ics) > 1 and np.std(ics, ddof=1) > 0 else float("nan"),
        "pct_positive": float(np.mean(ics > 0)),
    }


# ----------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------
def main():
    rows, dates, bydate = load()
    out = {
        "meta": {
            "panel": PANEL,
            "n_rows": len(rows),
            "n_dates": len(dates),
            "date_range": [dates[0], dates[-1]],
            "cost_per_leg_pct": COST_PER_LEG,
            "cost_per_rebal_pct": COST_PER_REBAL,
            "n_perm": N_PERM,
            "n_boot": N_BOOT,
            "construction": "daily top/bottom tercile by score, equal-weight dollar-neutral, LS=mean(long)-mean(short)",
            "note": "18 days, 5d overlap -> effective independent obs ~3-4. EXPLORATORY, not conclusive.",
        },
        "horizons": {},
    }

    for h in HORIZONS:
        cs_series = daily_ls_series(bydate, dates, "combined_score", h)
        hres = {
            "n_qualifying_days": len(cs_series),
            "daily_rebal": daily_rebal_stats(cs_series, h),
            "nonoverlap": nonoverlap_stats(bydate, dates, "combined_score", h),
            "permutation_combined": permutation_test(bydate, dates, "combined_score", h),
            "permutation_combined_winsorized": permutation_test(bydate, dates, "combined_score", h, winsor=True),
            "permutation_momentum": permutation_test(bydate, dates, "momentum_20d_pct", h),
            "momentum_vs_combined": momentum_vs_combined(bydate, dates, h),
            "lodo_combined_gross": lodo(cs_series),
            "block_bootstrap_combined_gross": block_bootstrap(cs_series, h),
            "single_name_robustness_combined": single_name_robustness(bydate, dates, "combined_score", h),
            "rank_ic_combined": daily_rank_ic(bydate, dates, "combined_score", h),
            "rank_ic_momentum": daily_rank_ic(bydate, dates, "momentum_20d_pct", h),
            "rank_ic_sentiment": daily_rank_ic(bydate, dates, "sentiment", h),
        }
        out["horizons"][h] = hres

    outpath = os.path.join(OUTDIR, "task_c_results.json")
    with open(outpath, "w") as f:
        json.dump(out, f, indent=2)
    print("wrote", outpath)

    # console summary
    print("\n=== SUMMARY (combined_score LS) ===")
    print("%-4s %8s %8s %8s %8s %8s %8s" % ("h", "net/day_DR", "net/day_NO", "perm_p", "vs_mom", "bootCI_lo", "bootCI_hi"))
    for h in HORIZONS:
        r = out["horizons"][h]
        dr = r["daily_rebal"]["net_perday_mean"]
        no = r["nonoverlap"]["net_perday_mean"]
        pp = r["permutation_combined"]["p_right"]
        vm = r["momentum_vs_combined"]["combined_minus_momentum"]
        bb = r["block_bootstrap_combined_gross"]
        print("%-4s %8.3f %8.3f %8.3f %8.3f %8.3f %8.3f" % (
            h, dr, no, pp, vm, bb["ci95_lo"], bb["ci95_hi"]))
    return out


if __name__ == "__main__":
    main()
