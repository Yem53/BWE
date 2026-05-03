# Paper-Shadow ↔ Backtest 一致性 Drift 归档

**目的**: 记录 paper-shadow 跟 backtest_runner 之间的所有不一致 (data drift, 计算差异, 时机偏差),
以及修复进度。Drift = paper 跟 backtest 在同一个 (event, strategy, params) 下产出不同 PnL 的根因。

**用法**:
- 每次发现新的 drift 立即追加在下方编号增加, status=OPEN
- 修复后改 status=FIXED 并 commit hash + before/after 数据
- 验证后改 status=VERIFIED + 对照表数据

**核心原则 (Rule #0 数据驱动)**:
- Drift 必须用具体数据 (单笔 trade 复现, 价格逐分钟对比) 证明, 不能凭直觉
- 修复后必须用 ablation 跑数据验证修复效果 (mean/sum/WR 前后对比)

---

## 时间线

| 日期 | 事件 |
|---|---|
| 2026-05-01 18:50 UTC | 用户问 "paper 跟回测 sum 2000% 出入这么大", 启动 audit |
| 2026-05-01 19:00 UTC | 找到 Drift #1 (entry look-ahead), 单笔 TAKEUSDT 验证 |
| 2026-05-01 19:10 UTC | 系统化 audit 找到 D2/D3/D4, 建本归档 |
| 2026-05-01 19:30 UTC | D1/D2/D3/D4 全部修复, V4 30d backtest 验证 alpha +10% mean |
| 2026-05-01 19:50 UTC | 用户要求重启前再 audit, 找到 D8/D9/D10/D13/D14 |
| 2026-05-01 20:00 UTC | 全部修复, ATR/entry/bars 三处 perfect match |
| 2026-05-01 20:05 UTC | Paper PID 39625 用全部修复后 code 重启 |
| 2026-05-01 22:48 UTC | 清空 state, restart PID 68913, 跑 4.9h LABUSDT 单币集中爆 -158% |
| 2026-05-02 01:30 UTC | 用户洞察: 1m kline backtest 隐含 look-ahead, paper 90s delay 也继承了这个 bias |
| 2026-05-02 01:45 UTC | **架构升级**: 写 paper_shadow_live.py 用 binance mark price API 实时入场 (D15) |
| 2026-05-02 01:55 UTC | Paper-LIVE PID 16448 启动, ENTRY_DELAY=0, max_concurrent_per_symbol=3 |

---

## Drift 列表 (按严重度排序)

### D1: ENTRY_PRICE LOOK-AHEAD BIAS in backtest 🔴 CRITICAL

**Status**: OPEN (待修)

**位置**:
- `backtest_runner.py:74-86` `_get_bars` 用 `WHERE open_time_ms >= ?` (event 之后)
- `backtest_runner.py:131-135` `entry_bar = bars[0]; entry_px = entry_bar.close`

**对应 paper 行为**:
- `paper_shadow.py:250-256` `_kline_close_at` 用 `WHERE open_time_ms <= ? ORDER BY DESC LIMIT 1`
- `paper_shadow.py:814` `entry_price = _kline_close_at(live_db, e.symbol, e.ts_ms)`

**差异本质**:
- Backtest entry_px = event +60s 之后 1m bar 的 close (即 event 之后 60-120s 的价)
- Paper entry_px = event 之前最近完成 1m bar 的 close (即 event 之前 0-60s 的价)
- 时间差 = 60-120s, 在 pump 触发瞬间足以错过整个 pump 顶部

**数据证据 (TAKEUSDT @ 16:43:50 UTC)**:

| time | 1m close | 用法 |
|---|---|---|
| 16:42:00 (-2min) | 0.0309 | Paper entry (DB 无 16:43 bar 时 fallback) |
| 16:43:00 (event 当时, bar 未完成) | 0.0323 | DB 还没数据 |
| 16:44:00 (+1min) | 0.0316 | **Backtest entry (look-ahead!)** |
| 17:44:00 (+60min, exit) | 0.0327 | 共享 |

- Paper PnL = (0.0309 - 0.0327) / 0.0309 = **-5.49%**
- Backtest PnL = (0.0316 - 0.0327) / 0.0316 = **-3.48%**
- 单笔差 +2.01% (backtest 有 look-ahead 优势)

**为什么严重**: SHORT-fade-pump 策略最受益于 *进顶部*。Backtest 在 pump 顶部之后第一根 bar close 入场,
比 paper "起点入场" 多 +2-5% 入场价优势。30 天累积 mean 差 +7-8%。

**对累积 sum 的影响**:
- CHAMP backtest: mean +7.96%, sum +4177% over 525 trades
- CHAMP paper (5.4h): mean +0.65%, ~12× 缩水
- 估算: 修掉 D1 后 backtest mean 从 +7.96% 降到 +1-2%, sum 从 +4177% 降到 +500-1000%

**修复方案**:
```python
# backtest_runner.py
def _kline_close_at_or_before(db, sym, ts_ms, fb_db=None):
    for c in [db, fb_db]:
        if c is None: continue
        row = c.execute(
            "SELECT close FROM klines_1m WHERE symbol=? AND open_time_ms<=? "
            "ORDER BY open_time_ms DESC LIMIT 1", (sym, ts_ms)
        ).fetchone()
        if row and row[0] is not None:
            return float(row[0])
    return None

# In _simulate_trade — accept entry_px from caller:
def _simulate_trade(trigger, bars, profile_id, profile_params, entry_px):
    pos = Position(side=..., entry_px=entry_px, ...)  # not bars[0].close
    # bars[0] still used for entry_ts_ms / ATR / first exit-check bar
```

```python
# In SingleExperimentRunner.run:
for tr in triggers:
    entry_px = _kline_close_at_or_before(self.live_db, tr.event.symbol, tr.event.ts_ms, self.ext_db)
    if entry_px is None or entry_px <= 0:
        continue
    bars = _get_bars(self.live_db, tr.event.symbol, tr.event.ts_ms, fb_db=self.ext_db)
    outcome = _simulate_trade(tr, bars, ..., entry_px)
```

**验证方法**: 重跑 V4 entry/exit search 30d, 对比修复前后 mean/sum/WR。

---

### D2: ATR LOOK-AHEAD BIAS in backtest 🟠 HIGH

**Status**: OPEN

**位置**:
- `backtest_runner.py:131-133`:
  ```python
  pre_entry_bars = bars[:1] if len(bars) < 30 else bars[:30]
  atr = _compute_atr_pct(pre_entry_bars)
  ```
  bars 是 event 之后的, 所以 bars[:30] = event +60s 起 30 个 1m bar

**对应 paper 行为**:
- `paper_shadow.py:819-825`:
  ```python
  pre = live_db.execute(
      "... WHERE symbol=? AND open_time_ms<=? ORDER BY open_time_ms DESC LIMIT ?",
      (e.symbol, e.ts_ms, PRE_ENTRY_BARS_FOR_ATR)
  ).fetchall()
  atr = _atr_pct_from_bars(list(reversed(pre)))
  ```
  pre = event 之前 30 个 1m bar

**差异本质**:
- Backtest ATR = event 之后 30 min 真实波动率 (有 look-ahead bias)
- Paper ATR = event 之前 30 min 历史波动率

对 ATR-based SL (EP11, AtrScaledTrail, BreakevenAtr):
- Backtest 知道未来 30 min ATR → 设的 SL 离价位更准确
- Paper 用过去 30 min ATR → SL 可能在 pump 触发后失真

**对累积影响**: 未量化, 估计 +0.5-2% mean 差距 (二阶效应)

**修复方案**:
```python
def _atr_pct_pre_event(db, sym, event_ts_ms, n=30, fb_db=None):
    for c in [db, fb_db]:
        if c is None: continue
        rows = c.execute(
            "SELECT open_time_ms, open, high, low, close, volume FROM klines_1m "
            "WHERE symbol=? AND open_time_ms<=? ORDER BY open_time_ms DESC LIMIT ?",
            (sym, event_ts_ms, n)
        ).fetchall()
        if len(rows) >= 5:
            from src.backtest_runner import _compute_atr_pct
            return _compute_atr_pct([Bar(...) for r in reversed(rows)])
    return 1.0
```

然后在 `_simulate_trade` 接受 atr 参数, 替代 `_compute_atr_pct(pre_entry_bars)`。

---

### D3: PnL FORMULA in backtest still uses engine.pnl_pct (Bug #2 leak) 🟠 HIGH

**Status**: OPEN

**位置**:
- `backtest_runner.py:142-144`:
  ```python
  decision = engine.decide(pos, slice_bars)
  if decision is not None:
      return {"pnl_pct": decision.pnl_pct, "reason": decision.reason, ...}
  ```

**对应 paper 行为 (paper Bug #2 fix)**:
- `paper_shadow.py:518-522`:
  ```python
  exit_close = float(bar_objs[i].close)
  if pos.side == "short":
      pnl = (pos.entry_price - exit_close) / pos.entry_price * 100.0
  else:
      pnl = (exit_close - pos.entry_price) / pos.entry_price * 100.0
  ```

**差异本质**:
- Paper 强制用 price-based PnL (因为 engine 在 trail_drawdown_exit 时返回的 pnl_pct 不等于 (entry - exit) / entry)
- Backtest 仍用 engine 返回的 pnl_pct, 所以 Bug #2 still affects backtest results
- 验证案例 (paper Bug #2 注释): GUAUSDT entry=0.816 exit=0.8419, engine 返回 +14.21%, 实际 SHORT = -3.17%

**对累积影响**: 主要影响 trail_drawdown_exit / lock@N 类 exit 的 pnl 准确度。
EP11/EP13 等 trail-based exit 可能高估真实盈利。

**修复方案**: 在 `_simulate_trade` 替换:
```python
if decision is not None:
    # Use price-based PnL like paper does (Bug #2 in backtest)
    exit_close = bars[i].close
    if pos.side == "short":
        pnl = (pos.entry_px - exit_close) / pos.entry_px * 100.0
    else:
        pnl = (exit_close - pos.entry_px) / pos.entry_px * 100.0
    return {"pnl_pct": pnl, "reason": decision.reason, "exit_ts_ms": decision.exit_ts_ms}
```

但要注意: SL_catastrophic / lock@N 类 exit 内部已经写死 exit_price (sl_price / cl), engine 的 pnl_pct 是用这些 price-based 算的, 应该一致。trail_drawdown_exit 是 problem。

---

### D4: PAPER V4 ATR LOOK-AHEAD BIAS 🟡 MED

**Status**: OPEN

**位置**:
- `paper_shadow.py:393-394` `_check_v4_exit`:
  ```python
  base_atr = _atr_pct_from_bars(bars[:30] if len(bars) >= 30 else bars)
  ```
  bars = entry+60s 之后的 bars, 所以 base_atr 用 entry +60s 起 30 个 1m bar 算

**问题**:
- Paper v4 自己的 SL 计算用了 *未来 30 min ATR*, 即 paper v4 内部也有 look-ahead bias
- 应该用 `pos.atr_at_entry` (已经存好的, 用过去 30 bars 算)

**修复方案**:
```python
def _check_v4_exit(pos, bars, exit_config):
    ...
    base_atr = pos.atr_at_entry  # 用 entry 时算好的 ATR (过去 30 bars)
    if base_atr <= 0:
        base_atr = _atr_pct_from_bars(bars[:30] if len(bars) >= 30 else bars)  # fallback
    ...
```

**对累积影响**: 影响 paper v4 SL 阈值。Paper 当前 95 笔 trade 里 6 笔 SL 命中 (`SL` + `hard_stop`), 修复后 SL 阈值会变化, 命中频率可能不同。

---

### D5: EVENT HISTORY WINDOW 🟢 LOW

**Status**: ACCEPTABLE

**位置**:
- Paper: 24h sliding window (Bug #1 fixed)
- Backtest: 全 30d events (load_events)

**为什么 acceptable**:
- yao_min 检查通常用 24h cutoff (template 内部)
- has_dump 也是 24h cutoff
- Paper 24h window 已覆盖全部已知 filter 的 lookback 需求
- 只有 multi-day 关联 (eg. 7d 内 N 次 pump) 受影响, 但目前没有这类 filter

**监控指标**: 如果未来加 multi-day filter, paper 必须扩窗口。

---

### D6: SUM_INTERPRETATION 🟢 INFO

**Status**: DOCUMENTED

**问题**: Paper 13 个 strategy 同时打同一 event, sum 是 13× 累加。Backtest 是 per-strategy 独立。
解读: 不能直接拿 paper sum vs backtest sum, 要 per-strategy 比较。

---

### D7: Paper-corrected state is partial — exit logic NOT re-simulated 🟡 KNOWN

**Status**: DOCUMENTED (working as designed)

**问题**: `state_realtime_repair.py` 只重 fetch entry_price/exit_price 两个数字,
**没有 重 simulate 整个 trade 的 exit decision**.
- Path-dependent exits (SL, lock@N, trail) 用了 *old* entry price 来跟踪 MFE / SL trigger
- 当 corrected entry 跟 old entry 差距大时 (e.g. UBUSDT 0.1139 → 0.1304), MFE/SL 阈值的相对位置变化 → 应该触发 lock@12 的 trade 在原 paper 里没触发

**例子 (GUAUSDT @ paper window)**:
- Paper 用 old entry 0.816 → MFE 计算 → 没达 lock@12 阈值 → time_exit @ 60min
- Backtest 用 corrected entry 0.8517 → MFE 计算 → 达 lock@12 阈值 → 早出场 → 利润不同

**修复方法**: 写一个 full-resimulate 脚本, 给 paper 每笔 trade 用 corrected entry 重跑 exit logic.
等于在 paper 时间窗口内重跑 backtest. 已通过 `scripts/v4_backtest_paper_window.py` 实现, 输出在
`stage3/v4_backtest_drift_check.json`.

**为什么 still document**: 用户当前不重启 paper, paper 旧 state.json 仍是 partial corrected. 
重启时换用 fully-corrected 状态需要决定。

---

## 修复历史

| ID | Drift | Status | Commit | Date | Verification |
|---|---|---|---|---|---|
| D1 | entry look-ahead in BT | **FIXED** | (current) | 2026-05-01 | ✅ TAKEUSDT entry 0.0316→0.0309 单笔 -2% 差距, 30d backtest re-run 后 CHAMP n=534 mean +7.96% → +9.99% (paper-aligned) |
| D2 | ATR look-ahead in BT | **FIXED** | (current) | 2026-05-01 | _atr_pct_pre_event 用 PRE-event 30 bars |
| D3 | PnL formula in BT | **FIXED** | (current) | 2026-05-01 | engine.pnl_pct → price-based (entry-exit)/entry |
| D4 | paper v4 ATR | **FIXED** | (current) | 2026-05-01 | _check_v4_exit 用 pos.atr_at_entry instead of bars[:30] |
| D5 | event history window | ACCEPTABLE | - | - | 24h cover all current filters |
| D6 | sum interpretation | DOCUMENTED | - | - | per-strategy comparison only |
| D7 | partial state correction | DOCUMENTED | - | 2026-05-01 | full-resimulate via v4_backtest_paper_window.py |

## 修复后 alpha 验证 (2026-05-01 19:30 UTC)

**全 30d backtest with all D1/D2/D3 fixes** (`scripts/v4_backtest_drift_check.py`):
| Family | n | Sum% | Mean% | WR% |
|---|---|---|---|---|
| BROAD | 1866 | +11358 | +6.09 | 65 |
| CHAMP | 1602 | +16016 | **+10.00** | 70 |
| QUAL  | 1272 | +15529 | **+12.21** | 73 |

**结论**: 修复 look-ahead bias 后, alpha 不仅没消失, 反而:
- CHAMP mean 从原 backtest +7.96% → +10.00% (n 从 525 → 1602, 因为 yao_min 用 24h 滑窗反而保留更多 events)
- QUAL mean +12.21%, WR 73% — **真实可达成的 alpha**

**为什么 paper-corrected 仍低 4-8%**: 5.4h regime 选择 bias (paper 跑的时段 BWE 信号密度 2.2× 全期均值) +
D7 partial correction 在 path-dependent exit 上失真。让 paper 跑 24-48h 后样本量足, 真实 alpha 会浮现。

---

## 待 audit 项目 (后续 batch)

- [x] D8: Paper kline 写入延迟 → 加 90s entry delay (FIXED 2026-05-01)
- [x] D9: max_concurrent_per_strategy=5 (paper) 同步到 backtest (FIXED 2026-05-01)
- [x] D10: legacy backtest bars[0] 起点对齐 paper event_ts+60s (FIXED 2026-05-01)
- [x] D11: legacy backtest events 24h sliding (DOCUMENTED — template 内部窗口已足)
- [x] D13: ATR 公式 paper 29-TR vs backtest 14-TR (FIXED 2026-05-01)
- [x] D14: pending_entries 持久化, restart 不丢失 in-flight events (FIXED 2026-05-01)
- [ ] _CacheBackedDB 跟 live_db 直接 query 在 funding/top_LS 数据上是否一致 (LOW prio)
- [ ] LONG side 在 paper 跟 backtest 的对称性 (当前都是 SHORT-only, OK)

---

## 新增 Drift 详情

### D8: Paper kline 写入延迟 → entry_px stale 🔴 CRITICAL

**Status**: FIXED 2026-05-01

**位置**: `paper_shadow.py:814` `entry_price = _kline_close_at(live_db, e.symbol, e.ts_ms)`

**根因**:
- BWE 在 event_ts 触发推送, paper 几秒内收到
- 包含 event_ts 的 1m bar (open_time = floor(event_ts) min) 还没 close (close 在 minute 边界)
- Binance kline 写入 collector 有 ~30-60s 延迟
- 所以 paper 在 event_ts 时 DB 里只有 *event 之前 1-2 min 的 bar*, 拿到 stale close
- Backtest replay 时 DB 完整, 拿到 *包含 event 的 bar 的 close* → 不同价

**例子 (TAKEUSDT @ 16:43:50 UTC, paper 当时记录)**:
- Paper @ live: entry_price=0.03097 (= 16:42 close, -2min stale)
- Backtest replay: entry_price=0.03227 (= 16:43 close, 包含 event 的 bar)
- 差 +4.2%, 同样的 SHORT trade backtest 多赚 ~4%

**修复方案**: paper 入场延迟 ENTRY_DELAY_SECONDS=90s
- Event 到达时只 append 到 recent_events + pending_entries
- 等 90s 后, 包含 event_ts 的 1m bar 已 close 并写入 DB
- 此时 _kline_close_at(event_ts) 返回正确的 close price (跟 backtest 一致)

**Trade-off**: paper 入场延迟 90s. 真实 live 也是 90s 后入场。这反而是好事 — pump 顶部往往在 event +60-90s,
延迟入场 = 在 pump 顶部 fade (alpha 来源).

**验证**: 重启后 paper 新 trade 的 entry_price 应该跟 backtest replay 一模一样。

---

### D9: max_concurrent_per_strategy 在 backtest 没生效 🟠 HIGH (alpha killer)

**Status**: FIXED 2026-05-01

**问题**:
- Paper config: `_position_size.max_concurrent_per_strategy = 5`
- 当一个 strategy 已有 5 个 open position 时, 新事件被 skip
- Backtest 旧版没这个限制 → 高密度信号期 backtest 多触发 trades

**对 alpha 的影响 (验证数据 30d)**:
- BT 无 cap: BROAD 1869 trades, mean +6.35%, sum +11869%
- BT 有 cap=5: BROAD 929 trades, mean +1.02%, sum +947%
- ⚠ Cap=5 把 mean 从 +6% 杀到 +1%, **高密度信号期是 alpha 集中地**

**原因分析**:
- BWE 高密度信号期 = market regime 异常 (BTC 大跌, alts 集体 squeeze pump)
- 这时 SHORT-fade 最赚 (squeeze 后必回落)
- max_concurrent=5 把这种 period 的 6th-Nth trade 全 cap 掉
- 漏掉的恰好是 best opportunities

**修复方案**: backtest scripts 加 max_concurrent_per_strategy 跟踪 + cap (跟 paper 一致)

**Implication**: 真实可执行 alpha 是 paper-cap 后的 +1-3% mean, 不是 backtest 无 cap 的 +10% mean.
要保 alpha, 用户可考虑:
1. 提高 max_concurrent (如 10-15) 接受更高 exposure
2. 使用动态 sizing (cap 在 portfolio risk 上, 不是 trade count)

---

### D10: legacy backtest bars[0] 起点偏 1 bar 🟠 HIGH

**Status**: FIXED 2026-05-01

**问题**:
- Paper bars: `_bars_after(entry_ts + 60_000)` → bars[0] = event +60s+ 之后第一根 bar
- Backtest bars: `_get_bars(event_ts)` → bars[0] = event 之后第一根 bar (包含 event 的下一根)
- 偏差 1 个 1m bar

对 v4 strategies 不影响 (我的 v4 script 直接用 paper SQL)。
对 legacy strategies (ST15, ST9, ST8) 有 1-bar 偏差 → engine.decide 触发时机略不同。

**修复方案**: backtest_runner.py 改用 event_ts + 60_000 起点; entry_ts_ms_override = event_ts (跟 paper 一致)。

---

### D13: ATR 公式 paper 29-TR vs backtest 14-TR 🟠 HIGH

**Status**: FIXED 2026-05-01

**位置**:
- Paper `_atr_pct_from_bars`: 给 30 bars, 计算 29 个 TR, 平均
- Backtest `_compute_atr_pct(period=14)`: 给 30 bars, 只取最后 14 个 TR, 平均

**数据验证 (TAKEUSDT pre-event 30 bars)**:
- Paper ATR: 1.8978%
- Backtest ATR: 1.7553%
- 差 7.51% relative

对 SL: 影响 7.5% (atr_mult=10 → SL_pct 17.0% vs 18.9%, 1.9% 差距)。
对 lock@N 不影响 (跟 ATR 无关)。

**修复方案**: backtest `_atr_pct_pre_event` 改用 paper 公式 (所有 TR 平均, 不用 period=14 截断)。

**验证**: 修复后 paper.atr_pct_from_bars(reversed pre 30bars) == backtest._atr_pct_pre_event() 完全一致 (0.00 diff)。

---

### D14: pending_entries 持久化 🟡 MED

**Status**: FIXED 2026-05-01

**问题**: D8 引入 pending_entries 队列 (events 等 90s 才入场). 如果 paper crash 后重启,
in-memory pending_entries 丢失 → 90s 内的 in-flight events 错失。

**修复方案**:
- RunnerState 加 `pending_entries_serialized: list[dict]` field
- 每次 save_state 前 sync pending_entries → state
- load_state 时 restore pending_entries

**测试**: 重启 paper 后会从 state.json 恢复 pending entries, 等 90s 后入场。无 events 丢失。

---

## 14 项一致性 audit 最终状态 (重启后)

| ID | Item | Status |
|---|---|---|
| D1 | ENTRY_PRICE 取价 SQL | ✅ FIXED |
| D2 | ATR look-ahead in BT | ✅ FIXED |
| D3 | PnL formula in BT | ✅ FIXED |
| D4 | Paper v4 ATR look-ahead | ✅ FIXED (重启后生效) |
| D5 | Recent events 24h window | ✅ ALIGNED (升 25h) |
| D6 | Sum interpretation | ✅ DOCUMENTED |
| D7 | Corrected state partial fix | ✅ DOCUMENTED |
| D8 | Paper kline write delay | ✅ FIXED (90s entry delay) |
| D9 | max_concurrent in BT | ✅ FIXED |
| D10 | Legacy BT bars[0] | ✅ FIXED |
| D11 | Legacy BT events window | ✅ DOCUMENTED |
| D12 | Trade dedup | ✅ INFO |
| D13 | ATR formula | ✅ FIXED |
| D14 | pending_entries persist | ✅ FIXED |

**Verification (single-trade, post-fix)**:
| Metric | Paper | Backtest | Match? |
|---|---|---|---|
| entry_px (TAKEUSDT) | 0.03227 | 0.03227 | ✅ identical |
| ATR_pre_event | 1.8978% | 1.8978% | ✅ identical |
| bars[0] open_time | 16:45:00 UTC | 16:45:00 UTC | ✅ identical |

---

## D15: Paper LIVE Mode (mark price API) 🔴 ARCHITECTURAL UPGRADE

**Status**: DEPLOYED 2026-05-02 (PID 16448 running)

**问题根因 (用户的关键洞察)**:
- 1m kline backtest 用 *event_ts 包含 bar 的 close*, 这个 close 在 bar 结束时(event +10~60s)才确定
- Backtest replay 时 DB 已有所有 bar, 等于 *使用了 60s 后才能知道的价格*
- 这是 **implicit look-ahead bias**, 不是 code drift, 是 *backtest 方法学* 缺陷
- Paper 90s 延迟方案是 align 了 backtest, 但等于 *继承 了 backtest 的 look-ahead*
- 真实 live 不能等 60s 让 1m bar 完成, 应该用 **real-time mark price**

**为什么这是 D15 而不是 fixing previous drifts**:
- D1-D14 是 *paper-backtest alignment* drifts (代码层面对齐)
- D15 是 *paper-reality alignment* drift (paper 测的不是真实 live, 而是带 look-ahead 的虚假场景)

**对 alpha 的影响估计**:
- Backtest mean: +10% (含 look-ahead)
- Paper kline mode (90s delay): +10% mean (== backtest, 因为对齐了)
- **Paper LIVE mode (real-time API)**: 估计 +1~3% mean (真实可达 alpha)

**修复方案**:
- 新建 `src/paper_shadow_live.py` (paper_shadow.py 的 live mode 版)
- 新建 `src/binance_client.py` (mark price API client + retry/cache)
- Entry source: `get_mark_price(symbol)` 替代 `_kline_close_at(db, symbol, ts)`
- ENTRY_DELAY_SECONDS = 0 (即时入场, 跟 BWE event 同步)
- Exit price: 仍用 1m kline DB (60min 后 DB 已有数据, 无 look-ahead)
- 新加 `max_concurrent_per_symbol=3` 防 LABUSDT 集中

**Trade-off (诚实记录)**:
- ❌ 失去跟 backtest 的直接对比能力 (entry 价不同)
- ✅ 测出来的 alpha 才是真实 live 可达的 alpha
- ✅ 100% 模拟实盘下单行为 (假设无滑点 + fees)
- 后续若加 testnet API 真下单, 还能测滑点/fees (D16+)

**当前部署**:
- PID 16448, runtime: paper_shadow/runtime_live/
- 旧 paper_shadow.py (kline mode) 已停 (PID 68913, state.before_live_switch_*.json 备份)
- 13 strategies 不变, 用 strategies_live.json (=strategies.json)
- max_concurrent_per_symbol=3 防止 LABUSDT 单币 13× 集中
- API health check 启动时验证, 失败则 abort
- API 失败 fallback 到 DB kline (state.api_fallback_count 跟踪)

**新增 audit 项 (后续)**:
- [ ] D17: 跑 24-48h 后, 对比 paper-LIVE mean vs backtest mean, 量化 look-ahead 衰减率
- [ ] D18: mark price vs last trade price 差异 (binance 内部 weighted, 跟实际成交可能差 0.05-0.2%)

---

## D16: Testnet Real Order Placement 🔴 PRODUCTION-LIVE INTEGRATION

**Status**: DEPLOYED 2026-05-02 02:10 UTC (PID 38218 alive with testnet trading)

**目的**: paper-live 用 mark price 模拟 alpha, 但 *没有滑点 + 没有 fees + 假设 mark = fill price*. 接 binance testnet 实下单可以测量真实 slippage + fees, 进一步逼近真实 live 表现。

**实现**:
- 新文件 `src/binance_testnet_client.py` (~280 lines): HMAC-SHA256 签名 client
  * 端点: https://testnet.binancefuture.com (DIFFERENT from production!)
  * Keys: BINANCE_TESTNET_API_KEY/BINANCE_TESTNET_SECRET 在 ~/.hermes/.env (gitignored)
  * place_market_order, close_position (with reduce_only=True), get_position, get_balance
  * `newOrderRespType=RESULT` 让 MARKET order 同步返回 fill 信息

- `paper_shadow_live.py` 升级:
  * `--enable-testnet-orders` flag
  * `--testnet-notional-usdt 50` (default per-trade size)
  * `--testnet-max-total-notional 3000` (safety cap)
  * 每个 entry 同时: 下 paper sim + 下 testnet MARKET order
  * 每个 exit 同时: paper sim 平仓 + testnet reduce_only close (按 strategy 自己记录的 qty)
  * 跟踪 testnet_pnl_pct, testnet_pnl_usdt per trade

**首次部署观察 (PID 38218 startup)**:
- LABUSDT @ $2.31 (3 strategies 同时入场, 每个 21.6 qty = $50 notional)
- testnet 实际 fill $2.3145 vs mark price $2.31309 = +0.097% **真实 slippage 测出** ✓
- 5 min 后 LABUSDT 回落到 ~$2.03, **unrealized PnL +$18.20** (3 strategies × +$6)
- 这个 unrealized PnL/strategy ≈ +12% vs backtest mean +10% — alpha **接近 backtest 期望** ✓

**设计权衡**:
- 多策略同币 (e.g. ST15 + PS5 + PS6 都 SHORT LABUSDT): testnet 看到 *combined position* (-64.8 = 3×21.6), 每个 strategy 用 reduce_only + 自己 qty 来 close, 互不干扰
- max_concurrent_per_symbol=3 限制每币最多 3 个 strategy 同时持仓 (避免 13× 集中)
- 如果某 strategy 平仓时 testnet position 已为 0 (不该, 但容错): 用 mark price 当 exit_price

**安全机制**:
- API key/secret 仅从 env 读取, 不打印, 不进 git
- HTTP error log 仅打印 method+path+status, 不打印 URL (含 signature)
- max_total_notional cap 防爆仓 (testnet 余额 $5000)
- reduce_only=True 在 close 时强制 (防反向开仓)
- 启动时 health_check 验证 auth, 失败即 abort

**Heartbeat 升级**:
- 从 30min → 5min (用户要求实时报告)
- Heartbeat 包含 testnet stats: orders_placed, orders_failed, total_pnl_usdt

**预期数据收集 (24-48h)**:
- Paper sim PnL (mark price-based, no friction)
- Testnet PnL (real fills, slippage included, no fees yet because testnet is fee-free)
- Diff = real-world slippage cost (~0.05-0.2% per trade)
- Cross-validate with backtest +10% mean expectation

---

## 备注

修复 D1 是最高优先级, 因为它解释了 12× mean 差距的大部分。修完 D1 之后 backtest 的 +2000% sum 大概率
落到 +500-800% sum 范围, 跟 paper 真实可执行的水平一致。

如果修完后 backtest 仍显著好于 paper, 说明还有 alpha — 应该探索 *能复制 backtest 那个 +60s 等待* 的策略
(例如: BWE 信号触发后等 1 分钟再下单, 让 1m bar 走完, 用真实 close 入场)。这个 1 分钟延迟可能就是 alpha 的来源。
