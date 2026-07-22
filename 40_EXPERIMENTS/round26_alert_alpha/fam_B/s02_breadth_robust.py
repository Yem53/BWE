"""S02: Is ANY breadth edge real after removing the 2025-10-10 artifact?
- Recompute breadth buckets EXCLUDING 2025-10-10, with cost, both sides, f60/f240.
- Finer breadth thresholds.
- Per-day mean distribution (how many days actually positive?).
- breadth_1h as macro thermometer (does whole panel drift after high-breadth hours?).
DEV only.
"""
import numpy as np, pandas as pd
from _harness import load, seg, net_return, cell_stats

df = load()
d = seg(df, "dev").copy()
d_no1010 = d[d["day"]!="2025-10-10"].copy()

def report(frame, mask, label, side, ret="f60"):
    sub = frame[mask].copy()
    if len(sub)==0:
        print(f"{label:32s} side={side} ret={ret}: EMPTY"); return None
    sub["net"] = net_return(sub[ret].values, sub["atr_pct"].values, side)
    st = cell_stats(sub, "net", label)
    if st is None: return None
    print(f"{label:30s} {side:5s} {ret} | n={st['n']:6d} mean={st['net_mean']:+.3f} med={st['net_median']:+.3f} "
          f"win={st['winrate']:.3f} p={st['p']:.4f} maxday={st['max_one_day_frac']:.2f} dropTop={st['mean_drop_topday']:+.3f} ndays={st['n_days']}")
    return st

print("="*100)
print("A) breadth_min buckets EXCLUDING 2025-10-10, NET, both sides, f60")
print("="*100)
for lo,hi,nm in [(1,2,"b1-2"),(3,5,"b3-5"),(6,10,"b6-10"),(11,15,"b11-15"),(16,99,"b16+")]:
    m = (d_no1010["breadth_min"]>=lo)&(d_no1010["breadth_min"]<=hi)
    for side in ["long","short"]:
        report(d_no1010, m, f"{nm}(no1010)", side, "f60")

print("\n" + "="*100)
print("B) Same buckets, f240 (longer horizon), NET, both sides, EXCLUDING 10-10")
print("="*100)
for lo,hi,nm in [(6,10,"b6-10"),(11,15,"b11-15"),(16,99,"b16+")]:
    m = (d_no1010["breadth_min"]>=lo)&(d_no1010["breadth_min"]<=hi)
    for side in ["long","short"]:
        report(d_no1010, m, f"{nm}(no1010)", side, "f240")

print("\n" + "="*100)
print("C) WITH 10-10 included for comparison (the 'lit' version) — to quantify the gap")
print("="*100)
for lo,hi,nm in [(11,99,"b11+ WITH 1010")]:
    m = (d["breadth_min"]>=lo)&(d["breadth_min"]<=hi)
    for side in ["long","short"]:
        report(d, m, f"{nm}", side, "f60")

print("\n" + "="*100)
print("D) Per-day mean of breadth>=11 long net (no 10-10): how many days actually positive?")
print("="*100)
sub = d_no1010[d_no1010["breadth_min"]>=11].copy()
sub["net"] = net_return(sub["f60"].values, sub["atr_pct"].values, "long")
dm = sub.groupby("day")["net"].agg(["count","mean"])
dm = dm[dm["count"]>=5]
print(f"days with >=5 signals: {len(dm)}, positive-mean days: {(dm['mean']>0).sum()} ({(dm['mean']>0).mean()*100:.0f}%)")
print(dm.sort_values("mean").round(2).to_string())
