# Decision Log — Round 4 Per-Symbol Strategy

> 每一次用户做的关键决策 + 推动它的数据 + 我的推荐 (是否被采纳)

---

## 决策 #1 — 妖币定义方案 (2026-04-28)

**用户问**: 妖币该如何定义?

**3 个选项 + 我的推荐**:
- A: 简单硬阈值 (market_cap < $200M, vol > $5M, ATR > 4%)
- B: 行为分 (composite 4 维 weighted score) ← 我推荐
- C: Cluster-based 自动分类

**用户选**: **B** (理由: 灵活、可平滑过渡到 per-symbol tier、数据需求温和)

**结果**: yaobi_score 公式 = 35×big_moves + 25×max_daily_range + 25×avg_atr + 15×(1-vol_rank)

---

## 决策 #2 — 用真实数据验证假设 (2026-04-28)

**用户**: "我让你在完整的数据中找答案就是让你更加灵活的去面对这些问题"

**含义**: 不要预设规则,让数据自己告诉我们规则

**触发**: 我之前 manual 设计了 6 条规则准备验证;用户更希望 data-driven discovery

**结果**: 跑 `rule_discovery.py` 做 single-feature + pair-feature winrate scan,自动产出 7 条规则

---

## 决策 #3 — Rule F 选择 (2026-04-28)

**用户问**: 高 pre-vol → SKIP / FOLLOW / 条件 (only late_burst follow)?

**用户初选**: III (条件 FOLLOW)
**Then 数据告诉**: 3 个变体差距 < 1%
**用户改选**: 维持 III,等 30d 数据验证

**30d 数据结论**: 仍然差距 < 1% (F=SKIP +43.7% / F=FOLLOW +43.4% / F=条件 +42.7%)

---

## 决策 #4 — 仓位 sizing 8% 还是 5% (2026-04-28)

**用户问** (我提): 规则 C (mean_revert + sustained/single_burst) 给 8% 仓位是不是太大?

**用户**: **不用保守,维持 8%**

**理由**: 历史 win 100% (n=45) 可信

---

## 决策 #5 — 数据采集 (2026-04-28)

**用户问**: 是否拉全市场 30d × 530 symbols 数据?

**初始打算**: top 100
**用户**: **A — 全市场补全**

**结果**:
- 530 syms × 30d klines (22.5M rows)
- 526 syms × open_interest_1h (377K rows)
- 526 syms × 3 long-short ratios
- 526 syms × taker_buy_sell (already in klines)
- DB size 3.3GB, 76 min runtime via 4 workers

---

## 决策 #6 — VPN 切换后自检 (2026-04-29)

**用户**: "把之前的 binance collector 全数据收集进程也修复起来,如果我以后开关 vpn 他们要能够有自检恢复的能力"

**实施**:
- 添加 `collectors_watchdog.sh` (cron 每分钟跑)
- 检测 process 死/数据 stale
- 自动重启 (区分 VPN-down vs collector-stuck)
- Crontab: `* * * * * /Users/ye/.hermes/scripts/collectors_watchdog.sh`

---

## 决策 #7 — Layer 4 vs Layer 3 取舍 (2026-04-29)

**用户**: "感觉第四版的策略效果反而没有第三版好,我该怎么取舍呢?我不想损失 alpha"

**数据真相** (Hermes 82 LIVE):
- L2 (exit_v2 only): +149.0% ⭐️
- L3 (rule SKIP): +143.9%
- L4 (per-thesis + dir-check): **+45.7%** ❌

**根因**: L4 的 dir-check 把 BWE 已选好的方向 override 掉,导致 28 trades 被砍

---

## 决策 #8 — Layer 选择 + Broader Market 验证 (2026-04-29)

**用户**: "如果你把 L1-L4 这些策略带入到近一个月中市场所有的妖币中进行一个验证呢"

**数据反转** (1425 broader-market events):
- L1 naive: -68.6% ❌
- L2 exit_v2: +1005.1%
- L3.5b: +723.3%
- **L4 directional: +1147.6%** ⭐️

**核心 mechanism**:
- 在 BWE-pre-filtered Hermes 上,L4 因 dir-check 损失 alpha
- 在 broader market 无外部方向信号上,L4 rule 决定的 direction +14% alpha 来源
- 86 trades (B+F follow direction) 贡献 +424% raw

---

## 决策 #9 — 优化变体最终选择 (2026-04-29)

**用户**: "L2/L3.5b 能够针对 BWE 继续优化一下吗?L4 能够针对整个市场优化一下吗?"

**优化测试结果**:

### BWE (Hermes 82 LIVE + 210 PAPER):

| Variant | LIVE total_raw | PAPER total_raw | 推荐? |
|---|---|---|---|
| L2-base | +149.0% | +131.9% | LIVE 最强 |
| L2-wide-trail | +83.7% (-65pp) | +84.0% (-48pp) | 两边都损 ❌ |
| L2-tight-trail | +106.0% | +128.5% | 双侧 modest 损 |
| **L2-per-lifecycle** | +101.4% | **+144.1% (+12pp ⭐️)** | ← 用户选 |
| L3.5b-tier-pos | +143.9% | +84.1% | mean_cap 提升但 raw 损 |

### Broader market (1425 events):

| Variant | total_raw | total_cap | mean_cap |
|---|---|---|---|
| L4-base | +1147.6% | +74.80% | +0.074% |
| L4-wider-follow | +1119.0% (-29pp) | +73.37% | +0.072% ❌ |
| L4-12pct-D | +1147.6% (=) | +87.40% (+17%) | +0.086% |
| L4-continuous-pos | +971.2% (-176pp) | +95.50% | +0.103% (失 alpha) |
| **L4-tier-3-5-8-12** | **+1147.6% (=)** | **+89.70% (+20%)** | **+0.088%** ⭐️ ← 用户选 |

**用户最终选**:
1. BWE: **L2-per-lifecycle** (PAPER +12pp 提升)
2. Broader: **L4-tier-3-5-8-12** (无损 alpha + 20% cap 提升)
3. 进入 spec v2 重写阶段
4. 全归档以便后期复盘

---

## 数据诚实性 audit (用户要求)

**用户**: "确定你的数据测试都是诚实的,全部基于数据说话,不要编造"

**Audit 通过**:
- ✅ 1425 events 真实存在 (re-detect 确认)
- ✅ TRADOOR event 0 fade=6.54% 与 dive json 完全一致 (manual spot-check)
- ✅ JSON 输出 = 报告数字 (字节级对比)

**Caveat 已诚实披露**:
1. ⚠️ "Broader L4" ≠ "Hermes L4" (前者无 dir-check / per-thesis exit)
2. ⚠️ Rule labels 只覆盖 top-100 dive coins (1166/1425 = 82%)
3. ⚠️ total_cap 是理论上限 (假设可同时入 1425 trades),跨 layer 比较仍 valid

---

## 关键 metric snapshot (lock-in baselines)

### Hermes LIVE (82 trades, 30d data):
- L1 原始: -72.1% raw / -3.61% cap / 35.4% win
- **L2-per-lifecycle (chosen)**: +101.4% raw / +5.07% cap / 67.1% win
- L2-base (alt): +149.0% raw / +7.45% cap / 67.1% win

### Hermes PAPER (210 trades, 30d data):
- L1 原始: -317.6% raw / -15.88% cap / 26.3% win
- **L2-per-lifecycle (chosen)**: **+144.1% raw / +7.21% cap** / 65.2% win
- L2-base (alt): +131.9% raw / +6.60% cap / 65.2% win

### Broader market (1425 events, 30d data):
- L1 naive: -68.6% raw / -3.43% cap / 27.6% win
- **L4-tier-3-5-8-12 (chosen)**: **+1147.6% raw / +89.70% cap** / 66.9% win / mean_cap +0.088%
