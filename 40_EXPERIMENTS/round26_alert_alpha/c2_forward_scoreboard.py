#!/usr/bin/env python3
"""C2 forward paper 记分板(Mac侧, 读rsync回来的summary.jsonl, 对照预注册验收门)"""
import json, os

SUMMARY = "/Volumes/T9/BWE/30_DATA/bwe_scanner_alerts/c2_forward/summary.jsonl"

def main():
    if not os.path.exists(SUMMARY):
        print("还没有forward数据(等scanner-rsync同步, 或EC2评估器还没跑出第一天)"); return
    rows = [json.loads(l) for l in open(SUMMARY) if l.strip()]
    rows = [r for r in rows if r.get("excess_day") is not None]
    if not rows:
        print("summary存在但无有效excess行"); return
    ex = [r["excess_day"] for r in rows]
    pos = sum(1 for x in ex if x > 0)
    pf = [r["c2_mean_postfund"] for r in rows if r.get("c2_mean_postfund") is not None]
    mean = lambda v: sum(v) / len(v)
    print("=" * 56)
    print("  C2 Forward Paper 记分板 (起点2026-06-09)")
    print("=" * 56)
    for r in rows[-10:]:
        print("  %s  excess %+6.2f%%  (C2 %+.2f vs 其它 %+.2f, n=%d/%d)" % (
            r["date"], r["excess_day"], r["c2_mean"], r["other_mean"], r["n_c2"], r["n_other"]))
    print("-" * 56)
    g = [
        ("G1 样本≥30天",   len(ex) >= 30,            "%d/30" % len(ex)),
        ("G2 超额>+0.30%/天", mean(ex) > 0.30,        "%+.3f%%/天" % mean(ex)),
        ("G3 正天≥55%",    pos / len(ex) >= 0.55,     "%d/%d (%.0f%%)" % (pos, len(ex), 100*pos/len(ex))),
        ("G4 扣资金费仍负(维持filter定位)", (mean(pf) < 0) if pf else None,
         "%+.3f%%" % mean(pf) if pf else "无数据"),
    ]
    for name, ok, detail in g:
        mark = "✅" if ok else ("❌" if ok is False else "⏳")
        print("  [%s] %-28s %s" % (mark, name, detail))
    npass = sum(1 for _, ok, _ in g[:3] if ok)
    print("-" * 56)
    print("  G1-G3: %d/3 通过。%s" % (npass,
          "→ 可提案接入live short体系当filter(需用户批准)" if npass == 3 else "继续攒forward天数"))

if __name__ == "__main__":
    main()
