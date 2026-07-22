"""S12: Final sweep for cells where ONE side has BOTH net mean>0 AND net median>0 (no tail trap).
Sweep many family cells x both sides x horizons. Require: mean>0, median>0, n>=200, maxday<0.5,
dropTop>0, q<0.10 on dev. Those (if any) go to val. Honest: expect very few / none beyond breadth dip-buy.
Also explicitly test the f5 immediate-dump shorts (n1h>=8, minsprev<=5m) — are they net>0 after cost?
"""
import numpy as np, pandas as pd
from _harness import load, seg, net_return, cell_stats, bh_fdr

df=load(); dev=seg(df,"dev").copy()
dev["minute"]=dev["ts_ms"]//60000
dev["abschg"]=dev["chg"].abs(); dev["rank_in_min"]=dev.groupby("minute")["abschg"].rank(ascending=False,method="first")

cells={
 "xwin=1":dev["xwin"]==1, "xwin=0":dev["xwin"]==0,
 "minsprev<=5":dev["mins_prev"]<=5, "minsprev<=2":dev["mins_prev"]<=2, "minsprev>120":dev["mins_prev"]>120,
 "n1h>=8":dev["n1h"]>=8, "n1h>=12":dev["n1h"]>=12, "n1h=1":dev["n1h"]==1,
 "n24h>=30":dev["n24h"]>=30, "n24h>=50":dev["n24h"]>=50, "n24h=1":dev["n24h"]==1,
 "first_day=1":dev["first_day"]==1, "first_day=0":dev["first_day"]==0,
 "breadth>=16":dev["breadth_min"]>=16, "breadth>=16&chg<=-2.5":(dev["breadth_min"]>=16)&(dev["chg"]<=-2.5),
 "breadth1h>=200":dev["breadth_1h"]>=200, "breadth1h<=10":dev["breadth_1h"]<=10,
 "hb_strongest":(dev["breadth_min"]>=6)&(dev["rank_in_min"]==1),
 "hb_weakest":(dev["breadth_min"]>=6)&(dev["rank_in_min"]==dev["grp_size"] if "grp_size" in dev else False),
 "n1h>=8&chg>0":(dev["n1h"]>=8)&(dev["chg"]>0),
 "n1h>=8&chg<0":(dev["n1h"]>=8)&(dev["chg"]<0),
}
# fix hb_weakest (need grp_size)
dev["grp_size"]=dev.groupby("minute")["abschg"].transform("size")
cells["hb_weakest"]=(dev["breadth_min"]>=6)&(dev["rank_in_min"]==dev["grp_size"])

rows=[]
for nm,m in cells.items():
    if m is False: continue
    for side in ["long","short"]:
        for ret in ["f5","f15","f60","f240"]:
            sub=dev[m].copy()
            if len(sub)<200: continue
            sub["net"]=net_return(sub[ret].values,sub["atr_pct"].values,side)
            st=cell_stats(sub,"net",nm); st.update(side=side,ret=ret)
            rows.append(st)
res=pd.DataFrame(rows)
res["q"]=bh_fdr(res["p"].values)
pd.set_option("display.width",240); pd.set_option("display.max_columns",40)

clean=res[(res["net_mean"]>0)&(res["net_median"]>0)&(res["n"]>=200)&(res["max_one_day_frac"]<0.5)&(res["mean_drop_topday"]>0)&(res["q"]<0.10)]
clean=clean.sort_values("net_mean",ascending=False)
print("=== CLEAN two-sided winners on DEV (mean>0 & median>0 & maxday<0.5 & dropTop>0 & q<0.10) ===")
if len(clean):
    print(clean[["label","side","ret","n","net_mean","net_median","winrate","q","max_one_day_frac","mean_drop_topday"]].round(3).to_string(index=False))
else:
    print("  NONE. (Only breadth dip-buy passed earlier with maxday>0.5 due to 10-10; everything else fails the no-tail-trap bar.)")

print("\n=== f5 immediate-dump shorts after cost (are they net>0?) ===")
for nm,m in [("n1h>=8",dev["n1h"]>=8),("n1h>=12",dev["n1h"]>=12),("minsprev<=2",dev["mins_prev"]<=2),("minsprev<=5",dev["mins_prev"]<=5)]:
    sub=dev[m].copy(); sub["net"]=net_return(sub["f5"].values,sub["atr_pct"].values,"short")
    st=cell_stats(sub,"net",nm)
    print(f"{nm:14s} f5 short | n={st['n']:6d} Smean={st['net_mean']:+.3f} Smed={st['net_median']:+.3f} win={st['winrate']:.3f} p={st['p']:.4f} maxday={st['max_one_day_frac']:.2f} dropTop={st['mean_drop_topday']:+.3f}")
    # gross (no cost) to see how much cost eats
    sub["g"]=-sub["f5"]
    print(f"               gross   | Gmean={sub['g'].mean():+.3f} Gmed={sub['g'].median():+.3f}  (cost eats ~{(sub['g'].mean()-st['net_mean']):.3f})")
