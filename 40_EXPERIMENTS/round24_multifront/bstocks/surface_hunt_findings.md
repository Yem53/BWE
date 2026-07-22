---
type: experiment
tags: [bstocks, data-surface, recon, round24]
created: 2026-06-11
status: done
---

# bStocks 公开行情面侦察结论 (2026-06-11)

任务: 找 Binance bStocks (MUB/SNDKB/CRCLB/NVDAB/TSLAB, 2026-06 上线的代币化美股) 的公开行情数据面。

## 一句话结论

**bStocks 本体没有公开 CEX 行情面**(只是 BNB Chain 上的转换凭证, 由 BTech Holdings 发行, 1:1 兑换、oracle 定价);
但侦察中发现 Binance 有**两个真实可采的"美股 on Binance"行情面**, 覆盖全部 5 只标的:

1. **Binance Alpha 的 Ondo 美股代币**(80 只, BSC 链)— Mac 可达, 已写好采集器 `capture_v2.py` 并验证落库
2. **USDⓈ-M 期货 TradFi 永续**(94 只: 80 美股 + 8 商品 + 3 pre-IPO + 3 韩股)— 标准 fapi, 仅 EC2 可达

## 排查证据(按路径)

| # | 路径 | 结果 | 证据 |
|---|------|------|------|
| 1 | `www.binance.com/bapi/asset/v2/public/asset-service/product/get-products?includeEtf=true` | ❌ 无 bStocks | HTTP 200, 1365 个产品(全 TRADING), 搜 MUB/SNDKB/CRCLB/NVDAB/TSLAB 仅命中 MUBARAK meme 币; 关键词 stock/tokenized/nvidia/tesla/micron/sandisk/circle 零命中 |
| 2 | 官方公告/媒体报道 | ⚠️ 无 API 细节 | crypto.news/The Defiant/CCN: bStocks 发于 BNB Chain, BTech 发行, Nest Trading 券商 + Alpaca 托管, "可转入钱包/DeFi"; 报道称"在 spot 交易"但 spot API 实测无此 symbol; binance.com 落地页 (`/en/bstocks`, `/en/stocks`) 被 JS challenge (HTTP 202), CMS 公告搜索 API 无 bStocks 条目 |
| 3 | Binance Alpha 段 | ❌ 无 bStocks 本体 / ✅ 发现 Ondo 美股面 | `bapi/defi/v1/public/wallet-direct/buw/wallet/cex/alpha/all/token/list` HTTP 200, 649 token; 无 NVDAB/TSLAB/...、无 "btech/bstock" 字样; 但有 80 只 `*on` 后缀 Ondo 美股代币 (NVDAon/TSLAon/CRCLon/MUon/SPYon/QQQon/AAPLon...), 字段含 `stockState:true` + `rwaInfo`(正股 ticker、multiplier、marketStatus、52w 区间) |
| 4 | EC2 (东京, api.binance.com 不被墙) | ❌ spot 无 / ✅ fapi 有 TradFi 段 | spot exchangeInfo 3591 symbol, `^(MUB|SNDKB|CRCLB|NVDAB|TSLAB)` 仅命中 MUBARAK*; **fapi exchangeInfo 786 symbol 中有 94 只 `TRADIFI_PERPETUAL`**, 含 NVDAUSDT/TSLAUSDT/CRCLUSDT/SNDKUSDT/MUUSDT (underlyingType=EQUITY, 全 TRADING) |
| 5 | 第三方退路 | 未深入 | 已无必要 — 路径 3/4 的面质量远高于 CG/CMC 聚合价 |

## 面 1: Binance Alpha · Ondo 美股代币(✅ 已接采集器)

- **端点**(Mac 可达, 无 key, 带浏览器 UA, 限速 ≥0.2s):
  - token 列表/元数据: `GET /bapi/defi/v1/public/wallet-direct/buw/wallet/cex/alpha/all/token/list`
  - 1m K线: `GET /bapi/defi/v1/public/alpha-trade/klines?symbol=ALPHA_692USDT&interval=1m&limit=5`(标准 kline 数组格式)
  - 24h ticker: `GET /bapi/defi/v1/public/alpha-trade/ticker?symbol=...`
  - 逐笔: `GET /bapi/defi/v1/public/alpha-trade/agg-trades?symbol=...&limit=50`
  - 盘口 depth: **404**(此面无公开 order book)
  - exchange-info: `GET /bapi/defi/v1/public/alpha-trade/get-exchange-info`
- **symbol 格式**: `ALPHA_<id>USDT`(NVDAon=ALPHA_692, TSLAon=ALPHA_745, CRCLon=ALPHA_742, MUon=ALPHA_786)
- **bStocks 5 标的覆盖 4/5**: SNDK 无 Ondo 版(SanDisk 缺)
- **流动性参考**(2026-06-11): NVDAon 24h $1.5M / CRCLon $3.0M / MUon $3.0M / TSLAon $1.0M; rwaInfo.marketStatus 显示 `overnight`(24/7 交易但有市况标记); 2026-02-12 上线 → **已有约 4 个月历史 K线可回补**
- **采集器**: `capture_v2.py`(同目录), 45s 验证: meta 4 行 + klines_1m 23 行 + ticker 8 行 + trades 215 行 ✅

## 面 2: USDⓈ-M TradFi 永续(fapi, 仅 EC2)

- 标准期货行情 API 全家桶可用 (klines/depth/aggTrades/fundingRate/openInterest/WS)
- **94 只 TRADIFI_PERPETUAL**:
  - EQUITY 80: AAPL/AMZN/GOOGL/META/MSFT/NVDA/TSLA/CRCL/SNDK/MU/COIN/HOOD/MSTR/SPY/QQQ/IWM/PLTR/GME/BRKB/JPM/WMT/...USDT
  - COMMODITY 8: XAU/XAG/CL/BZ/NATGAS/COPPER/XPD/XPT
  - PREMARKET 3: OPENAIUSDT / ANTHROPICUSDT / SPCXUSDT (pre-IPO 永续!)
  - KR_EQUITY 3: SAMSUNG/SKHYNIX/HYUNDAI
- 6 月以来几乎每天有 "Binance Futures Will Launch Multiple USDⓈ-Margined TradFi Perpetual Contracts" 公告 → 段在快速扩张, 新合约首日 = 同样的"做市未紧"窗口
- 现有 bwe_scanner 已在 EC2 上以 REST 轮询 fapi — 接入成本极低(把 TRADIFI symbol 加进 universe 即可)

## bStocks 本体为什么没有面(最可能解释)

1. 当前形态是**转换凭证**: Binance 券商账户里的正股 ↔ BNB Chain 代币 1:1 兑换, oracle 跟价, 不是订单簿交易品
2. 媒体说的 "24/7 在 Binance 交易" 实际指向 Alpha 上的 Ondo 代币 + TradFi 永续这两个面(或 app 内功能), bStock token 本身尚未挂任何公开撮合引擎
3. 可能存在 app-only / 地区门槛(美股券商功能本身就分地区), 公网 API 未开放

## 复查建议

- 每周重跑一次: ① spot exchangeInfo grep `(MUB|SNDKB|CRCLB|NVDAB|TSLAB)USDT` ② Alpha token list grep `btech|bstock|B"` 新后缀 ③ 公告 catalog 48 grep "bStock"
- 若 bStocks 开放交易, 大概率先出现在 Alpha 段(它已有 stockState/rwaInfo 基建)— alphaId 会是新的 `ALPHA_8xx`
- 链上备选: bStocks 是 BSC 代币, 若拿到合约地址可直接监听 DEX 池(本轮未深入, 因 CEX 面更优)

## Sources

- [crypto.news — Binance launches bStocks with 24/7 trading](https://crypto.news/binance-launches-bstocks-with-24-7-trading-for-tokenized-u-s-equities/)
- [The Defiant — Binance Converts Stock Holdings Into On-Chain Tokens](https://thedefiant.io/converge/tradfi-and-fintech/binance-launches-bstocks-tokenized-us-equities-24-7-onchain-trading)
- [CCN — Binance to Offer 7,000 US Stocks, Plans Tokenized bStocks on BNB Chain](https://www.ccn.com/news/crypto/binance-us-stocks-etfs-tokenized-bstocks-bnb-chain/)
- [PRNewswire — Binance Launches US Stocks Trading and Previews bStocks](https://www.prnewswire.com/news-releases/binance-launches-us-stocks-trading-and-previews-bstocks-tokenized-securities-302787226.html)
- [Fortune — Binance adds U.S. stocks in super app push](https://fortune.com/2026/06/01/binance-adds-u-s-stocks-in-super-app-push-plans-to-launch-tokenized-shares/)
- [news.bitcoin.com — Binance stock-trading pulls in $400M first week](https://news.bitcoin.com/binance-stock-trading-400-million-bstocks/)
