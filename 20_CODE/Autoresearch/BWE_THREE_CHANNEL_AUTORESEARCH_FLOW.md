# BWE 三频道 AutoResearch 触发式交易研究优化流程

> 版本：2026-04-24  
> 适用范围：BWE 三个高频触发频道：OI&Price、pricechange、Reserved6  
> 目标：用 Karpathy-style AutoResearch 的“假设 → 实验 → 验证 → 保留/淘汰 → 复盘”循环，建立 BWE 专用的触发式交易策略工厂。  
> 硬边界：只做历史回测和 paper shadow；不改 live、不重启 live、不读取 secrets、不下单。

---

## 0. 总结版

BWE AutoResearch 不应该被设计成“自动找历史最优参数后直接上线”，而应该是：

```text
三频道历史消息 + 1m/5m/1h 行情 + live/paper journal
→ 标准化事件
→ 事件研究 event study
→ 生成候选开仓/过滤/退出/风控
→ walk-forward + 成本 + 稳定性 + journal penalty 验证
→ 输出 paper shadow 候选
→ 每个 active strategy 20+ clean complete 后再复核是否进入 live
```

三频道分工：

```text
OI&Price    = 主策略源：OI 拥挤、踩踏、反转、延续，优先 short。
pricechange = 高频机会/噪音源：重点找过滤器、二次信号、burst bucket，先降噪。
Reserved6   = 极端行情源：急涨 fade short、急跌 continuation short、跨频道确认。
```

第一阶段只做：

```text
固定 entry family → 自动搜索 filter + exit + risk → 排 paper 候选
```

第二阶段再做：

```text
受限新开仓策略生成
```

第三阶段再做：

```text
三频道 cross-confirm 组合 alpha
```

---

## 1. 硬安全边界

AutoResearch agent 只能在 sandbox 里工作。

### 允许读取

- `/Users/ye/Desktop/Telegram/` 下三频道 Telegram Desktop exports
- `/Users/ye/.hermes/research/bwe_three_channel_fullrun3/` 已生成的回测产物
- `/Users/ye/.hermes/research/bwe_next_optimization_20260424/` 现有策略评分与 journal gate
- `/Users/ye/.hermes/research/binance_futures_1m_collector_runtime/binance_futures_1m.sqlite3` 的 1m kline 数据
- 脱敏后的 live/paper journal

### 允许写入

- `/Users/ye/.hermes/research/bwe_autoresearch_three_channel_*/`
- `/Users/ye/Desktop/GitHub/Autoresearch/` 下的 BWE 研究说明文档
- 自己生成的 candidate config、scoreboard、reject log、report

### 禁止

```text
- 禁止读取/输出 API key、token、secret
- 禁止修改 live autotrader 配置
- 禁止修改 launchd/cron/PM2 live 任务
- 禁止调用 Binance/OKX 下单或撤单 endpoint
- 禁止自动切换 live 策略
- 禁止把历史最高收益候选直接推荐 live
```

### live 晋级规则

任何候选必须先经过：

```text
历史样本外验证
→ paper shadow
→ 每个 active strategy 20+ clean complete
→ journal penalty 复核
→ 人工确认
```

---

## 2. 数据层

### 2.1 原始三频道

本地 Telegram Desktop export 优先：

```text
pricechange:
/Users/ye/Desktop/Telegram/方程式价格异动监测_history/result.json

OI&Price:
/Users/ye/Desktop/Telegram/方程式OI&Prce异动_history/result.json

Reserved6:
/Users/ye/Desktop/Telegram/方程式重大行情提醒 Important Price Alerts Only_history/result.json
```

### 2.2 已有 fullrun 产物

优先复用：

```text
/Users/ye/.hermes/research/bwe_three_channel_fullrun3/events.parquet
/Users/ye/.hermes/research/bwe_three_channel_fullrun3/forward.parquet
/Users/ye/.hermes/research/bwe_three_channel_fullrun3/event_hourly_2h_pre_48h_post.parquet
/Users/ye/.hermes/research/bwe_three_channel_fullrun3/strategy_grid.csv
/Users/ye/.hermes/research/bwe_three_channel_fullrun3/strategy_summary.csv
/Users/ye/.hermes/research/bwe_three_channel_fullrun3/report.md
```

### 2.3 下一轮优化产物

```text
/Users/ye/.hermes/research/bwe_next_optimization_20260424/next_round_research_report.md
/Users/ye/.hermes/research/bwe_next_optimization_20260424/journal_calibration_and_sample_gate.csv
/Users/ye/.hermes/research/bwe_next_optimization_20260424/candidate_scores_with_journal_penalty.csv
```

### 2.4 1m kline DB

```text
/Users/ye/.hermes/research/binance_futures_1m_collector_runtime/binance_futures_1m.sqlite3
表：klines_1m
```

用途：

```text
- MFE/MAE
- 先止盈/先止损保守路径模拟
- slippage/fill quality 估计
- paper/live 理论 exit 对比
```

---

## 3. 标准化事件 schema

每条事件必须统一成以下字段：

```yaml
event:
  source_channel: OI&Price | pricechange | Reserved6
  post_id: string
  event_ts_utc: datetime
  symbol_raw: string
  canonical_symbol: string
  exchange: Binance_USDM | OKX_SWAP | unknown
  event_family: oi_price | pricechange | reserved6
  event_type: pump | crash | mixed
  direction_hint: up | down | unknown
  raw_text: string
  parsed_fields: object
  tradable_at_event: bool
  marketcap: float | null
  quote_volume_24h: float | null
  liquidity_bucket: q0-q100 | null
  pretrend:
    pre3m_return: float
    pre5m_return: float
    pre30m_return: float
    pre2h_return: float
    trend_state: trend_up_all | trend_down_all | short_up_long_down | short_down_long_up | mixed
  regime:
    btc_pre30m: float
    eth_pre30m: float
    regime_state: risk_on | neutral | risk_off
  burst:
    same_symbol_count_5m: int
    burst_seq_5m: int
    burst_count_5m: int
  cross_confirm:
    confirm_before_5m_oi: bool
    confirm_after_5m_oi: bool
    confirm_before_5m_pricechange: bool
    confirm_after_5m_pricechange: bool
    confirm_before_5m_reserved6: bool
    confirm_after_5m_reserved6: bool
    confirm_count_5m: int
```

---

## 4. 候选策略 schema

所有 AutoResearch 生成的策略必须符合这个结构，不能自由写不可验证的文字策略。

```yaml
strategy_candidate:
  id: string
  name: string
  hypothesis: string
  source_channels:
    - OI&Price | pricechange | Reserved6
  entry:
    direction: long | short
    event_family: oi_price | pricechange | reserved6 | cross_channel
    trigger:
      conditions: []
      delay_seconds: 0 | 10 | 30 | 60 | 180
  filters:
    liquidity: {}
    marketcap: {}
    pretrend: {}
    early_confirmation: {}
    burst: {}
    cross_channel: {}
    regime: {}
    cooldown: {}
  exit:
    family: fixed_tp_sl | prove_then_hourly_state | hybrid_tp_hourly_state | partial_tp_runner | time_stop | short_event_hold
    params: {}
  risk:
    one_coin_one_position: true
    max_hold_minutes: int
    position_size_mode: paper_only_fixed_notional | risk_scaled
    max_concurrent_group: int | null
  validation:
    min_sample: int
    split_policy: chronological_walk_forward
    cost_model: taker_fee_plus_slippage
    required_reports:
      - summary
      - split_table
      - reject_reason
```

---

## 5. AutoResearch 实验循环

每一轮只能做一个清晰假设。

```text
1. 读取上一轮 scoreboard + reject_log + experiment_journal
2. 选择一个假设，例如：
   “OI price down + OI up 在 high liquidity 且 early 5m 不反弹时，short continuation 更稳”
3. 生成 5-30 个候选 config，不直接改 live code
4. 运行回测/验证器
5. 计算 robust_score
6. 如果通过 hard gates：放入 promote_to_paper 或 watchlist
7. 如果失败：写 reject_log，记录失败原因
8. 生成中文 report
9. 下一轮只基于结果做一个新变化
```

保留/淘汰规则：

```text
通过：稳定性评分高于 baseline，且不靠单个极端赢家。
淘汰：样本少、p25/p10 差、时间切分失效、费用压力后失效、单币种贡献过大、journal penalty 后失效。
观察：方向合理但样本不足，进入 need_more_data。
```

---

## 6. 三频道专属研究流程

# 6.1 OI&Price：主策略源

## 定位

OI&Price 是三频道中最适合做结构化策略的源，因为它同时包含价格变化和持仓变化。

核心研究方向：

```text
OI 拥挤
OI 踩踏
过热反转
下跌延续
去杠杆反弹
```

## 四象限拆分

### A. price up + OI up

含义：上涨中加仓，可能是追涨拥挤。

优先方向：

```text
short fade / reversal
```

候选：

```text
oi_hot_pump_reversal_short
oi_ultrahot_pump_reversal_short
oi_price_up_oi_up_reversal_short
```

### B. price down + OI up

含义：下跌中 OI 增加，可能是踩踏/拥挤继续。

优先方向：

```text
short continuation
```

候选：

```text
oi_overcrowded_crash_follow_short
oi_crash_follow_short
oi_highliq_riskoff_crash_follow_short
```

### C. price up + OI down

含义：可能是空头回补导致的拉升，持续性未必强。

优先方向：

```text
谨慎 fade short，只做样本研究
```

候选：

```text
oi_price_up_oi_down_reversal_short
oi_short_squeeze_exhaustion_short
```

### D. price down + OI down

含义：去杠杆/平仓下跌，可能反弹，也可能继续弱。

优先方向：

```text
bounce long 只观察，不优先 live
```

候选：

```text
oi_flush_bounce_long
oi_trend_down_all_bounce_long
```

## 搜索字段

```text
oi_change_pct: 3%, 5%, 8%, 10%, 15%, 20%
price_change_3600s_pct: ±3%, ±5%, ±8%, ±10%, ±15%
oi_usd bucket
oi_ratio_pct: 5%, 10%, 15%, 20%
24h_price_change bucket
marketcap bucket
quote_volume_24h bucket
pre2h_return bucket
early_5m_return gate
BTC/ETH regime
same_symbol cooldown
```

## Exit 搜索重点

第一轮聚焦 OI short：

```text
profit-first exits:
E072 / E074 / E076

stability-first exits:
E027 / E043 / E098
```

比较维度：

```text
mean_net_pct
median_net_pct
p25_net_pct
p10_net_pct
max_drawdown
longest_losing_streak
fee/slippage stress
outlier removal
journal penalty
```

## OI&Price 第一轮目标

```text
找出 2-4 个 OI short paper A/B 候选。
默认不扩大 long。
```

---

# 6.2 pricechange：高频机会/噪音源

## 定位

pricechange 消息最多，机会最多，但噪音也最大。它第一阶段的任务不是扩大 live，而是降噪和筛选。

核心研究方向：

```text
二次信号
burst bucket
early 5m gate
高量能 bucket
same-symbol cooldown
pump continuation vs overheat fade
crash bounce vs crash continuation
```

## pump 策略

候选：

```text
pc_pump_cont_long
pc_pump_fade_short
pc_bigmove_pump_fade_short
pc_second_signal_cont_long
pc_third_plus_overheat_short
pc_highliq_riskon_cont_long
```

关键拆分：

```text
first signal: 首次异动，方向不确定
second signal: 可能是真动量
third_plus burst: 可能过热，也可能强趋势，必须分 bucket
```

## crash 策略

候选：

```text
pc_crash_cont_short
pc_crash_bounce_long
pc_bigmove_crash_cont_short
pc_crash_bounce_long_preflush
pc_3s_crash_bounce_long
```

当前原则：

```text
pc_crash_bounce_long 先做过滤，不升风险。
pc_pump_cont_long 先解决 orphan/missing 和 live 样本不足。
pc_second_signal_cont_long 做 paper 观察。
```

## 搜索字段

```text
lookback_seconds: 3s vs 60s
price_change_pct magnitude
active quote volume bucket
early_5m_net gate: > -2%, > -1%, > 0%, > 0.5%
burst_seq_5m: 1, 2, 3+
burst_count_5m
same_symbol_count_5m
pre3m/pre5m/pre30m trend
marketcap bucket
BTC/ETH regime
alt/no_alt
same-symbol cooldown
```

## Exit 搜索重点

pricechange 不优先长持仓 fat-tail exit。第一阶段更适合：

```text
1m/3m/5m/10m/15m short event holds
quick fail exit
partial TP
time stop
early proof gate
```

## pricechange 第一轮目标

```text
找出哪些 pricechange long 可以保留，哪些必须过滤；
找出 second signal 和 third-plus burst 是否能转成更稳的 paper 策略。
```

输出：

```text
pc_long_filter_top.csv
pc_burst_bucket_risk_table.csv
pc_second_signal_candidates.csv
pc_reject_reasons.csv
```

---

# 6.3 Reserved6：极端行情源

## 定位

Reserved6 是重大行情提醒，样本少于 pricechange，但极端程度高，适合研究事件型短线策略和跨频道确认。

核心研究方向：

```text
急涨 fade short
急跌 continuation short
极端行情后的短线反转
Reserved6 + OI/pricechange 交叉确认
```

## pump 策略

候选：

```text
r6_bigmove_pump_fade_short
r6_pump_fade_short
r6_smallcap_pump_fade_short
r6_pump_cont_long
```

优先级：

```text
r6_bigmove_pump_fade_short > r6_pump_cont_long
```

## crash 策略

候选：

```text
r6_bigmove_crash_cont_short
r6_crash_cont_short
r6_bigmove_crash_bounce_long
r6_trend_down_all_bounce_long
```

优先级：

```text
r6_bigmove_crash_cont_short > r6_crash_bounce_long
```

## 搜索字段

```text
price_change_180s threshold: 8%, 10%, 12%, 15%
marketcap bucket
quote_volume bucket
pre30m trend
pre2h trend
BTC/ETH regime
pricechange confirm before/after 5m
OI confirm before/after 5m
same-symbol previous signals
```

## Exit 搜索重点

急涨 fade short：

```text
fast entry
partial TP
runner with hourly deterioration
hard stop if squeeze continues
```

急跌 continuation short：

```text
10s/30s delayed entry
3m/5m/15m short hold
if 5m strong rebound, exit
```

## Reserved6 第一轮目标

```text
验证 extreme move 是否可做 paper short/fade/continuation；
优先找和 OI/pricechange 同币确认后的稳定增强。
```

---

## 7. 三频道 cross-confirm 组合策略

第二阶段以后开始。

### 7.1 pricechange → OI 确认

```text
先 pricechange pump/crash
5m 内 OI&Price 同币确认
```

可能策略：

```text
pricechange pump + OI up = overheat short
pricechange crash + OI up = crash continuation short
```

### 7.2 OI → pricechange 确认

```text
先 OI price down + OI up
随后 pricechange crash
```

可能策略：

```text
踩踏延续 short
```

### 7.3 Reserved6 + pricechange burst

```text
Reserved6 pump + pricechange burst_seq >= 3
```

可能策略：

```text
极端过热 fade short
```

### 7.4 Reserved6 + OI 拥挤

```text
Reserved6 crash + OI up
```

可能策略：

```text
极端下跌 continuation short
```

### 关键要求

cross-confirm 必须区分：

```text
confirm_before_5m
confirm_after_5m
within_5m 但先后顺序未知不能用于实盘假设
```

禁止未来函数：开仓时只能用已经发生的确认事件。

---

## 8. 验证框架

### 8.1 Hard gates

候选必须先过硬门槛：

```text
sample_size 达标
median_net > 0
p25_net 不显著差于 baseline
p10_net 可接受
maxDD 可接受
longest losing streak 可接受
fee/slippage stress 后仍有效
walk-forward 至少多数窗口有效
去掉 top 1% 大赢家后不失效
单币种贡献不过度集中
exchange_position_missing / orphan penalty 后仍可接受
```

### 8.2 样本门槛建议

```text
OI&Price:
- offline promote_to_paper: >=100
- live review: active strategy 20+ clean complete

pricechange:
- offline promote_to_paper: >=300
- filter 子样本 watchlist: >=100
- live review: active strategy 20+ clean complete

Reserved6:
- offline promote_to_paper: >=50-100，视过滤后样本而定
- 小样本只能 need_more_data/watchlist
- live review: active strategy 20+ clean complete
```

### 8.3 切分方式

必须至少包含：

```text
chronological train/validation/test
walk-forward monthly/biweekly windows
symbol holdout
market regime holdout
liquidity/marketcap bucket split
```

### 8.4 成本模型

至少包含：

```text
taker fee
conservative slippage
funding approximation if holding long enough
minimum notional/tradability
1m bar 内先触发止损的保守路径假设
```

### 8.5 Journal penalty

对 live/paper journal 对齐后，加入：

```text
exchange_position_missing penalty
orphan close penalty
entry/exit mismatch penalty
missing fill penalty
untradeable symbol penalty
```

---

## 9. 评分体系

不要按 mean return 单独排序。建议两套榜：

```text
profit leaderboard: 看期望，但只作参考
stability leaderboard: 用于 paper/live 晋级
```

主排序：

```text
1. stability_score
2. median_net_pct
3. p25_net_pct
4. p10_net_pct
5. max_drawdown
6. longest_losing_streak
7. win_rate
8. mean_net_pct
9. journal_penalty
10. deployability
```

建议 robust_score：

```text
robust_score =
  + median_score
  + p25_score
  + p10_score
  + win_rate_score
  + profit_factor_score
  - drawdown_penalty
  - losing_streak_penalty
  - outlier_dependency_penalty
  - fee_slippage_sensitivity_penalty
  - journal_penalty
  - sample_size_penalty
```

输出必须分四类：

```text
promote_to_paper: 可进入 paper shadow
watchlist: 方向有潜力但还不够稳
need_more_data: 样本不足，继续观察
reject: 明确淘汰，并写人话原因
```

---

## 10. 开放式策略发现模式

用户明确希望 AutoResearch 不只优化已知策略参数，也要主动提出更多未知的开仓和退出策略。这里采用“受控开放探索”：允许 agent 创造新策略，但必须落入可验证的策略语法、数据字段和风险边界。

### 10.1 两层研究结构

```text
Layer A：已知策略优化
- 固定已有 entry family
- 搜索 filter / exit / risk 参数
- 目标：快速找到可 paper A/B 的稳健增强

Layer B：未知策略发现
- agent 主动提出新的 entry / exit / filter 组合
- 先做 event study，再做策略回测
- 目标：发现人没有提前枚举到的新模式
```

两层应该并行运行，但晋级标准不同：

```text
已知策略优化：可以较快进入 promote_to_paper
未知策略发现：默认先进入 watchlist/need_more_data，必须更严格验证后才 paper
```

### 10.2 允许 agent 提出的新开仓类型

AutoResearch 可以主动提出以下类型的新 entry，不限于当前手工命名的策略族：

```text
1. 顺势延续 entry
   - pump continuation long
   - crash continuation short
   - OI+price 同向后的延续

2. 反转/fade entry
   - pump fade short
   - crash bounce long
   - overheat reversal short
   - flush rebound long

3. 二次信号 entry
   - first signal 不交易，second signal 才交易
   - second signal continuation
   - second signal failure reversal

4. burst 状态 entry
   - burst_seq=1 视为初动
   - burst_seq=2 视为确认
   - burst_seq>=3 视为过热或强趋势，按 bucket 验证

5. 跨频道确认 entry
   - pricechange 后 OI 确认
   - OI 后 pricechange 确认
   - Reserved6 后 pricechange/OI 确认
   - 必须区分 before/after，禁止未来函数

6. 市场状态 entry
   - risk_on 只做 continuation
   - risk_off 只做 short/fade
   - neutral 缩小样本或只观察

7. 流动性/市值分层 entry
   - 小币高波动策略
   - 大币低滑点策略
   - 高 quote volume 才交易
   - 低流动性只观察或拒绝

8. 延迟确认 entry
   - 0s 立即入场
   - 10s/30s/60s/180s delayed entry
   - early 1m/3m/5m confirmation 后入场
```

### 10.3 允许 agent 提出的新退出类型

AutoResearch 也可以主动提出新的 exit family，不限于 E072/E074/E076/E027/E043/E098，但必须可模拟、可回放、可解释。

允许的 exit family：

```text
1. fixed_tp_sl
   固定止盈止损，适合短线基准。

2. short_event_hold
   1m/3m/5m/10m/15m/30m/60m 固定事件持仓。

3. prove_then_exit
   早期必须证明方向正确，否则退出。

4. prove_then_runner
   早期证明后保留 runner。

5. prove_then_hourly_state
   早期证明后根据 hourly state 恶化退出。

6. partial_tp_runner
   先部分止盈，再用 trailing/hourly 管理剩余仓位。

7. time_decay_target
   初始目标高，时间越久目标越低。

8. ratchet_lock
   盈利越高，保护线逐步上移/下移。

9. volatility_adaptive_exit
   根据事件后 1m/5m 波动自动调止损/止盈。

10. channel_invalidated_exit
   如果反向频道信号出现，退出。

11. cross_confirm_hold_exit
   如果后续同向频道确认出现，延长持仓；否则短持仓退出。

12. left_tail_guard_exit
   专门限制 p10/极端亏损的防守型退出。
```

### 10.4 新策略生成预算

为避免无限乱搜，每轮开放探索设预算：

```text
每轮最多 20-50 个新 entry hypotheses
每个 entry 最多 5-10 个 exit variants
每个组合最多 3-5 个核心 filter variants
每轮必须保留 reject log
连续 2 轮失败的 hypothesis family 暂停
```

推荐比例：

```text
70% 算力：已知高潜力方向的精细优化
20% 算力：受控新策略发现
10% 算力：反常识/探索性假设
```

### 10.5 未知策略的额外晋级门槛

未知策略比已知策略更容易过拟合，所以必须额外检查：

```text
- event study 先显示方向性，不允许直接 strategy grid 反推
- 至少两个时间窗口有效
- 至少多个 symbol 有贡献
- 去掉 top 1% 大赢家后仍然不崩
- 参数邻域稳定，不是单点最优
- long/short 逻辑能用人话解释
- 成本增加 2x 后不完全失效
- 不依赖未来确认字段
```

### 10.6 输出格式新增

开放探索每轮要额外输出：

```text
new_hypotheses.jsonl         # agent 主动提出的新策略假设
new_entry_candidates.jsonl   # 新开仓候选
new_exit_candidates.jsonl    # 新退出候选
discovery_scoreboard.csv     # 未知策略发现榜
neighborhood_stability.csv   # 参数邻域稳定性
hypothesis_reject_log.csv    # 假设级拒绝原因
```

未知策略报告必须单列：

```text
1. 新发现但可解释
2. 历史有效但疑似过拟合
3. 样本不足但值得继续攒
4. 明确拒绝
```

---

## 11. 阶段路线图

## Round 1：固定 entry family，搜索 filter + exit + risk

### OI&Price

```text
主攻：
oi_overcrowded_crash_follow_short
oi_hot_pump_reversal_short
oi_price_up_oi_up_reversal_short

比较：
E072/E074/E076 vs E027/E043/E098

目标：
选出 2-4 个 OI short paper A/B 候选。
```

### pricechange

```text
主攻：
pc_crash_bounce_long 过滤
pc_pump_cont_long 过滤
pc_second_signal_cont_long
pc_third_plus_overheat_short

过滤：
early_5m_net gate
high active quote volume bucket
burst_seq bucket
same-symbol cooldown
pretrend/regime

目标：
降低坏单，不扩大 live。
```

### Reserved6

```text
主攻：
r6_bigmove_pump_fade_short
r6_bigmove_crash_cont_short

目标：
验证极端行情 short/fade/continuation 是否值得 paper。
```

## Round 2：受限新开仓策略生成

只允许使用以下字段：

```text
三频道 parsed fields
pretrend
quote_volume/liquidity
marketcap
burst/repeat
cross-channel confirm
BTC/ETH regime
early 5m confirmation
```

每个新策略必须先有 event study，再进入 strategy backtest。

## Round 3：三频道组合 alpha

重点研究：

```text
pricechange→OI confirmation
OI→pricechange confirmation
Reserved6+pricechange burst
Reserved6+OI crowding
```

---

## 11. 产物目录结构

建议每轮放在：

```text
/Users/ye/.hermes/research/bwe_autoresearch_three_channel_YYYYMMDD/
```

目录：

```text
inputs/
  data_inventory.md
  source_paths.json

configs/
  candidate_schema.json
  metric_contract.json
  search_space_round1.yaml

experiments/
  0001_oi_short_exit_ab/
    candidates.jsonl
    scoreboard.csv
    reject_log.csv
    split_metrics.csv
    report_zh.md
  0002_pricechange_filter/
  0003_r6_extreme_short/

paper_shadow/
  promote_to_paper.yaml
  watchlist.yaml

reports/
  daily_summary_zh.md
  next_round_plan.md
```

---

## 12. 每轮报告格式

中文低噪音格式：

```text
结论：
- 哪些进入 paper
- 哪些拒绝
- 哪些继续攒样本

Promote to paper:
1. strategy_id
   - 频道：
   - 方向：
   - 开仓：
   - 退出：
   - 样本：
   - median/p25/p10：
   - 风险：
   - 为什么保留：

Reject:
1. strategy_id
   - 拒绝原因：p25 差 / 靠大赢家 / 时间切分失效 / 样本不足 / journal penalty 高

下一步：
- 只列 3-5 个动作
```

---

## 13. 推荐首个 AutoResearch prompt

给 agent 的第一条任务应该是：

```text
你是 BWE 三频道触发式交易研究员。只做 sandbox 研究，不碰 live。

目标：基于 OI&Price、pricechange、Reserved6 三频道历史数据，执行 Round 1：固定 entry family，优化 filter + exit + risk。

优先级：
1. OI&Price：OI short A/B，比较 E072/E074/E076 vs E027/E043/E098。
2. pricechange：long 降噪过滤，early_5m/high volume/burst/same-symbol cooldown。
3. Reserved6：bigmove pump fade short 与 bigmove crash continuation short。

输出：
- candidate configs
- scoreboard
- reject log
- promote_to_paper.yaml
- 中文 report

禁止：
- 读取 secrets
- 改 live config
- 下单
- 自动推荐 live
- 用 mean return 单独排序
```

---

## 14. 第一轮成功标准

Round 1 完成后，应该能回答：

```text
1. OI short 哪 2-4 个组合最值得 paper A/B？
2. pricechange long 哪些过滤真正减少坏单？
3. Reserved6 是否有稳定的 extreme short/fade 候选？
4. 哪些候选只是历史看起来好，但样本外/左尾/费用后失效？
5. 下一轮应该扩展哪个方向？
```

如果不能回答这五个问题，说明 AutoResearch 流程还不够完整。
