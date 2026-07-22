#!/usr/bin/env python3
"""radar forward 记分台: 读 radar_panel_forward.jsonl(OOS), 算预注册的4条正交线 + 验收门。
回答: 攒够OOS后, sentiment在动量之外到底有没有增量alpha。只读, 不下单。"""
import json, os, numpy as np
from collections import defaultdict

FWD = "/Volumes/T9/BWE/40_EXPERIMENTS/round25_stockusbinance/radar_panel_forward.jsonl"
COST_LEG = 0.10  # 永续往返%/腿

def spearman(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    m = ~(np.isnan(a) | np.isnan(b))
    if m.sum() < 3: return np.nan
    ra = np.argsort(np.argsort(a[m])); rb = np.argsort(np.argsort(b[m]))
    return np.corrcoef(ra, rb)[0, 1]

def ls_net(by_date, score, h):
    """每日tercile多空净LS序列(/天), 做空看均值。"""
    out = []
    for d, rows in by_date.items():
        sub = [r for r in rows if r.get(score) is not None and r.get(h) is not None]
        if len(sub) < 6: continue
        sub.sort(key=lambda r: -r[score]); k = len(sub)//3
        if k < 1: continue
        lo = np.mean([r[h] for r in sub[:k]]); sh = np.mean([r[h] for r in sub[-k:]])
        hold = int(h[1])
        out.append((lo - sh)/hold - 2*COST_LEG/hold)
    return np.array(out)

def resid_sentiment_ic(by_date, h):
    """sentiment 对 (fwd残差化于momentum) 的横截面rank相关, 每日平均。"""
    ics = []
    for d, rows in by_date.items():
        sub = [r for r in rows if r.get("sentiment") is not None and r.get("momentum_20d_pct") is not None and r.get(h) is not None]
        if len(sub) < 6: continue
        y = np.array([r[h] for r in sub]); x = np.array([r["momentum_20d_pct"] for r in sub])
        A = np.vstack([x, np.ones_like(x)]).T
        coef, *_ = np.linalg.lstsq(A, y, rcond=None)
        resid = y - (coef[0]*x + coef[1])
        sent = np.array([r["sentiment"] for r in sub])
        ic = spearman(sent, resid)
        if not np.isnan(ic): ics.append(ic)
    return np.array(ics)

def main():
    if not os.path.exists(FWD):
        print("forward面板还没数据(各radar日需+6天成熟, OOS起点06-16 → 最早06-22出第一行)"); return
    rows = [json.loads(l) for l in open(FWD)]
    by_date = defaultdict(list)
    for r in rows: by_date[r["date"]].append(r)
    nd = len(by_date)
    print("="*58); print("  radar Forward 记分台 (OOS, 起点06-16)"); print("="*58)
    print("已成熟天数: %d | 行数: %d" % (nd, len(rows)))
    eff5 = nd / 5
    print("有效独立观测(f5非重叠≈天数/5): %.1f\n" % eff5)
    print("【三腿正交 tercile-LS 净收益/天%】")
    for score in ("combined_score", "sentiment", "momentum_20d_pct"):
        line = "  %-16s" % score
        for h in ("f1", "f3", "f5"):
            v = ls_net(by_date, score, h)
            line += " %s=%+.3f(n%d)" % (h, v.mean() if len(v) else 0, len(v))
        print(line)
    print("\n【核心: sentiment 在动量残差上的增量 IC(每日均, >0且稳才算基本面有料)】")
    for h in ("f1", "f3", "f5"):
        ic = resid_sentiment_ic(by_date, h)
        print("  %s: 残差IC均 %+.3f (n=%d天)" % (h, ic.mean() if len(ic) else 0, len(ic)))
    print("\n【预注册验收门(全过才证明基本面AI有横截面alpha)】")
    g = [
        ("G1 OOS f5非重叠 n≥20", eff5 >= 20, "%.1f/20" % eff5),
        ("G2 sentiment残差IC>0且各horizon一致", None, "需n够后判"),
        ("G3 板块中性后仍正", None, "需n够后判"),
        ("G4 单名加帽20%后仍正", None, "需n够后判"),
        ("G5 跨≥1非普涨regime", None, "需观察"),
    ]
    for name, ok, det in g:
        mark = "✅" if ok else ("❌" if ok is False else "⏳")
        print("  [%s] %-30s %s" % (mark, name, det))
    print("\n  → 当前: 攒数据中, %s" % ("可初判" if eff5 >= 20 else "样本远不够, 继续记录(~14周)"))

if __name__ == "__main__":
    main()
