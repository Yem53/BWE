#!/usr/bin/env python3
"""Round27 族C — 宏观事件窗事件研究 (CPI/NFP/PCE 08:30 ET, FOMC 14:00 ET).

产出定位 = 结构地图 (n 极小, 全程探索性), 不是可交易宣称.

数据纪律:
- 硬上限: 任何 kline 查询 ot <= 1781654399000 (2026-06-15T23:59Z)
- dev = date <= 2026-05-31, val = 2026-06-01 ~ 06-15
- 成本: taker 0.08% 往返 + 点差 2bp/边 (qv_day < $5M 当日按 5bp/边)
- beta 剥离: 方向性结果同时报 减去同窗口全 universe 等权收益
- DST: date < 2026-03-08 → ET=UTC-5, 之后 → ET=UTC-4
"""
import bisect
import json
import sqlite3
from datetime import datetime, timezone

import numpy as np

ROOT = "/Volumes/T9/BWE/40_EXPERIMENTS/round27_usstock_alpha"
DB = ROOT + "/tradfi_full.sqlite3"
PANEL = ROOT + "/panel_devval.jsonl"
OUT = ROOT + "/alpha_screen/C/c_results.json"
HARD_CAP_MS = 1781654399000  # 2026-06-15T23:59:59Z — 铁律
MIN = 60_000

# ---- 宏观日历 (ALFRED 实际发布日, release_id 10/50/54; FOMC 静态日程) ----
# 已硬过滤 date <= 2026-06-15; 01-28 之前的事件因 kline 库 2026-01-28 才开始, 保留但会自动无数据
EVENTS = {
    "CPI": ["2026-02-13", "2026-03-11", "2026-04-10", "2026-05-12", "2026-06-10"],
    "NFP": ["2026-02-11", "2026-03-06", "2026-04-03", "2026-05-08", "2026-06-05"],
    "PCE": ["2026-02-20", "2026-03-13", "2026-04-09", "2026-04-30", "2026-05-28"],
    "FOMC": ["2026-01-28", "2026-03-18", "2026-04-29"],
}
DEV_END = "2026-05-31"
VAL_END = "2026-06-15"


def et_offset_hours(datestr: str) -> int:
    m, d = int(datestr[5:7]), int(datestr[8:10])
    return 5 if (m, d) < (3, 8) else 4  # 2026-03-08 DST 切换


def event_t0_ms(datestr: str, typ: str) -> int:
    h, mi = (14, 0) if typ == "FOMC" else (8, 30)
    off = et_offset_hours(datestr)
    dt = datetime(int(datestr[:4]), int(datestr[5:7]), int(datestr[8:10]),
                  h + off, mi, tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def rth_open_ms(datestr: str) -> int:
    off = et_offset_hours(datestr)
    dt = datetime(int(datestr[:4]), int(datestr[5:7]), int(datestr[8:10]),
                  9 + off, 30, tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


# ---- 数据访问 ----
conn = sqlite3.connect(DB)


def load_bars(t_lo: int, t_hi: int) -> dict:
    """全 universe 在 [t_lo, t_hi] 的 1m bar → {sym: {ot: (open, close)}}. 硬上限强制."""
    t_hi = min(t_hi, HARD_CAP_MS)
    out: dict = {}
    for sym, ot, o, cl in conn.execute(
            "SELECT symbol, ot, o, cl FROM klines_1m WHERE ot BETWEEN ? AND ? AND ot <= ?",
            (t_lo, t_hi, HARD_CAP_MS)):
        out.setdefault(sym, {})[ot] = (float(o), float(cl))
    return out


def px_at(bars_sym: dict, t_ms: int, lookback_min: int = 15):
    """t_ms 分钟 bar 的 open; 缺 bar 则回退最近 <=lookback 分钟内的前一 bar close."""
    if bars_sym is None:
        return None
    b = bars_sym.get(t_ms)
    if b is not None:
        return b[0]
    for k in range(1, lookback_min + 1):
        b = bars_sym.get(t_ms - k * MIN)
        if b is not None:
            return b[1]
    return None


# ---- panel: qv_day (成本档) + r_o30/r_o120 (传导) ----
panel = {}
panel_dates = set()
panel_stats = {"dev": {"rows": 0, "syms": set(), "by_month": {}},
               "val": {"rows": 0, "syms": set(), "by_month": {}}}
for line in open(PANEL):
    d = json.loads(line)
    key = "dev" if d["date"] <= DEV_END else "val"
    panel_stats[key]["rows"] += 1
    panel_stats[key]["syms"].add(d["symbol"])
    mo = d["date"][:7]
    panel_stats[key]["by_month"][mo] = panel_stats[key]["by_month"].get(mo, 0) + 1
    panel[(d["symbol"], d["date"])] = d
    panel_dates.add(d["date"])


def cost_pct(sym: str, datestr: str) -> float:
    """taker 0.08% 往返 + 点差 2bp/边 (小票/未知按 5bp/边). 返回 % 单位."""
    row = panel.get((sym, datestr))
    spread_bp = 2.0 if (row and row.get("qv_day", 0) >= 5e6) else 5.0
    return 0.08 + 2 * spread_bp / 100.0


# ---- 每事件窗口收益 ----
WINDOWS = ["pre60", "r0_5", "r5_30", "r30_120"]


def window_rets(bars_sym: dict, t0: int) -> dict | None:
    a = {lab: px_at(bars_sym, t0 + off * MIN)
         for lab, off in [("m60", -60), ("t0", 0), ("p5", 5), ("p30", 30), ("p120", 120)]}
    if any(v is None for v in a.values()):
        return None
    r = lambda p1, p0: (p1 / p0 - 1) * 100
    return {"pre60": r(a["t0"], a["m60"]), "r0_5": r(a["p5"], a["t0"]),
            "r5_30": r(a["p30"], a["p5"]), "r30_120": r(a["p120"], a["p30"]),
            "r5_120": r(a["p120"], a["p5"])}


ev_rows = []  # 每事件 × 每 instrument 明细
for typ, dates in EVENTS.items():
    for ds in dates:
        if ds > VAL_END:
            continue
        t0 = event_t0_ms(ds, typ)
        if t0 + 120 * MIN > HARD_CAP_MS:
            continue
        bars = load_bars(t0 - 75 * MIN, t0 + 125 * MIN)
        split = "dev" if ds <= DEV_END else "val"
        # 单 instrument
        per_sym = {}
        for sym, bs in bars.items():
            w = window_rets(bs, t0)
            if w is not None:
                per_sym[sym] = w
        if not per_sym:
            continue
        # 全 universe 等权
        ew = {k: float(np.mean([w[k] for w in per_sym.values()]))
              for k in per_sym[next(iter(per_sym))]}
        row = {"type": typ, "date": ds, "split": split, "t0_utc_ms": t0,
               "n_universe": len(per_sym), "EW": ew,
               "QQQ": per_sym.get("QQQUSDT"), "SPY": per_sym.get("SPYUSDT")}
        # 传导: print 后 58min 处信号 (9:28 ET), 与 RTH open→+30/+120 (panel)
        if typ != "FOMC":
            p_t0 = px_at(bars.get("QQQUSDT"), t0)
            p_928 = px_at(bars.get("QQQUSDT"), t0 + 58 * MIN)
            if p_t0 and p_928:
                row["qqq_print_to_928"] = (p_928 / p_t0 - 1) * 100
                pr = panel.get(("QQQUSDT", ds))
                if pr and "r_o30" in pr:
                    row["qqq_r_o30"] = pr["r_o30"]
                    row["qqq_r_o120"] = pr["r_o120"]
            # 横截面传导: 每 symbol print 反应 vs 开盘后
            cs = []
            for sym, w in per_sym.items():
                pr = panel.get((sym, ds))
                if pr and "r_o30" in pr:
                    cs.append((w["r0_5"], pr["r_o30"], pr["r_o120"]))
            row["_cs_transmission"] = cs
        ev_rows.append(row)

# ---- 手写 spearman ----
def spearman(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    if len(x) < 3:
        return None
    rx = np.argsort(np.argsort(x)).astype(float)
    ry = np.argsort(np.argsort(y)).astype(float)
    sx, sy = rx.std(), ry.std()
    if sx == 0 or sy == 0:
        return None
    return float(np.corrcoef(rx, ry)[0, 1])


# ---- 1) 结构地图: 事件类型 × 窗口 × instrument ----
char_map = {}
n_char_cells = 0
for typ in EVENTS:
    for instr in ["QQQ", "SPY", "EW"]:
        rows = [r for r in ev_rows if r["type"] == typ and r.get(instr)]
        if not rows:
            continue
        cell = {}
        for w in WINDOWS:
            vals = [r[instr][w] for r in rows]
            n_char_cells += 1
            cell[w] = {"n": len(vals), "mean": round(float(np.mean(vals)), 4),
                       "median": round(float(np.median(vals)), 4),
                       "mean_abs": round(float(np.mean(np.abs(vals))), 4),
                       "per_event": {r["date"]: round(r[instr][w], 4) for r in rows}}
        char_map[f"{typ}|{instr}"] = cell

# ---- 2) drift vs 过冲回归: sign(r0_5) 与后续窗口 ----
pattern_map = {}
for typ in EVENTS:
    for instr in ["QQQ", "EW"]:
        rows = [r for r in ev_rows if r["type"] == typ and r.get(instr)]
        if len(rows) < 2:
            continue
        s = np.array([np.sign(r[instr]["r0_5"]) for r in rows])
        f30 = np.array([r[instr]["r5_30"] for r in rows])
        f120 = np.array([r[instr]["r30_120"] for r in rows])
        pattern_map[f"{typ}|{instr}"] = {
            "n": len(rows),
            "P_cont_5_30": round(float(np.mean(np.sign(f30) == s)), 3),
            "mean_signed_5_30": round(float(np.mean(s * f30)), 4),
            "P_cont_30_120": round(float(np.mean(np.sign(f120) == s)), 3),
            "mean_signed_30_120": round(float(np.mean(s * f120)), 4)}

# ---- 3) 基线对照: 非事件日同 clock 窗口 (QQQ 时代 04-06 之后) ----
event_dates = {d for ds in EVENTS.values() for d in ds}
base_dates = sorted(d for d in panel_dates
                    if d <= DEV_END and d not in event_dates
                    and ("QQQUSDT", d) in panel)
baseline = {"n_days": 0, "qqq_abs_r0_5_0830": [], "qqq_abs_r0_5_1400": [],
            "ew_abs_r0_5_0830": []}
for ds in base_dates:
    t830 = event_t0_ms(ds, "CPI")
    t1400 = event_t0_ms(ds, "FOMC")
    if t1400 + 120 * MIN > HARD_CAP_MS:
        continue
    bars = load_bars(t830 - 75 * MIN, t1400 + 125 * MIN)
    w830 = window_rets(bars.get("QQQUSDT"), t830)
    w1400 = window_rets(bars.get("QQQUSDT"), t1400)
    if w830 is None or w1400 is None:
        continue
    baseline["n_days"] += 1
    baseline["qqq_abs_r0_5_0830"].append(abs(w830["r0_5"]))
    baseline["qqq_abs_r0_5_1400"].append(abs(w1400["r0_5"]))
    ew5 = [window_rets(bs, t830) for bs in bars.values()]
    ew5 = [w["r0_5"] for w in ew5 if w]
    if ew5:
        baseline["ew_abs_r0_5_0830"].append(abs(float(np.mean(ew5))))
baseline_summary = {
    "n_days": baseline["n_days"],
    "qqq_mean_abs_r0_5_at_0830ET": round(float(np.mean(baseline["qqq_abs_r0_5_0830"])), 4)
    if baseline["qqq_abs_r0_5_0830"] else None,
    "qqq_mean_abs_r0_5_at_1400ET": round(float(np.mean(baseline["qqq_abs_r0_5_1400"])), 4)
    if baseline["qqq_abs_r0_5_1400"] else None,
    "ew_mean_abs_r0_5_at_0830ET": round(float(np.mean(baseline["ew_abs_r0_5_0830"])), 4)
    if baseline["ew_abs_r0_5_0830"] else None}

# ---- 4) 规则筛 (全部探索性: n<100) ----
def eval_rule(rows, instr, direction_fn, entry_leg, label):
    """direction_fn(row)→±1/None; entry_leg: 窗口收益字段名 (持仓段).
    返回 dev/val 明细 + 净值 + beta 剥离 + LODO."""
    res = {"rule": label, "instr": instr}
    for split in ["dev", "val"]:
        nets, nets15, stripped, dates = [], [], [], []
        for r in rows:
            if r["split"] != split or not r.get(instr):
                continue
            d = direction_fn(r)
            if d is None or d == 0:
                continue
            gross = d * r[instr][entry_leg]
            c = cost_pct("QQQUSDT" if instr == "QQQ" else "SPYUSDT", r["date"]) \
                if instr in ("QQQ", "SPY") else 0.12
            nets.append(gross - c)
            nets15.append(gross - 1.5 * c)
            strip = d * (r[instr][entry_leg] - r["EW"][entry_leg]) - c
            stripped.append(strip)
            dates.append(r["date"])
        if not nets:
            res[split] = {"n": 0}
            continue
        nets_a = np.array(nets)
        tot = float(nets_a.sum())
        # LODO: 留一日 — 最大单日贡献占比 (仅当总和为正才有意义)
        lodo_max_share = None
        lodo_all_pos = None
        if tot > 0:
            shares = [float(x) / tot for x in nets_a]
            lodo_max_share = round(max(shares), 3)
            lodo_all_pos = all(tot - x > 0 for x in nets_a)
        res[split] = {
            "n": len(nets), "mean_net": round(float(nets_a.mean()), 4),
            "sum_net": round(tot, 4), "win": round(float((nets_a > 0).mean()), 3),
            "mean_net_1p5x_cost": round(float(np.mean(nets15)), 4),
            "mean_net_beta_stripped": round(float(np.mean(stripped)), 4),
            "lodo_max_share": lodo_max_share, "lodo_survives": lodo_all_pos,
            "per_event": {dt: round(float(x), 4) for dt, x in zip(dates, nets)},
            "exploratory": True}
    return res


rules_out = []
n_rule_cells = 0
mk_momo = lambda r, instr: (lambda s: s if s != 0 else None)(int(np.sign(r[instr]["r0_5"])))
for typ in ["CPI", "NFP", "PCE", "FOMC", "ALL830"]:
    rows = [r for r in ev_rows
            if (r["type"] == typ) or (typ == "ALL830" and r["type"] != "FOMC")]
    for instr in ["QQQ", "SPY"]:
        for leg, legname in [("r5_30", "5to30"), ("r5_120", "5to120")]:
            for sgn, sname in [(+1, "momo"), (-1, "fade")]:
                lab = f"{typ}_{sname}_{legname}"
                fn = (lambda sgn_, instr_: lambda r: (
                    (lambda s: sgn_ * s if s != 0 else None)(int(np.sign(r[instr_]["r0_5"])))
                ))(sgn, instr)
                res = eval_rule(rows, instr, fn, leg, lab)
                n_rule_cells += 1
                rules_out.append(res)

# print→open 传导规则: sign(8:30→9:28) 开盘 taker 进, open+30/open+120 出 (用 panel r_o30/r_o120)
for horizon in ["r_o30", "r_o120"]:
    for typ in ["CPI", "NFP", "PCE", "ALL830"]:
        rows = [r for r in ev_rows if "qqq_print_to_928" in r and "qqq_r_o30" in r
                and (r["type"] == typ or typ == "ALL830")]
        res = {"rule": f"{typ}_print2open_{horizon}", "instr": "QQQ"}
        for split in ["dev", "val"]:
            nets, stripped, dates, costs = [], [], [], []
            for r in rows:
                if r["split"] != split:
                    continue
                s = int(np.sign(r["qqq_print_to_928"]))
                if s == 0:
                    continue
                c = cost_pct("QQQUSDT", r["date"])
                gross = s * r[f"qqq_{horizon}"]
                nets.append(gross - c)
                costs.append(c)
                # beta 剥离: 减同窗全 universe 等权 (panel r_o30/r_o120 等权)
                ew_o = [panel[(sym, r["date"])][horizon]
                        for sym in {k[0] for k in panel if k[1] == r["date"]}
                        if horizon in panel[(sym, r["date"])]]
                strip = s * (r[f"qqq_{horizon}"] - float(np.mean(ew_o))) - c if ew_o else None
                stripped.append(strip)
                dates.append(r["date"])
            if not nets:
                res[split] = {"n": 0}
                continue
            a = np.array(nets)
            tot = float(a.sum())
            lodo = round(max(x / tot for x in a), 3) if tot > 0 else None
            res[split] = {"n": len(a), "mean_net": round(float(a.mean()), 4),
                          "sum_net": round(tot, 4), "win": round(float((a > 0).mean()), 3),
                          "mean_net_1p5x_cost":
                              round(float(np.mean(a - 0.5 * np.array(costs))), 4),
                          "mean_net_beta_stripped":
                              round(float(np.mean([x for x in stripped if x is not None])), 4)
                              if any(x is not None for x in stripped) else None,
                          "lodo_max_share": lodo,
                          "per_event": {dt: round(float(x), 4) for dt, x in zip(dates, a)},
                          "exploratory": True}
        n_rule_cells += 1
        rules_out.append(res)

# ---- 5) 传导相关 (结构量) ----
trans = {}
t_rows = [r for r in ev_rows if "qqq_print_to_928" in r and "qqq_r_o30" in r]
if len(t_rows) >= 3:
    x = [r["qqq_print_to_928"] for r in t_rows]
    trans["qqq_events_pooled"] = {
        "n_events": len(t_rows),
        "spearman_print_vs_o30": spearman(x, [r["qqq_r_o30"] for r in t_rows]),
        "spearman_print_vs_o120": spearman(x, [r["qqq_r_o120"] for r in t_rows]),
        "per_event": [{"date": r["date"], "type": r["type"],
                       "print928": round(r["qqq_print_to_928"], 4),
                       "r_o30": round(r["qqq_r_o30"], 4),
                       "r_o120": round(r["qqq_r_o120"], 4)} for r in t_rows]}
cs_sp30, cs_sp120 = [], []
for r in ev_rows:
    cs = r.get("_cs_transmission") or []
    if len(cs) >= 5:
        sp30 = spearman([c[0] for c in cs], [c[1] for c in cs])
        sp120 = spearman([c[0] for c in cs], [c[2] for c in cs])
        if sp30 is not None:
            cs_sp30.append({"date": r["date"], "type": r["type"], "n_sym": len(cs),
                            "sp_r05_vs_o30": round(sp30, 3),
                            "sp_r05_vs_o120": round(sp120, 3) if sp120 else None})
trans["cross_sectional_per_event"] = cs_sp30
if cs_sp30:
    trans["cs_mean_sp_r05_vs_o30"] = round(float(np.mean(
        [c["sp_r05_vs_o30"] for c in cs_sp30])), 3)

# ---- 汇总输出 ----
for r in ev_rows:
    r.pop("_cs_transmission", None)
out = {
    "family": "C_macro_event_window",
    "generated": datetime.now(timezone.utc).isoformat(),
    "hard_cap_ms": HARD_CAP_MS,
    "calendar_source": "ALFRED release dates rid=10(CPI)/50(NFP)/54(PCE) + FOMC static",
    "events_used": ev_rows,
    "sample_structure": {
        "panel_dev_rows": panel_stats["dev"]["rows"],
        "panel_dev_syms": len(panel_stats["dev"]["syms"]),
        "panel_dev_by_month": panel_stats["dev"]["by_month"],
        "panel_val_rows": panel_stats["val"]["rows"],
        "panel_val_syms": len(panel_stats["val"]["syms"]),
        "panel_val_by_month": panel_stats["val"]["by_month"],
        "n_events_total": len(ev_rows),
        "n_events_dev": sum(1 for r in ev_rows if r["split"] == "dev"),
        "n_events_val": sum(1 for r in ev_rows if r["split"] == "val"),
        "qqq_spy_listed_from": "2026-04-06 (早期事件只有 universe 等权口径, 2-3月 universe 仅 8 只)",
    },
    "characterization": char_map,
    "drift_vs_reversion": pattern_map,
    "baseline_nonevent": baseline_summary,
    "rules_screen": rules_out,
    "transmission_0830_to_0930": trans,
    "n_cells": {"characterization": n_char_cells, "rules": n_rule_cells,
                "total": n_char_cells + n_rule_cells},
    "honest_notes": [
        "n 极小: dev 每类型 3-5 个事件, val 每类型至多 1 个 (NFP 06-05, CPI 06-10) — 全部探索性, 无可交易宣称",
        "QQQ/SPY 永续 2026-04-06 才上市: 2-3 月事件只有 8 只票的等权口径, 不是市场 beta",
        "LODO 在 n<=7 时单事件占比几乎必然 >40% — 结构性无法通过, 如实报",
        "本族产出 = 结构地图, 为 forward 攒假设",
    ],
}
json.dump(out, open(OUT, "w"), indent=1, ensure_ascii=False)
print("WROTE", OUT)
print("events:", len(ev_rows), "dev:", out["sample_structure"]["n_events_dev"],
      "val:", out["sample_structure"]["n_events_val"])
print("cells:", out["n_cells"])
