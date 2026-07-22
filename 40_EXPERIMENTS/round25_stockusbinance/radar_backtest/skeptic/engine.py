"""
Adversarial re-verification engine for radar neutral long/short finding.
numpy only (no scipy). Hand-written spearman + permutation test.

Iron rules:
- LS construction: per day, sort by score desc, long top tercile (n//3),
  short bottom tercile (n//3), equal-weight dollar-neutral.
- LS day return = mean(long fwd) - mean(short fwd). Short uses MEAN (anti left-tail).
- Cost: perp round-trip 0.10%/leg. LS = both legs = 0.20%/rebalance.
  equal-weight long benchmark = 0.10%/rebalance.
- Only use days where horizon fN is fully populated (null = all-or-nothing per day).
- Effective N tiny (18 cal days, 5d overlap -> ~3-4 independent). Everything exploratory.
"""
import json
import numpy as np

PANEL = "/Volumes/T9/BWE/40_EXPERIMENTS/round25_stockusbinance/radar_panel.jsonl"
HORIZONS = ["f1", "f2", "f3", "f5"]
HOLD = {"f1": 1, "f2": 2, "f3": 3, "f5": 5}
COST_LEG = 0.10  # % per leg round trip


def load():
    rows = [json.loads(l) for l in open(PANEL)]
    by_date = {}
    for r in rows:
        by_date.setdefault(r["date"], []).append(r)
    dates = sorted(by_date)
    return rows, by_date, dates


def usable_days(by_date, dates, h):
    """Days where every row has non-null fN."""
    out = []
    for d in dates:
        sub = by_date[d]
        if all(r.get(h) is not None for r in sub) and len(sub) >= 3:
            out.append(d)
    return out


def ls_day(sub, score_key, h):
    """One day's LS gross return (%) and the long/short member fwd lists.
    sort desc by score; long top n//3, short bottom n//3."""
    s = sorted(sub, key=lambda r: r[score_key], reverse=True)
    n = len(s)
    k = n // 3
    if k < 1:
        return None
    longs = s[:k]
    shorts = s[-k:]
    lf = np.array([r[h] for r in longs], float)
    sf = np.array([r[h] for r in shorts], float)
    gross = lf.mean() - sf.mean()  # short uses MEAN
    return {"gross": gross, "lf": lf, "sf": sf, "k": k,
            "long_t": [r["ticker"] for r in longs],
            "short_t": [r["ticker"] for r in shorts]}


def eqw_long_day(sub, h):
    """Equal-weight whole-universe long gross return (pure beta)."""
    return np.mean([r[h] for r in sub])


def per_day_net_pct(by_date, dates, score_key, h):
    """Returns list of (date, net_perday_pct, gross_perday_pct, detail) using
    daily-rebal (overlap) convention: per-rebalance cost amortized over hold days.
    LS cost = 0.20% per rebalance; spread over HOLD days for a per-day figure."""
    days = usable_days(by_date, dates, h)
    hold = HOLD[h]
    out = []
    for d in days:
        ls = ls_day(by_date[d], score_key, h)
        if ls is None:
            continue
        gross = ls["gross"]
        net_total = gross - 2 * COST_LEG  # both legs round trip
        net_perday = net_total / hold
        gross_perday = gross / hold
        out.append({"date": d, "net_perday": net_perday,
                    "gross_perday": gross_perday, "net_total": net_total,
                    "gross_total": gross, "detail": ls})
    return out


def eqw_long_net_pct(by_date, dates, h):
    days = usable_days(by_date, dates, h)
    hold = HOLD[h]
    out = []
    for d in days:
        g = eqw_long_day(by_date[d], h)
        net_total = g - COST_LEG  # one leg
        out.append({"date": d, "net_perday": net_total / hold,
                    "gross_perday": g / hold, "net_total": net_total})
    return out


def nonoverlap_days(days, hold):
    """Pick every `hold`-th day so holding periods don't overlap."""
    return days[::hold]


# ---- hand-written stats ----
def rankdata(a):
    a = np.asarray(a, float)
    order = a.argsort()
    ranks = np.empty(len(a), float)
    ranks[order] = np.arange(1, len(a) + 1)
    # average ties
    _, inv, cnt = np.unique(a, return_inverse=True, return_counts=True)
    # compute average rank per unique value
    sums = np.zeros(len(cnt))
    np.add.at(sums, inv, ranks)
    avg = sums / cnt
    return avg[inv]


def spearman(x, y):
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    if len(x) < 3:
        return np.nan
    rx = rankdata(x)
    ry = rankdata(y)
    rx -= rx.mean()
    ry -= ry.mean()
    denom = np.sqrt((rx**2).sum() * (ry**2).sum())
    if denom == 0:
        return np.nan
    return float((rx * ry).sum() / denom)


def perm_test_mean(vals, n_perm=20000, seed=0):
    """Two-sided sign-flip permutation test that mean(vals)==0.
    Appropriate for paired LS day returns (sign flip = randomizing long/short label)."""
    rng = np.random.default_rng(seed)
    vals = np.asarray(vals, float)
    n = len(vals)
    obs = abs(vals.mean())
    if n == 0:
        return np.nan, np.nan
    cnt = 0
    for _ in range(n_perm):
        signs = rng.integers(0, 2, n) * 2 - 1
        if abs((vals * signs).mean()) >= obs - 1e-12:
            cnt += 1
    return obs * np.sign(vals.mean()), (cnt + 1) / (n_perm + 1)


def tstat(vals):
    vals = np.asarray(vals, float)
    n = len(vals)
    if n < 2:
        return np.nan
    sd = vals.std(ddof=1)
    if sd == 0:
        return np.nan
    return float(vals.mean() / (sd / np.sqrt(n)))
