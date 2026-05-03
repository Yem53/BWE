# Execution/Paper Architect Round 1 Memo

## Paper Path
The next phase should emit paper-shadow signals only after a candidate survives the expanded Round 1 review and a focused ablation pass. The signal payload must include entry trigger, side, timing, initial risk, monitoring fields, exit state, and execution-cost assumptions.

## Gate
No candidate moves beyond paper-shadow planning unless the same full strategy object remains positive after fee, slippage, latency, and missed-fill stress.

## Payload Requirements
- BWE trigger and channel.
- Trade/no-trade decision.
- Long/short/no-trade side.
- Entry timing and entry conditions.
- Initial risk rule.
- Holding monitor fields.
- Exit state-machine family.
- Fee, slippage, latency, missed-fill assumptions.

## Validation Path
The generated next-round config is a research config. It should feed a paper-shadow validator only after focused ablations refresh the ledger and the gate decision changes from hold to paper probe.
