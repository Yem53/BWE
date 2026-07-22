"""S11: The negative-long cells are candidate SHORTS. Evaluate them properly as shorts.
Rule-1: short = -f; for a GOOD short we want short_mean>0 AND short_median>0 (not just one).
A cell with long_median very negative but long_mean only mildly negative = right-tail trap for shorts
(rare squeezes hurt the short). So check BOTH mean and median on short, plus LODO, plus horizons.
Candidates: xwin=1, minsprev<=5m, n1h>=4, n24h>=16.  Combine the strongest into a composite.
Also positive-long: hb_strongest_mover. DEV first.
"""
import numpy as np, pandas as pd
from _harness import load, seg, net_return, cell_stats, bh_fdr

df=load(); dev=seg(df,"dev").copy()
dev["minute"]=dev["ts_ms"]//60000

def short_report(frame, mask, label, ret="f60"):
    sub=frame[mask].copy()
    if len(sub)<100:
        print(f"{label}: n<100"); return None
    sub["net"]=net_return(sub[ret].values,sub["atr_pct"].values,"short")
    st=cell_stats(sub,"net",label); st["ret"]=ret
    print(f"{label:30s} {ret} | n={st['n']:6d} Smean={st['net_mean']:+.3f} Smed={st['net_median']:+.3f} "
          f"win={st['winrate']:.3f} p={st['p']:.4f} maxday={st['max_one_day_frac']:.2f} dropTop={st['mean_drop_topday']:+.3f} nd={st['n_days']}")
    return st

print("="*95); print("SHORT side, key cells, f60 (want BOTH Smean>0 AND Smed>0)"); print("="*95)
cells={
 "xwin=1": dev["xwin"]==1,
 "minsprev<=5m": dev["mins_prev"]<=5,
 "n1h>=4": dev["n1h"]>=4,
 "n1h>=8": dev["n1h"]>=8,
 "n24h>=16": dev["n24h"]>=16,
 "n24h>=30": dev["n24h"]>=30,
}
rows=[]
for nm,m in cells.items():
    st=short_report(dev,m,nm);
    if st: rows.append(st)

print("\n--- horizon scan on the deepest-median ones (xwin=1, minsprev<=5m) short ---")
for nm,m in [("xwin=1",dev["xwin"]==1),("minsprev<=5m",dev["mins_prev"]<=5),("n1h>=8",dev["n1h"]>=8)]:
    for ret in ["f5","f15","f60","f240"]:
        short_report(dev,m,nm,ret)
    print()

print("="*95); print("COMPOSITE short: xwin=1 AND minsprev<=5m (densely-confirmed dump)"); print("="*95)
comp=(dev["xwin"]==1)&(dev["mins_prev"]<=5)
for ret in ["f15","f60","f240"]:
    short_report(dev,comp,"xwin&minsprev<=5",ret)

print("\n" + "="*95); print("And tighter: xwin=1 & n1h>=4 (confirmed + already-repeating)"); print("="*95)
for ret in ["f60","f240"]:
    short_report(dev,(dev["xwin"]==1)&(dev["n1h"]>=4),"xwin & n1h>=4",ret)

print("\n" + "="*95); print("Positive-LONG cell: high-breadth strongest-mover (long)"); print("="*95)
dev["abschg"]=dev["chg"].abs(); dev["rank_in_min"]=dev.groupby("minute")["abschg"].rank(ascending=False,method="first")
hb=dev[dev["breadth_min"]>=6]
sub=hb[hb["rank_in_min"]==1].copy()
for ret in ["f60","f240"]:
    sub["net"]=net_return(sub[ret].values,sub["atr_pct"].values,"long")
    st=cell_stats(sub,"net","hb_strongest_long")
    print(f"hb_strongest_long {ret} | n={st['n']} Lmean={st['net_mean']:+.3f} Lmed={st['net_median']:+.3f} win={st['winrate']:.3f} p={st['p']:.4f} maxday={st['max_one_day_frac']:.2f} dropTop={st['mean_drop_topday']:+.3f}")
