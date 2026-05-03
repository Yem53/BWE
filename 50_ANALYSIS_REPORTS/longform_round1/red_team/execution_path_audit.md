# Execution Path Audit

## Path Precision
The run uses `1m_trade_kline`. This is much better than mark-only fallback, but it is still not tick replay.

## Concern
State-machine and trailing exits can look better when the path ordering inside the minute is favorable or simplified.

## Mitigation
Before paper-shadow, replay the candidate with the exact paper feed and record:

- entry availability at chosen timing,
- fill/missed-fill behavior,
- exit path ordering,
- fee/slippage/latency sensitivity,
- no future data usage.
