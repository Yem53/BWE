---
name: 妖币策略 — 庄家控盘识别 + 宽 TP + 动态止盈 + 较宽 SL（≤10%）
description: User's core thesis for BWE Autoresearch — the trading universe is small-cap manipulated coins ("妖币"), so the research is fundamentally about detecting market-maker pump schemes; TP must be wide (tens of % to 100%+), SL absolute upper bound is 10%, and Round 3 archetypes that violated this are by-construction wrong-regime
type: feedback
---

## Core thesis (2026-04-27 强化版)

**研究本质 = 识别庄家控盘**（用户原话）：

> "我做的基本上都是小妖币，因为有庄家再拉升，所以更像是识别庄家控盘的一个过程，
>  然后在里面寻找规律。然后 TP 不要设置的太小，因为很多妖币有百分之大几十甚至
>  过百的收益，这个地方要给到充分的空间，大胆去尝试；然后 SL 也不能太过于谨慎，
>  在 10 以内找到合适的参数。"

**这意味着 BWE 项目不是"找 alpha"——是"识别 pump-and-dump 庄家行为模式"**。所有 entry archetype 应当对应庄家控盘的特征信号（abnormal volume burst、taker_buy + smallcap、OI 异动 + 低流动性、quiet period 后第一信号 等）。所有 exit geometry 应当配合"骑庄家拉升全程"的实战节奏。

## 已知违反 (Round 3 自我诊断)

Round 3 跑了 20K experiments，Top-50 entry 全部 TP ∈ [0.39, 1.5]%、SL ∈ [3, 6]%。这从根本上违反了下方"TP design"的所有要求 —— **Round 3 的 winner 排序在妖币 regime 下整体是错的方向**。Round 4 必须先把 archetype space 重设到妖币尺寸，再考虑跑 GPU loop。

## 用户口述（2026-04-27 早些时候）

> "TP 可以放的很宽，追求动态止盈，因为我这监测的全部都是妖币，利润空间很大，
>  就是注意不要被中途洗盘洗出去了，SL 也可以不用过于保守，因为小市值的
>  币种价格波动很大。"

The BWE channels (OI_Price, pricechange, Reserved6) all monitor small-cap "freak coins" (妖币) where:
- A single signal can lead to **几十% 甚至 100%+ moves** within hours-to-days (不只是 5-30%)
- Tight TPs (0.2-0.5%) leave most of the profit on the table
- Tight TPs are also FEE TRAPS — paper-shadow showed +0.15% mean got eaten by 16bps round-trip

## Implications for entry × exit search space

### TP design (2026-04-27 扩展)
- **Don't fix TP narrow** — explore TP up to **30-100%+** for top entries (用户原话："百分之大几十甚至过百")
- **大胆尝试** — 不要在搜索空间设保守上限，给庄家拉升留出全程空间
- **Prefer trailing / multi-stage TP** over fixed TP — let winners run
- **Activation thresholds matter** — trail should activate at +1-3% so we're not shaking out on early noise
- **Multi-stage TP**: 30-40% at first level (5-10%), 60-70% riding wide trail toward 30-100%+

### SL design (2026-04-27 强化)
- **Don't be too conservative** — small caps swing 2-5% on noise within minutes
- **绝对值上限 ≤ 10%**（用户原话："SL 也不能太过于谨慎，在 10 以内找到合适的参数"）
- Search SL ∈ [3, 10]%；avoid SL < 1% (容易被庄家洗盘洗出)
- **SL/TP ratio < 4** rule (Round 2 era) **应被废除** in 妖币 context — 那条规则隐含了大盘币的 fat-left-tail 假设；妖币 regime 下绝对值更重要

### Shake-out protection (中途洗盘) — explicit user concern
- After entry, price often retraces -1 to -2% before continuing — DON'T stop on this
- Strategies to consider:
  - Time-window protection (no SL in first 60-120s if entry signal was strong)
  - Volatility-aware SL (SL = max(fixed%, 1.5×ATR_5m))
  - Re-entry logic (if stopped early but trend resumes within Xmin)

## Implications for LLM debate posture

### Generator should:
- **Propose wide-TP variants** for top entries (>2% TP), not just narrow ones
- **Explore multi_tp + trail families more aggressively** — they were under-represented in Round 3
- **Avoid proposing TP < 1% unless explicitly testing fee-trap hypothesis**

### Pattern Miner should:
- **Flag any keep with TP<0.5% as fee-trap suspect** — even if it has high Kelly, real-world won't survive 16bps
- **Highlight trailing/multi_tp success patterns** when found

### Cross-Pair Recommender should:
- **Prioritize (entry × wide_dynamic_exit) pairs** for fast-test
- **Demote any pair where exit_family=fixed AND TP<1%**

### Synthesizer / Self-Reflection should:
- **Lean ACCEPT for novel wide-exit experiments** even if backtest score is mediocre — the registry needs more wide-exit data points

## Implications for variant grid (next loop)

When Round 4+ accepted archetypes are merged and the loop runs, expand TP variant grid:
- Old (Round 1-3, wrong-regime): TP ∈ {0.2, 0.3, 0.5, 0.8, 1.2, 2.0}
- Round 4 baseline: TP ∈ {1.5, 3, 5, 7, 10, 15, 25, 40, 70} (单位 %)；可以从 +5% 起，给庄家拉升全程空间

Same for trail step:
- Old: trail_step ∈ {0.5, 1.0, 1.5}
- Round 4 baseline: trail_step ∈ {1.5, 2.5, 4.0, 6.0}, plus multi-stage variants

SL grid:
- Round 4 baseline: SL ∈ {3, 5, 7, 10}（绝对上限 10%）

Hold horizon (新加 — 妖币拉升常持续小时到数天):
- Old (Round 1-3): hold ∈ {1, 5, 10, 30, 60} 分钟
- Round 4 baseline: hold ∈ {30m, 2h, 6h, 24h, 48h, 72h}

## Round 3 → Round 4 实验空间重设清单

| 维度 | Round 3 实际 | Round 4 应改为 | 原因 |
|---|---|---|---|
| TP grid | 0.2-1.5% | 1.5-70% (默认从 5% 起) | 庄家拉升空间 |
| SL grid | 0.2-6% | 3-10% (≤10% 绝对上限) | 妖币波动天然大 |
| trail_step | 0.2-1.5% | 1.5-6% | 不能被早期噪音洗 |
| hold horizon | 1-60 min | 30m-72h | 拉升周期长 |
| SL/TP ratio rule | "reject if >4" | **废除** | 大盘币遗留假设 |
| keep metric | legacy p25 (BUGGY) | 待重设 (mean_net + asymmetric_aware) | metric 自身有 bug |

## How to apply

- Read this memory at the START of any Round 4+ debate prep
- Inject summary into TEAM_PHILOSOPHY.md so all 11 LLM roles see it
- When user says "the score is positive but paper-shadow shows loss", check for tight-TP fee-trap pattern first
- When suggesting paper-shadow tests, check that exit kernel matches the 妖币 posture (wide trail / multi_tp)

User has explicitly authorized expanding the search space toward wider exits — do NOT add caution constraints like "be careful about wider TP risk", that goes against stated preference.
