# Codex Goal-Mode 优化交接文档 — BWE 妖币做空策略 (R28)

> 给 Codex 的自主优化任务书。作者: Claude (2026-05-21)。
> **在动手前必读全文,尤其是第 2 节「铁律」和第 6 节「已证伪死路」—— 否则你会浪费算力刷 train 海市蜃楼。**

---

## 1. 目标 (GOAL — goal 模式的成功判据)

在严格 3-split 协议下,找到一条策略**在 holdout(从未见过的数据)上**超过现有冠军 Champion C:

- **必达**: holdout WR ≥ 60% AND holdout sum ≥ +150% AND holdout n ≥ 40,同时 train + dev 也通过 strict Tier S(见第 5 节)
- **加分**: 找到一条与 Champion C **月度收益相关性 < 0.6** 的**不同类型**策略(真正能分散风险的第二条腿)

**如果搜不到 → 不算失败。** 严格证明「现有特征集已收敛、61% WR 是上限」同样是有价值的交付。**禁止为了"有结果"而上报只在 train 上变好的配置。**

---

## 2. 铁律 (THE IRON LAW — 违反则整个任务作废)

1. **唯一有效性标准 = holdout 提升。** 任何候选必须分别报告 train / dev / holdout 三段的 WR + sum + n。**只有 holdout 也变好才算数。** train 变好 / dev 变好都不算。
2. **必须用第 5 节的精确切分** (60/20/20 + 240分钟 embargo),边界由 t_grid 算出,不许改比例、不许去掉 embargo。
3. **所有特征必须 as-of (无未来函数)**: 只能用 `close[t-1]` 及更早,不能用 `close[t]`。现有 features 已经是 as-of(用 `np.roll(x,1)` 即上一根)。新加特征必须遵守同样规则,否则结果全是泄漏的假象。
4. **报告必须含样本量。** holdout 只有 ~43 笔,dev ~22 笔。任何 n<10 的"高胜率"都是噪声,直接忽略。
5. **滑点 + 资金费已内置** (SLIPPAGE_PCT=0.001 单边往返0.1%, FUNDING_PER_8H=0.0001)。不许为了好看把它们去掉。

> 反面教材(我亲测的过拟合陷阱): 候选 `ret60_atr_max≤6` 在 train 上 WR 从 61%→**75%** 看着像金矿,拿到 holdout 上**原地不动 59%** 还少赚一半。这就是不报 holdout 会犯的错。

---

## 3. 要打败的基线 — Champion C

```python
CHAMPION_C = {
    "side": "short",
    "entry": {
        "ret60_atr_min": 3.5, "ret60_atr_max": 10.0,   # 过去60分钟涨幅 = 3.5~10倍ATR
        "vol_zs_min": 1.0,    "vol_zs_max": 3.2,        # ★成交量z分1~3.2σ (砍极端放量是核心alpha)
        "pullback_pct_max": -0.040,                     # 已从峰值回落≥4%
        "rsi_min": 70,                                  # 超买
        "taker_max": 0.50,                              # 主动买盘≤50% (买力衰竭)
        "body_neg_max": -0.001,                         # 上一根收阴
        "atr_pct_min": 0.003,                           # 最低波动率(滤掉死币)
    },
    "exit": {"exit_type": "single", "tp_atr": 4.0, "sl_atr": 2.8,
             "time_stop_min": 200, "tp_confirm_bars": 1},
}
```

**基线 3-split 成绩** (这就是要超越的):
| 段 | WR | sum | n |
|----|----|----|----|
| train (118天) | 58% | +145% | 46 |
| dev (39天) | 63% | +43% | 22 |
| **holdout (39天)** | **60%** | **+150%** | **43** |

全程 196 天: 108 笔, 60% WR, +329%, 均盈+10%/均亏-7.5%, 最大回撤1.3%(5%仓位), 3.9笔/周。

---

## 4. 数据位置与类型

工作目录: `/Volumes/T9/BWE/40_EXPERIMENTS/round7_strict_live_search/`

### 主力数据 (196天, 2025-11-01 → 2026-05-16)
| 文件 | 内容 | 形状/类型 |
|------|------|-----------|
| `data/klines_extended_196d.npz` | K线 | `klines`(200, 282357, 6)=币×分钟×[O,H,L,C,V,?]; `t_grid`(282357,)=分钟时间戳ms |
| `data/features_strict_extended_196d.npz` | 已算特征(as-of) | 10个: atr_pct, rsi, ret_60m, ret_5m, upper_wick, body_ret, vol_zs, taker_ratio, pullback, eligible。各 (200, 282357) |
| `data/symbols_extended_196d.json` | 币名列表 | 200 个 (妖币宇宙, 无BTC/ETH) |

### 辅助数据 (可选, 用于扩展新特征)
| 文件 | 内容 | 注意 |
|------|------|------|
| `data/btc_regime_196d.npz` | BTC大盘regime(我已抓) | 4728根1h: ret_4h/24h/7d, vs_sma7, rsi, rvol_24h。**已测过,无holdout效果(第6节)** |
| `data/oi_funding_data.npz` | OI持仓量+资金费率 | ⚠️只30天(200, 8640)5分钟级 — 来自**实时API(限30天)**。扩到196d要走Vision daily metrics(见下) |
| `data/bwe_events.npz` | BWE电报信号 | ⚠️**空的**(0条)。原始BWE论文用电报当attention pointer, 这套搜索没接 |

### 外部数据源 (扩展用) — 已实测确认
- **Binance Vision** (唯一可用, fapi/api 被墙): `https://data.binance.vision/data/futures/um/...`
  - K线: `/{monthly,daily}/klines/{SYM}/1h/` 或 `/1m/` (monthly截上月, 当月用daily)
  - **⭐历史OI/多空比 metrics**: `/daily/metrics/{SYM}/{SYM}-metrics-{YYYY-MM-DD}.zip`
    - ✅ **已实测: 整个196天窗口(2025-11~2026-05)全部HTTP 200, 连妖币(PLAYUSDT等)都有**
    - ❌ **没有monthly打包(404)** — 只能一天一个daily zip拼 (196天 × 200币 = ~39200文件, 各~35KB)
    - CSV字段(5分钟级, 288行/天, as-of天然滞后5分钟): `create_time, symbol, sum_open_interest(持仓量张), sum_open_interest_value(USD), count_long_short_ratio(全市场多空账户比), sum_toptrader_long_short_ratio(★大户多空持仓比), sum_taker_long_short_vol_ratio(主动买卖比)`
    - **⭐⭐重点**: `sum_toptrader_long_short_ratio`(大户在追多还是反手做空) + OI变化率(价涨OI不涨=虚火) 是最可能破61%上限的新特征
    - 缩规模技巧: 可只抓策略实际成交的~70个币, 而非全200个
  - 参考 `fetch_btc_regime.py` 的抓取+解析+as-of对齐模板 (改URL和字段即可)

---

## 5. 评估引擎 (直接复用, 别重写)

```python
import loop_search_framework as f
from loop_search_r28_higher_freq import evaluate_on_range, tier_s_train, tier_s_dev, tier_s_holdout

klines, t_grid, syms, fd = f.load_data(variant="_extended_196d")
features = {k: fd[k] for k in fd.files}
eligible = features["eligible"]; atr_pct = features["atr_pct"]

# 精确切分 (60/20/20 + 240分钟 embargo)
MS=60_000; EMB=240*MS
fs, fe = int(t_grid[0]), int(t_grid[-1]); span = fe-fs
train_end  = fs + int(span*3/5)          # 2025-11-01 → 2026-02-26
dev_start  = train_end + EMB
dev_end    = fs + int(span*4/5)          # 2026-02-26 → 2026-04-06
hold_start = dev_end + EMB               # 2026-04-07 → 2026-05-16

# 评估一条策略在某区间
r = evaluate_on_range(strategy, klines, atr_pct, eligible, t_grid, syms, features, fs, train_end)
# 返回 dict: port_n, port_sum_pct, port_wr_pct, traded_syms, top_share_pct, unique_days
```

**入场逻辑**: `f.build_entry_mask(side, entry_dict, ...)` (loop_search_framework.py:96)。要加新特征,在这里加一行过滤,并把新特征数组塞进 `features` dict。

**出场引擎**: `advanced_exit_engine.simulate_combo_advanced(...)` — 已支持 tp_atr/sl_atr/time_stop_min/tp_confirm_bars/breakeven/trailing。

**组合层**: `f.simulate_portfolio` — max_concurrent=3, cooldown=60min, 一币一单。

### Strict Tier S 阈值 (loop_search_r28_higher_freq.py:91-102)
```python
tier_s_train:   WR≥55, sum≥90, traded_syms≥30, top_share≤20%, unique_days≥18
tier_s_dev:     WR≥55, sum≥30, traded_syms≥10, top_share≤25%, unique_days≥6
tier_s_holdout: WR≥55, sum≥30, traded_syms≥10, top_share≤25%, unique_days≥6
```
(iter脚本里会把 f.THRESH_* 调低做初筛, 但最终 winner 必须过上面这套真阈值)

---

## 6. 已证伪的死路 (别重走, 省算力)

经 57 轮迭代 + 专项消融,以下**全部在 holdout 上无效**,有 3-split 证据:

| 试过的方向 | 结果 |
|-----------|------|
| `hours` 时段过滤 | 用户明令禁止(巧合性大),且消融证明是噪声 |
| `upper_wick`(上影线) | train微升, holdout无效/有害 |
| `ret5_atr`(近5分钟) | 全部失败train |
| 收紧 rsi/taker/body/pullback | 全是train假象, holdout不成立 |
| `vol_zs_max` 调到 2.5/2.7 | 太严, 砍掉太多winner, holdout WR反降 |
| `ret60_atr_max≤5/6`(只打小涨) | **经典陷阱**: train 75%, holdout 59%不变 |
| **BTC大盘regime** (24h涨跌/vs均线/RSI/波动) 11个过滤器 | 全部 holdout 失败。"BTC跌时做空" train65%→holdout50% |
| 时间/月份 regime | 亏损不扎堆, 无可用规律 |

**核心教训**: 盈利单 vs 亏损单在**进场那一刻所有现有特征上几乎完全相同**(ret60/vol_zs/rsi/taker/pullback 中位数都一样)。决定输赢的是**进场后几分钟妖币自身走势**(最后血崩前是否还有一拉),**不在现有特征里**。→ 现有特征集 61% WR 是上限,纯调参已收敛。

---

## 7. 真正有料的方向 (按性价比排序)

**纯参数搜索价值≈0(已收敛)。要破61%上限,必须加信息维度:**

1. **⭐⭐扩展 OI + 大户多空比到196天** (最有希望, 数据已确认可得): 从 Vision `/daily/metrics/{SYM}/` 抓 (196天×币 daily zip), 算 as-of 特征:
   - 「OI变化率」: 价涨但OI不涨 = 逼空/虚火(该做空); 价涨OI也涨 = 真买盘(别空)
   - 「大户多空比变化」(`sum_toptrader_long_short_ratio`): 暴涨时大户在追多还是反手空? 这最可能就是那个"决定输赢但现有特征看不到"的信息
   - **这正是BWE原始论文核心(OI&Price异动)。** metrics是5分钟级, 对齐到分钟网格时用前向填充+滞后1根防泄漏。
2. **全市场breadth(广度)**: 用现有200币算「同期多少币在暴涨」。普涨(系统性) vs 个别异动(可做空)可能可分。**不需要抓新数据,现有klines就能算 → 性价比最高,先试这个**。
3. **资金费率特征**: 极端正funding = 多头过热 = 做空更优? Vision metrics不直接含funding rate, 需从 `/futures/um/daily/fundingRate/` 或 funding 专用归档抓。
4. **接入BWE电报信号** (`bwe_events.npz`现在是空的): 原始论文用电报当attention pointer。需从 `/Users/ye/Desktop/Telegram/*/result.json` 解析重灌。
5. **不同策略类型**(为真分散): long侧 / 均值回归 / 多日波段。注意: long侧在30天窗口测过结构性无alpha, 需先扩数据。

---

## 8. 诚实的期望管理

- 最可能的结果: **确认收敛** —— 现有特征下找不到显著超越 Champion C 的配置。这本身是有价值的负面结论。
- 真突破只可能来自**第7节的新特征**(尤其是 OI/breadth),而不是 entry/exit 参数的进一步网格搜索。
- 如果 Codex 报告"找到更好的",**必须附 train/dev/holdout 三段数字 + n + 与Champion C的月度相关性**。没有这些 = 不可信。

---

## 9. 快速上手命令

```bash
cd /Volumes/T9/BWE/40_EXPERIMENTS/round7_strict_live_search
# 参考现有迭代脚本结构:
#   loop_search_r28_iter55_min_explore.py   (参数搜索模板)
#   analyze_losers.py / analyze_btc_regime.py (消融+holdout验证模板)
#   fetch_btc_regime.py                      (Binance Vision抓取+as-of特征模板)
# 冠军配置: R28_FINAL_global_optimum.json
# 累计winner: r28_winners_cumulative.json (310条, 同一family)
```

环境: macOS, python3 (numpy装好), matplotlib(--break-system-packages已装)。Binance走 Proton VPN(日本/加拿大节点), 只有 data.binance.vision 通。
