#!/usr/bin/env python3
"""
任务B: 动量 vs 情绪拆解 — stockubot 的 sentiment 层在免费动量因子之外是否加 alpha?

核心问题: combined_score ≈ tech_score(动量) + sentiment。
LS 的预测力到底来自 momentum_20d_pct(免费动量) 还是 sentiment?

方法:
1. 单因子排序 LS: momentum_20d_pct 单独排名 vs sentiment 单独排名, 各 horizon。
2. 增量检验 (核心): 每天横截面把 fwd 收益对 momentum_20d_pct 回归取残差,
   再看 sentiment 能否预测残差 (横截面 rank 相关 + 残差上的 sentiment-LS)。
   等价: momentum-中性 的 sentiment 双重排序。
3. 结论: sentiment 在免费动量之外加不加 alpha。

铁律:
- LS = mean(多腿 fwd) − mean(空腿 fwd), 等权 dollar-neutral, 已是市场中性量。
- 成本: 永续往返 0.10%/腿, 多空两腿都扣, 每次调仓换手都算。
- 有效样本: 18天, 5d 持有重叠 → 有效独立观测 ≈3-4。一切探索性。
  报 daily-rebal(重叠) + 非重叠(每h天调仓) 两种。
- 做空看均值 (防左尾)。
- numpy 可用, scipy 不可用 (手写 spearman / permutation)。
"""
import json
import math
import numpy as np

PANEL = "/Volumes/T9/BWE/40_EXPERIMENTS/round25_stockusbinance/radar_panel.jsonl"
COST_PER_LEG = 0.10  # % 往返每腿; LS 两腿都扣 → 总成本 2*0.10 = 0.20% per rebalance
HORIZONS = ["f1", "f2", "f3", "f5"]
HOLD = {"f1": 1, "f2": 2, "f3": 3, "f5": 5}  # 持有天数 → 非重叠步长


def load():
    rows = [json.loads(l) for l in open(PANEL)]
    return rows


def by_date(rows):
    d = {}
    for r in rows:
        d.setdefault(r["date"], []).append(r)
    return d, sorted(d.keys())


# ----- 手写统计 -----
def rankdata(x):
    """平均秩 (处理 ties), 返回 1..n 秩。"""
    x = np.asarray(x, float)
    n = len(x)
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty(n, float)
    i = 0
    while i < n:
        j = i
        while j + 1 < n and x[order[j + 1]] == x[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0  # 平均秩 (1-based)
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(a, b):
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    mask = ~(np.isnan(a) | np.isnan(b))
    a, b = a[mask], b[mask]
    if len(a) < 3:
        return float("nan"), 0
    ra, rb = rankdata(a), rankdata(b)
    ra = ra - ra.mean()
    rb = rb - rb.mean()
    denom = math.sqrt((ra * ra).sum() * (rb * rb).sum())
    if denom == 0:
        return float("nan"), len(a)
    return float((ra * rb).sum() / denom), len(a)


def pearson(a, b):
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    mask = ~(np.isnan(a) | np.isnan(b))
    a, b = a[mask], b[mask]
    if len(a) < 3:
        return float("nan")
    a = a - a.mean()
    b = b - b.mean()
    denom = math.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / denom) if denom else float("nan")


def ols_resid(y, x):
    """y 对 x 单变量 OLS, 返回残差 (含截距)。NaN 安全: 只在有效点拟合, 残差对全体计算。"""
    y = np.asarray(y, float)
    x = np.asarray(x, float)
    mask = ~(np.isnan(y) | np.isnan(x))
    if mask.sum() < 3:
        return np.full_like(y, np.nan)
    xv, yv = x[mask], y[mask]
    A = np.vstack([xv, np.ones_like(xv)]).T
    coef, *_ = np.linalg.lstsq(A, yv, rcond=None)
    pred = coef[0] * x + coef[1]
    resid = y - pred
    resid[~mask] = np.nan
    return resid


# ----- LS 构造 (tercile, dollar-neutral) -----
def daily_ls(day_rows, score_key, fwd_key, market_neutral=False):
    """单日: 按 score 排名, 多最高 tercile, 空最低 tercile, 等权。
    返回 (gross_ls, long_mean, short_mean, n_long, n_short)。
    market_neutral=True: fwd 减去当日市场等权 (mkt_*) 再算。
    返回 None 若可交易名太少。"""
    cand = [r for r in day_rows if r.get(fwd_key) is not None and r.get(score_key) is not None]
    if len(cand) < 3:
        return None
    mkt_key = "mkt_" + fwd_key
    def fwd(r):
        v = r[fwd_key]
        if market_neutral and r.get(mkt_key) is not None:
            v = v - r[mkt_key]
        return v
    cand_sorted = sorted(cand, key=lambda r: r[score_key])
    n = len(cand_sorted)
    k = max(1, n // 3)  # tercile 大小
    short_leg = cand_sorted[:k]   # 最低分 → 空
    long_leg = cand_sorted[-k:]   # 最高分 → 多
    lm = float(np.mean([fwd(r) for r in long_leg]))   # 均值, 防左尾
    sm = float(np.mean([fwd(r) for r in short_leg]))
    gross = lm - sm  # dollar-neutral LS, 本身市场中性
    return gross, lm, sm, len(long_leg), len(short_leg)


def aggregate_ls(dates, dbd, score_key, fwd_key, market_neutral=False):
    """daily-rebal (重叠): 每天都建仓, 收集每日 LS 序列。
    成本: 每次调仓 = 2 腿 × COST_PER_LEG。daily-rebal 假设每日全换手。"""
    rec = []
    for d in dates:
        out = daily_ls(dbd[d], score_key, fwd_key, market_neutral)
        if out is None:
            continue
        gross, lm, sm, nl, ns = out
        rec.append((d, gross, lm, sm))
    if not rec:
        return None
    gross_arr = np.array([x[1] for x in rec])
    # daily-rebal 成本: 持有 HOLD 天但每天重建 → 每日扣 2 腿换手
    cost = 2 * COST_PER_LEG
    net_arr = gross_arr - cost
    return {
        "n_days": len(rec),
        "gross_mean_per_period": float(gross_arr.mean()),
        "net_mean_per_period": float(net_arr.mean()),
        "gross_std": float(gross_arr.std(ddof=1)) if len(gross_arr) > 1 else float("nan"),
        "long_mean": float(np.mean([x[2] for x in rec])),
        "short_mean": float(np.mean([x[3] for x in rec])),
        "series": [(x[0], x[1]) for x in rec],
    }


def aggregate_ls_nonoverlap(dates, dbd, score_key, fwd_key, hold, market_neutral=False):
    """非重叠: 每 hold 天调仓一次, 持有期与 fwd horizon 匹配。
    成本: 每次调仓 = 2 腿 × COST_PER_LEG, 换算到 per-day 用于对照。"""
    rec = []
    i = 0
    di = list(dates)
    while i < len(di):
        d = di[i]
        out = daily_ls(dbd[d], score_key, fwd_key, market_neutral)
        if out is not None:
            gross, lm, sm, nl, ns = out
            rec.append((d, gross, lm, sm))
        i += hold
    if not rec:
        return None
    gross_arr = np.array([x[1] for x in rec])
    cost = 2 * COST_PER_LEG  # 每次调仓总成本
    net_arr = gross_arr - cost
    # per-period = 整个 hold 期收益; per-day = /hold 便于横比
    return {
        "n_rebal": len(rec),
        "gross_mean_per_period": float(gross_arr.mean()),
        "net_mean_per_period": float(net_arr.mean()),
        "gross_mean_per_day": float(gross_arr.mean() / hold),
        "net_mean_per_day": float(net_arr.mean() / hold),
        "gross_std": float(gross_arr.std(ddof=1)) if len(gross_arr) > 1 else float("nan"),
        "series": [(x[0], x[1]) for x in rec],
    }


# ----- permutation: 每日把 score 随机洗牌, 看 LS 序列均值的 null 分布 -----
def permutation_pvalue(dates, dbd, score_key, fwd_key, observed_net, n_perm=2000, seed=42,
                       market_neutral=False, nonoverlap=False, hold=1):
    rng = np.random.default_rng(seed)
    null = np.zeros(n_perm)
    for p in range(n_perm):
        means = []
        di = list(dates)
        idx = 0
        step = hold if nonoverlap else 1
        while idx < len(di):
            d = di[idx]
            rows = dbd[d]
            cand = [r for r in rows if r.get(fwd_key) is not None and r.get(score_key) is not None]
            if len(cand) >= 3:
                fwd_key2 = fwd_key
                mkt_key = "mkt_" + fwd_key
                vals = np.array([
                    (r[fwd_key] - (r[mkt_key] if (market_neutral and r.get(mkt_key) is not None) else 0))
                    for r in cand
                ])
                n = len(vals)
                k = max(1, n // 3)
                perm = rng.permutation(n)  # 洗牌分数→等价洗牌仓位分配
                long_idx = perm[-k:]
                short_idx = perm[:k]
                means.append(vals[long_idx].mean() - vals[short_idx].mean())
            idx += step
        if means:
            null[p] = np.mean(means)
    cost = 2 * COST_PER_LEG
    null_net = null - cost  # null 也扣同样成本以可比
    # 单尾: observed_net >= null_net 的比例
    pval = float((np.sum(null_net >= observed_net) + 1) / (n_perm + 1))
    return pval, float(null_net.mean()), float(null_net.std())


def fmt(x, nd=4):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "nan"
    return round(float(x), nd)


def main():
    rows = load()
    dbd, dates = by_date(rows)

    result = {
        "meta": {
            "panel": PANEL,
            "n_rows": len(rows),
            "n_dates": len(dates),
            "n_tickers": len(set(r["ticker"] for r in rows)),
            "cost_per_leg_pct": COST_PER_LEG,
            "cost_per_rebalance_pct": 2 * COST_PER_LEG,
            "effective_independent_obs_estimate": "3-4 (18 days, up to 5d overlap)",
            "disclaimer": "探索性, 不可下结论。18天有效独立观测约3-4, 无统计力。",
        }
    }

    # =========================================================
    # 0. 因子结构诊断: combined / tech / sentiment / momentum 的关系
    # =========================================================
    ts = np.array([r["tech_score"] for r in rows])
    mom = np.array([r["momentum_20d_pct"] for r in rows])
    sent = np.array([r["sentiment"] for r in rows])
    comb = np.array([r["combined_score"] for r in rows])
    result["factor_structure"] = {
        "combined_minus_tech_plus_sentiment_mean": fmt(float(np.mean(comb - (ts + sent)))),
        "note_combined_decomp": "combined != tech+sentiment 精确; 有惩罚项(mean ~ -0.087)",
        "tech_score_unique_values": sorted(set(round(float(x), 3) for x in ts)),
        "pearson_tech_vs_momentum": fmt(pearson(ts, mom)),
        "pearson_sentiment_vs_momentum": fmt(pearson(sent, mom)),
        "pearson_sentiment_vs_tech": fmt(pearson(sent, ts)),
        "pearson_combined_vs_momentum": fmt(pearson(comb, mom)),
        "key_warning": "sentiment 本身与 momentum 相关 (pearson~0.52) → 单因子 sentiment-LS 会偷动量的功劳; 必须做动量中性增量检验",
    }

    # =========================================================
    # 1. 单因子排序 LS: momentum vs sentiment vs combined, 各 horizon
    #    报 daily-rebal(重叠) + 非重叠 两口径; 同时报 raw 与 市场中性
    # =========================================================
    single = {}
    for score_key in ["momentum_20d_pct", "sentiment", "combined_score", "tech_score"]:
        single[score_key] = {}
        for fwd_key in HORIZONS:
            hold = HOLD[fwd_key]
            daily = aggregate_ls(dates, dbd, score_key, fwd_key, market_neutral=False)
            daily_mn = aggregate_ls(dates, dbd, score_key, fwd_key, market_neutral=True)
            nonov = aggregate_ls_nonoverlap(dates, dbd, score_key, fwd_key, hold, market_neutral=False)
            entry = {}
            if daily:
                entry["daily_rebal"] = {
                    "n_days": daily["n_days"],
                    "gross_per_period_pct": fmt(daily["gross_mean_per_period"]),
                    "net_per_period_pct": fmt(daily["net_mean_per_period"]),
                    "long_mean_pct": fmt(daily["long_mean"]),
                    "short_mean_pct": fmt(daily["short_mean"]),
                    "gross_std": fmt(daily["gross_std"]),
                }
                # permutation on daily-rebal net
                pv, nm, ns = permutation_pvalue(
                    dates, dbd, score_key, fwd_key, daily["net_mean_per_period"],
                    n_perm=2000, market_neutral=False, nonoverlap=False, hold=1)
                entry["daily_rebal"]["perm_pvalue_1sided"] = fmt(pv, 4)
            if daily_mn:
                entry["daily_rebal_market_neutral"] = {
                    "gross_per_period_pct": fmt(daily_mn["gross_mean_per_period"]),
                    "net_per_period_pct": fmt(daily_mn["net_mean_per_period"]),
                }
            if nonov:
                entry["nonoverlap"] = {
                    "hold_days": hold,
                    "n_rebal": nonov["n_rebal"],
                    "gross_per_period_pct": fmt(nonov["gross_mean_per_period"]),
                    "net_per_period_pct": fmt(nonov["net_mean_per_period"]),
                    "gross_per_day_pct": fmt(nonov["gross_mean_per_day"]),
                    "net_per_day_pct": fmt(nonov["net_mean_per_day"]),
                }
            single[score_key][fwd_key] = entry
    result["single_factor_LS"] = single

    # =========================================================
    # 2. 增量检验 (核心): 每天横截面 fwd 对 momentum 回归取残差,
    #    sentiment 能否预测残差?
    #    (a) 横截面 rank 相关: pool 每日 spearman(sentiment, resid), 报均值 + permutation
    #    (b) 残差上的 sentiment-LS: 用 sentiment 排名做多空, 但 fwd 用残差
    #    (c) 等价的 momentum-中性 sentiment 双重排序
    # =========================================================
    incremental = {}
    for fwd_key in HORIZONS:
        hold = HOLD[fwd_key]
        # ---- (a) per-day spearman(sentiment, momentum-residual of fwd) ----
        per_day_rho = []
        per_day_n = []
        for d in dates:
            cand = [r for r in dbd[d] if r.get(fwd_key) is not None]
            if len(cand) < 4:
                continue
            y = np.array([r[fwd_key] for r in cand], float)
            xmom = np.array([r["momentum_20d_pct"] for r in cand], float)
            xsent = np.array([r["sentiment"] for r in cand], float)
            resid = ols_resid(y, xmom)  # fwd 去掉动量解释部分
            rho, nn = spearman(xsent, resid)
            if not math.isnan(rho):
                per_day_rho.append(rho)
                per_day_n.append(nn)
        rho_arr = np.array(per_day_rho)
        # permutation: 每日 shuffle sentiment, 重算 spearman 均值
        rng = np.random.default_rng(7)
        nperm = 2000
        null_means = np.zeros(nperm)
        # 预存每日 (resid, sentiment) 以加速
        day_cache = []
        for d in dates:
            cand = [r for r in dbd[d] if r.get(fwd_key) is not None]
            if len(cand) < 4:
                continue
            y = np.array([r[fwd_key] for r in cand], float)
            xmom = np.array([r["momentum_20d_pct"] for r in cand], float)
            xsent = np.array([r["sentiment"] for r in cand], float)
            resid = ols_resid(y, xmom)
            day_cache.append((xsent, resid))
        for p in range(nperm):
            vals = []
            for xsent, resid in day_cache:
                xs = rng.permutation(xsent)
                rho, _ = spearman(xs, resid)
                if not math.isnan(rho):
                    vals.append(rho)
            null_means[p] = np.mean(vals) if vals else 0.0
        obs_mean = float(rho_arr.mean()) if len(rho_arr) else float("nan")
        # 双尾 p (机制方向未知)
        pval_a = float((np.sum(np.abs(null_means) >= abs(obs_mean)) + 1) / (nperm + 1)) if not math.isnan(obs_mean) else float("nan")

        # ---- (b) 残差上的 sentiment-LS (sentiment 排名做多空, fwd=momentum 残差) ----
        # 自定义 daily LS: score=sentiment, target=resid
        resid_ls = []
        for d in dates:
            cand = [r for r in dbd[d] if r.get(fwd_key) is not None]
            if len(cand) < 3:
                continue
            y = np.array([r[fwd_key] for r in cand], float)
            xmom = np.array([r["momentum_20d_pct"] for r in cand], float)
            resid = ols_resid(y, xmom)
            sent_v = np.array([r["sentiment"] for r in cand], float)
            order = np.argsort(sent_v, kind="mergesort")
            n = len(order); k = max(1, n // 3)
            long_idx = order[-k:]; short_idx = order[:k]
            lm = float(np.nanmean(resid[long_idx]))
            sm = float(np.nanmean(resid[short_idx]))
            if not (math.isnan(lm) or math.isnan(sm)):
                resid_ls.append(lm - sm)
        resid_ls = np.array(resid_ls)
        resid_ls_gross = float(resid_ls.mean()) if len(resid_ls) else float("nan")
        # 注: 残差 LS 是"动量已剥离后的纯 sentiment LS"; 成本同样 2 腿
        resid_ls_net = resid_ls_gross - 2 * COST_PER_LEG if not math.isnan(resid_ls_gross) else float("nan")

        incremental[fwd_key] = {
            "spearman_sentiment_vs_momResidual": {
                "per_day_mean_rho": fmt(obs_mean),
                "n_days_used": len(rho_arr),
                "perm_pvalue_2sided": fmt(pval_a, 4),
                "null_mean": fmt(float(null_means.mean())),
                "interpretation": "sentiment 对'去动量后残差'的横截面相关; 正且显著=sentiment 有增量",
            },
            "sentiment_LS_on_momResidual": {
                "n_days": int(len(resid_ls)),
                "gross_per_period_pct": fmt(resid_ls_gross),
                "net_per_period_pct": fmt(resid_ls_net),
                "interpretation": "动量剥离后, 纯 sentiment 多空的残差收益; >0 (扣成本后) = 增量 alpha",
            },
        }
    result["incremental_sentiment_over_momentum"] = incremental

    # =========================================================
    # 3. 双重排序 (double sort): 先按 momentum 分两半 (中性化),
    #    每半内按 sentiment 分多空, 合并 LS。看 sentiment 在控制动量后的效应。
    # =========================================================
    double_sort = {}
    for fwd_key in HORIZONS:
        ls_series = []
        for d in dates:
            cand = [r for r in dbd[d] if r.get(fwd_key) is not None]
            if len(cand) < 6:
                continue
            mom_v = np.array([r["momentum_20d_pct"] for r in cand], float)
            med = np.median(mom_v)
            longs, shorts = [], []
            for half_mask in [mom_v <= med, mom_v > med]:
                idx = np.where(half_mask)[0]
                if len(idx) < 2:
                    continue
                sub = [cand[i] for i in idx]
                sub_sent = np.array([r["sentiment"] for r in sub], float)
                so = np.argsort(sub_sent, kind="mergesort")
                kk = max(1, len(so) // 2)  # 半内 上下半
                hi = so[-kk:]; lo = so[:kk]
                longs += [sub[i][fwd_key] for i in hi]
                shorts += [sub[i][fwd_key] for i in lo]
            if longs and shorts:
                ls_series.append(float(np.mean(longs) - np.mean(shorts)))
        ls_arr = np.array(ls_series)
        g = float(ls_arr.mean()) if len(ls_arr) else float("nan")
        double_sort[fwd_key] = {
            "n_days": int(len(ls_arr)),
            "gross_per_period_pct": fmt(g),
            "net_per_period_pct": fmt(g - 2 * COST_PER_LEG if not math.isnan(g) else float("nan")),
            "interpretation": "动量内分组后 sentiment 多空 (动量中性的 sentiment 效应)",
        }
    result["double_sort_momentum_controlled_sentiment"] = double_sort

    # =========================================================
    # 3b. 集中度/稳健性检验: f5 是唯一出信号的 horizon, 但 n 极薄。
    #     问: 是不是单名(MRVL)/单日/右尾驱动? leave-one-ticker-out + winsor。
    # =========================================================
    def f5_sent_ls(exclude_ticker=None, winsor=None):
        series = []
        for d in dates:
            cand = [r for r in dbd[d] if r.get("f5") is not None
                    and (exclude_ticker is None or r["ticker"] != exclude_ticker)]
            if len(cand) < 3:
                continue
            cand = sorted(cand, key=lambda r: r["sentiment"])
            n = len(cand); k = max(1, n // 3)
            def g(r):
                v = r["f5"]
                if winsor is not None:
                    v = max(-winsor, min(winsor, v))
                return v
            lm = float(np.mean([g(r) for r in cand[-k:]]))
            sm = float(np.mean([g(r) for r in cand[:k]]))
            series.append(lm - sm)
        return np.array(series)
    base = f5_sent_ls()
    # leave-one-ticker-out: 找影响最大的名
    loo = {}
    for tk in sorted(set(r["ticker"] for r in rows)):
        s = f5_sent_ls(exclude_ticker=tk)
        if len(s):
            loo[tk] = round(float(s.mean()), 3)
    loo_sorted = sorted(loo.items(), key=lambda kv: kv[1])  # 升序: 最低=该名贡献最大正向
    result["f5_sentiment_robustness"] = {
        "gross_all_pct": fmt(float(base.mean())),
        "n_days": int(len(base)),
        "positive_days": int((base > 0).sum()),
        "median_pct": fmt(float(np.median(base))),
        "drop_largest_abs_day_pct": fmt(float(np.sort(base)[np.argsort(np.abs(base))][:-1].mean())) if len(base) > 1 else "nan",
        "exclude_MRVL_pct": loo.get("MRVL"),
        "exclude_SNDK_pct": loo.get("SNDK"),
        "winsor_15pct": fmt(float(f5_sent_ls(winsor=15).mean())),
        "winsor_10pct": fmt(float(f5_sent_ls(winsor=10).mean())),
        "most_impactful_3_tickers_when_removed": loo_sorted[:3],
        "verdict": "f5 sentiment LS 高度集中在少数名/右尾: 去 MRVL 从 3.76→~1.3, winsor10 →~1.4。非稳健, 单名驱动。",
    }

    # =========================================================
    # 4. 概括判定
    # =========================================================
    # 取 f1..f5 净 LS, 比较 momentum vs sentiment, 以及增量
    verdict = {}
    for fwd_key in HORIZONS:
        mom_net = single["momentum_20d_pct"][fwd_key].get("daily_rebal", {}).get("net_per_period_pct")
        sent_net = single["sentiment"][fwd_key].get("daily_rebal", {}).get("net_per_period_pct")
        comb_net = single["combined_score"][fwd_key].get("daily_rebal", {}).get("net_per_period_pct")
        incr_net = incremental[fwd_key]["sentiment_LS_on_momResidual"]["net_per_period_pct"]
        incr_rho = incremental[fwd_key]["spearman_sentiment_vs_momResidual"]["per_day_mean_rho"]
        incr_p = incremental[fwd_key]["spearman_sentiment_vs_momResidual"]["perm_pvalue_2sided"]
        verdict[fwd_key] = {
            "momentum_LS_net": mom_net,
            "sentiment_LS_net": sent_net,
            "combined_LS_net": comb_net,
            "sentiment_incremental_LS_net_over_momentum": incr_net,
            "sentiment_resid_rho": incr_rho,
            "sentiment_resid_perm_p": incr_p,
        }
    result["verdict_by_horizon"] = verdict

    out_path = "/Volumes/T9/BWE/40_EXPERIMENTS/round25_stockusbinance/radar_backtest/orion/result.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print("wrote", out_path)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
