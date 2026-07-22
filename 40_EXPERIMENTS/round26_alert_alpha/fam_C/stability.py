"""
Stability / beta-decontamination check for top fam-C candidates.
Key insight from monthly baseline: f1440 short carries heavy market beta
(all-alerts short f1440 gross ranges -1.2% to +14.8% by month).
So for any candidate we report:
  - net mean (cost-adj)
  - EXCESS over same-window all-alerts-short baseline (alpha vs beta)
  - monthly net means (is it stable or one-month-driven?)
  - LODO
This separates real alert alpha from "short during down market".
"""
import numpy as np, json
from harness import load, net_ret, day_utc, describe, fmt, DEV_CUT
from datetime import datetime, timezone

DEV = f"ts_ms<={DEV_CUT}"

def ym(ts_ms):
    return datetime.fromtimestamp(ts_ms/1000, tz=timezone.utc).strftime("%Y-%m")

def baseline_short(ftag, where):
    """all-alerts short NET baseline per month for given ftag (cost-adj)."""
    rows = load([ftag,"atr_pct"], where=where)
    by = {}
    for r in rows:
        if r[ftag] is None: continue
        by.setdefault(ym(r["ts_ms"]),[]).append(net_ret(r[ftag], r["atr_pct"], "short"))
    return {m: float(np.mean(v)) for m,v in by.items()}, \
           float(np.mean([net_ret(r[ftag],r["atr_pct"],"short") for r in rows if r[ftag] is not None]))

def cand(name, rows, side, ftag, ff=None):
    nets, days, mons = [], [], []
    for r in rows:
        if r[ftag] is None: continue
        if ff and not ff(r): continue
        nets.append(net_ret(r[ftag], r["atr_pct"], side))
        days.append(day_utc(r["ts_ms"]))
        mons.append(ym(r["ts_ms"]))
    d = describe(nets, days)
    # monthly
    by = {}
    for v,m in zip(nets,mons): by.setdefault(m,[]).append(v)
    monthly = {m:(round(float(np.mean(v)),2), len(v)) for m,v in sorted(by.items())}
    d["monthly"] = monthly
    print(f"\n### {name} [{side} {ftag}]")
    print(f"   {fmt(d)}")
    print(f"   monthly net (mean,n): {monthly}")
    pos_months = sum(1 for m,(mu,n) in monthly.items() if mu>0 and n>=30)
    tot_months = sum(1 for m,(mu,n) in monthly.items() if n>=30)
    print(f"   months net>0 (n>=30): {pos_months}/{tot_months}")
    return d

print("="*70)
print("BASELINE all-alerts SHORT net by month (dev):")
bl240, bl240_all = baseline_short("f240", DEV)
bl1440, bl1440_all = baseline_short("f1440", DEV)
print(f"  f240  all-short net overall = {bl240_all:.3f}  monthly={ {m:round(v,2) for m,v in bl240.items()} }")
print(f"  f1440 all-short net overall = {bl1440_all:.3f}  monthly={ {m:round(v,2) for m,v in bl1440.items()} }")

# ---- Candidates ----
print("\n"+"="*70+"\nTOP CANDIDATES (dev) w/ monthly stability & baseline excess\n"+"="*70)

# 1. fund top10% short f1440 & f240
fall = load(["f240","f1440","atr_pct","fund"], where=f"{DEV} AND fund IS NOT NULL")
fv = np.quantile([r["fund"] for r in fall],[0.9,0.95])
cand("fund top10% SHORT f1440", fall, "short","f1440", lambda r,t=fv[0]: r["fund"]>=t)
cand("fund top10% SHORT f240",  fall, "short","f240",  lambda r,t=fv[0]: r["fund"]>=t)
cand("fund top5%  SHORT f240",  fall, "short","f240",  lambda r,t=fv[1]: r["fund"]>=t)

# 2. oi_chg>+15 short (oi_price_1h)
oi = load(["f240","f1440","atr_pct","oi_chg","chg"], where=DEV, wt="oi_price_1h")
cand("oi_chg>+15% SHORT f1440", oi, "short","f1440", lambda r: r["oi_chg"] is not None and r["oi_chg"]>15)
cand("oi_chg>+15% SHORT f240",  oi, "short","f240",  lambda r: r["oi_chg"] is not None and r["oi_chg"]>15)
# combine: price_up & OI_up (crowded longs) is the cleaner mechanism
cand("price_up & OI_up SHORT f1440", oi, "short","f1440", lambda r: r["chg"] and r["chg"]>0 and r["oi_chg"] is not None and r["oi_chg"]>0)

# 3. revert windows atr<1.5 short
rev = load(["f240","f1440","atr_pct"], where=DEV, wt=["price_60s","price_10s","price_90s","price_180s_extreme"])
cand("revert atr<1.5 SHORT f1440", rev, "short","f1440", lambda r: r["atr_pct"] is not None and r["atr_pct"]<1.5)
cand("revert atr<1.5 SHORT f240",  rev, "short","f240",  lambda r: r["atr_pct"] is not None and r["atr_pct"]<1.5)

# 4. COMBINE fund-high AND revert-window? small but maybe pure
allw = load(["f240","f1440","atr_pct","fund","wt"], where=f"{DEV} AND fund IS NOT NULL")
ft = np.quantile([r["fund"] for r in allw],0.9)
revset = {"price_60s","price_10s","price_90s","price_180s_extreme"}
cand("fund-top10 & revert-win SHORT f1440", allw, "short","f1440",
     lambda r,t=ft: r["fund"]>=t and r["wt"] in revset)
cand("fund-top10 & revert-win SHORT f240", allw, "short","f240",
     lambda r,t=ft: r["fund"]>=t and r["wt"] in revset)
