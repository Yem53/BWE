"""
VAL CONFIRMATION — one shot. Locked candidate defs from dev. ts_ms>DEV_CUT.
Thresholds are FROZEN from dev (computed on dev fund/quantiles) to avoid leakage.
Report val: n, net, median, win, t, p, LODO, and excess vs val all-short baseline.
Holdout 05-30+ is NOT in this DB (val max=05-29); main agent reveals separately.
"""
import numpy as np, json
from harness import load, net_ret, slip_per_side, day_utc, describe, fmt, DEV_CUT
from datetime import datetime, timezone
VAL=f"ts_ms>{DEV_CUT}"
def ym(t): return datetime.fromtimestamp(t/1000,tz=timezone.utc).strftime("%Y-%m")

# FROZEN dev thresholds (recompute on dev, do NOT refit on val)
DEVW=f"ts_ms<={DEV_CUT}"
dev_fund=[r["fund"] for r in load(["fund"],where=f"{DEVW} AND fund IS NOT NULL")]
FTHR_P90=float(np.quantile(dev_fund,0.9))
FTHR_P95=float(np.quantile(dev_fund,0.95))
print(f"FROZEN dev thresholds: fund_p90={FTHR_P90:.6f} fund_p95={FTHR_P95:.6f}")

# val all-short baseline (for excess)
def baseline_monthly(ftag):
    rows=load([ftag,"atr_pct"],where=VAL)
    by={}
    for r in rows:
        if r[ftag] is None: continue
        by.setdefault(ym(r["ts_ms"]),[]).append(net_ret(r[ftag],r["atr_pct"],"short"))
    overall=float(np.mean([net_ret(r[ftag],r["atr_pct"],"short") for r in rows if r[ftag] is not None]))
    return {m:float(np.mean(v)) for m,v in by.items()}, overall
BL1440,BL1440_all=baseline_monthly("f1440")
BL240,BL240_all=baseline_monthly("f240")
print(f"VAL all-short baseline net: f240={BL240_all:.3f} f1440={BL1440_all:.3f}")
print(f"VAL months present: {sorted(BL1440.keys())}")

def cand(rows,side,ftag,ff,blm):
    nets,days,mons=[],[],[]
    for r in rows:
        if r[ftag] is None: continue
        if ff and not ff(r): continue
        nets.append(net_ret(r[ftag],r["atr_pct"],side)); days.append(day_utc(r["ts_ms"])); mons.append(ym(r["ts_ms"]))
    d=describe(nets,days)
    by={}
    for v,m in zip(nets,mons): by.setdefault(m,[]).append(v)
    exs=[];ws=[]
    for m,vv in by.items():
        exs.append(np.mean(vv)-blm.get(m,0)); ws.append(len(vv))
    d["excess"]=float(np.average(exs,weights=ws)) if exs else None
    return d

print("\n"+"="*70+"\nVAL RESULTS (frozen defs)\n"+"="*70)
RES={}

# C1 fund top10 short f1440
fall=load(["f1440","f240","atr_pct","fund","wt"],where=f"{VAL} AND fund IS NOT NULL")
RES["C1_fund_top10_short_f1440"]=cand(fall,"short","f1440",lambda r:r["fund"]>=FTHR_P90,BL1440)
# C4 fund top5 short f240
RES["C4_fund_top5_short_f240"]=cand(fall,"short","f240",lambda r:r["fund"]>=FTHR_P95,BL240)
# C3 fund top10 & revert win short f1440
revset={"price_60s","price_10s","price_90s","price_180s_extreme"}
RES["C3_fund_top10_AND_revertwin_short_f1440"]=cand(fall,"short","f1440",
    lambda r:r["fund"]>=FTHR_P90 and r["wt"] in revset,BL1440)
# C2 oi_chg>15 short f1440
oi=load(["f1440","f240","atr_pct","oi_chg"],where=VAL,wt="oi_price_1h")
RES["C2_oichg_gt15_short_f1440"]=cand(oi,"short","f1440",lambda r:r["oi_chg"] is not None and r["oi_chg"]>15,BL1440)

# also val time-stop check: does 1440 still beat 240 on fund_top10?
print("VAL time-stop sanity (fund_top10):")
for ftag,bl in [("f240",BL240),("f1440",BL1440)]:
    d=cand(fall,"short",ftag,lambda r:r["fund"]>=FTHR_P90,bl)
    print(f"   {ftag}: {fmt(d)}  excess={d['excess']:+.3f}")

print("\n--- candidate confirmations ---")
for k,d in RES.items():
    print(f"\n  {k}")
    print(f"    {fmt(d)}")
    print(f"    excess_vs_val_baseline = {d['excess']:+.3f}")

out={k:dict(n=d['n'],net=d['mean'],median=d['median'],win=d['win'],t=d['t'],p=d['p'],
            excess=d['excess'],
            lodo_drop1010=d['lodo']['drop1010_mean'] if d.get('lodo') else None,
            lodo_minLO=d['lodo']['min_lo_mean'] if d.get('lodo') else None,
            maxDayFrac=d['lodo']['max_day_frac'] if d.get('lodo') else None) for k,d in RES.items()}
out["_frozen_thresholds"]={"fund_p90":FTHR_P90,"fund_p95":FTHR_P95}
out["_val_baseline"]={"f240":BL240_all,"f1440":BL1440_all,"months":sorted(BL1440.keys())}
with open("val_confirm_results.json","w") as fh: json.dump(out,fh,indent=2)
print("\nsaved val_confirm_results.json")
