#!/usr/bin/env python3
"""资金费倾斜规则增量实测: 同 29 信号, 持 5 天, 严格因果, 三口径对比。
口径: (a)不含资金费 (b)含资金费 (c)含资金费+倾斜过滤。
做空看均值 (中位正/均值负 = 左尾陷阱)。n<20 探索性。
输出: 控制台中文对比表 + funding_tilt_results.json。
"""
import json, os, sys, statistics as st

DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(DIR)
sys.path.insert(0, ROOT)
import paper_engine_v3 as eng  # noqa: E402

HOLD = 5
OUT_JSON = os.path.join(DIR, "funding_tilt_results.json")


def desc(nets):
    if not nets:
        return {"n": 0, "mean": None, "median": None, "winrate": None}
    w = sum(1 for x in nets if x > 0)
    return {"n": len(nets), "mean": round(st.mean(nets), 4),
            "median": round(st.median(nets), 4), "winrate": round(100 * w / len(nets), 1)}


def slice_stats(trades):
    return {
        "all": desc([t["net_pct"] for t in trades]),
        "short": desc([t["net_pct"] for t in trades if t["side"] == "short"]),
        "long": desc([t["net_pct"] for t in trades if t["side"] == "long"]),
    }


def main():
    res = eng.run_three_regimes(hold_days=HOLD)
    if res is None:
        print("DB 未就绪 — 先 rsync tradfi_capture_ec2.sqlite3")
        return

    a = res["a_no_funding"]; b = res["b_with_funding"]; cc = res["c_funding_tilt"]
    sa, sb, sc = slice_stats(a["trades"]), slice_stats(b["trades"]), slice_stats(cc["trades"])

    # 倾斜筛掉的具体信号 (在 b 里但不在 c 里)
    c_ids = {t["signal_id"] for t in cc["trades"]}
    dropped = [t for t in b["trades"] if t["signal_id"] not in c_ids]
    dropped_info = [{"signal_id": t["signal_id"], "side": t["side"], "symbol": t["symbol"],
                     "rate_at_entry": t["rate_at_entry"], "net_pct": t["net_pct"]} for t in dropped]

    # ---- 控制台报告 ----
    P = print
    P("=" * 78)
    P("资金费倾斜规则增量实测 — 持有 %d 天, 同 29 桥接信号, 严格因果" % HOLD)
    P("=" * 78)
    P("")
    P("【三口径对比】(net_pct = raw - 2×taker费 - 资金费; 做空看均值)")
    P("-" * 78)
    hdr = "%-22s %-22s %-22s %-22s"
    P(hdr % ("分组", "(a) 无资金费", "(b) 含资金费", "(c) 含资金费+倾斜"))
    P("-" * 78)

    def cell(d):
        if d["n"] == 0:
            return "n=0"
        return "n=%d 均%+.2f%% 胜%.0f%%" % (d["n"], d["mean"], d["winrate"])

    def cell_med(d):
        if d["n"] == 0:
            return ""
        return "       中%+.2f%%" % d["median"]

    for grp, key in [("全体", "all"), ("做空(均值口径)", "short"), ("做多", "long")]:
        da, db_, dc = sa[key], sb[key], sc[key]
        P(hdr % (grp, cell(da), cell(db_), cell(dc)))
        P(hdr % ("", cell_med(da), cell_med(db_), cell_med(dc)))
    P("-" * 78)
    P("")
    P("【诊断 (各口径可评估笔数)】")
    P("  (a) %s" % a["diag"])
    P("  (b) %s" % b["diag"])
    P("  (c) %s" % cc["diag"])
    P("")
    P("【倾斜规则筛掉的信号】(b→c 被过滤; 共 %d 个)" % len(dropped))
    if dropped_info:
        for d in sorted(dropped_info, key=lambda x: x["net_pct"]):
            P("  %-26s %-5s %-9s rate@entry=%+.6f  该笔net=%+.2f%%" % (
                d["signal_id"], d["side"], d["symbol"], d["rate_at_entry"], d["net_pct"]))
        dn = [d["net_pct"] for d in dropped_info]
        P("  → 被筛信号 net 均值=%+.3f%% (这些是被剔除的样本)" % st.mean(dn))
    else:
        P("  (无)")
    P("")

    # ---- 增量判定 ----
    P("【倾斜规则是否改善?】")
    P("-" * 78)
    for grp, key, focus in [("全体均值", "all", "mean"), ("做空均值", "short", "mean"), ("做多均值", "long", "mean")]:
        vb = sb[key][focus]; vc = sc[key][focus]
        if vb is None or vc is None:
            continue
        delta = vc - vb
        verdict = "↑ 改善" if delta > 0.001 else ("↓ 变差" if delta < -0.001 else "≈ 无变化")
        P("  %-10s: b=%+.3f%% → c=%+.3f%%  Δ=%+.3f%%  %s" % (grp, vb, vc, delta, verdict))
    P("-" * 78)

    # 资金费本身的增量 (a→b)
    P("")
    P("【资金费本身的拖累 (a→b, 不涉及过滤)】")
    for grp, key in [("全体", "all"), ("做空", "short"), ("做多", "long")]:
        va = sa[key]["mean"]; vb = sb[key]["mean"]
        if va is None or vb is None:
            continue
        P("  %-6s: 无费 %+.3f%% → 含费 %+.3f%%  资金费净影响 %+.3f%%" % (grp, va, vb, vb - va))

    # ---- JSON 落盘 ----
    payload = {
        "hold_days": HOLD,
        "n_signals_total": 29,
        "regimes": {
            "a_no_funding": {"diag": a["diag"], "stats": sa},
            "b_with_funding": {"diag": b["diag"], "stats": sb},
            "c_funding_tilt": {"diag": cc["diag"], "stats": sc},
        },
        "tilt_dropped_signals": dropped_info,
        "tilt_dropped_count": len(dropped),
        "deltas_b_to_c": {
            k: (round(sc[k]["mean"] - sb[k]["mean"], 4) if sb[k]["mean"] is not None and sc[k]["mean"] is not None else None)
            for k in ("all", "short", "long")
        },
        "all_trades_with_funding": b["trades"],
    }
    with open(OUT_JSON, "w") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    P("")
    P("→ %s" % OUT_JSON)


if __name__ == "__main__":
    main()
