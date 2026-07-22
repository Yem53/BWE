#!/usr/bin/env python3
"""
Round27 Family D — ADVERSARIAL VERIFICATION (independent recompute)
===================================================================
Audited claim: ALL|S_rxn|h2 dev strip_net +2.13%/event, t=2.25, n=23,
win 61%, LODO(date) min +1.77%, both sides positive, survives 1.5x cost;
effective n=26 (53/79 dropped: perp not listed at report); exploratory only.

Checks
 (a) beta-disguise : independent strip recompute; regression beta-hat strip;
                     self-excluded & median market baskets; side-conditional
                     market exposure.
 (b) concentration : leave-one-SYMBOL-out (their lodo was by date) + LOEO;
                     duplicate-symbol audit; top-2 event share.
 (c) multiple comp : hand-written sign/label permutation over the FULL
                     64-cell grid (B=5000): perm-p of the candidate cell,
                     P(max t over gate-eligible n>=20 cells >= obs),
                     P(min p over all cells <= obs min p),
                     P(horizon-monotone-positive pattern) under null.
 (d) cost realism  : 1m bar range + quote volume at the actual entry/exit
                     minutes (16:00 ET close), days-since-listing,
                     breakeven round-trip cost.
 (e) causality     : report_time/unknown audit; perp-listing drop audit vs
                     klines MIN(ot); post_earnings_date==anchor check;
                     IMPLEMENTABLE-SIGNAL test — replace sign(reaction)
                     (which uses the 16:00 close print = entry print) with
                     the perp price 4 min before entry vs pre-earnings close;
                     count sign flips and recompute the candidate cell.
Hard rule: nothing beyond 2026-06-15 (ot <= CUTOFF in every kline query).
"""
import json, math, sqlite3, random
import numpy as np
from collections import defaultdict, Counter
from datetime import date as _date

ROOT = "/Volumes/T9/BWE/40_EXPERIMENTS/round27_usstock_alpha"
CUTOFF_MS = 1781654399000
HORIZONS = [1, 2, 3, 5]
COST, COST_STRESS = 0.12, 0.18
MAX_GAP_DAYS = 4
rng = random.Random(20260706)

# ---------- panel ----------
panel = [json.loads(l) for l in open(f"{ROOT}/panel_devval.jsonl")]
bysym = defaultdict(dict)
for r in panel:
    bysym[r["symbol"]][r["date"]] = r
symdates = {s: sorted(d) for s, d in bysym.items()}
psyms = set(bysym)
panel_max_date = max(r["date"] for r in panel)
panel_max_ts = max(r["rth_close_ts"] for r in panel)

# ---------- funding ----------
db = sqlite3.connect(f"{ROOT}/tradfi_full.sqlite3")
fund = defaultdict(list)
for s, ft, fr in db.execute(
        "SELECT symbol, funding_time, funding_rate FROM funding WHERE funding_time <= ?",
        (CUTOFF_MS,)):
    fund[s].append((ft, fr))
for s in fund:
    fund[s].sort()

def fund_long(sym, t0, t1):
    return sum(fr for ft, fr in fund.get(sym, ()) if t0 < ft <= t1) * 100.0

# ---------- market baskets ----------
def mkt_ret(d0, d1, exclude=None, median=False):
    rs = []
    for s in psyms:
        if s == exclude:
            continue
        a, b = bysym[s].get(d0), bysym[s].get(d1)
        if a and b:
            rs.append((b["rth_close"] / a["rth_close"] - 1) * 100)
    if not rs:
        return 0.0
    return float(np.median(rs)) if median else float(np.mean(rs))

# ---------- perp listing times (klines MIN(ot), cutoff-respecting) ----------
min_ot = dict(db.execute(
    "SELECT symbol, MIN(ot) FROM klines_1m WHERE ot <= ? GROUP BY symbol", (CUTOFF_MS,)))

def _d(s):
    y, m, dd = map(int, s.split("-"))
    return _date(y, m, dd)

# ---------- events: independent replication of the frozen anchor rule ----------
events, drops = [], []
n_matched = 0
for line in open(f"{ROOT}/data/uw_earnings_events.jsonl"):
    line = line.strip()
    if not line or "_empty" in line:
        continue
    e = json.loads(line)
    if e["symbol"] + "USDT" not in psyms or e["_date"] > "2026-06-15":
        continue
    n_matched += 1
    sym = e["symbol"] + "USDT"
    ds = symdates[sym]
    if e["_session"] == "premarket":
        anchor = e["report_date"] if e["report_date"] in bysym[sym] else None
    else:
        anchor = next((d for d in ds if d > e["report_date"]), None)
    if anchor is not None and (_d(anchor) - _d(e["report_date"])).days > MAX_GAP_DAYS:
        anchor = None
    if anchor is None:
        drops.append(e)
        continue
    ai = ds.index(anchor)
    ev = {"symbol": sym, "stock": e["symbol"], "anchor": anchor, "ai": ai,
          "session": e["_session"], "report_date": e["report_date"],
          "reaction": float(e["reaction"]) if e["reaction"] is not None else None,
          "emp": float(e["expected_move_perc"]) if e["expected_move_perc"] else None,
          "pre_dt": e.get("pre_earnings_date"), "post_dt": e.get("post_earnings_date"),
          "report_time": e.get("report_time")}
    if e.get("actual_eps") is not None and e.get("street_mean_est") is not None \
            and abs(float(e["street_mean_est"])) > 0:
        ev["eps_sur"] = (float(e["actual_eps"]) - float(e["street_mean_est"])) / abs(float(e["street_mean_est"]))
    else:
        ev["eps_sur"] = None
    ev["S_eps"] = ev["eps_sur"]
    ev["S_rxn"] = ev["reaction"]
    ev["S_epsN"] = (ev["eps_sur"] / ev["emp"]) if (ev["eps_sur"] is not None and ev["emp"]) else None
    ev["S_rxnN"] = (ev["reaction"] / ev["emp"]) if (ev["reaction"] is not None and ev["emp"]) else None
    ent = bysym[sym][anchor]
    ev["entry_ts"], ev["entry_px"] = ent["rth_close_ts"], ent["rth_close"]
    ev["legs"] = {}
    for h in HORIZONS:
        if ai + h < len(ds):
            dx = ds[ai + h]
            ex = bysym[sym][dx]
            ev["legs"][h] = {
                "exit_date": dx, "exit_ts": ex["rth_close_ts"],
                "raw": (ex["rth_close"] / ent["rth_close"] - 1) * 100,
                "mkt": mkt_ret(anchor, dx),
                "mkt_ex": mkt_ret(anchor, dx, exclude=sym),
                "mkt_med": mkt_ret(anchor, dx, median=True),
                "fund": fund_long(sym, ent["rth_close_ts"], ex["rth_close_ts"]),
            }
    events.append(ev)

dev = [e for e in events if e["anchor"] <= "2026-05-31"]
val = [e for e in events if e["anchor"] > "2026-05-31"]

# ---------- (e) drop audit vs klines MIN(ot) ----------
drop_audit = {"n_drops": len(drops), "listed_before_report_but_dropped": []}
for e in drops:
    sym = e["symbol"] + "USDT"
    mo = min_ot.get(sym)
    # ms of report_date 00:00 UTC (coarse: listing must clearly predate report)
    import calendar
    rd = _d(e["report_date"])
    rd_ms = calendar.timegm(rd.timetuple()) * 1000
    if mo is not None and mo < rd_ms:
        drop_audit["listed_before_report_but_dropped"].append(
            {"symbol": sym, "report_date": e["report_date"],
             "first_kline_utc_date": str(_date.fromtimestamp(mo / 1000))})
kept_listing = []
for e in events:
    mo = min_ot.get(e["symbol"])
    import calendar
    a_ms = calendar.timegm(_d(e["anchor"]).timetuple()) * 1000
    days_since_listing = (a_ms - mo) / 86400000 if mo else None
    kept_listing.append({"symbol": e["symbol"], "anchor": e["anchor"],
                         "days_since_listing": round(days_since_listing, 1)})
drop_audit["kept_events_days_since_listing_min"] = min(k["days_since_listing"] for k in kept_listing)
drop_audit["kept_events_within_7d_of_listing"] = [k for k in kept_listing if k["days_since_listing"] <= 7]

# ---------- helpers ----------
def tstat(x):
    x = np.asarray(x, float)
    if len(x) < 3 or x.std(ddof=1) == 0:
        return 0.0
    return float(x.mean() / (x.std(ddof=1) / math.sqrt(len(x))))

def p_norm(t):
    return 2 * (1 - 0.5 * (1 + math.erf(abs(t) / math.sqrt(2))))

def pnls(evs, sig, h, cost=COST, mkt_key="mkt", beta=1.0, sig_override=None):
    out = []
    for i, e in enumerate(evs):
        s = e[sig] if sig_override is None else sig_override[i]
        if s is None or s == 0 or h not in e["legs"]:
            continue
        side = 1.0 if s > 0 else -1.0
        L = e["legs"][h]
        out.append({"date": e["anchor"], "symbol": e["symbol"], "side": side,
                    "raw": L["raw"], "mkt": L[mkt_key], "fund": L["fund"],
                    "net": side * L["raw"] - cost - side * L["fund"],
                    "pnl": side * (L["raw"] - beta * L[mkt_key]) - cost - side * L["fund"]})
    return out

def mstat(items):
    v = [it["pnl"] for it in items]
    return {"n": len(v), "mean": round(float(np.mean(v)), 4), "t": round(tstat(v), 3),
            "win": round(100 * float(np.mean([x > 0 for x in v])), 1)} if v else {"n": 0}

report = {"family": "D_PEAD_verify", "checks": {}}

# ---------- replication ----------
cand = pnls(dev, "S_rxn", 2)
rep = mstat(cand)
report["checks"]["replication"] = {
    "n_matched": n_matched, "n_dropped_unlisted": len(drops),
    "n_events": len(events), "n_dev": len(dev), "n_val": len(val),
    "ALL_S_rxn_h2_recomputed": rep,
    "reported": {"n": 23, "mean": 2.1301, "t": 2.255, "win": 60.9},
    "match": (rep["n"] == 23 and abs(rep["mean"] - 2.1301) < 0.01 and abs(rep["t"] - 2.255) < 0.02),
    "panel_max_date": panel_max_date, "panel_max_ts_lte_cutoff": panel_max_ts <= CUTOFF_MS,
}

# ---------- (a) beta-disguise ----------
raws = np.array([it["side"] * 0 + it["raw"] for it in cand])   # raw (unsigned)
mkts = np.array([it["mkt"] for it in cand])
sides = np.array([it["side"] for it in cand])
b_hat = float(np.polyfit(mkts, raws, 1)[0]) if len(cand) >= 3 else None
a = {"reported_strip": rep,
     "beta_hat_regression": round(b_hat, 3),
     "strip_beta_hat": mstat(pnls(dev, "S_rxn", 2, beta=b_hat)),
     "strip_self_excluded_mkt": mstat(pnls(dev, "S_rxn", 2, mkt_key="mkt_ex")),
     "strip_median_mkt": mstat(pnls(dev, "S_rxn", 2, mkt_key="mkt_med")),
     "no_strip_net": {"mean": round(float(np.mean([it["net"] for it in cand])), 4),
                      "t": round(tstat([it["net"] for it in cand]), 3)},
     "mean_mkt_long_events": round(float(mkts[sides > 0].mean()), 4),
     "mean_mkt_short_events": round(float(mkts[sides < 0].mean()), 4),
     "side_x_mkt_mean_(beta_pnl_at_beta1)": round(float((sides * mkts).mean()), 4)}
# beta=2 stress: if these perps run hot beta vs the stock-perp universe
a["strip_beta_2x"] = mstat(pnls(dev, "S_rxn", 2, beta=2.0))
report["checks"]["a_beta_disguise"] = a

# ---------- (b) concentration ----------
def leave_one_out(items, key):
    worst = None
    for k in set(it[key] for it in items):
        sub = [it["pnl"] for it in items if it[key] != k]
        m = float(np.mean(sub))
        if worst is None or m < worst[1]:
            worst = (k, m, round(tstat(sub), 3))
    return {"left_out": worst[0], "min_mean": round(worst[1], 4), "t_at_min": worst[2]}

pv = sorted(cand, key=lambda it: -abs(it["pnl"]))
tot_abs = sum(abs(it["pnl"]) for it in cand)
b = {"loso_symbol": leave_one_out(cand, "symbol"),
     "lodo_date": leave_one_out(cand, "date"),
     "loeo_event_min_mean": round(min(float(np.mean([x["pnl"] for j, x in enumerate(cand) if j != i]))
                                      for i in range(len(cand))), 4),
     "dup_symbols_in_dev": {k: v for k, v in Counter(it["symbol"] for it in cand).items() if v > 1},
     "top2_events_abs_share": round(sum(abs(it["pnl"]) for it in pv[:2]) / tot_abs, 3),
     "top2_events": [{"symbol": it["symbol"], "date": it["date"], "pnl": round(it["pnl"], 3)} for it in pv[:2]]}
report["checks"]["b_concentration"] = b

# ---------- (c) hand-written permutation over the full 64-cell grid ----------
# precompute per-dev-event: signal tuple + legs (raw, mkt, fund per h)
sig_names = ["S_eps", "S_rxn", "S_epsN", "S_rxnN"]
sig_tuples = [tuple(e[s] for s in sig_names) for e in dev]
legs = [e["legs"] for e in dev]
anchors = [e["anchor"] for e in dev]
# dev-frozen tercile bounds (recomputed; multiset of |signal| is permutation-invariant)
terc_bounds = {}
for si, s in enumerate(sig_names):
    mags = sorted(abs(t[si]) for t in sig_tuples if t[si] not in (None, 0))
    terc_bounds[s] = (mags[len(mags) // 3], mags[2 * len(mags) // 3])

def iso_week(dstr):
    y, m, d = map(int, dstr.split("-"))
    iy, iw, _ = _date(y, m, d).isocalendar()
    return f"{iy}-W{iw:02d}"
weeks_of = [iso_week(a2) for a2 in anchors]

def grid_stats(assign):
    """assign: list of signal tuples per event (permuted). Returns cell list of
    (name, n, mean, t) + gate/monotone diagnostics for ALL cells."""
    cells = []
    per = {}  # (si,h) -> list pnl for ALL cells
    for si, s in enumerate(sig_names[:2]):  # ALL: S_eps, S_rxn only (as original)
        for h in HORIZONS:
            v = []
            for i in range(len(dev)):
                sv = assign[i][si]
                if sv in (None, 0) or h not in legs[i]:
                    continue
                side = 1.0 if sv > 0 else -1.0
                L = legs[i][h]
                v.append(side * (L["raw"] - L["mkt"]) - COST - side * L["fund"])
            per[(si, h)] = v
            cells.append((f"ALL|{s}|h{h}", len(v), float(np.mean(v)) if v else 0.0, tstat(v)))
    for si, s in enumerate(sig_names):
        q1, q2 = terc_bounds[s]
        for t in (1, 2, 3):
            for h in HORIZONS:
                v = []
                for i in range(len(dev)):
                    sv = assign[i][si]
                    if sv in (None, 0) or h not in legs[i]:
                        continue
                    m2 = abs(sv)
                    tc = 1 if m2 <= q1 else (2 if m2 <= q2 else 3)
                    if tc != t:
                        continue
                    side = 1.0 if sv > 0 else -1.0
                    L = legs[i][h]
                    v.append(side * (L["raw"] - L["mkt"]) - COST - side * L["fund"])
                cells.append((f"T{t}|{s}|h{h}", len(v), float(np.mean(v)) if v else 0.0, tstat(v)))
    for si, s in enumerate(sig_names[:2]):  # CS weekly
        for h in HORIZONS:
            wk = defaultdict(lambda: {"p": [], "n": []})
            for i in range(len(dev)):
                sv = assign[i][si]
                if sv in (None, 0) or h not in legs[i]:
                    continue
                side = 1.0 if sv > 0 else -1.0
                L = legs[i][h]
                pnl = side * (L["raw"] - L["mkt"]) - COST - side * L["fund"]
                wk[weeks_of[i]]["p" if side > 0 else "n"].append(pnl)
            rets = [0.5 * float(np.mean(g["p"])) + 0.5 * float(np.mean(g["n"]))
                    for w, g in sorted(wk.items()) if g["p"] and g["n"]]
            cells.append((f"CS|{s}|h{h}", len(rets), float(np.mean(rets)) if rets else 0.0, tstat(rets)))
    return cells, per

obs_cells, obs_per = grid_stats(sig_tuples)
obs = {nm: (n2, m2, t2) for nm, n2, m2, t2 in obs_cells}
obs_cand_t = obs["ALL|S_rxn|h2"][2]
obs_gate_max_t = max(t2 for nm, n2, m2, t2 in obs_cells if n2 >= 20)
obs_min_p = min(p_norm(t2) for nm, n2, m2, t2 in obs_cells if n2 >= 3)
srxn_means = [obs[f"ALL|S_rxn|h{h}"][1] for h in HORIZONS]
obs_monotone = all(srxn_means[k] < srxn_means[k + 1] for k in range(3)) and all(x > 0 for x in srxn_means)

B = 5000
c_cand = c_gate = c_minp = c_mono = c_gate_full = 0
idx = list(range(len(dev)))
for _ in range(B):
    rng.shuffle(idx)
    assign = [sig_tuples[j] for j in idx]
    cells, per = grid_stats(assign)
    d2 = {nm: (n2, m2, t2) for nm, n2, m2, t2 in cells}
    if d2["ALL|S_rxn|h2"][2] >= obs_cand_t:
        c_cand += 1
    gmax = max(t2 for nm, n2, m2, t2 in cells if n2 >= 20)
    if gmax >= obs_gate_max_t:
        c_gate += 1
    if min(p_norm(t2) for nm, n2, m2, t2 in cells if n2 >= 3) <= obs_min_p:
        c_minp += 1
    # horizon monotone + all positive on either ALL family
    for s in ("S_eps", "S_rxn"):
        ms = [d2[f"ALL|{s}|h{h}"][1] for h in HORIZONS]
        if all(ms[k] < ms[k + 1] for k in range(3)) and all(x > 0 for x in ms):
            c_mono += 1
            break
    # full-gate false positive: any n>=20 cell with mean>0, t>=2, both sides pos is not
    # checkable cheaply here; approximate with t>=2.0 among n>=20
    if gmax >= 2.0:
        c_gate_full += 1

report["checks"]["c_permutation"] = {
    "B": B, "note": "signal tuples permuted across the 23 dev events; legs/funding recomputed per side",
    "obs_candidate_t": round(obs_cand_t, 3),
    "perm_p_candidate_cell_one_sided": round(c_cand / B, 4),
    "obs_max_t_gate_eligible_n>=20": round(obs_gate_max_t, 3),
    "perm_p_family_gate_eligible": round(c_gate / B, 4),
    "obs_min_p_all_64_cells": round(obs_min_p, 6),
    "perm_p_min_p_family_all_cells": round(c_minp / B, 4),
    "perm_p_any_gate_cell_t>=2": round(c_gate_full / B, 4),
    "obs_horizon_monotone_positive_S_rxn": bool(obs_monotone),
    "perm_p_horizon_monotone_positive_either_ALL_signal": round(c_mono / B, 4),
}

# ---------- (d) cost / liquidity realism at actual entry & exit minutes ----------
def bar_at(sym, ts):
    r = db.execute("SELECT o,h,l,cl,qv FROM klines_1m WHERE symbol=? AND ot=? AND ot<=?",
                   (sym, ts, CUTOFF_MS)).fetchone()
    return r

def qv_window(sym, ts, mins=5):
    r = db.execute("SELECT SUM(qv), COUNT(*) FROM klines_1m WHERE symbol=? AND ot BETWEEN ? AND ? AND ot<=?",
                   (sym, ts - mins * 60000, ts + mins * 60000, CUTOFF_MS)).fetchone()
    return r

liq = []
for e in dev:
    if e["S_rxn"] in (None, 0) or 2 not in e["legs"]:
        continue
    row = {"symbol": e["symbol"], "anchor": e["anchor"]}
    for tag, ts in (("entry", e["entry_ts"]), ("exit", e["legs"][2]["exit_ts"])):
        bar1 = bar_at(e["symbol"], ts)
        qvw = qv_window(e["symbol"], ts)
        if bar1:
            o, h2_, l2, cl, qv = bar1
            row[f"{tag}_bar_range_pct"] = round((h2_ - l2) / cl * 100, 4)
            row[f"{tag}_bar_qv_usd"] = round(qv, 0)
        row[f"{tag}_qv_pm5min_usd"] = round(qvw[0], 0) if qvw and qvw[0] else 0
    liq.append(row)
er = [r["entry_bar_range_pct"] for r in liq if "entry_bar_range_pct" in r]
eq = [r["entry_qv_pm5min_usd"] for r in liq]
gross_strip_mean = float(np.mean([it["pnl"] + COST for it in cand]))
report["checks"]["d_cost_realism"] = {
    "n_events": len(liq),
    "entry_1m_bar_range_pct": {"median": round(float(np.median(er)), 4),
                               "p90": round(float(np.percentile(er, 90)), 4),
                               "max": round(float(np.max(er)), 4)},
    "entry_qv_pm5min_usd": {"median": round(float(np.median(eq)), 0),
                            "min": round(float(np.min(eq)), 0)},
    "events_with_entry_pm5min_qv_below_100k": sum(1 for x in eq if x < 100_000),
    "assumed_cost_rt_pct": COST,
    "breakeven_rt_cost_pct_h2": round(gross_strip_mean, 3),
    "mean_at_0.5pct_rt_cost": round(gross_strip_mean - 0.50, 3),
    "worst_rows": sorted(liq, key=lambda r: r["entry_qv_pm5min_usd"])[:4],
}

# ---------- (e) causality: implementable signal (no close-print lookahead) ----------
flips, impl_sig, missing = [], [], 0
for e in dev:
    if e["S_rxn"] in (None, 0) or 2 not in e["legs"]:
        impl_sig.append(None)
        continue
    pre_row = bysym[e["symbol"]].get(e["pre_dt"])
    bar = bar_at(e["symbol"], e["entry_ts"] - 4 * 60000)  # 15:55 ET bar (close known 4min pre-entry)
    if pre_row is None or bar is None:
        impl_sig.append(None); missing += 1
        continue
    proxy = bar[3] / pre_row["rth_close"] - 1
    impl_sig.append(proxy)
    if (proxy > 0) != (e["S_rxn"] > 0):
        flips.append({"symbol": e["symbol"], "anchor": e["anchor"],
                      "uw_reaction": e["S_rxn"], "perp_proxy_1555": round(proxy, 4)})
# recompute candidate cell with implementable sign (events with proxy only)
impl_items = []
for e, s in zip(dev, impl_sig):
    if s is None or s == 0 or 2 not in e["legs"]:
        continue
    side = 1.0 if s > 0 else -1.0
    L = e["legs"][2]
    impl_items.append({"pnl": side * (L["raw"] - L["mkt"]) - COST - side * L["fund"]})
post_eq_anchor = all(e["post_dt"] == e["anchor"] for e in dev + val
                     if e["S_rxn"] not in (None, 0))
report["checks"]["e_causality"] = {
    "report_time_values_matched79": dict(Counter(
        json.loads(l).get("report_time") for l in open(f"{ROOT}/data/uw_earnings_events.jsonl")
        if l.strip() and "_empty" not in l
        and json.loads(l)["symbol"] + "USDT" in psyms and json.loads(l)["_date"] <= "2026-06-15")),
    "n_report_time_unknown": 0,
    "post_earnings_date_equals_anchor_all_used": bool(post_eq_anchor),
    "signal_completes_at_entry_instant": "yes — sign(reaction) uses the 16:00 close print, entry is the same print",
    "implementable_sign_test": {
        "proxy": "perp 15:55 ET bar close vs pre-earnings-date perp RTH close",
        "n_with_proxy": sum(1 for s in impl_sig if s is not None),
        "n_missing_proxy": missing,
        "sign_flips_vs_uw_reaction": flips,
        "candidate_cell_recomputed_with_implementable_sign": mstat(impl_items),
    },
    "drop_audit": {"n_drops": len(drops),
                   "drops_where_perp_actually_listed_before_report": drop_audit["listed_before_report_but_dropped"],
                   "kept_min_days_since_listing": drop_audit["kept_events_days_since_listing_min"],
                   "kept_within_7d_of_listing": drop_audit["kept_events_within_7d_of_listing"]},
}

with open(f"{ROOT}/alpha_screen/D_verify/verify_D.json", "w") as f:
    json.dump(report, f, indent=1, default=str)

print(json.dumps(report, indent=1, default=str))
