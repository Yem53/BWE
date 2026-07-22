#!/usr/bin/env python3
"""
Round27 Family A — 时段回归 (overnight drift -> open-window reversion)
=====================================================================
PRE-REGISTERED DESIGN (frozen before touching val):

Tests
  T1 TS-conditional fade: overnight_ret buckets {>+1,>+2,>+3,<-1,<-2,<-3}%
     -> fade (opposite side) hold to o30/o60/o120/o_close.
  T2 CS tercile LS fade (primary): daily rank by overnight_ret,
     long bottom tercile + short top tercile, per window. n>=6 names/day.
  T3 Control: follow = mirror of fade gross (reported, not a candidate).
  T4 Subsets: all / gap1 (gap_days==1) / weekend (is_weekend_gap==1).
  T5 Liquidity split (within-date median qv_day): TS at +/-2% x 4 windows x 2
     layers, CS x 4 windows x 2 layers (all-gap subset only).

Cells counted for global FDR:
  TS fade 6 thr x 4 win x 3 subsets            = 72
  CS fade 4 win x 3 subsets                    = 12
  TS liq  2 thr x 4 win x 2 layers             = 16
  CS liq  4 win x 2 layers                     =  8
  TOTAL                                        = 108

Costs (all in %, returns are in %):
  taker 0.08 round-trip + spread 0.02/side (0.05/side if qv_day < $5M)
  => 0.12 or 0.18 per position round-trip. CS LS pays BOTH legs.
  Funding: real settlements crossed in (open_ts, end_ts], from funding table
  (filtered to <= 1781654399000). long pnl -= sum(rate)*100 ; short += .
  Sensitivity: 1.5x trading cost (funding unchanged).

Beta-strip: subtract same-date same-window equal-weight universe mean return
  (computed from px anchors over ALL panel rows incl. day-1 listings).
  TS: strip_net = side*(r - mkt) - cost + fund_pnl. CS LS: strips cancel.

Candidate rule on dev (frozen): net_mean>0 AND t_net>=2.0 AND n>=100
  (TS rows; CS days — CS cells with n_days<100 are flagged exploratory and
  can only be promoted as "exploratory candidate")
  AND max single-date PnL share <=40% AND max single-symbol share <=40%
  AND beta-stripped net_mean>0 AND net at 1.5x cost >0.
Val (used ONCE, after dev selection): frozen candidates re-scored; survivor
  requires val net_mean same sign (>0).

Hard rule: no data beyond 2026-06-15 (panel is pre-cut; funding filtered).
"""
import json, sqlite3, math
import numpy as np
from collections import defaultdict

ROOT = "/Volumes/T9/BWE/40_EXPERIMENTS/round27_usstock_alpha"
CUTOFF_MS = 1781654399000
WINDOWS = ["o30", "o60", "o120", "o_close"]
THR = [("gt+1", 1.0), ("gt+2", 2.0), ("gt+3", 3.0), ("lt-1", -1.0), ("lt-2", -2.0), ("lt-3", -3.0)]

# ---------- load panel ----------
rows = [json.loads(l) for l in open(f"{ROOT}/panel_devval.jsonl")]
for r in rows:
    r["end_ts"] = {
        "o30": r["rth_open_ts"] + 30 * 60000,
        "o60": r["rth_open_ts"] + 60 * 60000,
        "o120": r["rth_open_ts"] + 120 * 60000,
        "o_close": r["rth_close_ts"],
    }
    # returns from px anchors (available for ALL rows incl. day-1 listings)
    r["r"] = {
        "o30": (r["px_o30"] / r["rth_open"] - 1) * 100,
        "o60": (r["px_o60"] / r["rth_open"] - 1) * 100,
        "o120": (r["px_o120"] / r["rth_open"] - 1) * 100,
        "o_close": (r["rth_close"] / r["rth_open"] - 1) * 100,
    }
    spread_side = 0.05 if r["qv_day"] < 5e6 else 0.02
    r["cost"] = 0.08 + 2 * spread_side  # % round-trip

# market mean per date x window (equal-weight, all rows)
mkt = {}
byd = defaultdict(list)
for r in rows:
    byd[r["date"]].append(r)
for d, rs in byd.items():
    mkt[d] = {w: float(np.mean([x["r"][w] for x in rs])) for w in WINDOWS}

# ---------- funding: settlements crossed per row x window ----------
db = sqlite3.connect(f"{ROOT}/tradfi_full.sqlite3")
fund = defaultdict(list)  # symbol -> [(ts, rate)]
for s, ft, fr in db.execute(
    "SELECT symbol, funding_time, funding_rate FROM funding WHERE funding_time <= ?", (CUTOFF_MS,)
):
    fund[s].append((ft, fr))
for s in fund:
    fund[s].sort()

def fund_cost_long(sym, t0, t1):
    """sum of funding rates (%) settled in (t0, t1] — cost to a long."""
    tot = 0.0
    for ft, fr in fund.get(sym, ()):
        if t0 < ft <= t1:
            tot += fr * 100.0
    return tot

for r in rows:
    r["fund_w"] = {w: fund_cost_long(r["symbol"], r["rth_open_ts"], r["end_ts"][w]) for w in WINDOWS}

univ = [r for r in rows if "overnight_ret" in r]
dev = [r for r in univ if r["date"] <= "2026-05-31"]
val = [r for r in univ if r["date"] > "2026-05-31"]

def sample_desc(rs, name):
    months = defaultdict(int)
    for r in rs:
        months[r["date"][:7]] += 1
    return {
        "name": name, "rows": len(rs),
        "symbols": len(set(r["symbol"] for r in rs)),
        "dates": len(set(r["date"] for r in rs)),
        "by_month": dict(sorted(months.items())),
    }

# ---------- stats helpers ----------
def tstat(x):
    x = np.asarray(x, float)
    if len(x) < 3 or x.std(ddof=1) == 0:
        return 0.0
    return float(x.mean() / (x.std(ddof=1) / math.sqrt(len(x))))

def lodo_shares(keys, pnl):
    """max |group-sum| / |total| by key; only meaningful if total != 0"""
    tot = float(np.sum(pnl))
    if tot == 0:
        return 1.0
    g = defaultdict(float)
    for k, p in zip(keys, pnl):
        g[k] += p
    return float(max(abs(v) for v in g.values()) / abs(tot))

# ---------- T1: time-series conditional fade ----------
def ts_cell(rs, thr_val, w, cost_mult=1.0):
    if thr_val > 0:
        sel = [r for r in rs if r["overnight_ret"] > thr_val]
        side = -1.0  # fade a positive overnight move = short
    else:
        sel = [r for r in rs if r["overnight_ret"] < thr_val]
        side = +1.0
    n = len(sel)
    if n == 0:
        return None
    r_ = np.array([x["r"][w] for x in sel])
    mk = np.array([mkt[x["date"]][w] for x in sel])
    c = np.array([x["cost"] for x in sel]) * cost_mult
    f = np.array([x["fund_w"][w] for x in sel])
    gross = side * r_
    fpnl = -side * f
    net = gross - c + fpnl
    strip_net = side * (r_ - mk) - c + fpnl
    net15 = gross - np.array([x["cost"] for x in sel]) * 1.5 + fpnl
    return {
        "n": n, "side": "short" if side < 0 else "long",
        "gross_mean": round(float(gross.mean()), 4),
        "net_mean": round(float(net.mean()), 4),
        "net_t": round(tstat(net), 2),
        "net_median": round(float(np.median(net)), 4),
        "hit": round(float((net > 0).mean()), 3),
        "strip_net_mean": round(float(strip_net.mean()), 4),
        "strip_net_t": round(tstat(strip_net), 2),
        "net_1p5x": round(float(net15.mean()), 4),
        "follow_gross_mean": round(float(-gross.mean()), 4),
        "follow_net_mean": round(float((-gross - np.array([x['cost'] for x in sel]) + side * f).mean()), 4),
        "lodo_date": round(lodo_shares([x["date"] for x in sel], net), 3),
        "lodo_sym": round(lodo_shares([x["symbol"] for x in sel], net), 3),
        "exploratory": bool(n < 100),
    }

# ---------- T2: cross-sectional tercile LS fade ----------
def cs_series(rs, w):
    byd_ = defaultdict(list)
    for r in rs:
        byd_[r["date"]].append(r)
    days, ls_g, ls_n, ls_n15, contrib_sym = [], [], [], [], defaultdict(float)
    for d in sorted(byd_):
        g = byd_[d]
        if len(g) < 6:
            continue
        g = sorted(g, key=lambda x: x["overnight_ret"])
        k = len(g) // 3
        bot, top = g[:k], g[-k:]  # long bottom (most-down overnight), short top
        rb = np.array([x["r"][w] for x in bot]); rt = np.array([x["r"][w] for x in top])
        cb = np.array([x["cost"] for x in bot]); ct = np.array([x["cost"] for x in top])
        fb = np.array([x["fund_w"][w] for x in bot]); ft = np.array([x["fund_w"][w] for x in top])
        gross = rb.mean() - rt.mean()
        fpnl = -fb.mean() + ft.mean()  # long pays bottom-leg funding, short receives top-leg
        cost = cb.mean() + ct.mean()
        ls_g.append(gross); ls_n.append(gross - cost + fpnl); ls_n15.append(gross - 1.5 * cost + fpnl)
        days.append(d)
        for x in bot:
            contrib_sym[x["symbol"]] += (x["r"][w] - x["cost"] - x["fund_w"][w]) / k
        for x in top:
            contrib_sym[x["symbol"]] += (-x["r"][w] - x["cost"] + x["fund_w"][w]) / k
    if not days:
        return None
    ls_n = np.array(ls_n)
    tot = float(ls_n.sum())
    lodo_s = 1.0 if tot == 0 else float(max(abs(v) for v in contrib_sym.values()) / abs(tot))
    return {
        "n_days": len(days),
        "gross_mean": round(float(np.mean(ls_g)), 4),
        "net_mean": round(float(ls_n.mean()), 4),
        "net_t": round(tstat(ls_n), 2),
        "hit": round(float((ls_n > 0).mean()), 3),
        "net_1p5x": round(float(np.mean(ls_n15)), 4),
        "follow_gross_mean": round(float(-np.mean(ls_g)), 4),
        "lodo_date": round(lodo_shares(days, ls_n), 3),
        "lodo_sym": round(lodo_s, 3),
        "exploratory": bool(len(days) < 100),
        "note": "LS is beta-neutral by construction (equal-weight strips cancel)",
    }

# ---------- run all cells on a sample ----------
def subsets(rs):
    return {
        "all": rs,
        "gap1": [r for r in rs if r["gap_days"] == 1],
        "weekend": [r for r in rs if r["is_weekend_gap"] == 1],
    }

def liq_layers(rs):
    """within-date median split on qv_day"""
    byd_ = defaultdict(list)
    for r in rs:
        byd_[r["date"]].append(r)
    hi, lo = [], []
    for d, g in byd_.items():
        med = float(np.median([x["qv_day"] for x in g]))
        for x in g:
            (hi if x["qv_day"] >= med else lo).append(x)
    return {"liq_hi": hi, "liq_lo": lo}

def run_all(rs):
    out = {"TS_fade": {}, "CS_tercile_fade": {}, "TS_liq": {}, "CS_liq": {}}
    subs = subsets(rs)
    for sname, srows in subs.items():
        for tname, tval in THR:
            for w in WINDOWS:
                out["TS_fade"][f"{sname}|{tname}|{w}"] = ts_cell(srows, tval, w)
        for w in WINDOWS:
            out["CS_tercile_fade"][f"{sname}|{w}"] = cs_series(srows, w)
    for lname, lrows in liq_layers(subs["all"]).items():
        for tname, tval in [("gt+2", 2.0), ("lt-2", -2.0)]:
            for w in WINDOWS:
                out["TS_liq"][f"{lname}|{tname}|{w}"] = ts_cell(lrows, tval, w)
        for w in WINDOWS:
            out["CS_liq"][f"{lname}|{w}"] = cs_series(lrows, w)
    return out

dev_res = run_all(dev)

# ---------- dev candidate selection (frozen rule) ----------
def passes(c, is_cs):
    if c is None:
        return False
    ok = c["net_mean"] > 0 and c["net_t"] >= 2.0 and c["net_1p5x"] > 0
    ok = ok and c["lodo_date"] <= 0.40 and c["lodo_sym"] <= 0.40
    if not is_cs:
        ok = ok and c["strip_net_mean"] > 0
        ok = ok and not c["exploratory"]  # TS needs n>=100
    return ok

candidates = []
for fam, is_cs in [("TS_fade", False), ("CS_tercile_fade", True), ("TS_liq", False), ("CS_liq", True)]:
    for key, c in dev_res[fam].items():
        if passes(c, is_cs):
            candidates.append({"family": fam, "cell": key, "dev": c})

# ---------- val (ONE evaluation of frozen candidates) + full val grid for transparency ----------
val_res = run_all(val)
for cand in candidates:
    cand["val"] = val_res[cand["family"]].get(cand["cell"])

n_cells = sum(len(dev_res[f]) for f in dev_res)
result = {
    "family": "A_session_reversion",
    "n_cells_tested": n_cells,
    "cost_model": "taker 0.08% RT + spread 2bp/side (5bp/side if qv_day<$5M) + real funding on crossed settlements",
    "sample": {"dev": sample_desc(dev, "dev"), "val": sample_desc(val, "val")},
    "dev_candidate_rule": "net>0 & t>=2 & 1.5x-cost>0 & LODO(date,sym)<=40% & beta-strip>0 (TS) & n>=100 (TS)",
    "candidates_frozen_from_dev": candidates,
    "dev_results": dev_res,
    "val_results_full_grid_for_transparency": val_res,
}
with open(f"{ROOT}/alpha_screen/A/results_A.json", "w") as f:
    json.dump(result, f, indent=1, ensure_ascii=False)

print("cells:", n_cells)
print("dev sample:", result["sample"]["dev"])
print("val sample:", result["sample"]["val"])
print("\n=== dev candidates (frozen) ===")
for c in candidates:
    print(c["family"], c["cell"], "dev_net=%.3f t=%.2f" % (c["dev"]["net_mean"], c["dev"]["net_t"]),
          "-> val:", None if c["val"] is None else "net=%.3f t=%.2f n=%s" % (
              c["val"]["net_mean"], c["val"]["net_t"], c["val"].get("n", c["val"].get("n_days"))))
