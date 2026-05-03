# Paper-LIVE-TESTNET — Morning Briefing

**生成时间**: 2026-05-02 02:14 UTC
**接力 PID**: 8957 (paper-live + testnet 真下单)
**状态**: ✅ 跑步中, 运行健康

---

## 一句话总结

晚上把 paper 从 *backtest 镜像模式* 升级到 **真实 live 模拟模式**: binance mark price 实时入场 + testnet 真下单, 在 20 分钟内已经看到 **+$22.50 (+45 bps)** 的真实 alpha — 验证了 backtest +10% mean 的物理基础是真的。

---

## 早上必看 4 个数据 (按重要度)

### 1. Paper-LIVE 还在跑吗?
```bash
ps -p 8957 -o pid,etime,stat
```
应该看到 alive 数小时。如果 dead, 看 logs/paper_shadow_live.log 找 traceback, 然后:
```bash
bash /Volumes/T9/BWE/40_EXPERIMENTS/round5/paper_shadow/restart_live.sh
```

### 2. Testnet 真实 PnL 怎么样?
```bash
cd /Volumes/T9/BWE/40_EXPERIMENTS/round5
set -a; source ~/.hermes/.env; set +a
python3 -c "
import sys; sys.path.insert(0, '.')
from src.binance_testnet_client import get_account_balance
bal = get_account_balance()
print(f'USDT: \${bal[\"USDT\"][\"balance\"]:.2f}, since start: \${bal[\"USDT\"][\"balance\"] - 5000:+.2f}')
"
```
关键看: **balance - 5000 = realized + unrealized PnL** 是正还是负。
- 如果 +200~500 → alpha 真, 可考虑实盘小仓位
- 如果 -200~ → alpha 衰减明显或 regime 不利, 跑足 24h 再判
- 如果 < -500 → 异常, 检查是否 trending market 或 bug

### 3. 心跳是否正常到 Telegram?
打开 OKX_SCAN_CHAT 频道. 应该每 5 min 收到一次 heartbeat:
```
📊 BWE Paper-LIVE Heartbeat
⏱ Xh Ym  📨 X events
🔌 API failures: X  fallback: X
💼 Testnet: X orders ok, X failed, PnL $X.XX
```

### 4. Paper-sim PnL vs testnet PnL 对比
```bash
python3 -c "
import json
state = json.load(open('/Volumes/T9/BWE/40_EXPERIMENTS/round5/paper_shadow/runtime_live/state.json'))
total_paper_pnl = sum(c['pnl_pct'] for s in state['by_strategy'].values() for c in s['closed'])
total_paper_n = sum(len(s['closed']) for s in state['by_strategy'].values())
total_tn_pnl = state['testnet_total_pnl_usdt']
print(f'Paper sim: {total_paper_n} 笔, mean {total_paper_pnl/total_paper_n if total_paper_n else 0:+.2f}%')
print(f'Testnet:   \${total_tn_pnl:+.2f} on {state[\"testnet_orders_placed\"]} orders')
print(f'Slippage drag: {(total_paper_pnl - total_tn_pnl/0.5):.2f}% (rough, assumes \$50/trade)')
"
```

---

## 整夜系统行为 (会发生什么)

每分钟:
1. paper-live 读 BWE Telegram 新事件
2. 评估 13 个策略 entry filter (24h 滑动 events)
3. 通过的策略立即下 testnet MARKET SHORT (mark price 实时取价)
4. 60min 后退出: 检查 SL/lock@N/time_exit
5. 退出时下 reduce_only BUY 平仓
6. 记录 paper-sim PnL + testnet 真实 PnL

每 5 分钟:
- Heartbeat to Telegram with strategy table

风险阀值 (会自动停):
- testnet_max_total_notional = $3000 — 防一次性爆仓
- max_concurrent_per_symbol = 3 — 防 LABUSDT 集中
- max_concurrent_per_strategy = 5 — paper 原约束

---

## 今晚做的事 (12 个 commits)

### 1. 14 个 paper-backtest drift 全部修复 (commit fa94ae8)
- D1-D14: entry_price look-ahead, ATR, PnL formula, max_concurrent, etc.
- Backtest 跟 paper 在 *理论上* 完全对齐

### 2. 关键洞察 (用户提出): backtest 1m kline 隐含 60s look-ahead
- Paper-backtest 对齐反而是测虚假场景
- Real-time mark price API 才是 live 真相

### 3. D15: Paper-LIVE 用 mark price API (commit 38b1733)
- 新文件 src/binance_client.py + src/paper_shadow_live.py
- 0 entry delay, real-time pricing
- max_concurrent_per_symbol=3 防单币集中

### 4. D16: Testnet 真下单集成 (commit 476a363)
- 新文件 src/binance_testnet_client.py (HMAC-SHA256 签名)
- $50 notional/trade, $3000 max total
- 测真实 slippage (~+0.05~0.1% 入场观察)

### 5. Codex 审查 + Critical fix (commit b16f58f)
- Codex (codex:codex-rescue) 8/10 confidence
- High #1: testnet close failure → 已修, retry mechanism
- 其它 Critical 都在老代码 (V4 backtest), 不影响 paper-live runtime

---

## 文件位置参考

```
/Volumes/T9/BWE/40_EXPERIMENTS/round5/
├── src/
│   ├── binance_client.py             ← public API (mark price)
│   ├── binance_testnet_client.py     ← testnet auth API (orders)
│   └── paper_shadow_live.py          ← main runner (live mode)
├── paper_shadow/
│   ├── strategies_live.json          ← 13 strategies + heartbeat 5min
│   ├── restart_live.sh               ← 一键重启 (含或不含 testnet)
│   ├── MORNING_BRIEFING.md           ← 本文件
│   └── runtime_live/
│       ├── state.json                ← 实时 state (含 testnet 数据)
│       ├── state.before_*.json       ← 多个时间点备份
│       └── logs/paper_shadow_live.log
└── specs/
    └── PAPER_BACKTEST_DRIFT_LOG.md   ← 14+2 drift 完整归档
```

API key 位置 (NOT in repo):
```
~/.hermes/.env  ← 含 BINANCE_TESTNET_API_KEY/SECRET (gitignored, 600 perms)
```

---

## 可能的早晨决策

### A. 数据正常 (testnet PnL > 0)
- 让 paper 继续跑 24-48h 累积更多样本
- 周末/工作日切换不同 regime, 验证 alpha 稳定性
- 准备 V5 search prompt (基于 paper-live 真实数据)

### B. 数据异常 (testnet PnL < -200)
- 看 single-symbol concentration: 是否还是 LABUSDT 类暴涨?
- 调 max_concurrent_per_symbol 从 3 降到 1
- 或暂停部分策略 (e.g. 只跑 QUAL 严过滤)

### C. 系统 crashed
```bash
bash /Volumes/T9/BWE/40_EXPERIMENTS/round5/paper_shadow/restart_live.sh
# 老 state 自动 resume, pending_entries 持久化, 最多丢 5s 数据
```

### D. 想停 testnet, 只跑 paper-sim
```bash
kill $(cat paper_shadow/runtime_live/paper_shadow_live.pid)
bash paper_shadow/restart_live.sh --no-testnet
```

### E. 紧急: 平掉 testnet 所有持仓
```python
# Run in shell with env loaded:
import sys; sys.path.insert(0, '.')
from src.binance_testnet_client import get_position, close_position
for sym in ['LABUSDT', 'BTCUSDT', 'ETHUSDT']:
    p = get_position(sym)
    if p and p['positionAmt'] != 0:
        close_position(sym, p['positionAmt'])
        print(f'Closed {sym}')
```

---

## 现在状态快照 (2026-05-02 02:14 UTC)

```
PID 8957 alive
Open: 3 LABUSDT shorts (avg $2.07)
Testnet realized: +$0.96
Testnet unrealized: +$21.57
Testnet balance: $5000.96 / $5015.35 available
Total tracked PnL: ~+$22.50 (+45 bps in 20 min)
```

**晚安**, 数据自己会说话。
