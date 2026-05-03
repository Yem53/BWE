# Round 6 Audit Findings — BWE Architecture Bug (2026-04-30)

## TL;DR

User caught me building v2/v3 with a fundamental architectural mistake. I treated BWE telegram messages as the **data source**; user's intent is messages = **attention pointers** to a symbol, then query **real-time binance data** for actual decisions.

**This single misunderstanding cascaded into 6 structural errors that shrunk v2/v3's alpha space significantly.**

## What was wrong

### 1. Parser drops 47% of pricechange-monitor events
- `src/events.py::_classify_direction` requires 🟢/🔻 emoji or `surged/飙升/drop/下跌` keywords
- BWE_pricechange_monitor uses 中文 "上涨"/"下跌" without emoji
- "下跌" matches → 1,403 dumps captured ✅
- "上涨" doesn't match → **1,328 pumps silently dropped** ❌
- Result: ALL pricechange-pump events missing for 30d. LONG strategies completely starved.

### 2. Channel whitelist too narrow (3 of 14)
- Used: BWE_OI_Price_monitor, BWE_pricechange_monitor, BWE_Reserved6
- **Skipped: BWE_Binance_monitor (74 events), bwe_korean_monitor (87), BWEnews (46)**
- Skipped channels are known huge pump catalysts (Binance/Upbit listings)
- 30 days without seeing a single binance/upbit listing event in our pipeline

### 3. No real-time data fetcher
- All decisions made on 30d historical cache + parsed message text
- Should query live binance API for: funding NOW, OI rolling 1m/5m, orderbook depth, CVD, BTC concurrent action
- Cache shim ≠ real DB ≠ live API — already burnt by this in stage3/v3 fix

### 4-6. Other issues
- Trust message-text magnitude (should compute from K-lines)
- Reserved6/OI/pricechange treated as equivalent in resonance (they have different latency profiles)
- Cache shim drift between stage1/2 and stage3 (fixed in commit 26159dd)

## Decision

**Round 5 closes here.** v2/v3 winners are validated within their (constrained) data view. Paper-shadow continues running on PID 14005 to confirm v2/v3 backtest fidelity in real-time.

**Round 6 will rebuild from architecture up:**

```
14 BWE channels listener → symbol extractor → RealtimeSnapshot fetcher → 
strategy engine (predicates over snapshot, not over message text) → executor
```

Full audit + brainstorm seed at:
`/Volumes/T9/BWE/40_EXPERIMENTS/round5/specs/2026-04-30-round6-architecture-audit.md`

## State preserved

- Paper-shadow PID 14005 alive, processing live BWE events with v2/v3 4-strategy spec
- All Round 5 commits intact (last: c199949)
- 5 v3 winners persisted in stage3/v3/
- v2 archive at _archive/v2_full_grid/
- Round 6 work happens in 40_EXPERIMENTS/round6/ (new dir, not yet created)

## User preferences captured (Round 6 inputs)

- "BWE 消息只是触发器，真实数据来自实时 binance"
- "扩到所有 14 个频道找 alpha"
- "实时查 funding/OI/orderbook 不是查 30 天 cache"
- "找 LONG alpha — 之前漏了一半"
- "请审查全部流程低级错误" → 6 错误已找到，可能还有

## Next session: Round 6 brainstorm

Topics for user when they return:
1. Confirm Layer 3 (real-time fetcher) architecture
2. Pick which non-3 channels to add (P0: Binance/Korean/News listings)
3. RealtimeSnapshot schema
4. Backfill plan: rebuild 30d backtest under new architecture
5. New LONG-side strategy templates
6. Migration plan from v3 winners
