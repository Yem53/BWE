#!/usr/bin/env python3
"""
Family J: funding settlement microstructure (8h settlements 00/08/16 UTC).

Question: do prices systematically drift before/after funding settlement,
conditioned on the sign/magnitude of the actually-settled rate
(payers closing positions pre-settlement -> price pressure)?

Discipline (round27 hardened):
- clustered t by settlement timestamp (all symbols settle simultaneously)
- fair beta-hat stripping: beta estimated on NON-event minutes, residual reported
- handwritten permutation (rates shuffled across symbols WITHIN each settlement
  cluster, >=1000 reps) -> where does best observed |t| sit in null max-|t| dist
- costs 0.12% RT (thin names 0.18% RT), 1.5x stress; LODO date/name >40% kill
- dev <= 2026-05-31, val 06-01..15 only if a dev cell passes all gates
- holdout ot > 1781654399000 never touched
"""
import json
import sqlite3
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

DB = "/Volumes/T9/BWE/40_EXPERIMENTS/round27_usstock_alpha/tradfi_full.sqlite3"
OUT = "/Volumes/T9/BWE/40_EXPERIMENTS/round27_usstock_alpha/alpha_screen/J/j_results.json"
HOLDOUT_MS = 1781654399000          # 2026-06-15T23:59:59Z, hard wall
DEV_END_MS = 1780272000000          # 2026-06-01T00:00:00Z (dev: T < this)
MIN = 60_000
W = 30                              # +/- 30 minutes around settlement
ET = ZoneInfo("America/New_York")
RNG = np.random.default_rng(27)
N_PERM = 1000

# ---------------------------------------------------------------- load funding
con = sqlite3.connect(DB)
fund = pd.read_sql(
    "SELECT symbol, funding_time, funding_rate FROM funding "
    f"WHERE funding_time <= {HOLDOUT_MS}", con)
# snap to minute (times are hh:00:00.000/001)
fund["T"] = (fund.funding_time // MIN) * MIN
fund["hr"] = (fund["T"] // 1000) % 86400 // 3600
fund = fund[fund.hr.isin([0, 8, 16])].copy()
symbols = sorted(fund.symbol.unique())

# ---------------------------------------------------------------- load klines
ph = ",".join("?" * len(symbols))
kl = pd.read_sql(
    f"SELECT symbol, ot, cl, qv FROM klines_1m WHERE symbol IN ({ph}) "
    f"AND ot <= {HOLDOUT_MS}", con, params=symbols)
con.close()

px = kl.pivot_table(index="ot", columns="symbol", values="cl")
grid = np.arange(px.index.min(), px.index.max() + MIN, MIN)
px = px.reindex(grid)                      # regular 1m grid, NaN where missing
lr = np.log(px).diff()                     # 1m log return, stamped at bar OPEN ot
                                           # (return over [ot, ot+1m), known at close)
nsym = lr.notna().sum(axis=1)
rsum = lr.sum(axis=1)
# leave-one-out equal-weight market return per minute
mkt_all = rsum / nsym.replace(0, np.nan)

# liquidity: per-symbol median 1m quote volume (dev only) -> thin = bottom quartile
qv_med = kl[kl.ot < DEV_END_MS].groupby("symbol").qv.median()
thin_cut = qv_med.quantile(0.25)
thin = set(qv_med[qv_med < thin_cut].index)

# --------------------------------------------------- fair beta on NON-event mins
mod = (grid // 1000) % 86400 // 60         # minute of day UTC
away = np.ones(len(grid), bool)
for h in (0, 8, 16):
    c = h * 60
    dist = np.minimum((mod - c) % 1440, (c - mod) % 1440)
    away &= dist > W
dev_mask = grid < DEV_END_MS
beta = {}
for s in symbols:
    r = lr[s].values
    m = ((rsum.values - np.nan_to_num(r)) / np.maximum(nsym.values - lr[s].notna().values, 1))
    ok = away & dev_mask & ~np.isnan(r) & ~np.isnan(m) & (nsym.values >= 10)
    if ok.sum() < 5000:
        beta[s] = 1.0
        continue
    rv, mv = r[ok], m[ok]
    beta[s] = float(np.dot(mv, rv - rv.mean()) / np.dot(mv - mv.mean(), mv - mv.mean()))

# ------------------------------------------------------------- event windows
g0 = grid[0]
pos = {t: i for i, t in enumerate(grid)}
lrv = lr.values
rsv = rsum.values
nsv = nsym.values
col = {s: i for i, s in enumerate(lr.columns)}

events = []   # per event: symbol,T,rate,split,raw path(-W..+W-1 of 1m rets),resid path
for row in fund.itertuples():
    T, s, f = row.T, row.symbol, row.funding_rate
    if T - W * MIN < g0 or T + W * MIN > grid[-1]:
        continue
    i0 = pos[T]
    ci = col[s]
    # 1m returns stamped at open: pre-window last X min = bars ot in [T-X*MIN, T-MIN]
    seg = lrv[i0 - W:i0 + W, ci]
    if np.isnan(seg).any():
        continue
    n_seg = nsv[i0 - W:i0 + W]
    m_seg = (rsv[i0 - W:i0 + W] - seg) / np.maximum(n_seg - 1, 1)
    resid = seg - beta[s] * m_seg
    split = "dev" if T < DEV_END_MS else "val"
    events.append((s, int(T), float(f), split, seg, resid))

ev = pd.DataFrame(events, columns=["symbol", "T", "rate", "split", "raw", "resid"])
med_nz = ev.loc[(ev.split == "dev") & (ev.rate != 0), "rate"].abs().median()
LARGE = 3 * med_nz

def win_ret(path, wname):
    """path = 61-ish array of 1m rets indexed -W..W-1 relative to T (stamped at open).
    PRE_X = sum of bars [-X..-1]  (ends exactly at settlement)
    POST_X = sum of bars [0..X-1] (starts exactly at settlement)."""
    x = int(wname[wname.index("_") + 1:])
    if wname.startswith("PRE"):
        return path[W - x:W].sum()
    return path[W:W + x].sum()

WINDOWS = ["PRE_5", "PRE_15", "PRE_30", "POST_5", "POST_15", "POST_30"]
BUCKETS = {
    "pos":        lambda r: r > 0,
    "neg":        lambda r: r < 0,
    "large_pos":  lambda r: r >= LARGE,
    "large_neg":  lambda r: r <= -LARGE,
    "nz_signed":  lambda r: r != 0,          # y = -sign(rate) * ret (fade payers)
    "large_signed": lambda r: np.abs(r) >= LARGE,
}
SIGNED = {"nz_signed", "large_signed"}

def clustered_t(df, ycol):
    """cluster = settlement timestamp T; t over cluster means (pandas, few calls)."""
    cm = df.groupby("T")[ycol].mean()
    k = len(cm)
    if k < 3 or cm.std(ddof=1) == 0:
        return np.nan, k
    return float(cm.mean() / (cm.std(ddof=1) / np.sqrt(k))), k

def clustered_t_np(codes, ncl, m, y):
    """cluster = settlement timestamp T; t over per-cluster means (numpy fast)."""
    cnt = np.bincount(codes[m], minlength=ncl)
    sm = np.bincount(codes[m], weights=y, minlength=ncl)
    ok = cnt > 0
    k = int(ok.sum())
    if k < 3:
        return np.nan, k
    cm = sm[ok] / cnt[ok]
    sd = cm.std(ddof=1)
    if sd == 0:
        return np.nan, k
    return float(cm.mean() / (sd / np.sqrt(k))), k

def precompute_wrets(sub):
    """window-return matrix per (meas, window) — independent of rates."""
    out = {}
    for meas in ("raw", "resid"):
        paths = np.stack(sub[meas].values)  # (n, 2W)
        for wname in WINDOWS:
            x = int(wname[wname.index("_") + 1:])
            if wname.startswith("PRE"):
                out[(meas, wname)] = paths[:, W - x:W].sum(axis=1)
            else:
                out[(meas, wname)] = paths[:, W:W + x].sum(axis=1)
    return out

def run_cells(sub, wrets, codes, ncl, rates=None):
    """compute all 72 cells on a split; rates override for permutation."""
    r = sub.rate.values if rates is None else rates
    masks = {b: cond(r) for b, cond in BUCKETS.items()}
    sgn = -np.sign(r)
    out = {}
    for meas in ("raw", "resid"):
        for wname in WINDOWS:
            wret = wrets[(meas, wname)]
            for bname in BUCKETS:
                m = masks[bname]
                if m.sum() == 0:
                    out[f"{meas}|{wname}|{bname}"] = dict(n=0, t=np.nan)
                    continue
                y = wret[m] * sgn[m] if bname in SIGNED else wret[m]
                t, k = clustered_t_np(codes, ncl, m, y)
                out[f"{meas}|{wname}|{bname}"] = dict(
                    n=int(m.sum()), n_clusters=k,
                    mean_bp=float(np.mean(y) * 1e4), t=t)
    return out

dev = ev[ev.split == "dev"].reset_index(drop=True)
codes_dev, uniqT = pd.factorize(dev["T"])
ncl_dev = len(uniqT)
wrets_dev = precompute_wrets(dev)
cells = run_cells(dev, wrets_dev, codes_dev, ncl_dev)
N_CELLS = len(cells)

# ------------------------------------------------------------- permutation null
# shuffle rate assignment across symbols WITHIN each settlement cluster:
# kills rate<->return link, preserves market moves & cross-sectional correlation.
Tv = dev["T"].values
order = np.argsort(Tv, kind="stable")
rates0 = dev.rate.values
groups = [np.where(Tv == t)[0] for t in np.unique(Tv)]
null_max = np.empty(N_PERM)
for p in range(N_PERM):
    rp = rates0.copy()
    for gidx in groups:
        rp[gidx] = rp[RNG.permutation(gidx)]
    cp = run_cells(dev, wrets_dev, codes_dev, ncl_dev, rates=rp)
    null_max[p] = np.nanmax([abs(v["t"]) for v in cp.values()])

best_key = max(cells, key=lambda k: abs(cells[k]["t"]) if not np.isnan(cells[k]["t"]) else -1)
best_t = cells[best_key]["t"]
perm_p_best = float((null_max >= abs(best_t)).mean())

# ------------------------------------------------------ tradeable check (dev)
# strategies on nonzero/large rate settlements:
#   PRE_X  : enter T-X, exit T          (rate ~known: premium avg nearly final)
#   POST_X : enter T,   exit T+X        (rate published exactly at T)
#   POSTs1_X: enter T+1min, exit T+1+X  (conservative: skip 1 bar after publish)
# direction: 'against' = -sign(rate) (fade payers) or 'with' = +sign(rate).
def trade_win(sub, wname):
    paths = np.stack(sub["raw"].values)
    x = int(wname.split("_")[1])
    if wname.startswith("POSTs1"):     # enter T+1 (rate published at T, no prediction)
        return paths[:, W + 1:W + 1 + x].sum(axis=1)
    if wname.startswith("PP"):         # enter T-1 (needs predicted rate; for large
        return paths[:, W - 1:W + x].sum(axis=1)  # rates ~fixed 1min pre-settle)
    return np.array([win_ret(p, wname) for p in sub["raw"]])

def trade_stats(sub, wname, bname, direction, stress=1.0):
    r = sub.rate.values
    m = BUCKETS[bname](r)
    wret = trade_win(sub, wname)
    d_sign = -np.sign(r[m]) if direction == "against" else np.sign(r[m])
    gross = wret[m] * d_sign
    syms = sub.symbol.values[m]
    cost = np.where([s in thin for s in syms], 0.0018, 0.0012) * stress
    net = gross - cost
    d = pd.DataFrame({"T": sub["T"].values[m], "y": net})
    t, k = clustered_t(d, "y")
    # LODO shares on gross pnl
    dd = pd.DataFrame({"T": sub["T"].values[m], "s": syms, "g": gross})
    dd["date"] = pd.to_datetime(dd["T"], unit="ms", utc=True).dt.date.astype(str)
    tot = dd.g.sum()
    date_sh = float((dd.groupby("date").g.sum().abs() / abs(tot)).max()) if tot != 0 else np.inf
    name_sh = float((dd.groupby("s").g.sum().abs() / abs(tot)).max()) if tot != 0 else np.inf
    return dict(n=int(m.sum()), direction=direction,
                mean_gross_bp=float(gross.mean() * 1e4),
                mean_net_bp=float(net.mean() * 1e4), t_net=t, n_clusters=k,
                lodo_max_date_share=date_sh, lodo_max_name_share=name_sh)

# PP_* added AFTER observing first-minute concentration of the bounce —
# flagged exploratory-spec; val is the arbiter. Justification: |rate| >= 10bp
# cannot materially change in the final minute of the 8h premium average.
TRADE_WINDOWS = WINDOWS + ["POSTs1_5", "POSTs1_15", "POSTs1_30",
                           "PP_5", "PP_15", "PP_30"]
trades = {}
for wname in TRADE_WINDOWS:
    for bname in ("nz_signed", "large_signed"):
        for direction in ("against", "with"):
            key = f"{wname}|{bname}|{direction}"
            trades[key] = trade_stats(dev, wname, bname, direction)
            trades[key + "|stress1.5x"] = trade_stats(dev, wname, bname, direction, stress=1.5)

# ------------------------------------------------------------------ gates + val
def passes(key):
    c = cells[key]
    if np.isnan(c["t"]) or abs(c["t"]) < 2 or c["n"] < 100:
        return False
    if (null_max >= abs(c["t"])).mean() > 0.05:
        return False
    # signed cells must also have >=1 EXECUTABLE implementation surviving
    # net cost @1.5x + t_net>=2 + LODO. Executable = POSTs1 (rate published at T,
    # enter T+1, no prediction needed) or PP (enter T-1 on predicted rate — valid
    # for large rates only; flagged assumption). Direction = sign of cell mean;
    # cells are two-sided so direction choice is covered by the |t| null.
    meas, wname, bname = key.split("|")
    if bname in SIGNED:
        direction = "against" if c["mean_bp"] > 0 else "with"
        if wname.startswith("PRE"):
            impls = [wname]
        else:
            x = wname.split("_")[1]
            impls = [f"POSTs1_{x}", f"PP_{x}"]
        ok_impls = []
        for wn in impls:
            tr = trades[f"{wn}|{bname}|{direction}|stress1.5x"]
            if (tr["mean_net_bp"] > 0 and not np.isnan(tr["t_net"]) and tr["t_net"] >= 2
                    and tr["lodo_max_date_share"] <= 0.4
                    and tr["lodo_max_name_share"] <= 0.4):
                ok_impls.append(wn)
        if not ok_impls:
            return False
        surviving_impl[key] = (direction, ok_impls)
    return True

surviving_impl = {}
survivors = [k for k in cells if passes(k)]
val = ev[ev.split == "val"].reset_index(drop=True)
val_results = {}
if survivors:
    codes_val, uT = pd.factorize(val["T"])
    vc = run_cells(val, precompute_wrets(val), codes_val, len(uT))
    for k in survivors:
        val_results[k] = vc[k]
        if k in surviving_impl:
            direction, impls = surviving_impl[k]
            _, _, bname = k.split("|")
            for wn in impls:
                val_results[k][f"trade_{wn}_{direction}_1.5x"] = trade_stats(
                    val, wn, bname, direction, stress=1.5)

# --------------------------------------------------------- descriptive extras
def cum_path(sub, meas):
    if len(sub) == 0:
        return None
    arr = np.stack(sub[meas].values)
    return (np.cumsum(arr.mean(axis=0)) * 1e4).round(3).tolist()

desc = {
    "path_bp_cum_by_bucket_resid": {
        b: cum_path(dev[BUCKETS[b](dev.rate.values)], "resid")
        for b in ("pos", "neg", "large_pos", "large_neg")},
    "path_bp_cum_all_raw": cum_path(dev, "raw"),
    "by_settlement_hour_raw_PRE15_bp": {
        str(h): float(np.mean([win_ret(p, "PRE_15") for p in
                       dev.loc[(dev["T"] // 1000) % 86400 // 3600 == h, "raw"]]) * 1e4)
        for h in (0, 8, 16)},
}
# by-hour breakdown of the key POST_5 large_signed effect (concentration check)
hr_dev = (dev["T"] // 1000) % 86400 // 3600
big = np.abs(dev.rate.values) >= LARGE
p5 = np.stack(dev["raw"].values)[:, W:W + 5].sum(axis=1)
mon = pd.to_datetime(dev["T"], unit="ms", utc=True).dt.strftime("%Y-%m").values
desc["POST15_large_withrate_by_month_bp"] = {
    m: {"n": int((big & (mon == m)).sum()),
        "mean_bp": float((np.stack(dev["raw"].values)[big & (mon == m), W:W + 15].sum(axis=1)
                          * np.sign(dev.rate.values[big & (mon == m)])).mean() * 1e4)}
    for m in sorted(set(mon))}
desc["POST5_large_withrate_by_hour"] = {
    str(h): {"n": int((big & (hr_dev == h)).sum()),
             "mean_bp": float((p5[big & (hr_dev == h)]
                               * np.sign(dev.rate.values[big & (hr_dev == h)])).mean() * 1e4)}
    for h in (0, 8, 16)}
# ET/RTH tag (DST-aware): 16:00 UTC settlement is 12:00 EDT (in RTH) after 2026-03-08
rth_flags = {}
for h in (0, 8, 16):
    ts = dev.loc[(dev["T"] // 1000) % 86400 // 3600 == h, "T"]
    if len(ts):
        et_hrs = {datetime.fromtimestamp(t / 1000, tz=timezone.utc).astimezone(ET).hour
                  for t in ts.sample(min(50, len(ts)), random_state=0)}
        rth_flags[str(h)] = sorted(et_hrs)
desc["settlement_utc_hour_to_ET_hours"] = rth_flags

result = {
    "family": "J_funding_settlement_microstructure",
    "n_cells_tested": N_CELLS,
    "n_trade_variants": len(trades),
    "universe": {"n_symbols": len(symbols),
                 "n_events_dev": int(len(dev)), "n_events_val": int(len(val)),
                 "n_clusters_dev": int(dev["T"].nunique()),
                 "pct_zero_rate_dev": float((dev.rate == 0).mean()),
                 "median_abs_nonzero_rate": float(med_nz),
                 "large_threshold(3x_med)": float(LARGE),
                 "n_thin_symbols": len(thin)},
    "beta_hat": {s: round(beta[s], 3) for s in symbols},
    "cells_dev": cells,
    "best_cell": {"key": best_key, "t": best_t, "perm_p_vs_null_max": perm_p_best,
                  "null_max_t_quantiles": {q: float(np.quantile(null_max, float(q)))
                                           for q in ("0.5", "0.95", "0.99")}},
    "tradeable_dev": trades,
    "gates": "cluster|t|>=2 AND n>=100 AND perm_p(null max)<=0.05 AND "
             "(signed: net>0 @1.5x stress, t_net>=2, LODO date/name<=40%)",
    "survivors_dev": survivors,
    "surviving_implementations": {k: {"direction": v[0], "impls": v[1]}
                                  for k, v in surviving_impl.items()},
    "val_results": val_results,
    "descriptive": desc,
}

def _clean(o):
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, float) and (np.isnan(o) or np.isinf(o)):
        return None
    if isinstance(o, (np.floating, np.integer)):
        return _clean(o.item())
    return o

with open(OUT, "w") as f:
    json.dump(_clean(result), f, indent=1)
print(json.dumps(_clean(result)["best_cell"], indent=1))
print("survivors:", survivors)
print("cells:", N_CELLS, "events dev/val:", len(dev), len(val))
