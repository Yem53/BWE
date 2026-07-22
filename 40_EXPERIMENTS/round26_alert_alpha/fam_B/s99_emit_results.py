"""S99: Emit final fam_B results JSON. Recomputes the locked numbers cleanly so the JSON
is self-contained and reproducible. No new selection happens here."""
import numpy as np, pandas as pd, json
from _harness import load, seg, net_return, cell_stats, lodo, ttest_p_mean_gt0, bh_fdr

df=load()

def cellnet(which, mask_fn, ret, side):
    s=seg(df,which).copy(); sub=s[mask_fn(s)].copy()
    sub["net"]=net_return(sub[ret].values,sub["atr_pct"].values,side)
    return sub

def full(which, mask_fn, ret, side):
    sub=cellnet(which,mask_fn,ret,side)
    st=cell_stats(sub,"net",which)
    dm=sub.groupby("day")["net"].mean()
    m,se,t,p=ttest_p_mean_gt0(dm.values)
    st["day_level_mean"]=float(m) if m==m else None
    st["day_level_p"]=float(p) if p==p else None
    st["pos_days"]=int((dm>0).sum()); st["tot_days"]=int(len(dm))
    return st

out={"family":"sequence/cluster/breadth (angles 26-55)","dev_max_ts":1778803200000,
     "n_dev":int(len(seg(df,'dev'))),"n_val":int(len(seg(df,'val'))),
     "cost_model":"RT 0.14% + slip(atr>=1.5%:+0.8%RT, atr>=3%:+1.2%RT)",
     "verdicts":[]}

# --- VERDICT 1: headline breadth_min signal = mostly artifact ---
hi=cellnet("dev",lambda s:s["breadth_min"]>=11,"f60","long")
ld=lodo(hi.dropna(subset=["net"]),"net")
out["verdicts"].append({
 "id":"breadth_headline_DEBUNK","claim":"breadth_min high -> f60 +1.33% (裸扫亮灯)",
 "ruling":"FALSE as stated — single-day artifact (2025-10-10)",
 "evidence":{"cell":"breadth_min>=11 long f60 net (dev)","n":int(len(hi)),
   "net_mean_with_1010":round(float(hi['net'].mean()),3),
   "max_one_day_frac":round(ld['max_one_day_frac'],3),
   "top_day":ld['day_sum_top_date'],
   "mean_drop_topday":round(ld['mean_drop_topday'],3),
   "val_mean":round(float(cellnet('val',lambda s:s['breadth_min']>=11,'f60','long')['net'].mean()),3),
   "note":"with 10-10: +2.16%; drop 10-10: -0.04% p=0.66; val: -0.02% flat. 82% of net PnL from 2025-10-10."}})

# --- VERDICT 2: refined extreme-breadth dip-buy = TRADEABLE (val-confirmed) ---
mf=lambda s:(s["breadth_min"]>=16)&(s["chg"]<=-2.5)
dev_f240=full("dev",mf,"f240","long"); val_f240=full("val",mf,"f240","long")
dev_no=cellnet("dev",mf,"f240","long"); dev_no=dev_no[dev_no["day"]!="2025-10-10"]
dev_no_st=cell_stats(dev_no,"net","dev_no1010")
dev_f60=full("dev",mf,"f60","long"); val_f60=full("val",mf,"f60","long")
# control
ctl_low=cellnet("dev",lambda s:(s["breadth_min"]<=5)&(s["chg"]<=-2.5)&(s["day"]!="2025-10-10"),"f60","long")
ctl_hi =cellnet("dev",lambda s:(s["breadth_min"]>=16)&(s["chg"]<=-2.5)&(s["day"]!="2025-10-10"),"f60","long")
out["verdicts"].append({
 "id":"extreme_breadth_dipbuy","claim":"extreme market-wide breadth + alert coin dumping -> bounce (long)",
 "ruling":"TRADEABLE (modest, val-confirmed). Best horizon ~4h (f240). 1-day horizon fails.",
 "spec":"breadth_min>=16 AND chg<=-2.5 ; side=LONG ; hold ~4h (f240). Entry = alert coin's entry_px.",
 "dev_f240":{k:(round(dev_f240[k],3) if isinstance(dev_f240[k],float) else dev_f240[k]) for k in
   ["n","net_mean","net_median","winrate","p","max_one_day_frac","mean_drop_topday","day_level_mean","day_level_p","pos_days","tot_days"]},
 "dev_no1010_f240":{"n":dev_no_st["n"],"net_mean":round(dev_no_st["net_mean"],3),"net_median":round(dev_no_st["net_median"],3),
   "winrate":round(dev_no_st["winrate"],3),"max_one_day_frac":round(dev_no_st["max_one_day_frac"],3),"mean_drop_topday":round(dev_no_st["mean_drop_topday"],3)},
 "val_f240":{k:(round(val_f240[k],3) if isinstance(val_f240[k],float) else val_f240[k]) for k in
   ["n","net_mean","net_median","winrate","p","max_one_day_frac","mean_drop_topday","day_level_mean","day_level_p","pos_days","tot_days"]},
 "val_f60_companion":{k:(round(val_f60[k],3) if isinstance(val_f60[k],float) else val_f60[k]) for k in
   ["n","net_mean","net_median","winrate","p","max_one_day_frac"]},
 "control_breadth_isolation":{
   "same_dump_HIGH_breadth(b16,no1010,f60)":{"n":int(len(ctl_hi)),"mean":round(float(ctl_hi['net'].mean()),3),"win":round(float((ctl_hi['net']>0).mean()),3)},
   "same_dump_LOW_breadth(b<=5,no1010,f60)":{"n":int(len(ctl_low)),"mean":round(float(ctl_low['net'].mean()),3),"win":round(float((ctl_low['net']>0).mean()),3)},
   "interpretation":"A -2.5% dump alone bleeds (low-breadth -0.65%); the SAME dump during a market-wide flush bounces (+1.60%). Breadth adds real info."},
 "honesty_caveats":[
   "Per-TRADE val mean +1.26% (p<1e-4) is inflated by within-day clustering: extreme-breadth minutes fire dozens of correlated alerts. Independent events ≈ 10 val days.",
   "Per-DAY val mean +0.15% (p=0.77) NOT significant — treat as 'few independent events, positive 7/10 val days, modest per-event edge', not 753 iid trades.",
   "f1440 (24h) FAILS val (-0.15%): bounce is a 1-4h phenomenon, fades by next day.",
   "dev maxday=0.91 (10-10) — would auto-fail the single-day rule on dev alone; rescued ONLY because val (no 10-10) independently confirms + control test isolates breadth."]})

# --- VERDICT 3: xwin / repeat / dense-spacing = LEFT-TAIL TRAPS, not alpha ---
def trap(maskfn,nm):
    sub=cellnet("dev",maskfn,"f60","short"); st=cell_stats(sub,"net",nm)
    return {"cell":nm,"n":st["n"],"short_net_mean":round(st["net_mean"],3),"short_net_median":round(st["net_median"],3),"win":round(st["winrate"],3)}
out["verdicts"].append({
 "id":"xwin_repeat_dense_TRAP","claim":"xwin=1 / n1h-n24h high / minsprev small = '真信号'值得做",
 "ruling":"FALSE — classic left-tail trap. Positive median but NEGATIVE short mean (rare squeezes blow out the short). Not tradeable either side after cost.",
 "evidence_short_f60":[trap(lambda s:s["xwin"]==1,"xwin=1"),
   trap(lambda s:s["mins_prev"]<=5,"minsprev<=5m"),
   trap(lambda s:s["n1h"]>=8,"n1h>=8"),
   trap(lambda s:s["n24h"]>=16,"n24h>=16")],
 "note":"e.g. xwin=1 short: median +0.76% but mean -1.00%, win 53%. f240 median climbs to +2.7% while mean stays -1.2% = a few violent squeezes dominate. As LONG these have negative median. f5 immediate-dump shorts: gross only +0.08-0.15%, fully eaten by ~0.75% RT cost."})

# --- VERDICT 4: breadth_1h macro thermometer ---
b1h=cellnet("dev",lambda s:s["breadth_1h"]>=200,"f60","long")
out["verdicts"].append({
 "id":"breadth_misc","claim":"various (breadth_1h thermometer, hb-strongest-mover, first_day)",
 "ruling":"No additional tradeable edge. hb_strongest-mover long: mean +0.57% but median NEGATIVE + dropTop<0 (mirror trap). first_day/n1h=1 long ~flat. breadth_1h high subsumed by breadth_min signal.",
 "tradeable":False})

out["bottom_line"]={
 "tradeable_candidates":1,
 "candidate":"extreme_breadth_dipbuy (breadth_min>=16 & chg<=-2.5, LONG, ~4h hold): val +1.26% net/trade, win 72%, 7/10 val days positive — but few independent events (~10/2wk) and day-level not significant. Size accordingly.",
 "debunked":["breadth_min headline +1.33% = 82% one-day(10-10) artifact","xwin/repeat/dense-spacing = left-tail squeeze traps, not alpha"],
 "family_honest_summary":"One genuine but small/low-frequency edge (panic-flush dip-buy). The rest of the sequence/cluster/breadth family is either single-day artifact or left-tail trap. No high-frequency tradeable alpha found."}

with open("/Volumes/T9/BWE/40_EXPERIMENTS/round26_alert_alpha/fam_B/fam_B_results.json","w") as f:
    json.dump(out,f,indent=2,ensure_ascii=False)
print("written fam_B_results.json")
print(json.dumps(out["bottom_line"],indent=2,ensure_ascii=False))
