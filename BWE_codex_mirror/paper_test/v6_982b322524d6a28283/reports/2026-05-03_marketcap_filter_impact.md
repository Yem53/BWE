# Market Cap Filter Impact

Generated: 2026-05-03

## Verdict

`marketcap <= 71M` is a real regime filter. It likely contributes to the alpha because the strategy is selecting small-cap BWE pump events where crowd/sentiment imbalance behaves differently.

It does not make the strict replay result a one-symbol artifact: the strict-passing row has `539` replayed trades, `111` symbols, and top-symbol share `5.19%`.

But it does reduce universality. This is not a full-Binance scanner strategy. It is a BWE-triggered small-cap long strategy.

## Current Local Counts

Binance futures metadata in the local hot DB currently shows:

- Active USDT perpetual symbols: `535`

Binance futures metadata does not include market cap. Market cap must come from BWE text/features or an external market-cap provider.

Using current BWE post log snapshots:

- Symbols with BWE market-cap snapshot: `234`
- Active USDT perpetuals with BWE market-cap snapshot: `177`
- Active USDT perpetuals with BWE market-cap `<= 71M`: `115`
- Missing market cap among active USDT perpetuals: `358`

Using the 30-day BWE feature parquet joined to current active USDT perpetuals:

- Active USDT perpetuals with 30-day BWE market-cap snapshot: `302`
- Active USDT perpetuals with 30-day BWE market-cap `<= 71M`: `200`
- Missing market cap among current active USDT perpetuals: `233`

## Interpretation

The exact answer to "how many Binance contracts have MC < 71M" is not available from Binance alone. The defensible local answer is:

- Current BWE live-log lower-bound: `115`
- 30-day BWE feature snapshot: `200`
- Exact all-Binance count: unknown without a current external market-cap source covering all active futures symbols.

Paper runner policy:

- Missing market cap is `skip_missing_marketcap`.
- Missing market cap is never treated as pass.
- This prevents the backtest/paper gap from silently improving results by excluding unknown symbols without being counted.
