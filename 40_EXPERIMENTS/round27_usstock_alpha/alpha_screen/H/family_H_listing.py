#!/usr/bin/env python3
"""
Round27 Family H — 永续新上市效应 (new-listing effect on US-stock perps)
========================================================================
PRE-REGISTERED DESIGN (frozen before running).

Question: crypto-world "listing pump/dump" — does it exist on Binance
US-stock perps? 87 listings inside the allowed window (<=2026-06-15),
50 dev events across 17 batch dates, 37 val events across 6 batch dates.
18 post-holdout listings (>06-15) are NEVER touched.

Events & split
  event = symbol's first panel day (panel_devval.jsonl, RTH ET anchors,
  built with zoneinfo => DST-safe incl 2026-03-08). day0 = listing day.
  dev = listing date <= 2026-05-31 (50 ev / 17 batches)
  val = 2026-06-01..15 (37 ev / 6 batches), touched ONLY for dev-gate
  survivors. Dev windows may exit into early June (same convention as
  family D); holdout wall 06-15 enforced by the pre-cut panel.

Returns
  Trading-day RTH close-to-close, arithmetic sum of daily % over windows
  (no compounding; consistent between real and permutation paths).
  raw   : own return
  resid : r - beta_hat * mkt   (FAIR beta strip, not beta=1)
    mkt  = leave-self-out equal-weight mean daily return over MATURE
           symbols (own day-index >= 11) sharing the date pair; needs
           >=3 mature others else None (early-Feb events drop out of
           resid cells — no mature universe existed yet).
    beta_hat = per-symbol OLS on its own mature days (>=15 obs, clipped
           to [0,3]); fallback = cross-sectional median beta_hat.
           NOTE: only post-event data exists for a new listing, so the
           "non-event window" is days 11+ (documented limitation).

Cells (ALL dev cells counted; n_cells = 27)
  PATH  |resid|d{k}          k in {1,2,3,5,10}   single-day residual  = 5
  WIN   |raw  |e{0,1}|h{1,2,3,5,10}  window sum from day-e close     = 10
  WIN   |resid|e{0,1}|h{1,2,3,5,10}                                  = 10
  FUND  |abs / signed        day0-2 funding vs own mature ref        =  2

Stats discipline (round27 wave-2, post-276-cell-graveyard)
  - clustered t (CR0) by listing-batch date; gate = |t_clust| >= 2
  - permutation: 1000 draws of placebo batch anchors (mature idx>=11,
    full 10d window, exit <= 05-31 so the null never touches val);
    same-batch symbols share the placebo date (cluster structure kept);
    report where the best real cell's |t| sits in the null max-|t|
    (search-size-honest) distribution across the whole grid.
  - LOBO (leave-one-batch-out), max batch/symbol |pnl| share <= 40%
  - BH-FDR q=0.10 over all dev cells (normal-approx p from t_clust)

Costs (new listings = thin tier by construction; D-verify found only
  tens of kUSD near the book in the first days)
  raw cells   : taker 0.08% RT + 5bp/side slippage = 0.18% RT; 1.5x=0.27
  resid cells : + QQQ hedge leg 0.08% RT fees + 2bp/side = 0.30% RT; 1.5x=0.45
  + real crossed funding on the event leg (long pays positive rate);
  funding table covers only 58/105 symbols — missing => 0 + caveat.

Descriptives (not cells): day0 intraday move, cumulative resid path
  d1..d10, funding path by day-index (Q2), full-day amplitude and
  qv_day evolution vs own mature median (Q3), day0-3 qv_day medians
  (capacity realism).

Hard rule: nothing beyond ot=1781654399000 (2026-06-15T23:59Z).
"""
import json
import math
import random
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np

ROOT = "/Volumes/T9/BWE/40_EXPERIMENTS/round27_usstock_alpha"
CUTOFF_MS = 1781654399000
ET = ZoneInfo("America/New_York")
MATURE_IDX = 11
PATH_KS = [1, 2, 3, 5, 10]
HORIZONS = [1, 2, 3, 5, 10]
COST = {"raw": 0.18, "resid": 0.30}
COST_S = {"raw": 0.27, "resid": 0.45}
N_PERM = 1000
random.seed(20260706)

# ---------------- panel ----------------
panel = [json.loads(l) for l in open(f"{ROOT}/panel_devval.jsonl")]
S = {}  # sym -> dict of arrays
for r in panel:
    S.setdefault(r["symbol"], []).append(r)
for sym in S:
    rows = sorted(S[sym], key=lambda r: r["date"])
    S[sym] = {
        "dates": [r["date"] for r in rows],
        "close": [r["rth_close"] for r in rows],
        "close_ts": [r["rth_close_ts"] for r in rows],
        "open": [r["rth_open"] for r in rows],
        "open_ts": [r["rth_open_ts"] for r in rows],
        "qv": [r.get("qv_day") for r in rows],
        "idx": {r["date"]: i for i, r in enumerate(rows)},
    }
syms = sorted(S)
listing_date = {sym: S[sym]["dates"][0] for sym in syms}
batch_of = dict(listing_date)  # batch key = ET listing date
dev_syms = [s for s in syms if listing_date[s] <= "2026-05-31"]
val_syms = [s for s in syms if "2026-06-01" <= listing_date[s] <= "2026-06-15"]
dev_batches = sorted(set(batch_of[s] for s in dev_syms))
gdates = sorted(set(d for sym in syms for d in S[sym]["dates"]))

# ---------------- klines first-ot (day0 funding window start) ----------------
db = sqlite3.connect(f"{ROOT}/tradfi_full.sqlite3")
first_ot = dict(db.execute("SELECT symbol, MIN(ot) FROM klines_1m GROUP BY symbol"))

# ---------------- daily returns + fair beta strip ----------------
# per symbol daily return r[i] (%) over its own consecutive panel days
for sym in syms:
    c = S[sym]["close"]
    S[sym]["r"] = [None] + [(c[i] / c[i - 1] - 1) * 100 for i in range(1, len(c))]

# group by date-pair; mature = own idx>=MATURE_IDX at the pair's end day
pair = defaultdict(list)  # (d0,d1) -> list of (sym, r, mature)
for sym in syms:
    d = S[sym]["dates"]
    for i in range(1, len(d)):
        pair[(d[i - 1], d[i])].append((sym, S[sym]["r"][i], i >= MATURE_IDX))
pair_sum = {}
for k, lst in pair.items():
    m = [(s, r) for s, r, mat in lst if mat]
    pair_sum[k] = (sum(r for _, r in m), len(m), {s: r for s, r in m})

def mkt(sym: str, d0: str, d1: str):
    """leave-self-out equal-weight mature-universe return for the pair."""
    tot, cnt, members = pair_sum.get((d0, d1), (0.0, 0, {}))
    if sym in members:
        tot, cnt = tot - members[sym], cnt - 1
    return tot / cnt if cnt >= 3 else None

# per-symbol mkt series aligned to its own days
for sym in syms:
    d = S[sym]["dates"]
    S[sym]["mkt"] = [None] + [mkt(sym, d[i - 1], d[i]) for i in range(1, len(d))]

# fair beta_hat from own mature days
betas = {}
for sym in syms:
    xs, ys = [], []
    for i in range(MATURE_IDX, len(S[sym]["dates"])):
        if S[sym]["r"][i] is not None and S[sym]["mkt"][i] is not None:
            xs.append(S[sym]["mkt"][i]); ys.append(S[sym]["r"][i])
    if len(xs) >= 15:
        x, y = np.array(xs), np.array(ys)
        vx = float(((x - x.mean()) ** 2).sum())
        if vx > 0:
            betas[sym] = float(np.clip(((x - x.mean()) * (y - y.mean())).sum() / vx, 0.0, 3.0))
beta_fallback = float(np.median(list(betas.values()))) if betas else 1.0
n_beta_est = len(betas)
for sym in syms:
    b = betas.get(sym, beta_fallback)
    S[sym]["beta"] = b
    S[sym]["resid"] = [None] + [
        (S[sym]["r"][i] - b * S[sym]["mkt"][i]) if S[sym]["mkt"][i] is not None else None
        for i in range(1, len(S[sym]["dates"]))
    ]

# ---------------- funding ----------------
fund = defaultdict(list)
for s, ft, fr in db.execute(
        "SELECT symbol, funding_time, funding_rate FROM funding WHERE funding_time <= ?",
        (CUTOFF_MS,)):
    fund[s].append((ft, fr))
for s in fund:
    fund[s].sort()

def fund_rates(sym: str, t0: int, t1: int):
    return [fr for ft, fr in fund.get(sym, ()) if t0 < ft <= t1]

def fund_long_pct(sym: str, t0: int, t1: int) -> float:
    return sum(fund_rates(sym, t0, t1)) * 100.0

# ---------------- stats helpers ----------------
def t_cluster(vals, clusters):
    """CR0 cluster-robust t of the mean; clusters = parallel labels."""
    x = np.asarray(vals, float)
    n = len(x)
    if n < 5:
        return 0.0
    xbar = x.mean()
    g = defaultdict(float)
    for v, c in zip(x, clusters):
        g[c] += v - xbar
    if len(g) < 5:
        return 0.0
    var = sum(s * s for s in g.values()) / (n * n)
    return float(xbar / math.sqrt(var)) if var > 0 else 0.0

def p_norm(t):
    return 2 * (1 - 0.5 * (1 + math.erf(abs(t) / math.sqrt(2))))

# ---------------- gross cell engine (shared real/permutation) ----------------
RET_CELLS = [f"PATH|resid|d{k}" for k in PATH_KS] + [
    f"WIN|{m}|e{e}|h{h}" for m in ("raw", "resid") for e in (0, 1) for h in HORIZONS]

def gross_grid(anchors):
    """anchors: sym -> anchor idx. -> cell -> list of (batch, sym, gross%)"""
    out = {c: [] for c in RET_CELLS}
    for sym, a in anchors.items():
        b = batch_of[sym]
        r, resid, nd = S[sym]["r"], S[sym]["resid"], len(S[sym]["dates"])
        for k in PATH_KS:
            i = a + k
            if i < nd and resid[i] is not None:
                out[f"PATH|resid|d{k}"].append((b, sym, resid[i]))
        for e in (0, 1):
            for h in HORIZONS:
                lo, hi = a + e + 1, a + e + h
                if hi >= nd:
                    continue
                rw = [r[i] for i in range(lo, hi + 1)]
                rs = [resid[i] for i in range(lo, hi + 1)]
                if all(v is not None for v in rw):
                    out[f"WIN|raw|e{e}|h{h}"].append((b, sym, sum(rw)))
                if all(v is not None for v in rs):
                    out[f"WIN|resid|e{e}|h{h}"].append((b, sym, sum(rs)))
    return out

def fund_cells(anchors, exclude_from_mature=True):
    """day0-2 funding vs own mature ref. -> {abs: [(b,sym,diff)], signed: [...]}"""
    out = {"abs": [], "signed": []}
    for sym, a in anchors.items():
        if sym not in fund:
            continue
        ts, nd = S[sym]["close_ts"], len(S[sym]["dates"])
        if a + 2 >= nd or nd <= MATURE_IDX + 1:
            continue
        t0 = (first_ot[sym] - 1) if a == 0 else ts[a - 1]
        t1 = ts[min(a + 2, nd - 1)]
        ev = fund_rates(sym, t0, t1)
        mat = [(ft, fr) for ft, fr in fund[sym] if ts[MATURE_IDX - 1] < ft <= ts[nd - 1]]
        if exclude_from_mature:
            mat = [(ft, fr) for ft, fr in mat if not (t0 < ft <= t1)]
        if len(ev) < 2 or len(mat) < 6:
            continue
        mfr = [fr for _, fr in mat]
        b = batch_of[sym]
        out["abs"].append((b, sym, (float(np.mean([abs(x) for x in ev]))
                                    - float(np.mean([abs(x) for x in mfr]))) * 100))
        out["signed"].append((b, sym, (float(np.mean(ev)) - float(np.mean(mfr))) * 100))
    return out

# ---------------- real dev run ----------------
dev_anchor = {s: 0 for s in dev_syms}
grid = gross_grid(dev_anchor)
fcells = fund_cells(dev_anchor)

def lobo_min(items):
    bs = set(b for b, _, _ in items)
    if len(bs) < 2:
        return None
    return min(float(np.mean([v for b, _, v in items if b != d])) for d in bs)

def max_share(items, pos):
    agg = defaultdict(float)
    for it in items:
        agg[it[pos]] += it[2]
    tot = sum(abs(v) for v in agg.values())
    if tot == 0:
        return 0.0, None
    k, v = max(agg.items(), key=lambda kv: abs(kv[1]))
    return abs(v) / tot, k

def net_stats(cell, items, side):
    """apply dev-sign direction + costs + real crossed funding."""
    parts = cell.split("|")
    metric = parts[1] if parts[0] in ("PATH", "WIN") else None
    nets, nets_s = [], []
    for b, sym, gross in items:
        if cell.startswith("PATH"):
            k = int(cell.split("d")[-1]); lo_i, hi_i = 0 + k - 1, 0 + k
        else:
            e, h = int(parts[2][1:]), int(parts[3][1:]); lo_i, hi_i = e, e + h
        ts = S[sym]["close_ts"]
        fp = -side * fund_long_pct(sym, ts[lo_i], ts[hi_i])
        nets.append(side * gross - COST[metric] + fp)
        nets_s.append(side * gross - COST_S[metric] + fp)
    return nets, nets_s

def cell_report(cell, items):
    if len(items) < 5:
        return {"n": len(items)}
    vals = [v for _, _, v in items]
    cl = [b for b, _, _ in items]
    m = float(np.mean(vals))
    side = 1.0 if m > 0 else -1.0
    if cell.startswith(("PATH", "WIN")):
        nets, nets_s = net_stats(cell, items, side)
    else:  # FUND cells: no direct pnl mapping
        nets = nets_s = None
    bsh, bwho = max_share(items, 0)
    ssh, swho = max_share(items, 1)
    rep = {
        "n": len(items), "n_batches": len(set(cl)),
        "gross_mean": round(m, 4),
        "t_clust": round(t_cluster(vals, cl), 3),
        "win": round(100 * float(np.mean([v > 0 for v in vals])), 1),
        "side_from_dev_sign": int(side),
        "lobo_min_mean": round(lobo_min(items), 4) if lobo_min(items) is not None else None,
        "max_batch_share": round(bsh, 3), "max_batch": bwho,
        "max_sym_share": round(ssh, 3), "max_sym": swho,
    }
    if nets is not None:
        rep["net_mean"] = round(float(np.mean(nets)), 4)
        rep["net_mean_stress"] = round(float(np.mean(nets_s)), 4)
    rep["p_raw"] = round(p_norm(rep["t_clust"]), 5)
    return rep

cells = {c: cell_report(c, grid[c]) for c in RET_CELLS}
cells["FUND|abs|d0_2"] = cell_report("FUND|abs|d0_2", fcells["abs"])
cells["FUND|signed|d0_2"] = cell_report("FUND|signed|d0_2", fcells["signed"])
N_CELLS = len(cells)

# BH-FDR q=0.10
pv = sorted([(k, c["p_raw"]) for k, c in cells.items() if "p_raw" in c], key=lambda kv: kv[1])
bh_sig = [(k, round(p, 5)) for i, (k, p) in enumerate(pv, 1) if p <= 0.10 * i / len(pv)]

# ---------------- permutation (null search distribution over the grid) ----------------
# eligible placebo anchors per dev batch: every batch symbol has idx>=11,
# idx+10 in range, and the day-(idx+10) exit date <= 2026-05-31 (val untouched)
elig = {}
for b in dev_batches:
    bsyms = [s for s in dev_syms if batch_of[s] == b]
    cand = None
    for sym in bsyms:
        ok = set()
        d = S[sym]["dates"]
        for i in range(MATURE_IDX, len(d) - 10):
            if d[i + 10] <= "2026-05-31":
                ok.add(d[i])
        cand = ok if cand is None else (cand & ok)
    if cand:
        elig[b] = sorted(cand)
perm_batches = sorted(elig)
perm_syms = [s for s in dev_syms if batch_of[s] in elig]

obs_best_cell, obs_best_t = max(((k, abs(c.get("t_clust", 0.0)))
                                 for k, c in cells.items() if c.get("n", 0) >= 10),
                                key=lambda kv: kv[1])
max_ts = []
for _ in range(N_PERM):
    anchors = {}
    for b in perm_batches:
        d0 = random.choice(elig[b])
        for sym in [s for s in dev_syms if batch_of[s] == b]:
            anchors[sym] = S[sym]["idx"][d0]
    g = gross_grid(anchors)
    fc = fund_cells(anchors)
    best = 0.0
    for c in RET_CELLS:
        items = g[c]
        if len(items) >= 10:
            best = max(best, abs(t_cluster([v for _, _, v in items], [b for b, _, _ in items])))
    for key in ("abs", "signed"):
        items = fc[key]
        if len(items) >= 10:
            best = max(best, abs(t_cluster([v for _, _, v in items], [b for b, _, _ in items])))
    max_ts.append(best)
perm_p = float(np.mean([m >= obs_best_t for m in max_ts]))

# ---------------- dev gate -> val (touched once, survivors only) ----------------
def passes(c):
    return (c.get("n", 0) >= 10
            and abs(c.get("t_clust", 0)) >= 2.0
            and (c.get("net_mean") or -1) > 0
            and (c.get("net_mean_stress") or -1) > 0
            and c.get("max_batch_share", 1) <= 0.40
            and c.get("max_sym_share", 1) <= 0.40
            and c.get("lobo_min_mean") is not None
            and math.copysign(1, c["lobo_min_mean"]) == math.copysign(1, c["gross_mean"]))
candidates = [k for k, c in cells.items() if k.startswith(("PATH", "WIN")) and passes(c)]

val_rescore = {}
if candidates:
    val_anchor = {s: 0 for s in val_syms}
    vgrid = gross_grid(val_anchor)
    for k in candidates:
        items = vgrid[k]
        rep = {"n": len(items)}
        if items:
            vals = [v for _, _, v in items]
            side = cells[k]["side_from_dev_sign"]
            nets, nets_s = net_stats(k, items, side)
            rep.update({
                "gross_mean": round(float(np.mean(vals)), 4),
                "t_clust": round(t_cluster(vals, [b for b, _, _ in items]), 3),
                "net_mean_devside": round(float(np.mean(nets)), 4),
                "net_mean_stress": round(float(np.mean(nets_s)), 4),
            })
        val_rescore[k] = rep

# ---------------- Q1 descriptive: residual path d1..d10 + day0 intraday ----------------
path_desc = {}
for k in range(1, 11):
    vals = [S[s]["resid"][k] for s in dev_syms
            if k < len(S[s]["dates"]) and S[s]["resid"][k] is not None]
    raws = [S[s]["r"][k] for s in dev_syms if k < len(S[s]["dates"])]
    path_desc[f"d{k}"] = {
        "n_resid": len(vals),
        "resid_mean": round(float(np.mean(vals)), 4) if vals else None,
        "resid_median": round(float(np.median(vals)), 4) if vals else None,
        "raw_mean": round(float(np.mean(raws)), 4) if raws else None,
    }
d0_intra = [(S[s]["close"][0] / S[s]["open"][0] - 1) * 100 for s in dev_syms]
day0_desc = {"n": len(d0_intra), "mean": round(float(np.mean(d0_intra)), 4),
             "median": round(float(np.median(d0_intra)), 4),
             "note": "day0 RTH open->close; open ~= listing minute for 09:30 batches"}

# ---------------- Q2 descriptive: funding path by day index ----------------
fund_path = {}
buckets = [(0, 0), (1, 1), (2, 2), (3, 3), (4, 5), (6, 10)]
for lo, hi in buckets:
    rates = []
    for sym in dev_syms:
        if sym not in fund:
            continue
        ts, nd = S[sym]["close_ts"], len(S[sym]["dates"])
        if lo >= nd:
            continue
        t0 = (first_ot[sym] - 1) if lo == 0 else ts[lo - 1]
        t1 = ts[min(hi, nd - 1)]
        rates += fund_rates(sym, t0, t1)
    if rates:
        a = np.array(rates) * 100
        fund_path[f"d{lo}_{hi}"] = {
            "n_settles": len(a), "mean_pct": round(float(a.mean()), 5),
            "median_pct": round(float(np.median(a)), 5),
            "mean_abs_pct": round(float(np.abs(a).mean()), 5),
            "p90_abs_pct": round(float(np.percentile(np.abs(a), 90)), 5),
        }
mat_rates = []
for sym in dev_syms:
    if sym not in fund or len(S[sym]["dates"]) <= MATURE_IDX:
        continue
    ts, nd = S[sym]["close_ts"], len(S[sym]["dates"])
    mat_rates += fund_rates(sym, ts[MATURE_IDX - 1], ts[nd - 1])
if mat_rates:
    a = np.array(mat_rates) * 100
    fund_path["mature_11plus"] = {
        "n_settles": len(a), "mean_pct": round(float(a.mean()), 5),
        "median_pct": round(float(np.median(a)), 5),
        "mean_abs_pct": round(float(np.abs(a).mean()), 5),
        "p90_abs_pct": round(float(np.percentile(np.abs(a), 90)), 5),
    }
n_dev_with_funding = sum(1 for s in dev_syms if s in fund)

# ---------------- Q3 descriptive: amplitude + turnover evolution ----------------
def et_day_bounds(dstr):
    y, m, d = map(int, dstr.split("-"))
    t0 = datetime(y, m, d, tzinfo=ET)
    return int(t0.timestamp() * 1000), int((t0 + timedelta(days=1)).timestamp() * 1000)

def day_amp(sym, dstr):
    t0, t1 = et_day_bounds(dstr)
    row = db.execute("SELECT MAX(h), MIN(l), MAX(cl) FROM klines_1m "
                     "WHERE symbol=? AND ot>=? AND ot<? AND ot<=?",
                     (sym, t0, t1 - 1, CUTOFF_MS)).fetchone()
    if row and row[0] and row[1] and row[2]:
        return (row[0] - row[1]) / row[2] * 100
    return None

amp_ratio, qv_ratio = defaultdict(list), defaultdict(list)
qv_day03 = []
for sym in dev_syms:
    d, qv, nd = S[sym]["dates"], S[sym]["qv"], len(S[sym]["dates"])
    mat_idx = list(range(MATURE_IDX, min(MATURE_IDX + 10, nd)))
    mat_amp = [a for i in mat_idx if (a := day_amp(sym, d[i])) is not None]
    mat_qv = [qv[i] for i in mat_idx if qv[i]]
    med_amp = float(np.median(mat_amp)) if len(mat_amp) >= 5 else None
    med_qv = float(np.median(mat_qv)) if len(mat_qv) >= 5 else None
    for k in range(0, 11):
        if k >= nd:
            break
        if med_amp:
            a = day_amp(sym, d[k])
            if a is not None:
                amp_ratio[k].append(a / med_amp)
        if med_qv and qv[k]:
            qv_ratio[k].append(qv[k] / med_qv)
    qv_day03.append(float(np.median([q for q in qv[:4] if q])) if any(qv[:4]) else None)

liq_desc = {
    "amp_ratio_median_by_day": {f"d{k}": round(float(np.median(v)), 3)
                                for k, v in sorted(amp_ratio.items()) if len(v) >= 5},
    "qv_ratio_median_by_day": {f"d{k}": round(float(np.median(v)), 3)
                               for k, v in sorted(qv_ratio.items()) if len(v) >= 5},
    "dev_event_qv_day0_3_median_usd": round(float(np.median([q for q in qv_day03 if q])), 0),
    "dev_event_qv_day0_3_p25_usd": round(float(np.percentile([q for q in qv_day03 if q], 25)), 0),
}

# ---------------- output ----------------
top = sorted([(k, c) for k, c in cells.items() if c.get("n", 0) >= 10],
             key=lambda kc: -abs(kc[1].get("t_clust", 0)))[:8]
out = {
    "family": "H_new_listing",
    "design": ("event=perp listing day0 (panel first day); trading-day RTH close series; "
               "resid = r - beta_hat*mkt (fair strip, beta_hat from own days 11+, "
               "leave-self-out mature EW market, >=3 mature names); clustered t by "
               "listing-batch date; costs 0.18%/0.30% RT (+1.5x stress) + real funding"),
    "n_events_dev": len(dev_syms), "n_batches_dev": len(dev_batches),
    "n_events_val": len(val_syms), "n_batches_val": len(set(batch_of[s] for s in val_syms)),
    "n_listings_post_holdout_untouched": 105 - len(syms),
    "n_cells": N_CELLS,
    "beta_hat": {"n_estimated": n_beta_est, "fallback_median": round(beta_fallback, 3),
                 "cross_sec_median": round(float(np.median([S[s]['beta'] for s in syms])), 3)},
    "dev_cells": cells,
    "bh_fdr_q10_significant": bh_sig,
    "candidates_dev_gate": candidates,
    "val_rescore": val_rescore,
    "permutation": {
        "n_perm": N_PERM, "best_cell": obs_best_cell, "best_abs_t": round(obs_best_t, 3),
        "p_best_vs_null_max_t": perm_p,
        "null_max_t_p50": round(float(np.percentile(max_ts, 50)), 3),
        "null_max_t_p90": round(float(np.percentile(max_ts, 90)), 3),
        "null_max_t_p99": round(float(np.percentile(max_ts, 99)), 3),
        "n_perm_batches": len(perm_batches), "n_perm_events": len(perm_syms),
        "note": ("placebo anchors restricted to mature windows fully inside dev "
                 "(exit<=05-31) => only early batches eligible; placebo periods have "
                 "lower vol than true listing windows (t is scale-free; caveat noted)"),
    },
    "q1_path_descriptive": {"day0_intraday": day0_desc, "per_day": path_desc},
    "q2_funding_path": {"n_dev_events_with_funding": n_dev_with_funding,
                        "coverage_caveat": "funding table covers 58/105 symbols only",
                        "by_day_bucket": fund_path},
    "q3_liquidity_evolution": liq_desc,
    "caveats": [
        "n=50 dev events / 17 batches (<100 => EXPLORATORY per protocol).",
        "beta_hat uses post-event mature days (no pre-listing data exists for a new "
        "listing); mild look-ahead in the risk model, none in the signal.",
        "June val events have <=10 trading days before the 06-15 wall; long-horizon "
        "val cells lose n mechanically.",
        "Early-Feb events (TSLA/INTC/HOOD/Feb-09 batch) drop out of resid cells: no "
        "mature universe existed to strip against.",
        "Funding pnl assumed 0 for the 47 symbols missing from the funding table.",
        "Permutation null drawn from mature (calmer) periods -- distribution-shape "
        "caveat; t is scale-free which mitigates but does not remove it.",
    ],
}
with open(f"{ROOT}/alpha_screen/H/results_H.json", "w") as f:
    json.dump(out, f, indent=1)

print(f"dev events {len(dev_syms)} in {len(dev_batches)} batches | val {len(val_syms)} | cells {N_CELLS}")
print(f"beta_hat estimated for {n_beta_est} syms, fallback {beta_fallback:.2f}")
print("\ntop dev cells by |t_clust| (n>=10):")
for k, c in top:
    print(f"  {k:22s} n={c['n']:3d} nb={c['n_batches']:2d} gross={c['gross_mean']:+7.3f}% "
          f"t={c['t_clust']:+5.2f} win={c['win']:5.1f}% net={c.get('net_mean')} "
          f"stress={c.get('net_mean_stress')} bshare={c['max_batch_share']}")
print(f"\nBH-FDR q=0.10: {bh_sig}")
print(f"dev-gate candidates: {candidates}")
for k, v in val_rescore.items():
    print(f"  VAL {k}: {v}")
print(f"\npermutation: best={obs_best_cell} |t|={obs_best_t:.2f} "
      f"p_vs_null_max_t={perm_p:.4f} null_p50={np.percentile(max_ts,50):.2f} "
      f"p90={np.percentile(max_ts,90):.2f} (batches={len(perm_batches)}, events={len(perm_syms)})")
print(f"\nday0 intraday: {day0_desc}")
print("resid path d1..d10 (mean%):",
      {k: v['resid_mean'] for k, v in path_desc.items()})
print("funding path:", {k: {'mean': v['mean_pct'], 'abs': v['mean_abs_pct']}
                        for k, v in fund_path.items()})
print("amp ratio by day:", liq_desc["amp_ratio_median_by_day"])
print("qv ratio by day:", liq_desc["qv_ratio_median_by_day"])
print(f"qv day0-3 median ${liq_desc['dev_event_qv_day0_3_median_usd']:,.0f} "
      f"p25 ${liq_desc['dev_event_qv_day0_3_p25_usd']:,.0f}")
