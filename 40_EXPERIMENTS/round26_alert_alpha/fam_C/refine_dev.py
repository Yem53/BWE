"""
Dev refinements before val:
 R1 lag sensitivity (does the derivatives short edge decay with lag_s?)
 R2 fund-high x oi-up combination (two crowding signals agree)
 R3 final candidate definitions locked, with baseline-EXCESS reported
    (excess = candidate net - same-month all-alerts-short net, averaged over months,
     to strip market beta).
"""
import numpy as np, json
from harness import load, net_ret, slip_per_side, day_utc, describe, fmt, DEV_CUT
from datetime import datetime, timezone
DEV=f"ts_ms<={DEV_CUT}"
def ym(t): return datetime.fromtimestamp(t/1000,tz=timezone.utc).strftime("%Y-%m")

# baseline all-short net per month (for excess)
def baseline_monthly(ftag):
    rows=load([ftag,"atr_pct"],where=DEV)
    by={}
    for r in rows:
        if r[ftag] is None: continue
        by.setdefault(ym(r["ts_ms"]),[]).append(net_ret(r[ftag],r["atr_pct"],"short"))
    return {m:float(np.mean(v)) for m,v in by.items()}
BL1440=baseline_monthly("f1440")
BL240=baseline_monthly("f240")

def cand_excess(rows,side,ftag,ff=None):
    nets,mons,days=[],[],[]
    for r in rows:
        if r[ftag] is None: continue
        if ff and not ff(r): continue
        nets.append(net_ret(r[ftag],r["atr_pct"],side)); mons.append(ym(r["ts_ms"])); days.append(day_utc(r["ts_ms"]))
    d=describe(nets,days)
    bl = BL1440 if ftag=="f1440" else BL240
    # excess per month, then avg weighted by count
    by={}
    for v,m in zip(nets,mons): by.setdefault(m,[]).append(v)
    exs=[]; ws=[]
    for m,vv in by.items():
        if side=="short":
            exs.append(np.mean(vv)-bl.get(m,0)); ws.append(len(vv))
        else:
            # long excess vs all-long baseline ~ -all-short; skip, report raw
            exs.append(np.mean(vv)); ws.append(len(vv))
    d["excess_vs_baseline"]=float(np.average(exs,weights=ws)) if exs else None
    return d

print("="*70+"\nR1 LAG sensitivity (fund_top10 short f1440 by lag bucket)\n"+"="*70)
fall=load(["f1440","atr_pct","fund","lag_s","wt"],where=f"{DEV} AND fund IS NOT NULL")
fthr=np.quantile([r["fund"] for r in fall],0.9)
Uf=[r for r in fall if r["fund"]>=fthr]
for lo,hi in [(0,30),(30,120),(120,600),(600,1e9)]:
    nets=[];days=[]
    for r in Uf:
        if r["lag_s"] is None or not(lo<=r["lag_s"]<hi) or r["f1440"] is None: continue
        nets.append(-r["f1440"]-(0.14+2*slip_per_side(r["atr_pct"]))); days.append(day_utc(r["ts_ms"]))
    print(f"  lag {lo}-{hi}s: {fmt(describe(nets,days))}")

print("\n"+"="*70+"\nR2 fund-high x oi-up (oi_price_1h only; both crowding agree) SHORT\n"+"="*70)
oi=load(["f240","f1440","atr_pct","fund","oi_chg","chg"],where=DEV,wt="oi_price_1h")
ofthr=np.quantile([r["fund"] for r in oi if r["fund"] is not None],0.9)
print("  oi_price_1h fund-90pct thr:",round(ofthr,5))
print("  [fund>=p90 & oi_chg>0] SHORT f1440:", fmt(cand_excess(oi,"short","f1440",
      lambda r: r["fund"] is not None and r["fund"]>=ofthr and r["oi_chg"] is not None and r["oi_chg"]>0)))
print("  [fund>=p90 & oi_chg>15] SHORT f1440:", fmt(cand_excess(oi,"short","f1440",
      lambda r: r["fund"] is not None and r["fund"]>=ofthr and r["oi_chg"] is not None and r["oi_chg"]>15)))

print("\n"+"="*70+"\nR3 FINAL DEV CANDIDATES (locked defs) — net + baseline EXCESS + LODO\n"+"="*70)
CANDS={}
# C1 fund top10% short f1440 (broad)
fall2=load(["f1440","f240","atr_pct","fund"],where=f"{DEV} AND fund IS NOT NULL")
fthr2=np.quantile([r["fund"] for r in fall2],0.9)
CANDS["C1_fund_top10_short_f1440"]=("fund_p90","f1440",cand_excess(fall2,"short","f1440",lambda r,t=fthr2:r["fund"]>=t))
# C2 oi_chg>15 short f1440
oi2=load(["f1440","f240","atr_pct","oi_chg"],where=DEV,wt="oi_price_1h")
CANDS["C2_oichg_gt15_short_f1440"]=("oi_chg>15","f1440",cand_excess(oi2,"short","f1440",lambda r:r["oi_chg"] is not None and r["oi_chg"]>15))
# C3 fund top10 & revert-window short f1440
allw=load(["f1440","f240","atr_pct","fund","wt"],where=f"{DEV} AND fund IS NOT NULL")
ft3=np.quantile([r["fund"] for r in allw],0.9)
revset={"price_60s","price_10s","price_90s","price_180s_extreme"}
CANDS["C3_fund_top10_AND_revertwin_short_f1440"]=("fund_p90 & revert_win","f1440",
   cand_excess(allw,"short","f1440",lambda r,t=ft3:r["fund"]>=t and r["wt"] in revset))
# C4 fund top5 short f240 (the only viable f240, shorter hold)
fthr5=np.quantile([r["fund"] for r in fall2],0.95)
CANDS["C4_fund_top5_short_f240"]=("fund_p95","f240",cand_excess(fall2,"short","f240",lambda r,t=fthr5:r["fund"]>=t))

for k,(defn,ft,d) in CANDS.items():
    print(f"\n  {k}")
    print(f"    def: {defn} | {ft} SHORT")
    print(f"    {fmt(d)}")
    print(f"    excess_vs_all-short_baseline (beta-stripped) = {d['excess_vs_baseline']:+.3f}")

out={k:dict(defn=defn,ftag=ft,n=d['n'],net=d['mean'],median=d['median'],win=d['win'],
            t=d['t'],p=d['p'],excess=d['excess_vs_baseline'],
            lodo_drop1010=d['lodo']['drop1010_mean'],lodo_minLO=d['lodo']['min_lo_mean'],
            maxDayFrac=d['lodo']['max_day_frac']) for k,(defn,ft,d) in CANDS.items()}
with open("dev_final_candidates.json","w") as fh: json.dump(out,fh,indent=2)
print("\nsaved dev_final_candidates.json")
