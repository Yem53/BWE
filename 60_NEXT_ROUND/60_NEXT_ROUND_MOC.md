---
type: moc
tags: [moc, planning, next-round]
created: 2026-05-02
---

# 🚀 60 下一轮 — MOC

> V5 search prompt + Round 6 audit + 待启动方向.

## V5 Search (即将启动)

- [[../40_EXPERIMENTS/round5/specs/2026-05-01-v5-search-prompt|V5 Search Prompt]]
- 30d backtest grid:
  - 4 bar shape × 3 magnitude × 3 side × 4 hold time × 3 regime = 432 specs
  - Or 6 bar shape × 5 hold time × 3 side × ... = 1296 specs
- 用 1s kline (after backfill complete) 量化 真实 alpha
- 找 conditional dual-side winners

## Round 6 Architecture Rebuild

- [[../40_EXPERIMENTS/round5/specs/2026-04-30-round6-architecture-audit|Round 6 Audit Findings]]
- 用户洞察: BWE 消息是 *指针* (pointer), 不是 *数据源* — 应实时拉 binance 数据
- 当前 parser 漏掉 47% pricechange-pump events
- 11 of 14 channels 被忽略 (含 binance/upbit listing alerts)
- LT3 LONG strategies structurally broken
- 完整 architecture rebuild

## 待启动 Items

### High Priority
- [ ] V5 search 实施 (30d × 1296 specs)
- [ ] Conditional dual-side strategy (LONG+SHORT regime detection)
- [ ] Wick reversion exit-mode 测试
- [ ] Per-symbol cooldown 加 paper-LIVE
- [ ] Strategy ordering randomization (修 ST15 主导 bias)
- [ ] aggTrades-based 真 1s perp data (历史 ~3天 only)

### Medium Priority
- [ ] LT1-4 LONG strategies 部署到 paper
- [ ] V5 winner 部署到 paper-LIVE 第二轮
- [ ] APFS migration evaluation (after 1 month exFAT data)
- [ ] Codex audit Round 6 architecture proposals

### Low Priority
- [ ] 自动 V5 grid 用 5090 GPU 加速 (用户暂不 use 5090)
- [ ] Mobile dashboard for paper-LIVE
- [ ] Regime detection 算法 (6h chg vs BTC 平稳)

## V5 Strategy Search Variables

```
变量 1: Bar shape — TREND / WICK_TOP / WICK_BOTTOM / BALANCED
变量 2: 1m pump magnitude — 3-5%, 5-10%, >10%
变量 3: Side — LONG / SHORT / Conditional
变量 4: Hold time — 5m / 15m / 30m / 60m
变量 5: 6h cumulative — <10% / 10-30% / >30%
变量 6: BTC regime — quiet / pump / dump
```

## 相关

- [[../00_INDEX|HOME]]
- [[../40_EXPERIMENTS/40_EXPERIMENTS_MOC|40 Experiments]]
