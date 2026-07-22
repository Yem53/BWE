#!/usr/bin/env python3
"""stockusbinance paper 引擎 v3: v2 基础上把"资金费倾斜"做成可开关的口径对比。

相对 v2 (paper_engine.py) 的改动 (原文件不动):
- funding_mode: "on"(并入真实8h结算, 同 v2) / "off"(完全不算资金费, 用于增量对照)。
- tilt: True 时启用"资金费倾斜过滤"——只交易资金费方向**有利或中性**的信号:
    long 且 entry 时点最近一笔结算费率 <= 0  (持多收钱/不付钱)
    short 且 entry 时点最近一笔结算费率 >= 0  (持空收钱/不付钱)
  不利信号 (long+正费率 / short+负费率) 标记 skip 并计数, 不计入统计。
  ⚠️ tilt 门用的是**因果**费率: entry_ts 之前最后一笔已结算 funding_rate (决策时可观测),
     不是用持仓窗口内的实现费率 (那是 hindsight)。
- funding_cost 窗口修正: 用 (entry_ts, exit_ts] 半开区间 (funding_time > entry, <= exit),
  避免把"进场同一时刻、你尚未持有"的那笔结算算进成本; 与 tilt 门的 "<=entry" 互补不重叠。

资金费记账保持 v2 的正确性: 做多付正费率=成本, 做空收正费率=收益; 真实结算序列求和, 非年化粗算。
回测优先 bf_* (历史真实价/费); forward 补充。
"""
import json, os, sqlite3, math
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(DIR, "tradfi_capture_ec2.sqlite3")
BRIDGED = os.path.join(DIR, "bridged_signals.jsonl")

TAKER_FEE = 0.0004                 # 单边taker费(永续标准)
FUND_ANNUAL_FALLBACK = {"MUUSDT": 0.26, "QQQUSDT": 0.19, "NVDAUSDT": 0.006, "_default": 0.05}


def conn():
    return sqlite3.connect("file:%s?mode=ro" % DB, uri=True) if os.path.exists(DB) else None


def has_table(c, t):
    return c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (t,)).fetchone() is not None


def first_bar_after(c, sym, ts_ms, ktab, max_delay_ms=2 * 3600000):
    """因果: 取收盘时刻(ot+60000) 严格 > ts 的第一根bar。返回(close_ts, close_px)或(None,None)。"""
    r = c.execute("SELECT ot+60000, c FROM %s WHERE symbol=? AND ot+60000>? AND ot+60000<=? ORDER BY ot ASC LIMIT 1" % ktab,
                  (sym, ts_ms, ts_ms + max_delay_ms)).fetchone()
    if r and r[1] and r[1] > 0 and math.isfinite(r[1]):
        return int(r[0]), float(r[1])
    return None, None


def half_spread(c, sym, ts_ms):
    """该symbol在ts附近的实测半点差(bp→小数)。无book则用历史中位估; 再无则保守0.05%。"""
    if has_table(c, "book"):
        r = c.execute("SELECT spread_bp FROM book WHERE symbol=? AND ts<=? ORDER BY ts DESC LIMIT 1",
                      (sym, ts_ms)).fetchone()
        if r and r[0] and r[0] > 0:
            return (r[0] / 2) / 1e4
        r2 = c.execute("SELECT spread_bp FROM book WHERE symbol=? AND spread_bp>0", (sym,)).fetchall()
        if r2:
            vals = sorted(x[0] for x in r2); med = vals[len(vals) // 2]
            return (med / 2) / 1e4
    return 0.0005


def funding_rate_at_entry(c, sym, entry_ts):
    """因果倾斜门用: entry_ts 之前(含)最后一笔已结算 funding_rate。无数据→None。"""
    if has_table(c, "bf_funding"):
        r = c.execute("SELECT funding_rate FROM bf_funding WHERE symbol=? AND funding_time<=? ORDER BY funding_time DESC LIMIT 1",
                      (sym, entry_ts)).fetchone()
        if r is not None:
            return float(r[0])
    return None


def funding_cost(c, sym, t0, t1, side, mode="on"):
    """真实8h资金费累加(bf_funding), 半开区间 (t0, t1]。
    做多付正费率→成本为正(net 里被减)。mode='off' 直接返回0(不算资金费口径)。
    缺数据回退年化基线(不返回0, 宁可高估)。"""
    if mode == "off":
        return 0.0
    if has_table(c, "bf_funding"):
        rows = c.execute("SELECT funding_rate FROM bf_funding WHERE symbol=? AND funding_time>? AND funding_time<=?",
                         (sym, t0, t1)).fetchall()
        if rows:
            total = sum(r[0] for r in rows)
            return total if side == "long" else -total
        # 窗口内确实无结算(短持仓/数据空档): 该 symbol 有数据时返回 0 是正确的
        any_row = c.execute("SELECT 1 FROM bf_funding WHERE symbol=? LIMIT 1", (sym,)).fetchone()
        if any_row is not None:
            return 0.0
    ann = FUND_ANNUAL_FALLBACK.get(sym, FUND_ANNUAL_FALLBACK["_default"])
    days = (t1 - t0) / 86400000
    est = ann / 365 * days
    return est if side == "long" else -est


def eval_signals(c, hold_days=5, funding_mode="on", tilt=False):
    """返回 (trades, diag)。funding_mode: on/off。tilt: 是否启用资金费倾斜过滤。"""
    if not os.path.exists(BRIDGED):
        return [], {}
    sigs = [json.loads(l) for l in open(BRIDGED)]
    ktab = "bf_klines_1m" if has_table(c, "bf_klines_1m") else "klines_1m"
    trades = []
    diag = {"no_entry": 0, "no_exit_future": 0, "bad_price": 0, "tilt_skip": 0, "ok": 0}
    for s in sigs:
        sym = s["symbol"]; side = s["side"]
        try:
            ra = s["recorded_at"].replace("Z", "+00:00")
            dt = datetime.fromisoformat(ra)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=ZoneInfo("America/New_York"))
            t_sig = int(dt.astimezone(timezone.utc).timestamp() * 1000)
        except Exception:
            continue
        entry_ts, entry = first_bar_after(c, sym, t_sig, ktab)
        if entry is None:
            diag["no_entry"] += 1; continue
        t_exit_target = entry_ts + hold_days * 86400000
        exit_ts, exit_px = first_bar_after(c, sym, t_exit_target, ktab, max_delay_ms=300000)
        if exit_ts is None:
            diag["no_exit_future"] += 1; continue
        if exit_ts < t_exit_target:
            diag["bad_price"] += 1; continue
        if not (entry and exit_px and entry > 0 and exit_px > 0 and math.isfinite(entry) and math.isfinite(exit_px)):
            diag["bad_price"] += 1; continue

        # 因果倾斜门: 用 entry 时点最近结算费率判方向是否有利
        rate_entry = funding_rate_at_entry(c, sym, entry_ts)
        favorable = None
        if rate_entry is not None:
            favorable = (side == "long" and rate_entry <= 0) or (side == "short" and rate_entry >= 0)
        if tilt:
            # rate 未知时保守: 视为不利? 这里选择"未知=放行"(本数据集 11 标的全有费率, 不触发)
            if favorable is False:
                diag["tilt_skip"] += 1; continue

        hs_in = half_spread(c, sym, entry_ts); hs_out = half_spread(c, sym, exit_ts)
        if side == "long":
            eff_entry = entry * (1 + hs_in); eff_exit = exit_px * (1 - hs_out)
            raw = (eff_exit - eff_entry) / eff_entry
        else:
            eff_entry = entry * (1 - hs_in); eff_exit = exit_px * (1 + hs_out)
            raw = (eff_entry - eff_exit) / eff_entry
        fund = funding_cost(c, sym, entry_ts, exit_ts, side, mode=funding_mode)
        net = raw - 2 * TAKER_FEE - fund

        stock_5d = None
        oc = s.get("outcomes") or {}
        if isinstance(oc, dict):
            stock_5d = (oc.get("5d") or {}).get("return_pct")
        trades.append({
            "signal_id": s.get("signal_id"), "symbol": sym, "side": side,
            "tradeable": s.get("tradeable"), "confidence": s.get("confidence"),
            "entry": round(entry, 4), "exit": round(exit_px, 4),
            "raw_pct": round(raw * 100, 3), "net_pct": round(net * 100, 3),
            "fund_pct": round(fund * 100, 3),
            "rate_at_entry": rate_entry, "tilt_favorable": favorable,
            "half_spread_bp": round(hs_in * 1e4, 2),
            "stock_5d_pct": stock_5d, "hold_days": hold_days,
        })
        diag["ok"] += 1
    return trades, diag


def stats(nets):
    import statistics as st
    if not nets:
        return None
    wins = sum(1 for x in nets if x > 0)
    return {"n": len(nets), "mean": st.mean(nets), "median": st.median(nets),
            "winrate": 100 * wins / len(nets)}


def run_three_regimes(hold_days=5):
    """同 29 信号, 三口径: (a)无资金费 (b)含资金费 (c)含资金费+倾斜。返回结构化结果。"""
    c = conn()
    if c is None:
        return None
    out = {}
    a, da = eval_signals(c, hold_days, funding_mode="off", tilt=False)
    b, db = eval_signals(c, hold_days, funding_mode="on", tilt=False)
    cc, dc = eval_signals(c, hold_days, funding_mode="on", tilt=True)
    out["a_no_funding"] = {"trades": a, "diag": da}
    out["b_with_funding"] = {"trades": b, "diag": db}
    out["c_funding_tilt"] = {"trades": cc, "diag": dc}
    return out


if __name__ == "__main__":
    import statistics as st
    res = run_three_regimes(hold_days=5)
    if res is None:
        print("DB 未就绪"); raise SystemExit
    for tag, label in [("a_no_funding", "(a) 不含资金费"),
                       ("b_with_funding", "(b) 含资金费"),
                       ("c_funding_tilt", "(c) 含资金费+倾斜")]:
        tr = res[tag]["trades"]
        nets = [t["net_pct"] for t in tr]
        s = stats(nets)
        shorts = [t["net_pct"] for t in tr if t["side"] == "short"]
        ss = stats(shorts)
        print("### %s  n=%d  diag=%s" % (label, len(tr), res[tag]["diag"]))
        if s:
            print("  全体: 均%+.3f%% 中%+.3f%% 胜%.0f%%" % (s["mean"], s["median"], s["winrate"]))
        if ss:
            print("  做空: n=%d 均%+.3f%% 中%+.3f%% 胜%.0f%%" % (ss["n"], ss["mean"], ss["median"], ss["winrate"]))
