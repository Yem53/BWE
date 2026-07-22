#!/usr/bin/env python3
"""β对冲诊断 (round25 stockusbinance).

诊断问题: 桥接信号 Buy侧(做多)5天 -2.08%, 是市场β污染 还是 真实个股弱alpha?
方法: 对每条信号重算 raw_return 与 β对冲后 hedged_return, 看 Buy侧对冲后是否转正。

只读 tradfi_capture_ec2.sqlite3 (bf_klines_1m) + bridged_signals.jsonl。绝不下单。

—— 严格因果与对冲符号约定 ——————————————————————————————————
进场 = 信号 recorded_at(带ET offset→UTC)后 **第一根已收盘** 1m bar 的 close
       (收盘时刻 ot+60000 严格 > t_sig; tol 180s)。
出场 = 进场收盘时刻 + 持有期(1d/5d) 后第一根已收盘 bar (tol 300s)。
       与 paper_engine.py 完全一致的因果规则。

raw_return(按 side):
  long  : (exit-entry)/entry
  short : (entry-exit)/entry      # = -(标的涨幅), 做空盈利方向已含在符号里

β对冲 (dollar-neutral, beta-weighted, 用 QQQUSDT 永续做 market proxy):
  long 标的  : 同时 **空 β份 QQQ** → hedged = raw_long  - β·qq_ret
  short 标的 : 同时 **多 β份 QQQ** → hedged = raw_short + β·qq_ret
  (两种情形对冲腿都剥离方向头寸里的市场 β 部分, 留下相对 QQQ 的个股 idiosyncratic 收益)
  自洽性: 若标的与QQQ同向同幅且β=1, long/short 的 hedged 都≈0 (纯β被抵消)。

β估计: 用该标的 **进场前** 全期 5m 收益对同窗 QQQ 5m 收益做 OLS 回归 (cov/var)。
       样本<30 点或方差异常→回退 β=1.0 并在 JSON 标注 beta_source。
       (用进场前数据避免前视; QQQ覆盖期外的早期信号回退到全期, 同样标注。)

成本:
  raw 腿     : 永续往返 0.08% (单边 0.04% taker × 2)。
  hedged     : 多一条 QQQ 对冲腿 → 共 2 腿 × 0.08% = 0.16% 往返。
  (本脚本聚焦 β 诊断, 用固定 4bp/边 简化, 不引入 paper_engine 的实测点差/资金费,
   以免把"对冲是否消除β"这一核心信号和成本模型纠缠; raw 数对照 paper_engine 已含全成本。)

样本极小 (Buy侧 n≈12, Sell侧 n≈16) → 全程探索性, 不可下结论, 这是诊断不是策略验证。
做空看 **均值** 不看中位 (防左尾)。
"""
import json
import math
import os
import sqlite3
import statistics as st
from collections import defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(DIR)
DB = os.path.join(ROOT, "tradfi_capture_ec2.sqlite3")
BRIDGED = os.path.join(ROOT, "bridged_signals.jsonl")
OUT_JSON = os.path.join(DIR, "beta_hedge_results.json")

PROXY = "QQQUSDT"
TAKER_FEE = 0.0004                  # 单边 taker
RT_ONE_LEG = 2 * TAKER_FEE          # 单腿往返 0.08%
RT_HEDGED = 2 * RT_ONE_LEG          # 两腿(标的+QQQ)往返 0.16%
ENTRY_TOL_MS = 180_000
EXIT_TOL_MS = 300_000
KTAB = "bf_klines_1m"


def conn():
    return sqlite3.connect("file:%s?mode=ro" % DB, uri=True)


def first_bar_after(c, sym, ts_ms, tol_ms):
    """因果: 收盘时刻 ot+60000 严格 > ts 的第一根 bar (tol 内)。返回 (close_ts, close_px) 或 (None, None)。"""
    r = c.execute(
        "SELECT ot+60000, c FROM %s WHERE symbol=? AND ot+60000>? AND ot+60000<=? "
        "ORDER BY ot ASC LIMIT 1" % KTAB,
        (sym, ts_ms, ts_ms + tol_ms),
    ).fetchone()
    if r and r[1] and r[1] > 0 and math.isfinite(r[1]):
        return int(r[0]), float(r[1])
    return None, None


def close_at(c, sym, target_ts, tol_ms):
    """取收盘时刻 >= target 的第一根 bar 的 close (用于 QQQ 同期点)。"""
    return first_bar_after(c, sym, target_ts - 1, tol_ms)


def series_5m(c, sym, t_end_ms, lookback_ms):
    """[t_end-lookback, t_end] 内每 5min 取一次 close, 返回按时间排序的 (ts, close) 列表 (用 1m bar 抽样)。"""
    t0 = t_end_ms - lookback_ms
    rows = c.execute(
        "SELECT ot+60000, c FROM %s WHERE symbol=? AND ot+60000>=? AND ot+60000<=? "
        "ORDER BY ot ASC" % KTAB,
        (sym, t0, t_end_ms),
    ).fetchall()
    out = []
    last_kept = None
    for ot1, px in rows:
        if px is None or px <= 0 or not math.isfinite(px):
            continue
        if last_kept is None or ot1 - last_kept >= 5 * 60_000 - 1000:
            out.append((int(ot1), float(px)))
            last_kept = ot1
    return out


def aligned_returns(s_a, s_b):
    """对齐两条 (ts, px) 序列到同一时间戳, 计算各自的 5m 对数/简单收益对。返回 (ra[], rb[])。"""
    map_b = dict(s_b)
    common = [(ts, px) for ts, px in s_a if ts in map_b]
    if len(common) < 3:
        return [], []
    ra, rb = [], []
    for i in range(1, len(common)):
        ts0, pa0 = common[i - 1]
        ts1, pa1 = common[i]
        pb0 = map_b[ts0]
        pb1 = map_b[ts1]
        if pa0 > 0 and pb0 > 0:
            ra.append((pa1 - pa0) / pa0)
            rb.append((pb1 - pb0) / pb0)
    return ra, rb


def estimate_beta(c, sym, entry_ts, lookback_days=21):
    """OLS β: 标的 5m 收益对 QQQ 5m 收益, 用进场前窗口 (避前视)。回退 1.0。"""
    lookback_ms = lookback_days * 86_400_000
    s_sym = series_5m(c, sym, entry_ts, lookback_ms)
    s_qqq = series_5m(c, PROXY, entry_ts, lookback_ms)
    ra, rb = aligned_returns(s_sym, s_qqq)
    n = len(ra)
    if n < 30:
        return 1.0, "fallback_few_points(n=%d)" % n
    var_b = st.pvariance(rb)
    if var_b <= 0 or not math.isfinite(var_b):
        return 1.0, "fallback_zero_var"
    mean_a = sum(ra) / n
    mean_b = sum(rb) / n
    cov = sum((ra[i] - mean_a) * (rb[i] - mean_b) for i in range(n)) / n
    beta = cov / var_b
    if not math.isfinite(beta) or abs(beta) > 5:
        return 1.0, "fallback_outlier_beta(%.2f)" % beta
    return beta, "ols_5m(n=%d,lookback=%dd)" % (n, lookback_days)


def to_utc_ms(recorded_at):
    ra = recorded_at.replace("Z", "+00:00")
    dt = datetime.fromisoformat(ra)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("America/New_York"))
    return int(dt.astimezone(timezone.utc).timestamp() * 1000)


def eval_signal(c, sig, hold_days):
    sym = sig["symbol"]
    side = sig["side"]
    rec = {"signal_id": sig.get("signal_id"), "symbol": sym, "side": side,
           "tradeable": sig.get("tradeable"), "hold_days": hold_days}

    t_sig = to_utc_ms(sig["recorded_at"])

    # 进场 (标的) — 因果第一根收盘 bar
    entry_ts, entry = first_bar_after(c, sym, t_sig, ENTRY_TOL_MS)
    if entry is None:
        rec["status"] = "no_entry"
        return rec
    # 出场 (标的)
    t_exit_target = entry_ts + hold_days * 86_400_000
    exit_ts, exit_px = first_bar_after(c, sym, t_exit_target, EXIT_TOL_MS)
    if exit_ts is None:
        rec["status"] = "no_exit_future"
        return rec

    # QQQ 同期: 用与标的 **相同的进/出收盘时刻** 取最接近的 QQQ 收盘 (tol 内), 保证同窗对齐
    q_entry_ts, q_entry = close_at(c, PROXY, entry_ts, EXIT_TOL_MS)
    q_exit_ts, q_exit = close_at(c, PROXY, exit_ts, EXIT_TOL_MS)
    if q_entry is None or q_exit is None:
        rec["status"] = "no_qqq_coverage"   # QQQ 数据期外 (晚期信号 5d 出场可能越界)
        return rec

    stock_ret = (exit_px - entry) / entry
    qq_ret = (q_exit - q_entry) / q_entry

    beta, beta_src = estimate_beta(c, sym, entry_ts)

    if side == "long":
        raw = stock_ret
        hedged = raw - beta * qq_ret           # 空 β 份 QQQ
    else:  # short
        raw = -stock_ret
        hedged = raw + beta * qq_ret           # 多 β 份 QQQ

    net_raw = raw - RT_ONE_LEG                  # 单腿成本
    net_hedged = hedged - RT_HEDGED            # 两腿成本

    rec.update({
        "status": "ok",
        "entry": round(entry, 4), "exit": round(exit_px, 4),
        "stock_ret_pct": round(stock_ret * 100, 3),
        "qq_ret_pct": round(qq_ret * 100, 3),
        "beta": round(beta, 3), "beta_source": beta_src,
        "raw_pct": round(raw * 100, 3),
        "hedged_pct": round(hedged * 100, 3),
        "net_raw_pct": round(net_raw * 100, 3),
        "net_hedged_pct": round(net_hedged * 100, 3),
        "stock_5d_ground_truth_pct": ((sig.get("outcomes") or {}).get("%dd" % hold_days) or {}).get("return_pct"),
    })
    return rec


def grp_stats(vals):
    n = len(vals)
    if n == 0:
        return None
    wins = sum(1 for x in vals if x > 0)
    return {"n": n, "mean": round(st.mean(vals), 3),
            "median": round(st.median(vals), 3),
            "win_rate": round(100 * wins / n, 1),
            "stdev": round(st.pstdev(vals), 3) if n > 1 else 0.0}


def main():
    sigs = [json.loads(l) for l in open(BRIDGED) if l.strip()]
    c = conn()
    nk = c.execute("SELECT COUNT(*) FROM %s" % KTAB).fetchone()[0]
    print("数据: %d 根 %s K线 | QQQ proxy=%s\n" % (nk, KTAB, PROXY))

    all_recs = []
    report = {}
    for hd in (1, 5):
        recs = [eval_signal(c, s, hd) for s in sigs]
        all_recs += recs
        ok = [r for r in recs if r["status"] == "ok"]
        dropped = defaultdict(int)
        for r in recs:
            if r["status"] != "ok":
                dropped[r["status"]] += 1

        print("=" * 78)
        print("### 持有 %dd — 可评估 %d / %d 信号 (丢弃: %s)" % (hd, len(ok), len(recs), dict(dropped)))

        block = {"n_ok": len(ok), "dropped": dict(dropped), "groups": {}}
        # 分组: side × {raw, hedged} (含成本与不含成本两版)
        for side_label, side_key in [("Buy(做多/long)", "long"), ("Sell(做空/short)", "short")]:
            sub = [r for r in ok if r["side"] == side_key]
            if not sub:
                continue
            raw_g = grp_stats([r["raw_pct"] for r in sub])
            hed_g = grp_stats([r["hedged_pct"] for r in sub])
            netr_g = grp_stats([r["net_raw_pct"] for r in sub])
            neth_g = grp_stats([r["net_hedged_pct"] for r in sub])
            # 稳健性: β=1.0 naive 市场中性对冲 (OLS β 在小样本+极端β标的上噪声大)
            hed_b1 = grp_stats([
                (r["stock_ret_pct"] - 1.0 * r["qq_ret_pct"]) if side_key == "long"
                else (-r["stock_ret_pct"] + 1.0 * r["qq_ret_pct"])
                for r in sub])
            beta_vals = [r["beta"] for r in sub]
            qq_vals = [r["qq_ret_pct"] for r in sub]
            block["groups"][side_key] = {
                "raw": raw_g, "hedged_ols_beta": hed_g, "hedged_beta1_robustness": hed_b1,
                "net_raw_1leg": netr_g, "net_hedged_2leg": neth_g,
                "avg_beta": round(st.mean(beta_vals), 3),
                "avg_qq_ret_pct": round(st.mean(qq_vals), 3),
            }
            warn = " ⚠️n<30探索性" if len(sub) < 30 else ""
            print("\n  %s  n=%d%s   平均β=%.2f  同期QQQ均%+.3f%%" % (
                side_label, len(sub), warn, st.mean(beta_vals), st.mean(qq_vals)))
            print("    raw(毛, 无成本)       均%+.3f%%  中%+.3f%%  胜%.0f%%" % (
                raw_g["mean"], raw_g["median"], raw_g["win_rate"]))
            print("    hedged(β=OLS, 无成本) 均%+.3f%%  中%+.3f%%  胜%.0f%%   ← 看均值(防左尾)" % (
                hed_g["mean"], hed_g["median"], hed_g["win_rate"]))
            print("    hedged(β=1.0 稳健)    均%+.3f%%  中%+.3f%%   ← OLS β 噪声对照" % (
                hed_b1["mean"], hed_b1["median"]))
            print("    net_raw   (1腿成本)   均%+.3f%%" % netr_g["mean"])
            print("    net_hedged(2腿成本)   均%+.3f%%" % neth_g["mean"])
        report["hold_%dd" % hd] = block

    # 写 JSON
    out = {
        "meta": {
            "purpose": "β对冲诊断: Buy侧亏损是市场β还是个股alpha",
            "proxy": PROXY, "n_signals_total": len(sigs),
            "cost_model": {"taker_per_side": TAKER_FEE, "raw_roundtrip_1leg": RT_ONE_LEG,
                           "hedged_roundtrip_2leg": RT_HEDGED},
            "hedge_convention": "long: hedged=raw-β·qq | short: hedged=raw+β·qq (剥离β, 留个股idio)",
            "beta": "OLS 5m 收益(标的~QQQ), 进场前21d窗; <30点回退1.0",
            "caveat": "样本极小(<30/侧), 探索性不可下结论, 诊断非策略验证; 做空看均值",
        },
        "summary": report,
        "per_signal": all_recs,
    }
    with open(OUT_JSON, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("\n→ %s" % OUT_JSON)


if __name__ == "__main__":
    main()
