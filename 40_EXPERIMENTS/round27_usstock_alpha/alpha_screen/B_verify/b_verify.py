#!/usr/bin/env python3
"""Round27 族B adversarial verification (independent re-implementation).

Attacks:
 (a) beta/momentum disguise  — recompute EW-strip myself + date-clustered t on stripped
 (b) LODO                    — leave-one-date / leave-one-symbol re-run (dev + val)
 (c) overlapping holding     — effective N = n_dates; date-clustered t
 (d) cost stress             — 1.5x, 2x, realistic weekend-entry spread (10/25bp per side)
 (e) listing-date bias       — per-month breakdown of dev edge; early-narrow-cross-section check
 (f) TZ/DST                  — manual ET->UTC spot checks around 2026-03-08; anchor staleness

Iron rule: no data with ot > 1781654399000.
"""
import json
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np

DIR = "/Volumes/T9/BWE/40_EXPERIMENTS/round27_usstock_alpha"
OUT = DIR + "/alpha_screen/B_verify"
CAP = 1781654399000
DEV_END = "2026-05-31"
ET = ZoneInfo("America/New_York")

REPORT = {}

# ---------------- load panel ----------------
rows = [json.loads(l) for l in open(DIR + "/panel_devval.jsonl")]
assert all(r["rth_open_ts"] <= CAP and r["rth_close_ts"] <= CAP for r in rows)
by_sym = defaultdict(list)
for r in rows:
    by_sym[r["symbol"]].append(r)
for s in by_sym:
    by_sym[s].sort(key=lambda x: x["date"])
    for i, r in enumerate(by_sym[s]):
        if i > 0 and r.get("prev_close") is not None:
            r["_prev_date"] = by_sym[s][i - 1]["date"]
            r["_prev_close_ts"] = by_sym[s][i - 1]["rth_close_ts"]

db = sqlite3.connect("file:%s?mode=ro" % (DIR + "/tradfi_full.sqlite3"), uri=True)

fund = {}
for s in by_sym:
    fr = db.execute(
        "SELECT funding_time, funding_rate FROM funding WHERE symbol=? AND funding_time<=? ORDER BY funding_time",
        (s, CAP)).fetchall()
    fund[s] = (np.array([x[0] for x in fr], np.int64), np.array([x[1] for x in fr], float))
REPORT["funding_syms_with_records"] = int(sum(1 for s in fund if len(fund[s][0]) > 0))


def fund_pnl(sym, t0, t1, pos):
    ft, fr = fund[sym]
    if len(ft) == 0:
        return 0.0
    m = (ft > t0) & (ft <= t1)
    return float(-pos * fr[m].sum() * 100)


def et_ms(date_str, hh, mm=0):
    y, mo, dd = map(int, date_str.split("-"))
    return int(datetime(y, mo, dd, hh, mm, tzinfo=ET).timestamp() * 1000)


# ---------------- (f) DST / timezone spot checks ----------------
tzchk = {}
# manual: before 2026-03-08 ET=UTC-5, after ET=UTC-4 (DST starts 2am ET on 03-08)
manual = {
    "2026-03-01 18:00 ET (EST)": ("2026-03-01", 18, 23),   # expect 23:00 UTC same day
    "2026-03-08 18:00 ET (EDT, DST day)": ("2026-03-08", 18, 22),
    "2026-06-07 18:00 ET (EDT)": ("2026-06-07", 18, 22),
    "2026-02-08 18:00 ET (EST)": ("2026-02-08", 18, 23),
}
for k, (d, hh, exp_utc_h) in manual.items():
    ms = et_ms(d, hh)
    got = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    tzchk[k] = {"utc": got.strftime("%Y-%m-%d %H:%M"), "expect_utc_hour": exp_utc_h,
                "ok": got.hour == exp_utc_h and got.strftime("%Y-%m-%d") == d}
# panel rth_open_ts should be 09:30 ET before and after DST
for d in ("2026-01-28", "2026-02-02", "2026-03-09", "2026-04-13", "2026-06-08"):
    cand = [r for r in rows if r["date"] == d]
    if cand:
        ts = cand[0]["rth_open_ts"]
        et_dt = datetime.fromtimestamp(ts / 1000, tz=ET)
        utc_dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        tzchk["panel_open_%s" % d] = {"et": et_dt.strftime("%H:%M"), "utc": utc_dt.strftime("%H:%M"),
                                      "ok": et_dt.strftime("%H:%M") == "09:30"}
REPORT["f_tz_dst_checks"] = tzchk

# ---------------- rebuild P2 paths independently ----------------
paths = []
anchor_stale_min = []
for sym, srows in sorted(by_sym.items()):
    need = [r for r in srows if r.get("is_weekend_gap") == 1 and r.get("gap_days") == 3
            and r.get("prev_close") is not None]
    if not need:
        continue
    kr = db.execute("SELECT ot, cl FROM klines_1m WHERE symbol=? AND ot<=? ORDER BY ot", (sym, CAP)).fetchall()
    ot = np.array([x[0] for x in kr], np.int64)
    cl = np.array([x[1] for x in kr], float)

    def px_at(ts, tol_min=45):
        j = int(np.searchsorted(ot, ts + 1)) - 1
        if j < 0 or ts - ot[j] > tol_min * 60000:
            return None, None
        return float(cl[j]), (ts - int(ot[j])) / 60000.0

    for r in need:
        f = datetime.strptime(r["_prev_date"], "%Y-%m-%d")
        sun = (f + timedelta(days=2)).strftime("%Y-%m-%d")
        s18_ts = et_ms(sun, 18)
        px, stale = px_at(s18_ts)
        if px is None:
            continue
        anchor_stale_min.append(stale)
        rec = {"symbol": sym, "date": r["date"], "qv_day": r["qv_day"],
               "drift": (px - r["prev_close"]) / r["prev_close"] * 100,
               "sun18_ts": s18_ts, "stale_min": stale,
               "mon_open_ts": r["rth_open_ts"], "mon_close_ts": r["rth_close_ts"]}
        if r.get("px_o60") is not None:
            rec["leg_o60"] = (r["px_o60"] - px) / px * 100
        rec["leg_open"] = (r["rth_open"] - px) / px * 100
        rec["leg_close"] = (r["rth_close"] - px) / px * 100
        # anchor-vs-open sanity: last 1m close just before Monday open vs panel rth_open
        pxo, _ = px_at(r["rth_open_ts"], tol_min=10)
        if pxo is not None:
            rec["preopen_vs_open_bp"] = abs(pxo - r["rth_open"]) / r["rth_open"] * 1e4
        paths.append(rec)

dev_p = [p for p in paths if p["date"] <= DEV_END]
val_p = [p for p in paths if p["date"] > DEV_END]
REPORT["paths"] = {"dev": len(dev_p), "val": len(val_p),
                   "anchor_stale_min_median": round(float(np.median(anchor_stale_min)), 2),
                   "anchor_stale_min_p90": round(float(np.percentile(anchor_stale_min, 90)), 2),
                   "preopen_vs_open_bp_median": round(float(np.median([p["preopen_vs_open_bp"] for p in paths if "preopen_vs_open_bp" in p])), 2)}

# EW per date per leg (beta baseline), over ALL paths on that date
ew = defaultdict(dict)
byd = defaultdict(list)
for p in paths:
    byd[p["date"]].append(p)
for d, lst in byd.items():
    for w in ("leg_o60", "leg_open", "leg_close"):
        vv = [x[w] for x in lst if x.get(w) is not None]
        if vv:
            ew[d][w] = float(np.mean(vv))


def cost_pct(qv, spread_big_bp=2.0, spread_small_bp=5.0):
    half = spread_big_bp if (qv or 0) >= 5e6 else spread_small_bp
    return 0.08 + 2 * half / 100.0


def make_trades(ps, leg, thr):
    out = []
    for p in ps:
        if p.get(leg) is None or abs(p["drift"]) < thr or ew[p["date"]].get(leg) is None:
            continue
        pos = -np.sign(p["drift"])
        if pos == 0:
            continue
        exit_ts = {"leg_o60": p["mon_open_ts"] + 3600000, "leg_open": p["mon_open_ts"],
                   "leg_close": p["mon_close_ts"]}[leg]
        out.append({"date": p["date"], "symbol": p["symbol"], "pos": float(pos),
                    "gross": p[leg], "ewm": ew[p["date"]][leg],
                    "cost": cost_pct(p["qv_day"]), "qv": p["qv_day"], "stale": p["stale_min"],
                    "fpnl": fund_pnl(p["symbol"], p["sun18_ts"], exit_ts, float(pos))})
    return out


def stats(tr, cost_mult=1.0, strip=False, extra_side_bp=0.0):
    if not tr:
        return {"n": 0}
    net = np.array([t["pos"] * (t["gross"] - (t["ewm"] if strip else 0.0))
                    - cost_mult * t["cost"] - 2 * extra_side_bp / 100.0 + t["fpnl"] for t in tr])
    n = len(net)
    se = net.std(ddof=1) / np.sqrt(n)
    # date-clustered: EW per date, t over dates
    agg = defaultdict(list)
    for t, x in zip(tr, net):
        agg[t["date"]].append(x)
    dm = np.array([np.mean(v) for v in agg.values()])
    tcl = float(dm.mean() / (dm.std(ddof=1) / np.sqrt(len(dm)))) if len(dm) > 2 and dm.std(ddof=1) > 0 else None
    return {"n": n, "mean": round(float(net.mean()), 4), "t_iid": round(float(net.mean() / se), 2) if se > 0 else None,
            "n_dates": len(dm), "date_mean": round(float(dm.mean()), 4),
            "t_clustered_by_date": round(tcl, 2) if tcl is not None else None,
            "sum": round(float(net.sum()), 2)}


def lodo(tr, key):
    if not tr:
        return {}
    net = np.array([t["pos"] * t["gross"] - t["cost"] + t["fpnl"] for t in tr])
    tot = float(net.sum())
    agg = defaultdict(float)
    for t, x in zip(tr, net):
        agg[t[key]] += float(x)
    best_k, best_v = max(agg.items(), key=lambda kv: kv[1])
    keep = [i for i, t in enumerate(tr) if t[key] != best_k]
    sub = net[keep]
    return {"best": best_k, "best_contrib": round(best_v, 2), "total": round(tot, 2),
            "share": round(best_v / tot, 3) if tot > 0 else None,
            "wo_best_mean": round(float(sub.mean()), 4) if len(sub) else None,
            "wo_best_t": round(float(sub.mean() / (sub.std(ddof=1) / np.sqrt(len(sub)))), 2) if len(sub) > 2 else None,
            "per_key": {k: round(v, 2) for k, v in sorted(agg.items())}}


# ---------------- survivor cell: P2TS fade thr1 leg_o60 ----------------
CELL = {}
tr_dev = make_trades(dev_p, "leg_o60", 1.0)
tr_val = make_trades(val_p, "leg_o60", 1.0)
CELL["dev_reproduce"] = stats(tr_dev)
CELL["val_reproduce"] = stats(tr_val)
CELL["audited_claim"] = {"dev": {"n": 53, "mean_net": 1.2098, "t": 2.18, "strip": 0.5276},
                         "val": {"n": 124, "mean_net": 0.1136, "t": 0.28, "strip": 0.0826}}
# (a) beta strip
CELL["a_dev_stripped"] = stats(tr_dev, strip=True)
CELL["a_val_stripped"] = stats(tr_val, strip=True)
# strip using traded-only EW as alternative
# (c) already inside stats() as t_clustered_by_date
# (b) LODO
CELL["b_lodo_dev_date"] = lodo(tr_dev, "date")
CELL["b_lodo_dev_sym"] = lodo(tr_dev, "symbol")
CELL["b_lodo_val_date"] = lodo(tr_val, "date")
CELL["b_lodo_val_sym"] = lodo(tr_val, "symbol")
# (d) cost stress
CELL["d_dev_cost15"] = stats(tr_dev, cost_mult=1.5)
CELL["d_val_cost15"] = stats(tr_val, cost_mult=1.5)
CELL["d_dev_cost2x"] = stats(tr_dev, cost_mult=2.0)
CELL["d_dev_weekend_spread_10bp_side"] = stats(tr_dev, extra_side_bp=8.0)   # 2bp->10bp entry side approx +8bp/side
CELL["d_dev_stripped_cost15"] = stats(tr_dev, cost_mult=1.5, strip=True)
# (e) per-month dev breakdown
bym = defaultdict(list)
for t in tr_dev:
    bym[t["date"][:7]].append(t)
CELL["e_dev_by_month"] = {m: stats(v) for m, v in sorted(bym.items())}
CELL["e_dev_syms_per_date"] = {d: len([t for t in tr_dev if t["date"] == d]) for d in sorted(set(t["date"] for t in tr_dev))}
late = [t for t in tr_dev if t["date"] >= "2026-04-01"]
CELL["e_dev_apr_may_only"] = stats(late)
CELL["e_dev_apr_may_stripped"] = stats(late, strip=True)
# anchor staleness attack: fresh anchors only (<=5 min stale)
fresh = [t for t in tr_dev if t["stale"] <= 5]
CELL["f_dev_fresh_anchor_only(<=5min)"] = stats(fresh)
CELL["f_dev_stale_anchor(>5min)"] = stats([t for t in tr_dev if t["stale"] > 5])
REPORT["survivor_cell_P2TS_fade_thr1_leg_o60"] = CELL

# ---------------- second cell: fade thr1 leg_close (dev-killed) ----------------
C2 = {}
tr2 = make_trades(dev_p, "leg_close", 1.0)
C2["dev_reproduce"] = stats(tr2)
C2["a_dev_stripped"] = stats(tr2, strip=True)
C2["b_lodo_dev_date"] = lodo(tr2, "date")
REPORT["cell_P2TS_fade_thr1_leg_close"] = C2

# ---------------- P1 best cell recheck: fade thr1 r_o_close on weekend rows ----------------
wk = [r for r in rows if r.get("is_weekend_gap") == 1]
dev_wk = [r for r in wk if r["date"] <= DEV_END]
ew1 = defaultdict(dict)
byd1 = defaultdict(list)
for r in rows:
    byd1[r["date"]].append(r)
for d, lst in byd1.items():
    vv = [x["r_o_close"] for x in lst if x.get("r_o_close") is not None]
    if vv:
        ew1[d]["r_o_close"] = float(np.mean(vv))
tr1 = []
for r in dev_wk:
    g = r.get("overnight_ret"); v = r.get("r_o_close")
    if g is None or v is None or abs(g) < 1.0:
        continue
    pos = -np.sign(g)
    tr1.append({"date": r["date"], "symbol": r["symbol"], "pos": float(pos), "gross": v,
                "ewm": ew1[r["date"]]["r_o_close"], "cost": cost_pct(r.get("qv_day")), "qv": r.get("qv_day"),
                "stale": 0.0,
                "fpnl": fund_pnl(r["symbol"], r["rth_open_ts"], r["rth_close_ts"], float(pos))})
P1C = {"dev_reproduce": stats(tr1), "a_dev_stripped": stats(tr1, strip=True),
       "b_lodo_dev_date": lodo(tr1, "date")}
REPORT["cell_P1TS_fade_thr1_r_o_close"] = P1C

# ---------------- (a) macro: is weekend reversion just market beta? ----------------
# per weekend: EW drift vs EW Monday leg — if reversion lives at the market level, it's beta.
mk = []
for d, lst in sorted(byd.items()):
    dr = [p["drift"] for p in lst]
    lg = [p["leg_o60"] for p in lst if p.get("leg_o60") is not None]
    if dr and lg:
        mk.append({"date": d, "ew_drift": round(float(np.mean(dr)), 3), "ew_leg_o60": round(float(np.mean(lg)), 3)})
REPORT["a_market_level_weekends"] = mk
dr = np.array([m["ew_drift"] for m in mk if m["date"] <= DEV_END])
lg = np.array([m["ew_leg_o60"] for m in mk if m["date"] <= DEV_END])
if len(dr) > 3:
    c = float(np.corrcoef(dr, lg)[0, 1])
    REPORT["a_market_drift_vs_leg_corr_dev"] = round(c, 3)

# ---------------- FDR context ----------------
REPORT["fdr_note"] = ("64 cells tested; best dev t_iid=2.18 (n=53, two-sided p~0.034); "
                      "expected false survivors at p<0.05 over 64 correlated cells >> 1")

with open(OUT + "/b_verify_results.json", "w") as f:
    json.dump(REPORT, f, ensure_ascii=False, indent=1, default=str)
print(json.dumps(REPORT, ensure_ascii=False, indent=1, default=str))
