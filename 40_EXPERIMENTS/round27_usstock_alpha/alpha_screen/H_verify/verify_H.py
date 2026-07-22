#!/usr/bin/env python3
"""
Adversarial verification of family H (H_new_listing) — round27.
Independent re-implementation (own code, own seed) of:
 (a) beta-hat strip recompute (+ robustness variants)
 (b) clustered-t / LOBO / batch-sign recount (dev + val)
 (c) hand-written permutation, different seed + apples-to-apples subset check
 (d) cost / liquidity realism (qv day0-3, funding coverage, net recompute)
 (e) timestamp & DST spot checks (2026-03-08), holdout-wall audit

Audited claims (from results_H.json / headline):
  dev 50 ev / 17 batches; val 37 / 6; 87 total <= 06-15; 18 post-holdout
  WIN|raw|e0|h1: gross -1.7337, t_clust -3.348, 14/17 batches day1<0
  PATH|resid|d1: gross -1.2122, t_clust -2.983, net +0.9649
  val day1: raw -0.51 (t -0.609), resid -0.6983 (t -1.30), 4/6 batches neg
  permutation: p(best|t|=3.348 vs null max-|t|) = 0.246, null p50 2.789 p90 4.002
  funding day0 mean +0.0352%/8h vs mature +0.0067 (~5.2x); qv d0-3 median $4.9M
"""
import json
import math
import random
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import numpy as np

ROOT = "/Volumes/T9/BWE/40_EXPERIMENTS/round27_usstock_alpha"
CUTOFF_MS = 1781654399000
ET = ZoneInfo("America/New_York")
MATURE = 11
random.seed(918273645)  # different from family script's 20260706

R = {}  # verification report

# ---------- load panel (independent parse) ----------
recs = [json.loads(l) for l in open(f"{ROOT}/panel_devval.jsonl")]
P = defaultdict(list)
for r in recs:
    P[r["symbol"]].append(r)
for s in P:
    P[s].sort(key=lambda r: r["date"])

syms = sorted(P)
lday = {s: P[s][0]["date"] for s in syms}
dev = [s for s in syms if lday[s] <= "2026-05-31"]
val = [s for s in syms if "2026-06-01" <= lday[s] <= "2026-06-15"]

db = sqlite3.connect(f"file:{ROOT}/tradfi_full.sqlite3?mode=ro", uri=True)
n_db_syms = db.execute("SELECT COUNT(DISTINCT symbol) FROM klines_1m").fetchone()[0]

R["a_split"] = {
    "n_panel_syms": len(syms),
    "n_dev": len(dev), "n_dev_batches": len({lday[s] for s in dev}),
    "n_val": len(val), "n_val_batches": len({lday[s] for s in val}),
    "n_post_holdout": n_db_syms - len(syms),
    "claim": "87 total, dev 50/17, val 37/6, 18 untouched",
}

# ---------- (e) timestamp / DST / holdout-wall audit ----------
dst_probe = {}
for s in syms:
    for r in P[s]:
        d = r["date"]
        if d in ("2026-03-06", "2026-03-09", "2026-03-05", "2026-03-10") and d not in dst_probe:
            o = datetime.fromtimestamp(r["rth_open_ts"] / 1000, tz=timezone.utc).astimezone(ET)
            c = datetime.fromtimestamp(r["rth_close_ts"] / 1000, tz=timezone.utc).astimezone(ET)
            ou = datetime.fromtimestamp(r["rth_open_ts"] / 1000, tz=timezone.utc)
            dst_probe[d] = {"open_ET": o.strftime("%H:%M"), "lastbar_ET": c.strftime("%H:%M"),
                            "open_UTC": ou.strftime("%H:%M")}
max_ts = max(r["rth_close_ts"] for s in syms for r in P[s])
max_date = max(r["date"] for s in syms for r in P[s])
# listing date vs first kline ET date
mism = []
for s in syms:
    fot = db.execute("SELECT MIN(ot) FROM klines_1m WHERE symbol=?", (s,)).fetchone()[0]
    fd = datetime.fromtimestamp(fot / 1000, tz=timezone.utc).astimezone(ET).strftime("%Y-%m-%d")
    if fd != lday[s]:
        mism.append((s, fd, lday[s]))
R["e_timestamps"] = {
    "dst_probe": dst_probe,
    "panel_max_close_ts_lte_cutoff": bool(max_ts <= CUTOFF_MS),
    "panel_max_date": max_date,
    "n_firstkline_vs_panelday0_mismatch": len(mism),
    "mismatches_first10": mism[:10],
}

# ---------- daily returns / market / beta (independent implementation) ----------
for s in syms:
    c = [r["rth_close"] for r in P[s]]
    P_s = P[s]
    ret = [None] + [(c[i] / c[i - 1] - 1) * 100 for i in range(1, len(c))]
    for i, r in enumerate(P_s):
        r["_ret"] = ret[i]
        r["_i"] = i

# date-pair -> mature members
pairm = defaultdict(dict)
for s in syms:
    for i in range(1, len(P[s])):
        if P[s][i]["_ret"] is not None and i >= MATURE:
            pairm[(P[s][i - 1]["date"], P[s][i]["date"])][s] = P[s][i]["_ret"]

def mkt_ret(s, d0, d1):
    mem = pairm.get((d0, d1), {})
    vals = [v for k, v in mem.items() if k != s]
    return float(np.mean(vals)) if len(vals) >= 3 else None

for s in syms:
    for i in range(1, len(P[s])):
        P[s][i]["_mkt"] = mkt_ret(s, P[s][i - 1]["date"], P[s][i]["date"])
    P[s][0]["_mkt"] = None

betas = {}
for s in syms:
    x, y = [], []
    for i in range(MATURE, len(P[s])):
        if P[s][i]["_ret"] is not None and P[s][i].get("_mkt") is not None:
            x.append(P[s][i]["_mkt"]); y.append(P[s][i]["_ret"])
    if len(x) >= 15:
        x, y = np.array(x), np.array(y)
        vx = float(np.var(x)) * len(x)
        if vx > 0:
            b = float(np.sum((x - x.mean()) * (y - y.mean())) / vx)
            betas[s] = min(max(b, 0.0), 3.0)
bfall = float(np.median(list(betas.values())))
R["b_beta"] = {"n_estimated": len(betas), "fallback_median": round(bfall, 3),
               "claim": "26 estimated, fallback 0.751"}

def resid(s, i, bmap=None, fb=None):
    b = (bmap or betas).get(s, fb if fb is not None else bfall)
    m = P[s][i].get("_mkt")
    if m is None or P[s][i]["_ret"] is None:
        return None
    return P[s][i]["_ret"] - b * m

# ---------- clustered t (own impl, CR0) ----------
def tclust(vals, cl):
    x = np.asarray(vals, float)
    n = len(x)
    if n < 5 or len(set(cl)) < 5:
        return 0.0
    xb = x.mean()
    g = defaultdict(float)
    for v, c in zip(x, cl):
        g[c] += v - xb
    var = sum(v * v for v in g.values()) / n**2
    return float(xb / math.sqrt(var)) if var > 0 else 0.0

def tclust_corr(vals, cl):
    """with G/(G-1) small-sample correction"""
    t = tclust(vals, cl)
    G = len(set(cl))
    return t / math.sqrt(G / (G - 1)) if G > 1 else t

# ---------- funding ----------
fund = defaultdict(list)
for s, ft, fr in db.execute("SELECT symbol, funding_time, funding_rate FROM funding "
                            "WHERE funding_time<=?", (CUTOFF_MS,)):
    fund[s].append((ft, fr))
for s in fund:
    fund[s].sort()
first_ot = dict(db.execute("SELECT symbol, MIN(ot) FROM klines_1m GROUP BY symbol"))

def fsum(s, t0, t1):
    return sum(fr for ft, fr in fund.get(s, ()) if t0 < ft <= t1) * 100.0

# ---------- (b) headline cells recompute: dev ----------
def day1_items(sylist, mode):  # mode raw|resid
    out = []
    for s in sylist:
        if len(P[s]) < 2:
            continue
        v = P[s][1]["_ret"] if mode == "raw" else resid(s, 1)
        if v is not None:
            out.append((lday[s], s, v))
    return out

def cellstats(items):
    vals = [v for _, _, v in items]
    cl = [b for b, _, _ in items]
    bm = defaultdict(list)
    for b, _, v in items:
        bm[b].append(v)
    bmeans = {b: float(np.mean(v)) for b, v in bm.items()}
    lobo = min(float(np.mean([v for b, _, v in items if b != d])) for d in bmeans) if len(bmeans) > 1 else None
    agg = defaultdict(float)
    for b, _, v in items:
        agg[b] += v
    tot = sum(abs(v) for v in agg.values())
    return {
        "n": len(items), "n_batches": len(bmeans),
        "gross_mean": round(float(np.mean(vals)), 4),
        "t_clust_CR0": round(tclust(vals, cl), 3),
        "t_clust_G_corr": round(tclust_corr(vals, cl), 3),
        "batches_negative": sum(1 for v in bmeans.values() if v < 0),
        "lobo_min_mean": round(lobo, 4) if lobo is not None else None,
        "max_batch_share": round(max(abs(v) for v in agg.values()) / tot, 3) if tot else None,
    }

d1_raw_dev = cellstats(day1_items(dev, "raw"))
d1_res_dev = cellstats(day1_items(dev, "resid"))
d1_raw_val = cellstats(day1_items(val, "raw"))
d1_res_val = cellstats(day1_items(val, "resid"))
# val per-batch means (check diag_val_d1_by_batch)
vb = defaultdict(list)
for b, s, v in day1_items(val, "raw"):
    vb[b].append(v)
val_by_batch = {b: round(float(np.mean(v)), 2) for b, v in sorted(vb.items())}

# beta robustness variants for resid d1 (dev)
def d1_resid_variant(bmap, fb):
    out = []
    for s in dev:
        if len(P[s]) < 2:
            continue
        v = resid(s, 1, bmap=bmap, fb=fb)
        if v is not None:
            out.append((lday[s], s, v))
    vals = [v for _, _, v in out]
    return {"n": len(out), "mean": round(float(np.mean(vals)), 4),
            "t": round(tclust(vals, [b for b, _, _ in out]), 3)}

variants = {
    "spec_replica": {"n": d1_res_dev["n"], "mean": d1_res_dev["gross_mean"], "t": d1_res_dev["t_clust_CR0"]},
    "all_beta_1": d1_resid_variant({}, 1.0),
    "all_beta_fallback": d1_resid_variant({}, bfall),
    "all_beta_0.5": d1_resid_variant({}, 0.5),
}

R["b_cells"] = {
    "dev_day1_raw": d1_raw_dev, "dev_day1_resid": d1_res_dev,
    "val_day1_raw": d1_raw_val, "val_day1_resid": d1_res_val,
    "val_d1_raw_by_batch": val_by_batch,
    "claims": {"dev_raw": "-1.7337 t=-3.348 14/17 neg", "dev_resid": "-1.2122 t=-2.983",
               "val_raw": "-0.5052 t=-0.609 4/6 neg", "val_resid": "-0.6983 t=-1.30"},
    "beta_variants_dev_resid_d1": variants,
}

# ---------- (d) net / cost recompute for headline (incl funding leg) ----------
def net_d1_short(sylist, cost_rt, mode="raw"):
    nets = []
    for s in sylist:
        if len(P[s]) < 2:
            continue
        g = P[s][1]["_ret"] if mode == "raw" else resid(s, 1)
        if g is None:
            continue
        fp = fsum(s, P[s][0]["rth_close_ts"], P[s][1]["rth_close_ts"])  # short collects +
        nets.append(-g - cost_rt + fp)
    return round(float(np.mean(nets)), 4), len(nets)

R["d_net"] = {
    "dev_raw_short_net_0.18": net_d1_short(dev, 0.18, "raw"),
    "dev_raw_short_net_stress_0.27": net_d1_short(dev, 0.27, "raw"),
    "dev_resid_short_net_0.30": net_d1_short(dev, 0.30, "resid"),
    "val_raw_short_net_stress_0.27": net_d1_short(val, 0.27, "raw"),
    "val_resid_short_net_0.30": net_d1_short(val, 0.30, "resid"),
    "claims": {"dev_raw_net": 1.6037, "dev_raw_stress": 1.5137, "dev_resid_net": 0.9649,
               "val_raw_stress": 0.2762, "val_resid_net": 0.4392},
}

# ---------- (d) liquidity: qv day0-3 + funding day path ----------
qv03 = []
for s in dev:
    q = [r.get("qv_day") for r in P[s][:4] if r.get("qv_day")]
    if q:
        qv03.append(float(np.median(q)))
d0_rates, mat_rates = [], []
n_dev_fund = 0
for s in dev:
    if s not in fund:
        continue
    n_dev_fund += 1
    t1 = P[s][0]["rth_close_ts"]
    d0_rates += [fr for ft, fr in fund[s] if first_ot[s] - 1 < ft <= t1]
    if len(P[s]) > MATURE:
        mat_rates += [fr for ft, fr in fund[s]
                      if P[s][MATURE - 1]["rth_close_ts"] < ft <= P[s][-1]["rth_close_ts"]]
R["d_liquidity_funding"] = {
    "qv_day0_3_median_usd": round(float(np.median(qv03)), 0),
    "qv_day0_3_p25_usd": round(float(np.percentile(qv03, 25)), 0),
    "n_dev_syms_with_funding": n_dev_fund,
    "funding_day0_mean_pct": round(float(np.mean(d0_rates)) * 100, 5) if d0_rates else None,
    "funding_mature_mean_pct": round(float(np.mean(mat_rates)) * 100, 5) if mat_rates else None,
    "funding_coverage": f"{len(fund)}/{n_db_syms}",
    "claims": {"qv_median": 4894711, "day0": 0.03523, "mature": 0.00672, "coverage": "58/105"},
}

# ---------- (c) permutation: independent rewrite, new seed ----------
PATH_KS = [1, 2, 3, 5, 10]
HORIZONS = [1, 2, 3, 5, 10]

def grid_max_t(anchors):
    """anchors: sym->idx; returns max |t_clust| over the same 25 ret-cell grid (n>=10)."""
    cells = defaultdict(list)
    for s, a in anchors.items():
        b = lday[s]
        n = len(P[s])
        for k in PATH_KS:
            i = a + k
            if i < n:
                v = resid(s, i)
                if v is not None:
                    cells[f"P{k}"].append((b, v))
        for e in (0, 1):
            for h in HORIZONS:
                lo, hi = a + e + 1, a + e + h
                if hi >= n:
                    continue
                rw = [P[s][i]["_ret"] for i in range(lo, hi + 1)]
                rs = [resid(s, i) for i in range(lo, hi + 1)]
                if all(v is not None for v in rw):
                    cells[f"Wr{e}{h}"].append((b, sum(rw)))
                if all(v is not None for v in rs):
                    cells[f"Ws{e}{h}"].append((b, sum(rs)))
    best, bestc = 0.0, None
    for c, items in cells.items():
        if len(items) >= 10:
            t = abs(tclust([v for _, v in items], [b for b, _ in items]))
            if t > best:
                best, bestc = t, c
    return best, bestc

# eligible placebo anchor dates per batch (replica of their constraint)
elig = {}
batch_syms = defaultdict(list)
for s in dev:
    batch_syms[lday[s]].append(s)
for b, bs in batch_syms.items():
    cand = None
    for s in bs:
        ok = {P[s][i]["date"] for i in range(MATURE, len(P[s]) - 10)
              if P[s][i + 10]["date"] <= "2026-05-31"}
        cand = ok if cand is None else cand & ok
    if cand:
        elig[b] = sorted(cand)

obs_best, obs_cell = grid_max_t({s: 0 for s in dev})
# apples-to-apples: observed max-|t| restricted to the perm-eligible batches only
perm_ev = [s for s in dev if lday[s] in elig]
obs_sub, obs_sub_cell = grid_max_t({s: 0 for s in perm_ev})

N_PERM = 1000
null_max = []
for _ in range(N_PERM):
    anchors = {}
    for b, dates in elig.items():
        d0 = random.choice(dates)
        for s in batch_syms[b]:
            anchors[s] = P[s][0]["_i"] if False else next(i for i, r in enumerate(P[s]) if r["date"] == d0)
    null_max.append(grid_max_t(anchors)[0])
null_max = np.array(null_max)
p_full = float(np.mean(null_max >= obs_best))
p_sub = float(np.mean(null_max >= obs_sub))

# per-cell (non-search) permutation p for the single frozen rule day1-short:
# null day1 raw t at placebo anchors vs observed -3.348
null_d1 = []
for _ in range(N_PERM):
    items = []
    for b, dates in elig.items():
        d0 = random.choice(dates)
        for s in batch_syms[b]:
            i = next(i for i, r in enumerate(P[s]) if r["date"] == d0)
            if i + 1 < len(P[s]) and P[s][i + 1]["_ret"] is not None:
                items.append((b, P[s][i + 1]["_ret"]))
    if len(items) >= 10:
        null_d1.append(abs(tclust([v for _, v in items], [b for b, _ in items])))
null_d1 = np.array(null_d1)
p_cell = float(np.mean(null_d1 >= abs(d1_raw_dev["t_clust_CR0"])))

R["c_permutation"] = {
    "n_perm": N_PERM, "seed": 918273645,
    "obs_best_cell": obs_cell, "obs_best_abs_t": round(obs_best, 3),
    "p_best_vs_null_max_t": round(p_full, 3),
    "null_p50": round(float(np.percentile(null_max, 50)), 3),
    "null_p90": round(float(np.percentile(null_max, 90)), 3),
    "n_perm_batches": len(elig), "n_perm_events": len(perm_ev),
    "apples_to_apples_obs_subset_max_t": round(obs_sub, 3),
    "apples_to_apples_subset_cell": obs_sub_cell,
    "p_subset_vs_null": round(p_sub, 3),
    "per_cell_day1_raw_null_p": round(p_cell, 3),
    "per_cell_day1_null_p90_abs_t": round(float(np.percentile(null_d1, 90)), 3),
    "claims": {"p": 0.246, "null_p50": 2.789, "null_p90": 4.002},
}

with open(f"{ROOT}/alpha_screen/H_verify/verify_H_results.json", "w") as f:
    json.dump(R, f, indent=1)

for k, v in R.items():
    print(f"== {k} ==")
    print(json.dumps(v, indent=1)[:2000])
