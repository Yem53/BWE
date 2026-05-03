# 04. 完整策略搜索空间

## 完整策略定义

```text
complete_strategy = trigger + entry + risk + in_position_monitor + exit_state_machine + portfolio_rule
```

每条候选必须至少包含：

- `strategy_family`
- `channel`
- `event_type`
- `side`
- `entry_timing`
- `entry_conditions`
- `initial_stop`
- `take_profit`
- `partial_exit`
- `trailing_rule`
- `breakeven_rule`
- `runner_rule`
- `indicator_invalidation_exit`
- `max_hold_time`
- `position_sizing`
- `portfolio_constraints`

## 入场搜索维度

### Trigger

- `BWE_OI_Price_monitor`
- `BWE_pricechange_monitor`
- `BWE_Reserved6`
- future channels if present

### Event

- `pump`
- `crash`
- unknown/other as no-trade or watchlist bucket

### Side

- long
- short
- no_trade

### Timing

- T0
- T0+30s
- T0+1m
- T0+3m
- T0+5m
- conditional wait until confirmation
- abandon if no confirmation

### Feature families

- message context
- OI / OI value / OI change
- funding
- global long/short
- top trader account ratio
- top trader position ratio
- taker buy/sell flow
- basis / premium / mark-index
- mark 1m structure
- BTC/ETH regime
- liquidity / quote volume
- marketcap
- listing age
- cross-channel confirmation

## 退出搜索维度

### Fixed exits

- fixed TP
- fixed SL
- time stop
- max hold

### Partial exits

- partial TP
- ladder TP
- scale-out

### Trailing exits

- fixed trailing
- runner trail
- vol adaptive trail
- mark/premium-aware trail

### Breakeven exits

- breakeven after profit threshold
- ratchet lock
- profit floor

### Time-decay exits

- prove-or-exit
- slow-start-cut
- time-decay TP/SL

### Path-aware exits

- first-touch
- failed continuation
- reversal candle
- wick rejection
- pullback fail

### Indicator invalidation exits

- OI invalidation
- taker reversal
- premium overheat
- basis overheat
- top trader reversal
- BTC/ETH reversal

### State machine exits

- prove-then-runner
- fast-profit-then-hold
- slow-start-cut
- pump-overheat-fade
- continuation-then-breakeven
- cross-channel-invalidated

## 搜索规模建议

在 5090 + 64GB + 4TB SSD 上：

```text
candidate space: 10B+
coarse sampled/evaluated: 100M+
medium path simulation: 1M-5M
deep state machine replay: 50K-200K
walk-forward/stress: 5K-20K
portfolio replay: 500-2000
paper manifest: 5-30
```

注意：百亿级是空间，不是全部深度回测。

## 剪枝原则

必须早停：

- sample size 太小
- median <= 0
- stress median <= 0
- p10 极差
- profit factor < 1.2
- top 1% winner dependency
- top symbol dependency
- walk-forward 大多数窗口无效
- complexity penalty 后不占优

