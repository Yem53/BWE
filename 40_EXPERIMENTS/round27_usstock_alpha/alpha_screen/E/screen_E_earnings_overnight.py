#!/usr/bin/env python3
"""
族E: 财报隔夜过冲回归 — 盘后财报落地时正股停牌, 永续是唯一定价场所。
即时反应(16:00→20/22/24 ET)过冲吗? 次日开盘窗回归还是延续?

探索性筛查 (n=68 事件, dev=62 / val=6)。目标 = 冻结规则给7月财报季 forward 验证。

纪律:
- 只用 ot ≤ 1781654399000 (2026-06-15T23:59Z), holdout 禁区硬断言
- ET 时区 zoneinfo America/New_York (自动 DST, 03-08 切换)
- β剥离: 每个窗减同窗全 universe (105 perp, 除自身) 等权收益
- 成本 0.12% 往返; 1.5× 加压 0.18%; 盘后进单滑点加倍 0.24%
- LODO (leave-one-date-out) 稳定性
- 报总 cell 数
"""
import json, math, sqlite3, sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ROOT = "/Volumes/T9/BWE/40_EXPERIMENTS/round27_usstock_alpha"
DB = ROOT + "/tradfi_full.sqlite3"
EVENTS = ROOT + "/data/uw_earnings_events.jsonl"
PANEL = ROOT + "/panel_devval.jsonl"
OUT = ROOT + "/alpha_screen/E/results_E.json"

HOLDOUT_MAX = 1781654399000
DEV_END = "2026-05-31"
VAL_END = "2026-06-15"
ET = ZoneInfo("America/New_York")
STALE_MS = 15 * 60000          # 点价查询容忍 15min 内最后一根bar
COSTS = {"c012": 0.12, "c018": 0.18, "c024": 0.24}  # % 往返

con = sqlite3.connect(DB)
UNIVERSE = [s for (s,) in con.execute("SELECT DISTINCT symbol FROM klines_1m")]
assert len(UNIVERSE) == 105

# ---------------- panel ----------------
panel = {}                      # (sym, date) -> row
sym_dates = defaultdict(list)   # sym -> sorted dates
for line in open(PANEL):
    r = json.loads(line)
    panel[(r["symbol"], r["date"])] = r
    sym_dates[r["symbol"]].append(r["date"])
for s in sym_dates:
    sym_dates[s].sort()

def next_trading_row(sym, d):
    ds = sym_dates[sym]
    import bisect
    i = bisect.bisect_right(ds, d)
    return panel[(sym, ds[i])] if i < len(ds) else None

# ---------------- events ----------------
events = []
for line in open(EVENTS):
    line = line.strip()
    if not line or "_empty" in line:
        continue
    e = json.loads(line)
    if e.get("_session") != "afterhours":
        continue
    if e["symbol"] + "USDT" not in set(UNIVERSE):
        continue
    if e["_date"] > VAL_END:
        continue
    events.append(e)
print("events loaded:", len(events))

# ---------------- point price lookup (cached) ----------------
_pt_cache = {}
def price_at(sym, ts):
    """最后一根在 ts 前收盘的1m bar 的 close (bar ot < ts, 即收盘时刻 ot+60000 ≤ ts)。
    容忍 STALE_MS。返回 (px, staleness_ms) 或 None。"""
    assert ts <= HOLDOUT_MAX + 60000, f"holdout violation ts={ts}"
    key = (sym, ts)
    if key in _pt_cache:
        return _pt_cache[key]
    row = con.execute(
        "SELECT ot, cl FROM klines_1m WHERE symbol=? AND ot<? AND ot>=? ORDER BY ot DESC LIMIT 1",
        (sym, ts, ts - STALE_MS)).fetchone()
    out = None
    if row:
        ot, cl = row
        assert ot <= HOLDOUT_MAX
        out = (float(cl), int(ts - (ot + 60000)))
    _pt_cache[key] = out
    return out

def et_ts(date_str, hour):
    """date_str 当日 ET hour:00 的 UTC 毫秒。hour=24 → 次日 00:00 ET。"""
    d = datetime.strptime(date_str, "%Y-%m-%d")
    if hour == 24:
        d += timedelta(days=1); hour = 0
    dt = datetime(d.year, d.month, d.day, hour, 0, tzinfo=ET)
    return int(dt.timestamp() * 1000)

def uni_ret(t1, t2, exclude):
    """universe 等权收益% (t1→t2), 排除事件币自身。两端都需 fresh 点价。
    ⚠️ universe 是逐步上线的: 2026-03 只有 8 只, 06-15 才 87 只 — min 5 只可用即剥离,
    并记录 n_uni (β剥离在早期事件上噪声大, 诚实报告)。"""
    rets = []
    for s in UNIVERSE:
        if s == exclude:
            continue
        p1 = price_at(s, t1); p2 = price_at(s, t2)
        if p1 and p2 and p1[0] > 0:
            rets.append((p2[0] / p1[0] - 1) * 100)
    return (sum(rets) / len(rets), len(rets)) if len(rets) >= 5 else (None, len(rets))

# ---------------- per-event measurement ----------------
rows, drops = [], defaultdict(int)
for e in events:
    sym = e["symbol"] + "USDT"
    D = e["_date"]
    rowD = panel.get((sym, D))
    if not rowD:
        drops["no_panel_report_day"] += 1; continue
    rowN = next_trading_row(sym, D)
    if not rowN:
        drops["no_next_day"] += 1; continue
    if rowN.get("px_o30") is None or rowN.get("px_o60") is None:
        drops["no_next_open_anchor"] += 1; continue
    # 时间锚点
    t_close = rowD["rth_close_ts"] + 60000          # ≈16:00 ET 收盘时刻
    t_open = rowN["rth_open_ts"] + 60000            # ≈09:31 ET (首根RTH bar收盘)
    t_o30 = rowN["rth_open_ts"] + 31 * 60000
    t_o60 = rowN["rth_open_ts"] + 61 * 60000
    if t_o60 > HOLDOUT_MAX:
        drops["holdout"] += 1; continue
    px_close = rowD["rth_close"]
    anchors = {"close": (t_close, px_close),
               "open": (t_open, rowN["rth_open"]),
               "o30": (t_o30, rowN["px_o30"]),
               "o60": (t_o60, rowN["px_o60"])}
    ok = True
    ev_px, ev_stale = {}, {}
    for H in (20, 22, 24):
        ts = et_ts(D, H)
        p = price_at(sym, ts)
        if p is None:
            ok = False; break
        anchors[f"e{H}"] = (ts, p[0]); ev_stale[f"e{H}"] = p[1]
    if not ok:
        drops["no_evening_price"] += 1; continue

    rec = {"symbol": e["symbol"], "date": D, "next_date": rowN["date"],
           "sector": e.get("sector"), "mcap": float(e.get("marketcap") or 0),
           "em_pct": float(e["expected_move_perc"]) * 100,
           "stock_reaction": float(e.get("reaction") or 0) * 100,
           "stale": ev_stale}
    # 即时反应 (raw)
    for H in (20, 22, 24):
        rec[f"react{H}"] = (anchors[f"e{H}"][1] / px_close - 1) * 100
    # 窗收益 raw + β剥离
    windows = {}
    for ent in ("e20", "e22", "e24", "open"):
        for ex in ("open", "o30", "o60"):
            if ent == "open" and ex == "open":
                continue
            t1, p1 = anchors[ent]; t2, p2 = anchors[ex]
            r = (p2 / p1 - 1) * 100
            u, nu = uni_ret(t1, t2, sym)
            windows[f"{ent}_{ex}"] = {"raw": r, "xr": (r - u) if u is not None else None, "n_uni": nu}
    # 反应本身也β剥离 (close→e22)
    for H in (20, 22, 24):
        u, _ = uni_ret(anchors["close"][0], anchors[f"e{H}"][0], sym)
        rec[f"react{H}_x"] = rec[f"react{H}"] - u if u is not None else None
    rec["win"] = windows
    # 盘后流动性: 16:00→22:00 ET
    t1, t2 = t_close, et_ts(D, 22)
    bars = con.execute("SELECT h,l,cl,qv FROM klines_1m WHERE symbol=? AND ot>=? AND ot<?",
                       (sym, t1, t2)).fetchall()
    qvs = sorted(b[3] for b in bars)
    rec["liq"] = {"n_bars": len(bars), "max_bars": int((t2 - t1) / 60000),
                  "qv_total": sum(qvs),
                  "qv_med_per_min": qvs[len(qvs)//2] if qvs else 0.0}
    ent_bars = con.execute("SELECT h,l,cl,qv FROM klines_1m WHERE symbol=? AND ot>=? AND ot<?",
                           (sym, t2 - 10*60000, t2)).fetchall()
    if ent_bars:
        rec["liq"]["entry_qv_per_min"] = sum(b[3] for b in ent_bars) / len(ent_bars)
        rec["liq"]["entry_hl_pct"] = sum((b[0]-b[1])/b[2]*100 for b in ent_bars) / len(ent_bars)
    rows.append(rec)

print("measured:", len(rows), "drops:", dict(drops))

# ---------------- cells ----------------
def stats(vals):
    n = len(vals)
    if n == 0:
        return {"n": 0}
    m = sum(vals) / n
    med = sorted(vals)[n // 2]
    sd = math.sqrt(sum((v - m) ** 2 for v in vals) / (n - 1)) if n > 1 else 0.0
    t = m / (sd / math.sqrt(n)) if sd > 0 else 0.0
    win = sum(1 for v in vals if v > 0) / n
    return {"n": n, "mean": round(m, 3), "median": round(med, 3), "sd": round(sd, 3),
            "t": round(t, 2), "win": round(win, 3)}

REACT_ANCHOR = {"e20": "react20", "e22": "react22", "e24": "react24", "open": "react22"}
BINS = {
    "all":        lambda r, ra: True,
    "abs_ge2":    lambda r, ra: abs(r[ra]) >= 2,
    "abs_ge5":    lambda r, ra: abs(r[ra]) >= 5,
    "abs_ge10":   lambda r, ra: abs(r[ra]) >= 10,
    "over_em":    lambda r, ra: abs(r[ra]) >= r["em_pct"],          # 反应超期权隐含预期波动
    "under_em05": lambda r, ra: abs(r[ra]) < 0.5 * r["em_pct"],     # 反应不足 (<0.5×EM)
}
WINDOWS = ["e20_open", "e20_o30", "e20_o60",
           "e22_open", "e22_o30", "e22_o60",
           "e24_open", "e24_o30", "e24_o60",
           "open_o30", "open_o60"]

dev = [r for r in rows if r["date"] <= DEV_END]
val = [r for r in rows if r["date"] > DEV_END]
print("dev:", len(dev), "val:", len(val))

def run_cells(sample, key="xr"):
    """key='xr' β剥离 (决策口径) / key='raw' 原始收益 (对照)。fade方向; continuation = 镜像。"""
    cells = {}
    for w in WINDOWS:
        ra = REACT_ANCHOR[w.split("_")[0]]
        for bname, bfn in BINS.items():
            fade = []
            for r in sample:
                if r["win"][w][key] is None or r[ra] == 0:
                    continue
                if not bfn(r, ra):
                    continue
                sign = -1.0 if r[ra] > 0 else 1.0
                fade.append(sign * r["win"][w][key])
            s = stats(fade)
            if s["n"] >= 5:
                for ck, cv in COSTS.items():
                    s[f"net_{ck}"] = round(s["mean"] - cv, 3)
            cells[f"{w}|{bname}"] = s
    return cells

dev_cells = run_cells(dev, "xr")
dev_cells_raw = run_cells(dev, "raw")
n_cells = len(dev_cells)
print("cells tested (dev, fade direction, xr口径; raw对照+镜像不另计):", n_cells)

# 排序看 dev 最强 cell (按 |t|, n≥6)
ranked = sorted(((k, v) for k, v in dev_cells.items() if v["n"] >= 6),
                key=lambda kv: -abs(kv[1]["t"]))
print("\ntop 15 dev cells by |t| (fade方向, β剥离, gross %):")
for k, v in ranked[:15]:
    raw = dev_cells_raw.get(k, {})
    print(f"  {k:22s} n={v['n']:3d} mean={v['mean']:+.2f} med={v['median']:+.2f} "
          f"t={v['t']:+.2f} win={v['win']:.2f} net012={v.get('net_c012')} raw_mean={raw.get('mean')}")

# ---------------- LODO on headline cell ----------------
def lodo(sample, w, bname):
    ra = REACT_ANCHOR[w.split("_")[0]]
    bfn = BINS[bname]
    per_date = defaultdict(list)
    for r in sample:
        if r["win"][w]["xr"] is None or r[ra] == 0 or not bfn(r, ra):
            continue
        sign = -1.0 if r[ra] > 0 else 1.0
        per_date[r["date"]].append(sign * r["win"][w]["xr"])
    dates = sorted(per_date)
    allv = [v for d in dates for v in per_date[d]]
    full = sum(allv) / len(allv) if allv else None
    means = []
    for d in dates:
        rest = [v for d2 in dates if d2 != d for v in per_date[d2]]
        if rest:
            means.append(sum(rest) / len(rest))
    if not means:
        return {}
    return {"full_mean": round(full, 3), "n_dates": len(dates),
            "lodo_min": round(min(means), 3), "lodo_max": round(max(means), 3),
            "sign_flips": sum(1 for m in means if (m > 0) != (full > 0))}

# ---------------- 反应 vs 正股次日 reaction 一致性 (诊断) ----------------
diag_corr = None
pairs = [(r["react22"], r["stock_reaction"]) for r in dev if r["stock_reaction"] != 0]
if len(pairs) > 5:
    mx = sum(p[0] for p in pairs) / len(pairs); my = sum(p[1] for p in pairs) / len(pairs)
    cov = sum((a - mx) * (b - my) for a, b in pairs)
    vx = sum((a - mx) ** 2 for a, _ in pairs); vy = sum((b - my) ** 2 for _, b in pairs)
    diag_corr = round(cov / math.sqrt(vx * vy), 3) if vx > 0 and vy > 0 else None

# ---------------- liquidity aggregate ----------------
def med(xs):
    xs = sorted(xs)
    return xs[len(xs)//2] if xs else None
liq = {
    "n": len(rows),
    "bar_coverage_med": med([r["liq"]["n_bars"] / r["liq"]["max_bars"] for r in rows]),
    "ah_qv_total_med_usd": med([r["liq"]["qv_total"] for r in rows]),
    "ah_qv_per_min_med_usd": med([r["liq"]["qv_med_per_min"] for r in rows]),
    "entry2200_qv_per_min_med_usd": med([r["liq"].get("entry_qv_per_min", 0) for r in rows]),
    "entry2200_hl_pct_med": med([r["liq"].get("entry_hl_pct", 0) for r in rows]),
    "stale_e22_med_ms": med([r["stale"]["e22"] for r in rows]),
}
print("\nliquidity (median across events):", json.dumps(liq, indent=1))

# ---------------- assemble output ----------------
out = {
    "family": "E_earnings_overnight_overshoot",
    "generated": datetime.now(timezone.utc).isoformat(),
    "n_events_loaded": len(events), "n_events_measured": len(rows),
    "n_dev": len(dev), "n_val": len(val), "drops": dict(drops),
    "coverage_note": "68个盘后事件中48个的perp在财报日尚未上线(universe逐步扩容: 03-02仅8只, 06-15才87只), "
                     "有效样本仅19 — 远小于协议预期的~70。β剥离universe同样受限(早期事件仅7-25只可用)。",
    "n_cells_tested": n_cells,
    "costs_pct_roundtrip": COSTS,
    "diag_corr_perp22_vs_stock_reaction": diag_corr,
    "liquidity": liq,
    "dev_cells": dev_cells,
    "dev_cells_raw": dev_cells_raw,
    "top_dev_cells": [{"cell": k, **v} for k, v in ranked[:15]],
}

# headline = dev 最强且 n≥8 的 cell → LODO + val
head = next(((k, v) for k, v in ranked if v["n"] >= 8), None)
if head:
    w, b = head[0].split("|")
    out["headline_cell"] = {"cell": head[0], "dev": head[1],
                            "lodo": lodo(dev, w, b)}
    val_cells = run_cells(val, "xr")
    out["headline_cell"]["val"] = val_cells.get(head[0], {"n": 0})
    out["val_all_cells_note"] = "val n=%d 事件, 仅对 headline cell 报告, 其余不看" % len(val)
    print("\nheadline:", json.dumps(out["headline_cell"], ensure_ascii=False))

# ---------------- 结论 + 冻结规则 (7月Q2财报季 forward) ----------------
out["finding"] = (
    "反证过冲假设: perp盘后即时反应是【反应不足→隔夜延续drift】, 不是过冲回归。"
    "fade方向几乎所有晚间entry cell均值为负(e22_open|abs_ge2 fade=-1.04%, t=-2.62, win 11%), "
    "镜像=顺势: +1.04% gross, 8/9胜, LODO 6日无翻符, val 3/3同向(+0.96%)。"
    "连反应超期权隐含预期波动(over_em)的事件也延续(fade -1.2~-2.4%, 但n=3-4)。"
    "diag: perp 22:00反应与正股最终reaction相关0.78 — 方向早已定, 幅度未走完。"
    "drift主要发生在22:00→次日开盘(perp独家定价时段); 开盘后(open→o30/o60)延续基本消失。"
    "⚠️ n=9(headline)/16(dev), 66 cells, t=2.62不过Bonferroni — 纯探索性, 决不可直接交易。")
out["frozen_rule_forward_july"] = {
    "name": "E_afterhours_drift_v1",
    "event": "UW earnings, _session=afterhours(postmarket), symbol有perp且已上线≥7天",
    "signal": "r = perp(22:00 ET) / RTH_close(16:00 ET) - 1 (1m close点价, zoneinfo ET)",
    "condition": "|r| >= 2%",
    "action": "方向 = sign(r) 顺势(延续, 非fade), 22:00 ET进场, 次日RTH开盘(09:30 ET首根bar)平仓",
    "hedge": "可选: 等权perp篮子反向对冲β(dev统计为β剥离口径)",
    "dev_expectation": "+1.04% gross/事件, +0.80% net@0.24%往返(盘后滑点加倍), win~89%",
    "kill_criteria": "forward>=10个事件后 net均值<=0 或 win<60% → 废弃",
    "sizing_note": "22:00 ET perp流动性中位数仅~$7.7k/min, 单事件名义<=$5k, 分钟级TWAP进场",
}

# per-event detail (供复查)
out["events_detail"] = [
    {k: r[k] for k in ("symbol", "date", "next_date", "em_pct", "stock_reaction",
                        "react20", "react22", "react24", "react22_x")}
    | {"xr_e22_open": r["win"]["e22_open"]["xr"], "xr_e22_o60": r["win"]["e22_o60"]["xr"],
       "xr_open_o60": r["win"]["open_o60"]["xr"],
       "raw_e22_open": r["win"]["e22_open"]["raw"], "raw_open_o60": r["win"]["open_o60"]["raw"],
       "n_uni_e22_open": r["win"]["e22_open"]["n_uni"],
       "ah_qv_total": round(r["liq"]["qv_total"], 0)}
    for r in rows]

with open(OUT, "w") as f:
    json.dump(out, f, indent=1, ensure_ascii=False)
print("\nwrote", OUT)
