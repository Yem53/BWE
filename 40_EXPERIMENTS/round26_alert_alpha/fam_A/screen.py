#!/usr/bin/env python3
"""round26 fam_A — 警报触发后方向性 alpha 筛选 (角度1-25).
共享面板筛选, 不是探索。目标: 能扛严格检验的可交易策略, 或诚实证明没有。

铁律实现:
 1. 因果内建 (f 是进场后)。做空净收益 = -f - 成本。
 2. 成本: 往返 taker 0.14% + 妖币滑点 (atr_pct>=1.5% 额外单边 0.4%; atr_pct>=3% 额外单边 0.6%)。
 3. 做空只看均值; 做多看均值+中位都要正。
 4. BH-FDR over ALL tested cells (一个 family), 只信 q<0.10。
 5. LODO: 去掉贡献最大那天 (尤其 2025-10-10), 算 max_one_day_frac, >40%=毙。
 6. cell n<100 标探索性。
 7. dev 选候选 → val 验一次 (同号 + 扣成本仍正)。

输出: cells_dev.csv (全部测过的 cell), survivors.json, summary 打印。不写 report。
"""
import sqlite3, json, os
import numpy as np
import pandas as pd

DB = "/Volumes/T9/BWE/40_EXPERIMENTS/round26_alert_alpha/alert_panel.sqlite3"
OUT = "/Volumes/T9/BWE/40_EXPERIMENTS/round26_alert_alpha/fam_A"
DEV_CUTOFF = 1778803200000  # ts_ms<=this -> dev (05-15 前)
RNG = np.random.default_rng(20260611)
N_BOOT = 20000
FDR_Q = 0.10
ROUNDTRIP_TAKER = 0.14  # %, 往返
MIN_N = 100

# ---------- 成本: 单边滑点按 atr_pct 分档, 往返 ----------
def slip_oneside(atr_pct):
    a = np.where(np.isnan(atr_pct), 0.0, atr_pct)
    s = np.zeros_like(a, dtype=float)
    s = np.where(a >= 1.5, 0.4, s)
    s = np.where(a >= 3.0, 0.6, s)
    return s  # 单边额外滑点 %

def cost_roundtrip(atr_pct):
    # taker 往返 0.14 + 滑点单边*2 (进+出)
    return ROUNDTRIP_TAKER + 2.0 * slip_oneside(atr_pct)

# ---------- 净收益: side=+1 做多, -1 做空 ----------
def net_return(f, atr_pct, side):
    gross = side * f                      # 做空 = -f
    return gross - cost_roundtrip(atr_pct)

# ---------- 统计: bootstrap 均值的单侧 p (H0: mean<=0 对 long; mean>=0 反向无意义) ----------
def boot_mean_p(x):
    """单侧 p-value, H0: 真实均值 <= 0。返回 (mean, p_gt0)。
    p_gt0 小 = 有证据均值>0。用 bootstrap 抽样均值分布。"""
    x = x[~np.isnan(x)]
    n = len(x)
    if n < 5:
        return np.nan, 1.0
    idx = RNG.integers(0, n, size=(N_BOOT, n))
    bmeans = x[idx].mean(axis=1)
    p_gt0 = float((bmeans <= 0).mean())   # 抽样均值落在<=0 的比例
    return float(x.mean()), p_gt0

def median_p(x):
    x = x[~np.isnan(x)]
    n = len(x)
    if n < 5:
        return np.nan
    return float(np.median(x))

# ---------- BH-FDR ----------
def bh_fdr(pvals):
    p = np.asarray(pvals, float)
    m = len(p)
    order = np.argsort(p)
    ranked = p[order]
    q = ranked * m / (np.arange(1, m+1))
    # 单调化 (从后往前取 min)
    q = np.minimum.accumulate(q[::-1])[::-1]
    q = np.clip(q, 0, 1)
    out = np.empty(m); out[order] = q
    return out

# ---------- 日贡献 / LODO ----------
def day_contrib(net, days):
    """返回 (max_one_day_frac, lodo_mean)。frac = 去掉贡献绝对值最大那天后均值变化的占比。
    更稳健: 用 '去掉单日后均值仍同号' 判定, max_one_day_frac = 该单日 sum 占总 sum 的绝对占比。"""
    net = np.asarray(net, float)
    mask = ~np.isnan(net)
    net = net[mask]; days = np.asarray(days)[mask]
    total = net.sum()
    if len(net) == 0 or total == 0:
        return 1.0, np.nan, None
    uniq = pd.unique(days)
    # 每天的 sum 贡献
    day_sums = {d: net[days == d].sum() for d in uniq}
    # 贡献绝对值最大的那天 (对总收益方向)
    if total > 0:
        worst_day = max(day_sums, key=lambda d: day_sums[d])  # 拿掉对正收益贡献最大的
    else:
        worst_day = min(day_sums, key=lambda d: day_sums[d])
    frac = abs(day_sums[worst_day]) / abs(total)
    lodo = net[days != worst_day].mean()
    return float(frac), float(lodo), str(worst_day)


def load():
    con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    df = pd.read_sql_query(
        "SELECT symbol, ts_ms, wt, chg, oi_chg, atr_pct, lag_s, "
        "f5, f15, f60, f240, f1440 FROM panel", con)
    con.close()
    df["day"] = pd.to_datetime(df["ts_ms"], unit="ms", utc=True).dt.strftime("%Y-%m-%d")
    df["is_dev"] = df["ts_ms"] <= DEV_CUTOFF
    return df

# chg 强度分档 (绝对值)
def chg_tier(chg):
    a = np.abs(chg)
    return np.select(
        [a < 7, (a >= 7) & (a < 11), a >= 11],
        ["sm3_7", "md7_11", "lg11p"],
        default="na")

WINDOWS = ["price_3s","price_5s","price_10s","price_30s","price_60s","price_90s",
           "price_180s_extreme","oi_price_1h"]
HORIZONS = ["f5","f15","f60","f240","f1440"]
SIDES = {"long": 1, "short": -1}


def build_cells(df, split_mask, tag):
    """生成所有 cell 的统计。cell = window × [全档|chg档] × horizon × side。"""
    d = df[split_mask].copy()
    rows = []
    for wt in WINDOWS:
        sub_w = d[d["wt"] == wt]
        if len(sub_w) == 0:
            continue
        # 分组: ALL + 三个 chg 档
        groups = {"ALL": sub_w}
        sub_w = sub_w.assign(_tier=chg_tier(sub_w["chg"].values))
        for t in ["sm3_7","md7_11","lg11p"]:
            g = sub_w[sub_w["_tier"] == t]
            if len(g) >= 30:   # 太小的档不单列
                groups[t] = g
        for gname, g in groups.items():
            for h in HORIZONS:
                f = g[h].values.astype(float)
                atr = g["atr_pct"].values.astype(float)
                day = g["day"].values
                for sname, side in SIDES.items():
                    net = net_return(f, atr, side)
                    valid = ~np.isnan(net)
                    nn = int(valid.sum())
                    if nn < 5:
                        continue
                    mean, p = boot_mean_p(net)
                    med = median_p(net)
                    frac, lodo, wday = day_contrib(net, day)
                    wr = float((net[valid] > 0).mean())
                    rows.append(dict(
                        split=tag, wt=wt, grp=gname, horizon=h, side=sname,
                        n=nn, net_mean=round(mean,4), net_median=round(med,4),
                        winrate=round(wr,4), p_mean=p,
                        max_one_day_frac=round(frac,4), lodo_mean=round(lodo,4),
                        worst_day=wday))
    return pd.DataFrame(rows)


def main():
    df = load()
    print("loaded", len(df), "rows; dev", int(df.is_dev.sum()), "val", int((~df.is_dev).sum()))

    # ===== DEV: 建全部 cell, BH-FDR =====
    dev_cells = build_cells(df, df["is_dev"].values, "dev")
    # FDR 只在 "方向对的" 上做? 不——family = 所有测过的 cell。两个方向都测了, 都计入。
    dev_cells["q_mean"] = bh_fdr(dev_cells["p_mean"].values)
    dev_cells = dev_cells.sort_values("p_mean").reset_index(drop=True)
    dev_cells.to_csv(os.path.join(OUT, "cells_dev.csv"), index=False)
    n_tested = len(dev_cells)
    print("\n=== DEV: tested %d cells (family size for FDR) ===" % n_tested)

    # ===== 候选门槛 (dev) =====
    # 通用: q<0.10, net_mean>0, n>=MIN_N, max_one_day_frac<=0.40
    # 做多额外: net_median>0
    # 做空: 只看均值 (已在 net_mean)
    cand = dev_cells[
        (dev_cells["q_mean"] < FDR_Q) &
        (dev_cells["net_mean"] > 0) &
        (dev_cells["n"] >= MIN_N) &
        (dev_cells["max_one_day_frac"] <= 0.40) &
        (dev_cells["lodo_mean"] > 0)
    ].copy()
    # 做多中位也要正
    long_bad = (cand["side"] == "long") & (cand["net_median"] <= 0)
    cand = cand[~long_bad].reset_index(drop=True)
    print("dev candidates passing all gates:", len(cand))
    print(cand.to_string())

    # ===== VAL: 对每个 dev 候选, 在 val 上重算同一 cell =====
    val_mask = (~df["is_dev"]).values
    results = []
    for _, c in cand.iterrows():
        g = df[val_mask & (df["wt"] == c["wt"])]
        if c["grp"] != "ALL":
            g = g.assign(_tier=chg_tier(g["chg"].values))
            g = g[g["_tier"] == c["grp"]]
        f = g[c["horizon"]].values.astype(float)
        atr = g["atr_pct"].values.astype(float)
        day = g["day"].values
        side = SIDES[c["side"]]
        net = net_return(f, atr, side)
        valid = ~np.isnan(net)
        nn = int(valid.sum())
        if nn < 5:
            vmean, vp, vmed, vwr, vfrac, vlodo = (np.nan,)*6
        else:
            vmean, vp = boot_mean_p(net)
            vmed = median_p(net)
            vwr = float((net[valid] > 0).mean())
            vfrac, vlodo, _ = day_contrib(net, day)
        # val 确认: 同号(均值仍>0) + 扣成本仍正(net 已扣) + (做多)中位>0
        confirm = (not np.isnan(vmean)) and (vmean > 0)
        if c["side"] == "long":
            confirm = confirm and (vmed > 0)
        results.append(dict(
            wt=c["wt"], grp=c["grp"], horizon=c["horizon"], side=c["side"],
            dev_n=int(c["n"]), dev_net_mean=c["net_mean"], dev_net_median=c["net_median"],
            dev_winrate=c["winrate"], dev_q=round(float(c["q_mean"]),5),
            dev_max_one_day_frac=c["max_one_day_frac"], dev_lodo=c["lodo_mean"],
            val_n=nn, val_net_mean=round(float(vmean),4) if not np.isnan(vmean) else None,
            val_net_median=round(float(vmed),4) if not np.isnan(vmed) else None,
            val_winrate=round(float(vwr),4) if nn>=5 else None,
            val_p_mean=round(float(vp),5) if nn>=5 else None,
            val_max_one_day_frac=round(float(vfrac),4) if nn>=5 else None,
            val_lodo=round(float(vlodo),4) if nn>=5 else None,
            VAL_CONFIRMED=bool(confirm)))
    out = dict(
        family="fam_A_direction_after_alert",
        n_cells_tested=int(n_tested),
        fdr_q_threshold=FDR_Q,
        cost_model="roundtrip taker 0.14% + slippage oneside*2 (atr>=1.5:0.4, atr>=3:0.6)",
        dev_candidates=int(len(cand)),
        val_confirmed=int(sum(r["VAL_CONFIRMED"] for r in results)),
        candidates=results)
    with open(os.path.join(OUT, "survivors.json"), "w") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False, default=str)
    print("\n=== VAL CONFIRMATION ===")
    print(json.dumps(results, indent=2, ensure_ascii=False, default=str))
    print("\nwrote cells_dev.csv + survivors.json")

if __name__ == "__main__":
    main()
