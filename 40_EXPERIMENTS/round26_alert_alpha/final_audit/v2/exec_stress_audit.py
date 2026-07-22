#!/usr/bin/env python3
"""终审agent V2 — 执行现实性加压: 滞后衰减曲线 + 滑点加压 (策略B & C2, 处女holdout).

round14教训: 信号统计上为真、但+1分钟进场就消失的alpha = 不可交易的幻影。
本审计回答: 真人真单(非colo、非首秒抢单)能不能吃到 B / C2 在holdout上的收益。

数据:
- 警报: /Volumes/T9/BWE/30_DATA/bwe_scanner_alerts/*.jsonl
  holdout窗口: 2026-05-30T00:00Z <= ts_ms < 2026-06-09T00:00Z
- K线: round26_alert_alpha/crypto_holdout.sqlite3  klines_1m(symbol,ot,o,h,l,c,v,qv) 只读

策略(规则FROZEN, 来自round26幸存候选):
- B  恐慌flush抄底: 同分钟全市场警报数breadth>=16 且 price_chg_pct<=-2.5
     → LONG 240min; 事件去重 key=(symbol, ts//1800000)
- C2 OI堆积反转空: window_type='oi_price_1h' 且 oi_chg_pct>15 → SHORT 1440min

基线语义(对齐 holdout_reveal + codex修正 bug e/f2):
- 进场: 第一根 ot+60000>ts 的bar收盘; tol: 该bar close_time - ts <= 180s
- 滞后+k bar: 进场bar = 基线进场bar右移k根(索引), 出场target随之顺延, 持有时长不变
- 出场: target = 进场bar close_time + hold*60_000; 第一根 ot>=target 的bar收盘;
  tol: 该bar ot - target <= 300s; 缺bar=丢弃(不漂移)
- 成本: 手续费往返0.14% + 2×单边滑点; 基线滑点0.4%/边 → 往返0.94%

加压矩阵:
1. 滞后衰减: lag ∈ {0,1,2,5,15} bar, 滑点固定0.4%/边
2. 滑点加压: slip ∈ {0.4,0.6,0.8,1.0}%/边, lag固定0
3. 组合最坏可信: lag=+2 × slip=0.6%/边
4. B/C2专项: 进场bar振幅 (h-l)/c 分布 + 下一根bar开盘跳价 (o[i+1]-c[i])/c[i] 分布

衰减曲线统一在"全lag均有效"的公共事件集上算(同一批事件, 纯滞后效应, 无样本漂移)。
内存: 逐symbol流式预载K线, 用完即弃, 峰值 << 1.5GB。
输出: audit_results.json (本目录)。不写report文件。
"""
import glob
import json
import os
import sqlite3
from collections import defaultdict, Counter
from datetime import datetime, timezone

import numpy as np

DIR = "/Volumes/T9/BWE/40_EXPERIMENTS/round26_alert_alpha"
OUT_DIR = os.path.join(DIR, "final_audit", "v2")
ALERTS_DIR = "/Volumes/T9/BWE/30_DATA/bwe_scanner_alerts"
KL_DB = os.path.join(DIR, "crypto_holdout.sqlite3")

HOLDOUT_LO = int(datetime(2026, 5, 30, tzinfo=timezone.utc).timestamp() * 1000)
HOLDOUT_HI = int(datetime(2026, 6, 9, tzinfo=timezone.utc).timestamp() * 1000)  # exclusive

FEES_RT = 0.14            # 手续费往返%
LAGS = [0, 1, 2, 5, 15]   # 进场滞后(bar)
SLIPS = [0.4, 0.6, 0.8, 1.0]  # 单边滑点%
BASE_SLIP = 0.4
ENTRY_TOL_MS = 180_000
EXIT_TOL_MS = 300_000


def cost_rt(slip: float) -> float:
    return FEES_RT + 2 * slip


# ---------------------------------------------------------------- alerts
def load_alerts() -> list:
    out = []
    for f in sorted(glob.glob(ALERTS_DIR + "/*.jsonl")):
        d = os.path.basename(f).split("alerts_")[1][:10]
        if d < "2026-05-30" or d > "2026-06-09":
            continue
        with open(f) as fh:
            for line in fh:
                try:
                    a = json.loads(line)
                except Exception:
                    continue
                if HOLDOUT_LO <= a["ts_ms"] < HOLDOUT_HI:
                    out.append(a)
    out.sort(key=lambda a: a["ts_ms"])
    return out


def build_events(alerts: list) -> list:
    """返回事件列表: dict(strat, symbol, ts, side, hold_min)."""
    bmin = Counter(a["ts_ms"] // 60000 for a in alerts)
    events = []

    # --- B: breadth>=16 & price_chg<=-2.5 → LONG 240m, 去重(symbol, ts//1800000)
    seen = set()
    for a in alerts:
        if bmin.get(a["ts_ms"] // 60000, 0) < 16:
            continue
        if (a.get("price_chg_pct") or 0) > -2.5:
            continue
        key = (a["symbol"], a["ts_ms"] // 1_800_000)
        if key in seen:
            continue
        seen.add(key)
        events.append(dict(strat="B", symbol=a["symbol"], ts=a["ts_ms"],
                           side="long", hold_min=240))

    # --- C2: oi_price_1h & oi_chg>15 → SHORT 1440m (规格无去重)
    for a in alerts:
        if a.get("window_type") != "oi_price_1h":
            continue
        if (a.get("oi_chg_pct") or 0) <= 15:
            continue
        events.append(dict(strat="C2", symbol=a["symbol"], ts=a["ts_ms"],
                           side="short", hold_min=1440))
    return events


# ---------------------------------------------------------------- klines + 模拟
def simulate(events: list) -> None:
    """逐symbol流式预载K线, 就地写入每个事件的 raw[lag] / amp_pct / gap_next_pct / entry_delay_s."""
    by_sym = defaultdict(list)
    for ev in events:
        by_sym[ev["symbol"]].append(ev)

    con = sqlite3.connect("file:%s?mode=ro" % KL_DB, uri=True)
    for sym in sorted(by_sym):
        rows = con.execute(
            "SELECT ot,o,h,l,c FROM klines_1m WHERE symbol=? ORDER BY ot", (sym,)
        ).fetchall()
        if not rows:
            continue
        arr = np.asarray(rows, float)
        ot, o, h, l, c = arr[:, 0], arr[:, 1], arr[:, 2], arr[:, 3], arr[:, 4]
        n = len(ot)
        for ev in by_sym[sym]:
            ts = ev["ts"]
            hold_ms = ev["hold_min"] * 60_000
            i0 = int(np.searchsorted(ot, ts - 59_999, side="left"))  # 第一根 ot+60000>ts
            if i0 >= n or ot[i0] + 60_000 - ts > ENTRY_TOL_MS or c[i0] <= 0:
                continue  # 基线进场bar无效 → 事件作废
            ev["entry_delay_s"] = (ot[i0] + 60_000 - ts) / 1000.0
            ev["amp_pct"] = (h[i0] - l[i0]) / c[i0] * 100.0
            if i0 + 1 < n and ot[i0 + 1] - ot[i0] == 60_000 and c[i0] > 0:
                ev["gap_next_pct"] = (o[i0 + 1] - c[i0]) / c[i0] * 100.0
            raws = {}
            for k in LAGS:
                idx = i0 + k
                if idx >= n or c[idx] <= 0:
                    raws[k] = None
                    continue
                entry = c[idx]
                target = ot[idx] + 60_000 + hold_ms  # 进场close_time + 持有
                j = int(np.searchsorted(ot, target, side="left"))
                if j >= n or ot[j] - target > EXIT_TOL_MS:
                    raws[k] = None
                    continue
                exitp = c[j]
                raw = (exitp - entry) / entry * 100.0 if ev["side"] == "long" \
                    else (entry - exitp) / entry * 100.0
                raws[k] = raw
            ev["raw"] = raws
        del arr, rows  # 用完即弃, 控内存
    con.close()


# ---------------------------------------------------------------- 统计
def cell(raws: list, cost: float, seed: int = 26) -> dict | None:
    a = np.asarray(raws, float)
    if len(a) == 0:
        return None
    net = a - cost
    out = dict(n=int(len(a)),
               raw_mean=round(float(a.mean()), 3),
               net_mean=round(float(net.mean()), 3),
               net_median=round(float(np.median(net)), 3),
               win_pct=round(float((net > 0).mean() * 100), 1))
    if len(a) >= 10:
        rng = np.random.default_rng(seed)
        idx = rng.integers(0, len(a), size=(2000, len(a)))
        boot = np.sort(net[idx].mean(axis=1))
        out["boot5_net"] = round(float(boot[100]), 3)
        out["boot95_net"] = round(float(boot[1899]), 3)
    return out


def day_stats(evs: list, lag: int, cost: float) -> dict | None:
    by_day = defaultdict(list)
    for ev in evs:
        r = ev.get("raw", {}).get(lag)
        if r is None:
            continue
        d = datetime.fromtimestamp(ev["ts"] / 1000, tz=timezone.utc).strftime("%m-%d")
        by_day[d].append(r - cost)
    if not by_day:
        return None
    dm = {d: round(float(np.mean(v)), 3) for d, v in sorted(by_day.items())}
    vals = np.asarray(list(dm.values()))
    return dict(day_net_means=dm,
                eqw_day_mean=round(float(vals.mean()), 3),
                pos_days="%d/%d" % (int((vals > 0).sum()), len(vals)))


def dist(vals: list) -> dict | None:
    a = np.asarray([v for v in vals if v is not None], float)
    if len(a) == 0:
        return None
    q = lambda p: round(float(np.percentile(a, p)), 3)
    return dict(n=int(len(a)), mean=round(float(a.mean()), 3),
                p10=q(10), p25=q(25), p50=q(50), p75=q(75),
                p90=q(90), p95=q(95), p99=q(99))


def analyse(evs: list, strat: str) -> dict:
    valid = [ev for ev in evs if "raw" in ev]                       # 基线进场bar有效
    common = [ev for ev in valid
              if all(ev["raw"].get(k) is not None for k in LAGS)]   # 全lag可比集

    res = dict(strategy=strat,
               n_triggers=len(evs),
               n_valid_entry=len(valid),
               n_common_all_lags=len(common),
               entry_delay_s=dist([ev.get("entry_delay_s") for ev in valid]))

    # 0) 基线 lag0 全样本 (对账 round26 holdout_reveal 数字)
    res["lag0_fullset_slip0.4"] = cell(
        [ev["raw"][0] for ev in valid if ev["raw"].get(0) is not None], cost_rt(BASE_SLIP))
    res["lag0_fullset_day_stats"] = day_stats(valid, 0, cost_rt(BASE_SLIP))

    # 1) 滞后衰减曲线 @0.4%/边, 公共事件集
    res["lag_curve_slip0.4_common"] = {
        "lag%+d" % k: cell([ev["raw"][k] for ev in common], cost_rt(BASE_SLIP))
        for k in LAGS}

    # 2) 滑点加压 @lag0, 公共事件集
    res["slip_matrix_lag0_common"] = {
        "slip%.1f" % s: cell([ev["raw"][0] for ev in common], cost_rt(s))
        for s in SLIPS}

    # 全网格净均值 (lag × slip)
    grid = {}
    for k in LAGS:
        rm = float(np.mean([ev["raw"][k] for ev in common])) if common else float("nan")
        grid["lag%+d" % k] = {"slip%.1f" % s: round(rm - cost_rt(s), 3) for s in SLIPS}
    res["net_mean_grid_common"] = grid

    # 3) 组合最坏可信: +2bar × 0.6%/边
    res["combo_lag2_slip0.6"] = cell([ev["raw"][2] for ev in common], cost_rt(0.6))
    res["combo_lag2_slip0.6_day_stats"] = day_stats(common, 2, cost_rt(0.6))

    # 4/5) 进场bar执行现实性: 振幅 + 下一根开盘跳价
    amps = [ev.get("amp_pct") for ev in valid]
    res["entry_bar_amp_pct"] = dist(amps)
    aa = np.asarray([v for v in amps if v is not None], float)
    if len(aa):
        res["entry_bar_amp_share"] = {
            "amp>=0.8pct": round(float((aa >= 0.8).mean() * 100), 1),
            "amp>=1.6pct": round(float((aa >= 1.6).mean() * 100), 1),
            "amp>=3.0pct": round(float((aa >= 3.0).mean() * 100), 1),
            "amp>=5.0pct": round(float((aa >= 5.0).mean() * 100), 1)}
    gaps = [ev.get("gap_next_pct") for ev in valid]
    res["next_bar_open_gap_pct"] = dist(gaps)   # B多头: 正=不利; C2空头: 负=不利
    ga = np.asarray([v for v in gaps if v is not None], float)
    if len(ga):
        adverse = ga if strat == "B" else -ga   # 不利方向跳价
        res["adverse_open_gap"] = {
            "mean": round(float(adverse.mean()), 3),
            "p50": round(float(np.percentile(adverse, 50)), 3),
            "p90": round(float(np.percentile(adverse, 90)), 3),
            "p95": round(float(np.percentile(adverse, 95)), 3),
            "share_gt_0.4pct": round(float((adverse > 0.4).mean() * 100), 1)}

    # ---- 判定 ----
    g = lambda k, s: grid["lag%+d" % k]["slip%.1f" % s]
    if not common:
        verdict, reason = "无法判定", "公共事件集为空"
    elif g(1, 0.4) <= 0:
        verdict, reason = "判死", "幻影alpha: +1bar滞后即翻负 (净均 %+.3f%%) — 拼不到的速度" % g(1, 0.4)
    elif g(0, 0.6) > 0 and g(2, 0.6) > 0:
        verdict, reason = "判过", "执行稳健: +2bar×0.6%%/边仍正 (净均 %+.3f%%)" % g(2, 0.6)
    elif g(0, 0.6) <= 0:
        verdict, reason = "判危", "边际太薄: 0.6%%/边扛不住 (lag0净均 %+.3f%%)" % g(0, 0.6)
    else:
        verdict, reason = "判危", "+2bar×0.6%%/边翻负 (净均 %+.3f%%), 滞后+滑点叠加扛不住" % g(2, 0.6)
    res["verdict"] = verdict
    res["verdict_reason"] = reason
    return res


def main() -> None:
    alerts = load_alerts()
    print("holdout警报数 [05-30, 06-09): %d" % len(alerts))
    events = build_events(alerts)
    nb = sum(1 for e in events if e["strat"] == "B")
    nc = sum(1 for e in events if e["strat"] == "C2")
    print("策略B触发(去重后): %d | 策略C2触发: %d | 涉及symbol: %d"
          % (nb, nc, len({e['symbol'] for e in events})))

    simulate(events)

    results = dict(
        meta=dict(
            audit="终审V2 执行现实性加压 (滞后衰减+滑点加压)",
            run_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            holdout_window="2026-05-30T00:00Z <= ts < 2026-06-09T00:00Z",
            alerts_n=len(alerts),
            entry_rule="第一根 ot+60000>ts 的bar收盘, tol 180s; 滞后+k=进场bar右移k根",
            exit_rule="target=进场close_time+hold*60s, 第一根 ot>=target 收盘, tol 300s, 缺bar丢弃",
            cost_rule="净=raw - (0.14%手续费往返 + 2×单边滑点); 基线0.4%/边 → 往返0.94%",
            lag_curve_note="衰减曲线/滑点矩阵在'全lag均有效'公共事件集上算 (同批事件纯滞后效应)",
            criteria=dict(判死="+1bar翻负=幻影alpha", 判危="0.6%/边扛不住 或 +2bar×0.6%翻负",
                          判过="+2bar×0.6%/边仍正")),
        B=analyse([e for e in events if e["strat"] == "B"], "B"),
        C2=analyse([e for e in events if e["strat"] == "C2"], "C2"))

    out_path = os.path.join(OUT_DIR, "audit_results.json")
    with open(out_path, "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    print("written:", out_path)

    for s in ("B", "C2"):
        r = results[s]
        print("\n=== %s — %s: %s ===" % (s, r["verdict"], r["verdict_reason"]))
        print(" 触发=%d 有效进场=%d 公共集=%d" % (r["n_triggers"], r["n_valid_entry"], r["n_common_all_lags"]))
        print(" lag曲线@0.4%/边:", {k: v["net_mean"] for k, v in r["lag_curve_slip0.4_common"].items()})
        print(" slip矩阵@lag0:", {k: v["net_mean"] for k, v in r["slip_matrix_lag0_common"].items()})
        c = r["combo_lag2_slip0.6"]
        print(" 组合+2bar×0.6%%: 净均%+.3f%% 胜%.1f%% boot5%+.3f%%"
              % (c["net_mean"], c["win_pct"], c.get("boot5_net", float("nan"))))
        print(" 进场bar振幅:", r["entry_bar_amp_pct"], "| 占比:", r.get("entry_bar_amp_share"))
        print(" 不利开盘跳价:", r.get("adverse_open_gap"))


if __name__ == "__main__":
    main()
