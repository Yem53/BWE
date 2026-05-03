# Phase 2 — 30d Full-Market Validation (2026-04-28 night → 04-29 morning)

> 30d × 530 symbols backfill → 4 analyses re-run → 5d 结论 robust 验证

## 数据采集 (76 min via 4 workers Proton VPN)

### 经历 (诚实披露)
- **3 次 puller 死亡**:
  1. Codex agent sandbox 阻止 localhost proxy → 0 数据
  2. T9 ExFAT fskit driver 阻止 SQLite locking → 写不入
  3. 5 min Bash timeout 杀进程 → 改用 nohup
- **VPN 切换**: clash 流量耗尽 → Proton VPN,后又掉一次,后又切墨西哥 (实际出 Czechia)
- **Bug 发现**: HTTP error 5 retry 后 break 但仍 mark done → 161 zombie symbols 错误标记
- **修复**: only mark done if n>0; reset 161 + restart
- **最终**: 76 min runtime, 0 失败 symbols

### Final dataset
| Table | Rows | Symbols | Time range |
|---|---|---|---|
| `klines_1m` | **22,497,630** | 529 | 2026-03-29 → 2026-04-29 (30d 6h) |
| `open_interest_1h` | 377,216 | 526 | 30d full |
| `global_long_short_1h` | 377,011 | 526 | 30d |
| `top_account_long_short_1h` | 377,118 | 526 | 30d |
| `top_position_long_short_1h` | 376,899 | 526 | 30d |

DB: `/Users/ye/.hermes/research/binance_extended_history.sqlite3` (3.3 GB, APFS)

## 4 套 Analyses Re-run on 30d

### 1. yaobi_score_v1_30d (530 syms)

**Sanity check (vs 5d v0)**:
| Symbol | 5d rank | 30d rank | 5d score | 30d score | 评论 |
|---|---|---|---|---|---|
| TRADOOR | 1 | 9 | 85.5 | 83.6 | 稳定极妖 |
| RAVE | 13 | **5** ⭐️ | 72.2 | 85.9 | 30d 揭示真实妖性 |
| DAM | 2 | 20 | 85.2 | 77.4 | 平稳 |
| ZKJ | 4 | 30 | 82.4 | 73.3 | 平稳 |
| KAT | 17 | **90** | 69.3 | 54.6 | 5d 是它 peak,真实退烧 |
| 0G | 277 | 347 | 32.1 | 26.9 | 仍然 quiet |
| BTC | 535 | 528 | 1.0 | 1.1 | confirmed 大盘 |

**80+ 极妖**: 6 (5d) → **12** (30d) — sample 多让区分清晰

### 2. yaobi_per_symbol_dive_v1_30d (top 100, 1407 waves)

**Lifecycle distribution** (30d):
- late_burst: 38 coins / 441 waves — fade total **+1059%**
- sustained: 33 coins / 610 waves — fade total **+2225%** ⭐️ 主力
- spike_decay: 25 coins / 349 waves — fade +729%
- single_burst: 4 coins / 7 waves

**Reaction distribution**:
- mixed: 55 coins / 894 waves — fade +2421%
- mean_revert: 36 coins / 458 waves — fade +1605%
- **trend_continue: 9 coins** / 55 waves — **follow +216%** (cigarette signal)
  - APE / PLAY / ESPORTS / SPK (5d 已知) + PUMPBTC / INX / CROSS / JOE / IRYS / ZEREBRO (30d 新)

**Pre-vol pattern (1407 waves) — 验证 5d 反向 signal**:
- < 1.5x: fade win 82.8%
- 1.5-2.5x: 79.9%
- 2.5-4x: 75.1%
- ≥ 4x: 72.6%
- 反向 confirmed ✓

**Wave duration 3-6min 的"死亡区"**:
- 5d: 71.0% win (-8 pp)
- 30d: **76.2% win (-3 pp)** — 不再是死亡区,只是略弱
- 这意味着原 Rule E (3-6 SKIP) 在 30d 数据上是过严

### 3. rule_discovery_v1_30d

baseline fade_win = **79.0%** on 30d (vs 5d 78.1%) — 几乎一致 ✓
跨 1407 waves 验证 7 条规则的 evidence 仍 hold (除 Rule E 偏严)

### 4. rule_engine_simulation_v1_30d

30d 1407 waves 验证 6 个 strategy variants:

| Strategy | Total Cap | Win % | Mean cap/trade | 灾难 |
|---|---|---|---|---|
| Always FOLLOW 5% ❌ | -74% | 58.4% | -0.053% | 95 |
| Random skip 50% + FADE | +112% | 77.9% | +0.157% | 15 |
| Always FADE 5% baseline | +202% | 79% | +0.144% | 23 |
| Rule Engine v1.1 (你选 F=条件) | +249% | 80.0% | +0.227% | 19 |
| Rule Engine v1 (F=FOLLOW) | +250% | 79.5% | +0.220% | 19 |
| **Rule Engine v1 (F=SKIP)** | +248.5% | **80.2%** | **+0.232%** | 19 |
| Always FADE 8% | **+323%** | 79% | +0.230% | 23 |
| Rule Engine 无 SKIP | +280% | 79.3% | +0.199% | 22 |

**3 个 F variants 差距 < 1%** — 决策不重要

## 30d 数据告诉我们

1. ✅ **5d 主要发现 robust** (yaobi 排名变化但相对位次稳定;rule winrate 变化 <2 pp)
2. ⚠️ **Rule E (3-6 SKIP) 30d 上是边际有害** — 5d 看是死亡区,30d 看 marginal -3pp
3. ✅ **trend_continue 多了 5 个新成员** (PUMPBTC/INX/CROSS/JOE/IRYS/ZEREBRO)
4. ✅ **L4 没改善 (broader Rule Engine 上)** — 在 BWE 数据上仍是 worst layer

---

## Phase 2 关键文件

- `05_audits/yaobi_score_v1_30d.json` — 30d 530 syms 妖性分
- `05_audits/yaobi_per_symbol_dive_v1_30d.json` — 30d 100 syms × 1407 waves
- `05_audits/rule_discovery_v1_30d.json` — 30d single + pair scan
- `05_audits/rule_engine_simulation_v1_30d.json` — 6-variant strategy sim
- `scripts/yaobi_*_v2.py`, `rule_*_v2.py`, `three_layer_comparison_v2.py` — 30d analysis variants
- `scripts/pull_binance_parallel.py` — 4-worker puller (production)
- `scripts/binance_24h_ticker_collector.py` — 新增 24h ticker collector
- `scripts/collectors_watchdog.sh` — VPN-safe auto-recovery

## Phase 2 → Phase 3 trigger

用户问:"如果你把 L1-L4 这些策略带入到近一个月中市场所有的妖币中进行一个验证呢"

→ 进入 broader market layer validation (Phase 3)
