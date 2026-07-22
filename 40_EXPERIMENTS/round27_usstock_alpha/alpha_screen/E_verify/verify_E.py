#!/usr/bin/env python3
"""对抗验证 族E (财报隔夜drift) — 独立复算, 不复用被审脚本代码。

检查项:
(a) β剥离自查复算 — 从DB独立重算全部66 cells + headline; β篮子污染敏感性(剔除同日财报名)
(b) 单名/单事件/单日集中 — LODO(date) 复跑 + leave-one-EVENT-out + 04-29三事件簇剔除
(c) 多重比较 — 手写permutation: 事件级sign-flip + 日期簇sign-flip, 统计 headline选择流程
    (n>=8里最大|t|) 在null下的分布, 报 p(max|t| >= 2.62)
(d) 成本/滑点现实性 — 22:00 ET入场流动性复核 + funding费(持仓22:00→09:31跨08:00UTC结算)
(e) 时间戳因果 — report_time vs _session 一致性, unknown处理, 信号可知性, drop审计
"""
import json, math, random, sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ROOT = "/Volumes/T9/BWE/40_EXPERIMENTS/round27_usstock_alpha"
DB = ROOT + "/tradfi_full.sqlite3"
EVENTS = ROOT + "/data/uw_earnings_events.jsonl"
PANEL = ROOT + "/panel_devval.jsonl"
THEIR = json.load(open(ROOT + "/alpha_screen/E/results_E.json"))
OUT = ROOT + "/alpha_screen/E_verify/verify_E_results.json"

HOLDOUT_MAX = 1781654399000
DEV_END = "2026-05-31"
VAL_END = "2026-06-15"
ET = ZoneInfo("America/New_York")
STALE_MS = 15 * 60000

con = sqlite3.connect(DB)
UNIVERSE = [s for (s,) in con.execute("SELECT DISTINCT symbol FROM klines_1m")]

# ---------- panel ----------
panel = {}
sym_dates = defaultdict(list)
for line in open(PANEL):
    r = json.loads(line)
    panel[(r["symbol"], r["date"])] = r
    sym_dates[r["symbol"]].append(r["date"])
for s in sym_dates:
    sym_dates[s].sort()

import bisect
def next_row(sym, d):
    ds = sym_dates[sym]
    i = bisect.bisect_right(ds, d)
    return panel[(sym, ds[i])] if i < len(ds) else None

# ---------- events (same filter, independent parse) ----------
all_ah_by_date = defaultdict(set)   # date -> set of afterhours-reporting perp symbols (for basket contamination)
events = []
report_time_counter = defaultdict(int)
mismatch = []
uniset = set(UNIVERSE)
for line in open(EVENTS):
    line = line.strip()
    if not line or '"_empty"' in line:
        continue
    e = json.loads(line)
    if e.get("_session") == "afterhours" and e["symbol"] + "USDT" in uniset:
        all_ah_by_date[e["_date"]].add(e["symbol"] + "USDT")
    if e.get("_session") != "afterhours":
        continue
    if e["symbol"] + "USDT" not in uniset:
        continue
    if e["_date"] > VAL_END:
        continue
    events.append(e)
    rt = e.get("report_time")
    report_time_counter[str(rt)] += 1
    if rt not in ("postmarket",):
        mismatch.append({"symbol": e["symbol"], "date": e["_date"], "report_time": rt})
print("events loaded:", len(events), " report_time dist:", dict(report_time_counter))
print("session/report_time mismatch:", mismatch)

# ---------- point price ----------
_pc = {}
def px_at(sym, ts):
    assert ts <= HOLDOUT_MAX + 60000, "holdout violation"
    k = (sym, ts)
    if k in _pc: return _pc[k]
    row = con.execute("SELECT ot, cl FROM klines_1m WHERE symbol=? AND ot<? AND ot>=? "
                      "ORDER BY ot DESC LIMIT 1", (sym, ts, ts - STALE_MS)).fetchone()
    out = float(row[1]) if row else None
    _pc[k] = out
    return out

def et_ts(dstr, hour):
    d = datetime.strptime(dstr, "%Y-%m-%d")
    if hour == 24:
        d += timedelta(days=1); hour = 0
    return int(datetime(d.year, d.month, d.day, hour, 0, tzinfo=ET).timestamp() * 1000)

def uni_ret(t1, t2, exclude_set):
    rets = []
    for s in UNIVERSE:
        if s in exclude_set: continue
        p1 = px_at(s, t1); p2 = px_at(s, t2)
        if p1 and p2 and p1 > 0:
            rets.append((p2 / p1 - 1) * 100)
    return (sum(rets) / len(rets), len(rets)) if len(rets) >= 5 else (None, len(rets))

# ---------- per-event measurement (independent) ----------
rows = []
drop_audit = []
for e in events:
    sym = e["symbol"] + "USDT"; D = e["_date"]
    rowD = panel.get((sym, D))
    rowN = next_row(sym, D) if rowD else None
    if not rowD or not rowN or rowN.get("px_o30") is None or rowN.get("px_o60") is None:
        # audit: bars on event date? (perp listed?)
        t0, t1 = et_ts(D, 0), et_ts(D, 24)
        nb = con.execute("SELECT COUNT(*) FROM klines_1m WHERE symbol=? AND ot>=? AND ot<?",
                         (sym, t0, t1)).fetchone()[0]
        drop_audit.append({"symbol": e["symbol"], "date": D, "bars_on_date": nb,
                           "reason": "no_panel" if not rowD else "no_next/anchor"})
        continue
    t_close = rowD["rth_close_ts"] + 60000
    t_open = rowN["rth_open_ts"] + 60000
    t_o30 = rowN["rth_open_ts"] + 31 * 60000
    t_o60 = rowN["rth_open_ts"] + 61 * 60000
    if t_o60 > HOLDOUT_MAX:
        drop_audit.append({"symbol": e["symbol"], "date": D, "reason": "holdout"})
        continue
    anchors = {"close": (t_close, rowD["rth_close"]), "open": (t_open, rowN["rth_open"]),
               "o30": (t_o30, rowN["px_o30"]), "o60": (t_o60, rowN["px_o60"])}
    ok = True
    for H in (20, 22, 24):
        p = px_at(sym, et_ts(D, H))
        if p is None: ok = False; break
        anchors[f"e{H}"] = (et_ts(D, H), p)
    if not ok:
        drop_audit.append({"symbol": e["symbol"], "date": D, "reason": "no_evening_px"})
        continue
    rec = {"symbol": e["symbol"], "date": D, "em_pct": float(e["expected_move_perc"]) * 100,
           "report_time": e.get("report_time")}
    for H in (20, 22, 24):
        rec[f"react{H}"] = (anchors[f"e{H}"][1] / anchors["close"][1] - 1) * 100
    win = {}
    for ent in ("e20", "e22", "e24", "open"):
        for ex in ("open", "o30", "o60"):
            if ent == "open" and ex == "open": continue
            t1, p1 = anchors[ent]; t2, p2 = anchors[ex]
            r = (p2 / p1 - 1) * 100
            u, nu = uni_ret(t1, t2, {sym})
            # 污染敏感性: 剔除同日所有盘后财报名
            u2, nu2 = uni_ret(t1, t2, all_ah_by_date[D] | {sym})
            win[f"{ent}_{ex}"] = {"raw": r, "xr": (r - u) if u is not None else None,
                                  "xr_clean": (r - u2) if u2 is not None else None,
                                  "n_uni": nu, "n_uni_clean": nu2}
    rec["win"] = win
    rec["t_entry"], rec["t_exit"] = anchors["e22"][0], anchors["open"][0]
    rows.append(rec)

print("measured:", len(rows))
dev = [r for r in rows if r["date"] <= DEV_END]
val = [r for r in rows if r["date"] > DEV_END]
print("dev:", len(dev), "val:", len(val))

# ---------- cells ----------
BINS = {
    "all": lambda r, ra: True,
    "abs_ge2": lambda r, ra: abs(r[ra]) >= 2,
    "abs_ge5": lambda r, ra: abs(r[ra]) >= 5,
    "abs_ge10": lambda r, ra: abs(r[ra]) >= 10,
    "over_em": lambda r, ra: abs(r[ra]) >= r["em_pct"],
    "under_em05": lambda r, ra: abs(r[ra]) < 0.5 * r["em_pct"],
}
WINDOWS = ["e20_open", "e20_o30", "e20_o60", "e22_open", "e22_o30", "e22_o60",
           "e24_open", "e24_o30", "e24_o60", "open_o30", "open_o60"]
RA = {"e20": "react20", "e22": "react22", "e24": "react24", "open": "react22"}

def tstat(vals):
    n = len(vals)
    m = sum(vals) / n
    sd = math.sqrt(sum((v - m) ** 2 for v in vals) / (n - 1)) if n > 1 else 0.0
    return m, sd, (m / (sd / math.sqrt(n)) if sd > 0 else 0.0)

def build_fades(sample, key="xr"):
    """cell -> list of (event_idx, fade_value)"""
    cells = {}
    for w in WINDOWS:
        ra = RA[w.split("_")[0]]
        for b, fn in BINS.items():
            fv = []
            for i, r in enumerate(sample):
                v = r["win"][w][key]
                if v is None or r[ra] == 0 or not fn(r, ra):
                    continue
                fv.append((i, (-1.0 if r[ra] > 0 else 1.0) * v))
            cells[f"{w}|{b}"] = fv
    return cells

cells_xr = build_fades(dev, "xr")
# --- (a) compare vs their JSON ---
cmp_bad = []
for k, fv in cells_xr.items():
    theirs = THEIR["dev_cells"].get(k)
    n = len(fv)
    if theirs is None or n == 0:
        if theirs and theirs.get("n", 0) != n:
            cmp_bad.append((k, "n", n, theirs))
        continue
    m, sd, t = tstat([v for _, v in fv])
    if theirs["n"] != n or abs(theirs["mean"] - m) > 0.005 or abs(theirs.get("t", 0) - t) > 0.05:
        cmp_bad.append((k, "stats", {"n": n, "mean": round(m, 3), "t": round(t, 2)}, theirs))
print("\n(a) cell-by-cell recompute mismatches vs their JSON:", len(cmp_bad))
for x in cmp_bad[:10]: print("   ", x)

HL = "e22_open|abs_ge2"
hl_fv = cells_xr[HL]
hm, hsd, ht = tstat([v for _, v in hl_fv])
print(f"headline recompute: n={len(hl_fv)} mean={hm:.3f} t={ht:.2f} "
      f"win={sum(1 for _,v in hl_fv if v>0)}/{len(hl_fv)}")

# clean-basket sensitivity (exclude same-date afterhours reporters from β basket)
hl_clean = []
for i, r in enumerate(dev):
    v = r["win"]["e22_open"]["xr_clean"]
    if v is None or abs(r["react22"]) < 2: continue
    hl_clean.append((-1.0 if r["react22"] > 0 else 1.0) * v)
if hl_clean:
    cm, csd, ct = tstat(hl_clean)
    print(f"headline β-basket-clean: n={len(hl_clean)} mean={cm:.3f} t={ct:.2f}")

# raw (no β strip) headline
hl_raw = [(-1.0 if r["react22"] > 0 else 1.0) * r["win"]["e22_open"]["raw"]
          for r in dev if abs(r["react22"]) >= 2]
rm, rsd, rt = tstat(hl_raw)
print(f"headline raw(no β): n={len(hl_raw)} mean={rm:.3f} t={rt:.2f}")

# val
val_hl = [(-1.0 if r["react22"] > 0 else 1.0) * r["win"]["e22_open"]["xr"]
          for r in val if r["win"]["e22_open"]["xr"] is not None and abs(r["react22"]) >= 2]
if val_hl:
    vm, vsd, vt = tstat(val_hl)
    print(f"val headline: n={len(val_hl)} mean={vm:.3f}")

# ---------- (b) concentration ----------
hl_events = [(dev[i]["symbol"], dev[i]["date"], v) for i, v in hl_fv]
print("\n(b) headline events:", [(s, d, round(v, 2)) for s, d, v in hl_events])
# leave-one-event-out
loo = []
tot = sum(v for _, _, v in hl_events)
for s, d, v in hl_events:
    loo.append((s, round((tot - v) / (len(hl_events) - 1), 3)))
print("leave-one-EVENT-out means:", loo)
print("max LOO mean (worst case):", max(m for _, m in loo))
# LODO by date
per_date = defaultdict(list)
for s, d, v in hl_events: per_date[d].append(v)
lodo_means = {}
for d in per_date:
    rest = [v for d2, vs in per_date.items() if d2 != d for v in vs]
    lodo_means[d] = round(sum(rest) / len(rest), 3)
print("LODO(date) means:", lodo_means)
# drop the 04-29 mega-cluster AND 04-30 (5 events same week)
week_cluster = [v for s, d, v in hl_events if d not in ("2026-04-29", "2026-04-30")]
if week_cluster:
    wm, wsd, wt = tstat(week_cluster)
    print(f"drop 04-29+04-30 cluster: n={len(week_cluster)} mean={wm:.3f} t={wt:.2f}")

# ---------- (c) permutation (hand-written) ----------
# 保持每事件在所有cell的隶属关系与|fade|不变, 仅随机翻转每事件的sign
# (null: 反应方向与后续漂移方向无关)。统计: headline选择流程 = n>=8 cells中最大|t|。
# 两种翻转: 事件级独立 / 日期簇级(同日事件同一翻转, 处理截面相关)。
random.seed(20260706)
cell_members = {k: fv for k, fv in cells_xr.items() if len(fv) >= 8}   # selection pool n>=8
cell_members6 = {k: fv for k, fv in cells_xr.items() if len(fv) >= 6}
obs_t8 = max(abs(tstat([v for _, v in fv])[2]) for fv in cell_members.values())
obs_t6 = max(abs(tstat([v for _, v in fv])[2]) for fv in cell_members6.values())
dev_dates = sorted({r["date"] for r in dev})
date_of = {i: dev[i]["date"] for i in range(len(dev))}

def perm_pass(cluster_by_date, nperm=10000):
    cnt8 = cnt6 = 0
    dist8 = []
    for _ in range(nperm):
        if cluster_by_date:
            fl_d = {d: random.choice((-1, 1)) for d in dev_dates}
            flip = {i: fl_d[date_of[i]] for i in range(len(dev))}
        else:
            flip = {i: random.choice((-1, 1)) for i in range(len(dev))}
        mt8 = 0.0
        for fv in cell_members.values():
            _, _, t = tstat([flip[i] * v for i, v in fv])
            mt8 = max(mt8, abs(t))
        mt6 = mt8
        for k, fv in cell_members6.items():
            if k in cell_members: continue
            _, _, t = tstat([flip[i] * v for i, v in fv])
            mt6 = max(mt6, abs(t))
        if mt8 >= obs_t8: cnt8 += 1
        if mt6 >= obs_t6: cnt6 += 1
        dist8.append(mt8)
    dist8.sort()
    return cnt8 / nperm, cnt6 / nperm, dist8[int(0.5 * nperm)], dist8[int(0.95 * nperm)]

p8_ev, p6_ev, med_ev, q95_ev = perm_pass(False)
p8_dt, p6_dt, med_dt, q95_dt = perm_pass(True)
print(f"\n(c) observed max|t| (n>=8 pool) = {obs_t8:.2f}; (n>=6 pool) = {obs_t6:.2f}")
print(f"perm event-flip:  p(max|t|>=obs, n>=8 pool) = {p8_ev:.4f}  (n>=6: {p6_ev:.4f})  null med={med_ev:.2f} q95={q95_ev:.2f}")
print(f"perm date-flip:   p(max|t|>=obs, n>=8 pool) = {p8_dt:.4f}  (n>=6: {p6_dt:.4f})  null med={med_dt:.2f} q95={q95_dt:.2f}")

# ---------- (d) funding + liquidity ----------
fund_detail = []
for r in dev + val:
    if abs(r["react22"]) < 2: continue
    sym = r["symbol"] + "USDT"
    side = 1 if r["react22"] > 0 else -1   # continuation direction
    fr = con.execute("SELECT funding_time, funding_rate FROM funding WHERE symbol=? AND funding_time>? AND funding_time<=?",
                     (sym, r["t_entry"], r["t_exit"])).fetchall()
    if fr:
        # long pays positive funding: pnl_funding = -side * sum(rate)
        drag = -side * sum(x[1] for x in fr) * 100
        fund_detail.append({"symbol": r["symbol"], "date": r["date"], "n_fund": len(fr),
                            "sum_rate_pct": round(sum(x[1] for x in fr) * 100, 4),
                            "funding_pnl_pct": round(drag, 4)})
    else:
        cov = con.execute("SELECT COUNT(*) FROM funding WHERE symbol=?", (sym,)).fetchone()[0]
        fund_detail.append({"symbol": r["symbol"], "date": r["date"], "n_fund": 0,
                            "sym_fund_rows_total": cov})
print("\n(d) funding across hold window (headline events):")
for f in fund_detail: print("   ", f)
have = [f["funding_pnl_pct"] for f in fund_detail if "funding_pnl_pct" in f]
if have:
    print(f"   mean funding pnl (where data): {sum(have)/len(have):.4f}% over n={len(have)}")

# liquidity re-verify: 21:50-22:00 entry window
liq_entry = []
for r in dev + val:
    sym = r["symbol"] + "USDT"
    t2 = r["t_entry"]
    bars = con.execute("SELECT qv FROM klines_1m WHERE symbol=? AND ot>=? AND ot<?",
                       (sym, t2 - 10 * 60000, t2)).fetchall()
    if bars:
        liq_entry.append(sum(b[0] for b in bars) / len(bars))
liq_entry.sort()
print(f"entry 21:50-22:00 qv/min: median=${liq_entry[len(liq_entry)//2]:,.0f}  "
      f"min=${liq_entry[0]:,.0f}  (n={len(liq_entry)})")

# ---------- (e) drop audit ----------
listed = sum(1 for d in drop_audit if d.get("bars_on_date", 0) > 0)
print(f"\n(e) drops: {len(drop_audit)}; of which had bars on event date (perp WAS trading): {listed}")
for d in drop_audit:
    if d.get("bars_on_date", 0) > 0: print("   SUSPICIOUS DROP:", d)

out = {
    "recompute_mismatches": len(cmp_bad),
    "headline_recompute": {"n": len(hl_fv), "mean": round(hm, 3), "t": round(ht, 2)},
    "headline_raw": {"n": len(hl_raw), "mean": round(rm, 3), "t": round(rt, 2)},
    "headline_beta_clean": {"n": len(hl_clean), "mean": round(cm, 3), "t": round(ct, 2)} if hl_clean else None,
    "val_headline": {"n": len(val_hl), "mean": round(vm, 3)} if val_hl else None,
    "loo_event_means": loo, "lodo_date_means": lodo_means,
    "drop_apr_cluster": {"n": len(week_cluster), "mean": round(wm, 3), "t": round(wt, 2)},
    "permutation": {"obs_max_t_n8": round(obs_t8, 2), "obs_max_t_n6": round(obs_t6, 2),
                    "p_event_flip_n8": p8_ev, "p_event_flip_n6": p6_ev,
                    "p_date_flip_n8": p8_dt, "p_date_flip_n6": p6_dt,
                    "null_med_n8_event": round(med_ev, 2), "null_q95_n8_event": round(q95_ev, 2),
                    "null_med_n8_date": round(med_dt, 2), "null_q95_n8_date": round(q95_dt, 2)},
    "funding": fund_detail,
    "liquidity_entry_qv_per_min": {"median": liq_entry[len(liq_entry)//2], "min": liq_entry[0]},
    "report_time_dist": dict(report_time_counter), "session_mismatch": mismatch,
    "drop_audit_suspicious": [d for d in drop_audit if d.get("bars_on_date", 0) > 0],
}
json.dump(out, open(OUT, "w"), indent=1, ensure_ascii=False)
print("\nwrote", OUT)
