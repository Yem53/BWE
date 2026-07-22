"""S08: Final lock + full robustness for the dip-buy winner.
Spec: breadth_min>=16 AND chg<=-2.5%, side=long, horizon=f240 (hold ~4h).
Full report: dev / dev(no1010) / val. Day-level test on val. Per-day val table.
Plus: does adding atr cap / oi context help or is plain spec best (avoid overfit)?
"""
import numpy as np, pandas as pd, json
from _harness import load, seg, net_return, cell_stats, lodo, ttest_p_mean_gt0

df=load()
def cell(which, extra_mask=None):
    s=seg(df,which).copy()
    m=(s["breadth_min"]>=16)&(s["chg"]<=-2.5)
    if extra_mask is not None: m=m&extra_mask(s)
    sub=s[m].copy()
    sub["net"]=net_return(sub["f240"].values,sub["atr_pct"].values,"long")
    return sub

print("="*90); print("FINAL SPEC: breadth_min>=16 & chg<=-2.5, LONG, f240 (~4h hold)"); print("="*90)
for which in ["dev","val"]:
    sub=cell(which); st=cell_stats(sub,"net",which)
    print(f"[{which}] n={st['n']} mean={st['net_mean']:+.3f} med={st['net_median']:+.3f} win={st['winrate']:.3f} "
          f"p={st['p']:.4f} ci=[{st['ci_lo']:+.2f},{st['ci_hi']:+.2f}] maxday={st['max_one_day_frac']:.2f} dropTop={st['mean_drop_topday']:+.3f} ndays={st['n_days']}")
# dev no 1010
dn=cell("dev"); dn=dn[dn["day"]!="2025-10-10"]; st=cell_stats(dn,"net","dev_no1010")
print(f"[dev_no1010] n={st['n']} mean={st['net_mean']:+.3f} med={st['net_median']:+.3f} win={st['winrate']:.3f} p={st['p']:.4f} maxday={st['max_one_day_frac']:.2f} dropTop={st['mean_drop_topday']:+.3f}")

print("\n--- VAL day-level test (each day = 1 obs, kills within-day clustering) ---")
v=cell("val"); dmean=v.groupby("day")["net"].mean()
m,se,t,p=ttest_p_mean_gt0(dmean.values)
print(f"val per-day means: {len(dmean)} days, equal-weight mean={m:+.3f} p={p:.4f}, positive={ (dmean>0).sum()}/{len(dmean)}")
print(v.groupby("day")["net"].agg(["count","mean","median"]).round(2).to_string())

print("\n--- VAL LODO drop progressive ---")
ds=v.groupby("day")["net"].sum().sort_values(ascending=False)
for k in [0,1,2]:
    if k==0: print(f"  full: mean={v['net'].mean():+.3f} n={len(v)}")
    else:
        kept=v[~v["day"].isin(ds.head(k).index)]
        print(f"  drop top-{k} {list(ds.head(k).index)}: mean={kept['net'].mean():+.3f} n={len(kept)}")

print("\n" + "="*90); print("Overfit guard: does adding filters beat plain spec on VAL? (more filters should NOT be needed)"); print("="*90)
filters={
 "plain": None,
 "+first_day=1": lambda s: s["first_day"]==1,
 "+oimc>0.05": lambda s: s["oimc"]>0.05,
 "+breg<2 (not bull)": lambda s: s["breg"]<2,
 "+atr<2 (avoid extreme)": lambda s: s["atr_pct"]<2,
}
for nm,f in filters.items():
    vv=cell("val",f); st=cell_stats(vv,"net",nm)
    if st: print(f"  {nm:24s} val n={st['n']:4d} mean={st['net_mean']:+.3f} med={st['net_median']:+.3f} win={st['winrate']:.3f} p={st['p']:.4f}")

# also report f60 version (faster exit, smaller edge) for completeness
print("\n--- companion f60 version (faster, smaller) ---")
for which in ["dev","val"]:
    s=seg(df,which).copy(); m=(s["breadth_min"]>=16)&(s["chg"]<=-2.5); sub=s[m].copy()
    sub["net"]=net_return(sub["f60"].values,sub["atr_pct"].values,"long"); st=cell_stats(sub,"net",which)
    print(f"[{which}] f60 n={st['n']} mean={st['net_mean']:+.3f} med={st['net_median']:+.3f} win={st['winrate']:.3f} p={st['p']:.4f} maxday={st['max_one_day_frac']:.2f}")
