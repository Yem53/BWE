#!/usr/bin/env python3
"""终审V3: 幸存者偏差定界 — 量化"被静默丢弃的交易"对 B / C2 holdout 结论的最坏影响。

丢弃分类(每笔 frozen 规则触发的交易):
  filled        正常成交(进+出都有bar)
  no_klines     (a) symbol 在 holdout 库完全无K线
  no_entry      (b) 有K线但警报后180s内无进场bar
  no_exit_cut   (c-可疑) 进场OK, 出场target在全局数据范围内, 但该symbol流提前终止
  no_exit_gap   (c-可疑) 进场OK, target处有>300s断口, 数据之后又恢复(停牌/断流)
  no_exit_tail  (c-正常) target 超出全局数据末端(窗口尾部截断)

定界:
  worst  可疑丢弃(a+b+cut+gap)按 min(观测分布p1, -10[B]/-15[C2]) 计入
         C2 超额额外让 baseline 的可疑丢弃按 0% 计入(最大化抬高基线)
  base   只用成交样本(现行结论)
  optim  可疑丢弃按 0% 计入

进出场(frozen, bug-e 修正版): 进=第一根 ot+60000>ts 的bar收盘(tol 180s);
出=第一根 ot >= 进场bar收盘时刻+持有 的bar(tol 300s); 成本 0.94% RT。
"""
import bisect
import glob
import json
import os
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone

import numpy as np

DIR = "/Volumes/T9/BWE/40_EXPERIMENTS/round26_alert_alpha"
OUT_DIR = os.path.join(DIR, "final_audit", "v3")
HOLD_KL = os.path.join(DIR, "crypto_holdout.sqlite3")
ARCHIVE = "/Volumes/T9/BWE/30_DATA/binance_collectors_runtime/binance_futures_klines_archive.sqlite3"
ALERTS = "/Volumes/T9/BWE/30_DATA/bwe_scanner_alerts"

HOLDOUT_LO = int(datetime(2026, 5, 30, tzinfo=timezone.utc).timestamp() * 1000)
HOLDOUT_HI = int(datetime(2026, 6, 9, tzinfo=timezone.utc).timestamp() * 1000)
COST_RT = 0.94          # % round trip
ENTRY_TOL = 180_000     # ms
EXIT_TOL = 300_000      # ms
MS_MIN = 60_000

kc = sqlite3.connect("file:%s?mode=ro" % HOLD_KL, uri=True)
GLOBAL_END = kc.execute("SELECT MAX(ot) FROM klines_1m WHERE symbol='BTCUSDT'").fetchone()[0]
HOLD_SYMBOLS = {r[0] for r in kc.execute("SELECT DISTINCT symbol FROM klines_1m")}

# K线窗口: 进场最早 05-30 00:00, 出场最晚 06-10 00:06 + tol
KL_LO = HOLDOUT_LO - 3_600_000
KL_HI = HOLDOUT_HI + 1440 * MS_MIN + 1_800_000
_kl_cache: dict = {}


def get_kl(sym: str):
    if sym in _kl_cache:
        return _kl_cache[sym]
    rows = kc.execute(
        "SELECT ot, c FROM klines_1m WHERE symbol=? AND ot BETWEEN ? AND ? ORDER BY ot",
        (sym, KL_LO, KL_HI)).fetchall()
    if rows:
        ot = np.fromiter((r[0] for r in rows), dtype=np.int64, count=len(rows))
        cl = np.fromiter((r[1] for r in rows), dtype=np.float64, count=len(rows))
        _kl_cache[sym] = (ot, cl)
    else:
        _kl_cache[sym] = None
    return _kl_cache[sym]


def fill(sym: str, ts: int, hold_min: int, side: str):
    """返回 (status, net_ret_or_None, detail)."""
    if sym not in HOLD_SYMBOLS:
        return ("no_klines", None, "")
    a = get_kl(sym)
    if a is None:
        return ("no_klines", None, "window_empty")  # 库里有symbol但窗口内无bar
    ot, cl = a
    # 进场: 第一根 ot + 60000 > ts ⇔ 第一根 ot > ts - 60000
    i = bisect.bisect_right(ot, ts - MS_MIN)
    if i >= len(ot):
        return ("no_entry", None, "stream_ended_before_alert")
    if ot[i] + MS_MIN - ts > ENTRY_TOL:
        return ("no_entry", None, "gap_at_alert(next_bar_%+dmin)" % ((ot[i] + MS_MIN - ts) // MS_MIN))
    entry = float(cl[i])
    if entry <= 0:
        return ("no_entry", None, "bad_price")
    target = int(ot[i]) + MS_MIN + hold_min * MS_MIN
    j = bisect.bisect_left(ot, target)
    if j >= len(ot):
        if target > GLOBAL_END - EXIT_TOL:
            return ("no_exit_tail", None, "")
        return ("no_exit_cut", None,
                "sym_last_bar=%s target=%s" % (iso(int(ot[-1])), iso(target)))
    if ot[j] - target > EXIT_TOL:
        return ("no_exit_gap", None,
                "gap %.0fmin at exit, resumed later" % ((ot[j] - target) / MS_MIN))
    px = float(cl[j])
    raw = (px - entry) / entry * 100.0 if side == "long" else (entry - px) / entry * 100.0
    return ("filled", raw - COST_RT, "")


def iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%m-%dT%H:%M")


def day_of(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def load_alerts():
    out = []
    for f in sorted(glob.glob(ALERTS + "/*.jsonl")):
        d = os.path.basename(f).split("alerts_")[1][:10]
        if d < "2026-05-29" or d > "2026-06-09":
            continue
        for line in open(f):
            try:
                a = json.loads(line)
            except Exception:
                continue
            if HOLDOUT_LO <= a["ts_ms"] < HOLDOUT_HI:
                out.append(a)
    out.sort(key=lambda a: a["ts_ms"])
    return out


def load_alerts_wide():
    """重建用: 05-29 ~ 06-11 全部警报(出场target可越过06-09)。"""
    out = []
    for f in sorted(glob.glob(ALERTS + "/*.jsonl")):
        d = os.path.basename(f).split("alerts_")[1][:10]
        if d < "2026-05-29" or d > "2026-06-11":
            continue
        for line in open(f):
            try:
                a = json.loads(line)
            except Exception:
                continue
            out.append(a)
    return out


def simulate(trades, hold_min, side):
    """trades: list of alert dicts. 返回 detail list."""
    res = []
    for a in trades:
        st, ret, det = fill(a["symbol"], a["ts_ms"], hold_min, side)
        res.append({"symbol": a["symbol"], "ts_ms": a["ts_ms"], "day": day_of(a["ts_ms"]),
                    "status": st, "net_ret": ret, "detail": det})
    return res


SUSPECT = ("no_klines", "no_entry", "no_exit_cut", "no_exit_gap")


def stats(label, res, worst_floor):
    filled = [r for r in res if r["status"] == "filled"]
    rets = np.array([r["net_ret"] for r in filled])
    n_susp = sum(1 for r in res if r["status"] in SUSPECT)
    n_tail = sum(1 for r in res if r["status"] == "no_exit_tail")
    p1 = float(np.percentile(rets, 1)) if len(rets) else float("nan")
    worst_fill = min(p1, worst_floor)

    def daily(extra_fill=None):
        by_day = defaultdict(list)
        for r in res:
            if r["status"] == "filled":
                by_day[r["day"]].append(r["net_ret"])
            elif extra_fill is not None and r["status"] in SUSPECT:
                by_day[r["day"]].append(extra_fill)
        days = sorted(by_day)
        means = {d: float(np.mean(by_day[d])) for d in days}
        return means

    def scen(extra_fill):
        arr = rets if extra_fill is None else np.concatenate([rets, np.full(n_susp, extra_fill)])
        dm = daily(extra_fill)
        vals = list(dm.values())
        return {"per_trade_mean": float(arr.mean()) if len(arr) else None,
                "n": int(len(arr)),
                "win_pct": float(100 * (arr > 0).mean()) if len(arr) else None,
                "daily_means": dm,
                "daily_mean_avg": float(np.mean(vals)) if vals else None,
                "days_pos": int(sum(v > 0 for v in vals)), "days_n": len(vals)}

    out = {"label": label,
           "n_signals": len(res), "n_filled": len(filled),
           "n_suspect_dropped": n_susp, "n_tail_truncated": n_tail,
           "drop_breakdown": dict(Counter(r["status"] for r in res if r["status"] != "filled")),
           "p1_observed": p1, "worst_fill_used": worst_fill,
           "base": scen(None), "worst": scen(worst_fill), "optim": scen(0.0)}
    return out


def main():
    alerts = load_alerts()
    print("holdout警报数(05-30 <= ts < 06-09): %d, 全局K线末端=%s" % (len(alerts), iso(GLOBAL_END)))

    # ---- 策略B: 同分钟广度>=16 & price_chg<=-2.5 → LONG 240m, 去重(symbol, ts//1800000)
    bmin = Counter(a["ts_ms"] // MS_MIN for a in alerts)
    braw = [a for a in alerts
            if bmin.get(a["ts_ms"] // MS_MIN, 0) >= 16 and (a.get("price_chg_pct") or 0) <= -2.5]
    seen, btr = set(), []
    for a in braw:  # alerts已按ts排序 → 桶内保留最早
        k = (a["symbol"], a["ts_ms"] // 1_800_000)
        if k not in seen:
            seen.add(k)
            btr.append(a)
    print("B: raw=%d dedup=%d" % (len(braw), len(btr)))
    res_b = simulate(btr, 240, "long")

    # ---- 策略C2: oi_price_1h & oi_chg>15 → SHORT 1440m (无去重, frozen原样)
    c2tr = [a for a in alerts
            if a.get("window_type") == "oi_price_1h" and (a.get("oi_chg_pct") or 0) > 15]
    print("C2: n=%d" % len(c2tr))
    res_c2 = simulate(c2tr, 1440, "short")

    # ---- C2 beta基线: 全部 oi_price_1h 警报 SHORT 1440m (全量, 不切片)
    basetr = [a for a in alerts if a.get("window_type") == "oi_price_1h"]
    print("baseline(all oi_price_1h): n=%d" % len(basetr))
    res_base = simulate(basetr, 1440, "short")

    st_b = stats("B_long_240m", res_b, -10.0)
    st_c2 = stats("C2_short_1440m", res_c2, -15.0)
    st_base = stats("BASE_all_oi_short_1440m", res_base, -15.0)

    # ---- C2 同日配对超额: scenario × (C2侧, baseline侧)
    def paired_excess(c2_extra, base_extra):
        c2d, bad = defaultdict(list), defaultdict(list)
        for r in res_c2:
            if r["status"] == "filled":
                c2d[r["day"]].append(r["net_ret"])
            elif c2_extra is not None and r["status"] in SUSPECT:
                c2d[r["day"]].append(c2_extra)
        for r in res_base:
            if r["status"] == "filled":
                bad[r["day"]].append(r["net_ret"])
            elif base_extra is not None and r["status"] in SUSPECT:
                bad[r["day"]].append(base_extra)
        days = sorted(set(c2d) & set(bad))
        ex = {d: float(np.mean(c2d[d]) - np.mean(bad[d])) for d in days}
        vals = list(ex.values())
        return {"daily_excess": ex, "mean": float(np.mean(vals)) if vals else None,
                "days_pos": int(sum(v > 0 for v in vals)), "days_n": len(vals)}

    wf_c2 = st_c2["worst_fill_used"]
    excess = {
        "base": paired_excess(None, None),
        "worst": paired_excess(wf_c2, 0.0),     # C2按worst, baseline丢弃按0%抬高基线
        "worst_sym": paired_excess(wf_c2, st_base["worst_fill_used"]),  # 对称同罚(参考)
        "optim": paired_excess(0.0, None),
    }

    # ---- 经验重建: 丢弃交易的真实收益 ≈ 用同symbol警报价流近似 (alert['price']=扫描器实时价)
    by_sym_alerts = defaultdict(list)
    for a in load_alerts_wide():  # 含06-09之后, 出场可能在窗口外
        by_sym_alerts[a["symbol"]].append((a["ts_ms"], a.get("price")))
    for v in by_sym_alerts.values():
        v.sort()

    def recon(res, hold_min, side, tol_ms):
        out = []
        for r in res:
            if r["status"] not in SUSPECT:
                continue
            sa = by_sym_alerts.get(r["symbol"], [])
            ts = r["ts_ms"]
            entry_px = next((p for t, p in sa if t == ts and p), None)
            if entry_px is None:  # 触发警报自身的价
                cand = [(abs(t - ts), p) for t, p in sa if abs(t - ts) <= 120_000 and p]
                entry_px = min(cand)[1] if cand else None
            target = ts + hold_min * MS_MIN
            cand = [(abs(t - target), t, p) for t, p in sa if abs(t - target) <= tol_ms and p]
            rec = None
            if entry_px and cand:
                off, t_exit, exit_px = min(cand)
                raw = ((exit_px - entry_px) / entry_px * 100.0 if side == "long"
                       else (entry_px - exit_px) / entry_px * 100.0)
                rec = {"net_ret": raw - COST_RT, "exit_offset_min": round((t_exit - target) / MS_MIN),
                       "entry_px": entry_px, "exit_px": exit_px}
            out.append({"symbol": r["symbol"], "day": r["day"], "ts_ms": ts, "recon": rec})
        return out

    rec_b = recon(res_b, 240, "long", 120 * MS_MIN)
    rec_c2 = recon(res_c2, 1440, "short", 360 * MS_MIN)
    rec_base = recon(res_base, 1440, "short", 360 * MS_MIN)

    def scen_recon(st, res, rec, worst_fill):
        """recon场景: 可重建的用重建值, 不可重建的用worst_fill."""
        fills = [r["recon"]["net_ret"] if r["recon"] else worst_fill for r in rec]
        rets = np.array([r["net_ret"] for r in res if r["status"] == "filled"] + fills)
        by_day = defaultdict(list)
        for r in res:
            if r["status"] == "filled":
                by_day[r["day"]].append(r["net_ret"])
        for r, f in zip(rec, fills):
            by_day[r["day"]].append(f)
        vals = [float(np.mean(v)) for v in by_day.values()]
        st["recon"] = {"per_trade_mean": float(rets.mean()), "n": int(len(rets)),
                       "n_reconstructed": sum(1 for r in rec if r["recon"]),
                       "n_fallback_worst": sum(1 for r in rec if not r["recon"]),
                       "daily_mean_avg": float(np.mean(vals)),
                       "days_pos": int(sum(v > 0 for v in vals)), "days_n": len(vals)}
        return {r2["ts_ms"]: f for r2, f in zip(rec, fills)}

    fills_b = scen_recon(st_b, res_b, rec_b, st_b["worst_fill_used"])
    fills_c2 = scen_recon(st_c2, res_c2, rec_c2, st_c2["worst_fill_used"])
    fills_base = scen_recon(st_base, res_base, rec_base, st_base["worst_fill_used"])

    def paired_excess_fills(c2_fills, base_fills):
        c2d, bad = defaultdict(list), defaultdict(list)
        for r in res_c2:
            if r["status"] == "filled":
                c2d[r["day"]].append(r["net_ret"])
            elif r["status"] in SUSPECT:
                c2d[r["day"]].append(c2_fills[r["ts_ms"]])
        for r in res_base:
            if r["status"] == "filled":
                bad[r["day"]].append(r["net_ret"])
            elif r["status"] in SUSPECT:
                bad[r["day"]].append(base_fills[r["ts_ms"]])
        days = sorted(set(c2d) & set(bad))
        vals = [float(np.mean(c2d[d]) - np.mean(bad[d])) for d in days]
        return {"mean": float(np.mean(vals)), "days_pos": int(sum(v > 0 for v in vals)),
                "days_n": len(vals)}

    excess["recon"] = paired_excess_fills(fills_c2, fills_base)

    # ---- 丢弃symbol明细 + 8个月归档存在性
    def drop_syms(res):
        d = defaultdict(lambda: defaultdict(int))
        for r in res:
            if r["status"] != "filled":
                d[r["status"]][r["symbol"]] += 1
        return {k: dict(v) for k, v in d.items()}

    drops = {"B": drop_syms(res_b), "C2": drop_syms(res_c2), "BASE": drop_syms(res_base)}
    check_syms = sorted({s for strat in drops.values() for cls in strat.values() for s in cls})
    arch = {}
    if os.path.exists(ARCHIVE):
        ac = sqlite3.connect("file:%s?mode=ro" % ARCHIVE, uri=True)
        for s in check_syms:
            row = ac.execute("SELECT MIN(open_time_ms), MAX(open_time_ms) FROM klines_1m "
                             "WHERE symbol=?", (s,)).fetchone()
            arch[s] = None if row[0] is None else {
                "first": iso(row[0]), "last": iso(row[1]),
                "in_holdout_db": s in HOLD_SYMBOLS}
        ac.close()

    # 丢弃交易逐笔明细(可疑类)
    detail = {name: [
        {k: r[k] for k in ("symbol", "ts_ms", "day", "status", "detail")}
        for r in res if r["status"] != "filled"]
        for name, res in (("B", res_b), ("C2", res_c2))}

    # 丢弃symbol的警报生命线(证明是否退市): 全archive范围 first/last alert
    lifespan = {}
    for s in check_syms:
        ts_list = []
        for f in sorted(glob.glob(ALERTS + "/*.jsonl")):
            for line in open(f):
                if s not in line:
                    continue
                try:
                    a = json.loads(line)
                except Exception:
                    continue
                if a.get("symbol") == s:
                    ts_list.append(a["ts_ms"])
        if ts_list:
            lifespan[s] = {"first_alert": iso(min(ts_list)), "last_alert": iso(max(ts_list)),
                           "n_alerts_total": len(ts_list),
                           "alive_past_holdout_end": max(ts_list) >= HOLDOUT_HI}

    out = {"holdout": {"lo": HOLDOUT_LO, "hi": HOLDOUT_HI, "n_alerts": len(alerts),
                       "global_kline_end": iso(GLOBAL_END),
                       "n_symbols_in_holdout_db": len(HOLD_SYMBOLS)},
           "B": st_b, "C2": st_c2, "BASE": st_base,
           "C2_paired_excess": excess,
           "dropped_symbols": drops,
           "archive_check": arch,
           "dropped_symbol_alert_lifespan": lifespan,
           "reconstruction": {"B": rec_b, "C2": rec_c2,
                              "BASE_n_recon": sum(1 for r in rec_base if r["recon"])},
           "dropped_trades_detail": detail}
    with open(os.path.join(OUT_DIR, "v3_results.json"), "w") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)

    # ---- console 摘要
    for st in (st_b, st_c2, st_base):
        print("\n== %s ==" % st["label"])
        print(" signals=%d filled=%d suspect_drop=%d tail=%d breakdown=%s" % (
            st["n_signals"], st["n_filled"], st["n_suspect_dropped"],
            st["n_tail_truncated"], st["drop_breakdown"]))
        print(" p1=%.2f%% worst_fill=%.2f%%" % (st["p1_observed"], st["worst_fill_used"]))
        for sc in ("base", "worst", "optim"):
            s = st[sc]
            print(" %-5s per-trade %+0.2f%% (n=%d, win %.0f%%) | daily %+0.2f%%/d (%d/%d days pos)"
                  % (sc, s["per_trade_mean"], s["n"], s["win_pct"],
                     s["daily_mean_avg"], s["days_pos"], s["days_n"]))
        s = st["recon"]
        print(" recon per-trade %+0.2f%% (n=%d, 重建%d/兜底%d) | daily %+0.2f%%/d (%d/%d days pos)"
              % (s["per_trade_mean"], s["n"], s["n_reconstructed"], s["n_fallback_worst"],
                 s["daily_mean_avg"], s["days_pos"], s["days_n"]))
    print("\n== C2 同日配对超额 (C2 - all_oi_short) ==")
    for sc, e in excess.items():
        print(" %-9s %+0.2f%%/day (%d/%d days pos)" % (sc, e["mean"], e["days_pos"], e["days_n"]))
    print("\narchive check (dropped syms): %s" % json.dumps(arch, ensure_ascii=False))
    print("alert lifespan: %s" % json.dumps(lifespan, ensure_ascii=False))
    print("\nB dropped trades 重建明细:")
    for r in rec_b:
        print("  %s %s %s" % (r["day"], r["symbol"],
              "net%+.2f%% (exit_off%+dmin)" % (r["recon"]["net_ret"], r["recon"]["exit_offset_min"])
              if r["recon"] else "无法重建→worst兜底"))
    print("C2 dropped trades 重建明细:")
    for r in rec_c2:
        print("  %s %s %s" % (r["day"], r["symbol"],
              "net%+.2f%% (exit_off%+dmin)" % (r["recon"]["net_ret"], r["recon"]["exit_offset_min"])
              if r["recon"] else "无法重建→worst兜底"))


if __name__ == "__main__":
    main()
