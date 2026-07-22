#!/usr/bin/env python3
"""stockusbinance paper 引擎 v2: 纸面记账, 绝不下真单。
四方审查全部修复:
- F1: 进场=信号后**第一根**已收盘bar(因果, 非ceiling往未来扫); 出场同规则; exit_ts<t_exit则丢弃并计数。
- 成本: 用 backfill/forward 的 book 实测点差(taker吃盘口=进ask/出bid); 无盘口则用历史K线±实测半点差。
- 资金费: 用 bf_funding 真实8h结算序列精确累加(非60s采样均值); 缺数据回退实测年化基线(不返回0)。
- 边界: 拒绝 None/<=0/非有限 价格。
- 归因(N1): 按 side/confidence/tradeable 分组; 并排 net_perp vs stock_5d(F3对照)。
回测优先用 backfill(bf_*表, 历史真实价); forward(klines_1m/book)补充近期。
"""
import json, os, sqlite3, math, sys
from datetime import datetime, timezone

DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(DIR, "tradfi_capture_ec2.sqlite3")
BRIDGED = os.path.join(DIR, "bridged_signals.jsonl")
OUT = os.path.join(DIR, "paper_trades.jsonl")

TAKER_FEE = 0.0004                 # 单边taker费(永续标准)
# 实测年化资金费基线(缺数据回退用; 来自probe): 多数小, MU/QQQ偏高
FUND_ANNUAL_FALLBACK = {"MUUSDT": 0.26, "QQQUSDT": 0.19, "NVDAUSDT": 0.006, "_default": 0.05}

def conn():
    return sqlite3.connect("file:%s?mode=ro" % DB, uri=True) if os.path.exists(DB) else None

def has_table(c, t):
    return c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (t,)).fetchone() is not None

def first_bar_after(c, sym, ts_ms, ktab, max_delay_ms=2*3600000):
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
            return (r[0] / 2) / 1e4   # 半点差
        # 退: 该symbol全期中位
        r2 = c.execute("SELECT spread_bp FROM book WHERE symbol=? AND spread_bp>0", (sym,)).fetchall()
        if r2:
            vals = sorted(x[0] for x in r2); med = vals[len(vals)//2]
            return (med / 2) / 1e4
    return 0.0005   # 0.05% 保守半点差

def funding_cost(c, sym, t0, t1, side):
    """真实8h资金费累加(bf_funding)。多头付正费率→成本为正。缺数据回退年化基线(不返回0)。"""
    if has_table(c, "bf_funding"):
        rows = c.execute("SELECT funding_rate FROM bf_funding WHERE symbol=? AND funding_time>=? AND funding_time<=?",
                         (sym, t0, t1)).fetchall()
        if rows:
            total = sum(r[0] for r in rows)            # 真实结算费率求和
            return total if side == "long" else -total
    # 回退: 年化基线按持仓时长折算(宁可高估)
    ann = FUND_ANNUAL_FALLBACK.get(sym, FUND_ANNUAL_FALLBACK["_default"])
    days = (t1 - t0) / 86400000
    est = ann / 365 * days
    return est if side == "long" else -est

def eval_signals(c, hold_days=5):
    if not os.path.exists(BRIDGED):
        return [], {}
    sigs = [json.loads(l) for l in open(BRIDGED)]
    # 选历史表优先(bf_*覆盖过去), 否则forward(klines_1m)
    ktab = "bf_klines_1m" if has_table(c, "bf_klines_1m") else "klines_1m"
    trades = []
    diag = {"no_entry": 0, "no_exit_future": 0, "bad_price": 0, "ok": 0}
    from zoneinfo import ZoneInfo
    for s in sigs:
        sym = s["symbol"]; side = s["side"]
        # 时区: recorded_at 带offset则用之; naive则按ET
        try:
            ra = s["recorded_at"].replace("Z", "+00:00")
            dt = datetime.fromisoformat(ra)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=ZoneInfo("America/New_York"))
            t_sig = int(dt.astimezone(timezone.utc).timestamp() * 1000)
        except Exception:
            continue
        # F1: 进场=信号后第一根已收盘bar(因果)
        entry_ts, entry = first_bar_after(c, sym, t_sig, ktab)
        if entry is None:
            diag["no_entry"] += 1; continue
        t_exit_target = entry_ts + hold_days * 86400000
        exit_ts, exit_px = first_bar_after(c, sym, t_exit_target, ktab, max_delay_ms=300000)
        if exit_ts is None:
            diag["no_exit_future"] += 1; continue   # forward还没到出场时点
        if exit_ts < t_exit_target:
            diag["bad_price"] += 1; continue
        if not (entry and exit_px and entry > 0 and exit_px > 0 and math.isfinite(entry) and math.isfinite(exit_px)):
            diag["bad_price"] += 1; continue
        # 成本: taker吃盘口 → 进场付半点差(买在ask/卖在bid), 出场同; + taker费; + 资金费
        hs_in = half_spread(c, sym, entry_ts); hs_out = half_spread(c, sym, exit_ts)
        # 做多: 进场实付 entry*(1+hs_in), 出场实得 exit*(1-hs_out); 做空相反
        if side == "long":
            eff_entry = entry * (1 + hs_in); eff_exit = exit_px * (1 - hs_out)
            raw = (eff_exit - eff_entry) / eff_entry
        else:
            eff_entry = entry * (1 - hs_in); eff_exit = exit_px * (1 + hs_out)
            raw = (eff_entry - eff_exit) / eff_entry
        fund = funding_cost(c, sym, entry_ts, exit_ts, side)
        net = raw - 2 * TAKER_FEE - fund
        # F3: 正股5d realized对照
        stock_5d = None
        oc = s.get("outcomes") or {}
        if isinstance(oc, dict):
            stock_5d = (oc.get("5d") or {}).get("return_pct")
        trades.append({
            "signal_id": s.get("signal_id"), "symbol": sym, "side": side,
            "tradeable": s.get("tradeable"), "confidence": s.get("confidence"),
            "entry": round(entry, 4), "exit": round(exit_px, 4),
            "raw_pct": round(raw*100, 3), "net_pct": round(net*100, 3),
            "fund_pct": round(fund*100, 3), "half_spread_bp": round(hs_in*1e4, 2),
            "stock_5d_pct": stock_5d, "hold_days": hold_days,
        })
        diag["ok"] += 1
    return trades, diag

def group_report(trades, key, label):
    from collections import defaultdict
    import statistics as st
    g = defaultdict(list)
    for t in trades: g[t.get(key)].append(t["net_pct"])
    print("  [按%s分组]" % label)
    for k, v in sorted(g.items(), key=lambda x: -len(x[1])):
        wins = sum(1 for x in v if x > 0)
        warn = " ⚠️n<30" if len(v) < 30 else ""
        print("    %-10s n=%-3d 净均%+.3f%% 中%+.3f%% 胜%d%%%s" % (
            str(k), len(v), st.mean(v), st.median(v), 100*wins/len(v), warn))

def main():
    c = conn()
    if c is None:
        print("采集/回填DB还没同步到本地。先 rsync。"); return
    nk = c.execute("SELECT COUNT(*) FROM %s" % ("bf_klines_1m" if has_table(c,"bf_klines_1m") else "klines_1m")).fetchone()[0]
    print("数据: %d K线 (源: %s)\n" % (nk, "回填+forward" if has_table(c,"bf_klines_1m") else "仅forward"))
    all_trades = []
    for hd in (1, 5):
        trades, diag = eval_signals(c, hold_days=hd)
        for t in trades: t["_hd"] = hd
        all_trades += trades
        if not trades:
            print("### 持有%dd: 0可评估 (诊断: %s)" % (hd, diag)); continue
        import statistics as st
        nets = [t["net_pct"] for t in trades]
        wins = sum(1 for x in nets if x > 0)
        print("### 持有%dd (n=%d, 诊断:%s)" % (hd, len(trades), diag))
        print("  全体: 净均%+.3f%% 中%+.3f%% 胜%d%%%s" % (
            st.mean(nets), st.median(nets), 100*wins/len(nets), " ⚠️n<30探索性" if len(nets)<30 else ""))
        group_report(trades, "side", "方向")
        group_report(trades, "tradeable", "白名单(True=实测正edge侧)")
        # F3: 永续net vs 正股5d 对照(基差+成本侵蚀)
        paired = [(t["net_pct"], t["stock_5d_pct"]) for t in trades if t.get("stock_5d_pct") is not None]
        if paired:
            perp = st.mean(p[0] for p in paired); stk = st.mean(p[1] for p in paired)
            print("  [永续vs正股] 永续net均%+.3f%% | 正股5d均%+.3f%% | 基差+成本侵蚀%+.3f%%" % (perp, stk, perp-stk))
    with open(OUT, "w") as f:
        for t in all_trades: f.write(json.dumps(t, ensure_ascii=False) + "\n")
    print("\n→ %s (%d trades)" % (OUT, len(all_trades)))
    print("注: 做空看均值(中位正/均值负=左尾陷阱); n<30一律探索性不可下结论。")

if __name__ == "__main__":
    main()
