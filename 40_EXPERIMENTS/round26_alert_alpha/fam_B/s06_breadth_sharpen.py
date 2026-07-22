"""S06: Sharpen the surviving breadth dip-buy (C2/C3). Find the cleanest tradeable spec.
Grid over: breadth threshold {16,18,20}, chg cut {<=-2, <=-2.5, <=-3}, horizon {f60,f240,f1440}.
Pick on DEV by drop-top-day stability (not raw mean), then ONE val read of the chosen spec.
Also: cost sensitivity (these are dumping/high-atr coins -> slippage matters).
"""
import numpy as np, pandas as pd
from _harness import load, seg, net_return, cell_stats, bh_fdr

df = load()
d = seg(df,"dev").copy()

rows=[]
for bth in [16,18,20]:
    for cc in [-2,-2.5,-3]:
        for ret in ["f60","f240","f1440"]:
            m = (d["breadth_min"]>=bth)&(d["chg"]<=cc)
            sub = d[m].copy()
            if len(sub)<100:
                continue
            sub["net"]=net_return(sub[ret].values, sub["atr_pct"].values,"long")
            st=cell_stats(sub,"net",f"b{bth}_c{cc}_{ret}")
            rows.append({**st, "bth":bth,"cc":cc,"ret":ret})
res=pd.DataFrame(rows)
res["q"]=bh_fdr(res["p"].values)
# rank by drop-top-day mean (robust), require maxday<0.5 and dropTop>0
res=res.sort_values("mean_drop_topday",ascending=False)
pd.set_option("display.width",200); pd.set_option("display.max_columns",30)
print("DEV grid (sorted by drop-top-day mean = robust edge):")
print(res[["label","n","net_mean","net_median","winrate","p","q","max_one_day_frac","mean_drop_topday","n_days"]].round(3).to_string(index=False))

# choose: best dropTop with maxday<0.55 and n>=150
cand = res[(res["max_one_day_frac"]<0.55)&(res["n"]>=150)&(res["mean_drop_topday"]>0)].sort_values("mean_drop_topday",ascending=False)
print("\n--- DEV candidates with maxday<0.55, n>=150, dropTop>0 ---")
print(cand[["label","n","net_mean","net_median","winrate","p","q","max_one_day_frac","mean_drop_topday"]].round(3).to_string(index=False))

if len(cand):
    top = cand.iloc[0]
    bth,cc,ret = int(top["bth"]),top["cc"],top["ret"]
    print(f"\n=== CHOSEN: breadth>=%d & chg<=%.1f, long, %s ===" % (bth,cc,ret))
    v=seg(df,"val").copy()
    vm=(v["breadth_min"]>=bth)&(v["chg"]<=cc)
    vs=v[vm].copy(); vs["net"]=net_return(vs[ret].values,vs["atr_pct"].values,"long")
    vst=cell_stats(vs,"net","VAL chosen")
    print(f"VAL: n={vst['n']} mean={vst['net_mean']:+.3f} med={vst['net_median']:+.3f} win={vst['winrate']:.3f} "
          f"p={vst['p']:.4f} maxday={vst['max_one_day_frac']:.2f} dropTop={vst['mean_drop_topday']:+.3f} ndays={vst['n_days']}")

# Cost sensitivity on chosen-style spec (b16,c-2.5,f240): how does net move if slippage doubles?
print("\n--- Cost sensitivity: b16 & chg<=-2.5, f240, DEV (no-1010) ---")
sub=d[(d["breadth_min"]>=16)&(d["chg"]<=-2.5)&(d["day"]!="2025-10-10")].copy()
g=sub["f240"].values; a=sub["atr_pct"].values
for label,extra in [("base cost",0.0),("+0.2% RT",0.2),("+0.4% RT",0.4)]:
    base=net_return(g,a,"long")-extra
    print(f"  {label:10s}: mean={np.nanmean(base):+.3f} median={np.nanmedian(base):+.3f} n={np.sum(~np.isnan(base))}")
print(f"  mean atr_pct in this cell: {np.nanmean(a):.2f}%  (frac atr>=1.5%: {np.nanmean(a>=1.5):.2f}, >=3%: {np.nanmean(a>=3):.2f})")
