#!/usr/bin/env python3
"""族F: 资金费横截面 LS 筛查 (round27 US-stock perps)
Signal: fund_overnight (prev_close→open 累计资金费%, 多头视角=正值多头支付), 当日开盘已知(因果).
Windows: RTH(D open→close) / next-overnight(D close→D+1 open).
Directions: harvest(多最负费率+空最正, 收费) / momentum(反向).
Groupings: tercile(n>=9) / decile(n>=20).
Costs: taker 0.08% RT + spread 2bp/side (prev-day qv<$5M → 5bp/side), 双腿.
Discipline: β-strip legs vs universe EW, LODO day/name >40% kill, dev选/val冻结验一次.
"""
import json, sqlite3, math
from collections import defaultdict

DIR = "/Volumes/T9/BWE/40_EXPERIMENTS/round27_usstock_alpha"
CUTOFF_MS = 1781654399000
DEV_END = "2026-05-31"; VAL_START = "2026-06-01"; VAL_END = "2026-06-15"

# ---------- load panel ----------
rows = [json.loads(l) for l in open(DIR + "/panel_devval.jsonl")]
assert all(r["date"] <= VAL_END for r in rows)
by_sym_date = {(r["symbol"], r["date"]): r for r in rows}
all_dates = sorted(set(r["date"] for r in rows))
next_date = {d: all_dates[i+1] for i, d in enumerate(all_dates[:-1])}
frows = [r for r in rows if r.get("fund_pctile") is not None]
byd = defaultdict(list)
for r in frows: byd[r["date"]].append(r)

# prev row per symbol (for causal qv cost tier)
by_sym = defaultdict(list)
for r in rows: by_sym[r["symbol"]].append(r)
prev_qv = {}
for s, rl in by_sym.items():
    rl.sort(key=lambda x: x["date"])
    for i, r in enumerate(rl):
        prev_qv[(s, r["date"])] = rl[i-1]["qv_day"] if i > 0 else None

# ---------- RTH funding from sqlite (for decomposition of RTH window) ----------
kc = sqlite3.connect(DIR + "/tradfi_full.sqlite3")
fund_all = defaultdict(list)
for s, ft, fr_ in kc.execute("SELECT symbol,funding_time,funding_rate FROM funding WHERE funding_time<=?", (CUTOFF_MS,)):
    fund_all[s].append((ft, fr_))
for s in fund_all: fund_all[s].sort()
def fund_in(sym, t0, t1):  # sum funding_rate% in (t0, t1]
    return sum(fr_ for ft, fr_ in fund_all.get(sym, ()) if t0 < ft <= t1) * 100.0

# universe EW returns (β-strip baseline): all panel rows that date
ew_rth = {d: None for d in all_dates}; ew_on = {d: None for d in all_dates}
tmp_r = defaultdict(list); tmp_o = defaultdict(list)
for r in rows:
    if r.get("r_o_close") is not None: tmp_r[r["date"]].append(r["r_o_close"])
    if r.get("overnight_ret") is not None: tmp_o[r["date"]].append(r["overnight_ret"])
for d in all_dates:
    if tmp_r[d]: ew_rth[d] = sum(tmp_r[d])/len(tmp_r[d])
    if tmp_o[d]: ew_on[d] = sum(tmp_o[d])/len(tmp_o[d])

def cost_rt(sym, d):  # % round trip per name
    qv = prev_qv.get((sym, d))
    spread_side = 0.05 if (qv is not None and qv < 5e6) else 0.02
    return 0.08 + 2*spread_side

def mean(x): return sum(x)/len(x) if x else None

# ---------- daily portfolio engine ----------
def run_config(grouping, direction, window, dates_filter, cost_mult=1.0):
    """returns list of per-day dicts"""
    min_n = 9 if grouping == "tercile" else 20
    out = []
    for d in sorted(byd):
        if not dates_filter(d): continue
        cs = byd[d]
        n = len(cs)
        if n < min_n: continue
        k = n//3 if grouping == "tercile" else max(2, n//10)
        srt = sorted(cs, key=lambda x: (x["fund_overnight"], x["symbol"]))
        neg, pos = srt[:k], srt[-k:]          # most-negative / most-positive funding
        if direction == "harvest": longs, shorts = neg, pos
        else:                      longs, shorts = pos, neg
        # returns for the window
        def held(r, side):
            if window == "rth":
                pr = r.get("r_o_close")
                if pr is None: return None
                fu = fund_in(r["symbol"], r["rth_open_ts"], r["rth_close_ts"])
                sym, dd = r["symbol"], r["date"]
            else:  # next overnight: D close → D+1 open
                nd = next_date.get(d)
                if nd is None: return None
                r2 = by_sym_date.get((r["symbol"], nd))
                if r2 is None or r2.get("overnight_ret") is None: return None
                pr, fu = r2["overnight_ret"], (r2.get("fund_overnight") or 0.0)
                sym, dd = r["symbol"], d
            c = cost_rt(sym, dd) * cost_mult
            if side == "L":  return dict(sym=sym, price=pr,  fund=-fu, cost=c)
            else:            return dict(sym=sym, price=-pr, fund=+fu, cost=c)
        L = [h for h in (held(r, "L") for r in longs) if h]
        S = [h for h in (held(r, "S") for r in shorts) if h]
        if not L or not S: continue
        ewd = ew_rth[d] if window == "rth" else ew_on.get(next_date.get(d, ""), None)
        lp, sp = mean([h["price"] for h in L]), mean([h["price"] for h in S])
        lf, sf = mean([h["fund"] for h in L]), mean([h["fund"] for h in S])
        lc, sc = mean([h["cost"] for h in L]), mean([h["cost"] for h in S])
        gross = lp + sp + lf + sf
        net = gross - lc - sc
        out.append(dict(date=d, n_cs=n, k=k, gross=gross, net=net,
                        price_comp=lp+sp, fund_comp=lf+sf, cost=lc+sc,
                        long_excess=(lp-ewd) if ewd is not None else None,
                        short_excess=(sp+ewd) if ewd is not None else None,
                        names_L=[(h["sym"], h["price"]+h["fund"]-h["cost"]) for h in L],
                        names_S=[(h["sym"], h["price"]+h["fund"]-h["cost"]) for h in S]))
    return out

def summarize(days):
    if not days: return dict(n_days=0)
    nets = [x["net"] for x in days]; N = len(nets)
    mu = mean(nets); sd = (sum((v-mu)**2 for v in nets)/(N-1))**0.5 if N > 1 else float("nan")
    t = mu/(sd/math.sqrt(N)) if N > 1 and sd > 0 else float("nan")
    strip = [x["price_comp"] for x in days]  # LS price comp == β-stripped LS (EW cancels across legs)
    le = [x["long_excess"] for x in days if x["long_excess"] is not None]
    se = [x["short_excess"] for x in days if x["short_excess"] is not None]
    return dict(n_days=N, mean_net=round(mu,4), sum_net=round(sum(nets),3), t=round(t,2),
                win=round(sum(1 for v in nets if v > 0)/N,3),
                mean_gross=round(mean([x["gross"] for x in days]),4),
                mean_price_comp=round(mean(strip),4),
                mean_fund_comp=round(mean([x["fund_comp"] for x in days]),4),
                mean_cost=round(mean([x["cost"] for x in days]),4),
                mean_long_excess=round(mean(le),4) if le else None,
                mean_short_excess=round(mean(se),4) if se else None,
                mean_k=round(mean([x["k"] for x in days]),1),
                mean_cs=round(mean([x["n_cs"] for x in days]),1))

def lodo(days):
    """leave-one-day / leave-one-name contribution >40% → fail. Only meaningful if total>0."""
    total = sum(x["net"] for x in days)
    res = dict(total=round(total,3))
    if total <= 0 or not days:
        res["verdict"] = "n/a (total<=0)"; return res
    worst_day = max(days, key=lambda x: x["net"])
    day_frac = worst_day["net"]/total
    contrib = defaultdict(float)
    for x in days:
        for nm, pnl in x["names_L"]: contrib[nm] += pnl/len(x["names_L"])
        for nm, pnl in x["names_S"]: contrib[nm] += pnl/len(x["names_S"])
    top_names = sorted(contrib.items(), key=lambda kv: -kv[1])[:5]
    name_frac = top_names[0][1]/total if top_names else 0
    res.update(max_day=worst_day["date"], max_day_frac=round(day_frac,3),
               max_name=top_names[0][0] if top_names else None, max_name_frac=round(name_frac,3),
               top5_names=[(nm, round(v,3)) for nm, v in top_names],
               verdict=("FAIL" if (day_frac > 0.40 or name_frac > 0.40) else "PASS"))
    return res

in_dev = lambda d: d <= DEV_END
in_val = lambda d: VAL_START <= d <= VAL_END

# ---------- run all dev cells ----------
results = {"cells": {}, "n_cells": 0}
cells = [(g, dr, w) for g in ("tercile", "decile") for dr in ("harvest", "momentum") for w in ("rth", "overnight")]
for g, dr, w in cells:
    key = f"{g}|{dr}|{w}"
    dev_days = run_config(g, dr, w, in_dev)
    s = summarize(dev_days)
    ld = lodo(dev_days)
    dev15 = run_config(g, dr, w, in_dev, cost_mult=1.5)
    s15 = summarize(dev15)
    results["cells"][key] = dict(dev=s, dev_lodo=ld,
                                 dev_cost1_5x=dict(mean_net=s15.get("mean_net"), sum_net=s15.get("sum_net")))
    results["n_cells"] += 1

# ---------- persistence & turnover ----------
def spearman(a, b):
    def rank(v):
        idx = sorted(range(len(v)), key=lambda i: v[i]); rk = [0.0]*len(v); i = 0
        while i < len(idx):
            j = i
            while j+1 < len(idx) and v[idx[j+1]] == v[idx[i]]: j += 1
            r = (i+j)/2.0 + 1
            for t in range(i, j+1): rk[idx[t]] = r
            i = j+1
        return rk
    ra, rb = rank(a), rank(b); n = len(a)
    ma, mb = mean(ra), mean(rb)
    num = sum((x-ma)*(y-mb) for x, y in zip(ra, rb))
    da = math.sqrt(sum((x-ma)**2 for x in ra)); db = math.sqrt(sum((y-mb)**2 for y in rb))
    return num/(da*db) if da > 0 and db > 0 else None

pers = []
dev_dates_f = [d for d in sorted(byd) if in_dev(d)]
for i, d in enumerate(dev_dates_f[:-1]):
    nd = dev_dates_f[i+1]
    if next_date.get(d) != nd: pass  # allow gaps: consecutive funding-cross-section days
    m0 = {r["symbol"]: r["fund_overnight"] for r in byd[d]}
    m1 = {r["symbol"]: r["fund_overnight"] for r in byd[nd]}
    common = sorted(set(m0) & set(m1))
    if len(common) < 8: continue
    rho = spearman([m0[s] for s in common], [m1[s] for s in common])
    if rho is not None: pers.append(dict(date=d, n=len(common), rho=round(rho,3)))
rhos = [p["rho"] for p in pers]
results["persistence"] = dict(n_day_pairs=len(rhos),
                              mean_rho=round(mean(rhos),3) if rhos else None,
                              median_rho=round(sorted(rhos)[len(rhos)//2],3) if rhos else None,
                              pct_positive=round(sum(1 for r in rhos if r > 0)/len(rhos),3) if rhos else None)

# tercile-leg turnover (dev): fraction of leg names retained next cross-section day
stay, tot = 0, 0
for i, d in enumerate(dev_dates_f[:-1]):
    cs0, cs1 = byd[d], byd[dev_dates_f[i+1]]
    if len(cs0) < 9 or len(cs1) < 9: continue
    def legs(cs):
        k = len(cs)//3
        srt = sorted(cs, key=lambda x: (x["fund_overnight"], x["symbol"]))
        return set(x["symbol"] for x in srt[:k]), set(x["symbol"] for x in srt[-k:])
    l0, s0 = legs(cs0); l1, s1 = legs(cs1)
    stay += len(l0 & l1) + len(s0 & s1); tot += len(l0) + len(s0)
results["tercile_leg_retention_dev"] = round(stay/tot, 3) if tot else None

# ---------- sample structure ----------
def struct(f):
    rs = [r for r in frows if f(r["date"])]
    ds = sorted(set(r["date"] for r in rs))
    bym = defaultdict(int)
    for d in ds: bym[d[:7]] += 1
    return dict(rows=len(rs), symbols=len(set(r["symbol"] for r in rs)), days=len(ds),
                days_by_month=dict(bym),
                days_cs_ge9=sum(1 for d in ds if len(byd[d]) >= 9),
                days_cs_ge20=sum(1 for d in ds if len(byd[d]) >= 20))
results["sample"] = dict(dev=struct(in_dev), val=struct(in_val),
                         panel_rows_total=len(rows), rows_with_funding=len(frows))

# ---------- freeze & val (dev net>0 AND LODO PASS only) ----------
survivors = [k for k, v in results["cells"].items()
             if v["dev"].get("n_days", 0) > 0 and v["dev"]["mean_net"] > 0 and v["dev_lodo"]["verdict"] == "PASS"]
results["frozen_for_val"] = survivors
for key in survivors:
    g, dr, w = key.split("|")
    val_days = run_config(g, dr, w, in_val)
    results["cells"][key]["val"] = summarize(val_days)
    results["cells"][key]["val_lodo"] = lodo(val_days)
    v15 = summarize(run_config(g, dr, w, in_val, cost_mult=1.5))
    results["cells"][key]["val_cost1_5x"] = dict(mean_net=v15.get("mean_net"), sum_net=v15.get("sum_net"))

json.dump(results, open(DIR + "/alpha_screen/F/results_F.json", "w"), indent=1, ensure_ascii=False)
print(json.dumps(results, indent=1, ensure_ascii=False))
