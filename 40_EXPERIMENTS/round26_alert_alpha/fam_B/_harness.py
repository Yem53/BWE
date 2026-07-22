"""
Shared harness for fam_B (sequence / cluster / breadth) alpha mining.
No scipy: implements Welch t-test p-value, BH-FDR, bootstrap, LODO by hand.

Iron rules baked in:
- short = -f (we evaluate a *side*; for short, forward return is negated)
- cost = round-trip 0.14% + 妖币 slippage (atr>=1.5% -> +0.4%/side i.e. +0.8% RT;
                                          atr>=3%   -> +0.6%/side i.e. +1.2% RT)
- BH-FDR over all reported cells, only trust q<0.10
- LODO mandatory; max_one_day_frac>40% of total signed PnL contribution -> single-day artifact flag
- cell n<100 -> exploratory only
- dev select -> val confirm (same sign)
"""
import sqlite3, math
import numpy as np
import pandas as pd

DB = "/Volumes/T9/BWE/40_EXPERIMENTS/round26_alert_alpha/alert_panel.sqlite3"
DEV_MAX_TS = 1778803200000  # ts_ms<=this is dev; after is val. (holdout 05-30+ not in panel)

# ---------- data ----------
def load(cols=None):
    con = sqlite3.connect(DB)
    df = pd.read_sql("SELECT * FROM panel", con)
    con.close()
    df["day"] = pd.to_datetime(df["ts_ms"], unit="ms").dt.strftime("%Y-%m-%d")
    return df

def seg(df, which):
    if which == "dev":
        return df[df["ts_ms"] <= DEV_MAX_TS]
    elif which == "val":
        return df[df["ts_ms"] > DEV_MAX_TS]
    return df

# ---------- cost ----------
def rt_cost_pct(atr_pct):
    """round-trip cost in % (per-trade). atr_pct in percent units (e.g. 1.5 = 1.5%)."""
    base = 0.14
    a = np.where(np.isnan(atr_pct), 0.0, atr_pct)
    slip = np.where(a >= 3.0, 1.2, np.where(a >= 1.5, 0.8, 0.0))
    return base + slip

def net_return(f, atr_pct, side):
    """net forward return after cost. side='long' uses f, 'short' uses -f. cost subtracted."""
    gross = f if side == "long" else -f
    return gross - rt_cost_pct(atr_pct)

# ---------- stats (no scipy) ----------
def _norm_sf(z):
    # survival function of standard normal via erfc
    return 0.5 * math.erfc(z / math.sqrt(2.0))

def ttest_p_mean_gt0(x):
    """two-sided p-value that mean(x)==0, Welch/one-sample using normal approx (large n).
    Returns (mean, se, t, p_two_sided)."""
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    n = len(x)
    if n < 3:
        return (np.nan, np.nan, np.nan, np.nan)
    m = x.mean()
    sd = x.std(ddof=1)
    se = sd / math.sqrt(n)
    if se == 0:
        return (m, 0.0, np.inf, 0.0)
    t = m / se
    p = 2.0 * _norm_sf(abs(t))
    return (m, se, t, p)

def bh_fdr(pvals):
    """Benjamini-Hochberg q-values. pvals: list/array. Returns q array same order."""
    p = np.asarray(pvals, float)
    ok = ~np.isnan(p)
    q = np.full_like(p, np.nan)
    idx = np.where(ok)[0]
    if len(idx) == 0:
        return q
    pp = p[idx]
    order = np.argsort(pp)
    m = len(pp)
    ranked = pp[order]
    qv = ranked * m / (np.arange(m) + 1)
    # enforce monotonicity from the largest
    qv = np.minimum.accumulate(qv[::-1])[::-1]
    qv = np.minimum(qv, 1.0)
    out = np.empty(m)
    out[order] = qv
    q[idx] = out
    return q

def boot_ci(x, n_boot=2000, seed=0):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    if len(x) < 3:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    means = x[rng.integers(0, len(x), size=(n_boot, len(x)))].mean(axis=1)
    return (np.percentile(means, 2.5), np.percentile(means, 97.5))

# ---------- LODO ----------
def lodo(df_cell, ret_col):
    """Leave-one-day-out. Returns dict with:
       max_one_day_frac: fraction of TOTAL signed PnL contributed by the single biggest day
                         (computed on sum of returns; uses abs to gauge concentration of |contribution|),
       worst_drop_mean: the mean when we drop the single day that most inflates the mean,
       n_days, per-day means.
    Convention for max_one_day_frac: sum of returns per day; the day whose sum has the
    largest absolute value / total absolute sum across days. >0.40 -> single-day artifact."""
    g = df_cell.groupby("day")[ret_col]
    day_sum = g.sum()
    day_mean = g.mean()
    day_n = g.size()
    total_sum = df_cell[ret_col].sum()
    # concentration: which day dominates the net sum
    abs_total = day_sum.abs().sum()
    max_one_day_frac = (day_sum.abs().max() / abs_total) if abs_total > 0 else np.nan
    # also: drop the most-positive-sum day, recompute overall mean (robustness of edge)
    if len(day_sum) >= 2:
        top_day = day_sum.idxmax()
        kept = df_cell[df_cell["day"] != top_day]
        mean_drop_top = kept[ret_col].mean()
    else:
        mean_drop_top = np.nan
    return {
        "n_days": int(len(day_sum)),
        "overall_mean": float(df_cell[ret_col].mean()),
        "mean_drop_topday": float(mean_drop_top) if mean_drop_top==mean_drop_top else np.nan,
        "max_one_day_frac": float(max_one_day_frac) if max_one_day_frac==max_one_day_frac else np.nan,
        "day_sum_top": float(day_sum.max()),
        "day_sum_top_date": str(day_sum.idxmax()) if len(day_sum)>0 else "",
        "total_sum": float(total_sum),
    }

def cell_stats(df_cell, ret_col, label=""):
    x = df_cell[ret_col].dropna().values
    n = len(x)
    if n == 0:
        return None
    m, se, t, p = ttest_p_mean_gt0(x)
    med = float(np.median(x))
    win = float((x > 0).mean())
    lo, hi = boot_ci(x)
    ld = lodo(df_cell.dropna(subset=[ret_col]), ret_col)
    return {
        "label": label, "n": int(n),
        "net_mean": float(m), "net_median": med, "winrate": win,
        "se": float(se) if se==se else np.nan, "t": float(t) if t==t else np.nan, "p": float(p) if p==p else np.nan,
        "ci_lo": float(lo) if lo==lo else np.nan, "ci_hi": float(hi) if hi==hi else np.nan,
        "max_one_day_frac": ld["max_one_day_frac"], "mean_drop_topday": ld["mean_drop_topday"],
        "n_days": ld["n_days"], "day_sum_top_date": ld["day_sum_top_date"],
    }

if __name__ == "__main__":
    df = load()
    print("rows", len(df), "dev", len(seg(df,'dev')), "val", len(seg(df,'val')))
    print("days dev", seg(df,'dev')['day'].nunique())
