---
type: moc
tags: [moc, references, pointers]
created: 2026-05-02
---

# 🔗 90 源数据指针 — MOC

> 外部数据 source 索引 + legacy reference.

## Existing Pointers

- [[FILE_INDEX_legacy_BWE_autoresearch|File Index — Legacy BWE Autoresearch]]
- [[DATA_SNAPSHOT_INDEX_legacy_BWE_autoresearch|Data Snapshot Index — Legacy]]

## External Sources

### Karpathy Autoresearch (architecture inspiration)
- GitHub: https://github.com/karpathy/autoresearch
- Local Mac clone: `/Users/ye/Desktop/Github/Autoresearch`
- Local T9 snapshot: `/Volumes/T9/BWE/20_CODE/Autoresearch/`

### Telegram raw exports (Mac only)
- `/Users/ye/Desktop/Telegram/方程式价格异动监测_history/result.json`
- `/Users/ye/Desktop/Telegram/方程式OI&Prce异动_history/result.json`
- `/Users/ye/Desktop/Telegram/方程式重大行情提醒 Important Price Alerts Only_history/result.json`

### Binance Endpoints
- fapi (Futures): `https://fapi.binance.com` (used for perp trading data)
- api (Spot): `https://api.binance.com` (1s kline, NOT supported in fapi)
- testnet: `https://testnet.binancefuture.com` (real orders on demo balance)

### Documentation
- Binance API docs: https://binance-docs.github.io/apidocs/futures/en/
- SQLite WAL: https://www.sqlite.org/wal.html
- Obsidian: https://obsidian.md/

## 相关

- [[../00_INDEX|HOME]]
