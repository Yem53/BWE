"""
EXIT RESEARCH (fam C core deliverable).
We only have extrema (mfe/mae at 60m & 240m) + close (f60/f240/f1440), not full path.
So we simulate TP/SL with the standard MFE/MAE bracket logic + an explicit
'ambiguity' assumption when BOTH tp and sl are touched within the window.

For a SHORT (profit = price drop):
  short_mfe_h = -mae_h   (best favorable, pct)   [h in {60,240}]
  short_mae_h = -mfe_h   (worst adverse,  pct)
  close_ret_h = -f_h

TP at +tp%  is reached iff short_mfe_h >= tp.
SL at -sl%  is reached iff short_mae_h <= -sl.
Cases:
  - neither: exit at close_ret_h
  - only TP : exit at +tp
  - only SL : exit at -sl
  - BOTH    : ambiguous -> assume WORST (SL first) = conservative. Also report OPTIMISTIC.

We use the 240m extrema window as the trade horizon for the exit search (matches
where the alert-alpha lives: post-pump multi-hour decay). Time-stop = close at 240m
if neither bracket hit. Compare to 1440m hold (no bracket) as the 'baseline hold'.

Cost: round-trip 0.14 + 2*slip(atr). Applied once per trade regardless of exit.
"""
import numpy as np, json, itertools
from harness import load, slip_per_side, day_utc, describe, fmt, bh_fdr, DEV_CUT
from datetime import datetime, timezone

DEV = f"ts_ms<={DEV_CUT}"
def ym(t): return datetime.fromtimestamp(t/1000,tz=timezone.utc).strftime("%Y-%m")

def sim_exit(r, tp, sl, horizon=240, assume="worst"):
    """Return net pct for a SHORT with TP/SL bracket over `horizon` minutes.
       r must have mfe{h}, mae{h}, f{h}, atr_pct.
       Horizons 60 and 240 have extrema; 1440 only has close (no bracket possible)."""
    cost = 0.14 + 2.0*slip_per_side(r["atr_pct"])
    if horizon == 1440:
        # plain hold to 1440 close, no bracket (no extrema available)
        f = r["f1440"]
        if f is None: return None
        return -f - cost
    mfe = r[f"mfe{horizon}"]; mae = r[f"mae{horizon}"]; f = r[f"f{horizon}"]
    if mfe is None or mae is None or f is None: return None
    s_mfe = -mae   # short favorable
    s_mae = -mfe   # short adverse
    s_close = -f
    hit_tp = (tp is not None) and (s_mfe >= tp)
    hit_sl = (sl is not None) and (s_mae <= -sl)
    if hit_tp and hit_sl:
        gross = (-sl if assume=="worst" else tp)
    elif hit_tp:
        gross = tp
    elif hit_sl:
        gross = -sl
    else:
        gross = s_close
    return gross - cost

def eval_exit(rows, tp, sl, horizon, ff=None, assume="worst"):
    nets, days = [], []
    for r in rows:
        if ff and not ff(r): continue
        v = sim_exit(r, tp, sl, horizon, assume)
        if v is None: continue
        nets.append(v); days.append(day_utc(r["ts_ms"]))
    return describe(nets, days)

# ---------- load the high-conviction short universes ----------
cols = ["f60","f240","f1440","mfe60","mae60","mfe240","mae240","atr_pct","fund","oi_chg","chg","wt"]

# Universe A: fund top10% (all windows) -- strongest broad short
fall = load(cols, where=f"{DEV} AND fund IS NOT NULL")
fthr = np.quantile([r["fund"] for r in fall],0.9)
univ_fund = [r for r in fall if r["fund"]>=fthr]
# Universe B: oi_chg>+15 (oi_price_1h)
univ_oi = load(cols, where=DEV, wt="oi_price_1h")
univ_oi = [r for r in univ_oi if r["oi_chg"] is not None and r["oi_chg"]>15]
# Universe C: revert windows atr<1.5
univ_rev = load(cols, where=DEV, wt=["price_60s","price_10s","price_90s","price_180s_extreme"])
univ_rev = [r for r in univ_rev if r["atr_pct"] is not None and r["atr_pct"]<1.5]

UNIVS = {"fund_top10": univ_fund, "oi_chg_gt15": univ_oi, "revert_atr_lt1.5": univ_rev}

print("Universe sizes (dev):", {k:len(v) for k,v in UNIVS.items()})

# baselines: plain hold at 240 and 1440 (no bracket), cost-adj
print("\n===== BASELINE HOLDS (no exit logic) =====")
for name, U in UNIVS.items():
    for h in (240,1440):
        d = eval_exit(U, None, None, h)  # no tp/sl -> always close
        print(f"  {name} hold f{h}: {fmt(d)}")

# ---------- EXIT GRID SEARCH (horizon=240 bracket) ----------
print("\n===== EXIT GRID (SHORT, 240m bracket, WORST-case both-touch) =====")
tps = [2,3,4,5,6,8,10]
sls = [2,3,4,5,8,100]   # 100 = effectively no SL
GRID_RESULTS = []
for name, U in UNIVS.items():
    print(f"\n--- {name} (n={len(U)}) ---  [tp x sl -> net (worst-case)]")
    best = None
    for tp in tps:
        row = []
        for sl in sls:
            d = eval_exit(U, tp, sl, 240, assume="worst")
            row.append(f"{d['mean']:+.2f}")
            GRID_RESULTS.append((name,tp,sl,d))
            if d['n']>=200 and (best is None or d['mean']>best[3]['mean']):
                best=(name,tp,sl,d)
        print(f"  tp={tp:>2}: " + " ".join(f"sl{sl}={v}" for sl,v in zip(sls,row)))
    if best:
        print(f"  >> best worst-case: tp={best[1]} sl={best[2]} -> {fmt(best[3])}")

# ---------- For the best brackets, also show OPTIMISTIC bound & monthly ----------
print("\n===== TOP EXIT CONFIGS: worst vs optimistic bound + monthly + LODO =====")
# pick a few sensible configs to highlight per universe
HILITE = {
 "fund_top10":     [(5,5),(4,5),(6,8),(5,100)],
 "oi_chg_gt15":    [(5,5),(6,8),(8,100),(4,5)],
 "revert_atr_lt1.5":[(4,4),(5,5),(3,4),(6,8)],
}
FINAL = []
for name, U in UNIVS.items():
    print(f"\n### {name}")
    for tp,sl in HILITE[name]:
        dw = eval_exit(U, tp, sl, 240, assume="worst")
        do = eval_exit(U, tp, sl, 240, assume="opt")
        # monthly on worst
        nets,mons=[],[]
        for r in U:
            v=sim_exit(r,tp,sl,240,"worst")
            if v is None: continue
            nets.append(v); mons.append(ym(r["ts_ms"]))
        by={}
        for v,m in zip(nets,mons): by.setdefault(m,[]).append(v)
        monthly={m:round(float(np.mean(x)),1) for m,x in sorted(by.items()) if len(x)>=20}
        posm=sum(1 for x in monthly.values() if x>0); totm=len(monthly)
        print(f"  tp={tp} sl={sl}: WORST {fmt(dw)}")
        print(f"             OPT  net={do['mean']:+.2f} | monthly(worst,n>=20)={monthly} pos={posm}/{totm}")
        FINAL.append(dict(universe=name,tp=tp,sl=sl,horizon=240,
                          worst=dw,opt_mean=do['mean'],monthly=monthly,pos_months=posm,tot_months=totm))

# save
with open("exit_sim_results.json","w") as fh:
    json.dump([dict(universe=n,tp=tp,sl=sl,mean=d['mean'],n=d['n'],t=d['t'],p=d['p'],
                    win=d['win'],median=d['median']) for (n,tp,sl,d) in GRID_RESULTS], fh, indent=2)
with open("exit_final.json","w") as fh:
    json.dump(FINAL, fh, indent=2, default=str)
print("\nsaved exit_sim_results.json, exit_final.json")
