#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
终审 agent V1【洁净室复算】— 从零独立实现策略 B / C2 的 holdout 评估。

独立性声明: 本脚本只依据冻结规格实现, 全程未打开/参考
holdout_reveal.py, build_panel.py, fam_A/B/C/D 任何主线代码。

冻结规格:
  数据
    - 警报: /Volumes/T9/BWE/30_DATA/bwe_scanner_alerts/*.jsonl
      (排除 macOS AppleDouble 资源叉文件 "._*", 非数据)
    - holdout K线: crypto_holdout.sqlite3 表 klines_1m(symbol, ot, o,h,l,c,v,qv), 只读
    - holdout 窗口: 2026-05-30T00:00:00Z <= ts_ms < 2026-06-09T00:00:00Z
  策略B (恐慌flush抄底, LONG 240min)
    - breadth_min = 全部警报流里与该警报同一分钟桶(ts_ms//60000)的警报总数(含自身)
    - 触发: breadth_min>=16 且 price_chg_pct<=-2.5
    - 去重: 同(symbol, ts_ms//1800000) 只取第一条(按时间序)
  策略C2 (OI堆积空, SHORT 1440min)
    - 触发: window_type=='oi_price_1h' 且 oi_chg_pct>15 (None视0), 不去重
    - 配对基线: 同窗口内全部 oi_price_1h 警报, SHORT 1440min 同口径
  进出场 (两策略同)
    - 进场bar = 第一根 ot+60000 > ts_ms 的bar; 要求 ot+60000-ts_ms <= 180000 否则丢弃计数
      进场价 = 该bar c
    - target = 进场bar(ot+60000) + 持有分钟*60000
      出场bar = 第一根 ot >= target; 要求 ot-target <= 300000 否则丢弃计数; 出场价 = 该bar c
    - 净收益% = 方向毛收益% - 0.94
      LONG毛 = (exit-entry)/entry*100; SHORT毛 = (entry-exit)/entry*100
    - 拒绝 entry<=0 或非有限
内存: 警报逐行流式; K线按 symbol 逐个加载 (每 symbol <~2万行), 远低于 1.5GB。
"""

import glob
import json
import math
import os
import resource
import sqlite3
import statistics
import time
from bisect import bisect_left, bisect_right
from collections import defaultdict
from datetime import datetime, timezone

ALERT_DIR = "/Volumes/T9/BWE/30_DATA/bwe_scanner_alerts"
DB_PATH = "/Volumes/T9/BWE/40_EXPERIMENTS/round26_alert_alpha/crypto_holdout.sqlite3"
OUT_DIR = "/Volumes/T9/BWE/40_EXPERIMENTS/round26_alert_alpha/final_audit/v1"

HOLD_START = int(datetime(2026, 5, 30, tzinfo=timezone.utc).timestamp() * 1000)
HOLD_END = int(datetime(2026, 6, 9, tzinfo=timezone.utc).timestamp() * 1000)

COST_PCT = 0.94            # 往返成本: 0.14 费 + 0.8 滑点
B_BREADTH_MIN = 16
B_PRICE_MAX = -2.5
B_HOLD_MIN = 240           # LONG
C2_OI_MIN = 15.0
C2_HOLD_MIN = 1440         # SHORT
ENTRY_MAX_GAP_MS = 180_000
EXIT_MAX_GAP_MS = 300_000

# 对账目标 (主线现有数字)
TARGETS = {
    "B_n": 2358, "B_net_mean": 1.43, "B_net_median": 1.37, "B_win_rate": 0.68,
    "B_daily_eqw": 0.44, "B_pos_days": 4, "B_n_days": 7,
    "C2_n": 1774, "C2_net_mean": 0.62,
    "C2_excess_daily": 1.18, "C2_excess_pos_days": 7, "C2_excess_n_days": 10,
}


def utc_day(ts_ms):
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def alert_files():
    out = []
    for p in sorted(glob.glob(os.path.join(ALERT_DIR, "*.jsonl"))):
        if os.path.basename(p).startswith("._"):
            continue  # AppleDouble 资源叉, 非数据
        out.append(p)
    return out


def main():
    t0 = time.time()

    # ---------- Pass 1: 流式扫全部警报 ----------
    breadth = defaultdict(int)   # minute_bucket -> 全流警报数
    b_cand = []                  # (ts, symbol, minute_bucket, seq) 价格条件已过
    c2_ev = []                   # (ts, symbol)
    base_ev = []                 # (ts, symbol) 全部 oi_price_1h
    total_lines = bad_lines = 0
    seq = 0

    for fp in alert_files():
        with open(fp, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                total_lines += 1
                try:
                    a = json.loads(line)
                    ts = a["ts_ms"]
                    if not isinstance(ts, (int, float)) or isinstance(ts, bool):
                        raise ValueError("ts_ms not numeric")
                    ts = int(ts)
                except Exception:
                    bad_lines += 1
                    continue
                breadth[ts // 60_000] += 1
                if not (HOLD_START <= ts < HOLD_END):
                    continue
                sym = a.get("symbol")
                if not sym:
                    continue
                pc = a.get("price_chg_pct")
                if pc is not None and pc <= B_PRICE_MAX:
                    b_cand.append((ts, sym, ts // 60_000, seq))
                    seq += 1
                if a.get("window_type") == "oi_price_1h":
                    base_ev.append((ts, sym))
                    oc = a.get("oi_chg_pct")
                    if (oc if oc is not None else 0) > C2_OI_MIN:
                        c2_ev.append((ts, sym))

    # ---------- 策略B: breadth 过滤 + 30min 去重 ----------
    b_trig = [(ts, sym) for ts, sym, mb, sq in
              sorted(b_cand, key=lambda x: (x[0], x[3]))
              if breadth[mb] >= B_BREADTH_MIN]
    b_events, seen = [], set()
    for ts, sym in b_trig:
        key = (sym, ts // 1_800_000)
        if key in seen:
            continue
        seen.add(key)
        b_events.append((ts, sym))

    # ---------- 按 symbol 分组评估 ----------
    trades_by_symbol = defaultdict(list)  # sym -> [(set, ts, side, hold_min)]
    for ts, sym in b_events:
        trades_by_symbol[sym].append(("B", ts, +1, B_HOLD_MIN))
    for ts, sym in c2_ev:
        trades_by_symbol[sym].append(("C2", ts, -1, C2_HOLD_MIN))
    for ts, sym in base_ev:
        trades_by_symbol[sym].append(("BASE", ts, -1, C2_HOLD_MIN))

    db = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    cur = db.cursor()

    results = {k: [] for k in ("B", "C2", "BASE")}   # (ts, sym, net)
    disc = {k: defaultdict(int) for k in ("B", "C2", "BASE")}

    for sym in sorted(trades_by_symbol):
        trades = trades_by_symbol[sym]
        lo = min(t[1] for t in trades) - 120_000
        hi = max(t[1] + ENTRY_MAX_GAP_MS + t[3] * 60_000 + EXIT_MAX_GAP_MS + 60_000
                 for t in trades)
        rows = cur.execute(
            "SELECT ot, c FROM klines_1m WHERE symbol=? AND ot>=? AND ot<=? ORDER BY ot",
            (sym, lo, hi)).fetchall()
        if not rows:
            for name, ts, side, hold in trades:
                disc[name]["symbol_no_klines"] += 1
            continue
        ots = [r[0] for r in rows]
        cls = [r[1] for r in rows]
        for name, ts, side, hold in trades:
            # 进场: 第一根 ot+60000 > ts  <=>  ot > ts-60000
            i = bisect_right(ots, ts - 60_000)
            if i >= len(ots) or (ots[i] + 60_000 - ts) > ENTRY_MAX_GAP_MS:
                disc[name]["no_entry_bar"] += 1
                continue
            entry = cls[i]
            if entry is None or not math.isfinite(entry) or entry <= 0:
                disc[name]["bad_entry_price"] += 1
                continue
            target = ots[i] + 60_000 + hold * 60_000
            j = bisect_left(ots, target)   # 第一根 ot >= target
            if j >= len(ots) or (ots[j] - target) > EXIT_MAX_GAP_MS:
                disc[name]["no_exit_bar"] += 1
                continue
            exitp = cls[j]
            if exitp is None or not math.isfinite(exitp):
                disc[name]["bad_exit_price"] += 1
                continue
            gross = (exitp - entry) / entry * 100.0 * side
            results[name].append((ts, sym, gross - COST_PCT))
    db.close()

    # ---------- 统计 ----------
    def basic_stats(rs):
        nets = [r[2] for r in rs]
        if not nets:
            return {"n": 0}
        by_day = defaultdict(list)
        for ts, sym, net in rs:
            by_day[utc_day(ts)].append(net)
        day_means = {d: sum(v) / len(v) for d, v in sorted(by_day.items())}
        return {
            "n": len(nets),
            "net_mean": sum(nets) / len(nets),
            "net_median": statistics.median(nets),
            "win_rate": sum(1 for x in nets if x > 0) / len(nets),
            "daily_eqw": sum(day_means.values()) / len(day_means),
            "pos_days": sum(1 for m in day_means.values() if m > 0),
            "n_days": len(day_means),
            "day_means": day_means,
            "day_counts": {d: len(v) for d, v in sorted(by_day.items())},
        }

    sB = basic_stats(results["B"])
    sC2 = basic_stats(results["C2"])
    sBASE = basic_stats(results["BASE"])

    # C2 同日配对超额: C2 有成交的天, excess_d = mean(C2_d) - mean(BASE_d)
    excess = {}
    for d, m in sC2.get("day_means", {}).items():
        if d in sBASE.get("day_means", {}):
            excess[d] = m - sBASE["day_means"][d]
    paired = {
        "n_days": len(excess),
        "mean_excess_daily": (sum(excess.values()) / len(excess)) if excess else None,
        "pos_days": sum(1 for v in excess.values() if v > 0),
        "day_excess": dict(sorted(excess.items())),
    }

    # ---------- 对账 ----------
    mine = {
        "B_n": sB.get("n"), "B_net_mean": sB.get("net_mean"),
        "B_net_median": sB.get("net_median"), "B_win_rate": sB.get("win_rate"),
        "B_daily_eqw": sB.get("daily_eqw"), "B_pos_days": sB.get("pos_days"),
        "B_n_days": sB.get("n_days"),
        "C2_n": sC2.get("n"), "C2_net_mean": sC2.get("net_mean"),
        "C2_excess_daily": paired["mean_excess_daily"],
        "C2_excess_pos_days": paired["pos_days"],
        "C2_excess_n_days": paired["n_days"],
    }
    recon = {}
    for k, tgt in TARGETS.items():
        v = mine.get(k)
        if v is None:
            recon[k] = {"mine": None, "target": tgt, "rel_diff": None, "gt10pct": True}
            continue
        rel = abs(v - tgt) / abs(tgt) if tgt != 0 else (0.0 if v == 0 else float("inf"))
        recon[k] = {"mine": v, "target": tgt, "rel_diff": rel, "gt10pct": rel > 0.10}

    out = {
        "meta": {
            "agent": "final_audit_v1_cleanroom",
            "run_at_utc": datetime.now(timezone.utc).isoformat(),
            "holdout_start_ms": HOLD_START, "holdout_end_ms": HOLD_END,
            "alert_files_used": len(alert_files()),
            "alert_lines_total": total_lines, "alert_lines_bad": bad_lines,
            "cost_pct_roundtrip": COST_PCT,
            "independence": "未读 holdout_reveal.py / build_panel.py / fam_* 任何代码",
            "runtime_sec": round(time.time() - t0, 1),
            "peak_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6, 1),
        },
        "B": {
            "pre_dedup_triggers": len(b_trig),
            "post_dedup_events": len(b_events),
            "stats": sB, "discards": dict(disc["B"]),
        },
        "C2": {
            "triggers": len(c2_ev),
            "stats": sC2, "discards": dict(disc["C2"]),
            "baseline_all_oi_price_1h": {
                "triggers": len(base_ev),
                "stats": {k: v for k, v in sBASE.items() if k != "day_means"} | {
                    "day_means": sBASE.get("day_means", {})},
                "discards": dict(disc["BASE"]),
            },
            "paired_excess": paired,
        },
        "reconciliation": recon,
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "results_v1.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # ---------- 控制台摘要 ----------
    print("=== 终审V1 洁净室复算 ===")
    print(f"警报行: {total_lines} (坏行 {bad_lines}), 文件 {len(alert_files())}")
    print(f"B: 触发(pre-dedup)={len(b_trig)}  去重后={len(b_events)}  评估成功={sB.get('n')}")
    if sB.get("n"):
        print(f"   net_mean={sB['net_mean']:+.4f}%  median={sB['net_median']:+.4f}%  "
              f"win={sB['win_rate']*100:.1f}%  daily_eqw={sB['daily_eqw']:+.4f}%/天  "
              f"正天数={sB['pos_days']}/{sB['n_days']}")
        print("   B day_means:", {k: round(v, 3) for k, v in sB["day_means"].items()})
    print(f"   丢弃: {dict(disc['B'])}")
    print(f"C2: 触发={len(c2_ev)}  评估成功={sC2.get('n')}")
    if sC2.get("n"):
        print(f"   net_mean={sC2['net_mean']:+.4f}%  daily_eqw={sC2['daily_eqw']:+.4f}%/天  "
              f"正天数={sC2['pos_days']}/{sC2['n_days']}")
    print(f"   丢弃: {dict(disc['C2'])}")
    print(f"BASE(all oi_price_1h): 触发={len(base_ev)}  评估成功={sBASE.get('n')}  "
          f"net_mean={sBASE.get('net_mean', float('nan')):+.4f}%  丢弃: {dict(disc['BASE'])}")
    print(f"配对超额: mean={paired['mean_excess_daily']:+.4f}%/天  "
          f"正天数={paired['pos_days']}/{paired['n_days']}")
    print("   day_excess:", {k: round(v, 3) for k, v in paired["day_excess"].items()})
    print("--- 对账 ---")
    for k, r in recon.items():
        flag = " <-- >10%" if r["gt10pct"] else ""
        mv = r["mine"]
        mv_s = f"{mv:.4f}" if isinstance(mv, float) else str(mv)
        print(f"  {k:22s} mine={mv_s:>10s}  target={r['target']:>8}  "
              f"rel_diff={r['rel_diff']*100 if r['rel_diff'] is not None else -1:.1f}%{flag}")
    print(f"runtime={out['meta']['runtime_sec']}s  peak_rss={out['meta']['peak_rss_mb']}MB")


if __name__ == "__main__":
    main()
