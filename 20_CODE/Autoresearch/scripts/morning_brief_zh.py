"""生成早间简报（中文）—— Round 3 pipeline 完成后的最终总结。

Aggregates outputs from:
  - results.tsv (loop 最终状态)
  - H:/BWE/40_EXPERIMENTS/analysis/<最新>/  (analyze_results 输出)
  - H:/BWE/40_EXPERIMENTS/analysis/rescore_<最新>/  (rescore_with_v2 输出)
  - H:/BWE/40_EXPERIMENTS/debates/<最新>/  (Round 3 LLM debate 完整输出)
  - H:/BWE/40_EXPERIMENTS/paper_shadow/  (paper sim 结果)

输出: H:/BWE/40_EXPERIMENTS/morning_brief_<timestamp>.md
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
from bwe_autoresearch.bwe_paths import (  # noqa: E402
    ANALYSIS_DIR, DEBATES_DIR, PAPER_DIR,
    EXPERIMENTS_DIR as OUT_DIR, RESULTS_TSV,
)


def _num(x, default: float = 0.0) -> float:
    """Safely coerce CSV/JSON values (possibly strings) to float for f-string formatting."""
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _latest(dir_path: Path, prefix: str = "") -> Path | None:
    if not dir_path.exists():
        return None
    candidates = [d for d in dir_path.iterdir() if d.is_dir() and d.name.startswith(prefix)]
    if not candidates:
        return None
    return max(candidates, key=lambda d: d.stat().st_mtime)


def _read_results_summary() -> dict:
    if not RESULTS_TSV.exists():
        return {"total": 0}
    lines = RESULTS_TSV.read_text(encoding="utf-8").splitlines()
    if len(lines) < 2:
        return {"total": 0}
    rows = []
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        try:
            rows.append({
                "score": float(parts[1]),
                "triggers": int(parts[2]),
                "status": parts[3],
                "desc": parts[4],
            })
        except ValueError:
            pass
    if not rows:
        return {"total": 0}
    by_status = {}
    for r in rows:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    keeps = [r for r in rows if r["status"] == "keep"]
    return {
        "total": len(rows),
        "by_status": by_status,
        "best_score": max((r["score"] for r in rows if r["status"] in ("keep", "discard")), default=None),
        "n_keeps": len(keeps),
    }


def _read_rescore_top(rescore_dir: Path | None, n: int = 10):
    """从 rescore_v2.csv 读 top N (按 Kelly)."""
    if rescore_dir is None or not rescore_dir.exists():
        return []
    csv = rescore_dir / "rescore_v2.csv"
    if not csv.exists():
        return []
    lines = csv.read_text(encoding="utf-8").splitlines()
    if len(lines) < 2:
        return []
    header = lines[0].split(",")
    rows = []
    for line in lines[1:]:
        parts = line.split(",")
        if len(parts) != len(header):
            continue
        row = dict(zip(header, parts))
        try:
            row["score_kelly_pct"] = float(row.get("score_kelly_pct", 0))
            row["score_mean"] = float(row.get("score_mean", 0))
            row["score_legacy_p25"] = float(row.get("score_legacy_p25", 0))
            row["paper_final_pct"] = float(row.get("paper_final_pct", 0))
            row["paper_max_dd_pct"] = float(row.get("paper_max_dd_pct", 0))
        except ValueError:
            continue
        rows.append(row)
    rows.sort(key=lambda r: r["score_kelly_pct"], reverse=True)
    return rows[:n]


def _read_debate(debate_dir: Path | None) -> dict:
    """读 Round 3 debate 的关键输出."""
    if debate_dir is None or not debate_dir.exists():
        return {}
    out = {"run_dir": str(debate_dir)}
    for fname in ["0_pattern_miner.json", "1_generator.json", "synthesizer.json",
                  "3_synthesizer.json", "4_self_reflection.json",
                  "5_cross_pair_recommender.json"]:
        p = debate_dir / fname
        if p.exists():
            try:
                out[fname.replace(".json", "")] = json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                out[fname.replace(".json", "")] = {"_parse_error": True}

    accepted = []
    new_arch = debate_dir / "new_archetypes.jsonl"
    if new_arch.exists():
        for line in new_arch.read_text(encoding="utf-8").splitlines():
            try:
                accepted.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    out["accepted_archetypes"] = accepted
    return out


def _read_paper_recent() -> list[dict]:
    """读最近的 paper_shadow_sim 输出."""
    if not PAPER_DIR.exists():
        return []
    out = []
    md_files = sorted(PAPER_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    for p in md_files[:5]:
        out.append({"name": p.stem, "path": str(p), "content": p.read_text(encoding="utf-8")[:2000]})
    return out


def render(brief_data: dict) -> str:
    L = []
    ts = time.strftime("%Y-%m-%d %H:%M")
    L.append(f"# 🌅 BWE Round 3 早间简报")
    L.append("")
    L.append(f"生成时间：**{ts}**")
    L.append("")
    L.append("---")
    L.append("")

    # 一、Loop 完成情况
    rs = brief_data.get("results_summary", {})
    L.append("## 一、Loop 完成情况")
    L.append("")
    if rs.get("total"):
        L.append(f"- **总实验数**：{rs['total']:,} / 20,000 "
                 f"({rs['total']*100/20000:.1f}%)")
        L.append(f"- **按状态分布**：{rs.get('by_status', {})}")
        L.append(f"- **best score (legacy p25)**：{_num(rs.get('best_score')):.4f}")
        L.append(f"- **总 keeps**：{rs.get('n_keeps', 0)}")
    else:
        L.append("- ⚠️ results.tsv 为空 — loop 可能没产出数据")
    L.append("")

    # 二、Top winners by Kelly metric
    L.append("## 二、Top 10 真正的 Winners（按 Kelly metric 排序）")
    L.append("")
    L.append("> 注：Kelly metric 是新的 v2 指标，能正确识破 asymmetric TP/SL trap。"
             "传统 p25 metric 之前误把 E126 (paper -13.5%) 排第一 —— Kelly 不会犯这个错。")
    L.append("")
    top_kelly = brief_data.get("top_kelly", [])
    if top_kelly:
        L.append("| # | entry_id | archetype | exit family | TP | SL | trig | Kelly% | mean% | paper% |")
        L.append("|---:|---|---|---|---:|---:|---:|---:|---:|---:|")
        for i, r in enumerate(top_kelly, 1):
            L.append(
                f"| {i} | {r.get('entry_id', '?')} | {r.get('entry_archetype', '?')[:30]} | "
                f"{r.get('exit_family', '?')} | {_num(r.get('best_tp')):.2f} | "
                f"{_num(r.get('best_sl')):.2f} | {r.get('triggers', 0)} | "
                f"**{_num(r.get('score_kelly_pct')):+.2f}** | "
                f"{_num(r.get('score_mean')):+.4f} | "
                f"{_num(r.get('paper_final_pct')):+.2f} |"
            )
    else:
        L.append("- ⚠️ rescore 输出未找到")
    L.append("")

    # 三、Round 3 LLM team 输出
    L.append("## 三、Round 3 LLM Team 输出")
    L.append("")
    debate = brief_data.get("debate", {})
    if not debate:
        L.append("- ⚠️ Round 3 debate 输出未找到")
    else:
        # Pattern miner 总结
        pm = debate.get("0_pattern_miner", {})
        if pm and not pm.get("_parse_error"):
            L.append("### 3.1 Pattern Miner 发现")
            L.append("")
            if pm.get("summary"):
                L.append(f"> {pm['summary']}")
                L.append("")
            for theme in pm.get("dominant_themes", [])[:3]:
                L.append(f"- **主导**：{theme.get('theme', '?')} — {theme.get('evidence', '?')}")
            L.append("")
            for theme in pm.get("underexplored_themes", [])[:3]:
                L.append(f"- **未充分探索**：{theme.get('theme', '?')} — {theme.get('why_underexplored', '?')}")
            L.append("")

        # Synthesizer + self-reflection summary
        syn = debate.get("3_synthesizer", {})
        refl = debate.get("4_self_reflection", {})
        accepted = debate.get("accepted_archetypes", [])
        L.append("### 3.2 Synthesizer + Self-Reflection 决策")
        L.append("")
        L.append(f"- **接受的新 archetype 数**：{len(accepted)}")
        if syn.get("summary"):
            L.append(f"- **Synthesizer 总结**：{syn['summary'][:300]}")
        if refl.get("summary"):
            L.append(f"- **Self-Reflection 总结**：{refl['summary'][:300]}")
            n_promo = len(refl.get("promotions", []))
            if n_promo:
                L.append(f"  - 自我反思又**回头加票**了 {n_promo} 个 archetype")
        L.append("")

        # Show accepted archetypes
        if accepted:
            L.append("### 3.3 新接受的 Archetypes")
            L.append("")
            for a in accepted[:15]:
                L.append(f"- **{a.get('id', '?')}** `{a.get('archetype', '?')}` "
                         f"({a.get('channel', '?')}/{a.get('side', '?')})")
                if a.get("notes"):
                    L.append(f"  > {a['notes'][:200]}")
                if a.get("synthesizer_note"):
                    L.append(f"  > _Synthesizer note_: {a['synthesizer_note'][:200]}")
            L.append("")

        # Cross-pair recommender top 10
        cpr = debate.get("5_cross_pair_recommender", {})
        if cpr and not cpr.get("_parse_error"):
            L.append("### 3.4 推荐 Top 10 (Entry × Exit) 测试对")
            L.append("")
            if cpr.get("summary"):
                L.append(f"> {cpr['summary']}")
                L.append("")
            top_pairs = cpr.get("top_pairs", [])
            if top_pairs:
                L.append("| 排名 | Entry | Exit | Family | 优先级 | 思路 |")
                L.append("|---:|---|---|---|---|---|")
                for p in top_pairs[:10]:
                    L.append(
                        f"| {p.get('rank', '?')} | **{p.get('entry_id', '?')}** {p.get('entry_archetype', '?')[:25]} | "
                        f"{p.get('exit_id', '?')} {p.get('exit_archetype', '?')[:20]} | "
                        f"{p.get('exit_family', '?')} | {p.get('test_priority', '?')} | "
                        f"{p.get('thesis', '?')[:120]} |"
                    )
            div = cpr.get("diversity_audit", {})
            if div:
                L.append("")
                L.append(f"**多样性审计**：")
                L.append(f"- 频道分布：{div.get('by_channel', {})}")
                L.append(f"- 方向分布：{div.get('by_side', {})}")
                L.append(f"- Exit family 分布：{div.get('by_exit_family', {})}")
                L.append(f"- 评估：{div.get('diversity_assessment', '?')}")
            L.append("")

    # 四、Paper Shadow 结果
    L.append("## 四、Paper Shadow（$1000 复利模拟）Top 5 结果")
    L.append("")
    papers = brief_data.get("papers", [])
    if papers:
        for p in papers[:5]:
            L.append(f"### {p['name']}")
            L.append("")
            # 提取关键数字
            content = p["content"]
            # 查找 Scenario 表格部分
            m = re.search(r"\| Scenario \|.*?\n((?:\|.*\n)+)", content, re.DOTALL)
            if m:
                L.append("```")
                L.append(m.group(0).strip())
                L.append("```")
            L.append("")
    else:
        L.append("- ⚠️ Paper shadow 输出未找到")
    L.append("")

    # 五、关键发现 / 警示
    L.append("## 五、关键发现 / 警示")
    L.append("")
    findings = []
    # Pattern miner traps
    if debate:
        pm = debate.get("0_pattern_miner", {})
        for trap in pm.get("trap_warnings", [])[:3]:
            findings.append(f"⚠️ **{trap.get('pattern', '?')}** — {trap.get('avoid_or_mitigate', '?')}")
    # Top Kelly is positive vs negative
    if top_kelly and _num(top_kelly[0].get("score_kelly_pct")) > 0:
        best = top_kelly[0]
        findings.append(
            f"✅ Top winner **{best.get('entry_id')}** 在 Kelly metric 下 "
            f"{_num(best.get('score_kelly_pct')):+.2f}% — 真有 alpha（不是 p25 trap）"
        )
    elif top_kelly and _num(top_kelly[0].get("score_kelly_pct")) <= 0:
        findings.append(
            f"⚠️ 即使 top entry **{top_kelly[0].get('entry_id') if top_kelly else '?'}** 的 Kelly 也 ≤0 — "
            f"当前发现都没有真 alpha，需要 Round 4 探索新方向"
        )
    if not findings:
        findings.append("（无特殊发现）")
    for f in findings:
        L.append(f"- {f}")
    L.append("")

    # 六、推荐下一步
    L.append("## 六、推荐下一步")
    L.append("")
    L.append("### 立即可做")
    L.append("")
    if top_kelly:
        positive_kelly = [r for r in top_kelly if r.get("score_kelly_pct", 0) > 0]
        if len(positive_kelly) >= 3:
            L.append(f"1. **Paper shadow** 这 {len(positive_kelly)} 个真 alpha 候选（Kelly>0）"
                     f"——拿真实 1 周 PnL 数据")
        else:
            L.append("1. ⚠️ Kelly>0 候选太少 → **Round 4 重点探索新方向**而不是 paper")
    L.append("2. Review 上面 Round 3 接受的 archetypes，去除任何明显错位")
    L.append("3. 检查 Cross-Pair Recommender 推荐对，挑 3 个 `fast` 优先级先 GPU 验证")
    L.append("")
    L.append("### 中期（Round 4）")
    L.append("")
    L.append("- 基于今晚结果让 LLM team 加深 winner 邻域")
    L.append("- 探索 Round 3 标记的 underexplored 主题")
    L.append("- 如有需要，调整 score metric / variant grid 范围")
    L.append("")
    L.append("---")
    L.append("")
    L.append(f"完整产物路径：")
    if brief_data.get("debate", {}).get("run_dir"):
        L.append(f"- Round 3 debate: `{brief_data['debate']['run_dir']}`")
    if brief_data.get("rescore_dir"):
        L.append(f"- Rescore (4 metrics): `{brief_data['rescore_dir']}`")
    if brief_data.get("analysis_dir"):
        L.append(f"- Analysis: `{brief_data['analysis_dir']}`")
    L.append("")

    return "\n".join(L)


def main():
    print("[brief] gathering inputs...")

    # 1. Loop summary from results.tsv
    rs = _read_results_summary()

    # 2. Latest analysis dir (non-rescore)
    analysis = None
    for d in sorted(ANALYSIS_DIR.iterdir() if ANALYSIS_DIR.exists() else [],
                    key=lambda p: p.stat().st_mtime, reverse=True):
        if d.is_dir() and not d.name.startswith("rescore_"):
            analysis = d
            break

    # 3. Latest rescore dir
    rescore = _latest(ANALYSIS_DIR, prefix="rescore_")

    # 4. Latest debate dir (most recent)
    debate_dir = _latest(DEBATES_DIR)
    debate = _read_debate(debate_dir)

    # 5. Recent paper shadow outputs
    papers = _read_paper_recent()

    # 6. Top kelly from rescore
    top_kelly = _read_rescore_top(rescore, n=10)

    brief_data = {
        "results_summary": rs,
        "analysis_dir": str(analysis) if analysis else None,
        "rescore_dir": str(rescore) if rescore else None,
        "debate": debate,
        "papers": papers,
        "top_kelly": top_kelly,
    }

    md = render(brief_data)
    out_path = OUT_DIR / f"morning_brief_{time.strftime('%Y%m%d_%H%M%S')}.md"
    out_path.write_text(md, encoding="utf-8")
    print(f"[brief] saved: {out_path}")

    # Also write a stable "latest" pointer
    latest = OUT_DIR / "morning_brief_latest.md"
    latest.write_text(md, encoding="utf-8")
    print(f"[brief] latest pointer: {latest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
