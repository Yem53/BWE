"""S03: Drill the surviving candidate: EXTREME breadth_min long (dip-buy on panic flush).
- Clean LODO on b16+: drop top-1 AND top-2 days, recompute.
- Does it need the alert coin to be DOWN (short-window dump) to bounce? Split by chg sign / wt.
- Horizon scan f5..f1440.
- Direction logic: is high breadth_min actually a 'market crashing' marker? check breg/dist_lo24.
DEV only. Then we'll val it in a later script.
"""
import numpy as np, pandas as pd
from _harness import load, seg, net_return, cell_stats, lodo

df = load()
d = seg(df, "dev").copy()

b16 = d[d["breadth_min"]>=16].copy()
print(f"b16+ rows (dev): {len(b16)}, days: {b16['day'].nunique()}")
print("\n--- b16+ rows per day (top 12) ---")
print(b16["day"].value_counts().head(12))

# LODO dropping progressively
b16["net"] = net_return(b16["f60"].values, b16["atr_pct"].values, "long")
day_sum = b16.groupby("day")["net"].sum().sort_values(ascending=False)
print(f"\n--- b16+ long net f60: mean={b16['net'].mean():+.3f}, n={len(b16)} ---")
print("top days by net-sum contribution:")
print(day_sum.head(6).round(1))
for k in [1,2,3]:
    drop_days = day_sum.head(k).index
    kept = b16[~b16["day"].isin(drop_days)]
    print(f"  drop top-{k} days {list(drop_days)}: mean={kept['net'].mean():+.3f} n={len(kept)} days={kept['day'].nunique()}")

print("\n" + "="*90)
print("Horizon scan: b16+ long NET by horizon")
print("="*90)
for ret in ["f5","f15","f60","f240","f1440"]:
    b16["net"] = net_return(b16[ret].values, b16["atr_pct"].values, "long")
    st = cell_stats(b16, "net", f"b16_long_{ret}")
    print(f"{ret:6s} n={st['n']} mean={st['net_mean']:+.3f} med={st['net_median']:+.3f} win={st['winrate']:.3f} "
          f"p={st['p']:.4f} maxday={st['max_one_day_frac']:.2f} dropTop={st['mean_drop_topday']:+.3f}")

print("\n" + "="*90)
print("Mechanism: is b16+ a 'market dumping' marker? breg / dist_lo24 / chg")
print("="*90)
print("breg dist among b16+:")
print(b16["breg"].value_counts(normalize=True).round(3))
print(f"\nb16+ mean chg (trigger move): {b16['chg'].mean():.2f}, median: {b16['chg'].median():.2f}")
print(f"b16+ mean dist_lo24: {b16['dist_lo24'].mean():.2f} (near 24h low?), dist_hi24: {b16['dist_hi24'].mean():.2f}")
print(f"all-dev   mean dist_lo24: {d['dist_lo24'].mean():.2f}, dist_hi24: {d['dist_hi24'].mean():.2f}")

print("\n" + "="*90)
print("Split b16+ long by trigger direction (chg>0 pump vs chg<0 dump at alert)")
print("="*90)
for nm, m in [("chg<0 (alert coin dumping)", b16["chg"]<0), ("chg>=0 (alert coin pumping)", b16["chg"]>=0)]:
    sub = b16[m].copy()
    if len(sub)<20:
        print(f"{nm}: n={len(sub)} too few"); continue
    sub["net"] = net_return(sub["f60"].values, sub["atr_pct"].values, "long")
    st = cell_stats(sub,"net",nm)
    print(f"{nm:34s} n={st['n']:5d} mean={st['net_mean']:+.3f} med={st['net_median']:+.3f} win={st['winrate']:.3f} p={st['p']:.4f} maxday={st['max_one_day_frac']:.2f} dropTop={st['mean_drop_topday']:+.3f}")
