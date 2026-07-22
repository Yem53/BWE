"""S10: Remaining family angles — broad scan with cost, both sides, LODO, dev->val.
Angles:
 (1) Same-coin repeat: n24h buckets, n1h buckets; first_day vs repeat. Continuation vs exhaustion?
 (2) xwin (cross-window 2min confirm) vs single-window.
 (3) mins_prev (alert spacing): dense connect vs sparse.
 (4) breadth x direction interaction: high breadth + this coin's chg strongest vs weakest.
For each: pick best side per cell by dev signed mean, report dev cell_stats; flag maxday.
Collect all p for one BH-FDR table. Mark dev->val candidates (|dev mean|>0.3, n>=200, maxday<0.5).
"""
import numpy as np, pandas as pd
from _harness import load, seg, net_return, cell_stats, bh_fdr

df=load(); dev=seg(df,"dev").copy()
rows=[]
def add(frame, mask, label, angle):
    sub=frame[mask].copy()
    if len(sub)<100: return
    best=None
    for side in ["long","short"]:
        sub2=sub.copy(); sub2["net"]=net_return(sub2["f60"].values,sub2["atr_pct"].values,side)
        st=cell_stats(sub2,"net",label)
        st["side"]=side; st["angle"]=angle
        if best is None or st["net_mean"]>best["net_mean"]: best=st
    rows.append(best)

# (1) repeat
print("### Angle 1: same-coin repeat (n24h / n1h / first_day) ###")
for lo,hi,nm in [(1,1,"n24h=1"),(2,3,"n24h2-3"),(4,7,"n24h4-7"),(8,15,"n24h8-15"),(16,999,"n24h16+")]:
    add(dev,(dev["n24h"]>=lo)&(dev["n24h"]<=hi),f"n24h_{nm}","repeat_n24h")
for lo,hi,nm in [(1,1,"n1h=1"),(2,3,"n1h2-3"),(4,7,"n1h4-7"),(8,999,"n1h8+")]:
    add(dev,(dev["n1h"]>=lo)&(dev["n1h"]<=hi),f"n1h_{nm}","repeat_n1h")
add(dev,dev["first_day"]==1,"first_day=1","firstday")
add(dev,dev["first_day"]==0,"first_day=0(repeat)","firstday")

# (2) xwin
print("### Angle 2: xwin ###")
add(dev,dev["xwin"]==1,"xwin=1(confirm)","xwin")
add(dev,dev["xwin"]==0,"xwin=0(single)","xwin")

# (3) mins_prev spacing (only where there IS a prev, i.e. not NaN)
print("### Angle 3: mins_prev spacing ###")
mp=dev[dev["mins_prev"].notna()]
for lo,hi,nm in [(0,5,"<=5m"),(5,30,"5-30m"),(30,120,"30-120m"),(120,1e9,"120m+")]:
    add(mp,(mp["mins_prev"]>lo)&(mp["mins_prev"]<=hi),f"minsprev_{nm}","spacing")

# (4) breadth x direction: among same-minute alerts, is THIS coin the biggest mover or smallest?
print("### Angle 4: breadth x relative strength ###")
# compute per (ts_ms minute) rank of |chg| within that minute's alerts
dev["minute"]=(dev["ts_ms"]//60000)
dev["abschg"]=dev["chg"].abs()
dev["rank_in_min"]=dev.groupby("minute")["abschg"].rank(ascending=False,method="first")
dev["grp_size"]=dev.groupby("minute")["abschg"].transform("size")
hb=dev[dev["breadth_min"]>=6]  # only meaningful when several alerts same minute
add(hb,hb["rank_in_min"]==1,"hb_strongest_mover","breadth_rs")
add(hb,hb["rank_in_min"]>1,"hb_weaker_movers","breadth_rs")

res=pd.DataFrame(rows)
res["q"]=bh_fdr(res["p"].values)
res=res.sort_values("net_mean",ascending=False)
pd.set_option("display.width",230); pd.set_option("display.max_columns",40)
print("\n=== DEV best-side per cell (sorted by net_mean) ===")
print(res[["angle","label","side","n","net_mean","net_median","winrate","p","q","max_one_day_frac","mean_drop_topday","n_days"]].round(3).to_string(index=False))

cand=res[(res["net_mean"].abs()>0.3)&(res["n"]>=200)&(res["max_one_day_frac"]<0.5)&(res["q"]<0.10)]
print("\n=== dev->val candidates (|mean|>0.3, n>=200, maxday<0.5, q<0.10) ===")
print(cand[["angle","label","side","n","net_mean","net_median","winrate","q","max_one_day_frac"]].round(3).to_string(index=False) if len(cand) else "  NONE pass the gate on dev.")
