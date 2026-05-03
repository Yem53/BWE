# Round 4 Final Report — 整夜 10h Pipeline 结果

> 时间: 2026-04-27 23:00 ~ 2026-04-28 09:30 (~10.5h)
> 5090 GPU + Mac Claude Max 自动化 pipeline
> 状态: **5 epochs + 4 LLM debate cycles 全完成, 0% crash, 但 best_score 没破 R3 baseline 0.211**

---

## 1. 完成度速览

| 项 | 计划 | 实际 |
|---|---|---|
| GPU epochs | 3 | **5** ✓ (134,574 combo evaluations) |
| LLM debate cycles | 3 | **4 完成 + 2 退化** (cycles 5/6 LLM 提 0 archetype) |
| 新增 R4 archetypes | ~75 | **49** (LLM-added E340+) |
| Registry 总规模 | ~660 | **652** ✓ |
| Crash rate | <5% | **0.0%** ✓ |
| 7d hold | 加入 grid | **❌ 没成功** (1m kline rebuild 卡 22000/22724 后 process die) |
| Mac 内存崩 | 0 | **0** ✓ (memory-safe orchestrator) |
| LLM cost | ≥$80 | ~$50-80 (4 valid cycles, max effort, opus-4-7) |
| Best score 提升 | beat 0.211 | **❌ 没破** (R4 max 0.2015 ≈ R6 channel baseline) |

## 2. Best Score 进化轨迹（5 epoch cumulative）

```
Phase             Best score    Note
─────────────────────────────────────────────────────────────────
R3 baseline       +0.21119      E036 pc_first_signal_immediate_long × X001
                                trig=5000 (pricechange/long channel saturation)

R4 epoch 1-5      +0.21119      未刷新 — 没有 R4 archetype 击破 R3 0.211
LLM cycle 1-4 加  +0.21119      LLM 提的 49 个新 archetype 也没击破

Top R4 archetype: +0.2015       E316 r6_extreme_smallcap_long × X300
                                trig=120 (R6 channel baseline saturation)
                                ⚠️ 这个 archetype 实际 silent fall-through(见 §4 P0 bug)
```

## 3. 跨 Epoch 综合 Top 30 keeps（unique by entry_id）

[top entries 集中于 R6 channel saturated baseline @ trig=120, score 0.2015]

| 频道分布 | 数量 | Best score | 说明 |
|---|---|---|---|
| R6 long (single-condition) | 25 | +0.2015 | **全部 trig=120 = R6 channel/side baseline** (filter saturated) |
| pricechange long | 41 | +0.1944 | **trig=5000 = PC long channel baseline** |
| pricechange short | 24 | +0.1323 | trig=5000 = PC short baseline |
| OI long | 41 | -0.1376 | trig=1401 = OI channel baseline (negative score) |
| OI short | 32 | -0.2355 | trig=1401 = OI channel baseline (more negative) |
| LLM-added (E340+) | 49 | +0.1885 | 没显著 differentiation |
| Cross-channel | 17 | +0.0839 | weak |

**关键观察**: 所有"top" archetype 实际是 channel/side baseline saturation, **filter 没真 work**。

## 4. CRITICAL BUGS 暴露（R5 必修 P0）

### P0 #1. marketcap_bucket silent fall-through（**致命 bug**）

```
SUPPORTED_FIELDS.md 写: marketcap_bucket = small / mid / large
实际数据值:               <50m / 50m-200m / 200m-1b / >=1b / unknown
```

后果: R4 archetypes 用 `marketcap_bucket=small` 全部 **silent fall-through** = 等于无 filter = channel/side baseline。

受影响 R4 archetypes (估约 15-20 个): `*_smallcap_*` 系列。

修法 (R5):
- 修 SUPPORTED_FIELDS.md 写实际 bucket 值
- OR 在 entry_filter 加 mapping: `small → <50m`, `mid → 50m-200m`, `large → 200m-1b OR >=1b`
- 推荐后者保留 LLM 用易记的 small/mid/large 语义

### P0 #2. best_tp / best_sl 全部 grid 边界值

```
best_tp 分布: 0.50 (121,756×) / 0.80 (5,906×) / 0.63 (2,604×) / 0.56 (1,475×)
              → 几乎全部最低值 0.50!
best_sl 分布: 10.0 (101,200×) / 3.0 (16,889×) / 7.0 (9,843×) / 5.0 (6,642×)
              → 大量最高值 10!
```

含义: r4_keep_gate metric **倾向 small TP / wide SL** — 跟妖币 wide-TP thesis **直接矛盾**。

修法 (R5):
- TP grid lower bound 至 5%: `np.geomspace(5.0, 500.0, 40)` (去 0.5-3% fee-trap region)
- SL grid 加最低值约束 ≥3%
- OR 修 metric: 加 small-TP penalty

### P0 #3. R6 channel events 太稀疏 → channel saturation 假阳性

```
R6 共 120 events 在 30d 数据 (paper_shadow events parquet)
任何单条件 R6 archetype trig 都收敛到 ~120 = R6 channel/side baseline
故 score = R6 baseline score = +0.2015
```

修法 (R5):
- 加 saturation penalty: trig 落在 channel baseline ±10% 时 score 强制乘 0.5
- 或要求 trig < channel total events × 0.7 才算 valid filter

### P0 #4. 7d hold 没实现

5h hold 在妖币长期拉升周期下截断收益。1m kline rebuild 22724 文件 streaming 5+小时未完。

修法 (R5):
- **用 1h kline 替代** (用户 2026-04-28 上午建议): 6301 个 1h JSON × 168 hours/event = ~1.2M rows total (比 1m 的 73.7M 缩 60×)
- 1h bar broadcast 到 1m grid 让 GPU eval kernel 不动
- Hold grid 扩到 [30m, 1h, 2h, 5h, 12h, 24h, 48h, 72h, 168h]

### P0 #5. best_score.json 跨 epoch 没 reset

orchestrator 每 epoch reset cursor 但保留 best_score.json → 后续 epochs 全部 keep=0 because 必须 beat 之前 epoch 的 best (R3 0.211 starting point)。

修法 (R5):
- 每 epoch start 删除 best_score.json (允许新 archetype 重新 set 起 baseline)
- 或加 `--reset-best-score` flag

## 5. 整夜 LLM Debate 实际产出

| Cycle | Time | New archetypes | Notes |
|---|---|---|---|
| 1 | 01:44 | 15 | mostly OI/PC variants |
| 2 | 03:32 | 19 | cross-channel + R6 variants |
| 3 | 05:21 | 15 | session/funding-aware |
| 4 | 07:08 | **0** | LLM 看到 best_score 没破，gave up proposing |
| 5 | 09:07 | **0** (in flight) | 同 4 |

LLM 提了 49 个 archetype 但 **max score +0.1885 (E342) < R3 baseline 0.211** — LLM-added 也没击破 saturation ceiling。

LLM cycle 4-5 提 0 archetype 是诚实信号: 在 r4_keep_gate metric 当前 saturated 状态下 LLM 看不到该补什么。需要先修 metric/grid 再继续 LLM cycle。

## 6. R5 Plan（接下来要做的事）

### Phase C (现在开始)
1. ✅ **Phase B done** — 5 epoch 综合分析 + critical bug 找出
2. **Build 1h kline event_windows.parquet** (memory-safe 流式, 6301 1h JSON × 168 bars/event ~ 1.2M rows ~100 MB)
3. **修 marketcap_bucket** mapping (small/mid/large → 实际值)
4. **TP grid lower bound 5%**
5. **加 saturation penalty** to r4_keep_gate metric
6. **加 reset-best-score** flag, 启动 R5 epoch with **clean best_score**
7. **R5 LLM cycle 启用** with corrected metric

### R5 期望
- best_tp / best_sl 不再全部 grid 边界 (TP 5-50% sweet spot)
- 真正的 entry-side filter alpha 显现 (无 saturation 绕过)
- 7d hold 让妖币长期拉升 alpha 进入回测
- LLM 重启提 archetype (有清晰信号 = 不再 0 produce)

## 7. 整夜的 Pipeline 工程经验

### Worked ✓
- WMI Win32_Process.Create detached parent → main loop survive ssh disconnect 整夜
- smart_priority cursor cycling → R4 entries × R4 exits 800 combos 优先跑完
- Memory-safe orchestrator → Mac 内存 footprint <500 MB sustained, 0 OOM
- LLM debate 11 角色 max effort 自动跑通 4 cycles
- scp + ssh polling 远程操控 5090 完美 (0 hop dropped)

### 失败 ❌
- 7d hold via 1m kline rebuild — 数据量太大 (22724 JSON × ~10K rows = 200M rows), 5+小时未完成
- 7d injector 90 min timeout 太短 (没料到 1m rebuild 会跑 5 小时)
- best_score 没每 epoch reset

### 改进 (R5 应当采纳)
- 用 1h kline (60× 缩减) — 用户 2026-04-28 决定 ✓
- 7d builder 改成 incremental + 进度 telemetry
- best_score reset per epoch flag

---

**Total 整夜 cost (Max plan cached pricing 估算):**
- LLM debate cycles: 4 × ~$15-25 = $60-100
- 5090 GPU electric: ~$1-2
- Mac CPU: $0

**结论**: 工程层面整夜 pipeline **稳定完美跑通 10h**, 但**研究层面**因为 4 个 P0 bug ( marketcap fall-through + grid edge + saturation + best_score retention) **alpha 信号未浮现**。R5 修这些后预计能击破 +0.211 ceiling。
