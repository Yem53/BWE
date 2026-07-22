#!/usr/bin/env python3
"""Round27 族C 对抗验证 — 独立复算, 默认族C发现是假alpha, 逐项攻击.

攻击面:
(a) beta/动量伪装 — 独立复算 beta 剥离; 另用非事件日估计真实 beta_hat 做 beta-scaled 剥离
    (等权 universe 波动远大于 QQQ, beta=1 剥离可能过度剥离 → 检查 no-survivor 结论是否被过度剥离制造)
(b) LODO 单日集中 — 独立复跑留一日; 单名: instrument 本身就是单名 QQQ, 如实报
(c) 重叠持有期 — 检查每个 cell 的事件日期是否重复 / 持有窗是否跨日重叠
(d) 成本 1.5x 加压 — 独立复算 (含 qv_day 档位核查)
(e) 上市日期偏差 — 早期截面仅 8 只; 用 listing-matched universe 复算 CPI 等权倍数;
    检查候选 cell 是否全部落在 QQQ 时代 (04-06+)
(f) 时区/DST — zoneinfo America/New_York 独立换算 vs 手工规则; 经验验证:
    事件 t0 附近逐分钟 |r| 尖峰是否正好落在 t0, 错位假设 (t0±60min) 是否更强

铁律: ot <= 1781654399000; dev <= 2026-05-31; 手写统计 (无 scipy).
"""
import json
import sqlite3
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import numpy as np

ROOT = "/Volumes/T9/BWE/40_EXPERIMENTS/round27_usstock_alpha"
DB = ROOT + "/tradfi_full.sqlite3"
PANEL = ROOT + "/panel_devval.jsonl"
OUT = ROOT + "/alpha_screen/C_verify/c_verify_results.json"
HARD_CAP_MS = 1781654399000
MIN = 60_000
DEV_END = "2026-05-31"
NY = ZoneInfo("America/New_York")

EVENTS = {
    "CPI": ["2026-02-13", "2026-03-11", "2026-04-10", "2026-05-12", "2026-06-10"],
    "NFP": ["2026-02-11", "2026-03-06", "2026-04-03", "2026-05-08", "2026-06-05"],
    "PCE": ["2026-02-20", "2026-03-13", "2026-04-09", "2026-04-30", "2026-05-28"],
    "FOMC": ["2026-01-28", "2026-03-18", "2026-04-29"],
}

conn = sqlite3.connect(DB)
out: dict = {"family": "C_verify", "generated": datetime.now(timezone.utc).isoformat(),
             "hard_cap_ms": HARD_CAP_MS, "attacks": {}}

# ---------------- (f) 时区/DST: 独立换算 ----------------
def t0_zoneinfo(datestr: str, typ: str) -> int:
    h, mi = (14, 0) if typ == "FOMC" else (8, 30)
    dt = datetime(int(datestr[:4]), int(datestr[5:7]), int(datestr[8:10]), h, mi, tzinfo=NY)
    return int(dt.timestamp() * 1000)

def t0_manual(datestr: str, typ: str) -> int:  # 被审脚本的规则
    h, mi = (14, 0) if typ == "FOMC" else (8, 30)
    off = 5 if (int(datestr[5:7]), int(datestr[8:10])) < (3, 8) else 4
    return int(datetime(int(datestr[:4]), int(datestr[5:7]), int(datestr[8:10]),
                        h + off, mi, tzinfo=timezone.utc).timestamp() * 1000)

tz_check = []
for typ, dates in EVENTS.items():
    for ds in dates:
        a, b = t0_zoneinfo(ds, typ), t0_manual(ds, typ)
        tz_check.append({"type": typ, "date": ds, "zoneinfo_ms": a, "manual_ms": b,
                         "match": a == b,
                         "utc": datetime.fromtimestamp(a / 1000, tz=timezone.utc).strftime("%H:%M")})
out["attacks"]["f_tz_conversion"] = {
    "all_match": all(r["match"] for r in tz_check), "rows": tz_check}

# ---------------- 数据访问 (独立实现: close-of-prev-bar 价格约定) ----------------
def bars_window(t_lo: int, t_hi: int) -> dict:
    t_hi = min(t_hi, HARD_CAP_MS)
    d: dict = {}
    for sym, ot, o, cl in conn.execute(
            "SELECT symbol, ot, o, cl FROM klines_1m WHERE ot>=? AND ot<=?", (t_lo, t_hi)):
        d.setdefault(sym, {})[ot] = (float(o), float(cl))
    return d

def px(bs: dict, t: int, lb: int = 15):
    """独立约定: t 时刻价 = t-1min bar 的 close (即 t 之前最后成交), 回退 lb 分钟."""
    if bs is None:
        return None
    for k in range(1, lb + 1):
        b = bs.get(t - k * MIN)
        if b is not None:
            return b[1]
    b = bs.get(t)  # 最后回退: 该分钟 open
    return b[0] if b else None

# ---------------- (f) 经验尖峰对齐: 每分钟 |r| profile ----------------
spike_rows = []
for typ, dates in EVENTS.items():
    for ds in dates:
        t0 = t0_zoneinfo(ds, typ)
        if t0 + 125 * MIN > HARD_CAP_MS:
            continue
        bars = bars_window(t0 - 95 * MIN, t0 + 95 * MIN)
        if not bars:
            spike_rows.append({"type": typ, "date": ds, "n_sym": 0})
            continue
        # 等权逐分钟 |r|: offset -90..+90
        prof = {}
        for off in range(-90, 91):
            t = t0 + off * MIN
            rs = []
            for bs in bars.values():
                b = bs.get(t)
                if b and b[0] > 0:
                    rs.append(abs(b[1] / b[0] - 1) * 100)
            if rs:
                prof[off] = float(np.mean(rs))
        if not prof:
            spike_rows.append({"type": typ, "date": ds, "n_sym": len(bars)})
            continue
        peak_off = max(prof, key=prof.get)
        near = float(np.mean([prof.get(o, 0) for o in range(0, 5)]))      # [t0, t0+5)
        m60 = float(np.mean([prof.get(o, 0) for o in range(-60, -55)]))   # 错 DST -1h
        p60 = float(np.mean([prof.get(o, 0) for o in range(60, 65)]))     # 错 DST +1h
        far = [v for o, v in prof.items() if abs(o) > 15]
        spike_rows.append({
            "type": typ, "date": ds, "n_sym": len(bars),
            "peak_offset_min": peak_off, "peak_val": round(prof[peak_off], 4),
            "mean_abs_r_t0_5": round(near, 4),
            "mean_abs_r_minus60": round(m60, 4), "mean_abs_r_plus60": round(p60, 4),
            "bg_mean_abs_r": round(float(np.mean(far)), 4) if far else None,
            "t0_wins_vs_pm60": near > m60 and near > p60})
ok = [r for r in spike_rows if r.get("peak_offset_min") is not None]
out["attacks"]["f_empirical_spike"] = {
    "n_events_with_data": len(ok),
    "n_peak_in_0_to_5": sum(1 for r in ok if 0 <= r["peak_offset_min"] <= 5),
    "n_t0_beats_pm60": sum(1 for r in ok if r["t0_wins_vs_pm60"]),
    "rows": spike_rows}

# ---------------- panel ----------------
panel: dict = {}
dates_all: set = set()
for line in open(PANEL):
    d = json.loads(line)
    panel[(d["symbol"], d["date"])] = d
    dates_all.add(d["date"])

def cost_pct(sym: str, ds: str) -> float:
    row = panel.get((sym, ds))
    sp = 2.0 if (row and row.get("qv_day", 0) >= 5e6) else 5.0
    return 0.08 + 2 * sp / 100.0

# ---------------- 事件收益 (独立价格约定) ----------------
ev = []
for typ, dates in EVENTS.items():
    for ds in dates:
        t0 = t0_zoneinfo(ds, typ)
        if t0 + 125 * MIN > HARD_CAP_MS:
            continue
        bars = bars_window(t0 - 80 * MIN, t0 + 125 * MIN)
        per = {}
        for sym, bs in bars.items():
            a = {o: px(bs, t0 + o * MIN) for o in (0, 5, 120)}
            if any(v is None for v in a.values()):
                continue
            per[sym] = {"r0_5": (a[5] / a[0] - 1) * 100,
                        "r5_120": (a[120] / a[5] - 1) * 100}
        if not per:
            continue
        ew = {k: float(np.mean([v[k] for v in per.values()])) for k in ("r0_5", "r5_120")}
        ew_ex = None
        if "QQQUSDT" in per and len(per) > 1:
            ew_ex = {k: float(np.mean([v[k] for s, v in per.items() if s != "QQQUSDT"]))
                     for k in ("r0_5", "r5_120")}
        ev.append({"type": typ, "date": ds, "split": "dev" if ds <= DEV_END else "val",
                   "t0": t0, "n_sym": len(per), "per": per, "EW": ew, "EW_exQQQ": ew_ex})

# ---------------- beta_hat 估计 (非事件日, 同 clock 窗, QQQ vs EW) ----------------
event_dates = {d for v in EVENTS.values() for d in v}
base_days = sorted(d for d in dates_all if d <= DEV_END and d not in event_dates
                   and ("QQQUSDT", d) in panel)
bx, by, b5x, b5y = [], [], [], []
base_prof_qqq, base_prof_ew = [], []
for ds in base_days:
    t0 = t0_zoneinfo(ds, "CPI")
    if t0 + 125 * MIN > HARD_CAP_MS:
        continue
    bars = bars_window(t0 - 20 * MIN, t0 + 125 * MIN)
    rets, rets5 = {}, {}
    for sym, bs in bars.items():
        p5, p120, p0 = px(bs, t0 + 5 * MIN), px(bs, t0 + 120 * MIN), px(bs, t0)
        if p5 and p120:
            rets[sym] = (p120 / p5 - 1) * 100
        if p0 and p5:
            rets5[sym] = (p5 / p0 - 1) * 100
    if "QQQUSDT" in rets and len(rets) > 5:
        mkt = float(np.mean([v for s, v in rets.items() if s != "QQQUSDT"]))
        bx.append(mkt); by.append(rets["QQQUSDT"])
    if "QQQUSDT" in rets5 and len(rets5) > 5:
        mkt5 = float(np.mean([v for s, v in rets5.items() if s != "QQQUSDT"]))
        b5x.append(mkt5); b5y.append(rets5["QQQUSDT"])
        base_prof_qqq.append(abs(rets5["QQQUSDT"]))
        base_prof_ew.append(abs(float(np.mean(list(rets5.values())))))
bx, by = np.array(bx), np.array(by)
beta_hat = float(np.cov(bx, by, ddof=1)[0, 1] / np.var(bx, ddof=1)) if len(bx) > 3 else None
b5x, b5y = np.array(b5x), np.array(b5y)
beta_hat5 = float(np.cov(b5x, b5y, ddof=1)[0, 1] / np.var(b5x, ddof=1)) if len(b5x) > 3 else None
corr = float(np.corrcoef(bx, by)[0, 1]) if len(bx) > 3 else None
out["attacks"]["a_beta_hat"] = {
    "n_baseline_days": len(bx), "window": "t0+5 -> t0+120 clock-matched 8:30ET",
    "beta_hat_qqq_vs_ew_exqqq_5to120": round(beta_hat, 3) if beta_hat else None,
    "corr": round(corr, 3) if corr else None,
    "beta_hat_r0_5": round(beta_hat5, 3) if beta_hat5 else None,
    "note": "beta<1 → 被审的 beta=1 全额剥离是过度剥离(对候选更严); beta>1 → 剥离不足"}

# ---------------- 候选 cell 独立复算 ----------------
def eval_cell(rows, direction_fn, label):
    res = {"rule": label}
    for split in ("dev", "val"):
        recs = []
        for r in rows:
            if r["split"] != split or "QQQUSDT" not in r["per"]:
                continue
            d = direction_fn(r)
            if not d:
                continue
            c = cost_pct("QQQUSDT", r["date"])
            g = d * r["per"]["QQQUSDT"]["r5_120"]
            strip1 = d * (r["per"]["QQQUSDT"]["r5_120"] - r["EW"]["r5_120"]) - c
            sb = None
            if beta_hat is not None and r["EW_exQQQ"]:
                sb = d * (r["per"]["QQQUSDT"]["r5_120"]
                          - beta_hat * r["EW_exQQQ"]["r5_120"]) - c
            recs.append({"date": r["date"], "net": g - c, "net15": g - 1.5 * c,
                         "strip_beta1": strip1, "strip_betahat": sb, "cost": c})
        if not recs:
            res[split] = {"n": 0}
            continue
        nets = np.array([x["net"] for x in recs])
        tot = float(nets.sum())
        lodo = None
        if tot > 0 and len(nets) > 1:
            lodo = round(float(max(nets) / tot), 3)
        res[split] = {
            "n": len(recs),
            "mean_net": round(float(nets.mean()), 4),
            "mean_net_1p5x": round(float(np.mean([x["net15"] for x in recs])), 4),
            "mean_strip_beta1": round(float(np.mean([x["strip_beta1"] for x in recs])), 4),
            "mean_strip_betahat": round(float(np.mean(
                [x["strip_betahat"] for x in recs if x["strip_betahat"] is not None])), 4)
            if any(x["strip_betahat"] is not None for x in recs) else None,
            "lodo_max_share": lodo if lodo is not None else (1.0 if len(recs) == 1 else None),
            "per_event": {x["date"]: {"net": round(x["net"], 4),
                                      "strip_beta1": round(x["strip_beta1"], 4),
                                      "strip_betahat": round(x["strip_betahat"], 4)
                                      if x["strip_betahat"] is not None else None,
                                      "cost": x["cost"]} for x in recs}}
    return res

def momo(r):
    s = np.sign(r["per"]["QQQUSDT"]["r0_5"])
    return int(s) if s else None

def fade(r):
    s = momo(r)
    return -s if s else None

cells = []
for typ, fn, nm in [("NFP", momo, "NFP_momo_5to120"), ("PCE", momo, "PCE_momo_5to120"),
                    ("CPI", fade, "CPI_fade_5to120"), ("FOMC", fade, "FOMC_fade_5to120")]:
    cells.append(eval_cell([r for r in ev if r["type"] == typ], fn, nm))
cells.append(eval_cell([r for r in ev if r["type"] != "FOMC"], momo, "ALL830_momo_5to120"))

# print→open (PCE_print2open_r_o120): sign(8:30→9:28) → panel r_o120
p2o = {"rule": "PCE_print2open_r_o120"}
for split in ("dev", "val"):
    recs = []
    for r in ev:
        if r["type"] != "PCE" or r["split"] != split:
            continue
        bs = bars_window(r["t0"] - 20 * MIN, r["t0"] + 60 * MIN).get("QQQUSDT")
        p0, p928 = px(bs, r["t0"]), px(bs, r["t0"] + 58 * MIN)
        pr = panel.get(("QQQUSDT", r["date"]))
        if not (p0 and p928 and pr and "r_o120" in pr):
            continue
        s = int(np.sign(p928 / p0 - 1))
        if not s:
            continue
        c = cost_pct("QQQUSDT", r["date"])
        ew_o = [panel[k]["r_o120"] for k in panel
                if k[1] == r["date"] and "r_o120" in panel[k]]
        strip = s * (pr["r_o120"] - float(np.mean(ew_o))) - c if ew_o else None
        recs.append({"date": r["date"], "net": s * pr["r_o120"] - c,
                     "net15": s * pr["r_o120"] - 1.5 * c, "strip_beta1": strip})
    if recs:
        nets = np.array([x["net"] for x in recs])
        tot = float(nets.sum())
        p2o[split] = {"n": len(recs), "mean_net": round(float(nets.mean()), 4),
                      "mean_net_1p5x": round(float(np.mean([x["net15"] for x in recs])), 4),
                      "mean_strip_beta1": round(float(np.mean(
                          [x["strip_beta1"] for x in recs if x["strip_beta1"] is not None])), 4),
                      "lodo_max_share": round(float(max(nets) / tot), 3) if tot > 0 else None,
                      "per_event": {x["date"]: round(x["net"], 4) for x in recs}}
    else:
        p2o[split] = {"n": 0}
cells.append(p2o)
out["attacks"]["a_b_d_cells_recomputed"] = cells

# ---------------- (c) 重叠持有期 ----------------
overlap = []
for c in cells:
    for split in ("dev", "val"):
        pe = c.get(split, {}).get("per_event")
        if not pe:
            continue
        ds = list(pe)
        overlap.append({"rule": c["rule"], "split": split, "n": len(ds),
                        "n_unique_dates": len(set(ds)),
                        "dates_distinct": len(ds) == len(set(ds))})
# 同日跨事件类型: 检查 EVENTS 里有无同日两类事件
flat = [(t, d) for t, v in EVENTS.items() for d in v]
dupdays = {d for t, d in flat if sum(1 for _, dd in flat if dd == d) > 1}
out["attacks"]["c_overlap"] = {
    "cells": overlap, "cross_type_same_day": sorted(dupdays),
    "note": "持有窗均为单日内 115min, 不同事件在不同日 → 无跨事件持有重叠; "
            "但 ALL830 与各单类型 cell 共用同一批事件 → 96 cells 高度相关, 有效独立检验远少于 96"}

# ---------------- (e) 上市偏差: listing-matched CPI 倍数 ----------------
# 每个 CPI 事件: 用该事件当时存在的 symbol, 对每个 symbol 用其自身基线日均 |r0_5| 归一
sym_base: dict = {}
for ds in base_days:
    t0 = t0_zoneinfo(ds, "CPI")
    if t0 + 10 * MIN > HARD_CAP_MS:
        continue
    bars = bars_window(t0 - 20 * MIN, t0 + 10 * MIN)
    for sym, bs in bars.items():
        p0, p5 = px(bs, t0), px(bs, t0 + 5 * MIN)
        if p0 and p5:
            sym_base.setdefault(sym, []).append(abs(p5 / p0 - 1) * 100)
match_rows = []
for r in ev:
    if r["type"] != "CPI":
        continue
    ratios = []
    for sym, v in r["per"].items():
        if sym in sym_base and len(sym_base[sym]) >= 10:
            b = float(np.mean(sym_base[sym]))
            if b > 0:
                ratios.append(abs(v["r0_5"]) / b)
    match_rows.append({"date": r["date"], "n_sym_event": r["n_sym"],
                       "n_sym_matched": len(ratios),
                       "median_per_sym_ratio": round(float(np.median(ratios)), 2)
                       if ratios else None,
                       "mean_per_sym_ratio": round(float(np.mean(ratios)), 2)
                       if ratios else None})
qqq_ev_cpi = [abs(r["per"]["QQQUSDT"]["r0_5"]) for r in ev
              if r["type"] == "CPI" and "QQQUSDT" in r["per"]]
out["attacks"]["e_listing_bias"] = {
    "note": "基线日全在 04-06 后(QQQ时代), 早期事件(2-3月)只有 8 只 → 原 EW 倍数口径不匹配; "
            "此处 per-symbol listing-matched 复算",
    "cpi_matched_ratio_rows": match_rows,
    "qqq_cpi_events_abs_r0_5": [round(x, 4) for x in qqq_ev_cpi],
    "qqq_baseline_mean_abs_r0_5": round(float(np.mean(base_prof_qqq)), 4)
    if base_prof_qqq else None,
    "qqq_cpi_multiple_recomputed": round(float(np.mean(qqq_ev_cpi))
                                         / float(np.mean(base_prof_qqq)), 2)
    if base_prof_qqq and qqq_ev_cpi else None,
    "candidate_cells_all_post_qqq_listing": all(
        d >= "2026-04-06"
        for c in cells for split in ("dev", "val")
        for d in (c.get(split, {}).get("per_event") or {}))}

# ---------------- (d) 成本档核查 ----------------
qv_rows = []
for r in ev:
    pr = panel.get(("QQQUSDT", r["date"]))
    if pr:
        qv_rows.append({"date": r["date"], "qv_day_usd": round(pr.get("qv_day", 0)),
                        "tier": "2bp" if pr.get("qv_day", 0) >= 5e6 else "5bp",
                        "roundtrip_cost_pct": cost_pct("QQQUSDT", r["date"])})
out["attacks"]["d_cost_tiers_qqq_event_days"] = qv_rows

json.dump(out, open(OUT, "w"), indent=1, ensure_ascii=False)
print("WROTE", OUT)
