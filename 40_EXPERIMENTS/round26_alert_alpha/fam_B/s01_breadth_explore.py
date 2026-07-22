"""S01: Reproduce the 'breadth lit' headline and stress it.
breadth_min high (whole-market piling in) -> later f60 mean +1.33% vs low +0.03%?
Step 1: reproduce GROSS long f60 by breadth bucket (no cost) to confirm the claim.
Step 2: same but NET (cost) + by side.
Step 3: LODO each bucket -> is it 2025-10-10 single-day?
All on DEV only.
"""
import numpy as np, pandas as pd
from _harness import load, seg, net_return, lodo

df = load()
d = seg(df, "dev").copy()

# breadth_min buckets
def bucket(b):
    if b <= 2: return "1_lo(1-2)"
    if b <= 5: return "2_mid(3-5)"
    if b <= 10: return "3_hi(6-10)"
    return "4_xhi(11+)"
d["bb"] = d["breadth_min"].apply(bucket)

print("="*70)
print("STEP1: GROSS long f60 by breadth_min bucket (reproduce headline, no cost)")
print("="*70)
g = d.groupby("bb")["f60"].agg(["count","mean","median"])
print(g.round(3))

print("\n" + "="*70)
print("STEP2: NET f60 by bucket x side (with cost)")
print("="*70)
for side in ["long","short"]:
    d["net"] = net_return(d["f60"].values, d["atr_pct"].values, side)
    g = d.groupby("bb")["net"].agg(["count","mean","median"]).round(3)
    g["winrate"] = d.groupby("bb").apply(lambda x: (x["net"]>0).mean(), include_groups=False).round(3)
    print(f"\n--- side={side} ---")
    print(g)

print("\n" + "="*70)
print("STEP3: LODO on the high-breadth long bucket (the headline) — GROSS f60")
print("="*70)
hi = d[d["breadth_min"]>=11].dropna(subset=["f60"]).copy()
print(f"n(breadth>=11) = {len(hi)}")
ld = lodo(hi, "f60")
for k,v in ld.items(): print(f"  {k}: {v}")

# top contributing days
print("\n--- top 8 days by sum(f60) in breadth>=11 bucket ---")
ds = hi.groupby("day")["f60"].agg(["count","sum","mean"]).sort_values("sum",ascending=False)
print(ds.head(8).round(2))

print("\n--- breadth>=11: how concentrated in time? day-of count ---")
print(hi["day"].value_counts().head(10))

# Also: what fraction of ALL high-breadth rows are on the single biggest day?
print(f"\nbreadth>=11 total rows: {len(hi)}, on top day: {hi['day'].value_counts().iloc[0]} ({hi['day'].value_counts().iloc[0]/len(hi)*100:.1f}%)")
