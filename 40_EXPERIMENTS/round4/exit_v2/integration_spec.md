# exit_v2 Integration Spec — How to Apply to Live Bot

> 本文是给你 review 后决定如何 plug in `exit_v2` 模块到 `bwe_live_autotrader.py`.
> **不会自动修改 live bot**, 等你 ack 后再改.

---

## 风险评估

| 项 | 风险 |
|---|---|
| live bot 跑实钱 ($15/单 × max concurrent) | **改动需 paper 验证 3-7 天** |
| 改动主要在 exit logic | 入场不变,可控 |
| Backtest delta 显著 | LIVE +210% / PAPER +480% raw, 反 overfit pass |
| TRADOOR-类 black swan trade | 损失 ~50%, 但其它 30 trades 加固覆盖 |

## 建议 rollout 顺序

1. **Week 1**: paper bot only — 用 `exit_v2` 替换 paper 的 exit logic, 跑 3-7 天看 paper PnL trends
2. **Week 2**: 1 live strategy (`oi_overcrowded_crash_follow_short` 是金矿但 sample 小, 用它做 live 试点) with `exit_v2`
3. **Week 3+**: 全 live 切换 if Week 2 OK

## Integration Steps

### Step 1: Copy exit_v2.py

```bash
cp /Volumes/T9/BWE/40_EXPERIMENTS/round4/exit_v2/exit_v2.py \
   /Users/ye/.hermes/lib/exit_v2.py
```

### Step 2: 在 `bwe_live_autotrader.py` 顶部 import

```python
sys.path.insert(0, '/Users/ye/.hermes/lib')
from exit_v2 import (Bar, Position, ExitConfig, ExitEngine,
                     compute_atr_pct)

# Production config (from backtest sensitivity)
PROD_EXIT_CONFIG = ExitConfig()  # default first-principles params
PROD_EXIT_ENGINE = ExitEngine(PROD_EXIT_CONFIG)
```

### Step 3: 在 entry 时计算 ATR + initialize Position

在 `_open_position` 处 (entry creation), 添加:

```python
# Fetch last 30 1m bars for ATR computation (从 kline DB or REST)
pre_entry_bars = fetch_recent_1m_bars(market_symbol, n=30)
atr_pct = compute_atr_pct(pre_entry_bars, period=14, ref_px=fill_price)

pos['atr_at_entry_pct'] = atr_pct
pos['high_water_pct'] = 0.0  # already tracked
```

### Step 4: 替换 `_handle_prove_then_hourly_state` 的 stop logic

**原 logic** (line 1372-1420):
- prove_gate (前 N min 内)
- profit_protection_exit_reason
- hourly check + runner_floor + adverse_count + hourly_state_exit

**新 logic**: 调用 `ExitEngine.decide(pos, bars)`. Engine 包含:
- Hard stop / catastrophe stop (含 min_hold grace)
- Dynamic trail (tier-based)
- Volume confirm

Skeleton:
```python
def _handle_with_v2_engine(self, positions, *, symbol, pos, last, hold_min):
    # Get recent bars (need at least 35 for volume confirm)
    bars = self._get_recent_bars(symbol, lookback_min=60)

    # Wrap pos as exit_v2.Position
    exit_pos = Position(
        entry_ts_ms=int(pos['entry_ts'] * 1000),
        entry_px=float(pos['entry_px']),
        side=pos['side'],
        hold_minutes_limit=float(pos.get('hold_minutes_limit', 360)),
        atr_at_entry=float(pos.get('atr_at_entry_pct', 0)),
        high_water_pct=float(pos.get('high_water_pct', 0)),
    )

    decision = PROD_EXIT_ENGINE.decide(exit_pos, bars)

    # Sync high_water back to live pos
    pos['high_water_pct'] = exit_pos.high_water_pct

    if decision is not None:
        self._close_full_position(
            positions, symbol=symbol, pos=pos,
            exit_reason=decision.reason,
            last=decision.exit_px,  # use engine-recommended exit price
            hold_min=hold_min,
        )
        # Log v2 decision details for monitoring
        self.logger.info(f"[exit_v2] {symbol}: {decision.reason} "
                        f"pnl={decision.pnl_pct:.2f}% notes={decision.notes}")
        return True

    positions[symbol] = pos
    return False
```

### Step 5: 加 `_get_recent_bars` helper

```python
def _get_recent_bars(self, symbol: str, lookback_min: int = 60) -> list[Bar]:
    """Fetch last N min of 1m kline from DB."""
    end_ms = int(time.time() * 1000)
    start_ms = end_ms - lookback_min * 60_000

    market_sym = symbol if symbol.endswith('USDT') else symbol + 'USDT'
    cur = self.kline_db.execute(
        "SELECT open_time_ms, open, high, low, close, volume "
        "FROM klines_1m WHERE symbol=? AND open_time_ms >= ? "
        "ORDER BY open_time_ms",
        (market_sym, start_ms),
    )
    return [Bar(*r) for r in cur.fetchall()]
```

### Step 6: A/B switch via config

```yaml
# In config.yaml:
exit_engine:
  use_v2: false  # toggle to true after paper validation
  v2_config: prod
```

```python
def _handle_position(self, ...):
    if self.config.get('exit_engine', {}).get('use_v2'):
        return self._handle_with_v2_engine(...)
    return self._handle_prove_then_hourly_state(...)  # legacy
```

## 验证 plan

### Phase 1 (3-7 天 paper)

启用 `use_v2=True` 在 paper bot only. 观察:

| 指标 | 现 (paper) | exit_v2 期望 |
|---|---|---|
| total raw pnl | -361% | > +50% |
| win rate | 22% | 50%+ |
| capture ratio | -227% | > 30% |

**Pass condition**: paper PnL **3 天移动均值 > 0**, win rate > 50%.

**Fail condition**: paper PnL 持续负, 或者 catastrophic exit reason 频繁 (> 20% trades).

### Phase 2 (1 week, 1 strategy live)

启用 `use_v2=True` 仅 `oi_overcrowded_crash_follow_short`. 观察 5-10 trades 表现.

**Pass condition**: total pnl positive, no catastrophe stop triggers.

### Phase 3 (full live rollout)

全 strategy 启用 `use_v2`.

## Monitoring metrics

每天 dashboard 看:
- `n_exits_by_reason`: trail / hard_stop / catastrophe / time / volume_held
- `volume_held_count`: how many times volume confirm prevented exit (洗盘 detection 触发数)
- `avg_capture_ratio`: realized_pnl / max_fav_pct
- `tier_hit_distribution`: 哪些 trail tier 实际被触发 (验证 dynamic 是否有用)

## Rollback

如果 Phase 1 paper 数据显示退化, 把 `use_v2=False` 切回 legacy. 完全 backwards compatible.

## 已知 limitation

1. **TRADOOR-style black swan 损失**：dynamic trail tier (上限 25%) 无法 capture +60%+ runs. 如果未来有 confidence 是 black swan, 可加 manual override (e.g. `pos['black_swan_mode']=True`) 跳过 trail.
2. **Volume confirm 依赖 1m kline DB**：DB 必须 up-to-date (collector 在跑). 如果 collector down, volume_confirm 默认 return True (conservative).
3. **ATR computation 依赖 30 prior 1m bars**：新上市 symbol 可能没足够 history, fallback 是 atr=0 → hard_stop_min_pct=5%.
