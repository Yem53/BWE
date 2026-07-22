#!/usr/bin/env python3
"""Round27 族B【周末效应】screen — 美股永续周末结构.

Part1: panel 周末gap(周五收→周一开) 分布 + fade/follow (TS + CS中性) cells
Part2: 1m 周末路径 — 周六/周日漂移, 周日晚(ET18:00)→周一开盘最后一段, 漂移分档→周一反应; sun18 进场 cells
Part3: 周末流动性现实 — bar覆盖率 / (h-l)/cl 点差代理 / 每bar成交额, 周末 vs RTH vs 平日隔夜
Part4: 资金费 — 周末持仓跨结算数量与 fund_overnight 分布; 所有跨结算持仓 cell 计入资金费

纪律: dev(≤05-31)选 → 冻结 → val(06-01~15)只验一次; CAP=1781654399000 之后数据一律不碰;
成本 taker 0.08%往返 + 点差2bp/边(qv_day<5e6 用5bp/边); 1.5×成本敏感性;
β剥离(TS cell 减同窗口全universe等权); LODO(单日/单名贡献>40%毙); n<100 标探索性.
资金费符号约定: funding_rate>0 = 多头付(Binance惯例), 多头资金费pnl = -sum(rate)*100 (%).
"""
import json
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np

DIR = "/Volumes/T9/BWE/40_EXPERIMENTS/round27_usstock_alpha"
OUT = DIR + "/alpha_screen/B"
CAP = 1781654399000          # 2026-06-15T23:59:59Z 铁律
DEV_END = "2026-05-31"
VAL_END = "2026-06-15"
ET = ZoneInfo("America/New_York")
RNG = np.random.default_rng(27)

# ---------- helpers ----------

def rankavg(x):
    x = np.asarray(x, float)
    order = np.argsort(x, kind="mergesort")
    sx = x[order]
    ranks = np.empty(len(x))
    i = 0
    while i < len(x):
        j = i
        while j + 1 < len(x) and sx[j + 1] == sx[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j + 2) / 2.0
        i = j + 1
    return ranks


def spearman(a, b, nperm=2000):
    a = np.asarray(a, float); b = np.asarray(b, float)
    m = np.isfinite(a) & np.isfinite(b)
    a, b = a[m], b[m]
    n = len(a)
    if n < 8:
        return None, None, n
    ra, rb = rankavg(a), rankavg(b)
    ra -= ra.mean(); rb -= rb.mean()
    d = np.sqrt((ra ** 2).sum() * (rb ** 2).sum())
    if d == 0:
        return None, None, n
    rho = float((ra * rb).sum() / d)
    # permutation p (two-sided)
    cnt = 0
    for _ in range(nperm):
        rp = RNG.permutation(rb)
        if abs(float((ra * rp).sum() / d)) >= abs(rho):
            cnt += 1
    return rho, (cnt + 1) / (nperm + 1), n


def et_ms(date_str, hh, mm=0):
    y, mo, dd = map(int, date_str.split("-"))
    return int(datetime(y, mo, dd, hh, mm, tzinfo=ET).timestamp() * 1000)


def dstat(v):
    v = np.asarray(v, float)
    v = v[np.isfinite(v)]
    if len(v) == 0:
        return {"n": 0}
    return {"n": int(len(v)), "mean": round(float(v.mean()), 4), "median": round(float(np.median(v)), 4),
            "std": round(float(v.std(ddof=1)), 4) if len(v) > 1 else None,
            "p10": round(float(np.percentile(v, 10)), 4), "p25": round(float(np.percentile(v, 25)), 4),
            "p75": round(float(np.percentile(v, 75)), 4), "p90": round(float(np.percentile(v, 90)), 4),
            "pos_frac": round(float(np.mean(v > 0)), 4)}


# ---------- load panel ----------
rows = [json.loads(l) for l in open(DIR + "/panel_devval.jsonl")]
assert all(r["date"] <= VAL_END for r in rows)
for r in rows:
    assert r["rth_close_ts"] <= CAP and r["rth_open_ts"] <= CAP

by_sym = defaultdict(list)
for r in rows:
    by_sym[r["symbol"]].append(r)
for s in by_sym:
    by_sym[s].sort(key=lambda x: x["date"])
    for i, r in enumerate(by_sym[s]):
        if i > 0 and r.get("prev_close"):
            prev = by_sym[s][i - 1]
            assert abs(prev["rth_close"] - r["prev_close"]) < 1e-9
            r["_prev_close_ts"] = prev["rth_close_ts"]
            r["_prev_date"] = prev["date"]

WINS = ["r_o30", "r_o60", "r_o120", "r_o_close"]
# universe EW per date per window (β剥离基准)
ew = defaultdict(dict)
by_date = defaultdict(list)
for r in rows:
    by_date[r["date"]].append(r)
for d, rs in by_date.items():
    for w in WINS + ["overnight_ret"]:
        v = [x[w] for x in rs if x.get(w) is not None]
        if v:
            ew[d][w] = float(np.mean(v))

wk_rows = [r for r in rows if r.get("is_weekend_gap") == 1]
wd_rows = [r for r in rows if r.get("is_weekend_gap") == 0]
dev_wk = [r for r in wk_rows if r["date"] <= DEV_END]
val_wk = [r for r in wk_rows if r["date"] > DEV_END]
dev_wd = [r for r in wd_rows if r["date"] <= DEV_END]

sample = {
    "panel_rows_total": len(rows),
    "weekend_gap_rows": {"dev": len(dev_wk), "val": len(val_wk)},
    "weekday_overnight_rows": {"dev": len(dev_wd), "val": len(wd_rows) - len(dev_wd)},
    "weekend_dates": {"dev": sorted(set(r["date"] for r in dev_wk)), "val": sorted(set(r["date"] for r in val_wk))},
    "symbols": {"dev_wk": len(set(r["symbol"] for r in dev_wk)), "val_wk": len(set(r["symbol"] for r in val_wk))},
    "wk_rows_by_month": dict(sorted(
        {m: sum(1 for r in wk_rows if r["date"][:7] == m) for m in set(r["date"][:7] for r in wk_rows)}.items())),
    "holiday_extended_gap_rows(gap_days>3)": sum(1 for r in wk_rows if r["gap_days"] > 3),
}
print("SAMPLE:", json.dumps(sample, ensure_ascii=False))

# ---------- cost model ----------

def cost_pct(qv_day):
    half = 0.02 if (qv_day or 0) >= 5e6 else 0.05
    return 0.08 + 2 * half   # taker往返 + 点差两边, %


# ---------- funding lookup ----------
db = sqlite3.connect("file:%s?mode=ro" % (DIR + "/tradfi_full.sqlite3"), uri=True)
fund = {}
for s in by_sym:
    fr = db.execute("SELECT funding_time, funding_rate FROM funding WHERE symbol=? AND funding_time<=? ORDER BY funding_time",
                    (s, CAP)).fetchall()
    fund[s] = (np.array([x[0] for x in fr], np.int64), np.array([x[1] for x in fr], float))


def fund_pnl(sym, t0, t1, pos):
    """pos=+1多/-1空; 返回 % pnl (多头付正费率)."""
    ft, fr = fund[sym]
    if len(ft) == 0:
        return 0.0
    m = (ft > t0) & (ft <= t1)
    return float(-pos * fr[m].sum() * 100)


# ---------- cell evaluation ----------
CELLS = {}   # cell_id -> dict


def eval_trades(trades):
    """trades: list of dict(date,symbol,pos,gross,strip_gross,cost,fpnl). Returns stats."""
    if not trades:
        return {"n": 0}
    net = np.array([t["pos"] * t["gross"] - t["cost"] + t["fpnl"] for t in trades])
    net15 = np.array([t["pos"] * t["gross"] - 1.5 * t["cost"] + t["fpnl"] for t in trades])
    strip = np.array([t["pos"] * t["strip_gross"] - t["cost"] + t["fpnl"] for t in trades])
    n = len(net)
    se = net.std(ddof=1) / np.sqrt(n) if n > 1 else np.nan
    tot = float(net.sum())
    # LODO 贡献: 单日 / 单名 最大正贡献占比
    def max_share(key):
        agg = defaultdict(float)
        for t, x in zip(trades, net):
            agg[t[key]] += x
        if tot <= 0:
            return None, None
        best_k, best_v = max(agg.items(), key=lambda kv: kv[1])
        rest = tot - best_v
        return round(best_v / tot, 3), (best_k, round(rest, 2))
    ds, drop_d = max_share("date")
    ss, drop_s = max_share("symbol")
    return {
        "n": n, "mean_net": round(float(net.mean()), 4), "median_net": round(float(np.median(net)), 4),
        "sum_net": round(tot, 2), "t": round(float(net.mean() / se), 2) if se and se > 0 else None,
        "win": round(float(np.mean(net > 0)), 3),
        "mean_net_cost1.5x": round(float(net15.mean()), 4),
        "mean_net_beta_stripped": round(float(strip.mean()), 4),
        "max_date_share": ds, "drop_best_date_rest_sum": drop_d,
        "max_sym_share": ss, "drop_best_sym_rest_sum": drop_s,
        "n_dates": len(set(t["date"] for t in trades)),
        "exploratory": n < 100,
    }


def dev_pass(st, directional):
    if st["n"] < 30 or st.get("t") is None:
        return False
    if not (st["mean_net"] > 0 and st["t"] >= 1.5 and st["mean_net_cost1.5x"] > 0):
        return False
    if directional and st["mean_net_beta_stripped"] <= 0:
        return False
    if st["max_date_share"] is None or st["max_date_share"] > 0.4 or st["max_sym_share"] > 0.4:
        return False
    if st["drop_best_date_rest_sum"] and st["drop_best_date_rest_sum"][1] <= 0:
        return False
    return True


# ============ PART 1: panel gap 分布 + fade/follow ============
P1 = {}
P1["gap_dist_weekend_dev"] = dstat([r["overnight_ret"] for r in dev_wk])
P1["gap_dist_weekday_dev"] = dstat([r["overnight_ret"] for r in dev_wd])
P1["abs_gap_weekend_dev"] = dstat([abs(r["overnight_ret"]) for r in dev_wk])
P1["abs_gap_weekday_dev"] = dstat([abs(r["overnight_ret"]) for r in dev_wd])
# gap → 开盘窗反应 spearman (dev)
P1["spearman_gap_vs_reaction_dev"] = {}
for grp, rs in (("weekend", dev_wk), ("weekday", dev_wd)):
    for w in WINS:
        pairs = [(r["overnight_ret"], r[w]) for r in rs if r.get(w) is not None]
        rho, p, n = spearman([a for a, _ in pairs], [b for _, b in pairs])
        P1["spearman_gap_vs_reaction_dev"]["%s_%s" % (grp, w)] = {"rho": round(rho, 3) if rho else None, "p": round(p, 4) if p else None, "n": n}
# CS版: gap的当日截面demean后与反应截面demean的相关 (dev weekend, 按日demean再pool)
def cs_demean_pairs(rs, w):
    byd = defaultdict(list)
    for r in rs:
        if r.get(w) is not None and r.get("overnight_ret") is not None:
            byd[r["date"]].append(r)
    A, B = [], []
    for d, lst in byd.items():
        if len(lst) < 6:
            continue
        g = np.array([x["overnight_ret"] for x in lst]); v = np.array([x[w] for x in lst])
        A += list(g - g.mean()); B += list(v - v.mean())
    return A, B
P1["spearman_gap_vs_reaction_CSdemean_dev"] = {}
for w in WINS:
    A, B = cs_demean_pairs(dev_wk, w)
    rho, p, n = spearman(A, B)
    P1["spearman_gap_vs_reaction_CSdemean_dev"][w] = {"rho": round(rho, 3) if rho else None, "p": round(p, 4) if p else None, "n": n}

EXIT_TS = {"r_o30": lambda r: r["rth_open_ts"] + 30 * 60000, "r_o60": lambda r: r["rth_open_ts"] + 60 * 60000,
           "r_o120": lambda r: r["rth_open_ts"] + 120 * 60000, "r_o_close": lambda r: r["rth_close_ts"]}


def p1_ts_trades(rs, win, direction, thr, side=None):
    out = []
    for r in rs:
        g = r.get("overnight_ret"); v = r.get(win)
        if g is None or v is None or abs(g) < thr or ew[r["date"]].get(win) is None:
            continue
        pos = -np.sign(g) if direction == "fade" else np.sign(g)
        if pos == 0:
            continue
        if side == "up_short" and g <= 0:
            continue
        if side == "down_long" and g >= 0:
            continue
        out.append({"date": r["date"], "symbol": r["symbol"], "pos": float(pos), "gross": v,
                    "strip_gross": v - ew[r["date"]][win], "cost": cost_pct(r.get("qv_day")),
                    "fpnl": fund_pnl(r["symbol"], r["rth_open_ts"], EXIT_TS[win](r), float(pos))})
    return out


def p1_cs_trades(rs, win, direction, kfrac, minN):
    out = []
    byd = defaultdict(list)
    for r in rs:
        if r.get("overnight_ret") is not None and r.get(win) is not None:
            byd[r["date"]].append(r)
    for d, lst in sorted(byd.items()):
        if len(lst) < minN:
            continue
        lst.sort(key=lambda x: x["overnight_ret"])
        k = max(1, int(len(lst) * kfrac))
        lo, hi = lst[:k], lst[-k:]
        for r, pos0 in [(x, 1.0) for x in lo] + [(x, -1.0) for x in hi]:
            pos = pos0 if direction == "fade" else -pos0
            out.append({"date": d, "symbol": r["symbol"], "pos": pos, "gross": r[win],
                        "strip_gross": r[win] - ew[d][win], "cost": cost_pct(r.get("qv_day")),
                        "fpnl": fund_pnl(r["symbol"], r["rth_open_ts"], EXIT_TS[win](r), pos)})
    return out


for thr in (0.0, 1.0, 2.0):
    for direction in ("fade", "follow"):
        for win in WINS:
            cid = "P1TS_%s_thr%g_%s" % (direction, thr, win)
            CELLS[cid] = {"kind": "TS", "make": (lambda rs, w=win, d=direction, t=thr: p1_ts_trades(rs, w, d, t))}
for side in ("up_short", "down_long"):
    for win in WINS:
        cid = "P1TS_fade_%s_%s" % (side, win)
        CELLS[cid] = {"kind": "TS", "make": (lambda rs, w=win, s=side: p1_ts_trades(rs, w, "fade", 0.0, side=s))}
for scheme, kfrac, minN in (("terc", 1 / 3, 6), ("quint", 1 / 5, 15)):
    for direction in ("fade", "follow"):
        for win in WINS:
            cid = "P1CS_%s_%s_%s" % (scheme, direction, win)
            CELLS[cid] = {"kind": "CS", "make": (lambda rs, w=win, d=direction, kf=kfrac, mn=minN: p1_cs_trades(rs, w, d, kf, mn))}

# ============ PART 2: 1m 周末路径 ============
# anchors: fri_close(面板), sat12, sun12, sun18(ET), mon_open(面板)
paths = []      # 每 (symbol, weekend) 一条
liq = {"weekend": defaultdict(list), "rth": defaultdict(list), "wd_overnight": defaultdict(list)}
cover = defaultdict(list)
DST_MS = int(datetime(2026, 3, 8, 7, 0, tzinfo=timezone.utc).timestamp() * 1000)
DEV_CUT_MS = et_ms("2026-06-01", 0)   # part3 流动性只用 dev 期 bars

for si, (sym, srows) in enumerate(sorted(by_sym.items())):
    kr = db.execute("SELECT ot,h,l,cl,v,qv FROM klines_1m WHERE symbol=? AND ot<=? ORDER BY ot", (sym, CAP)).fetchall()
    if not kr:
        continue
    ot = np.array([x[0] for x in kr], np.int64)
    h = np.array([x[1] for x in kr]); l = np.array([x[2] for x in kr]); cl = np.array([x[3] for x in kr])
    v = np.array([x[4] for x in kr]); qv = np.array([x[5] for x in kr])
    med_qvday = float(np.median([r["qv_day"] for r in srows]))
    tier = "big" if med_qvday >= 5e6 else "small"
    # --- part3 分类 (dev 期) ---
    m3 = ot < DEV_CUT_MS
    if m3.any():
        o3 = ot[m3]
        off = np.where(o3 >= DST_MS, 4, 5).astype(np.int64)
        ems = o3 - off * 3600000
        eday = ems // 86400000
        emin = (ems % 86400000) // 60000
        dow = (eday + 3) % 7          # 1970-01-01=周四 → +3 使 0=周一
        # sanity: 2026-06-13 是周六
        assert (int((et_ms("2026-06-13", 12) - 4 * 3600000) // 86400000) + 3) % 7 == 5
        wkend = (dow == 5) | (dow == 6)
        rth = (~wkend) & (emin >= 570) & (emin < 960)
        wdov = (~wkend) & (~rth)
        rel = (h[m3] - l[m3]) / np.where(cl[m3] > 0, cl[m3], np.nan) * 1e4   # bp
        for name, msk in (("weekend", wkend), ("rth", rth), ("wd_overnight", wdov)):
            if msk.sum() > 50:
                liq[name][tier].append({"sym": sym, "med_hl_bp": float(np.nanmedian(rel[msk])),
                                        "med_qv_bar": float(np.median(qv[m3][msk])),
                                        "zero_vol_frac": float(np.mean(v[m3][msk] == 0))})
        # 周末覆盖率: 周末分钟里有bar的比例 (dev期总周末分钟 ≈ 周末数×2880)
        n_wkend_days = len(np.unique(eday[wkend]))
        if n_wkend_days:
            cover[tier].append({"sym": sym, "cover": float(wkend.sum() / (n_wkend_days * 1440.0))})

    # --- part2 路径 anchors ---
    def px_at(ts, tol_min=45):
        j = int(np.searchsorted(ot, ts + 1)) - 1
        if j < 0 or ts - ot[j] > tol_min * 60000:
            return None
        return float(cl[j])

    for r in srows:
        if r.get("is_weekend_gap") != 1 or r.get("_prev_close_ts") is None or r["gap_days"] != 3:
            continue
        fri_d = r["_prev_date"]
        f = datetime.strptime(fri_d, "%Y-%m-%d")
        sat = (f + timedelta(days=1)).strftime("%Y-%m-%d")
        sun = (f + timedelta(days=2)).strftime("%Y-%m-%d")
        a = {"sat12": px_at(et_ms(sat, 12)), "sun12": px_at(et_ms(sun, 12)), "sun18": px_at(et_ms(sun, 18))}
        fri_px = r["prev_close"]
        rec = {"symbol": sym, "date": r["date"], "fri_px": fri_px, "qv_day": r["qv_day"], "tier": tier,
               "mon_open": r["rth_open"], "mon_open_ts": r["rth_open_ts"], "mon_close_ts": r["rth_close_ts"],
               "px_o60": r.get("px_o60"), "mon_close": r["rth_close"], "sun18_ts": et_ms(sun, 18)}
        for k, p in a.items():
            rec[k] = p
        if a["sun18"]:
            rec["drift_fs18"] = (a["sun18"] - fri_px) / fri_px * 100
            rec["leg_s18_open"] = (r["rth_open"] - a["sun18"]) / a["sun18"] * 100
            if r.get("px_o60"):
                rec["leg_s18_o60"] = (r["px_o60"] - a["sun18"]) / a["sun18"] * 100
            rec["leg_s18_close"] = (r["rth_close"] - a["sun18"]) / a["sun18"] * 100
        if a["sat12"]:
            rec["drift_f_sat12"] = (a["sat12"] - fri_px) / fri_px * 100
        if a["sat12"] and a["sun12"]:
            rec["drift_sat12_sun12"] = (a["sun12"] - a["sat12"]) / a["sat12"] * 100
        if a["sun12"] and a["sun18"]:
            rec["drift_sun12_18"] = (a["sun18"] - a["sun12"]) / a["sun12"] * 100
        paths.append(rec)

dev_paths = [p for p in paths if p["date"] <= DEV_END and p.get("drift_fs18") is not None]
val_paths = [p for p in paths if p["date"] > DEV_END and p.get("drift_fs18") is not None]
P2 = {"n_paths_dev": len(dev_paths), "n_paths_val": len(val_paths),
      "anchor_coverage": round(np.mean([p.get("sun18") is not None for p in paths]), 3) if paths else None}
for seg in ("drift_f_sat12", "drift_sat12_sun12", "drift_sun12_18", "drift_fs18", "leg_s18_open"):
    P2["seg_%s_dev" % seg] = dstat([p.get(seg) for p in dev_paths if p.get(seg) is not None])
# 连续/回归: drift_fs18 → 最后一段 & 周一窗
P2["spearman_dev"] = {}
for tgt in ("leg_s18_open", "leg_s18_close"):
    pairs = [(p["drift_fs18"], p[tgt]) for p in dev_paths if p.get(tgt) is not None]
    rho, pv, n = spearman([a for a, _ in pairs], [b for _, b in pairs])
    P2["spearman_dev"]["drift_fs18_vs_%s" % tgt] = {"rho": round(rho, 3) if rho else None, "p": round(pv, 4) if pv else None, "n": n}
# 分档: drift_fs18 bins → leg_s18_open / 周一 r_o_close(即 leg 与面板反应)
bins = [(-99, -2), (-2, -0.5), (-0.5, 0.5), (0.5, 2), (2, 99)]
P2["bins_drift_fs18_to_lastleg_dev"] = []
for lo, hi in bins:
    sel = [p for p in dev_paths if lo <= p["drift_fs18"] < hi]
    P2["bins_drift_fs18_to_lastleg_dev"].append({
        "bin": "[%g,%g)" % (lo, hi), "n": len(sel),
        "mean_leg_s18_open": round(float(np.mean([p["leg_s18_open"] for p in sel])), 3) if sel else None,
        "mean_leg_s18_close": round(float(np.mean([p["leg_s18_close"] for p in sel if p.get("leg_s18_close") is not None])), 3) if sel else None})

# P2 EW (β剥离基准, 按周末日期)
ew2 = defaultdict(dict)
byd2 = defaultdict(list)
for p in paths:
    if p.get("drift_fs18") is not None:
        byd2[p["date"]].append(p)
for d, lst in byd2.items():
    for w in ("leg_s18_open", "leg_s18_o60", "leg_s18_close"):
        vv = [x[w] for x in lst if x.get(w) is not None]
        if vv:
            ew2[d][w] = float(np.mean(vv))

P2_EXIT = {"leg_s18_open": lambda p: p["mon_open_ts"], "leg_s18_o60": lambda p: p["mon_open_ts"] + 60 * 60000,
           "leg_s18_close": lambda p: p["mon_close_ts"]}


def p2_ts_trades(ps, exit_w, direction, thr):
    out = []
    for p in ps:
        g = p.get("drift_fs18"); vv = p.get(exit_w)
        if g is None or vv is None or abs(g) < thr or ew2[p["date"]].get(exit_w) is None:
            continue
        pos = -np.sign(g) if direction == "fade" else np.sign(g)
        if pos == 0:
            continue
        out.append({"date": p["date"], "symbol": p["symbol"], "pos": float(pos), "gross": vv,
                    "strip_gross": vv - ew2[p["date"]][exit_w], "cost": cost_pct(p["qv_day"]),
                    "fpnl": fund_pnl(p["symbol"], p["sun18_ts"], P2_EXIT[exit_w](p), float(pos))})
    return out


def p2_cs_trades(ps, exit_w, direction, minN=6):
    out = []
    byd = defaultdict(list)
    for p in ps:
        if p.get("drift_fs18") is not None and p.get(exit_w) is not None:
            byd[p["date"]].append(p)
    for d, lst in sorted(byd.items()):
        if len(lst) < minN:
            continue
        lst.sort(key=lambda x: x["drift_fs18"])
        k = max(1, len(lst) // 3)
        for p, pos0 in [(x, 1.0) for x in lst[:k]] + [(x, -1.0) for x in lst[-k:]]:
            pos = pos0 if direction == "fade" else -pos0
            out.append({"date": d, "symbol": p["symbol"], "pos": pos, "gross": p[exit_w],
                        "strip_gross": p[exit_w] - ew2[d][exit_w], "cost": cost_pct(p["qv_day"]),
                        "fpnl": fund_pnl(p["symbol"], p["sun18_ts"], P2_EXIT[exit_w](p), pos)})
    return out


for thr in (0.0, 1.0):
    for direction in ("fade", "follow"):
        for exit_w in ("leg_s18_open", "leg_s18_o60", "leg_s18_close"):
            cid = "P2TS_%s_thr%g_%s" % (direction, thr, exit_w)
            CELLS[cid] = {"kind": "TS", "p2": True, "make": (lambda ps, w=exit_w, d=direction, t=thr: p2_ts_trades(ps, w, d, t))}
for direction in ("fade", "follow"):
    for exit_w in ("leg_s18_open", "leg_s18_close"):
        cid = "P2CS_terc_%s_%s" % (direction, exit_w)
        CELLS[cid] = {"kind": "CS", "p2": True, "make": (lambda ps, w=exit_w, d=direction: p2_cs_trades(ps, w, d))}

# ============ PART 3 aggregate ============
P3 = {}
for name in liq:
    for tier in liq[name]:
        lst = liq[name][tier]
        if lst:
            P3["%s_%s" % (name, tier)] = {
                "n_syms": len(lst),
                "med_hl_range_bp": round(float(np.median([x["med_hl_bp"] for x in lst])), 1),
                "med_qv_per_bar_usd": round(float(np.median([x["med_qv_bar"] for x in lst])), 0),
                "zero_vol_frac": round(float(np.median([x["zero_vol_frac"] for x in lst])), 3)}
for tier in cover:
    P3["weekend_bar_coverage_%s" % tier] = round(float(np.median([x["cover"] for x in cover[tier]])), 3)

# ============ PART 4 funding ============
P4 = {}
P4["fund_overnight_weekend_dev"] = dstat([r["fund_overnight"] for r in dev_wk if r.get("fund_overnight") is not None])
P4["fund_overnight_weekday_dev"] = dstat([r["fund_overnight"] for r in dev_wd if r.get("fund_overnight") is not None])
nx = []
for r in dev_wk:
    if r.get("_prev_close_ts"):
        ft, _ = fund[r["symbol"]]
        nx.append(int(((ft > r["_prev_close_ts"]) & (ft <= r["rth_open_ts"])).sum()))
P4["n_settlements_crossed_weekend_dev"] = dstat(nx)
P4["funding_table_symbols_covered"] = sum(1 for s in fund if len(fund[s][0]) > 0)
P4["note"] = "funding表覆盖不全(45/105 symbols有记录), 缺失按0计 — cell资金费或低估"

# ============ dev screen → freeze → val ============
results = {}
survivors = []
for cid, spec in CELLS.items():
    src_dev = dev_paths if spec.get("p2") else dev_wk
    st = eval_trades(spec["make"](src_dev))
    results[cid] = {"dev": st}
    if st.get("n", 0) and dev_pass(st, directional=(spec["kind"] == "TS")):
        survivors.append(cid)

print("n_cells=%d, dev survivors=%d: %s" % (len(CELLS), len(survivors), survivors))
for cid in survivors:
    spec = CELLS[cid]
    src_val = val_paths if spec.get("p2") else val_wk
    results[cid]["val"] = eval_trades(spec["make"](src_val))

# top dev cells by t (for report)
ranked = sorted([c for c in results if results[c]["dev"].get("t") is not None],
                key=lambda c: -results[c]["dev"]["t"])

out = {"config": {"cap_ms": CAP, "dev_end": DEV_END, "val_end": VAL_END,
                  "cost": "taker0.08%RT + 2bp/边(qv_day<5e6→5bp/边); 敏感性1.5×",
                  "funding_sign": "rate>0多头付; 多头fpnl=-sum(rate)*100",
                  "n_cells": len(CELLS)},
       "sample": sample, "P1": P1, "P2": P2, "P3": P3, "P4": P4,
       "cells": results, "survivors": survivors,
       "top10_dev_by_t": [{"cell": c, **results[c]["dev"]} for c in ranked[:10]]}
with open(OUT + "/b_weekend_results.json", "w") as f:
    json.dump(out, f, ensure_ascii=False, indent=1, default=str)
print("WROTE", OUT + "/b_weekend_results.json")
