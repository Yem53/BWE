# Execution And Paper Architect Memo

## Execution Readiness
The current artifacts are research-ready, not paper-ready. The execution model includes fee, slippage, latency, and missed-fill sensitivity, and the path resolution is `1m_trade_kline`. That is strong for research, but paper-shadow should require a signal schema and replay validator.

## Required Complete Strategy Payload
Every paper-shadow candidate must include:

- BWE trigger and channel.
- Trade/no-trade decision.
- Long/short/no-trade side.
- Entry timing and entry conditions.
- Initial risk rule.
- Holding monitor fields.
- Exit family and exit state machine.
- Fee/slippage/latency/missed-fill assumptions.
- Path-resolution declaration.
- Paper-only and live-disallowed flags.

## Execution Stress Evidence
|   latency_seconds |   rows |   strategies |   median_stressed |   p10_stressed |   min_stressed |   median_missed_fill |
|------------------:|-------:|-------------:|------------------:|---------------:|---------------:|---------------------:|
|                 0 |  20000 |        20000 |           16.3057 |        13.372  |        10.3158 |                  0   |
|                 1 |  20000 |        20000 |           16.2987 |        13.3651 |        10.3089 |                  2.5 |
|                 3 |  20000 |        20000 |           16.2918 |        13.3581 |        10.302  |                  7.5 |
|                 5 |  20000 |        20000 |           16.2878 |        13.3541 |        10.2979 |                 12.5 |
|                10 |  20000 |        20000 |           16.2817 |        13.348  |        10.2919 |                 25   |
|                30 |  20000 |        20000 |           16.2713 |        13.3377 |        10.2815 |                 75   |

The cost/latency degradation does not erase the top stressed candidates, which is encouraging. But the validator still needs to test whether the assumed entry timing can be executed in a paper feed without lookahead and without relying on unavailable intra-minute path information.

## Paper Path
The next generated config should be used for `focused_ablation_before_paper_shadow`. If that passes, then the subsequent paper-shadow plan can be created with strict no-order behavior and signal-only output.

## Decision
Do not emit paper-shadow signals from this round. Emit a paper-shadow design only after ablation confirms a cluster representative complete strategy.
