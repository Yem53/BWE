---
type: experiment
tags: [round15, ls_positioning, contrarian, long_short_ratio, a09]
created: 2026-05-31
status: wip
priority: med
---

# a09 — 多空比极值 Contrarian (LS positioning) 研究设计

方向负责人独立攻坚。**只读数据、不碰实盘、本机省资源。** 诚实报负=合格,不 p-hack。

## 1. 数据 (全本地只读)
- `binance_futures_aux_archive.sqlite3` 表 `metrics_5m(symbol, ts_ms, sum_oi, sum_oi_value, toptrader_ls, global_ls, taker_ls_vol)`
  - 8 个月 (2025-10-01 → 2026-05-30), 592 币, 36.9M 行, ts_ms 严格落在 5min 边界, LS 列无 null。
  - **关键语义**: `metrics_5m` 的 ts_ms 是 bar **收盘**时刻 → 在 T 标记的指标反映 `[T-5m, T]` 的状态。**进场必须用下一根 bar 开盘 (T+5m open)**,杜绝前视。
  - `toptrader_ls` = 大户/聪明钱持仓多空比 (p50≈1.47);`global_ls` = 散户/全账户多空比 (p50≈2.81, 结构上恒高于大户)。
- `binance_futures_klines_archive.sqlite3` 表 `klines_5m(symbol, open_time_ms, open, high, low, close, volume, ...)`
  - 5min open_time_ms 对齐;640 币 (aux 的超集)。用于前向收益 + ATR 分层。
- 可交易币池 (复用): `round14/tradable_universe.json` — 278 币日均成交额 ≥ $3M。

## 2. 信号家族 (3 族 × 多空)
全部基于 **per-symbol rolling 分位** (用该币自身 trailing 窗口的历史排名),这是最干净的 contrarian 形式,最不易退化成"选币赌注"。同时跑 cross-sectional 作为副镜。

- **F1 global_ls 极值** (散户定位极端):
  - 散户极度看多 (global_ls rolling pct 高) → **做空**
  - 散户极度看空 (global_ls rolling pct 低) → **做多**
- **F2 toptrader vs global 背离** (聪明钱与散户对立):
  - 定义 `div = zscore(toptrader_ls) − zscore(global_ls)` (各自 per-symbol rolling 标准化)
  - div 极高 (大户相对更多 / 散户相对更空) → **做多**
  - div 极低 (大户相对更空 / 散户相对更多) → **做空**
- **F3 LS 快速变化** (velocity):
  - `dglobal = global_ls(T) − global_ls(T−Δ)` (Δ=30m/1h)
  - 散户快速加多 → **做空**;散户快速减多 → **做多**

### "极值"定义 (核心方法论)
- **主**: per-symbol rolling 分位 — 窗口 trailing 7d (2016 根 5m bar),**严格只用 T 之前的数据**。极值阈 = rolling pct ≤ 0.10 或 ≥ 0.90 (副测 0.05/0.95)。
- **副**: cross-sectional rank — 同一 ts_ms 跨币排名 (会混入币身份,仅作对照)。
- 不用静态固定阈 (如 global_ls>4.5):那只是在选币,不是选时刻。

## 3. 进出场机制 (轻量 cohort 法,非 portfolio sim)
不堆 round8 的重型组合引擎。每个信号 = 一个"事件",测该 cohort 的**前向收益分布**。

- **进场**: 信号在 T 触发 → 进场价 = T+5m bar 的 open (下一根)。
- **出场**: 固定持有期 close (多 horizon: 1h / 4h / 12h / 24h)。**不调 TP/SL 网格** — 在噪声进场上叠加调过的出场是 p-hack 陷阱;任务=深挖 entry 极值/背离组合。
- **收益**: `ret = exit_close / entry_open − 1`,做空取负。
- **成本**: 扣 0.14% 往返。yao 层若隐含滑点会 >0.8% (低流动性 bar) 标注"可能不可成交"。
- **方向**: contrarian 规则如上,逐族固定,不搜方向。

## 4. 度量 (cohort 统计,不是组合曲线)
每个 (family × side × tier × horizon × 阈值) 单元:
- n (事件数,去重后), mean_ret, median_ret, win_rate, t-stat (mean/se), 扣成本后 mean。
- **baseline** = 同 tier/同 horizon 的**无条件**前向收益 (随机时刻进场),作为对照基准。
- **edge** = cohort mean − baseline mean,须扣成本仍正、且超 baseline。
- 样本 < 50 → 标注 sparse,不下结论。

## 5. 切分 + 折 (硬纪律)
- **holdout 封存** = ts ≥ 2026-04-20 (最近 40d),全程只在最后揭晓一次。
- **dev** = 2025-11-01 ≤ ts < 2026-04-20 (留 Oct 给 rolling 分位预热)。
- **dev walk-forward 3 折** (连续三等分): 候选须 **3 折同号** (edge 方向一致) 才算 candidate。
- 赢家判定: dev 3 折同号 + 扣成本正 + 超 baseline → 过 holdout (同号 + 扣成本正) → 合格。太好 (win_rate>80% 或 t>8) 先查泄漏。

## 6. 防泄漏
- 下一根 bar 进场 (信号 T → 进场 T+5m open)。
- rolling 分位/zscore 严格只用 T 之前 bar。
- **重叠去重**: 同币的 24h 窗口高度自相关 → 每币每 horizon 做**非重叠**去重 (一个仓位平了才允许下一个计数),报有效独立样本数。
- 前向收益用真实 kline,缺 bar 的事件丢弃。

## 7. 本机资源纪律
- 逐币 streaming 读 (symbol,ts 索引);单线程;币间 micro-sleep。
- 先 5 币 smoke,确认管线 + 量级,再全量 278 币 (tradable 池)。
- 中间产物落 numpy/parquet,避免重复扫库。

## 8. 交付
- 脚本: `ls_common.py` (切分/读库/分层/统计), `build_signals.py` (逐币算 LS 特征 + 前向收益 → 事件表), `build_baseline.py` (无条件 baseline 采样), `evaluate.py` (cohort 统计 + dev 折 + holdout 揭晓 + clustered bootstrap)。
- 结果: `events.npz`, `baseline.npz`, `dev_results.json`, `holdout_results.json`。
- 中文报告: `REPORT_CN.md` — 诚实结论 (噪声也如实报)。

## 9. 跨模型 review 修复记录 (codex, 2026-05-31)
codex 审出 3 个 High + 3 Medium + 1 Low, 全部修复后才跑正式数据 (旧结果作废重跑):
- **[High] 前向收益差 1 根 bar**: 原进场 `op[i+1]` 出场 `cl[i+1+h]` → 持有 (h+1) bar (1h 实为 65min)。改出场 `cl[i+h]` → 恰 h*5min。
- **[High] ATR 分层泄漏未来**: `atr_pct` 分母用 `close[i]` (=bar [T,T+5m] 收盘, T 时刻未知)。改 `close[i-1]` (信号时已观测)。tier 用于候选筛选, 故此泄漏会污染选择。
- **[High] 未校验 5m 连续性**: inner-join 丢缺口后用 `i+1+h` 位移, "1h" 可能跨缺口。加 `ts[i+1]-ts[i]==5m` (进场) 与 `ts[i+h]-ts[i]==h*5m` (路径无缺口) 检查。
- **[Med] rolling_pct 桶边界用全序列 min/max** (含未来/holdout)。改只用最早 min_n 个 finite 值 (warmup-only) 定边界, 超界 clamp (对分位正确)。
- **[Med] 折级 edge 用全 dev baseline** → 削弱 walk-forward。改每折用 `dev{k}` 自己的 baseline。
- **[Med] 多重比较欠控**: ~119 相关 cohort + t-stat 在跨币/时间聚类下非 iid。加 symbol-clustered bootstrap (对 holdout 候选) + 报告显式讨论 FDR。
- **[Low] t-stat 用 gross**: 加 `tstat_edge` (net-minus-baseline 口径)。
