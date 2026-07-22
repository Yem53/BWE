#!/usr/bin/env python3
"""Adversarial verification of family F (funding-rate cross-section LS).
Independent re-implementation + 6 attacks:
(a) beta/momentum disguise (per-symbol beta estimation, momentum-proxy test)
(b) LODO re-run (contribution share + true drop-name re-run)
(c) overlapping holding periods / effective N (window disjointness + lag-1 autocorr)
(d) 1.5x cost stress recompute
(e) listing-date bias (cross-section width/composition over time, early-vs-late split)
(f) timezone/DST spot-checks (ET conversion of rth_open_ts, funding-sum reconciliation)
"""
import json, sqlite3, math
from collections import defaultdict
from datetime import datetime, timezone, timedelta

DIR = "/Volumes/T9/BWE/40_EXPERIMENTS/round27_usstock_alpha"
OUT = DIR + "/alpha_screen/F_verify"
CUTOFF_MS = 1781654399000
DEV_END = "2026-05-31"; VAL_START = "2026-06-01"; VAL_END = "2026-06-15"

rows = [json.loads(l) for l in open(DIR + "/panel_devval.jsonl")]
assert all(r["date"] <= VAL_END for r in rows), "panel leaks past val end"
by_sym_date = {(r["symbol"], r["date"]): r for r in rows}
all_dates = sorted(set(r["date"] for r in rows))
next_date = {d: all_dates[i+1] for i, d in enumerate(all_dates[:-1])}

# signal-eligible rows: use fund_overnight presence (check vs fund_pctile presence)
n_fo = sum(1 for r in rows if r.get("fund_overnight") is not None)
n_fp = sum(1 for r in rows if r.get("fund_pctile") is not None)
frows = [r for r in rows if r.get("fund_overnight") is not None]
byd = defaultdict(list)
for r in frows: byd[r["date"]].append(r)

by_sym = defaultdict(list)
for r in rows: by_sym[r["symbol"]].append(r)
prev_qv = {}
for s, rl in by_sym.items():
    rl.sort(key=lambda x: x["date"])
    for i, r in enumerate(rl):
        prev_qv[(s, r["date"])] = rl[i-1]["qv_day"] if i > 0 else None

kc = sqlite3.connect(DIR + "/tradfi_full.sqlite3")
fund_all = defaultdict(list)
for s, ft, fr_ in kc.execute(
        "SELECT symbol,funding_time,funding_rate FROM funding WHERE funding_time<=?", (CUTOFF_MS,)):
    fund_all[s].append((ft, fr_))
for s in fund_all: fund_all[s].sort()

def fund_in(sym, t0, t1):
    return sum(fr_ for ft, fr_ in fund_all.get(sym, ()) if t0 < ft <= t1) * 100.0

# universe EW baselines
ew_rth, ew_on = {}, {}
tmp_r, tmp_o = defaultdict(list), defaultdict(list)
for r in rows:
    if r.get("r_o_close") is not None: tmp_r[r["date"]].append(r["r_o_close"])
    if r.get("overnight_ret") is not None: tmp_o[r["date"]].append(r["overnight_ret"])
for d in all_dates:
    if tmp_r[d]: ew_rth[d] = sum(tmp_r[d]) / len(tmp_r[d])
    if tmp_o[d]: ew_on[d] = sum(tmp_o[d]) / len(tmp_o[d])

def cost_rt(sym, d):
    qv = prev_qv.get((sym, d))
    spread_side = 0.05 if (qv is not None and qv < 5e6) else 0.02
    return 0.08 + 2 * spread_side

def mean(x): return sum(x) / len(x) if x else None

in_dev = lambda d: d <= DEV_END
in_val = lambda d: VAL_START <= d <= VAL_END

# ---------------- independent engine ----------------
def run_cell(grouping, direction, window, dates_filter, cost_mult=1.0, drop_sym=None,
             signal_key="fund_overnight"):
    min_n = 9 if grouping == "tercile" else 20
    out = []
    for d in sorted(byd):
        if not dates_filter(d): continue
        cs = [r for r in byd[d] if r["symbol"] != drop_sym] if drop_sym else byd[d]
        # signal override (momentum-proxy attack): need signal value present
        cs = [r for r in cs if r.get(signal_key) is not None]
        n = len(cs)
        if n < min_n: continue
        k = n // 3 if grouping == "tercile" else max(2, n // 10)
        srt = sorted(cs, key=lambda x: (x[signal_key], x["symbol"]))
        neg, pos = srt[:k], srt[-k:]
        longs, shorts = (neg, pos) if direction == "harvest" else (pos, neg)
        def held(r, side):
            if window == "rth":
                pr = r.get("r_o_close")
                if pr is None: return None
                fu = fund_in(r["symbol"], r["rth_open_ts"], r["rth_close_ts"])
            else:
                nd = next_date.get(d)
                if nd is None: return None
                r2 = by_sym_date.get((r["symbol"], nd))
                if r2 is None or r2.get("overnight_ret") is None: return None
                pr, fu = r2["overnight_ret"], (r2.get("fund_overnight") or 0.0)
            c = cost_rt(r["symbol"], d) * cost_mult
            if side == "L": return dict(sym=r["symbol"], price=pr, fund=-fu, cost=c)
            return dict(sym=r["symbol"], price=-pr, fund=+fu, cost=c)
        L = [h for h in (held(r, "L") for r in longs) if h]
        S = [h for h in (held(r, "S") for r in shorts) if h]
        if not L or not S: continue
        ewd = ew_rth.get(d) if window == "rth" else ew_on.get(next_date.get(d, ""))
        lp, sp = mean([h["price"] for h in L]), mean([h["price"] for h in S])
        lf, sf = mean([h["fund"] for h in L]), mean([h["fund"] for h in S])
        lc, sc = mean([h["cost"] for h in L]), mean([h["cost"] for h in S])
        out.append(dict(date=d, n_cs=n, k=k, ew=ewd,
                        net=lp+sp+lf+sf-lc-sc, gross=lp+sp+lf+sf,
                        price=lp+sp, fund=lf+sf, cost=lc+sc,
                        Lsyms=[h["sym"] for h in L], Ssyms=[h["sym"] for h in S],
                        names=[(h["sym"], "L", h["price"]+h["fund"]-h["cost"], len(L)) for h in L]
                             +[(h["sym"], "S", h["price"]+h["fund"]-h["cost"], len(S)) for h in S]))
    return out

def summ(days):
    if not days: return dict(n_days=0)
    nets = [x["net"] for x in days]; N = len(nets)
    mu = mean(nets)
    sd = (sum((v-mu)**2 for v in nets)/(N-1))**0.5 if N > 1 else float("nan")
    t = mu/(sd/math.sqrt(N)) if N > 1 and sd > 0 else float("nan")
    ac = None
    if N > 2:
        x0, x1 = nets[:-1], nets[1:]
        m0, m1 = mean(x0), mean(x1)
        num = sum((a-m0)*(b-m1) for a, b in zip(x0, x1))
        den = math.sqrt(sum((a-m0)**2 for a in x0)*sum((b-m1)**2 for b in x1))
        ac = num/den if den > 0 else None
    return dict(n_days=N, mean_net=round(mu, 4), sum_net=round(sum(nets), 3),
                t=round(t, 2), win=round(sum(1 for v in nets if v > 0)/N, 3),
                mean_gross=round(mean([x["gross"] for x in days]), 4),
                mean_price=round(mean([x["price"] for x in days]), 4),
                mean_fund=round(mean([x["fund"] for x in days]), 4),
                mean_cost=round(mean([x["cost"] for x in days]), 4),
                lag1_autocorr=round(ac, 3) if ac is not None else None)

def lodo_contrib(days):
    total = sum(x["net"] for x in days)
    if total <= 0: return dict(total=round(total, 3), verdict="n/a")
    md = max(days, key=lambda x: x["net"])
    contrib = defaultdict(float)
    for x in days:
        for nm, side, pnl, legn in x["names"]: contrib[nm] += pnl/legn
    top = sorted(contrib.items(), key=lambda kv: -kv[1])[:5]
    return dict(total=round(total, 3), max_day=md["date"], max_day_frac=round(md["net"]/total, 3),
                max_name=top[0][0], max_name_frac=round(top[0][1]/total, 3),
                top5=[(nm, round(v, 3)) for nm, v in top],
                verdict="FAIL" if (md["net"]/total > .4 or top[0][1]/total > .4) else "PASS")

results = {"checks": {}}

# ---- 0. sample structure verification ----
def struct(f):
    rs = [r for r in frows if f(r["date"])]
    ds = sorted(set(r["date"] for r in rs))
    bym = defaultdict(int)
    for d in ds: bym[d[:7]] += 1
    return dict(rows=len(rs), symbols=len(set(r["symbol"] for r in rs)), days=len(ds),
                days_by_month=dict(bym),
                days_cs_ge9=sum(1 for d in ds if len(byd[d]) >= 9),
                days_cs_ge20=sum(1 for d in ds if len(byd[d]) >= 20))
results["checks"]["sample"] = dict(
    dev=struct(in_dev), val=struct(in_val), panel_rows=len(rows),
    rows_fund_overnight=n_fo, rows_fund_pctile=n_fp)

# ---- 1. independent recompute of all 8 dev cells + 1.5x ----
cells = [(g, dr, w) for g in ("tercile", "decile") for dr in ("harvest", "momentum")
         for w in ("rth", "overnight")]
recomp = {}
for g, dr, w in cells:
    key = f"{g}|{dr}|{w}"
    dd = run_cell(g, dr, w, in_dev)
    s = summ(dd)
    s15 = summ(run_cell(g, dr, w, in_dev, cost_mult=1.5))
    recomp[key] = dict(dev=s, lodo=lodo_contrib(dd),
                       cost15=dict(mean_net=s15.get("mean_net"), sum_net=s15.get("sum_net")))
results["checks"]["recompute"] = recomp

# ---- 2. attack (a): true per-symbol beta stripping ----
def est_betas(ret_key, ew_map):
    betas = {}
    for s, rl in by_sym.items():
        xs, ys = [], []
        for r in rl:
            if not in_dev(r["date"]): continue
            y = r.get(ret_key); x = ew_map.get(r["date"])
            if y is None or x is None: continue
            xs.append(x); ys.append(y)
        if len(xs) < 10: continue
        mx, my = mean(xs), mean(ys)
        vx = sum((a-mx)**2 for a in xs)
        if vx == 0: continue
        betas[s] = sum((a-mx)*(b-my) for a, b in zip(xs, ys)) / vx
    return betas

beta_rth = est_betas("r_o_close", ew_rth)
beta_on = est_betas("overnight_ret", ew_on)

def beta_adjusted(days, betamap, ew_key="ew"):
    adj, bl_list, bs_list = [], [], []
    for x in days:
        if x[ew_key] is None: continue
        bl = mean([betamap.get(s, 1.0) for s in x["Lsyms"]])
        bs = mean([betamap.get(s, 1.0) for s in x["Ssyms"]])
        adj.append(x["price"] - (bl - bs) * x[ew_key])
        bl_list.append(bl); bs_list.append(bs)
    if not adj: return None
    N = len(adj); mu = mean(adj)
    sd = (sum((v-mu)**2 for v in adj)/(N-1))**0.5 if N > 1 else float("nan")
    return dict(n=N, mean_beta_adj_price=round(mu, 4),
                t=round(mu/(sd/math.sqrt(N)), 2) if sd and sd > 0 else None,
                mean_long_beta=round(mean(bl_list), 2), mean_short_beta=round(mean(bs_list), 2))

d_harv = run_cell("tercile", "harvest", "rth", in_dev)
d_mom = run_cell("tercile", "momentum", "overnight", in_dev)
results["checks"]["beta_strip"] = dict(
    tercile_harvest_rth=beta_adjusted(d_harv, beta_rth),
    tercile_momentum_overnight=beta_adjusted(d_mom, beta_on),
    note="beta est per-symbol OLS vs universe EW on dev; adj = LS_price - (betaL-betaS)*EW_day")

# ---- 2b. momentum-proxy: is fund_overnight just lagged price momentum? ----
def spearman(a, b):
    def rank(v):
        idx = sorted(range(len(v)), key=lambda i: v[i]); rk = [0.0]*len(v); i = 0
        while i < len(idx):
            j = i
            while j+1 < len(idx) and v[idx[j+1]] == v[idx[i]]: j += 1
            rr = (i+j)/2.0 + 1
            for t in range(i, j+1): rk[idx[t]] = rr
            i = j+1
        return rk
    ra, rb = rank(a), rank(b)
    ma, mb = mean(ra), mean(rb)
    num = sum((x-ma)*(y-mb) for x, y in zip(ra, rb))
    da = math.sqrt(sum((x-ma)**2 for x in ra)); db = math.sqrt(sum((y-mb)**2 for y in rb))
    return num/(da*db) if da > 0 and db > 0 else None

rho_on, rho_prev = [], []
prev_rth = {}  # (sym, date)-> prev day's r_o_close
for s, rl in by_sym.items():
    for i, r in enumerate(rl):
        if i > 0 and rl[i-1].get("r_o_close") is not None:
            prev_rth[(s, r["date"])] = rl[i-1]["r_o_close"]
for d in sorted(byd):
    if not in_dev(d): continue
    cs = [r for r in byd[d] if r.get("overnight_ret") is not None]
    if len(cs) >= 9:
        rho = spearman([r["fund_overnight"] for r in cs], [r["overnight_ret"] for r in cs])
        if rho is not None: rho_on.append(rho)
    cs2 = [r for r in byd[d] if prev_rth.get((r["symbol"], d)) is not None]
    if len(cs2) >= 9:
        rho = spearman([r["fund_overnight"] for r in cs2],
                       [prev_rth[(r["symbol"], d)] for r in cs2])
        if rho is not None: rho_prev.append(rho)
# same strategy with overnight_ret as signal instead of funding
mom_price = summ(run_cell("tercile", "momentum", "overnight", in_dev, signal_key="overnight_ret"))
# leg overlap funding-signal vs overnight-ret-signal
d_mom_p = run_cell("tercile", "momentum", "overnight", in_dev, signal_key="overnight_ret")
ovl, tot = 0, 0
pmap = {x["date"]: x for x in d_mom_p}
for x in d_mom:
    y = pmap.get(x["date"])
    if not y: continue
    ovl += len(set(x["Lsyms"]) & set(y["Lsyms"])) + len(set(x["Ssyms"]) & set(y["Ssyms"]))
    tot += len(x["Lsyms"]) + len(x["Ssyms"])
results["checks"]["momentum_proxy"] = dict(
    n_days_rho=len(rho_on),
    mean_rho_fund_vs_same_overnight_ret=round(mean(rho_on), 3) if rho_on else None,
    mean_rho_fund_vs_prev_rth_ret=round(mean(rho_prev), 3) if rho_prev else None,
    strategy_with_overnightret_signal=mom_price,
    leg_overlap_fund_vs_ret_signal=round(ovl/tot, 3) if tot else None)

# ---- 3. attack (b): true LODO drop-and-rerun ----
def drop_rerun(g, dr, w, sym):
    s = summ(run_cell(g, dr, w, in_dev, drop_sym=sym))
    s15 = summ(run_cell(g, dr, w, in_dev, cost_mult=1.5, drop_sym=sym))
    return dict(drop=sym, mean_net=s.get("mean_net"), sum_net=s.get("sum_net"),
                t=s.get("t"), cost15_mean_net=s15.get("mean_net"))
results["checks"]["lodo_rerun"] = dict(
    tercile_harvest_rth_dropPAYP=drop_rerun("tercile", "harvest", "rth", "PAYPUSDT"),
    tercile_momentum_on_dropMU=drop_rerun("tercile", "momentum", "overnight", "MUUSDT"),
    decile_harvest_rth_dropFLNC=drop_rerun("decile", "harvest", "rth", "FLNCUSDT"),
    decile_momentum_on_dropNBIS=drop_rerun("decile", "momentum", "overnight", "NBISUSDT"))
# leave-one-day
def drop_day(days, d0):
    return summ([x for x in days if x["date"] != d0])
results["checks"]["lodo_day"] = dict(
    tercile_harvest_rth_drop_0420=drop_day(d_harv, "2026-04-20"),
    tercile_momentum_on_drop_0507=drop_day(d_mom, "2026-05-07"))

# ---- 4. attack (c): window disjointness ----
# RTH windows same-day, disjoint by construction; overnight window D close -> D+1 open.
# Verify no two consecutive formation dates produce overlapping [t0,t1] intervals.
iv = []
for x in d_mom:
    nd = next_date.get(x["date"])
    r2s = [by_sym_date.get((s, nd)) for s in x["Lsyms"] if by_sym_date.get((s, nd))]
    if r2s:
        iv.append((by_sym_date[(x["Lsyms"][0], x["date"])]["rth_close_ts"],
                   r2s[0]["rth_open_ts"], x["date"]))
iv.sort()
overlaps = sum(1 for i in range(len(iv)-1) if iv[i][1] > iv[i+1][0])
results["checks"]["overlap"] = dict(
    n_overnight_intervals=len(iv), n_overlapping_pairs=overlaps,
    lag1_autocorr_harvest_rth=summ(d_harv)["lag1_autocorr"],
    lag1_autocorr_momentum_on=summ(d_mom)["lag1_autocorr"],
    note="overnight hold D_close->D+1_open; consecutive intervals disjoint if no overlap pairs")

# ---- 5. attack (e): listing-date / cross-section composition ----
first_fund = {s: min(ft for ft, _ in v) for s, v in fund_all.items()}
first_fund_date = {s: datetime.fromtimestamp(t/1000, tz=timezone.utc).strftime("%Y-%m-%d")
                   for s, t in first_fund.items()}
cs_by_day = {d: len(byd[d]) for d in sorted(byd) if in_dev(d)}
terc_days = [d for d in sorted(byd) if in_dev(d) and len(byd[d]) >= 9]
bym = defaultdict(int)
for d in terc_days: bym[d[:7]] += 1
# median qv of cross-section early vs late
early = [d for d in terc_days if d < "2026-05-01"]; late = [d for d in terc_days if d >= "2026-05-01"]
def med_qv(dl):
    q = [r["qv_day"] for d in dl for r in byd[d] if r.get("qv_day") is not None]
    q.sort(); return round(q[len(q)//2], 0) if q else None
# split-period performance of the 2 positive cells
h_early = summ([x for x in d_harv if x["date"] < "2026-05-01"])
h_late = summ([x for x in d_harv if x["date"] >= "2026-05-01"])
m_early = summ([x for x in d_mom if x["date"] < "2026-05-01"])
m_late = summ([x for x in d_mom if x["date"] >= "2026-05-01"])
results["checks"]["listing_bias"] = dict(
    tercile_days_by_month=dict(bym),
    n_symbols_funding_start_by_month=dict(sorted(
        (m, sum(1 for s, dd in first_fund_date.items() if dd[:7] == m))
        for m in set(v[:7] for v in first_fund_date.values()))),
    median_qv_early=med_qv(early), median_qv_late=med_qv(late),
    harvest_rth_early=dict(n=h_early.get("n_days"), mean_net=h_early.get("mean_net")),
    harvest_rth_late=dict(n=h_late.get("n_days"), mean_net=h_late.get("mean_net")),
    momentum_on_early=dict(n=m_early.get("n_days"), mean_net=m_early.get("mean_net")),
    momentum_on_late=dict(n=m_late.get("n_days"), mean_net=m_late.get("mean_net")))

# ---- 6. attack (f): DST / timezone spot-checks ----
DST_SWITCH = "2026-03-08"
def to_et(ms, date):
    off = -5 if date < DST_SWITCH else -4
    return (datetime.fromtimestamp(ms/1000, tz=timezone.utc)
            + timedelta(hours=off)).strftime("%Y-%m-%d %H:%M:%S")
spot = []
picks = []
seen = set()
for r in frows:
    m = r["date"][:7]
    if m in ("2026-02", "2026-03", "2026-05") and m not in seen and r.get("prev_close") is not None:
        # find prev row for prev_close_ts
        rl = by_sym[r["symbol"]]
        idx = next(i for i, q in enumerate(rl) if q["date"] == r["date"])
        if idx == 0: continue
        picks.append((r, rl[idx-1])); seen.add(m)
# also force one straddling DST switch week (first March date after 03-08)
for r in frows:
    if "2026-03-09" <= r["date"] <= "2026-03-13" and r.get("prev_close") is not None:
        rl = by_sym[r["symbol"]]
        idx = next(i for i, q in enumerate(rl) if q["date"] == r["date"])
        if idx > 0:
            picks.append((r, rl[idx-1])); break
for r, rp in picks:
    fsum = fund_in(r["symbol"], rp["rth_close_ts"], r["rth_open_ts"])
    nset_on = sum(1 for ft, _ in fund_all.get(r["symbol"], ())
                  if rp["rth_close_ts"] < ft <= r["rth_open_ts"])
    nset_rth = sum(1 for ft, _ in fund_all.get(r["symbol"], ())
                   if r["rth_open_ts"] < ft <= r["rth_close_ts"])
    spot.append(dict(symbol=r["symbol"], date=r["date"],
                     open_ET=to_et(r["rth_open_ts"], r["date"]),
                     close_ET=to_et(r["rth_close_ts"], r["date"]),
                     panel_fund_overnight=r.get("fund_overnight"),
                     sqlite_fund_prevclose_to_open=round(fsum, 6),
                     match=abs((r.get("fund_overnight") or 0) - fsum) < 1e-6,
                     n_settle_overnight=nset_on, n_settle_rth=nset_rth))
# funding cadence check
gaps = defaultdict(int)
for s, v in list(fund_all.items())[:20]:
    for i in range(1, len(v)):
        gaps[v[i][0]-v[i-1][0]] += 1
results["checks"]["dst_spot"] = dict(events=spot,
    funding_gap_ms_top=sorted(gaps.items(), key=lambda kv: -kv[1])[:3])

json.dump(results, open(OUT + "/verify_F_results.json", "w"), indent=1, ensure_ascii=False)
print(json.dumps(results, indent=1, ensure_ascii=False))
