# Phase 4 — Optimization (2026-04-29)

> 针对 BWE / Broader 各自跑 5 个变体,找最优解

## BWE 优化变体 (5 个)

针对 Hermes 82 LIVE + 210 PAPER,围绕 L2 (exit_v2 only) 和 L3.5b (var pos) 设计:

| 变体 | 设计 |
|---|---|
| **L2-base** | 当前默认,trail tier (5/10/25/50/100% → 4/7/12/18/25%) |
| L2-wide-trail | 放宽 trail (4/7/12/18/25 → 5/10/18/28/40)。假设 winners 跑更远 |
| L2-tight-trail | 收紧 trail (3/5/8/12/18)。假设锁利更快 |
| **L2-per-lifecycle** | sustained/late_burst → wide trail; spike_decay → tight trail |
| L3.5b-tier-pos | 4 档仓位:3% (sc<50) / 5% (default) / 8% (C/D) / 12% (sc≥85) |

## BWE 测试结果

### LIVE (82 trades)
| Variant | total_raw | total_cap | mean_cap |
|---|---|---|---|
| **L2-base** ⭐️ | **+149.0%** | **+7.45%** | +0.091% |
| L2-wide-trail | +83.7% (-65pp ❌) | +4.18% | +0.051% |
| L2-tight-trail | +106.0% | +5.30% | +0.065% |
| L2-per-lifecycle | +101.4% (-48pp) | +5.07% | +0.062% |
| L3.5b-tier-pos | +143.9% | +6.37% | **+0.100%** |

### PAPER (210 trades)
| Variant | total_raw | total_cap | mean_cap |
|---|---|---|---|
| L2-base | +131.9% | +6.60% | +0.031% |
| L2-wide-trail | +84.0% (❌) | +4.20% | +0.020% |
| L2-tight-trail | +128.5% | +6.42% | +0.031% |
| **L2-per-lifecycle** ⭐️ | **+144.1% (+12pp)** | **+7.21%** | +0.034% |
| L3.5b-tier-pos | +84.1% | +7.38% | **+0.052%** |

### BWE 关键发现

1. **L2-base 在 LIVE 最强** — LIVE 主要是 spike_decay coins (oi_overcrowded_crash type)
2. **L2-per-lifecycle 在 PAPER 最强** — PAPER 主要是 sustained/late_burst coins (pc_crash_bounce type)
3. **wider trail 在 spike_decay 上反而 hurt** (LIVE -65pp) — 这些 coins decay 太快,需要 tight 锁利
4. **per-lifecycle 不是 universal winner** — 但根据用户决策 #9 偏向 PAPER 表现 (validation gate),**最终选 L2-per-lifecycle**

## Broader Market 优化变体 (5 个)

针对 1425 events,围绕 L4 (rule directional + var pos) 设计:

| 变体 | 设计 |
|---|---|
| **L4-base** | 当前 5/8% pos + exit_v2 baseline |
| L4-wider-follow | B/F follow trades 用 wider trail |
| L4-12pct-D | D 规则仓位 8% → 12% |
| L4-continuous-pos | 仓位线性按 score (50→5%, 90→12%) |
| **L4-tier-3-5-8-12** | 4-tier 仓位 (sc<50: 3%, default: 5%, C/D: 8%, sc≥85: 12%) |

## Broader Market 测试结果

| Variant | trades | total_raw | total_cap | mean_cap | big_w | cat |
|---|---|---|---|---|---|---|
| L4-base | 1017 | +1147.6% | +74.80% | +0.074% | 109 | 41 |
| L4-wider-follow | 1017 | +1119.0% (-29pp ❌) | +73.37% | +0.072% | 109 | 41 |
| L4-12pct-D-rule | 1017 | +1147.6% (=) | +87.40% (+17%) | +0.086% | 109 | 41 |
| L4-continuous-pos | 923 | +971.2% (-176pp ❌) | +95.50% | **+0.103%** | 98 | 38 |
| **L4-tier-3-5-8-12** ⭐️ | 1017 | **+1147.6% (=)** | **+89.70% (+20%)** | **+0.088%** | 109 | 41 |

### Broader 关键发现

1. **L4-tier-3-5-8-12 是无损 alpha 的最佳选择** — total_raw 不变,total_cap +20% 提升
2. **L4-continuous-pos cap 最高 (+95.50%)** 但**牺牲 -176pp raw alpha** — 用户说"不想漏 alpha",**不选**
3. **L4-wider-follow 失败** — wider trail on follow trades 反而 hurt (-29pp)
4. **L4-12pct-D 是 sub-optimal 版** (+17% cap) — L4-tier-3-5-8-12 更全面

### 用户决策 #9 总结

| 维度 | 选择 | 理由 |
|---|---|---|
| BWE | **L2-per-lifecycle** | PAPER +12pp raw,LIVE 略损但 paper 验证更重要 |
| Broader | **L4-tier-3-5-8-12** | 无损 alpha + 20% cap 提升 |
| Action | 进入 spec v2 重写 + 全归档 | |

---

## Phase 4 关键文件

- `scripts/optimization_tests.py` — 5+5 变体测试脚本
- `/tmp/opt_tests.log` — 完整测试输出 (full log)
- 此文档为 archive copy

## Final lock-in 数据 (baseline)

### BWE L2-per-lifecycle
- **LIVE**: +101.4% raw / +5.07% cap / 67.1% win / mean_cap +0.062%
- **PAPER**: +144.1% raw / +7.21% cap / 65.2% win / mean_cap +0.034%

### Broader Market L4-tier-3-5-8-12
- **1425 events**: +1147.6% raw / +89.70% cap / 66.9% win / mean_cap +0.088%
- 灾难数: 41 (vs L2 56) — 风险更低
- 大赢家: 109 (vs L2 154) — 略少但 cap 翻倍

## Phase 4 → Phase 5 trigger

用户决策 #9 → 进入 spec v2 重写 + 全归档 (本档案)。
之后:writing-plans skill → implementation plan。
