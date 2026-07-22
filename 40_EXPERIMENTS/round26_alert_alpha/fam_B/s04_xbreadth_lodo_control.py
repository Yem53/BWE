"""S04: Rigorous LODO + control for the b16+ dip-buy candidate.
Q1: Of the 16 non-10-10 days, how many have positive long-net mean? (sign consistency)
Q2: CONTROL: is the edge from breadth specifically, or just 'alert coin is down a lot'?
    Compare b16+ long vs a chg-matched (chg<=-2.5%) but LOW-breadth (<=5) control.
Q3: Trimmed mean (drop top & bottom 5% of returns) to kill outlier dependence.
DEV only.
"""
import numpy as np, pandas as pd
from _harness import load, seg, net_return, cell_stats

df = load()
d = seg(df, "dev").copy()
d["net60"] = net_return(d["f60"].values, d["atr_pct"].values, "long")
d["net240"] = net_return(d["f240"].values, d["atr_pct"].values, "long")

b16 = d[d["breadth_min"]>=16].copy()
b16_no = b16[b16["day"]!="2025-10-10"].copy()

print("="*90)
print("Q1: b16+ long net60, per-day means EXCLUDING 10-10 (sign consistency)")
print("="*90)
dm = b16_no.groupby("day")["net60"].agg(["count","mean","median"]).sort_values("mean")
print(dm.round(2).to_string())
print(f"\n{len(dm)} days. positive-mean: {(dm['mean']>0).sum()} ({(dm['mean']>0).mean()*100:.0f}%), "
      f"positive-median: {(dm['median']>0).sum()} ({(dm['median']>0).mean()*100:.0f}%)")
# day-level t-test: are per-day means > 0 on average (each day = 1 obs, kills within-day clustering)
day_means = dm["mean"].values
from _harness import ttest_p_mean_gt0
m,se,t,p = ttest_p_mean_gt0(day_means)
print(f"DAY-LEVEL test (16 day-means, equal weight): mean={m:+.3f} p={p:.4f}  <-- robust to within-day clustering")

print("\n" + "="*90)
print("Q2: CONTROL — chg<=-2.5% dump, but breadth_min<=5 (low) vs b16+ (high). Same dump, diff breadth.")
print("="*90)
for nm, m in [
    ("HIGH breadth b16+ (no1010), chg<=-2.5", (d["breadth_min"]>=16)&(d["chg"]<=-2.5)&(d["day"]!="2025-10-10")),
    ("LOW breadth <=5   (no1010), chg<=-2.5", (d["breadth_min"]<=5)&(d["chg"]<=-2.5)&(d["day"]!="2025-10-10")),
    ("MID breadth 6-15  (no1010), chg<=-2.5", (d["breadth_min"]>=6)&(d["breadth_min"]<=15)&(d["chg"]<=-2.5)&(d["day"]!="2025-10-10")),
]:
    sub = d[m]
    st = cell_stats(sub, "net60", nm)
    print(f"{nm:42s} n={st['n']:6d} mean={st['net_mean']:+.3f} med={st['net_median']:+.3f} win={st['winrate']:.3f} p={st['p']:.4f} maxday={st['max_one_day_frac']:.2f} dropTop={st['mean_drop_topday']:+.3f}")

print("\n" + "="*90)
print("Q3: Trimmed mean (5% each tail) of b16+ long net60 — outlier independence")
print("="*90)
for nm, sub in [("b16+ ALL (with 1010)", b16), ("b16+ no-1010", b16_no)]:
    x = np.sort(sub["net60"].dropna().values)
    k = int(len(x)*0.05)
    tm = x[k:len(x)-k].mean()
    print(f"{nm:22s}: raw_mean={x.mean():+.3f}  trimmed5%_mean={tm:+.3f}  median={np.median(x):+.3f}  n={len(x)}")

print("\n" + "="*90)
print("Q4: f240 day-level robustness (no-1010)")
print("="*90)
dm2 = b16_no.groupby("day")["net240"].mean()
m,se,t,p = ttest_p_mean_gt0(dm2.values)
print(f"f240 DAY-LEVEL (16 days): mean={m:+.3f} p={p:.4f} pos_days={(dm2>0).sum()}/{len(dm2)}")
