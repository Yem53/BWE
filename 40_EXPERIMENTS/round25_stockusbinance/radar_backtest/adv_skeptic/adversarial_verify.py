#!/usr/bin/env python3
"""
ADVERSARIAL VERIFICATION of the radar neutral long/short "finding".
Code-name: adv_skeptic
Default stance: the alpha is GUILTY (fake) until proven otherwise.

We re-implement the LS construction from scratch (NOT trusting the audited
numbers) and then run 5 falsification batteries:
  (a) momentum disguise   -> incremental over free momentum factor
  (b) single-day / single-name driver -> jackknife
  (c) overlapping-holding CI inflation -> effective N + non-overlap
  (d) survivorship / tradeability bias -> only 30 perp-mappable names
  (e) cost realism -> 0.10%/leg vs 0.20%/leg

Iron rules honored:
  - LS = mean(top tercile fwd) - mean(bottom tercile fwd), equal-weight, dollar-neutral.
  - Cost: round-trip 0.10%/leg => both legs charged each rebalance turnover.
  - Effective N tiny -> everything flagged exploratory.
  - SHORT side judged on MEAN not median (left-tail protection).
  - numpy only; spearman + permutation hand-written.
"""
import json, math
import numpy as np
from collections import defaultdict

np.random.seed(12345)
PANEL = "/Volumes/T9/BWE/40_EXPERIMENTS/round25_stockusbinance/radar_panel.jsonl"
HORIZONS = {"f1":1, "f2":2, "f3":3, "f5":5}
COST_PER_LEG = 0.10   # % per leg, round trip already (per iron rule #2)

rows = [json.loads(l) for l in open(PANEL)]

# ---------- helpers ----------
def spearman(x, y):
    """Hand-written Spearman rho with average-rank tie handling."""
    x = np.asarray(x, float); y = np.asarray(y, float)
    n = len(x)
    if n < 3: return float("nan")
    def rank(a):
        order = np.argsort(a, kind="mergesort")
        r = np.empty(n, float)
        r[order] = np.arange(n, dtype=float)
        # average ties
        i = 0
        sa = a[order]
        while i < n:
            j = i
            while j+1 < n and sa[j+1] == sa[i]:
                j += 1
            if j > i:
                avg = (i + j) / 2.0
                r[order[i:j+1]] = avg
            i = j+1
        return r
    rx, ry = rank(x), rank(y)
    rx -= rx.mean(); ry -= ry.mean()
    denom = math.sqrt((rx*rx).sum() * (ry*ry).sum())
    return float((rx*ry).sum()/denom) if denom > 0 else float("nan")

def ls_daily(day_rows, score_key, fwd_key, cost=COST_PER_LEG):
    """One day's LS net return (%). top tercile long, bottom tercile short.
    Returns (net, gross, n_long, n_short) or None if not computable."""
    pts = [(r[score_key], r[fwd_key]) for r in day_rows
           if r.get(fwd_key) is not None and r.get(score_key) is not None]
    n = len(pts)
    if n < 3:  # need at least 3 to form terciles
        return None
    pts.sort(key=lambda t: t[0])
    k = max(1, n // 3)
    short_leg = pts[:k]          # lowest score -> short
    long_leg  = pts[-k:]         # highest score -> long
    long_ret  = np.mean([p[1] for p in long_leg])
    short_ret = np.mean([p[1] for p in short_leg])  # MEAN not median
    gross = long_ret - short_ret
    # cost: long opens+closes, short opens+closes -> 2 legs * cost each side.
    # Iron rule: round-trip 0.10%/leg, both legs. A full LS round trip = 2 legs * 0.10 = 0.20
    net = gross - 2*cost
    return net, gross, len(long_leg), len(short_leg)

def residualize_by_day(day_rows, fwd_key, ctrl_key="momentum_20d_pct"):
    """Regress fwd on control within the day, return residual fwd attached."""
    pts = [(r, r.get(ctrl_key), r.get(fwd_key)) for r in day_rows
           if r.get(fwd_key) is not None and r.get(ctrl_key) is not None]
    if len(pts) < 3: return []
    X = np.array([p[1] for p in pts], float)
    Y = np.array([p[2] for p in pts], float)
    # OLS y = a + b x
    A = np.vstack([np.ones_like(X), X]).T
    coef, *_ = np.linalg.lstsq(A, Y, rcond=None)
    resid = Y - A.dot(coef)
    out = []
    for (r,_,_), rr in zip(pts, resid):
        rc = dict(r); rc["_resid_fwd"] = float(rr)
        out.append(rc)
    return out

def run_ls_series(score_key, fwd_key, exclude_dates=None, exclude_tickers=None,
                  cost=COST_PER_LEG, fwd_field=None):
    """Daily LS series. fwd_field overrides the column used as the return."""
    exclude_dates = exclude_dates or set()
    exclude_tickers = exclude_tickers or set()
    bydate = defaultdict(list)
    for r in rows:
        if r["date"] in exclude_dates: continue
        if r["ticker"] in exclude_tickers: continue
        bydate[r["date"]].append(r)
    series = []  # (date, net, gross)
    fk = fwd_field or fwd_key
    for d in sorted(bydate):
        res = ls_daily(bydate[d], score_key, fk, cost=cost)
        if res is None: continue
        net, gross, nl, ns = res
        series.append((d, net, gross))
    return series

def summ(series):
    if not series: return None
    nets = np.array([s[1] for s in series])
    gross = np.array([s[2] for s in series])
    return {
        "n_days": len(series),
        "sum_net": float(nets.sum()),
        "mean_net": float(nets.mean()),
        "sum_gross": float(gross.sum()),
        "mean_gross": float(gross.mean()),
    }

# ---------- permutation test (hand written) ----------
def perm_test_meanLS(score_key, fwd_key, n_perm=5000, cost=COST_PER_LEG):
    """Null: shuffle scores within each day, recompute LS mean_net.
    One-sided p that observed mean_net is as high or higher by chance."""
    bydate = defaultdict(list)
    for r in rows:
        if r.get(fwd_key) is not None and r.get(score_key) is not None:
            bydate[r["date"]].append((r[score_key], r[fwd_key]))
    days = [v for v in bydate.values() if len(v) >= 3]
    def meanls(perm=False):
        vals=[]
        for day in days:
            scores=np.array([p[0] for p in day],float)
            fwd=np.array([p[1] for p in day],float)
            if perm:
                scores=scores[np.random.permutation(len(scores))]
            order=np.argsort(scores,kind="mergesort")
            n=len(order); k=max(1,n//3)
            short=fwd[order[:k]].mean()
            lng=fwd[order[-k:]].mean()
            vals.append(lng-short-2*cost)
        return float(np.mean(vals))
    obs=meanls(False)
    ge=0
    for _ in range(n_perm):
        if meanls(True)>=obs: ge+=1
    return obs,(ge+1)/(n_perm+1)

# =====================================================================
# BASELINE: reproduce the audited LS net by horizon (daily-rebal)
# =====================================================================
print("="*70)
print("STEP 0  — reproduce audited daily-rebal LS net (sanity vs claim)")
print("="*70)
baseline = {}
for fwd in HORIZONS:
    for sk,label in [("momentum_20d_pct","momentum"),("sentiment","sentiment"),
                     ("combined_score","combined")]:
        s = run_ls_series(sk, fwd)
        sm = summ(s)
        baseline[(label,fwd)] = sm
        print(f"  {label:9s} {fwd}: n_days={sm['n_days']:2d} "
              f"sum_net={sm['sum_net']:+7.3f} mean_net={sm['mean_net']:+6.3f} "
              f"(gross sum {sm['sum_gross']:+7.3f})")

# =====================================================================
# (a) MOMENTUM DISGUISE  — incremental sentiment over momentum residual
# =====================================================================
print()
print("="*70)
print("(a) MOMENTUM DISGUISE — sentiment alpha on momentum-residualized fwd")
print("="*70)
# Correlations first
sent = np.array([r["sentiment"] for r in rows if r.get("sentiment") is not None])
mom  = np.array([r["momentum_20d_pct"] for r in rows if r.get("momentum_20d_pct") is not None])
tech = np.array([r["tech_score"] for r in rows])
both = [(r["sentiment"],r["momentum_20d_pct"],r["tech_score"]) for r in rows
        if r.get("sentiment") is not None and r.get("momentum_20d_pct") is not None]
S=np.array([b[0] for b in both]); M=np.array([b[1] for b in both]); T=np.array([b[2] for b in both])
def pearson(a,b):
    a=a-a.mean();b=b-b.mean()
    return float((a*b).sum()/math.sqrt((a*a).sum()*(b*b).sum()))
print(f"  pearson(sentiment, momentum) = {pearson(S,M):+.3f}")
print(f"  pearson(sentiment, tech)     = {pearson(S,T):+.3f}")
print(f"  pearson(tech, momentum)      = {pearson(T,M):+.3f}")

resid_incremental = {}
resid_rho = {}
for fwd in HORIZONS:
    # build residual fwd per day, then LS on sentiment using residual fwd
    bydate=defaultdict(list)
    for r in rows: bydate[r["date"]].append(r)
    series=[]; rhos=[]
    for d in sorted(bydate):
        rr = residualize_by_day(bydate[d], fwd)
        res = ls_daily(rr, "sentiment", "_resid_fwd")
        if res: series.append((d,res[0],res[1]))
        # spearman of sentiment vs residual fwd within day
        sv=[x["sentiment"] for x in rr]; rv=[x["_resid_fwd"] for x in rr]
        if len(sv)>=3: rhos.append(spearman(sv,rv))
    sm=summ(series)
    resid_incremental[fwd]=sm
    meanrho=float(np.mean(rhos)) if rhos else float("nan")
    resid_rho[fwd]=meanrho
    print(f"  {fwd}: incremental sentiment-on-residual LS sum_net={sm['sum_net']:+7.3f} "
          f"mean={sm['mean_net']:+6.3f} | mean within-day spearman(sent,residfwd)={meanrho:+.3f}")

# double sort: within momentum terciles, sentiment long/short (momentum-controlled)
print("\n  -- momentum-controlled double sort (sentiment LS inside mom terciles) --")
double_sort={}
for fwd in HORIZONS:
    bydate=defaultdict(list)
    for r in rows:
        if r.get(fwd) is not None: bydate[r["date"]].append(r)
    daily=[]
    for d,dr in bydate.items():
        if len(dr)<6: continue
        dr=sorted(dr,key=lambda r:r["momentum_20d_pct"])
        n=len(dr); t=n//3
        buckets=[dr[:t],dr[t:2*t],dr[2*t:]] if t>=1 else []
        legdiffs=[]
        for b in buckets:
            if len(b)<2: continue
            b2=sorted(b,key=lambda r:r["sentiment"])
            kk=max(1,len(b2)//2)
            lo=np.mean([x[fwd] for x in b2[:kk]])
            hi=np.mean([x[fwd] for x in b2[-kk:]])
            legdiffs.append(hi-lo)
        if legdiffs: daily.append(np.mean(legdiffs)-2*COST_PER_LEG)
    if daily:
        double_sort[fwd]=float(np.sum(daily))
        print(f"  {fwd}: mom-controlled sentiment LS sum_net = {np.sum(daily):+7.3f} "
              f"(n_days={len(daily)})")

# =====================================================================
# (b) SINGLE-DAY / SINGLE-NAME DRIVER  — jackknife
# =====================================================================
print()
print("="*70)
print("(b) JACKKNIFE — drop biggest day / biggest name (focus on positives)")
print("="*70)
jackknife={}
# focus on the signals the audit says are positive: sentiment f1, f5; combined f5
for sk in ["sentiment","combined_score"]:
    for fwd in ["f1","f5"]:
        full = run_ls_series(sk,fwd)
        full_sum = summ(full)["sum_net"]
        # leave-one-day-out: find day whose removal most reduces sum
        day_contrib=[]
        for (d,net,_) in full:
            day_contrib.append((d,net))
        # most positive day
        day_contrib.sort(key=lambda x:x[1])
        worst_day = day_contrib[-1]  # largest positive contribution
        s_drop_day = summ(run_ls_series(sk,fwd,exclude_dates={worst_day[0]}))["sum_net"]
        # leave-one-name-out: drop each ticker, find min resulting sum
        tickers=set(r["ticker"] for r in rows)
        name_results=[]
        for tk in tickers:
            ss=run_ls_series(sk,fwd,exclude_tickers={tk})
            if ss: name_results.append((tk,summ(ss)["sum_net"]))
        name_results.sort(key=lambda x:x[1])
        worst_name=name_results[0]   # ticker whose removal hurts most -> biggest driver
        jackknife[(sk,fwd)]={
            "full_sum":full_sum,
            "drop_top_day":[worst_day[0], s_drop_day],
            "drop_biggest_name":[worst_name[0], worst_name[1]],
        }
        print(f"  {sk:14s} {fwd}: full={full_sum:+7.3f} | "
              f"drop best day {worst_day[0]}(+{worst_day[1]:.2f})->{s_drop_day:+7.3f} | "
              f"drop name {worst_name[0]}->{worst_name[1]:+7.3f}")

# Which single name drives f5 sentiment most? Check MRVL & others by leg membership
print("\n  -- f5 sentiment: per-ticker net contribution when in a leg --")
def leg_contrib(sk,fwd):
    bydate=defaultdict(list)
    for r in rows:
        if r.get(fwd) is not None: bydate[r["date"]].append(r)
    contrib=defaultdict(float); count=defaultdict(int)
    for d,dr in bydate.items():
        if len(dr)<3: continue
        dr2=sorted(dr,key=lambda r:r[sk]); n=len(dr2);k=max(1,n//3)
        nl=len(dr2[-k:]); ns=len(dr2[:k])
        for r in dr2[-k:]:
            contrib[r["ticker"]] += r[fwd]/nl; count[r["ticker"]]+=1
        for r in dr2[:k]:
            contrib[r["ticker"]] += -r[fwd]/ns; count[r["ticker"]]+=1
    return contrib,count
c,ct=leg_contrib("sentiment","f5")
top=sorted(c.items(),key=lambda x:-abs(x[1]))[:8]
for tk,v in top:
    print(f"     {tk:6s} net_contrib_to_LSsum={v:+7.3f}  (appeared in {ct[tk]} day-legs)")

# =====================================================================
# (c) OVERLAPPING-HOLDING CI INFLATION  — effective N + non-overlap
# =====================================================================
print()
print("="*70)
print("(c) OVERLAP / EFFECTIVE N — non-overlapping rebalance per horizon")
print("="*70)
def nonoverlap_series(sk, fwd, h):
    """Rebalance every h trading days (non-overlapping holding)."""
    bydate=defaultdict(list)
    for r in rows:
        if r.get(fwd) is not None: bydate[r["date"]].append(r)
    days=sorted(bydate)
    picked=days[::h]
    series=[]
    for d in picked:
        res=ls_daily(bydate[d], sk, fwd)
        if res: series.append((d,res[0],res[1]))
    return series
overlap_report={}
for sk in ["momentum_20d_pct","sentiment","combined_score"]:
    for fwd,h in HORIZONS.items():
        daily = run_ls_series(sk,fwd)
        nonov = nonoverlap_series(sk,fwd,h)
        sm_d=summ(daily); sm_n=summ(nonov)
        overlap_report[(sk,fwd)]={
            "daily_rebal":{"n_days":sm_d["n_days"],"sum_net":sm_d["sum_net"],"mean_net":sm_d["mean_net"]},
            "nonoverlap":{"n_rebal":sm_n["n_days"],"sum_net":sm_n["sum_net"],
                          "mean_net_per_rebal":sm_n["mean_net"]},
        }
    print(f"  {sk}:")
    for fwd,h in HORIZONS.items():
        r=overlap_report[(sk,fwd)]
        print(f"    {fwd}(h={h}): daily n={r['daily_rebal']['n_days']:2d} "
              f"sum={r['daily_rebal']['sum_net']:+7.3f} | "
              f"nonov rebals={r['nonoverlap']['n_rebal']} "
              f"sum={r['nonoverlap']['sum_net']:+7.3f} "
              f"mean/rebal={r['nonoverlap']['mean_net_per_rebal']:+6.3f}")

# effective N estimate via lag-1 autocorr of daily LS (sentiment f5)
def eff_n(series):
    x=np.array([s[1] for s in series]); n=len(x)
    if n<3: return n, float("nan")
    x=x-x.mean()
    ac1=float((x[:-1]*x[1:]).sum()/(x*x).sum()) if (x*x).sum()>0 else 0.0
    # Newey-style crude: N_eff = N*(1-ac1)/(1+ac1)
    neff=n*(1-ac1)/(1+ac1) if (1+ac1)!=0 else n
    return neff, ac1
for sk in ["sentiment","combined_score"]:
    for fwd in ["f1","f5"]:
        s=run_ls_series(sk,fwd)
        neff,ac1=eff_n(s)
        print(f"  eff-N {sk} {fwd}: n_days={len(s)} lag1_autocorr={ac1:+.3f} -> N_eff~{neff:.1f}")

# =====================================================================
# (d) SURVIVORSHIP / TRADEABILITY — only 30 perp-mappable names
# =====================================================================
print()
print("="*70)
print("(d) SURVIVORSHIP / TRADEABILITY")
print("="*70)
print("  Panel already restricted to 30 perp-mappable tickers (by construction).")
print("  We CANNOT add the dropped names (no perp price). What we CAN test:")
print("  - dispersion of the universe (is the cross-section degenerate?)")
print("  - whether result depends on the late universe expansion (11->30 names)")
# subsample: early regime (<= 2026-06-05, ~11 names) vs late (>=2026-06-08, 22-30 names)
early=set(['2026-05-22','2026-05-26','2026-05-27','2026-05-28','2026-05-29',
           '2026-06-01','2026-06-02','2026-06-03','2026-06-04','2026-06-05','2026-06-07'])
for sk in ["sentiment","combined_score"]:
    for fwd in ["f1","f5"]:
        bydate=defaultdict(list)
        for r in rows:
            if r.get(fwd) is not None: bydate[r["date"]].append(r)
        e=[];l=[]
        for d,dr in bydate.items():
            res=ls_daily(dr,sk,fwd)
            if not res: continue
            (e if d in early else l).append(res[0])
        es=np.sum(e) if e else float('nan'); ls_=np.sum(l) if l else float('nan')
        print(f"  {sk} {fwd}: early-regime sum_net={es:+7.3f} (n={len(e)}) | "
              f"late-regime sum_net={ls_:+7.3f} (n={len(l)})")
# cross-sectional dispersion: std of fwd within day
disp=[]
bydate=defaultdict(list)
for r in rows:
    if r.get("f1") is not None: bydate[r["date"]].append(r["f1"])
for d,v in bydate.items():
    if len(v)>=3: disp.append(np.std(v))
print(f"  median within-day cross-sectional std of f1 = {np.median(disp):.3f}% "
      f"(low dispersion -> LS spread fragile)")

# =====================================================================
# (e) COST REALISM — 0.10 vs 0.20 per leg
# =====================================================================
print()
print("="*70)
print("(e) COST STRESS — 0.10%/leg (base) vs 0.20%/leg")
print("="*70)
cost_report={}
for sk in ["sentiment","combined_score"]:
    for fwd in HORIZONS:
        base=summ(run_ls_series(sk,fwd,cost=0.10))["sum_net"]
        stress=summ(run_ls_series(sk,fwd,cost=0.20))["sum_net"]
        gross=summ(run_ls_series(sk,fwd,cost=0.0))["sum_net"]
        cost_report[(sk,fwd)]={"gross":gross,"net_010":base,"net_020":stress}
        # also non-overlap (fewer rebalances => cost hit less often)
        h=HORIZONS[fwd]
        nv010=summ(nonoverlap_series(sk,fwd,h)) if nonoverlap_series(sk,fwd,h) else None
        print(f"  {sk:14s} {fwd}: gross={gross:+7.3f} | net@0.10={base:+7.3f} | "
              f"net@0.20={stress:+7.3f}  ({'ALIVE' if stress>0 else 'DEAD'} @0.20)")

# =====================================================================
# PERMUTATION p-values for the positive claims
# =====================================================================
print()
print("="*70)
print("PERMUTATION TESTS (hand-written, 5000 shuffles, daily-rebal net)")
print("="*70)
perm_results={}
for sk in ["sentiment","combined_score"]:
    for fwd in ["f1","f5"]:
        obs,p=perm_test_meanLS(sk,fwd,n_perm=5000)
        perm_results[f"{sk}_{fwd}"]={"obs_mean_net":obs,"p_1sided":p}
        print(f"  {sk:14s} {fwd}: obs_mean_net={obs:+6.3f}  p_1sided={p:.4f}")

# =====================================================================
# DUMP JSON
# =====================================================================
out={
 "code_name":"adv_skeptic",
 "panel":{"rows":len(rows),"dates":18,"tickers":30,
          "usable_days_by_horizon":{k:summ(run_ls_series('sentiment',k))['n_days'] for k in HORIZONS},
          "universe_note":"11 names early -> 22-30 late; f5 only 14 realized days"},
 "baseline_daily_rebal_LS_net":{f"{lab}_{fwd}":baseline[(lab,fwd)] for (lab,fwd) in baseline},
 "a_momentum_disguise":{
    "pearson_sent_mom":pearson(S,M),"pearson_sent_tech":pearson(S,T),"pearson_tech_mom":pearson(T,M),
    "incremental_sentiment_on_momresidual_LS":{k:resid_incremental[k] for k in resid_incremental},
    "within_day_spearman_sent_vs_residfwd":resid_rho,
    "mom_controlled_double_sort_sum_net":double_sort,
 },
 "b_jackknife":{f"{sk}_{fwd}":jackknife[(sk,fwd)] for (sk,fwd) in jackknife},
 "c_overlap_effective_n":{f"{sk}_{fwd}":overlap_report[(sk,fwd)] for (sk,fwd) in overlap_report},
 "d_survivorship_tradeability":"see stdout: early vs late regime + dispersion",
 "e_cost_stress":{f"{sk}_{fwd}":cost_report[(sk,fwd)] for (sk,fwd) in cost_report},
 "permutation":perm_results,
}
with open("/Volumes/T9/BWE/40_EXPERIMENTS/round25_stockusbinance/radar_backtest/adv_skeptic/results.json","w") as f:
    json.dump(out,f,indent=2,default=str)
print("\nJSON written.")
