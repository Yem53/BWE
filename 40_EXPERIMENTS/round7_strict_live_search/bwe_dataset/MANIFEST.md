# BWE 数据集清单 (MANIFEST)

> 整理人: Claude | 日期: 2026-05-21 | 时间窗口统一: **2025-11-01 → 2026-05-16 (196 天, 282357 分钟)**
> 所有特征均为 **as-of (无未来函数)**: 只用当前分钟及更早的已收盘数据。

本文件夹 (`bwe_dataset/`) 汇总 BWE 妖币做空策略研究用到的全部数据。下表标注每个文件的内容、形状、来源、对齐方式。

---

## 一、核心数据 (策略回测必需)

### 1. `klines_extended_196d.npz` (541 MB) — K线
| 数组 | 形状 | 类型 | 含义 |
|------|------|------|------|
| `klines` | (200, 282357, 6) | float32 | 200币 × 282357分钟 × [开,高,低,收,量,成交额] |
| `t_grid` | (282357,) | int64 | 每分钟的 UTC 时间戳 (毫秒) |
| `syms` | (200,) | str | 币名 (与 symbols json 一致) |

- **来源**: Binance 现货/期货 1分钟K线 (sqlite + Binance Vision 月度归档拼接)
- **分辨率**: 1 分钟

### 2. `features_strict_extended_196d.npz` (1174 MB) — 入场特征 (as-of)
10 个特征, 各 (200, 282357) float32 (eligible 为 bool):

| 特征 | 含义 | 计算 (全部用上一根 t-1, 防泄漏) |
|------|------|------|
| `atr_pct` | ATR/价格 (波动率) | 14周期 ATR ÷ 收盘 |
| `ret_60m` | 过去60分钟收益 | (c[t-1]-c[t-61])/c[t-61] |
| `ret_5m` | 过去5分钟收益 | (c[t-1]-c[t-6])/c[t-6] |
| `rsi` | RSI(14) | 标准 RSI |
| `vol_zs` | 成交量z分 | (v[t-1]-均值)/标准差 (滚动) |
| `taker_ratio` | 主动买盘占比 | taker_buy_vol / total_vol |
| `body_ret` | 实体涨跌 | (c[t-1]-o[t-1])/o[t-1] (负=阴线) |
| `upper_wick` | 上影线占比 | (h[t-1]-实体顶)/c[t-1] |
| `pullback` | 距近期峰值回落% | (c[t-1]-滚动最高)/最高 (负值) |
| `eligible` | 是否可交易 | 上市且数据完整 |

### 3. `symbols_extended_196d.json` — 币名列表
- 200 个妖币 (USDT 永续)。**注意: 不含 BTC/ETH** (只有 ETHFIUSDT 这种衍生币)。

---

## 二、新增数据 (2026-05-21 抓取, 用于破 61% 胜率上限)

### 4. `oi_ls_metrics_196d.npz` ⭐ — 持仓量 + 多空比 (本次新抓)
> **来源**: Binance Vision **daily metrics 归档** (`/futures/um/daily/metrics/{SYM}/`)
> 实时 API 只有30天, **但 Vision 历史归档有完整196天** (一天一个 zip 拼成)。
> **分辨率**: 原始 5 分钟级 → 前向填充对齐到 1 分钟网格, **滞后 5 分钟防泄漏 (as-of)**。

| 数组 | 形状 | 含义 | 策略直觉 |
|------|------|------|----------|
| `sum_open_interest` | (200, 282357) | 持仓量 (合约张数) | OI 绝对水平 |
| `sum_open_interest_value` | (200, 282357) | 持仓量 (USD) | OI 美元价值 |
| `oi_chg_60m` | (200, 282357) | 过去60分钟OI变化% | ⭐ 价涨+OI涨=新多进场(可fade); 价涨+OI降=逼空(危险) |
| `ls_toptrader` | (200, 282357) | 大户多空持仓比 | ⭐⭐ 聪明钱在追多还是反手空 |
| `ls_global` | (200, 282357) | 全市场多空账户比 | 散户情绪 |
| `taker_ls` | (200, 282357) | 主动买卖量比 | 买卖力 (metrics自带, 区别于klines的taker_ratio) |
| `t_grid` | (282357,) | 分钟时间戳 | 与 klines 对齐 |

- **覆盖率**: **91.7% 的格子有 OI 数据, 199/200 币有数据** (抓取 36147 文件成功, 3056 个404=新币上市前, 197网络错误)。早期未上市的妖币那段为 NaN, 入场时会被自动跳过。

### 5. `btc_regime_196d.npz` (246 KB) — BTC 大盘环境
> **来源**: Binance Vision BTCUSDT 1h 期货K线。**已测试: 对本策略 holdout 无效** (见 analyze_btc_regime.py)。保留供参考/未来组合用。

| 数组 | 形状 | 含义 |
|------|------|------|
| `open_ms` | (4728,) | 小时时间戳 |
| `close, ret_4h, ret_24h, ret_7d, vs_sma7, rsi, rvol_24h` | (4728,) | BTC 各 regime 指标 |

---

## 三、旧数据 / 辅助 (保留备查)

### 6. `oi_funding_data_30d.npz` — 旧版 OI (仅30天, 来自实时API)
- `oi` (200, 8640) 5分钟级 + `funding` (200,100,2)。**已被 #4 取代** (196天版)。保留作对照。

### 7. `bwe_events.npz` — BWE 电报信号 (⚠️ 当前为空, 0 条)
- 原始 BWE 论文用电报当 attention pointer。这套搜索未接入。需从 `/Users/ye/Desktop/Telegram/*/result.json` 重新解析。**待办**。

---

## 四、时间切分协议 (所有验证统一)

```
TRAIN   : 2025-11-01 → 2026-02-26   (118天, 搜参数, in-sample)
〰️embargo 240分钟
DEV     : 2026-02-26 → 2026-04-06   (39天,  验证1, out-of-sample)
〰️embargo 240分钟
HOLDOUT : 2026-04-07 → 2026-05-16   (39天,  验证2, 从未见过)
```
切分由 t_grid 按 60%/20%/20% + 240分钟隔离带算出。**唯一有效性标准 = holdout 提升。**

---

## 五、配套代码 (在上级目录)

| 文件 | 用途 |
|------|------|
| `loop_search_framework.py` | 评估引擎: load_data / build_entry_mask / simulate_portfolio |
| `loop_search_r28_higher_freq.py` | evaluate_on_range + tier_s 阈值 |
| `advanced_exit_engine.py` | 出场模拟 (tp/sl/time_stop/trailing) |
| `fetch_oi_metrics_196d.py` | 本次 OI 抓取脚本 (Vision daily metrics 模板) |
| `search_oi_features.py` | OI/多空比/广度 特征消融搜索 |
| `R28_FINAL_global_optimum.json` | 当前冠军 Champion C/D 配置 |

## 六、当前冠军基线 (要打败的)
Champion C: 做空, ret60∈[3.5,10]×ATR + vol_zs∈[1,3.2] + 回落≥4% + RSI≥70 + taker≤0.5 + 阴线 + atr≥0.3%; 出场 tp=4×ATR/sl=2.8/200分钟。
**holdout: 60% 胜率 / +150% / 43笔。** 全程196天: 60%/+329%/108笔/最大回撤1.3%。
