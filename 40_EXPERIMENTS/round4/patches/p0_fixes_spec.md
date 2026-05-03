# Live Bot P0 Fixes — Code Patches (Not Yet Applied)

> 这些 patch **不会改 live bot**, 仅作为 spec 给你 review。
> Backtest replay 用相同 logic 模拟,验证后再决定是否应用。

---

## Patch P0 #1 — `runner_floor_exit` Trail with High-Water

**Bug**: `bwe_live_autotrader.py:1404-1408` 用 `pnl_pct < runner_floor_pct` 判 exit, 但
`high_water_pct` 已在 line 1369 tracked **却完全没用**。所以 KAT max_fav +33% 后跑回 -7%
触发 exit, **33% 利润全丢**。

### 加 default config (line 36-50 region)

```python
# 在 default strategy config 加:
'trail_activate_pct': 5.0,    # 已赚 5%+ 才启动 trailing
'trail_step_pct': 5.0,        # 从 high_water 回撤 5% 触发 exit
'trail_lock_in_partial': 0.5, # 高水位 ≥ 15% 时 lock in 50% partial (可选)
```

### 修改 `_handle_prove_then_hourly_state` (line 1399 后插入)

```python
# 在 line 1399 (profit_protect_reason check) 之后, line 1404 (next_hour_check) 之前

# === NEW: trail with high_water (check every tick, not gated by hourly) ===
high_water = float(pos.get('high_water_pct', 0.0))
trail_activate = float(self._strategy_value(strategy_name, 'trail_activate_pct', 5.0))
trail_step = float(self._strategy_value(strategy_name, 'trail_step_pct', 5.0))

if high_water >= trail_activate:
    effective_floor = high_water - trail_step
    if pnl_pct < effective_floor:
        self._close_full_position(
            positions, symbol=symbol, pos=pos,
            exit_reason='trail_drawdown_exit',
            last=last, hold_min=hold_min,
        )
        return True
# === END NEW ===

# 然后 line 1404 原 hourly check 继续:
next_hour_check_ts = float(pos.get('next_hour_check_ts') or 0.0)
if next_hour_check_ts and self.time_fn() >= next_hour_check_ts:
    if pnl_pct < runner_floor_pct:
        # 这里仍然保留原 logic 作为 ungated fallback
        ...
```

**为什么放在 hourly check 之前**: 让 trail 每 tick 都跑(几秒一次), 不等下一个整点。
KAT 例子: 高水位 33% 之后 5 分钟内开始回撤, hourly check 要等 ~55 min, 那时已 -7%; 新 logic
回撤到 28% (high_water 33% - step 5%) 立即 exit, 锁住 28% profit。

---

## Patch P0 #3 — `catastrophe_stop` 加 Min-Hold Grace Period

**Bug**: line 1373-1380 在 hold_min < activation_delay_min 期间用 catastrophe_stop_pct
作为 stop 阈值。但 LAB hold=4min max_fav=0.9% 就触发 catastrophe -7.7% — 妖币 4 min 内
-7% 是 normal noise / 洗盘, 不是 真 catastrophe。

### 加 default config

```python
'catastrophe_min_hold_min': 30.0,   # 头 30 min 内 catastrophe 阈值放宽
'catastrophe_grace_multiplier': 2.0, # grace 期 catastrophe 阈值 × 2
```

### 修改 line 1372-1378

```python
# Original:
if activation_delay_min > 0 and hold_min < activation_delay_min:
    if catastrophe_stop_pct is not None and pnl_pct <= -catastrophe_stop_pct:
        exit_reason = 'catastrophe_stop'
else:
    if pnl_pct <= -hard_stop_pct:
        exit_reason = 'hard_stop'

# Change to:
catastrophe_min_hold = float(self._strategy_value(
    strategy_name, 'catastrophe_min_hold_min', 30.0))
catastrophe_multiplier = float(self._strategy_value(
    strategy_name, 'catastrophe_grace_multiplier', 2.0))

# 在 grace period 内 (head 30 min) 用更宽 catastrophe 阈值
catastrophe_pct_effective = catastrophe_stop_pct
if hold_min < catastrophe_min_hold and catastrophe_stop_pct is not None:
    catastrophe_pct_effective = catastrophe_stop_pct * catastrophe_multiplier

if activation_delay_min > 0 and hold_min < activation_delay_min:
    if catastrophe_pct_effective is not None and pnl_pct <= -catastrophe_pct_effective:
        exit_reason = 'catastrophe_stop'
else:
    if pnl_pct <= -hard_stop_pct:
        exit_reason = 'hard_stop'
```

**效果**: head 30 min 内 catastrophe 阈值从 e.g. -8% 放宽到 -16%, 给 signal 时间反弹。
hard_stop (-2.5% default) 仍硬性保护 catastrophic loss。

---

## Patch P0 #4 — OI Strategy Scale Up

**当前**: oi_overcrowded_crash_follow_short (5 trades, 80% win, +39% mean) 是金矿
**瓶颈**: trigger 条件可能太紧, 5 days 仅 5 unique symbols matched.

### 加新 strategy: `oi_unwind_bounce_long`

对称的 long-side strategy: OI 大跌 + 价格反弹 = 空头被挤爆 squeeze.

```python
# 在 strategies config 加:
'oi_unwind_bounce_long': {
    'channel': 'BWE_OI_Price_monitor',
    'side': 'long',
    'enabled': True,
    'trigger_filter': {
        'oi_change_pct': '<= -8',           # OI 大跌
        'event_type': 'pump',                # 价格在涨
        'prev_hour_quote_volume_q': '>= Q3', # 流动性够
    },
    'entry_delay_s': 30,
    'hold_minutes_limit': 360,  # 6h, 跟 oi_overcrowded_crash 类似
    'hard_stop_pct': 5.0,
    'runner_floor_pct': 0.0,
    'trail_activate_pct': 5.0,
    'trail_step_pct': 5.0,
}
```

### 放宽现有 oi_overcrowded threshold

如 oi_overcrowded_crash_follow_short 的 oi_change 阈值从 ≥ 15% 降到 ≥ 10% (找更多 signal).

⚠️ **注意**: 这条 patch **改了 trigger 条件本身, 影响 signal selection**.
应当 **先在 paper bot 跑 1-2 天** 确认 win rate 没退化才上 live.

---

## Patch P0 #2 — `pc_crash_bounce_long` Filter Tighten

**当前**: 45 live trades, win 29%, mean -1.4%, total -63%. 在 P0 #1 + #3 fix 之前 disable risk: 高
(loses real winners). Fix 之后 backtest 再判断.

### 待 Patch P0 #1 + #3 backtest 通过后再决定

如果 backtest 显示新 exit logic 让 pc_crash_bounce_long 从 -63% 变 +30%+, **保留 strategy**.
否则 disable 或加 entry filter:

```python
# 添加 entry filter (in trigger checking before _can_open):
'pc_crash_bounce_long': {
    'trigger_filter': {
        'prev_hour_quote_volume': '>= 30M',   # 流动性硬要求
        'marketcap_usd': '>= 50M',              # 排除 ultra-microcap
        'pre2h_ret_abs': '>= 1.0',              # 之前 2h 至少有 1% 动量 (有 bounce 的基础)
        'burst_seq_5m': '<= 2',                 # 排除连续多次触发的过热信号
    }
}
```

但这是 **data-driven filter** (基于 live winners 的特征), 有 overfit risk. 建议先看 backtest 然后决定。
