"""
Fam C harness — microstructure / OI / funding / basis / exit.
Reusable stats core: cost model, BH-FDR, LODO, dev/val split.

Iron rules:
  1. SHORT = -f ; short uses mean.
  2. Cost = round-trip 0.14% + yaobi slippage: atr>=1.5% -> +0.4%/side, atr>=3% -> +0.6%/side.
     (per-side slippage applied on BOTH legs => *2)
  3. BH-FDR over reported cells, q<0.10.
  4. LODO mandatory (drop 2025-10-10; if any single day frac>40% of trades -> flag/kill).
  5. n<100 = exploratory only.
  6. dev pick -> val confirm once.

Data: ../alert_panel.sqlite3 table panel.
"""
import sqlite3, numpy as np, math, json, os
from datetime import datetime, timezone

DB = os.path.join(os.path.dirname(__file__), "..", "alert_panel.sqlite3")
DEV_CUT = 1778803200000  # ts_ms <= -> dev, else val
# holdout 05-30+ is NOT in this DB's val (val max = 05-29). Main agent reveals separately.

def load(cols, where="1", wt=None):
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    wcl = where
    if wt is not None:
        if isinstance(wt, (list, tuple)):
            inlist = ",".join("'%s'" % w for w in wt)
            wcl = f"({where}) AND wt IN ({inlist})"
        else:
            wcl = f"({where}) AND wt='{wt}'"
    q = f"SELECT {','.join(cols)}, ts_ms FROM panel WHERE {wcl}"
    rows = con.execute(q).fetchall()
    con.close()
    return rows

def day_utc(ts_ms):
    return datetime.fromtimestamp(ts_ms/1000, tz=timezone.utc).strftime("%Y-%m-%d")

def slip_per_side(atr):
    """yaobi slippage per side, in pct (0.4 => 0.4%)."""
    if atr is None: atr = 0.0
    if atr >= 3.0: return 0.6
    if atr >= 1.5: return 0.4
    return 0.0

def net_ret(f_long, atr, side):
    """Net return after costs, in pct units (same units as f).
       side='short' uses -f. Cost = 0.14 round-trip + 2*slip_per_side."""
    gross = (-f_long if side == "short" else f_long)
    cost = 0.14 + 2.0 * slip_per_side(atr)
    return gross - cost

# ---- stats ----
def tstat(x):
    x = np.asarray(x, float)
    n = len(x)
    if n < 2: return 0.0, 1.0, n
    m = x.mean(); sd = x.std(ddof=1)
    if sd == 0: return 0.0, 1.0, n
    t = m / (sd / math.sqrt(n))
    # two-sided p via normal approx (n large here); use survival of |t|
    from math import erfc
    p = erfc(abs(t)/math.sqrt(2))
    return t, p, n

def bh_fdr(pvals, q=0.10):
    """Return boolean array: which pass BH-FDR at level q. pvals: list."""
    p = np.asarray(pvals, float)
    m = len(p)
    order = np.argsort(p)
    passed = np.zeros(m, bool)
    thresh = 0.0
    for i, idx in enumerate(order):
        if p[idx] <= (i+1)/m * q:
            thresh = (i+1)/m * q
    passed = p <= thresh
    return passed, thresh

def lodo(net_by_day):
    """net_by_day: dict day->list of net returns.
       Returns: full_mean, min_leaveout_mean (worst day dropped), worst_day,
                max_day_frac, drop_1010_mean."""
    days = sorted(net_by_day.keys())
    all_n = np.concatenate([np.asarray(net_by_day[d]) for d in days]) if days else np.array([])
    total = len(all_n)
    if total == 0:
        return None
    full_mean = all_n.mean()
    # leave-one-day-out: recompute mean dropping each day, report worst (lowest) resulting mean
    lo_means = {}
    for d in days:
        rest = np.concatenate([np.asarray(net_by_day[x]) for x in days if x != d]) if len(days) > 1 else np.array([])
        lo_means[d] = rest.mean() if len(rest) else float('nan')
    # the day whose removal hurts least info: we care if one day carries all alpha
    # report the lowest LODO mean (most fragile) and which day removed gives it
    worst_day = min(lo_means, key=lambda d: lo_means[d]) if lo_means else None
    min_lo = lo_means[worst_day] if worst_day else float('nan')
    # day fractions
    fracs = {d: len(net_by_day[d])/total for d in days}
    max_day = max(fracs, key=lambda d: fracs[d])
    max_frac = fracs[max_day]
    # drop 2025-10-10 specifically
    d1010 = "2025-10-10"
    if d1010 in net_by_day:
        rest = np.concatenate([np.asarray(net_by_day[x]) for x in days if x != d1010])
        drop1010 = rest.mean() if len(rest) else float('nan')
    else:
        drop1010 = full_mean
    return dict(full_mean=full_mean, min_lo_mean=min_lo, min_lo_day=worst_day,
                max_day=max_day, max_day_frac=max_frac, drop1010_mean=drop1010,
                n=total)

def describe(nets, days=None):
    """nets: list/array of net returns. days: parallel list of day strings for LODO."""
    a = np.asarray(nets, float)
    n = len(a)
    if n == 0:
        return dict(n=0)
    t, p, _ = tstat(a)
    out = dict(n=n, mean=float(a.mean()), median=float(np.median(a)),
               win=float((a > 0).mean()), t=float(t), p=float(p),
               std=float(a.std(ddof=1)) if n > 1 else 0.0)
    if days is not None:
        nbd = {}
        for v, d in zip(a, days):
            nbd.setdefault(d, []).append(v)
        out["lodo"] = lodo(nbd)
    return out

def fmt(d):
    if d.get("n", 0) == 0:
        return "n=0"
    s = f"n={d['n']} net={d['mean']:.3f} med={d['median']:.3f} win={d['win']*100:.1f}% t={d['t']:.2f} p={d['p']:.4f}"
    if "lodo" in d and d["lodo"]:
        l = d["lodo"]
        s += f" | LODO drop1010={l['drop1010_mean']:.3f} minLO={l['min_lo_mean']:.3f}(rm {l['min_lo_day']}) maxDayFrac={l['max_day_frac']*100:.0f}%"
    return s

if __name__ == "__main__":
    # smoke test
    rows = load(["f240","atr_pct","wt"], wt="price_60s")
    nets = [net_ret(r["f240"], r["atr_pct"], "short") for r in rows if r["f240"] is not None]
    days = [day_utc(r["ts_ms"]) for r in rows if r["f240"] is not None]
    print("price_60s short f240:", fmt(describe(nets, days)))
