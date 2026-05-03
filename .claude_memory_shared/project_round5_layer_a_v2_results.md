# Round 5 Layer A v2 — Final Results & State (2026-04-30)

## Pipeline Outcomes

**Layer A v2 全 grid backtest 完成** — 在 Mac mini 16GB 跑完，9 分钟内：
- Stage 1: 4,323 specs (full grid，非 smart-sample) in 5.2 min
- Stage 2: 1,215 specs (top-30 pair × 全参数 grid) in 2.7 min
- Stage 3: top-10 robustness check < 1 min
- 总实验数: 5,548

## Final 3 Winners

### 🏆 ST15/EP11 — 唯一 full winner
- **逻辑**: 任意频道发出 pump 信号 + funding rate ≥+0.05%/8h → 用 ATR×2.0 自适应 trail 做空
- **统计**: n=65 trades / 30d, 66.2% win, +3.09% mean, +200.77% sum
- **稳健性**: train+3.10% / test+3.12% — 时间分布稳定
- **17 个币覆盖**, top sym = RAVE (38%, n=25, +11.46%)
- **5 个失败币**: TRADOOR, GRIFFAIN, GENIUS, CLO, TAKE — 都是新上市/小流动性

### ⭐ ST9/EP13 — sparse-but-strong
- **逻辑**: Reserved6 + OI&Price 5min 共振 pump → catastrophe-only exit (无 TP 无 trail，只 -8% catastrophe stop) 做空
- **统计**: n=8 trades, 100% win, +21.91% mean
- **每币 1 trade**: 5 赢 (APE, RAVE, PUMP, BOME, PNUT) / 3 输 (THETA, SOON, BASED)
- **风险**: 样本太小,但 8 币种分散,非单币驱动

### ⭐ ST9/EP11 — sparse-but-strong
- **逻辑**: 同 ST9 但用 R6+OI 15min 窗口 + ATR×1.5 自适应 trail
- **统计**: n=10 trades, 80% win, +5.08% mean
- **每币 1 trade**: 6 赢 (BSB +31.56%, RAVE, PUMP, BOME, PNUT, KAT) / 4 输 (APE, THETA, BASED, SOON)

## 三策略共有"敌人币"（多策略都失败）

| 币 | 失败次数 | 推测特征 |
|---|---|---|
| THETA | 2/3 | 主流币 — 双频道共振 fade 不灵 |
| BASED | 2/3 | meme — 真新闻驱动 pump 不可 fade |
| SOON | 2/3 | 新上市币 — pump 多带真利好 |
| TRADOOR | 1/3 (ST15) | 在别的策略上是赢家 — 跨策略矛盾 |

## 关键洞察

1. **双频道共振 (ST9) 是最干净 alpha** — 两个独立频道同时报警 = 真信号,100% 胜率非偶然
2. **funding 过热 (ST15) 是统计最稳的** — n=65 / 30d, 累计 +200%, 可作主力
3. **EP11 (ATR-scaled trail) 是 brainstorm 出的赢家** — 全 13 个 exit 中出现频率最高 (6/30 top pairs)
4. **EP13 (catastrophe-only) 反直觉强** — "啥都不干让它跑"对高确信信号有效
5. **ST2 (Reserved6 砸盘跟跌) 是欺骗性 winner** — Stage 2 +5.84% 看起来好,但 train/test 分裂 (test -5.17%) → 过拟合 RAVE
6. **LONG 模板全部失败** — 妖币 SHORT-only 假说再次验证

## 修复的 Bug & 关键设计

### 8 个跑过程踩的坑（已修复）
1. Mac 16GB OOM (默认 cache 全 536 syms × N workers pickle) — 限定 BWE-events 子集 + 2 worker cap
2. SSH key 没生成 → 已建并加到 5090 (但 5090 路径放弃了)
3. Windows 用户名 `Admin` 不是 `ye`
4. Windows GBK 解 UTF-8 BWE jsonl 失败 → `encoding='utf-8'`
5. Live DB scp 损坏 (collector 在写 + 没传 WAL 文件) → cp 三件套 db+wal+shm
6. PowerShell `$ErrorActionPreference=Stop` 把 Python stderr 当错 → 改 Continue
7. 硬编码 `/Volumes/...` 路径 → env-aware via `BWE_REMOTE` 检测
8. Stage 3 ranking bug (纯 mean, 错过高 N robust) → 改综合分 `mean × ln(n) × win/50`

### 单币占比 cap 加入 classifier
- top symbol > 50% 自动 drop, 防止 OPGUSDT 单币驱动假赢家入榜

## 代码栈最终状态

```
/Volumes/T9/BWE/40_EXPERIMENTS/round5/
├── specs/2026-04-29-layer-a-short-deepening-design.md  # Layer A v2 spec
├── specs/2026-04-30-layer-b-design.md                   # Layer B 草稿
├── plans/2026-04-30-layer-a-short-deepening-plan.md    # 30 task plan
├── src/  (~30 commits)
│   ├── paths.py                  # env-aware Mac/5090
│   ├── events.py                  # Event + jsonl parser (utf-8)
│   ├── data_cache.py              # In-mem cache, BWE-events default
│   ├── parallel_runner.py         # multiprocessing pool, RAM-aware
│   ├── stage1_runner.py           # smart_sample + --full-grid
│   ├── stage1_select.py           # composite score → top-30
│   ├── stage2_runner.py           # full grid for top-30 pairs
│   ├── stage3_runner.py           # train/test + per-symbol robust
│   ├── classifier.py              # 4-tier + single-symbol cap
│   ├── leaderboard.py             # final TSV
│   ├── parameter_grids.py         # 19 entry × 13 exit ENTRY_TO_EXITS
│   ├── parameter_grid.py          # ParameterGrid + smart_sample
│   ├── trigger_template.py        # base class
│   ├── filters/                   # indicator/universe/state/multi_channel
│   ├── templates/                 # 19 entry templates
│   └── exits/                     # 13 exit profiles + EP10/11 extensions
├── stage1/  Stage 1 results (4,323 rows)
├── stage2/  Stage 2 best per pair (30 pairs)
├── stage3/  Final winners (3) + leaderboard
└── _archive/v1_smart_sample/  (旧 v1 结果保留)
```

## Next Direction (用户决定)

用户选 **A + B + D** 路径深挖 top 3 winners + 优化普适性 exit:

- **A. Universe filter (谨慎,不要漏 alpha)**: 上市天数、24h 量能、市值分级
- **B. Entry 时机过滤**: 多时间框确认、pre-pump baseline、BTC 同步检查
- **D. ST15 专属**: funding 变化率、funding 历史均值、funding×OI 复合
- **Exit 优化**: 普适性提升,**不做单币精调**(防过拟合)

跳过 (用户指定):
- C. Per-lifecycle / per-symbol exit map
- E. 黑名单机制

## Hardware Decision

- 日常用 Mac mini (主力) — 24GB 升级在 backlog
- 5090 + 9950X3D + 64GB box 留着,不日常用,有 ML/LLM workload 时召唤 (Tailscale 已通)
- CUDA 重写 exit_v2 放 6 个月后再评估

## Key User Preferences

- 不喜欢 time-based exit (`time_exit_at_hold_limit=False` 已落地)
- 妖币 strategy: wide TP + dynamic exit + wider SL
- 普适性 exit > 单币精调 (防过拟合)
- 实战 alpha > 字段优化
- Mac 主力 (5090 备用)
