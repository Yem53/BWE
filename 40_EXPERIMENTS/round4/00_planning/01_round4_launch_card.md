# Round 4 启动卡 — 5090 Windows

> 状态：Mac 端 hygiene 完成 (2026-04-27)，等下次 H: 插上 5090 即可启动。
> 准备时间：10-15 分钟（含 reset + smoke + monitor 起停）
> Loop 估算：~30K experiments，1-3 天 on 5090 GPU

---

## 0. 切换到 5090 之前的最后一步（在 Mac 这边）

如果你看这份文档时还在 Mac 上，确认以下都 done：

```bash
# 在 Mac 上 (T9 还插 Mac)
cd /Volumes/T9/BWE
git status                                    # 看一下有没有未 commit 的改动
git add 20_CODE/Autoresearch 40_EXPERIMENTS/round4 40_EXPERIMENTS/hypothesis_registry.jsonl
git commit -m "[BWE-Round4] Mac hygiene: registry +60 (E300-E339 + X300-X319), variant grid wide-TP, paper_shadow cross-family fix, results path bug fix, R4 metric proposal"
# 提示: score metric 改动等 user confirm 后再 commit
```

然后拔 H: 插 5090 windows。

---

## 1. 5090 上 pre-flight 检查（5 分钟）

```powershell
cd H:\BWE\20_CODE\Autoresearch
git pull   # 拉到 Mac 的改动 (如果用 git remote)，OR 直接因为 H: 是 portable 自带

# 1.1 验证 R4 archetypes 已合并到 registry
python -c "
import json
n = sum(1 for _ in open(r'H:\BWE\40_EXPERIMENTS\hypothesis_registry.jsonl', encoding='utf-8'))
print(f'registry rows: {n} (expect 603)')
ids = [json.loads(l)['id'] for l in open(r'H:\BWE\40_EXPERIMENTS\hypothesis_registry.jsonl', encoding='utf-8')]
print(f'R4 entries E300-E339: {sum(1 for i in ids if i.startswith(\"E3\"))}')
print(f'R4 exits X300-X319: {sum(1 for i in ids if i.startswith(\"X3\"))}')
"

# 1.2 验证 variant grid 是 R4 spec
python -c "
from bwe_autoresearch.bwe_loop import DEFAULT_TP_GRID, DEFAULT_SL_GRID, DEFAULT_HOLD_MINUTES
print(f'TP grid: {len(DEFAULT_TP_GRID)} values, range [{DEFAULT_TP_GRID.min():.2f}, {DEFAULT_TP_GRID.max():.2f}]')
print(f'SL grid: {DEFAULT_SL_GRID.tolist()}')
print(f'Hold: {DEFAULT_HOLD_MINUTES}')
print(f'Total variants/exp: {len(DEFAULT_TP_GRID) * len(DEFAULT_SL_GRID) * len(DEFAULT_HOLD_MINUTES)}')
"
# Expected: TP 60 values [0.50, 500.00], SL [3, 5, 7, 10], Hold [30, 60, 120, 180, 240, 300], 1440 variants/exp

# 1.3 GPU 可用性
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}, device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}')"
# Expected: CUDA: True, device: NVIDIA GeForce RTX 5090

# 1.4 GPU eval kernel self-test
python -m bwe_autoresearch.bwe_loop_gpu_eval
# Expected: ALL TESTS PASSED + ~100M+ evals/sec on 5090
```

如果任何一步失败 → 暂停 → 排查后再起 loop。

---

## 2. R4 reset（一次性，destructive）

R4 必须重置 cursor + best_score（R3 残留: cursor=20000, best_score=0.39 不能跨 R3/R4 比较）。

```powershell
# 先 dry-run 看会改什么
python scripts/round4_reset.py
# 确认输出后:
python scripts/round4_reset.py --execute
```

dry-run 会显示：
- backup results.tsv (R3 20001 rows) → registry_backups/results_round3_<ts>.tsv
- reset results.tsv to header only
- reset cursor 20000 → 0
- backup best_score.json → registry_backups/best_score_round3_<ts>.json
- delete best_score.json (loop 会从 -inf 重新 build best)

---

## 3. R4 smoke test（30 秒）

```powershell
# 跑 1 个 combo 验证端到端不 crash
python -m bwe_autoresearch.bwe_loop --max-experiments 1
# Expected: 1 experiment runs, decision = keep (因为 best is now -inf)
```

如果输出 `score=0.XX best_tp=YY best_sl=ZZ`, GPU eval 成功，进入下一步。

---

## 4. 启动 R4 主 loop（挂 1-3 天）

```powershell
# 后台启动，输出重定向
nohup python -m bwe_autoresearch.bwe_loop > round4.log 2>&1 &

# 或者 Windows PowerShell：
Start-Process -NoNewWindow -FilePath python -ArgumentList @("-m","bwe_autoresearch.bwe_loop") -RedirectStandardOutput round4.log -RedirectStandardError round4.err
```

**预计**：
- 总 combos: 253 entries × 126 exits = 31,878
- 但 cursor 顺序是 entry_first，每轮 N_entries 后 exit 切下一个
- 每 combo 1,440 variants × ~3K events = 4.3M evals
- 5090 GPU 100M evals/sec → 每 combo ~0.04s，单 epoch 31,878 combos ~21 minutes
- 以 R3 实际 cursor=20000 用了一晚（~6h）的速度参考，R4 grid 是 1/63 计算量但 archetype 多 1.4x → R4 单 epoch 估约 1-2h
- 最后跑 1-3 天足够多 epoch + LLM debate cycles

---

## 5. 监控（Mac 端，可远程查看）

```powershell
# 5090 上看 results.tsv 增长 + GPU 利用率
nvidia-smi -l 5         # 实时 GPU util / VRAM
Get-Content round4.log -Wait -Tail 20

# 或在 Mac 上从 H: drive 远程读 (如果 H: 共享):
tail -f /Volumes/T9/BWE/20_CODE/Autoresearch/round4.log
wc -l /Volumes/T9/BWE/20_CODE/Autoresearch/results.tsv  # 看进度
```

cron stall-check（已配置，类似 R3 hourly check）会自动报告进度。

---

## 6. 异常停止

```powershell
# 找 python 进程
Get-Process python | Select-Object Id, ProcessName, StartTime

# Stop（Ctrl+C 或）
Stop-Process -Id <PID>

# 重启会从 cursor 继续，不会重跑已完成 combos
python -m bwe_autoresearch.bwe_loop > round4.log 2>&1 &
```

---

## 7. R4 跑完后回 Mac 收尾

跑完 1-3 天后（或者中途主动 stop）：

1. 拔 H: 插 Mac mini
2. Mac 上跑：
   ```bash
   cd /Volumes/T9/BWE/20_CODE/Autoresearch
   /tmp/codex_round4_venv/bin/python scripts/analyze_results.py  # R4 metric 排序
   /tmp/codex_round4_venv/bin/python scripts/rescore_with_v2.py  # 按 R4 metric rescore
   ```
3. 修过的 paper_shadow:
   ```bash
   /tmp/codex_round4_venv/bin/python scripts/paper_shadow_sim.py <top_entry_id>  # cross-family auto-pick best
   ```
4. LLM team R4 debate（用 11 个 prompt 角色）
5. Round 4 morning brief

---

## 8. 已知风险 / Watch list

| 风险 | 监控信号 | 应对 |
|---|---|---|
| GPU OOM (R4 1440 variants × N events × 300 minutes) | nvidia-smi VRAM > 22GB 持续 | 减小 variant_chunk in `bwe_loop_gpu_eval` 默认 8192 → 4096 |
| Crash rate 仍 > 5% | results.tsv 里 status=crash 占比 | 看 archetype 是不是 filter 太严；记到 99_ADMIN/round4_crash_log.md |
| score 全部正/全部负 | morning_brief 看分布 | 调 metric 阈值（R4 metric proposal 4 open questions） |
| 单 archetype variants 都 NaN | results.tsv val_score 列出现 NaN 行 | event count < MIN_TRIGGERS_PER_OOS=5 检查 archetype filter |

---

## 9. 重要 reference

- Registry: `40_EXPERIMENTS/hypothesis_registry.jsonl` (603 rows, R4 archetypes E300-E339 + X300-X319)
- Variant grid: `20_CODE/Autoresearch/bwe_autoresearch/bwe_loop.py:78-89`
- Score metric: `20_CODE/Autoresearch/bwe_autoresearch/bwe_loop_score_v2.py` (still default `kelly_capped`; R4 metric proposal in `40_EXPERIMENTS/round4/03_metrics/r4_score_metric_proposal.md`)
- TEAM_PHILOSOPHY: `20_CODE/Autoresearch/prompts/TEAM_PHILOSOPHY.md` (R4 妖币 regime updated)
- D1 实证: `40_EXPERIMENTS/round4/00_planning/02_max_forward_return.md`
- Master overview: `40_EXPERIMENTS/round4/00_planning/00_overview.md`
- X100 audit: `40_EXPERIMENTS/round4/05_audits/x100_audit_report.md` (Verdict GREEN)

**最后更新**: 2026-04-27 by Mac 端 R4 hygiene phase
