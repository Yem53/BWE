"""S05: VAL confirmation of the breadth dip-buy candidate (ONE shot on val).
Candidate locked from dev:
  C1: breadth_min>=16, side=long, f60   (extreme-breadth panic dip-buy)
  C2: breadth_min>=16 & chg<=-2.5, long, f60  (the cleaner control-validated version, maxday 0.33 on dev)
  C3: breadth_min>=16, long, f240
Report dev vs val side by side. Same sign = confirmed.
Also val day composition (is val dominated by one crash day too?).
"""
import numpy as np, pandas as pd
from _harness import load, seg, net_return, cell_stats

df = load()

def run(which, mask_fn, ret, side, label):
    s = seg(df, which).copy()
    sub = s[mask_fn(s)].copy()
    sub["net"] = net_return(sub[ret].values, sub["atr_pct"].values, side)
    st = cell_stats(sub, "net", label)
    if st is None:
        print(f"[{which}] {label}: EMPTY"); return None
    print(f"[{which:3s}] {label:34s} n={st['n']:5d} mean={st['net_mean']:+.3f} med={st['net_median']:+.3f} "
          f"win={st['winrate']:.3f} p={st['p']:.4f} maxday={st['max_one_day_frac']:.2f} dropTop={st['mean_drop_topday']:+.3f} ndays={st['n_days']}")
    return st

cands = [
    ("C1 b16+ long f60",       lambda s: s["breadth_min"]>=16, "f60",  "long"),
    ("C2 b16+ & chg<=-2.5 f60", lambda s: (s["breadth_min"]>=16)&(s["chg"]<=-2.5), "f60", "long"),
    ("C3 b16+ long f240",      lambda s: s["breadth_min"]>=16, "f240", "long"),
    ("C4 b11+ long f60",       lambda s: s["breadth_min"]>=11, "f60",  "long"),
]
for label, mf, ret, side in cands:
    run("dev", mf, ret, side, label)
    run("val", mf, ret, side, label)
    print()

print("="*90)
print("VAL day composition for b16+ (is val also one-crash-day dominated?)")
print("="*90)
v = seg(df,"val").copy()
vb = v[v["breadth_min"]>=16].copy()
print(f"val b16+ rows: {len(vb)}, days: {vb['day'].nunique()}")
print(vb["day"].value_counts().head(10))
vb["net"]=net_return(vb["f60"].values, vb["atr_pct"].values,"long")
print("\nval b16+ long net60 per-day mean:")
print(vb.groupby("day")["net"].agg(["count","mean"]).round(2).to_string())
