# bwe_v2 — Alerts & VPN Watchdog Spec v1
**Date**: 2026-04-29
**Approved by**: user (`没什么问题，你也觉得ok的对吧` + accepts 4 改动)
**Owner**: bwe_v2 monitoring layer

---

## 用户 4 项硬约束 (必须满足)

1. **精简播报** — only critical + entry/exit
2. **复用现有 2 bots** — `@BWE_trade_bot` (主, live), `@BWE_trade_test_bot` (test, paper smoke + scan)
3. **覆盖旧内容** — 老 OKX 通知全部废弃
4. **无主动 heartbeat** — 仅 `/status` DM 回应

## 4 项设计修正 (本次会话定稿)

| # | 修正点 | 内容 |
|---|---|---|
| C1 | T1.2 cap 公式 | `cap_loss_pct = pos_pct × leverage × raw_pct`; `cap_loss_$ = cap_loss_pct × cap` |
| C2 | T1.4 VPN 双阈值 | 有持仓 90s, 无持仓 5min |
| C3 | T1.5 Regression n 门槛 | `n ≥ 30` 才允许触发,避免 Phase 3 小样本误报 |
| C4 | 全部播报带 $ | 除百分比外,每条都附绝对美元数 (cap × pct) |

---

## 模块边界 (3 个新文件)

```
bwe_v2/
├── alert_formatter.py   纯函数,只产字符串,无 I/O,易测
├── alert_dispatcher.py  状态 + 去重 + Telegram 分发 (复用 telegram_hermes_bridge.send_message)
├── vpn_watchdog.py      binance API 健康轮询 + 指数退避 + 升级 T1.4
└── tests/
    ├── test_alert_formatter.py   ~30 tests (覆盖每条 mock)
    ├── test_alert_dispatcher.py  ~10 tests (dedup / rate-limit / routing)
    └── test_vpn_watchdog.py      ~8 tests (退避 / 阈值 / 升级)
```

---

## Telegram 播报清单 (定稿)

### Tier 1 — Critical (实时)

#### T1.1 Bot Down
```
🚨 BOT DOWN
process: bwe_live_autotrader
last_alive: 02:34 UTC
exit_signal: SIGTERM (code 1)
auto_restart: failed 3x
→ SSH macmini 手查
```

#### T1.2 Catastrophe (raw ≤ -15%)
```
🆘 CATASTROPHE
TRADOOR short  8%×3x  ($80 margin / $240 notional)
entry: 03:12 UTC @ 0.01240
now:   -16.3% raw  →  -3.91% cap (-$39.12)
status: force-closed
→ 复查 ExitConfig
```

公式:
- `cap_loss_pct = 8 × 3 × 16.3 / 100 = 3.91%`
- `cap_loss_$ = 3.91% × $1000 = $39.12`

#### T1.3 Liquidation
```
⛔ LIQUIDATION
ARIA short  5%×3x  ($50 margin / $150 notional)
liq_price: 1.847  (-23.4%)
loss: -3.51% cap (-$35.10)
day_liq_count: 2 / 累计 cap -5.4% (-$54)
```

#### T1.4 VPN Down (双阈值)

**有持仓 (90s):**
```
🌐 VPN DOWN  (敏感模式)
持仓: 2 个,SL 不能延迟
阈值: 90s
binance API 无响应: 1m47s
clash_verge 切换: 2 次失败
程序: 第 3 次重连中
```

**无持仓 (5min):**
```
🌐 VPN DOWN  (常规模式)
持仓: 0
阈值: 5min
binance API 无响应: 6m23s
程序: 第 4 次重连中
```

退避: 5s / 15s / 45s / 90s 指数。重连成功**静默**(不发).

#### T1.5 Regression (≥3d 连续 + n≥30)
```
📉 REGRESSION
window: 7d rolling
N: 47 ✓  (≥30 门槛过)
Layer A cap: +2.18% (+$21.80)  | baseline +5.07% (+$50.70) | -57%
Sharpe:      0.43              | baseline 1.21              | -64%
连续: 3d
→ 复盘 trades.json,决定是否 /pause
```

触发条件 (全部满足):
- `current_cap_pct < 0.5 × baseline_cap_pct`
- `n_trades >= 30`
- `consecutive_breach_days >= 3`

---

### Tier 2 — Trade Events (实时)

#### T2.1 Entry — Layer A (BWE)
```
🟢 ENTER A
TRADOOR short
score 83.6 | wave#3 | spike_decay × mean_revert
pos 8% ($80 margin) × 3x → notional $240
rule prime_fade
exit_cfg: trail 6/4 (wider)
@ 0.01237
```

#### T2.2 Entry — Layer B (Market scan)
```
🟡 ENTER B
ARIA short
score 89.2 | wave#5 | sustained × mixed
pos 5% ($50 margin) × 3x → notional $150
rule G_default_fade
exit_cfg: trail 5/4 (baseline)
@ 1.847
```

#### T2.3 Exit — TP
```
✅ EXIT TP
TRADOOR @ 0.01102  (-10.91% raw)
hold: 47min
pnl: +1.67% cap  (+$16.78 net of fees)
trigger: trail tier-1 (-6%)
```

#### T2.4 Exit — SL
```
❌ EXIT SL
ARIA @ 1.961  (+6.15% raw 反向)
hold: 22min
pnl: -0.92% cap  (-$9.22 net of fees)
trigger: SL (trail tier-0)
```

#### T2.5 Exit — Trail
```
🔄 EXIT TRAIL
RAVE @ 0.0814  (-7.42% raw)
peak 曾达 -10.4%
hold: 1h13min
pnl: +1.11% cap  (+$11.10)
trigger: trail back  (4% from peak)
```

---

### Tier 3 — 12h Digest (UTC 00:00 / 12:00)

```
📊 12h Digest | 2026-04-29 12:00 UTC

[Layer A · BWE]
trades 4  (2W/2L)
raw +12.4%  |  cap +1.86% (+$18.60)
Sharpe 1.18  |  DD -1.2% (-$12)

[Layer B · Market Scan]
trades 7  (4W/2L/1 trail)
raw +21.8%  |  cap +2.13% (+$21.30)
Sharpe 1.42  |  DD -2.1% (-$21)

[Top 3 Wins]
1. TRADOOR S  +$10.91  (raw +10.9%, 47m)
2. ARIA    S  +$8.20   (raw +8.2%, 1h13m)
3. RAVE    S  +$6.10   (raw +6.1%, 32m)

[Bottom 2 Losses]
1. AKE   L  -$6.20  (raw -6.2%, 22m)
2. BLESS S  -$5.80  (raw -5.8%, 18m)

[系统]
live: ✅ 11h47m
paper: ✅ 11h47m
vpn: ✅ (重连 0 次)
features 更新: ✅ 04:00 UTC

[Phase 进度]
当前 Phase 3 Ramped ($200)
累计 cap pnl: +4.21% (+$8.42)  ※ Phase 3 cap=$200
→ Phase 4 门槛:
   trades 23/30 ✗
   Sharpe 1.32 ✓  (≥1.0)
   DD 2.1%/20% ✓
```

---

### DM 命令 (用户主动询问)

#### `/status`
```
✅ healthy
live uptime: 11h47m
paper uptime: 11h47m
vpn: clash-verge auto-switch (0 重连)
持仓: 2 (TRADOOR-S 8%, ARIA-S 5%)
今日 cap pnl: +1.04% (+$10.40)
```

#### `/positions`
```
持仓 (3):
1. TRADOOR S  8%×3x  +6.7% (+$16.08)  hold 23m
2. ARIA    S  5%×3x  +2.1% (+$3.15)   hold 8m
3. RAVE    S  5%×3x  -1.2% (-$1.80)   hold 47s
```

#### `/pnl 7d`
```
7d cap pnl: +4.21% (+$42.10)
- Layer A (BWE):  +1.86% (+$18.60, 12 trades)
- Layer B (Scan): +2.35% (+$23.50, 28 trades)
Sharpe 1.34 | DD -3.2% (-$32)
```

#### `/pause`
```
✅ 已暂停新开仓
现有持仓继续 ExitConfig 管理
恢复: /resume
```

#### `/halt` (紧急)
```
🚨 已紧急平仓全部
reason: USER_HALT
持仓: 3 → 0
最终 cap pnl: +0.87% (+$8.70)
状态: HALTED  (重启需 SSH 手动)
```

---

## Bot 路由

| 事件类型 | `@BWE_trade_bot` (主) | `@BWE_trade_test_bot` (test) |
|---|---|---|
| T1.1-1.5 (live) | ✓ | — |
| T1.1-1.5 (paper smoke) | — | ✓ |
| T2 entry/exit (live) | ✓ | — |
| T2 entry/exit (paper) | — | ✓ |
| T3 12h digest | ✓ (合并 live+paper) | — |
| DM 命令 | ✓ | ✓ |

---

## VPN Watchdog 算法

```python
检查间隔: 30s
失败累计 → 触发重连尝试
退避: [5, 15, 45, 90] s 指数
连续失败 ≥ 阈值 (90s 有持仓 / 5min 无持仓) → T1.4 alert
重连成功 → 静默清状态,不发 alert
重连尝试 > 10 次 → 升级 T1.1 (BOT DOWN)
```

伪代码:
```python
def watchdog_loop():
    state = {"down_since": None, "attempt": 0, "alerted": False}
    while True:
        ok = ping_binance_api()  # GET /fapi/v1/time
        if ok:
            if state["down_since"]:
                LOG.info("vpn recovered after %ds", time.time() - state["down_since"])
            state = {"down_since": None, "attempt": 0, "alerted": False}
        else:
            if state["down_since"] is None:
                state["down_since"] = time.time()
            elapsed = time.time() - state["down_since"]
            threshold = 90 if has_open_positions() else 300
            if elapsed >= threshold and not state["alerted"]:
                send_t1_4_alert(elapsed, state["attempt"], has_positions=has_open_positions())
                state["alerted"] = True
            backoff = [5, 15, 45, 90][min(state["attempt"], 3)]
            state["attempt"] += 1
            time.sleep(backoff)
            continue
        time.sleep(30)
```

---

## 集成点

`bwe_live_autotrader.py` 已有 `notifications` 配置块。新建一个并行 `alerts_v2` 块:
```json
{
  "alerts_v2": {
    "enabled": true,
    "live_bot_token_env": "BWE_LIVE_BOT_TOKEN",
    "live_chat_id_env":   "BWE_LIVE_CHAT_ID",
    "test_bot_token_env": "BWE_TEST_BOT_TOKEN",
    "test_chat_id_env":   "BWE_TEST_CHAT_ID",
    "is_paper": false,
    "cap_usd":  1000,
    "regression_check_interval_min": 60,
    "digest_interval_hours": 12,
    "vpn_check_interval_sec": 30
  }
}
```

老 `notifications` 块标记为 `deprecated`,程序运行时优先 `alerts_v2`。
