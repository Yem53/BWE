# Execution And Paper Architect Long Memo

## Execution Status
The execution model includes fee, slippage, latency, and missed-fill stress, and the path resolution is `1m_trade_kline`. That is sufficient for research screening, not sufficient for live-like fill claims.

## Paper Payload Must Include
- BWE trigger.
- trade/no-trade.
- long/short/no_trade.
- entry timing.
- entry conditions.
- initial risk.
- holding monitor fields.
- exit state machine.
- fee/slippage/latency/missed-fill assumptions.
- paper-only flag.

## Gate
Paper-shadow opens only after a complete strategy survives focused ablation and replay validation. Current gate remains closed.
