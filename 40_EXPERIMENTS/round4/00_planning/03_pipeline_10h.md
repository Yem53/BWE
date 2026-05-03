# Round 4 — 10 小时端到端 Pipeline (5090 GPU + Mac Claude Max)

> **预算**: 10 小时
> **目标**: 充分利用 5090 + Max 订阅旗舰模型 (`claude-opus-4-7 --effort max --exclude-dynamic-system-prompt-sections`) 的深度辩论
> **设计**: 3 GPU epochs + 3 LLM debate cycles (11 角色 max effort 全跑) + paper_shadow + final brief

## 总览（time budget = ~9.6h, 24 min buffer）

| Phase | T+ start | Dur | 内容 | 跑在哪 | 关键产物 |
|---|---|---:|---|---|---|
| **P1** | 0:00 (NOW) | 110 min | Epoch 1: 31,878 combos × 1,440 variants（registry 603）| 5090 | results.tsv, best_score.json |
| **P2** | 1:50 | 60 min | LLM debate cycle 1（11 角色 max effort）| Mac | new_archetypes_round4_1.jsonl (~25 条) |
| **P3** | 2:50 | 130 min | Epoch 2（registry ~628）| 5090 | results.tsv 追加 |
| **P4** | 5:00 | 60 min | LLM debate cycle 2（cross-pair recommend + 新 archetypes）| Mac | new_archetypes_round4_2.jsonl (~30 条) |
| **P5** | 6:00 | 150 min | Epoch 3（registry ~658）| 5090 | results.tsv 追加 |
| **P6** | 8:30 | 60 min | LLM debate cycle 3（**final synthesis only, no new archetype**）| Mac | round4_final_synthesis.md |
| **P7** | 9:30 | 25 min | paper_shadow top-30 keeps + morning_brief 生成 | 5090 + Mac | round4_morning_brief.md |
| **P8** | 9:55 | 5 min | 总结 + Mac 落地最终 R4 report | Mac | round4_final_report.md |

## 每 Phase 详细

### P1 — Epoch 1（已在跑, NOW = 23:49:47, ETA 01:40）

5090 main loop（PID 173944）跑全 31,878 combos × 1,440 variants。当前 cursor=1238 (3.9%) → 大约 106 min 后自然完成。

监控信号：
- `(Get-Content results.tsv).Count` 应单调递增到 31,879
- `Get-Process python` 应持续在跑
- GPU 利用率 25-60%（小 batch overhead 限制）

### P2 — LLM debate cycle 1（Mac, max effort）

5090 epoch 1 自然 stop 后:

```bash
# 1. Pull all R4 epoch 1 artifacts to Mac
scp Admin@192.168.1.155:'C:/bwe_compute/20_CODE/Autoresearch/results.tsv' \
    /Volumes/T9/BWE/20_CODE/Autoresearch/results.tsv
scp Admin@192.168.1.155:'C:/bwe_compute/20_CODE/Autoresearch/best_score.json' \
    /Volumes/T9/BWE/20_CODE/Autoresearch/best_score.json

# 2. Run rescore + analysis（5 min）
python scripts/analyze_results.py
python scripts/rescore_with_v2.py

# 3. Trigger LLM debate（11 roles, max effort）
BWE_LLM_EFFORT=max python -m bwe_autoresearch.bwe_loop_llm_team
# Each role: claude -p --model claude-opus-4-7 --effort max --exclude-dynamic-system-prompt-sections
```

11 角色顺序（参 `prompts/role_*.md`）:
1. **Pattern Miner** (~5 min) — 找 dominant themes / underexplored
2. **Generator** (~10 min) — 提 18-25 新 archetypes（input: pattern miner output）
3. **Devil** + **Steelman** + **Quant** + **Risk** + **Metric Critic** (per-proposal critiques, parallel ≈ 15 min)
4. **Synthesizer** (~10 min) — accept/reject decision per proposal
5. **Self-Reflection** (~5 min) — 是否漏掉了应该 promote 的
6. **Cross-Pair Recommender** (~10 min) — 提 top entry × exit pairs to fast-test
7. **Behavior Annotator** (~5 min) — annotate accepted archetypes for next-round Pattern Miner

总共 ~60 min, 输出:
- `40_EXPERIMENTS/debates/debate_<ts>/new_archetypes.jsonl`（25 条左右）
- `cross_pair_recommendations.json`
- `synthesizer_decisions.json`

### P3 — Epoch 2（5090, with new archetypes）

```bash
# 1. Append new archetypes to registry
cat new_archetypes_round4_1.jsonl >> hypothesis_registry.jsonl

# 2. Push updated registry to 5090
scp hypothesis_registry.jsonl Admin@192.168.1.155:'C:/bwe_compute/40_EXPERIMENTS/'

# 3. Reset cursor 0 but keep best_score（让 epoch 2 找超过 epoch 1 best 的 winner）
ssh Admin@192.168.1.155 'cd /D C:\bwe_compute\20_CODE\Autoresearch && powershell -c "Set-Content combo_cursor.json (\"{\"\"cursor\"\": 0}\")"'

# 4. Re-launch main loop
ssh Admin@192.168.1.155 'powershell -ExecutionPolicy Bypass -File C:\bwe_compute\launch_main_loop_v2.ps1'
```

期望：~628 archetypes × ~120 exits = ~75K combos × 1440 variants（更多 archetypes 但 entry × exit 不全 cartesian, 顺序 entry_first cycle 完一遍 entries 才 exit++）。实际需要重算 N = n_entries × n_exits 后估算时间。

### P4 — LLM debate cycle 2（Mac, max effort）

类似 P2，但 input 含 epoch 2 results。LLM 应当：
- 看 epoch 1 → 2 哪些 archetype 起色 / 哪些仍死
- 提 cross_pair refined：entry × exit 配对优化
- Pattern miner 找新 themes (e.g. R6 在 wide-TP exit 下表现, OI long 模式)

输出: ~30 new archetypes (E450+, X400+, etc.)

### P5 — Epoch 3（5090）

最大 archetype 集 ~658。estimate 150 min。

### P6 — LLM debate cycle 3（**final synthesis only**）

**不再加 archetype**。让 LLM team 输出：
- Final winners by category (channel × side × exit family)
- 哪些 R4 archetype confirmed worth paper-shadow
- 哪些 R3 archetype 在 R4 metric 下仍有效
- 总结 R4 学到了什么 vs R3
- 推荐 R5 主题 + 改 metric 建议

输出: `round4_final_synthesis.md`

### P7 — paper_shadow top-30 + morning_brief

```bash
# Top 30 archetypes by r4_keep_gate score (跨 family, 真正 best_exit)
python scripts/paper_shadow_sim.py <each top-30 entry_id>
# Now uses cross-family lookup + best_exit (R4 fix)

# Morning brief
python scripts/generate_morning_brief.py
```

### P8 — Final report

合并 P6 synthesis + P7 paper_shadow → `round4_final_report.md`. 用户回来直接看。

## 风险 + Failure Handling

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| 5090 epoch 1 中途死掉（GPU OOM, Windows update reboot） | 低 | 阶段失败 | results.tsv 已 partial 写入，cursor 保留，重启 loop 续跑（cursor 不丢） |
| LLM debate 单个 role timeout（max effort 一些 role 5+ min）| 中 | 流程卡住 | bwe_loop_llm_team.py 有 5min/role timeout, fallback to "skip role with empty"; debate 仍可继续 |
| max effort 跑出来 cost burst（Max 订阅 cap）| 低 | LLM 限速 | Max 订阅没硬 cap, 会自动限速（rate limit 不是 hard fail） |
| Epoch 2/3 时间超预算 | 中 | P7/P8 缩短 | 砍 epoch 3, 直接 P6 final synthesis at T+5h |
| LLM 提的新 archetype 含 SUPPORTED_FIELDS 之外的 field（fall-through）| 中 | 部分 archetype 无效 | bwe_loop 加载时 silent skip; 不阻塞 |

## Success Criteria

10h 后:
1. ≥ 2 epochs 跑完，3 epochs 是 stretch goal
2. ≥ 2 LLM debate cycles 跑完，3 cycles 是 stretch goal
3. **Best score 比 R3 (+0.21) 高** — 这是核心成功标准
4. Top-30 paper_shadow 已跑，至少 5 个 archetype 在 16bps realistic cost 下正收益
5. round4_final_report.md 写完
