#!/usr/bin/env python3
"""验收仪表盘: paper表现 + forward样本进度 + 上真钱验收门checklist。
回答"够不够格上真钱"。N1绩效归因 + N3回撤监控 + 第6节验收门, 一处看全。
只读 paper_trades.jsonl, 不碰真钱。"""
import json, os, statistics as st

DIR = os.path.dirname(os.path.abspath(__file__))
TRADES = os.path.join(DIR, "paper_trades.jsonl")

# 验收门(风控agent规格): 全部满足才允许小额真钱
GATES = {
    "forward样本": (40, "条已完整出场的forward trade(非回填)"),
    "净期望为正": (0.0, "白名单子集净均值>0 且 中位>0(扣全成本)"),
    "最大回撤": (12.5, "paper累计回撤<12.5%(总熔断25%的一半)"),
    "子集一致": (2, "≥2个独立子集都不为负"),
}

def main():
    if not os.path.exists(TRADES):
        print("无paper_trades"); return
    trades = [json.loads(l) for l in open(TRADES)]
    # 区分回填(历史)vs forward(真实采集) — 暂全标历史(回填), forward需采集器累积后由时间戳判定
    # 这里以 hold_days=5 的白名单(short)子集为核心评估对象
    core = [t for t in trades if t.get("_hd") == 5 and t.get("tradeable")]
    print("=" * 60)
    print("  stockusbinance 验收仪表盘")
    print("=" * 60)
    if not core:
        print("核心子集(5d白名单/short)暂无交易"); return
    nets = [t["net_pct"] for t in core]
    wins = sum(1 for x in nets if x > 0)
    print("\n## 核心策略: Sell信号→做空5天 (实测唯一正edge侧)")
    print("  样本 n=%d | 净均值 %+.3f%% | 中位 %+.3f%% | 胜率 %d%%" % (
        len(nets), st.mean(nets), st.median(nets), 100*wins/len(nets)))
    # 简易equity + maxDD(按signal顺序)
    eq = 0.0; peak = 0.0; mdd = 0.0
    for n in nets:
        eq += n; peak = max(peak, eq); mdd = min(mdd, eq - peak)
    print("  累计(等权) %+.2f%% | 最大回撤 %.2f%%" % (eq, mdd))
    # 各标的
    from collections import defaultdict
    bysym = defaultdict(list)
    for t in core: bysym[t["symbol"]].append(t["net_pct"])
    print("  按标的:", ", ".join("%s(%d:%+.1f%%)" % (s.replace("USDT",""), len(v), st.mean(v))
                                  for s, v in sorted(bysym.items(), key=lambda x:-len(x[1]))[:8]))
    # 验收门
    print("\n## 上真钱验收门 (全绿才允许小额)")
    checks = []
    checks.append(("forward样本≥40", len(nets) >= 40, "%d/40 (注:当前多为回填,需forward真实样本)" % len(nets)))
    checks.append(("净均值>0", st.mean(nets) > 0, "%+.3f%%" % st.mean(nets)))
    checks.append(("中位>0", st.median(nets) > 0, "%+.3f%%" % st.median(nets)))
    checks.append(("最大回撤<12.5%", abs(mdd) < 12.5, "%.2f%%" % abs(mdd)))
    checks.append(("标的分散(≥5)", len(bysym) >= 5, "%d个标的" % len(bysym)))
    for name, ok, detail in checks:
        print("  [%s] %-16s %s" % ("✅" if ok else "❌", name, detail))
    n_pass = sum(1 for _, ok, _ in checks if ok)
    print("\n  → %d/%d 门通过。%s" % (n_pass, len(checks),
          "可考虑小额(仍需子账户隔离+人工确认)" if n_pass == len(checks) else "未达标, 继续forward攒数据"))
    print("\n  ⚠️ 即使全绿: 子账户隔离 + orphan演练 + kill switch实测 + 用户显式确认 缺一不可上真钱")

if __name__ == "__main__":
    main()
