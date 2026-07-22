#!/usr/bin/env python3
"""
Adversarial verification of Family A (session reversion) "no survivor" finding.
Independent recomputation from panel_devval.jsonl + tradfi_full.sqlite3.
Attacks:
 (a) beta/momentum disguise — recompute beta-strip two ways:
     (1) equal-weight universe subtraction (their method, ex-self variant)
     (2) per-symbol regression beta (dev-estimated) vs ex-self market
 (b) LODO (leave-one-date / leave-one-symbol) full rerun
 (c) overlapping holding periods -> day-clustered t (effective N = days)
 (d) 1.5x cost stress
 (e) listing-date bias — per-month decomposition + universe width + market drift
 (f) timezone/DST — verify rth_open/close ET times across 2026-03-08, cross-check vs 1m bars
Hard rule: no data with ot > 1781654399000.
"""
import json, sqlite3, math
from collections import defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import numpy as np

ROOT = "/Volumes/T9/BWE/40_EXPERIMENTS/round27_usstock_alpha"
CUTOFF_MS = 1781654399000
ET = ZoneInfo("America/New_York")

rows = [json.loads(l) for l in open(f"{ROOT}/panel_devval.jsonl")]
rows = [r for r in rows if r.get("overnight_ret") is not None and r.get("r_o_close") is not None]

# leakage check
max_ts = max(r["rth_close_ts"] for r in rows)
assert max_ts <= CUTOFF_MS, f"LEAKAGE: {max_ts}"

for r in rows:
    r["split"] = "dev" if r["date"] <= "2026-05-31" else "val"
    spread_side = 0.05 if r["qv_day"] < 5_000_000 else 0.02
    r["cost"] = 0.08 + 2 * spread_side  # % round trip

# ---- funding (independent pull) ----
con = sqlite3.connect(f"{ROOT}/tradfi_full.sqlite3")
fund = defaultdict(list)
for s, ft, fr in con.execute(
    "SELECT symbol, funding_time, funding_rate FROM funding WHERE funding_time <= ?", (CUTOFF_MS,)):
    fund[s].append((ft, fr))
for s in fund: fund[s].sort()

def fund_cost_long(sym, t0, t1):
    return sum(fr for ft, fr in fund.get(sym, ()) if t0 < ft <= t1) * 100.0

for r in rows:
    r["fund_hold"] = fund_cost_long(r["symbol"], r["rth_open_ts"], r["rth_close_ts"])

# ---- market (equal-weight universe) per date per split ----
by_date = defaultdict(list)
for r in rows: by_date[r["date"]].append(r)
for d, rs in by_date.items():
    m = float(np.mean([x["r_o_close"] for x in rs]))
    s = float(np.sum([x["r_o_close"] for x in rs])); k = len(rs)
    for x in rs:
        x["mkt"] = m
        x["mkt_ex"] = (s - x["r_o_close"]) / (k - 1) if k > 1 else 0.0
        x["width"] = k

# ---- per-symbol regression beta on dev (r_o_close vs mkt_ex) ----
dev_by_sym = defaultdict(list)
for r in rows:
    if r["split"] == "dev": dev_by_sym[r["symbol"]].append(r)
beta = {}
for s, rs in dev_by_sym.items():
    if len(rs) >= 30:
        x = np.array([q["mkt_ex"] for q in rs]); y = np.array([q["r_o_close"] for q in rs])
        vx = np.var(x)
        beta[s] = float(np.cov(x, y, bias=True)[0, 1] / vx) if vx > 1e-12 else 1.0

def tstat(a):
    a = np.asarray(a, float)
    if len(a) < 2 or a.std(ddof=1) == 0: return 0.0
    return float(a.mean() / (a.std(ddof=1) / math.sqrt(len(a))))

def eval_rule(split, thr=-2.0, weekend_only=False, liq_hi=False, cost_mult=1.0):
    sel = [r for r in rows if r["split"] == split and r["overnight_ret"] < thr]
    if weekend_only: sel = [r for r in sel if r.get("is_weekend_gap") == 1]
    if liq_hi:
        med = {d: float(np.median([x["qv_day"] for x in rs])) for d, rs in by_date.items()}
        sel = [r for r in sel if r["qv_day"] >= med[r["date"]]]
    if not sel: return None
    g = np.array([r["r_o_close"] for r in sel])                       # long side
    net = g - np.array([r["cost"] for r in sel]) * cost_mult - np.array([r["fund_hold"] for r in sel])
    strip_ew = net - np.array([r["mkt"] for r in sel])                # their method
    strip_ex = net - np.array([r["mkt_ex"] for r in sel])             # ex-self ew
    strip_beta = net - np.array([beta.get(r["symbol"], 1.0) * r["mkt_ex"] for r in sel])
    # day-clustered t
    dd = defaultdict(list)
    for r, v in zip(sel, net): dd[r["date"]].append(v)
    daily = np.array([np.mean(v) for v in dd.values()])
    # LODO shares (their metric) + full LODO sign flip
    tot = net.sum()
    cd = defaultdict(float); cs = defaultdict(float)
    for r, v in zip(sel, net): cd[r["date"]] += v; cs[r["symbol"]] += v
    lodo_date = max(abs(v) for v in cd.values()) / abs(tot) if tot else float("inf")
    lodo_sym = max(abs(v) for v in cs.values()) / abs(tot) if tot else float("inf")
    flip_d = sum(1 for v in cd.values() if (tot - v) * tot < 0)
    flip_s = sum(1 for v in cs.values() if (tot - v) * tot < 0)
    bym = defaultdict(list)
    for r, v in zip(sel, net): bym[r["date"][:7]].append(v)
    return dict(n=len(sel), n_days=len(dd), gross=round(float(g.mean()), 4),
                net=round(float(net.mean()), 4), t_iid=round(tstat(net), 2),
                t_daycluster=round(tstat(daily), 2),
                strip_ew=round(float(strip_ew.mean()), 4), strip_ew_t=round(tstat(strip_ew), 2),
                strip_exself=round(float(strip_ex.mean()), 4),
                strip_beta=round(float(strip_beta.mean()), 4), strip_beta_t=round(tstat(strip_beta), 2),
                lodo_date=round(lodo_date, 3), lodo_sym=round(lodo_sym, 3),
                n_lodo_sign_flips_date=flip_d, n_lodo_sign_flips_sym=flip_s,
                by_month={m: [len(v), round(float(np.mean(v)), 3)] for m, v in sorted(bym.items())})

out = {"cells_tested_by_verifier": 0, "checks": {}}

# (a)(b)(c)(d) candidate 1: all|lt-2|o_close
c1 = {sp: eval_rule(sp) for sp in ("dev", "val")}
c1["dev_1p5x"] = eval_rule("dev", cost_mult=1.5)["net"]
c1["val_1p5x"] = eval_rule("val", cost_mult=1.5)["net"]
out["checks"]["cand1_all_lt2_oclose"] = c1

# candidate 2: liq_hi|lt-2|o_close
c2 = {sp: eval_rule(sp, liq_hi=True) for sp in ("dev", "val")}
c2["dev_1p5x"] = eval_rule("dev", liq_hi=True, cost_mult=1.5)["net"]
out["checks"]["cand2_liqhi_lt2_oclose"] = c2

# weekend exploratory: lt-2 weekend
out["checks"]["weekend_lt2_oclose"] = {sp: eval_rule(sp, weekend_only=True) for sp in ("dev", "val")}
out["cells_tested_by_verifier"] = 8

# (e) listing-date bias / regime: universe width + market intraday drift by month
reg = {}
for sp in ("dev", "val"):
    bym = defaultdict(lambda: [[], set(), []])
    for d, rs in by_date.items():
        if rs[0]["split"] != sp: continue
        m = d[:7]
        bym[m][0].append(rs[0]["mkt"]); bym[m][1].update(x["symbol"] for x in rs); bym[m][2].append(len(rs))
    reg[sp] = {m: {"n_days": len(v[0]), "mkt_oclose_mean": round(float(np.mean(v[0])), 3),
                   "n_syms": len(v[1]), "median_daily_width": int(np.median(v[2]))}
               for m, v in sorted(bym.items())}
out["checks"]["regime_by_month"] = reg
new_in_val = sorted({r["symbol"] for r in rows if r["split"] == "val"} -
                    {r["symbol"] for r in rows if r["split"] == "dev"})
out["checks"]["universe_drift"] = {"n_new_symbols_in_val": len(new_in_val), "examples": new_in_val[:10]}

# (f) DST / timezone spot checks
tz = {"open_et": defaultdict(int), "close_et": defaultdict(int)}
bad = []
for r in rows:
    o = datetime.fromtimestamp(r["rth_open_ts"] / 1000, ET)
    c = datetime.fromtimestamp(r["rth_close_ts"] / 1000, ET)
    tz["open_et"][o.strftime("%H:%M")] += 1
    tz["close_et"][c.strftime("%H:%M")] += 1
    if o.strftime("%H:%M") != "09:30" or o.date().isoformat() != r["date"]:
        bad.append((r["symbol"], r["date"]))
out["checks"]["dst"] = {"open_et_hist": dict(tz["open_et"]), "close_et_hist": dict(tz["close_et"]),
                        "n_bad_open": len(bad), "bad_examples": bad[:5]}

# spot-check events straddling 2026-03-08 vs raw 1m bars
spot = []
for sym, d in [("TSLAUSDT", "2026-03-06"), ("TSLAUSDT", "2026-03-09"),
               ("NVDAUSDT", "2026-03-06"), ("NVDAUSDT", "2026-03-09"), ("TSLAUSDT", "2026-06-08")]:
    rr = next((r for r in rows if r["symbol"] == sym and r["date"] == d), None)
    if rr is None: continue
    row = con.execute("SELECT o, cl FROM klines_1m WHERE symbol=? AND ot=?", (sym, rr["rth_open_ts"])).fetchone()
    rowc = con.execute("SELECT cl FROM klines_1m WHERE symbol=? AND ot=?", (sym, rr["rth_close_ts"])).fetchone()
    utc = datetime.fromtimestamp(rr["rth_open_ts"] / 1000, timezone.utc).strftime("%H:%M")
    et = datetime.fromtimestamp(rr["rth_open_ts"] / 1000, ET).strftime("%H:%M")
    ok_o = row is not None and abs(row[0] - rr["rth_open"]) < 1e-9
    ok_c = rowc is not None and abs(rowc[0] - rr["rth_close"]) < 1e-9
    ret_chk = abs((rr["rth_close"] / rr["rth_open"] - 1) * 100 - rr["r_o_close"]) < 1e-6
    spot.append(dict(sym=sym, date=d, open_utc=utc, open_et=et, bar_open_matches=ok_o,
                     bar_close_matches=ok_c, r_oclose_consistent=ret_chk))
out["checks"]["dst_spot_vs_1m_bars"] = spot

# overnight_ret internal consistency: prev_close vs prior panel close
sym_rows = defaultdict(list)
for r in rows: sym_rows[r["symbol"]].append(r)
mism = 0; tot = 0
allrows = [json.loads(l) for l in open(f"{ROOT}/panel_devval.jsonl")]
prevmap = {}
for s in sorted({a["symbol"] for a in allrows}):
    srows = sorted([a for a in allrows if a["symbol"] == s], key=lambda a: a["date"])
    for i in range(1, len(srows)):
        prevmap[(s, srows[i]["date"])] = srows[i - 1]["rth_close"]
for r in rows:
    pc = prevmap.get((r["symbol"], r["date"]))
    if pc is None: continue
    tot += 1
    if abs(pc - r["prev_close"]) > 1e-9: mism += 1
    if abs((r["rth_open"] / r["prev_close"] - 1) * 100 - r["overnight_ret"]) > 1e-6: mism += 1
out["checks"]["overnight_ret_consistency"] = {"checked": tot, "mismatches": mism}

json.dump(out, open(f"{ROOT}/alpha_screen/A_verify/verify_A_results.json", "w"),
          indent=1, ensure_ascii=False)
print(json.dumps(out, indent=1, ensure_ascii=False))
