#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""round26 fam_D — 截面 / regime / 择时 / 市值分层 / 位置 家族 (角度 86-110).

负责轴:
  - 位置:    dist_hi24 (贴24h高 -> 续涨 or 见顶空), dist_lo24 (贴24h低 -> 超跌反弹)
  - 24h背景: chg24 (已大涨再触发=见顶空; 已大跌触发=反弹)
  - 波动分层: atr_pct (妖币层, round14/D 核心) — 全覆盖, 主用
  - 市值/流动: qv24 / mc — 仅 ~11% / ~9% 覆盖, 探索性 only
  - BTC regime: breg (0熊1震2牛)
  - 时段:    hour (UTC), dow (周内)
  - 截面相对强弱: 同一时间桶内多币触发, 追最强 vs 最弱 (round15 a02 重做)
  - 组合:    最有希望的 2-3 维交互, 每加一维样本骤减, n<100 标死

铁律 (与 fam_A/B 一致):
 1. 做空 = -f; 做空判定只看均值; 做多需 均值 AND 中位 都 > 0。
 2. 成本: 往返 taker 0.14% + 妖币滑点 (atr_pct>=1.5% 额外单边 0.4%; atr_pct>=3% 额外单边 0.6%)。
 3. BH-FDR over ALL tested cells (整个 family 一起)，只信 q<0.10。
 4. LODO 必做: max_one_day_frac (单日贡献绝对值 / 总绝对贡献) > 0.40 -> 单日 artifact, 毙。
    额外: drop 贡献最大那天后均值仍同号 (lodo_mean)。重点查 2025-10-10。
 5. cell n<100 -> 探索性 (不进可交易候选)。
 6. dev 选候选 -> val 验一次 (同号 + 扣成本仍正 + 做多中位>0)。
 7. 幸存者偏差: 归零/下架死币缺失 -> 做空真实表现可能更好, 结论标注。

输出: cells_dev.csv (所有测过 cell), survivors.json, summary 打印。不写 report。
"""
import sqlite3
import json
import os
import numpy as np
import pandas as pd

DB = "/Volumes/T9/BWE/40_EXPERIMENTS/round26_alert_alpha/alert_panel.sqlite3"
OUT = "/Volumes/T9/BWE/40_EXPERIMENTS/round26_alert_alpha/fam_D"
DEV_CUTOFF = 1778803200000  # ts_ms<=this -> dev (~05-15 前); 之后 val
RNG = np.random.default_rng(20260611)
N_BOOT = 20000
FDR_Q = 0.10
ROUNDTRIP_TAKER = 0.14  # %, 往返
MIN_N = 100
LODO_FRAC_KILL = 0.40
LODO_DAY = "2025-10-10"  # 必查的崩盘日


# ---------- 成本 ----------
def slip_oneside(atr_pct):
    a = np.where(np.isnan(atr_pct), 0.0, atr_pct)
    s = np.zeros_like(a, dtype=float)
    s = np.where(a >= 1.5, 0.4, s)
    s = np.where(a >= 3.0, 0.6, s)
    return s  # 单边额外滑点 %


def cost_roundtrip(atr_pct):
    return ROUNDTRIP_TAKER + 2.0 * slip_oneside(atr_pct)


def net_return(f, atr_pct, side):
    """side=+1 做多, -1 做空。净 = side*f - 往返成本。"""
    return side * f - cost_roundtrip(atr_pct)


# ---------- 统计 ----------
def _norm_sf(z):
    import math
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def boot_mean_p(x):
    """单侧 p: H0 真实均值<=0。返回 (mean, p_gt0)。p_gt0 小 = 有证据均值>0。

    n>=2000: 用解析正态近似 (CLT 在此 n 下与 bootstrap 不可区分, 且 O(n) 内存安全)。
    n<2000: bootstrap (与 fam_A 一致), 内存上限 N_BOOT*n < 4e7 安全。"""
    import math
    x = x[~np.isnan(x)]
    n = len(x)
    if n < 5:
        return np.nan, 1.0
    mean = float(x.mean())
    if n >= 2000:
        sd = x.std(ddof=1)
        if sd == 0:
            return mean, 0.0 if mean > 0 else 1.0
        z = mean / (sd / math.sqrt(n))
        # p(真实均值<=0) ~ 单侧上尾: mean>0 时 = SF(z); mean<=0 时 ->大
        return mean, float(_norm_sf(z))
    idx = RNG.integers(0, n, size=(N_BOOT, n))
    bmeans = x[idx].mean(axis=1)
    return mean, float((bmeans <= 0).mean())


def bh_fdr(pvals):
    p = np.asarray(pvals, float)
    m = len(p)
    if m == 0:
        return p
    order = np.argsort(p)
    ranked = p[order]
    q = ranked * m / (np.arange(1, m + 1))
    q = np.minimum.accumulate(q[::-1])[::-1]
    q = np.clip(q, 0, 1)
    out = np.empty(m)
    out[order] = q
    return out


def day_contrib(net, days):
    """返回 (max_one_day_frac, lodo_mean, worst_day, frac_20251010)。
    max_one_day_frac = 对总收益方向贡献绝对值最大那天的 |sum| / 总 |sum|。
    lodo_mean = 去掉那天后的均值。frac_20251010 = 该崩盘日单独占比。"""
    net = np.asarray(net, float)
    mask = ~np.isnan(net)
    net = net[mask]
    days = np.asarray(days)[mask]
    total = net.sum()
    if len(net) == 0 or total == 0:
        return 1.0, np.nan, None, np.nan
    uniq = pd.unique(days)
    day_sums = {d: net[days == d].sum() for d in uniq}
    abs_total = sum(abs(v) for v in day_sums.values())
    if total > 0:
        worst_day = max(day_sums, key=lambda d: day_sums[d])
    else:
        worst_day = min(day_sums, key=lambda d: day_sums[d])
    frac = abs(day_sums[worst_day]) / abs_total if abs_total > 0 else 1.0
    lodo = net[days != worst_day].mean()
    frac_crash = (abs(day_sums.get(LODO_DAY, 0.0)) / abs_total) if abs_total > 0 else np.nan
    return float(frac), float(lodo), str(worst_day), float(frac_crash)


def cell_eval(sub, side, h, label, split):
    """对一个子集算一个 cell 的全部统计。返回 dict 或 None (n太小)。"""
    f = sub[h].values.astype(float)
    atr = sub["atr_pct"].values.astype(float)
    day = sub["day"].values
    nr = net_return(f, atr, side)
    valid = ~np.isnan(nr)
    nn = int(valid.sum())
    if nn < 5:
        return None
    mean, p = boot_mean_p(nr)
    nrv = nr[valid]
    med = float(np.median(nrv))
    wr = float((nrv > 0).mean())
    frac, lodo, wday, frac_crash = day_contrib(nr, day)
    return dict(
        split=split, label=label, h=h, side=("long" if side == 1 else "short"),
        n=nn, net_mean=round(mean, 4), net_median=round(med, 4),
        winrate=round(wr, 4), p_mean=p,
        max_one_day_frac=round(frac, 4), lodo_mean=round(lodo, 4),
        worst_day=wday, frac_20251010=round(frac_crash, 4) if frac_crash == frac_crash else None,
    )


# ---------- 数据 ----------
def load():
    con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    df = pd.read_sql_query(
        "SELECT symbol, ts_ms, wt, chg, oi_chg, chg24, qv24, mc, oimc, atr_pct, "
        "dist_hi24, dist_lo24, f60, f240, f1440, breg, hour, dow "
        "FROM panel", con)
    con.close()
    df["day"] = pd.to_datetime(df["ts_ms"], unit="ms", utc=True).dt.strftime("%Y-%m-%d")
    df["is_dev"] = df["ts_ms"] <= DEV_CUTOFF
    return df


HORIZONS = ["f60", "f240", "f1440"]
SIDES = {"long": 1, "short": -1}


def qbin_labels(s, n, prefix):
    """返回与 s 等长的 label 数组 (quantile 分箱); 处理 NaN -> 'na'。"""
    out = np.full(len(s), "na", dtype=object)
    m = s.notna().values
    if m.sum() < n * 20:
        return out
    try:
        codes, bins = pd.qcut(s[m], n, labels=False, duplicates="drop", retbins=True)
    except ValueError:
        return out
    lab = np.array(["%s_q%d" % (prefix, c) for c in codes], dtype=object)
    out[np.where(m)[0]] = lab
    return out


def make_groups(d):
    """对一个 split 子集, 生成 {axis_label: boolean_mask_subdf} 的所有 cell 分组。
    返回 list of (label, subdf)。"""
    groups = []

    # ---- 全样本 baseline (诚实参照) ----
    groups.append(("ALL", d))

    # ---- 1. chg24 背景: 5 分位 + 极端阈值 ----
    c24q = qbin_labels(d["chg24"], 5, "chg24")
    for lab in pd.unique(c24q):
        if lab == "na":
            continue
        g = d[c24q == lab]
        if len(g) >= 30:
            groups.append((lab, g))
    # 极端阈值 (fade 高涨幅 / 抄底大跌)
    for thr in [20, 30, 50, 80]:
        g = d[d["chg24"] >= thr]
        if len(g) >= 30:
            groups.append(("chg24_ge%d" % thr, g))
    for thr in [-10, -20, -30]:
        g = d[d["chg24"] <= thr]
        if len(g) >= 30:
            groups.append(("chg24_le%d" % thr, g))

    # ---- 2. dist_hi24 位置 (负值, 越接近0=越贴24h高) ----
    dhq = qbin_labels(d["dist_hi24"], 5, "disthi")
    for lab in pd.unique(dhq):
        if lab == "na":
            continue
        g = d[dhq == lab]
        if len(g) >= 30:
            groups.append((lab, g))
    # 贴高阈值 (刚突破): dist_hi24 >= -2% / -1%
    for thr in [-2, -1, -0.5]:
        g = d[d["dist_hi24"] >= thr]
        if len(g) >= 30:
            groups.append(("disthi_ge%.1f" % thr, g))

    # ---- 3. dist_lo24 位置 (正值, 越小=越贴24h低) ----
    dlq = qbin_labels(d["dist_lo24"], 5, "distlo")
    for lab in pd.unique(dlq):
        if lab == "na":
            continue
        g = d[dlq == lab]
        if len(g) >= 30:
            groups.append((lab, g))
    for thr in [3, 5, 8]:
        g = d[d["dist_lo24"] <= thr]
        if len(g) >= 30:
            groups.append(("distlo_le%d" % thr, g))

    # ---- 4. atr_pct 波动分层 (妖币层) ----
    for lab, lo, hi in [("atr_lt0.5", -1, 0.5), ("atr_0.5_1.5", 0.5, 1.5),
                        ("atr_1.5_3", 1.5, 3.0), ("atr_ge3", 3.0, 1e9)]:
        g = d[(d["atr_pct"] >= lo) & (d["atr_pct"] < hi)]
        if len(g) >= 30:
            groups.append((lab, g))

    # ---- 5. breg BTC regime ----
    for b, name in [(0, "breg_bear"), (1, "breg_chop"), (2, "breg_bull")]:
        g = d[d["breg"] == b]
        if len(g) >= 30:
            groups.append((name, g))

    # ---- 6. hour UTC 时段桶 ----
    for lab, hrs in [("hr_asia_0_4", range(0, 4)), ("hr_asia_4_8", range(4, 8)),
                     ("hr_eu_8_12", range(8, 12)), ("hr_eu_12_16", range(12, 16)),
                     ("hr_us_16_20", range(16, 20)), ("hr_us_20_24", range(20, 24))]:
        g = d[d["hour"].isin(list(hrs))]
        if len(g) >= 30:
            groups.append((lab, g))

    # ---- 7. dow 周内 ----
    for dw in range(7):
        g = d[d["dow"] == dw]
        if len(g) >= 30:
            groups.append(("dow%d" % dw, g))

    # ---- 8. qv24 / mc 流动性-市值 (探索性, 覆盖低) ----
    qvq = qbin_labels(d["qv24"], 4, "qv24")
    for lab in pd.unique(qvq):
        if lab == "na":
            continue
        g = d[qvq == lab]
        if len(g) >= 30:
            groups.append((lab + "_EXPL", g))
    mcq = qbin_labels(d["mc"], 4, "mc")
    for lab in pd.unique(mcq):
        if lab == "na":
            continue
        g = d[mcq == lab]
        if len(g) >= 30:
            groups.append((lab + "_EXPL", g))

    # ---- 9. 截面相对强弱: 同一 10min 桶内按 |chg| 排名 ----
    dd = d.copy()
    dd["bucket"] = (dd["ts_ms"] // (10 * 60 * 1000))
    dd["_amag"] = dd["chg"].abs()
    dd["_absrank"] = dd.groupby("bucket")["_amag"].rank(pct=True)
    dd["_bsize"] = dd.groupby("bucket")["_amag"].transform("size")
    multi = dd[dd["_bsize"] >= 3]  # 只在多币同时触发的桶里比强弱 (按 |chg| 排名)
    if len(multi) >= 100:
        groups.append(("xs_strongest", multi[multi["_absrank"] >= 0.8]))
        groups.append(("xs_weakest", multi[multi["_absrank"] <= 0.2]))

    # ---- 10. 组合 (2维, 严防过拟合; n 会在主循环里 gate) ----
    combos = [
        ("C_chg24ge30_x_atrlt1.5", d[(d["chg24"] >= 30) & (d["atr_pct"] < 1.5)]),
        ("C_chg24ge30_x_atrge1.5", d[(d["chg24"] >= 30) & (d["atr_pct"] >= 1.5)]),
        ("C_chg24ge30_x_bear", d[(d["chg24"] >= 30) & (d["breg"] == 0)]),
        ("C_chg24ge30_x_chopbull", d[(d["chg24"] >= 30) & (d["breg"].isin([1, 2]))]),
        ("C_chg24ge30_x_disthi_ge-2", d[(d["chg24"] >= 30) & (d["dist_hi24"] >= -2)]),
        ("C_disthi_ge-1_x_chg24ge15", d[(d["dist_hi24"] >= -1) & (d["chg24"] >= 15)]),
        ("C_chg24ge50_x_oi1h", d[(d["chg24"] >= 50) & (d["wt"] == "oi_price_1h")]),
        ("C_chg24ge30_x_asia0_8", d[(d["chg24"] >= 30) & (d["hour"].isin(range(0, 8)))]),
        ("C_chg24ge30_x_us16_24", d[(d["chg24"] >= 30) & (d["hour"].isin(range(16, 24)))]),
    ]
    for lab, g in combos:
        if len(g) >= 30:
            groups.append((lab, g))

    return groups


def build_cells(d, split):
    rows = []
    for label, g in make_groups(d):
        for h in HORIZONS:
            for sname, side in SIDES.items():
                r = cell_eval(g, side, h, label, split)
                if r is not None:
                    rows.append(r)
    return pd.DataFrame(rows)


def reeval_on(d_val, label, h, side_name):
    """在 val 上对一个 dev 候选 cell 重建同一分组并算统计。"""
    side = SIDES[side_name]
    g = group_by_label(d_val, label)
    if g is None or len(g) == 0:
        return None
    return cell_eval(g, side, h, "val:" + label, "val")


def group_by_label(d, label):
    """根据 label 重建子集 (val 复算用)。必须与 make_groups 的定义一致。"""
    if label == "ALL":
        return d
    # quantile 分箱在 val 上重算 (用 val 自身的分位 — 与 dev 保持 '相对位置' 语义一致)
    if label.startswith("chg24_q"):
        q = int(label.split("q")[1])
        codes = qbin_labels(d["chg24"], 5, "chg24")
        return d[codes == label]
    if label.startswith("chg24_ge"):
        thr = float(label.replace("chg24_ge", ""))
        return d[d["chg24"] >= thr]
    if label.startswith("chg24_le"):
        thr = float(label.replace("chg24_le", ""))
        return d[d["chg24"] <= thr]
    if label.startswith("disthi_q"):
        codes = qbin_labels(d["dist_hi24"], 5, "disthi")
        return d[codes == label]
    if label.startswith("disthi_ge"):
        thr = float(label.replace("disthi_ge", ""))
        return d[d["dist_hi24"] >= thr]
    if label.startswith("distlo_q"):
        codes = qbin_labels(d["dist_lo24"], 5, "distlo")
        return d[codes == label]
    if label.startswith("distlo_le"):
        thr = float(label.replace("distlo_le", ""))
        return d[d["dist_lo24"] <= thr]
    if label.startswith("atr_"):
        bounds = {"atr_lt0.5": (-1, 0.5), "atr_0.5_1.5": (0.5, 1.5),
                  "atr_1.5_3": (1.5, 3.0), "atr_ge3": (3.0, 1e9)}[label]
        return d[(d["atr_pct"] >= bounds[0]) & (d["atr_pct"] < bounds[1])]
    if label.startswith("breg_"):
        b = {"breg_bear": 0, "breg_chop": 1, "breg_bull": 2}[label]
        return d[d["breg"] == b]
    if label.startswith("hr_"):
        hrs = {"hr_asia_0_4": range(0, 4), "hr_asia_4_8": range(4, 8),
               "hr_eu_8_12": range(8, 12), "hr_eu_12_16": range(12, 16),
               "hr_us_16_20": range(16, 20), "hr_us_20_24": range(20, 24)}[label]
        return d[d["hour"].isin(list(hrs))]
    if label.startswith("dow"):
        return d[d["dow"] == int(label[3:])]
    if label.endswith("_EXPL"):
        base = label[:-5]
        if base.startswith("qv24_q"):
            codes = qbin_labels(d["qv24"], 4, "qv24")
            return d[codes == base]
        if base.startswith("mc_q"):
            codes = qbin_labels(d["mc"], 4, "mc")
            return d[codes == base]
    if label in ("xs_strongest", "xs_weakest"):
        dd = d.copy()
        dd["bucket"] = (dd["ts_ms"] // (10 * 60 * 1000))
        dd["_amag"] = dd["chg"].abs()
        dd["_absrank"] = dd.groupby("bucket")["_amag"].rank(pct=True)
        dd["_bsize"] = dd.groupby("bucket")["_amag"].transform("size")
        multi = dd[dd["_bsize"] >= 3]
        if label == "xs_strongest":
            return multi[multi["_absrank"] >= 0.8]
        return multi[multi["_absrank"] <= 0.2]
    if label.startswith("C_"):
        m = {
            "C_chg24ge30_x_atrlt1.5": (d["chg24"] >= 30) & (d["atr_pct"] < 1.5),
            "C_chg24ge30_x_atrge1.5": (d["chg24"] >= 30) & (d["atr_pct"] >= 1.5),
            "C_chg24ge30_x_bear": (d["chg24"] >= 30) & (d["breg"] == 0),
            "C_chg24ge30_x_chopbull": (d["chg24"] >= 30) & (d["breg"].isin([1, 2])),
            "C_chg24ge30_x_disthi_ge-2": (d["chg24"] >= 30) & (d["dist_hi24"] >= -2),
            "C_disthi_ge-1_x_chg24ge15": (d["dist_hi24"] >= -1) & (d["chg24"] >= 15),
            "C_chg24ge50_x_oi1h": (d["chg24"] >= 50) & (d["wt"] == "oi_price_1h"),
            "C_chg24ge30_x_asia0_8": (d["chg24"] >= 30) & (d["hour"].isin(range(0, 8))),
            "C_chg24ge30_x_us16_24": (d["chg24"] >= 30) & (d["hour"].isin(range(16, 24))),
        }.get(label)
        if m is not None:
            return d[m]
    return None


def main():
    df = load()
    print("loaded %d rows; dev %d val %d; dev days %d"
          % (len(df), int(df.is_dev.sum()), int((~df.is_dev).sum()),
             df[df.is_dev]["day"].nunique()))

    dev = df[df.is_dev].copy()
    val = df[~df.is_dev].copy()

    # ===== DEV: 建全部 cell + BH-FDR =====
    cells = build_cells(dev, "dev")
    cells["q_mean"] = bh_fdr(cells["p_mean"].values)
    cells = cells.sort_values("p_mean").reset_index(drop=True)
    cells.to_csv(os.path.join(OUT, "cells_dev.csv"), index=False)
    n_tested = len(cells)
    print("\n=== DEV: tested %d cells (FDR family size) ===" % n_tested)

    # ===== 候选门槛 =====
    # 通用: q<0.10, net_mean>0, n>=MIN_N, max_one_day_frac<=0.40, lodo_mean>0
    # 做多额外: net_median>0
    gate = (
        (cells["q_mean"] < FDR_Q)
        & (cells["net_mean"] > 0)
        & (cells["n"] >= MIN_N)
        & (cells["max_one_day_frac"] <= LODO_FRAC_KILL)
        & (cells["lodo_mean"] > 0)
    )
    cand = cells[gate].copy()
    long_bad = (cand["side"] == "long") & (cand["net_median"] <= 0)
    cand = cand[~long_bad].reset_index(drop=True)
    print("dev candidates passing ALL gates:", len(cand))
    show_cols = ["label", "h", "side", "n", "net_mean", "net_median", "winrate",
                 "q_mean", "max_one_day_frac", "lodo_mean", "frac_20251010"]
    if len(cand):
        print(cand[show_cols].to_string(index=False))

    # 也打印 "近门槛" 的探索性 (n<100 或 frac 偏高但信号强) 供诚实记录
    near = cells[(cells["q_mean"] < FDR_Q) & (cells["net_mean"] > 0)
                 & ~gate].sort_values("net_mean", ascending=False).head(20)
    if len(near):
        print("\n--- 近门槛 / 探索性 (q<0.10 & mean>0 但未过全 gate) top20 ---")
        print(near[show_cols].to_string(index=False))

    # ===== VAL: 对每个候选复算同一 cell =====
    results = []
    for _, c in cand.iterrows():
        vr = reeval_on(val, c["label"], c["h"], c["side"])
        if vr is None or vr["n"] < 5:
            confirm = False
            vr = vr or {}
        else:
            confirm = vr["net_mean"] > 0
            if c["side"] == "long":
                confirm = confirm and (vr["net_median"] > 0)
        results.append(dict(
            label=c["label"], h=c["h"], side=c["side"],
            dev_n=int(c["n"]), dev_net_mean=c["net_mean"], dev_net_median=c["net_median"],
            dev_winrate=c["winrate"], dev_q=round(float(c["q_mean"]), 5),
            dev_max_one_day_frac=c["max_one_day_frac"], dev_lodo=c["lodo_mean"],
            dev_frac_20251010=c["frac_20251010"],
            val_n=int(vr.get("n", 0)),
            val_net_mean=vr.get("net_mean"), val_net_median=vr.get("net_median"),
            val_winrate=vr.get("winrate"), val_p_mean=vr.get("p_mean"),
            val_max_one_day_frac=vr.get("max_one_day_frac"), val_lodo=vr.get("lodo_mean"),
            VAL_CONFIRMED=bool(confirm)))

    out = dict(
        family="fam_D_crosssection_regime_timing_tier_position",
        angles="86-110",
        n_cells_tested=int(n_tested),
        fdr_q_threshold=FDR_Q,
        min_n=MIN_N,
        lodo_frac_kill=LODO_FRAC_KILL,
        cost_model="roundtrip taker 0.14% + slippage oneside*2 (atr>=1.5:0.4, atr>=3:0.6)",
        survivorship_note="数据集缺归零/下架死币 -> 做空真实表现可能比此处更好 (此处偏保守)",
        dev_candidates=int(len(cand)),
        val_confirmed=int(sum(r["VAL_CONFIRMED"] for r in results)),
        candidates=results)
    with open(os.path.join(OUT, "survivors.json"), "w") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False, default=str)

    print("\n=== VAL CONFIRMATION ===")
    print(json.dumps(results, indent=2, ensure_ascii=False, default=str))
    print("\nwrote cells_dev.csv (%d cells) + survivors.json" % n_tested)


if __name__ == "__main__":
    main()
