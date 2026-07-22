"""
Fam C DEV exploration. All cells computed on dev (ts_ms<=DEV_CUT).
Angles: OI direction, oi_mc, funding timing, basis prem, ttls, atr/bar_amp layering.
Reports every cell n/net/median/win/t/p + LODO, then BH-FDR over all reported cells.
"""
import numpy as np, json, os
from harness import load, net_ret, day_utc, describe, fmt, bh_fdr, DEV_CUT

DEV = f"ts_ms<={DEV_CUT}"

def cell(rows, side, ftag="f240", extra_filter=None):
    nets, days = [], []
    for r in rows:
        if r[ftag] is None: continue
        if extra_filter is not None and not extra_filter(r): continue
        nets.append(net_ret(r[ftag], r["atr_pct"], side))
        days.append(day_utc(r["ts_ms"]))
    return describe(nets, days)

RESULTS = []  # (label, side, ftag, descdict)

def add(label, rows, side, ftag="f240", ff=None):
    d = cell(rows, side, ftag, ff)
    RESULTS.append((label, side, ftag, d))
    print(f"[{label}] {side} {ftag}: {fmt(d)}")
    return d

# ============ ANGLE 1: OI DIRECTION (oi_price_1h, L17) ============
print("\n===== ANGLE 1: OI DIRECTION (oi_price_1h) =====")
cols = ["f60","f240","f1440","atr_pct","oi_chg","chg","oimc","fund","prem","ttls"]
oi = load(cols + [], where=DEV, wt="oi_price_1h")
print(f"loaded oi_price_1h dev rows: {len(oi)}")

# price up + OI up (new longs crowding -> reversal short) vs price up + OI down (short cover -> continue up)
# 'chg' is the alert price-change magnitude. Treat chg>0 as price-up alert.
for ftag in ["f240","f1440"]:
    add(f"OI: price_up & OI_up (>0)  SHORT", oi, "short", ftag,
        lambda r: r["chg"] is not None and r["chg"]>0 and r["oi_chg"] is not None and r["oi_chg"]>0)
    add(f"OI: price_up & OI_down(<0)  LONG ", oi, "long", ftag,
        lambda r: r["chg"] is not None and r["chg"]>0 and r["oi_chg"] is not None and r["oi_chg"]<0)
    add(f"OI: price_up & OI_down(<0)  SHORT", oi, "short", ftag,
        lambda r: r["chg"] is not None and r["chg"]>0 and r["oi_chg"] is not None and r["oi_chg"]<0)

# oi_chg strength layering, SHORT side (crowded new longs)
print("--- oi_chg strength deciles, price_up, SHORT f240 ---")
oi_chg_vals = sorted([r["oi_chg"] for r in oi if r["oi_chg"] is not None])
import numpy as _np
qs = _np.quantile(oi_chg_vals, [0.2,0.4,0.6,0.8,0.9])
print("oi_chg quantiles 20/40/60/80/90:", [round(x,2) for x in qs])
add("OI: oi_chg>+15% (strong build) SHORT", oi, "short", "f240",
    lambda r: r["oi_chg"] is not None and r["oi_chg"]>15 and r["chg"] is not None and r["chg"]>0)
add("OI: oi_chg>+15% (strong build) SHORT f1440", oi, "short", "f1440",
    lambda r: r["oi_chg"] is not None and r["oi_chg"]>15 and r["chg"] is not None and r["chg"]>0)
add("OI: oi_chg<-15% (heavy unwind) LONG ", oi, "long", "f240",
    lambda r: r["oi_chg"] is not None and r["oi_chg"]<-15 and r["chg"] is not None and r["chg"]>0)
add("OI: oi_chg<-15% (heavy unwind) LONG f1440", oi, "long", "f1440",
    lambda r: r["oi_chg"] is not None and r["oi_chg"]<-15 and r["chg"] is not None and r["chg"]>0)

# ============ ANGLE 2: oi_mc (over-leverage) ============
print("\n===== ANGLE 2: oi_mc ratio (over-leverage -> reversal short) =====")
oimc_all = load(["f240","f1440","atr_pct","oimc","chg"], where=f"{DEV} AND oimc IS NOT NULL")
print(f"rows with oimc dev: {len(oimc_all)}")
ov = sorted([r["oimc"] for r in oimc_all])
if ov:
    qq = _np.quantile(ov, [0.5,0.8,0.9])
    print("oimc q50/80/90:", [round(x,3) for x in qq])
    add("oimc top20% SHORT f240", oimc_all, "short", "f240", lambda r,t=qq[1]: r["oimc"]>=t)
    add("oimc top20% SHORT f1440", oimc_all, "short", "f1440", lambda r,t=qq[1]: r["oimc"]>=t)
    add("oimc top10% SHORT f240", oimc_all, "short", "f240", lambda r,t=qq[2]: r["oimc"]>=t)

# ============ ANGLE 3: FUNDING TIMING ============
print("\n===== ANGLE 3: funding timing =====")
fcols = ["f240","f1440","atr_pct","fund","chg","wt"]
# Use all windows but tag; funding extreme high => longs crowded => short better
fall = load(fcols, where=f"{DEV} AND fund IS NOT NULL")
fv = sorted([r["fund"] for r in fall])
qf = _np.quantile(fv, [0.05,0.1,0.9,0.95])
print("fund q5/10/90/95:", [round(x,5) for x in qf])
add("fund top10% (longs crowded) SHORT f240", fall, "short", "f240", lambda r,t=qf[2]: r["fund"]>=t)
add("fund top10% (longs crowded) SHORT f1440", fall, "short", "f1440", lambda r,t=qf[2]: r["fund"]>=t)
add("fund top5%  (longs crowded) SHORT f240", fall, "short", "f240", lambda r,t=qf[3]: r["fund"]>=t)
add("fund bot10% (shorts crowded) LONG  f240", fall, "long", "f240", lambda r,t=qf[1]: r["fund"]<=t)
add("fund bot10% (shorts crowded) LONG  f1440", fall, "long", "f1440", lambda r,t=qf[1]: r["fund"]<=t)
add("fund bot5%  (shorts crowded) LONG  f240", fall, "long", "f240", lambda r,t=qf[0]: r["fund"]<=t)

# ============ ANGLE 4: BASIS prem ============
print("\n===== ANGLE 4: basis prem =====")
pcols = ["f240","f1440","atr_pct","prem","chg"]
pall = load(pcols, where=f"{DEV} AND prem IS NOT NULL")
# winsorize away absurd tails (|prem|>10 likely bad)
pall = [r for r in pall if r["prem"] is not None and abs(r["prem"])<10]
pv = sorted([r["prem"] for r in pall])
qp = _np.quantile(pv, [0.05,0.1,0.9,0.95])
print(f"prem (|<10|) n={len(pall)} q5/10/90/95:", [round(x,4) for x in qp])
add("prem top10% (perp expensive) SHORT f240", pall, "short", "f240", lambda r,t=qp[2]: r["prem"]>=t)
add("prem top10% (perp expensive) SHORT f1440", pall, "short", "f1440", lambda r,t=qp[2]: r["prem"]>=t)
add("prem bot10% (perp cheap)     LONG  f240", pall, "long", "f240", lambda r,t=qp[1]: r["prem"]<=t)

# ============ ANGLE 5: ttls (top trader L/S) ============
print("\n===== ANGLE 5: ttls top-trader long/short =====")
tcols = ["f240","f1440","atr_pct","ttls","chg"]
tall = load(tcols, where=f"{DEV} AND ttls IS NOT NULL")
tall = [r for r in tall if r["ttls"] is not None and r["ttls"]<20]
tv = sorted([r["ttls"] for r in tall])
qt = _np.quantile(tv, [0.1,0.9])
print(f"ttls (<20) n={len(tall)} q10/90:", [round(x,3) for x in qt])
add("ttls top10% (whales long) FADE->SHORT f240", tall, "short", "f240", lambda r,t=qt[1]: r["ttls"]>=t)
add("ttls top10% (whales long) FOLLOW->LONG f240", tall, "long", "f240", lambda r,t=qt[1]: r["ttls"]>=t)
add("ttls bot10% (whales short) FOLLOW->SHORT f240", tall, "short", "f240", lambda r,t=qt[0]: r["ttls"]<=t)

# ============ ANGLE 6: atr / bar_amp layering on the SHORT mean-revert windows ============
print("\n===== ANGLE 6: atr layering on revert windows (60s/10s/90s/180s SHORT) =====")
rcols = ["f240","f1440","atr_pct","bar_amp","chg","wt"]
revert = load(rcols, where=DEV, wt=["price_60s","price_10s","price_90s","price_180s_extreme"])
print(f"revert windows dev rows: {len(revert)}")
add("revert-windows ALL SHORT f240", revert, "short", "f240")
add("revert-windows ALL SHORT f1440", revert, "short", "f1440")
add("revert atr<1.5 (low slip) SHORT f240", revert, "short", "f240", lambda r: r["atr_pct"] is not None and r["atr_pct"]<1.5)
add("revert atr<1.5 (low slip) SHORT f1440", revert, "short", "f1440", lambda r: r["atr_pct"] is not None and r["atr_pct"]<1.5)
add("revert atr>=3 (high slip) SHORT f240", revert, "short", "f240", lambda r: r["atr_pct"] is not None and r["atr_pct"]>=3)

# price_60s alone (largest revert window)
p60 = load(rcols, where=DEV, wt="price_60s")
add("price_60s atr<1.5 SHORT f1440", p60, "short", "f1440", lambda r: r["atr_pct"] is not None and r["atr_pct"]<1.5)
add("price_60s atr<1.5 SHORT f240", p60, "short", "f240", lambda r: r["atr_pct"] is not None and r["atr_pct"]<1.5)

# ============ BH-FDR over all reported cells ============
print("\n===== BH-FDR over all reported cells (q<0.10) =====")
pvals = [d["p"] for (_,_,_,d) in RESULTS if d.get("n",0)>0]
labels = [(l,s,ft,d) for (l,s,ft,d) in RESULTS if d.get("n",0)>0]
passed, thresh = bh_fdr(pvals, 0.10)
print(f"BH threshold p<={thresh:.5f}  ({passed.sum()}/{len(pvals)} cells pass)")
for (l,s,ft,d), pz in zip(labels, passed):
    flag = "PASS" if pz else "    "
    print(f"  {flag} [{l}] {s} {ft}: net={d['mean']:.3f} n={d['n']} p={d['p']:.4f}")

# save raw
out = []
for (l,s,ft,d) in RESULTS:
    rec = dict(label=l, side=s, ftag=ft)
    rec.update(d)
    out.append(rec)
with open("dev_explore_results.json","w") as fh:
    json.dump(out, fh, indent=2, default=str)
print("\nsaved dev_explore_results.json")
