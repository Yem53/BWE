#!/usr/bin/env python3
"""
Adversarial verification of Family J (funding settlement microstructure).

Independent re-implementation (not a re-run of j_funding_settlement.py):
 (a) beta-hat stripping recomputed 4 ways (their beta / beta=1 over-strip /
     daily-return beta / within-cluster cross-sectional demean)
 (b) re-clustering by UTC date (harsher than settlement-timestamp clusters)
     + LODO leave-one-date-out and leave-one-symbol-out min |t|
 (c) handwritten permutation, own code + own seed (within-cluster rate
     shuffle, 1000 reps, null max-|t| over the same 72-cell grid)
     + placebo-time test: identical windows at T+/-4h (non-settlement times)
 (d) cost/liquidity realism: Roll spread estimates, zero-volume bars,
     capacity, PP-entry staleness, and — the big one — FUNDING PAYMENT AUDIT:
     the PP implementation enters T-1min and holds through settlement in the
     WITH-rate direction => always on the paying side => pays |settled rate|.
     j_funding_settlement.py's trade_stats has no funding term (protocol
     violation: "持仓跨结算算真实资金费"). Recompute PP nets including funding.
     Also bracket the no-funding executable: POSTs1 (enter T+1m, pessimistic)
     vs POST0open (enter at first print of bar T, optimistic).
 (e) timestamp + DST spot checks (settlement hours, ms offsets, ET mapping
     across 2026-03-08, holdout wall).

Holdout wall ot <= 1781654399000 enforced in every SQL query.
"""
import json
import sqlite3
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

DB = "/Volumes/T9/BWE/40_EXPERIMENTS/round27_usstock_alpha/tradfi_full.sqlite3"
REPORTED = "/Volumes/T9/BWE/40_EXPERIMENTS/round27_usstock_alpha/alpha_screen/J/j_results.json"
OUT = "/Volumes/T9/BWE/40_EXPERIMENTS/round27_usstock_alpha/alpha_screen/J_verify/verify_J.json"
HOLDOUT_MS = 1781654399000
DEV_END_MS = 1780272000000
MIN = 60_000
W = 30
ET = ZoneInfo("America/New_York")
RNG = np.random.default_rng(20260706)   # different seed from audited run (27)
N_PERM = 1000

rep = json.load(open(REPORTED))
res = {"family": "J_verify", "checks": {}}

# ------------------------------------------------------------------ (e) wall
con = sqlite3.connect(DB)
wall = {}
wall["max_funding_time_in_db"] = con.execute(
    "SELECT MAX(funding_time) FROM funding").fetchone()[0]
wall["max_ot_in_db"] = con.execute("SELECT MAX(ot) FROM klines_1m").fetchone()[0]
wall["db_extends_past_wall"] = wall["max_ot_in_db"] > HOLDOUT_MS
wall["wall_utc"] = datetime.fromtimestamp(HOLDOUT_MS / 1000, tz=timezone.utc).isoformat()
wall["dev_end_utc"] = datetime.fromtimestamp(DEV_END_MS / 1000, tz=timezone.utc).isoformat()

fund_all = pd.read_sql(
    f"SELECT symbol, funding_time, funding_rate FROM funding WHERE funding_time <= {HOLDOUT_MS}", con)
fund_all["T"] = (fund_all.funding_time // MIN) * MIN
fund_all["hr"] = (fund_all["T"] // 1000) % 86400 // 3600
hr_counts = fund_all.hr.value_counts().sort_index()
wall["funding_rows_by_hour"] = {int(k): int(v) for k, v in hr_counts.items()}
wall["n_rows_dropped_by_hour_filter"] = int((~fund_all.hr.isin([0, 8, 16])).sum())
wall["ms_offset_distribution"] = {
    int(k): int(v) for k, v in
    (fund_all.funding_time % 3600000).value_counts().head(5).items()}
fund = fund_all[fund_all.hr.isin([0, 8, 16])].copy()
symbols = sorted(fund.symbol.unique())
wall["n_symbols_with_8h_funding"] = len(symbols)
wall["max_funding_used"] = int(fund.funding_time.max())
res["checks"]["e_wall_and_timestamps"] = wall

# DST mapping spot check
dst = {}
for label, d in [("pre_dst_2026-02-15", datetime(2026, 2, 15, tzinfo=timezone.utc)),
                 ("post_dst_2026-03-15", datetime(2026, 3, 15, tzinfo=timezone.utc))]:
    dst[label] = {h: d.replace(hour=h).astimezone(ET).strftime("%H:%M %Z")
                  for h in (0, 8, 16)}
res["checks"]["e_dst_mapping"] = dst

# ------------------------------------------------------------------ load klines
ph = ",".join("?" * len(symbols))
kl = pd.read_sql(
    f"SELECT symbol, ot, o, cl, v, qv FROM klines_1m WHERE symbol IN ({ph}) "
    f"AND ot <= {HOLDOUT_MS}", con, params=symbols)
con.close()
assert kl.ot.max() <= HOLDOUT_MS and fund.funding_time.max() <= HOLDOUT_MS

px = kl.pivot(index="ot", columns="symbol", values="cl")
op = kl.pivot(index="ot", columns="symbol", values="o")
vv = kl.pivot(index="ot", columns="symbol", values="v")
qvp = kl.pivot(index="ot", columns="symbol", values="qv")
grid = np.arange(px.index.min(), px.index.max() + MIN, MIN)
px = px.reindex(grid); op = op.reindex(grid)
vv = vv.reindex(grid); qvp = qvp.reindex(grid)
lr = np.log(px).diff()
nsym = lr.notna().sum(axis=1)
rsum = lr.sum(axis=1)

qv_med = kl[kl.ot < DEV_END_MS].groupby("symbol").qv.median()
thin_cut = qv_med.quantile(0.25)
thin = set(qv_med[qv_med < thin_cut].index)

# ------------------------------------------------- beta on non-event minutes
mod = (grid // 1000) % 86400 // 60
away = np.ones(len(grid), bool)
for h in (0, 8, 16):
    c = h * 60
    dist = np.minimum((mod - c) % 1440, (c - mod) % 1440)
    away &= dist > W
dev_mask_grid = grid < DEV_END_MS
lrv = lr.values; rsv = rsum.values; nsv = nsym.values
col = {s: i for i, s in enumerate(lr.columns)}

beta = {}
for s in symbols:
    r = lrv[:, col[s]]
    m = (rsv - np.nan_to_num(r)) / np.maximum(nsv - ~np.isnan(r) * 0 - (~np.isnan(r)).astype(int) * 0 - 1, 1)
    # careful: exclude self only where self is non-NaN
    has = ~np.isnan(r)
    m = (rsv - np.where(has, r, 0.0)) / np.maximum(nsv - has.astype(int), 1)
    ok = away & dev_mask_grid & has & ~np.isnan(m) & (nsv >= 10)
    if ok.sum() < 5000:
        beta[s] = 1.0
        continue
    rv, mv = r[ok], m[ok]
    beta[s] = float(np.dot(mv, rv - rv.mean()) / np.dot(mv - mv.mean(), mv - mv.mean()))

beta_rep = rep["beta_hat"]
res["checks"]["a_beta_replication"] = {
    "max_abs_diff_vs_reported": float(max(abs(beta[s] - beta_rep[s]) for s in symbols)),
    "beta_quantiles": {q: float(np.quantile(list(beta.values()), q))
                       for q in (0.1, 0.5, 0.9)},
}

# daily-return beta (low-frequency, robust to 1m asynchronicity attenuation)
day_idx = pd.to_datetime(px.index, unit="ms", utc=True).date
dclose = px.groupby(day_idx).last()
dclose = dclose[pd.Series(pd.to_datetime(dclose.index)).values
                < np.datetime64("2026-06-01")]
dlr = np.log(dclose).diff()
dmkt_sum = dlr.sum(axis=1); dmkt_n = dlr.notna().sum(axis=1)
beta_daily = {}
for s in symbols:
    r = dlr[s]
    m = (dmkt_sum - r.fillna(0)) / (dmkt_n - r.notna().astype(int)).clip(lower=1)
    ok = r.notna() & m.notna() & (dmkt_n >= 10)
    if ok.sum() < 30:
        beta_daily[s] = beta[s]
        continue
    rv, mv = r[ok].values, m[ok].values
    beta_daily[s] = float(np.dot(mv, rv - rv.mean()) / np.dot(mv - mv.mean(), mv - mv.mean()))
res["checks"]["a_beta_replication"]["beta_daily_quantiles"] = {
    q: float(np.quantile(list(beta_daily.values()), q)) for q in (0.1, 0.5, 0.9)}

# ------------------------------------------------------------------ events
pos = {t: i for i, t in enumerate(grid)}
g0, g1 = grid[0], grid[-1]
rows = []
for row in fund.itertuples():
    T, s, f = row.T, row.symbol, row.funding_rate
    if T - W * MIN < g0 or T + W * MIN > g1:
        continue
    i0 = pos[T]; ci = col[s]
    seg = lrv[i0 - W:i0 + W, ci]
    if np.isnan(seg).any():
        continue
    n_seg = nsv[i0 - W:i0 + W]
    m_seg = (rsv[i0 - W:i0 + W] - seg) / np.maximum(n_seg - 1, 1)
    rows.append((s, int(T), float(f), "dev" if T < DEV_END_MS else "val",
                 i0, ci, seg, m_seg,
                 seg - beta[s] * m_seg,          # resid, their beta
                 seg - m_seg,                    # resid, beta=1 overstrip
                 seg - beta_daily[s] * m_seg))   # resid, daily beta
ev = pd.DataFrame(rows, columns=["symbol", "T", "rate", "split", "i0", "ci",
                                 "raw", "mkt", "resid", "resid_b1", "resid_bd"])
dev = ev[ev.split == "dev"].reset_index(drop=True)
val = ev[ev.split == "val"].reset_index(drop=True)
med_nz = dev.loc[dev.rate != 0, "rate"].abs().median()
LARGE = 3 * med_nz
res["checks"]["replication_universe"] = {
    "n_events_dev": len(dev), "n_events_val": len(val),
    "n_clusters_dev": int(dev["T"].nunique()),
    "pct_zero_rate_dev": float((dev.rate == 0).mean()),
    "median_abs_nonzero_rate_bp": float(med_nz * 1e4),
    "large_threshold_bp": float(LARGE * 1e4),
    "n_large_dev": int((dev.rate.abs() >= LARGE).sum()),
    "n_large_val": int((val.rate.abs() >= LARGE).sum()),
    "reported": {"n_events_dev": rep["universe"]["n_events_dev"],
                 "n_events_val": rep["universe"]["n_events_val"],
                 "large_threshold_bp": rep["universe"]["large_threshold(3x_med)"] * 1e4},
}

WINDOWS = ["PRE_5", "PRE_15", "PRE_30", "POST_5", "POST_15", "POST_30"]
BUCKETS = {
    "pos": lambda r: r > 0, "neg": lambda r: r < 0,
    "large_pos": lambda r: r >= LARGE, "large_neg": lambda r: r <= -LARGE,
    "nz_signed": lambda r: r != 0, "large_signed": lambda r: np.abs(r) >= LARGE,
}
SIGNED = {"nz_signed", "large_signed"}

def wsum(paths, wname):
    x = int(wname.split("_")[1])
    return paths[:, W - x:W].sum(axis=1) if wname.startswith("PRE") \
        else paths[:, W:W + x].sum(axis=1)

def tstat(cl_ids, y):
    d = pd.DataFrame({"c": cl_ids, "y": y})
    cm = d.groupby("c").y.mean()
    k = len(cm)
    if k < 3 or cm.std(ddof=1) == 0:
        return float("nan"), k
    return float(cm.mean() / (cm.std(ddof=1) / np.sqrt(k))), k

def cell(df, meas, wname, bname, cl="T"):
    r = df.rate.values
    m = BUCKETS[bname](r)
    y = wsum(np.stack(df[meas].values), wname)[m]
    if bname in SIGNED:
        y = y * -np.sign(r[m])
    t, k = tstat(df[cl].values[m], y)
    return {"n": int(m.sum()), "n_clusters": k,
            "mean_bp": float(np.mean(y) * 1e4), "t": t}

dev["date"] = pd.to_datetime(dev["T"], unit="ms", utc=True).strftime("%Y-%m-%d") \
    if False else pd.to_datetime(dev["T"], unit="ms", utc=True).astype(str).str[:10]
val["date"] = pd.to_datetime(val["T"], unit="ms", utc=True).astype(str).str[:10]

# -------------------------------------------------- replication of survivors
SURV = ["raw|POST_5|large_signed", "raw|POST_15|large_signed",
        "resid|POST_5|large_signed", "resid|POST_15|large_signed"]
repl = {}
for key in SURV + ["raw|PRE_30|large_signed", "resid|PRE_30|large_signed",
                   "raw|POST_5|nz_signed"]:
    meas, wname, bname = key.split("|")
    mine = cell(dev, meas, wname, bname)
    repl[key] = {"mine": mine, "reported": rep["cells_dev"].get(key),
                 "match": abs(mine["t"] - rep["cells_dev"][key]["t"]) < 0.05}
res["checks"]["replication_cells"] = repl

# -------------------------------------------------- (a) beta variants on survivors
avar = {}
for key in ["POST_5|large_signed", "POST_15|large_signed"]:
    wname, bname = key.split("|")
    avar[key] = {
        "raw": cell(dev, "raw", wname, bname),
        "resid_their_betahat": cell(dev, "resid", wname, bname),
        "resid_beta1_overstrip": cell(dev, "resid_b1", wname, bname),
        "resid_daily_beta": cell(dev, "resid_bd", wname, bname),
    }
    # within-cluster cross-sectional demean (harshest: vs other settling names)
    r = dev.rate.values
    m = BUCKETS[bname](r)
    y_all = wsum(np.stack(dev["raw"].values), wname)
    d = pd.DataFrame({"T": dev["T"], "y": y_all})
    y_dm = (y_all - d.groupby("T").y.transform("mean").values)[m] * -np.sign(r[m])
    t, k = tstat(dev["T"].values[m], y_dm)
    avar[key]["cross_sectional_demeaned"] = {
        "n": int(m.sum()), "n_clusters": k, "mean_bp": float(np.mean(y_dm) * 1e4), "t": t}
res["checks"]["a_beta_variants"] = avar

# -------------------------------------------------- (b) date clustering + LODO
bchk = {}
for key in SURV:
    meas, wname, bname = key.split("|")
    bchk[key] = {"cluster_by_T_dev": cell(dev, meas, wname, bname, cl="T"),
                 "cluster_by_date_dev": cell(dev, meas, wname, bname, cl="date"),
                 "cluster_by_date_val": cell(val, meas, wname, bname, cl="date"),
                 "cluster_by_T_val": cell(val, meas, wname, bname, cl="T")}
# LODO on the key phenomenon cell (resid POST_15 large_signed) and best cell
def lodo(df, meas, wname, bname, by):
    r = df.rate.values
    m = BUCKETS[bname](r)
    y = wsum(np.stack(df[meas].values), wname)[m] * -np.sign(r[m])
    sub = pd.DataFrame({"T": df["T"].values[m], "date": df["date"].values[m],
                        "sym": df["symbol"].values[m], "y": y})
    out = []
    for u in sub[by].unique():
        s2 = sub[sub[by] != u]
        t, k = tstat(s2["T"].values, s2.y.values)
        out.append((u, t))
    ts = [t for _, t in out if not np.isnan(t)]
    worst = min(ts, key=abs)
    worst_u = [u for u, t in out if t == worst][0]
    return {"min_abs_t": float(worst), "left_out": str(worst_u),
            "n_folds": len(out)}
for key in ["raw|POST_5|large_signed", "resid|POST_15|large_signed"]:
    meas, wname, bname = key.split("|")
    bchk[key]["lodo_date"] = lodo(dev, meas, wname, bname, "date")
    bchk[key]["lodo_symbol"] = lodo(dev, meas, wname, bname, "sym")
res["checks"]["b_clustering_lodo"] = bchk

# symbol concentration among large dev events
big = dev.rate.abs() >= LARGE
sc = dev.loc[big, "symbol"].value_counts()
res["checks"]["b_large_event_concentration"] = {
    "n_symbols_in_large": int(sc.size),
    "top5_event_share": {k: round(v / big.sum(), 3) for k, v in sc.head(5).items()},
    "n_thin_in_large_events": int(dev.loc[big, "symbol"].isin(thin).sum()),
}

# -------------------------------------------------- (c) permutation, own code
codes_dev, uT = pd.factorize(dev["T"])
ncl = len(uT)
wrets = {}
for meas in ("raw", "resid"):
    paths = np.stack(dev[meas].values)
    for wname in WINDOWS:
        wrets[(meas, wname)] = wsum(paths, wname)

def all_cells_t(rates):
    masks = {b: c(rates) for b, c in BUCKETS.items()}
    sgn = -np.sign(rates)
    ts = []
    for meas in ("raw", "resid"):
        for wname in WINDOWS:
            wr = wrets[(meas, wname)]
            for bname in BUCKETS:
                m = masks[bname]
                if m.sum() == 0:
                    continue
                y = wr[m] * sgn[m] if bname in SIGNED else wr[m]
                cnt = np.bincount(codes_dev[m], minlength=ncl)
                sm = np.bincount(codes_dev[m], weights=y, minlength=ncl)
                ok = cnt > 0
                if ok.sum() < 3:
                    continue
                cm = sm[ok] / cnt[ok]
                sd = cm.std(ddof=1)
                if sd > 0:
                    ts.append(cm.mean() / (sd / np.sqrt(ok.sum())))
    return np.array(ts)

obs_ts = all_cells_t(dev.rate.values)
obs_best = float(np.max(np.abs(obs_ts)))
Tv = dev["T"].values
groups = [np.where(Tv == t)[0] for t in np.unique(Tv)]
null_max = np.empty(N_PERM)
rates0 = dev.rate.values
for p in range(N_PERM):
    rp = rates0.copy()
    for g in groups:
        rp[g] = rp[RNG.permutation(g)]
    null_max[p] = np.max(np.abs(all_cells_t(rp)))
res["checks"]["c_permutation"] = {
    "observed_best_abs_t": obs_best,
    "reported_best_abs_t": abs(rep["best_cell"]["t"]),
    "perm_p": float((null_max >= obs_best).mean()),
    "null_max_quantiles": {q: float(np.quantile(null_max, float(q)))
                           for q in ("0.5", "0.95", "0.99")},
    "reported_null_quantiles": rep["best_cell"]["null_max_t_quantiles"],
    "n_perm": N_PERM, "seed": 20260706,
}

# placebo-time test: same events/rates, windows at T +/- 4h
setl_times = set(zip(fund_all.symbol, fund_all["T"]))
plc = {}
for shift_h in (4, -4):
    sh = shift_h * 3600 * 1000
    prow = []
    for r_ in dev.itertuples():
        Tp = r_.T + sh
        if Tp - W * MIN < g0 or Tp + W * MIN > g1 or Tp >= DEV_END_MS or Tp < g0:
            continue
        # exclude if a REAL settlement (any hour) for this symbol within +/-30m
        if any((r_.symbol, Tp + k * MIN) in setl_times for k in range(-W, W + 1)):
            continue
        i0 = pos.get(Tp)
        if i0 is None:
            continue
        seg = lrv[i0 - W:i0 + W, r_.ci]
        if np.isnan(seg).any():
            continue
        prow.append((r_.T, r_.rate, seg))
    if not prow:
        continue
    pT = np.array([x[0] for x in prow])
    prate = np.array([x[1] for x in prow])
    ppaths = np.stack([x[2] for x in prow])
    m = np.abs(prate) >= LARGE
    out = {}
    for wname in ("POST_5", "POST_15"):
        y = wsum(ppaths, wname)[m] * -np.sign(prate[m])
        t, k = tstat(pT[m], y)
        out[wname + "_large_signed"] = {"n": int(m.sum()), "mean_bp": float(y.mean() * 1e4),
                                        "t": t, "n_clusters": k}
    plc[f"T{'+' if shift_h > 0 else ''}{shift_h}h"] = out
res["checks"]["c_placebo_time"] = plc

# -------------------------------------------------- (d) costs / liquidity / FUNDING
dcost = {}
# Roll effective spread per symbol (dev, away-from-settlement minutes)
roll = {}
for s in symbols:
    r = lrv[:, col[s]]
    ok = away & dev_mask_grid & ~np.isnan(r)
    rr = r[ok]
    if len(rr) < 5000:
        continue
    c1 = np.cov(rr[1:], rr[:-1])[0, 1]
    roll[s] = float(2 * np.sqrt(-c1) * 1e4) if c1 < 0 else 0.0
rv_ = [v for v in roll.values() if v > 0]
dcost["roll_spread_bp_full"] = {"median": float(np.median(rv_)),
                                "p90": float(np.quantile(rv_, 0.9)),
                                "n_symbols_est": len(rv_)}
# spread assumed in audited run: normal 2bp/side (4bp RT) + 8bp fee = 12bp RT
big_syms = dev.loc[big, "symbol"]
roll_big = [roll.get(s, np.nan) for s in big_syms.unique() if s in roll]
dcost["roll_spread_bp_large_event_symbols"] = {
    "median": float(np.nanmedian(roll_big)), "max": float(np.nanmax(roll_big))}

# volumes around settlement for large dev events
i0s = dev.loc[big, "i0"].values
cis = dev.loc[big, "ci"].values
vmat = vv.values; qmat = qvp.values; omat = op.values; cmat = px.values
zerov_T = np.array([vmat[i, c] == 0 or np.isnan(vmat[i, c]) for i, c in zip(i0s, cis)])
zerov_entry = np.array([vmat[i - 2, c] == 0 or np.isnan(vmat[i - 2, c]) for i, c in zip(i0s, cis)])
qv_T5 = np.array([np.nansum(qmat[i:i + 5, c]) for i, c in zip(i0s, cis)])
dcost["large_events_liquidity"] = {
    "pct_zero_volume_bar_T": float(zerov_T.mean()),
    "pct_zero_volume_PP_entry_bar(T-2)": float(zerov_entry.mean()),
    "median_qv_bars_T_to_T+4_usd": float(np.median(qv_T5)),
    "p10_qv_bars_T_to_T+4_usd": float(np.quantile(qv_T5, 0.1)),
    "capacity_at_10pct_participation_usd": float(np.median(qv_T5) * 0.1),
}

# bar-T decomposition: gap (cl[T-1]->o[T]) vs body (o[T]->cl[T]), signed w/ rate
sgn_big = np.sign(dev.loc[big, "rate"].values)
gap = np.array([np.log(omat[i, c] / cmat[i - 1, c]) for i, c in zip(i0s, cis)])
body = np.array([np.log(cmat[i, c] / omat[i, c]) for i, c in zip(i0s, cis)])
dcost["barT_decomposition_large_signed_bp"] = {
    "gap_cl(T-1)_to_open(T)": float(np.nanmean(gap * sgn_big) * 1e4),
    "body_open(T)_to_cl(T)": float(np.nanmean(body * sgn_big) * 1e4),
    "note": "gap = first print after settlement vs last print before; "
            "body = capturable by entering at first post-settlement print",
}

# ------------------ FUNDING PAYMENT AUDIT on PP implementation ------------------
# PP enters T-1m, holds through settlement, direction = WITH sign(rate)
# => always the paying side => pays |settled rate| per trade. Audited
# trade_stats omitted this. Recompute PP_5/15/30 net WITH funding.
def pp_net(df, x, bname, stress, include_funding):
    r = df.rate.values
    m = BUCKETS[bname](r)
    paths = np.stack(df["raw"].values)
    gross = paths[:, W - 1:W + x].sum(axis=1)[m] * np.sign(r[m])   # 'with'
    syms = df.symbol.values[m]
    cost = np.where([s in thin for s in syms], 0.0018, 0.0012) * stress
    net = gross - cost - (np.abs(r[m]) if include_funding else 0.0)
    t, k = tstat(df["T"].values[m], net)
    return {"n": int(m.sum()), "mean_gross_bp": float(gross.mean() * 1e4),
            "mean_funding_paid_bp": float(np.abs(r[m]).mean() * 1e4) if include_funding else 0.0,
            "mean_net_bp": float(net.mean() * 1e4), "t_net": t,
            "win_rate": float((net > 0).mean())}

fa = {"protocol_rule": "持仓跨结算算真实资金费 (positions crossing settlement pay real funding)",
      "audited_code_has_funding_term": False,
      "mean_abs_rate_large_dev_bp": float(dev.loc[big, "rate"].abs().mean() * 1e4),
      "median_abs_rate_large_dev_bp": float(dev.loc[big, "rate"].abs().median() * 1e4)}
for x in (5, 15, 30):
    fa[f"PP_{x}_dev"] = {
        "no_funding_1.5x(as_audited)": pp_net(dev, x, "large_signed", 1.5, False),
        "with_funding_1.0x": pp_net(dev, x, "large_signed", 1.0, True),
        "with_funding_1.5x": pp_net(dev, x, "large_signed", 1.5, True),
    }
fa["PP_15_val"] = {
    "no_funding_1.5x(as_audited)": pp_net(val, 15, "large_signed", 1.5, False),
    "with_funding_1.0x": pp_net(val, 15, "large_signed", 1.0, True),
    "with_funding_1.5x": pp_net(val, 15, "large_signed", 1.5, True),
}
# no-funding executable bracket: POSTs1 (pessimistic) vs POST0open (optimistic)
def post0open(df, x, stress):
    r = df.rate.values
    m = BUCKETS["large_signed"](r)
    i0a = df.i0.values[m]; cia = df.ci.values[m]
    gross = np.array([np.log(cmat[i + x - 1, c] / omat[i, c])
                      for i, c in zip(i0a, cia)]) * np.sign(r[m])
    syms = df.symbol.values[m]
    cost = np.where([s in thin for s in syms], 0.0018, 0.0012) * stress
    net = gross - cost
    t, k = tstat(df["T"].values[m], net)
    return {"n": int(m.sum()), "mean_gross_bp": float(np.nanmean(gross) * 1e4),
            "mean_net_bp": float(np.nanmean(net) * 1e4), "t_net": t}
fa["POST0open_15_dev_1.5x_optimistic_no_funding"] = post0open(dev, 15, 1.5)
fa["POST0open_5_dev_1.5x_optimistic_no_funding"] = post0open(dev, 5, 1.5)
res["checks"]["d_costs_liquidity"] = dcost
res["checks"]["d_funding_payment_audit"] = fa

# -------------------------------------------------- month/hour stability recheck
big_paths = np.stack(dev.loc[big, "raw"].values)
p15 = big_paths[:, W:W + 15].sum(axis=1) * sgn_big
mon = dev.loc[big, "date"].str[:7].values
res["checks"]["stability"] = {
    "POST15_large_withrate_by_month_bp": {
        m_: {"n": int((mon == m_).sum()), "mean_bp": float(p15[mon == m_].mean() * 1e4)}
        for m_ in sorted(set(mon))},
    "POST5_large_withrate_by_hour_bp": {}}
hrs = (dev.loc[big, "T"].values // 1000) % 86400 // 3600
p5 = big_paths[:, W:W + 5].sum(axis=1) * sgn_big
for h in (0, 8, 16):
    res["checks"]["stability"]["POST5_large_withrate_by_hour_bp"][str(h)] = {
        "n": int((hrs == h).sum()), "mean_bp": float(p5[hrs == h].mean() * 1e4)}

def _clean(o):
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, float) and (np.isnan(o) or np.isinf(o)):
        return None
    if isinstance(o, (np.floating, np.integer, np.bool_)):
        return _clean(o.item())
    return o

with open(OUT, "w") as f:
    json.dump(_clean(res), f, indent=1)
print(json.dumps(_clean(res), indent=1))
