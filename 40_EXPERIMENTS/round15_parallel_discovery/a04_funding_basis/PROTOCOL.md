---
type: experiment
tags: [round15, funding, premium, basis, carry, mean-reversion, protocol]
created: 2026-05-31
status: design
priority: high
---

# A04 — Funding / Premium / Basis 的 Carry 与均值回归 (研究协议)

> 方向负责人: 量化研究员 (独立子任务 a04)
> 输出目录: `40_EXPERIMENTS/round15_parallel_discovery/a04_funding_basis/`
> 状态: **协议设计 (只规划, 待开跑完整搜索)** — 数据体检已完成

---

## 0. 一句话 thesis (待数据验证, 非预设结论)

当 **premium**(标记价相对指数价的溢价, aux 库 `premium_5m.premium_pct`)或 **funding** 处于
**极端分位**时, 价格是否倾向 **均值回归**? 两条彼此独立的经济解释:

- **拥挤反转**: 极端正 premium = 多头拥挤 / 做多在付费 → 未来 N 小时倾向回调 → **做空**极端正分位;
  极端负 premium = 空头拥挤 / 做空在付费 → **做多**极端负分位。
- **Carry 持有**: 把 funding / premium 当 carry 收益, 持有 **收 funding 的方向**, 测持有期净 PnL
  (premium>0 时多头付空头 → 做空收 carry; 反之做多收 carry)。

注意这两条**方向一致**(都偏向 fade 极端正 premium / 多极端负 premium), 但驱动逻辑不同:
反转赌的是**价格回归**, carry 赌的是**资金费现金流**。回测会**分别记账**(价格 PnL vs carry 现金流)以区分来源。

### 与历史用法的区别 (关键, 防重复踩坑)

之前 round8 `validate_premium_90d.py` / `validate_funding_step_a.py` 把 premium 当
**"做空成交后的回避过滤闸"**(跳过极端负 premium 的做空) → 判为噪声。
**本任务 = 把 premium / funding 当独立的 carry / 反转进场信号正经测一次**, 横跨全 perp,
不依赖任何 BWE 事件、不当过滤器。这是全新的用法。

---

## 1. 数据体检结论 (已完成, 2026-05-31)

只读 `binance_futures_aux_archive.sqlite3` + `binance_futures_klines_archive.sqlite3`,
`immutable=1` 只读。

| 表 | 行数 | 币种 | 时间覆盖 | 用途 |
|---|---|---|---|---|
| `premium_5m`(symbol, open_time_ms, premium_pct) | 37,461,255 | 598 | 2025-10-01 → **2026-05-29** | **主信号** |
| `funding`(symbol, funding_time_ms, funding_rate) | 628,070 | 589 | 2025-10-01 → **2026-04-30** | 辅助 (5月缺, 见下) |
| `metrics_5m`(symbol, ts_ms, sum_oi, ...) | 36,905,706 | 592 | 2025-10-01 → 2026-05-30 | 选用 (拥挤度交叉验证) |
| `klines_{1m..6h}` | (40GB) | — | 同期 | forward return |

### 单位锁定 (用 BTC funding 反推, 已验证)

- `funding_rate` = **比例制**。BTC med abs ≈ 0.000039 (即 0.0039%/8h), 正常。
- `premium_pct` = **百分点 (%)**。BTC premium med abs ≈ **0.047 (即 0.047%)**, 与 funding 同量级, 合理。
  - ⚠️ **旧脚本 (round8 `trades_BD_prem.json` 的 `prem` 字段) 写的是"分数 ×100=百分比", 与 aux 库口径不同。本任务一律以 aux 库实测口径为准 (premium_pct 直接就是百分点), 不沿用旧假设。** 这正是历史"数据损坏教训"的来源之一。

### 数据健康问题 (必须先清洗, 否则作废)

1. **zero 占比 45.9%** (17.2M / 37.5M)。判定: **不是全局填充** —— BTC/ETH zero 率仅 0.0-0.1%。
   - 小币 zero 率中位数 ~48%, 7 个币 zero 率 >90% (ALPHAUSDT, FISUSDT, MKRUSDT, OLUSDT, UXLINKUSDT, VICUSDT, ZRCUSDT)。
   - 按时间看无任何一天 zero 率 >80% → **不是采集集体断档**, 是**小币 5m bar 无更新**。
   - **清洗规则**: `premium_pct == 0` 在大币是真值; 但保守起见, 凡 `premium_pct == 0` 的样本一律**当缺失剔除**(避免把"无更新"误当"零溢价")。这只损失精度, 不引入偏差。
2. **值域离谱**: min=-71.3, max=+101.5, p99=16.2, p99.9=64.8。极端大值集中在低价小币
   (RDNTUSDT 19.6k 个 >1, A2Z, FORTH, PUFFER, KDA...)。
   - **清洗规则**: `abs(premium_pct) > 3.0` 一律剔除 (funding 上限一般 ±2%/8h, premium 瞬时可略超,
     >3% 基本是脏数据或低价币标记价异常)。这些币本来也多是滑点 >0.8% 不可成交的"妖币"。
3. **p25=p50=p75=0**: 中间 50% 被 0 主导 → 印证 zero 当缺失处理的必要性。

### 流动性 / 可成交闸 (成本纪律的前置)

`premium` 极端的币往往是低流动性币, 滑点 >0.8% **不可成交**。
- **可成交筛**: 用 `metrics_5m.sum_oi_value` (USDT 计价 OI) 或 klines 的成交额做流动性下限。
  具体阈值在 Step 1 用数据定 (见下), 候选: 单币 24h quote volume ≥ $5M, 或 sum_oi_value 分位下限。
- 妖币 (低流动) 走 **0.8% 滑点**; 大币走 **小滑点**。回测对每笔按其流动性分档计滑点 (见 §5 成本)。

---

## 2. 纪律关卡 (硬性, 违则作废)

| 关卡 | 规则 |
|---|---|
| **窗口** | 8 个月 (2025-10-01 → 2026-05-29) |
| **Holdout 封存** | **最近 35 天 (open_time_ms ≥ 2026-04-26 00:00 UTC, 即 ts ≥ 1777全部) 只在最后揭晓一次**。dev 区 = 2025-10-01 → 2026-04-25, 在 dev 内做 walk-forward。⚠️ funding 只到 04-30, 故 funding 信号的 holdout 仅 04-26→04-30 共 5 天可用 → **funding 不单独进 holdout 验收, 只做 dev 内交叉验证 + premium 作主**。 |
| **无前视** | t 时刻的分位阈值**只能用 t 之前的数据估** (滚动分位, expanding 或 trailing-90d 窗口)。**绝不用全样本分位** (那是经典前视泄漏)。forward return 用 t **收盘后**下一根 bar 开盘进场 (entry at bar t+1 open), 不在信号 bar 内成交。 |
| **成本** | 往返 taker ~0.14% + 滑点分档 (妖币 0.8%, 大币 ~0.04%) + 持有期 funding 现金流 (carry 记账时计入)。**>0.8% 滑点的币不可成交, 直接排除。** |
| **赢家门槛** | (a) 净收益(扣全部成本)为正 且 (b) 超基线 (buy&hold / 随机进场同持有期) 且 (c) 跨 walk-forward 折一致 (符号不翻转) 且 (d) **过 holdout 仍正**。四条全过才算 alpha。 |
| **样本标注** | 任何 cell 样本 <50 笔**必须标注** "样本不足, 仅参考"。 |
| **泄漏自查** | 结果"太好" (如 Sharpe>3 / 月化 >50%) **先查泄漏**: ①是否误用未来分位 ②是否信号 bar 内成交 ③是否 survivorship (只统计存活币) ④premium 单位是否再次错位。 |
| **诚实** | **诚实报负 = 合格**。不 p-hack, 不挑窗口, 不事后改阈值凑显著。负结论照样写进报告。 |
| **范围** | **只研究不上实盘**。不碰实盘/EC2/fapi。Mac 被墙, 绝不调 Binance API, 全本地只读。 |

---

## 3. 本机资源纪律

- 只读 (`file:...?mode=ro&immutable=1`), 只写本任务目录。
- 3700万行不全量载入内存。**分批**: 按币种流式查询, 或按时间分块。
- 单线程, 查询间微 sleep (避免占满 IO 把实盘库/采集器拖慢)。
- **先小样本验证** (5-10 个币 / 1 个月) 跑通管线 + 看信号方向, 再放大到全样本。

---

## 4. 实验设计 (Step 1 → Step 5)

### Step 1 — 构建干净面板 + 滚动分位 (基础设施)
1. 流式读 `premium_5m`, 清洗 (剔 0、剔 |p|>3、剔 zero率>90% 的币)。
2. 对每个币按 `open_time_ms` 排序, 计算 **trailing 滚动分位** (窗口候选: 过去 30 天, 即 ~8640 根 5m bar)
   → 得到每个 (币, 时刻) 的 `premium_pctile ∈ [0,1]`。**只用过去数据 → 无前视**。
   - 同时存**横截面分位** (同一时刻所有币里的相对排名) 作为备选信号 (拥挤是相对的)。
3. 流动性筛: join `metrics_5m.sum_oi_value` / klines quote vol, 标记每个币每时刻是否"可成交" + 滑点档。
4. 对齐 forward return: 信号 bar t → 进场 bar t+1 open → 持有 H 后 exit。用 `klines_1h` (或按 H 选 5m/1h/4h) 取 open/close。
5. **产出**: `panel.parquet` 或分块 npz (symbol, ts, premium_pct, premium_pctile, xs_pctile, liq_tier, slippage, fwd_ret_1h/4h/12h/24h)。
6. **小样本先验** (BTC+ETH+5妖币 / 1 个月) 跑通, 人工核对几条信号方向对不对。

### Step 2 — 单变量 carry/反转信号扫描 (dev 区, walk-forward)
对每个 (信号定义 × 分位阈值 × 持有期 × 币池) 组合, 测 fade 方向 PnL:

- **信号定义**: ①trailing premium 分位 ②横截面 premium 分位 ③premium 绝对值 (百分点) ④funding 分位 (辅, dev only)
- **分位阈值**: 极端正 {p90, p95, p99} → 做空; 极端负 {p10, p5, p1} → 做多。也测对称双边。
- **持有期 H**: {1h, 4h, 8h, 12h, 24h, 48h} (carry thesis 偏长, 反转 thesis 偏短, 都测)
- **币池**: 全 perp / 大币 (top 流动性) / 妖币 (行为指纹, 复用 round 的 prior_pumps 定义或用 vol/换手代理) — **分开统计** (用户要求横跨币种)
- **记账分离**: 价格 PnL 与 funding carry 现金流分别记, 报告里拆开 (看 alpha 到底来自回归还是 carry)。
- 每个组合在 **walk-forward 折** (dev 区切 N 段, 逐段 out-of-sample) 上看符号是否一致。

### Step 3 — 基线对照 (避免假阳性)
- **随机进场基线**: 同币池、同持有期、随机时刻进场同方向 → 信号必须显著超随机。
- **buy&hold 基线**: 同期单纯持有 (多/空)。
- **always-on carry 基线**: 不看分位, 永远持 carry 方向 → 看极端分位是否真比"永远 carry"强。

### Step 4 — 组合 / 稳健化 (仅对 Step 2-3 存活的信号)
- 若单变量存活: 加 1-2 个**独立维度**确认 (如 premium 极端 + OI 上升 = 拥挤确认; premium 极端 + 横截面也极端)。
  遵守"每个 filter 必须独立贡献证据, 不冗余"。
- 参数稳健性: 阈值 / 窗口 / 持有期小幅扰动, 看 PnL 是否平滑 (非尖峰 = 非过拟合)。

### Step 5 — Holdout 最终揭晓 (一次性)
- 取 dev 区选出的**最多 3 个**最稳信号, 在封存的 **35 天 holdout** 上**只跑一次**。
- 扣全部成本后仍正 + 符号与 dev 一致 → 标 PASS; 否则诚实标 FAIL。
- funding 信号因 holdout 仅 5 天 → 不做 holdout 验收, 仅报 dev 结论。

---

## 5. 成本模型 (与既有 round7/8 口径一致)

```
往返手续费: 0.14% (taker 双边, 复用 round7 常量)
滑点:
  - 大币 (高流动 tier): ~0.04% 单边
  - 妖币 (低流动 tier): 0.8% 单边 (达到 0.8% 即视为不可成交 → 排除该笔)
funding carry: 持有期跨越的每个 8h 结算点 × 该币 funding_rate
  - 反转记账: funding 现金流单独列, 不混入价格 alpha
  - carry 记账: funding 现金流是收益主体
净收益 = 价格 PnL - 手续费 - 滑点 (± funding, 看 thesis)
```

复用 `round8_calibration/calibrate.py` 的 `SLIPPAGE_PCT / FUNDING_PER_8H / MS_PER_MIN`
常量与 `make_splits` 三分逻辑, 但**面板回测器独立实现** (BWE 引擎是事件驱动, 不适配横截面连续信号)。

---

## 6. 交付物

落到 `a04_funding_basis/`:
- `scripts/` — `01_build_panel.py` (清洗+滚动分位+对齐), `02_scan_signals.py` (walk-forward 扫描),
  `03_baselines.py`, `04_holdout.py`
- `results/` — `panel_meta.json`, `scan_dev.jsonl` (每组合一行), `holdout_final.json`
- `reports/` — `REPORT_中文.md` (含: 数据体检表、单位说明、每信号 dev 表、基线对照、holdout 揭晓、
  **诚实结论** alpha 在不在、来自回归还是 carry、可成交性现实评估)

---

## 7. 已知风险 / 预判

- **大概率结果**: premium 极端的币 = 低流动妖币, 滑点 0.8% 很可能**吃掉全部 carry**(BTC funding 才 0.004%/8h,
  小币 funding 高但滑点更高)。**carry 在扣滑点后大概率不可成交盈利** —— 若如此, 诚实报负。
- **反转 thesis** 在大币上 (可成交) premium 极端较少且幅度小, alpha 空间可能很薄。
- **真正可能有货的区**: 中等流动性币 (可成交 + premium 偶尔极端) 的短期反转。Step 2 分币池就是为定位这块。
- 凡结果好 → 先按 §2 泄漏自查四条过一遍。

---

## 8. 待确认 (开跑前)

1. **滚动分位窗口**: trailing-30d 还是 expanding? (默认 trailing-30d, 兼顾自适应与样本量)
2. **妖币币池定义**: 复用既有 prior_pumps 行为指纹, 还是用本库可得的代理 (高 vol / 高换手 / premium 频繁极端)?
3. **持有期网格**是否够 (1h-48h)? carry thesis 是否要测更长 (3d/7d)?

确认后即开 Step 1 (先小样本跑通)。
