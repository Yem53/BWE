# Phase 3 — L1-L4 Layer Validation (2026-04-29 morning)

> 把 L1-L4 同时跑在 (a) Hermes 82 LIVE+210 PAPER 和 (b) Broader market 1425 events 上,看不同信号源下哪个 layer 最强

## Layer 定义 (固化)

| Layer | 含义 | 关键设计 |
|---|---|---|
| **L1 原始** | bot 现行 logic | runner_floor_exit + buggy hourly check |
| **L2 exit_v2 only** | 加 exit_v2 module | dynamic trail + ATR + G2 + volume confirm |
| **L3 + rule SKIP** | L2 + rule engine 过滤入场 | uniform 5% pos, strict E (3-6 SKIP) |
| **L3.5 relaxed E + var pos** | 放宽 E + 5/8% sizing | only duration==4 SKIP, F=SKIP |
| **L3.5b strict E + var pos** | 维持 E + 5/8% sizing | 隔离仓位 sizing 效果 |
| **L4 directional + per-thesis** | rule 决定方向 + per-thesis exit | (Hermes context) dir-check + wider trail for follow |

**Caveat (诚实披露)**:
- "Hermes L4" 含 dir-check (BWE 方向 vs rule 方向不一致 → SKIP) + per-thesis exit
- "Broader L4" 含 rule 决定方向 + var pos + exit_v2 baseline (无 per-thesis)
- 两者不可直接比较

## Hermes 测试 (BWE-pre-filtered)

### LIVE 82 trades:
| Layer | trades | total_raw | total_cap | win % | mean_cap |
|---|---|---|---|---|---|
| L1 原始 | 82 | -72.1% | -3.61% | 35.4% | -0.044% |
| **L2 exit_v2 only** | 82 | **+149.0%** | **+7.45%** ⭐️ | 67.1% | +0.091% |
| L3 strict E | 64 | +143.9% | +7.19% | 68.8% | **+0.112%** |
| L3.5 relaxed E | 66 | +121.4% | +5.11% | 66.7% | +0.077% |
| L3.5b strict E + var pos | 64 | +143.9% | +6.24% | 68.8% | +0.097% |
| L4 full per-thesis ❌ | 39 | +45.7% | +1.71% | 59.0% | +0.044% |

### PAPER 210 trades:
| Layer | trades | total_raw | total_cap | win % | mean_cap |
|---|---|---|---|---|---|
| L1 原始 | 209 | -317.6% | -15.88% | 26.3% | -0.076% |
| **L2 exit_v2 only** | 210 | **+131.9%** | **+6.60%** ⭐️ | 65.2% | +0.031% |
| L3 strict E | 142 | +89.2% | +4.46% | 64.8% | +0.031% |
| L3.5 relaxed E | 158 | +39.0% | +3.26% | 63.3% | +0.021% |
| L3.5b strict E + var pos | 141 | +84.1% | +5.51% | 64.5% | **+0.039%** |
| L4 full | 69 | -15.3% | -0.30% | 58.0% | -0.004% |

### Hermes 关键发现

1. **L2 在两个 sample 总 cap 都最高** — 任何 rule 加入都损失 alpha
2. **L4 在 Hermes 上是 worst** (-71% LIVE / -105% PAPER vs L2 cap)
3. **rule SKIP 在 PAPER 上特别 hurt** (-32% cap) — pc_crash_bounce_long 大量被 E 误砍
4. **var pos sizing 在 LIVE 上略损** (cap +6.24% < +7.19% L3) 因为 LIVE 的 C/D triggered trades 不够强
5. **var pos sizing 在 PAPER 上略益** (mean_cap +0.039% > +0.031%)

## Broader Market 测试 (1425 events,无 BWE 过滤)

| Layer | trades | total_raw | total_cap | win % | mean_cap |
|---|---|---|---|---|---|
| **L1 naive (-5%/+20%)** | 1424 | **-68.6%** ❌ | -3.43% | 27.6% | -0.002% |
| L2 exit_v2 only | 1425 | +1005.1% | +50.26% | 64.6% | +0.035% |
| L3 strict E uniform 5% | 1017 | +671.0% | +33.55% | 65.7% | +0.033% |
| L3.5 relaxed E + var | 1019 | +707.5% | +52.79% | 66.4% | +0.052% |
| L3.5b strict E + var | 940 | +723.3% | +53.58% | 66.5% | +0.057% |
| **L4 directional + var** | 1017 | **+1147.6%** ⭐️ | **+74.80%** ⭐️ | 66.9% | **+0.074%** |

### Broader 关键发现 (与 Hermes 完全反转)

1. **L4 是 broader market 上 winner** (+1147.6% raw / +74.80% cap, +14% over L2)
2. **L1 naive 完全失败** (-68.6%) — 简单 -5% SL/+20% TP 不适合妖币
3. **rule SKIP 仍损 alpha 一点** (L3 -33% raw vs L2)
4. **L4 分配 86 trades 到 follow direction** (B+F rule):
   - 9 B (trend_continue): direction 切换
   - 77 F (high pre_vol): SKIP → ENTER follow
   - 这 86 trades 贡献 +424.3% 额外 raw

### 数据反转的 mechanism

| Sample | Direction signal source | L4 表现 | 原因 |
|---|---|---|---|
| Hermes (BWE) | BWE Telegram 已选 | **-71%** (worst) | dir-check 否决 BWE 正确决策 |
| Broader market | 无外部信号 | **+14%** (best) | rule 选方向是真 alpha |

**结论**: 不同信号源应用不同 layer。

## Caveat 已诚实披露

1. ⚠️ Hermes L4 vs Broader L4 不同 (前者 dir-check + per-thesis;后者 rule direction + baseline exit)
2. ⚠️ 1425 events 中 1166 (82%) 来自 top-100 dive coins,其他 259 (18%) 默认 Rule A SKIP
3. ⚠️ total_cap 是理论上限 (假设可同时入 1425 trades),跨 layer 比较 valid

---

## Phase 3 关键文件

- `05_audits/three_layer_v3_l35.json` — Hermes L1-L3.5b
- `05_audits/market_layers_v3.json` — Broader market L1-L4
- `scripts/three_layer_comparison_v3.py` — Hermes 4-layer test
- `scripts/market_layers_validation.py` — Broader market 6-layer test

## Phase 3 → Phase 4 trigger

用户:"L2/L3.5b 能够针对 BWE 继续优化一下吗?L4 能够针对整个市场优化一下吗?"

→ 进入 optimization (Phase 4)
