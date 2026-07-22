"""
EXIT RESEARCH part 2 — the RESOLVABLE questions.

Bracket TP/SL is unresolvable here: ~63% of trades in the short universe touch
BOTH +/-3% within 240m, so with extrema-only data the realized bracket outcome
is indeterminate (worst-case demolishes, optimistic flatters). NOT reported as tradeable.

What IS unambiguous: the CLOSE returns f60, f240, f1440 (and -mae as a one-sided
'profit cap' for an early-favorable taker). So we answer:
  Q1 TIME-STOP: for each short universe, which fixed holding horizon (60 / 240 / 1440)
     gives the best net? (no bracket, pure close)
  Q2 EARLY-FAVORABLE 'profit-lock' that is one-sided and resolvable:
     'exit at +K% if short_mfe60 >= K within first 60m, ELSE hold to 1440 close'.
     This only needs the FIRST-60m extreme (one-sided TP) + the 1440 close -> resolvable
     as long as we don't also impose an SL (no both-touch problem).
  Q3 GIVEBACK: among trades whose short_mfe240 was large (>=5%) but f1440 short close < 0,
     how much alpha is 'given back'? quantify.
"""
import numpy as np, json
from harness import load, slip_per_side, day_utc, describe, fmt, DEV_CUT
from datetime import datetime, timezone

DEV = f"ts_ms<={DEV_CUT}"
def ym(t): return datetime.fromtimestamp(t/1000,tz=timezone.utc).strftime("%Y-%m")
def cost_of(r): return 0.14 + 2.0*slip_per_side(r["atr_pct"])

cols=["f60","f240","f1440","mfe60","mae60","mfe240","mae240","atr_pct","fund","oi_chg","wt"]
fall=load(cols,where=f"{DEV} AND fund IS NOT NULL")
fthr=np.quantile([r["fund"] for r in fall],0.9)
U_fund=[r for r in fall if r["fund"]>=fthr]
U_oi=[r for r in load(cols,where=DEV,wt="oi_price_1h") if r["oi_chg"] is not None and r["oi_chg"]>15]
U_rev=[r for r in load(cols,where=DEV,wt=["price_60s","price_10s","price_90s","price_180s_extreme"]) if r["atr_pct"] is not None and r["atr_pct"]<1.5]
UNIVS={"fund_top10":U_fund,"oi_chg_gt15":U_oi,"revert_atr_lt1.5":U_rev}

print("="*70+"\nQ1 TIME-STOP: net short return at fixed horizon (no bracket)\n"+"="*70)
for name,U in UNIVS.items():
    print(f"\n--- {name} (n={len(U)}) ---")
    for h in (60,240,1440):
        nets=[];days=[]
        for r in U:
            f=r[f"f{h}"]
            if f is None: continue
            nets.append(-f - cost_of(r)); days.append(day_utc(r["ts_ms"]))
        print(f"  hold {h:>4}m: {fmt(describe(nets,days))}")

print("\n"+"="*70+"\nQ2 EARLY-FAVORABLE one-sided lock (resolvable, no SL):")
print("  rule: if short_mfe60 (=-mae60) >= K within 60m -> bank +K; else hold to 1440 close.")
print("="*70)
for name,U in UNIVS.items():
    print(f"\n--- {name} ---")
    for K in (2,3,4,5,6):
        nets=[];days=[];locked=0
        for r in U:
            if r["mae60"] is None or r["f1440"] is None: continue
            s_mfe60=-r["mae60"]
            if s_mfe60>=K:
                gross=K; locked+=1
            else:
                gross=-r["f1440"]
            nets.append(gross-cost_of(r)); days.append(day_utc(r["ts_ms"]))
        d=describe(nets,days)
        print(f"  K={K}: lock={locked}/{len(nets)} ({locked/max(len(nets),1)*100:.0f}%) {fmt(d)}")

print("\n"+"="*70+"\nQ3 GIVEBACK analysis (fund_top10):")
print("="*70)
# among trades where short was deeply favorable intra-240m (smfe240>=5) what fraction
# ends the 1440 close negative for short? how much mean is lost vs locking at +5?
g=U_fund
big=[r for r in g if r["mae240"] is not None and -r["mae240"]>=5 and r["f1440"] is not None]
giveback_neg=[r for r in big if -r["f1440"]<0]
print(f"  trades w/ short_mfe240>=5%: {len(big)} of {len(g)}")
print(f"  of those, 1440-close short <0 (gave it ALL back + more): {len(giveback_neg)} ({len(giveback_neg)/max(len(big),1)*100:.0f}%)")
hold_mean=np.mean([-r["f1440"]-cost_of(r) for r in big])
lock5_mean=np.mean([5-cost_of(r) for r in big])
print(f"  on this favorable subset: hold-1440 net={hold_mean:.2f} vs lock-at-+5 net={lock5_mean:.2f}")
print(f"  => giveback cost of NOT locking = {lock5_mean-hold_mean:.2f} pct/trade on the favorable subset")

# save a compact summary
summary={"both_touched_note":"~63% touch both +/-3% in 240m -> bracket exit unresolvable from extrema-only data",
         "resolvable":"time-stop + one-sided early lock"}
with open("exit_time_results.json","w") as fh: json.dump(summary,fh,indent=2)
print("\nsaved exit_time_results.json")
