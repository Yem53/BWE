#!/usr/bin/env python3
"""终审 V4: 全周期统一重测 (2025-09-28 ~ 2026-05-27 警报, K线到 2026-05-29).

冻结规格(不得调参):
  B : 同分钟(ts_ms//60000)全市场警报总数>=16 且 price_chg_pct<=-2.5 -> LONG 240min
      去重 (symbol, ts//1800000), 按 ts 先后保留第一条
  C2: window_type='oi_price_1h' 且 oi_chg_pct>15 -> SHORT 1440min (无去重)
  基线: 全部 oi_price_1h 警报 SHORT 1440min (同评估器, 用于同日配对超额)

统一评估器(修正版, 与holdout终审 bug-e 修复一致):
  进场: 第一根 open_time_ms+60000 > ts 的bar, 取其收盘价; 若该bar收盘时刻晚于 ts+180s -> 丢弃(计数)
  出场: 第一根 open_time_ms >= entry_close_time + hold*60000 的bar, 取其收盘价;
        若该bar开盘晚于目标+300s -> 丢弃(计数)。缺K线=丢弃, 不漂移。
  成本: 0.94% RT;  拒绝价格<=0/非有限。
  资金费(仅C2, 数据到2026-04-30): SHORT收益 += sum(funding_rate)*100,
        结算取 entry_t < funding_time_ms <= exit_t; 仅统计资金费完整覆盖持仓窗口的trade。

内存纪律: 逐symbol流式; 只取 (open_time_ms, close) 两列。
"""
import glob
import json
import os
import resource
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone

import numpy as np

ROOT = "/Volumes/T9/BWE"
ALERT_DIR = ROOT + "/30_DATA/bwe_scanner_alerts"
KL_DB = ROOT + "/30_DATA/binance_collectors_runtime/binance_futures_klines_archive.sqlite3"
AUX_DB = ROOT + "/30_DATA/binance_collectors_runtime/binance_futures_aux_archive.sqlite3"
OUT_DIR = ROOT + "/40_EXPERIMENTS/round26_alert_alpha/final_audit/v4"

TS_LO = int(datetime(2025, 9, 28, tzinfo=timezone.utc).timestamp() * 1000)
TS_HI = int(datetime(2026, 5, 28, tzinfo=timezone.utc).timestamp() * 1000)  # ts<HI 即警报到05-27
COST_RT = 0.94
ENTRY_TOL_MS = 180_000
EXIT_TOL_MS = 300_000
HOLD_B = 240
HOLD_C2 = 1440
CRASH_DAY = "2025-10-10"


def utc_day(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000, timezone.utc).strftime("%Y-%m-%d")


def rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6  # macOS: bytes


# ---------------------------------------------------------------- alerts
def load_events():
    alerts = []  # (ts, symbol, wtype, price_chg, oi_chg)
    for f in sorted(glob.glob(ALERT_DIR + "/alerts_*.jsonl")):
        if "/._" in f:
            continue
        for line in open(f):
            try:
                a = json.loads(line)
            except Exception:
                continue
            alerts.append((a["ts_ms"], a["symbol"], a.get("window_type"),
                           a.get("price_chg_pct"), a.get("oi_chg_pct")))
    # 广度: 同分钟全市场警报总数(所有窗口类型, 全corpus, 与panel语义一致)
    bmin = Counter(ts // 60000 for ts, *_ in alerts)
    inw = [a for a in alerts if TS_LO <= a[0] < TS_HI]

    # B: breadth>=16 & price_chg<=-2.5, 去重(symbol, ts//1800000) 保留首条
    b_raw = [a for a in inw
             if bmin[a[0] // 60000] >= 16 and a[3] is not None and a[3] <= -2.5]
    b_raw.sort(key=lambda x: x[0])
    seen, b_events = set(), []
    for a in b_raw:
        k = (a[1], a[0] // 1_800_000)
        if k in seen:
            continue
        seen.add(k)
        b_events.append(a)

    # OI基线(全部oi_price_1h) + C2子集标记
    oi_events = [a for a in inw if a[2] == "oi_price_1h"]
    oi_events.sort(key=lambda x: x[0])
    return b_events, oi_events, len(b_raw), len(alerts), len(inw)


# ---------------------------------------------------------------- evaluator
class Drops:
    def __init__(self):
        self.no_klines = 0
        self.entry_miss = 0
        self.exit_miss = 0
        self.bad_price = 0

    def as_dict(self):
        return dict(no_klines=self.no_klines, entry_miss=self.entry_miss,
                    exit_miss=self.exit_miss, bad_price=self.bad_price)


def eval_symbol(ot, cl, ts, hold_min, side, drops):
    """统一评估器. 返回 (net_pct, raw_pct, entry_t, exit_t) 或 None(丢弃)."""
    n = len(ot)
    i = int(np.searchsorted(ot, ts - 59_999))      # 第一根 ot+60000 > ts
    if i >= n or ot[i] + 60_000 - ts > ENTRY_TOL_MS:
        drops.entry_miss += 1
        return None
    entry = float(cl[i])
    if not np.isfinite(entry) or entry <= 0:
        drops.bad_price += 1
        return None
    entry_t = int(ot[i]) + 60_000
    target = entry_t + hold_min * 60_000
    j = int(np.searchsorted(ot, target))           # 第一根 ot >= target
    if j >= n or ot[j] - target > EXIT_TOL_MS:
        drops.exit_miss += 1
        return None
    exitp = float(cl[j])
    if not np.isfinite(exitp) or exitp <= 0:
        drops.bad_price += 1
        return None
    exit_t = int(ot[j]) + 60_000
    raw = (exitp - entry) / entry * 100.0
    if side == "SHORT":
        raw = -raw
    return raw - COST_RT, raw, entry_t, exit_t


# ---------------------------------------------------------------- aggregation
def day_stats(trades):
    """trades: list of dict(net, day). 返回事件级+按天等权统计."""
    if not trades:
        return dict(n=0)
    nets = np.array([t["net"] for t in trades])
    by_day = defaultdict(list)
    for t in trades:
        by_day[t["day"]].append(t["net"])
    dmeans = np.array([np.mean(v) for v in by_day.values()])
    return dict(
        n=len(nets), net_mean=round(float(nets.mean()), 4),
        net_median=round(float(np.median(nets)), 4),
        win_rate=round(float((nets > 0).mean()), 4),
        n_days=len(by_day),
        day_mean=round(float(dmeans.mean()), 4),
        day_median=round(float(np.median(dmeans)), 4),
        pos_day_ratio=round(float((dmeans > 0).mean()), 4),
        worst_day=min(by_day, key=lambda d: np.mean(by_day[d])),
        worst_day_mean=round(float(dmeans.min()), 4),
        best_day=max(by_day, key=lambda d: np.mean(by_day[d])),
        best_day_mean=round(float(dmeans.max()), 4),
    )


def monthly_breakdown(trades):
    by_m = defaultdict(list)
    for t in trades:
        by_m[t["day"][:7]].append(t)
    out = {}
    for m in sorted(by_m):
        out[m] = day_stats(by_m[m])
    return out


def top_contrib_day(trades):
    s = defaultdict(float)
    for t in trades:
        s[t["day"]] += t["net"]
    d = max(s, key=s.get)
    return d, round(s[d], 2)


def main():
    t0 = time.time()
    b_events, oi_events, b_raw_n, n_all, n_inw = load_events()
    n_c2 = sum(1 for a in oi_events if a[4] is not None and a[4] > 15)
    print(f"alerts total={n_all} in-window={n_inw}; B raw={b_raw_n} dedup={len(b_events)}; "
          f"oi_price_1h={len(oi_events)} (C2={n_c2}); RSS={rss_mb():.2f}GB", flush=True)

    # 按symbol分组
    by_sym = defaultdict(lambda: {"B": [], "OI": []})
    for a in b_events:
        by_sym[a[1]]["B"].append(a)
    for a in oi_events:
        by_sym[a[1]]["OI"].append(a)

    kc = sqlite3.connect(f"file:{KL_DB}?mode=ro", uri=True)
    kc.execute("PRAGMA cache_size=-100000")
    ac = sqlite3.connect(f"file:{AUX_DB}?mode=ro", uri=True)
    fund_lo, fund_hi = ac.execute(
        "SELECT min(funding_time_ms), max(funding_time_ms) FROM funding").fetchone()

    drops_b, drops_oi = Drops(), Drops()
    trades_b, trades_oi = [], []   # OI记录含 is_c2 / funding 字段
    fund_uncov = 0

    syms = sorted(by_sym)
    for k, sym in enumerate(syms, 1):
        evs = by_sym[sym]
        all_ts = [a[0] for a in evs["B"]] + [a[0] for a in evs["OI"]]
        hold_max = HOLD_C2 if evs["OI"] else HOLD_B
        lo = min(all_ts) - 70_000
        hi = max(all_ts) + 60_000 + ENTRY_TOL_MS + hold_max * 60_000 + EXIT_TOL_MS + 120_000
        rows = kc.execute(
            "SELECT open_time_ms, close FROM klines_1m WHERE symbol=? AND "
            "open_time_ms BETWEEN ? AND ? ORDER BY open_time_ms", (sym, lo, hi)).fetchall()
        if not rows:
            drops_b.no_klines += len(evs["B"])
            drops_oi.no_klines += len(evs["OI"])
            continue
        arr = np.array(rows, dtype=np.float64)
        del rows
        ot = arr[:, 0].astype(np.int64)
        cl = arr[:, 1]

        for a in evs["B"]:
            r = eval_symbol(ot, cl, a[0], HOLD_B, "LONG", drops_b)
            if r is None:
                continue
            net, raw, et, xt = r
            trades_b.append(dict(sym=sym, ts=a[0], day=utc_day(a[0]), net=net))

        oi_recs = []
        for a in evs["OI"]:
            r = eval_symbol(ot, cl, a[0], HOLD_C2, "SHORT", drops_oi)
            if r is None:
                continue
            net, raw, et, xt = r
            oi_recs.append(dict(sym=sym, ts=a[0], day=utc_day(a[0]), net=net,
                                is_c2=(a[4] is not None and a[4] > 15),
                                entry_t=et, exit_t=xt))
        # 资金费: 仅C2 trade需要
        c2_here = [t for t in oi_recs if t["is_c2"]]
        if c2_here:
            fr = ac.execute("SELECT funding_time_ms, funding_rate FROM funding "
                            "WHERE symbol=? ORDER BY funding_time_ms", (sym,)).fetchall()
            if fr:
                fa = np.array(fr, dtype=np.float64)
                ft, frate = fa[:, 0], fa[:, 1]
                smin, smax = ft[0], ft[-1]
            for t in c2_here:
                if (not fr) or t["entry_t"] < smin or t["exit_t"] > smax:
                    t["fund_adj"] = None        # 覆盖不完整 -> 不进修正子集
                    fund_uncov += 1
                else:
                    m = (ft > t["entry_t"]) & (ft <= t["exit_t"])
                    t["fund_adj"] = float(frate[m].sum()) * 100.0
        for t in oi_recs:
            t.pop("entry_t", None); t.pop("exit_t", None)
        trades_oi.extend(oi_recs)
        del arr, ot, cl
        if k % 80 == 0 or k == len(syms):
            print(f"  [{k}/{len(syms)}] {sym} | B={len(trades_b)} OI={len(trades_oi)} "
                  f"| {time.time()-t0:.0f}s RSS={rss_mb():.2f}GB", flush=True)

    trades_c2 = [t for t in trades_oi if t["is_c2"]]
    res = {"meta": dict(
        window=["2025-09-28", "2026-05-27"], cost_rt=COST_RT,
        entry_tol_s=180, exit_tol_s=300, alerts_total=n_all, alerts_in_window=n_inw,
        b_raw=b_raw_n, b_dedup=len(b_events), oi_all=len(oi_events), c2_selected=n_c2,
        drops_b=drops_b.as_dict(), drops_oi=drops_oi.as_dict(),
        funding_coverage=[utc_day(fund_lo), utc_day(fund_hi)],
        c2_funding_uncovered=fund_uncov, runtime_s=round(time.time() - t0, 1))}

    # ---- 1. B 全周期
    res["B_full"] = day_stats(trades_b)
    res["B_monthly"] = monthly_breakdown(trades_b)
    res["B_per_day"] = {d: dict(n=len(v), mean=round(float(np.mean(v)), 3),
                                sum=round(float(np.sum(v)), 2))
                        for d, v in sorted(
                            {d: [t["net"] for t in trades_b if t["day"] == d]
                             for d in {t["day"] for t in trades_b}}.items())}

    # ---- 2. B LODO
    b_ex_crash = [t for t in trades_b if t["day"] != CRASH_DAY]
    res["B_lodo_ex_20251010"] = day_stats(b_ex_crash)
    top_d, top_sum = top_contrib_day(trades_b)
    res["B_top_contrib_day"] = dict(day=top_d, sum_net=top_sum)
    res["B_lodo_ex_top_day"] = day_stats([t for t in trades_b if t["day"] != top_d])
    # 双重LODO: 同时去掉10-10和top day(若不同)
    if top_d != CRASH_DAY:
        res["B_lodo_ex_both"] = day_stats(
            [t for t in trades_b if t["day"] not in (CRASH_DAY, top_d)])

    # ---- 3. B 容量现实: 每30min簇只取前3个事件
    by_bucket = defaultdict(list)
    for t in sorted(trades_b, key=lambda x: x["ts"]):
        by_bucket[t["ts"] // 1_800_000].append(t)
    b_cap = [t for v in by_bucket.values() for t in v[:3]]
    res["B_capacity_top3_per_30min"] = day_stats(b_cap)
    res["B_capacity_top3_ex_20251010"] = day_stats(
        [t for t in b_cap if t["day"] != CRASH_DAY])

    # ---- 4. C2 全周期 + 同日配对超额
    res["C2_full"] = day_stats(trades_c2)
    res["C2_monthly"] = monthly_breakdown(trades_c2)
    res["OI_base_full"] = day_stats(trades_oi)
    c2_by_day = defaultdict(list)
    base_by_day = defaultdict(list)
    for t in trades_c2:
        c2_by_day[t["day"]].append(t["net"])
    for t in trades_oi:
        base_by_day[t["day"]].append(t["net"])
    excess_days = {d: float(np.mean(c2_by_day[d]) - np.mean(base_by_day[d]))
                   for d in c2_by_day}
    ex_arr = np.array(list(excess_days.values()))
    res["C2_excess_paired"] = dict(
        n_days=len(ex_arr), excess_day_mean=round(float(ex_arr.mean()), 4),
        excess_day_median=round(float(np.median(ex_arr)), 4),
        pos_day_ratio=round(float((ex_arr > 0).mean()), 4))
    exm = defaultdict(list)
    for d, v in excess_days.items():
        exm[d[:7]].append(v)
    res["C2_excess_monthly"] = {m: dict(
        n_days=len(v), excess_mean=round(float(np.mean(v)), 4),
        pos_day_ratio=round(float(np.mean(np.array(v) > 0)), 4))
        for m, v in sorted(exm.items())}

    # ---- 5. C2 资金费修正 (完整覆盖子集, 配对前后)
    cov = [t for t in trades_c2 if t.get("fund_adj") is not None]
    if cov:
        pre = [dict(net=t["net"], day=t["day"]) for t in cov]
        post = [dict(net=t["net"] + t["fund_adj"], day=t["day"]) for t in cov]
        adj = np.array([t["fund_adj"] for t in cov])
        res["C2_funding"] = dict(
            n_covered=len(cov), n_uncovered=fund_uncov,
            mean_funding_adj_pct=round(float(adj.mean()), 4),
            pos_adj_ratio=round(float((adj > 0).mean()), 4),
            pre=day_stats(pre), post=day_stats(post))

    # ---- 6. C2 LODO
    res["C2_lodo_ex_20251010"] = day_stats(
        [t for t in trades_c2 if t["day"] != CRASH_DAY])
    top_d2, top_sum2 = top_contrib_day(trades_c2)
    res["C2_top_contrib_day"] = dict(day=top_d2, sum_net=top_sum2)
    res["C2_lodo_ex_top_day"] = day_stats(
        [t for t in trades_c2 if t["day"] != top_d2])
    if top_d2 != CRASH_DAY:
        res["C2_lodo_ex_both"] = day_stats(
            [t for t in trades_c2 if t["day"] not in (CRASH_DAY, top_d2)])
    ex_wo = {d: v for d, v in excess_days.items() if d != CRASH_DAY}
    ea = np.array(list(ex_wo.values()))
    res["C2_excess_ex_20251010"] = dict(
        n_days=len(ea), excess_day_mean=round(float(ea.mean()), 4),
        pos_day_ratio=round(float((ea > 0).mean()), 4))

    res["meta"]["runtime_s"] = round(time.time() - t0, 1)
    res["meta"]["max_rss_gb"] = round(rss_mb(), 3)
    out = os.path.join(OUT_DIR, "v4_results.json")
    json.dump(res, open(out, "w"), indent=1, ensure_ascii=False)
    print(json.dumps(res, indent=1, ensure_ascii=False), flush=True)
    print(f"\nwritten -> {out}  ({time.time()-t0:.0f}s, maxRSS {rss_mb():.2f}GB)", flush=True)


if __name__ == "__main__":
    main()
