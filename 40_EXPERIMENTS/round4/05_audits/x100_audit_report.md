# X100 Composite Exit Static Audit + R4 Grid Mock Distribution

Date: 2026-04-27

## 1. Static Audit Conclusion

Verdict: logic OK. No kernel source bug found in `composite_exit_be_partial_runner` routing or the breakeven outcome logic.

Evidence:

- `classify_exit_family()` routes `composite_exit_be...` to `breakeven`: `s.startswith("composite_exit_be")` returns `"breakeven"` at `bwe_loop_exit_kernels.py:331-332`.
- In `eval_breakeven()`, `gross_be = torch.zeros(...)` at line 153 is the intended gross breakeven outcome after TP has fired and price later touches entry. It is not a hardcoded net floor.
- Outcome decision at lines 156-164 is:
  - SL first: `gross = -SL`
  - TP first and post-TP entry retouch: `gross = 0`
  - TP first without retouch: `gross = close_at_hold`
  - no TP/SL: `gross = close_at_hold`
- Cost is subtracted once for breakeven at line 164: `out = gross - cost_pct`.
- No clipping or clamping was found in the breakeven branch that would artificially force all variants to `-0.08`.
- Cost handling is consistent with `eval_trailing_pct()` line 223, which also subtracts `cost_pct` once. `eval_multi_tp_50_50()` intentionally differs at lines 303-305 by using a two-leg cost approximation when TP1 hits.

Interpretation: the Round 3 `-0.08` floor is a parameter-regime artifact. If `cost_pct=0.08`, then BE-invalidated outcomes have gross `0`, net `-0.08`.

## 2. Source Warning Checked

Morning brief warning:

> `composite_exit_be_partial_runner_floor` -- Stop pairing X100 with new entries until exit-side hypothesis is sharper; use fixed exit as default exit_id

Round 3 family summary confirms the anomaly:

| Exit family | n | mean | median | p75 | max | n_pos |
|---|---:|---:|---:|---:|---:|---:|
| breakeven | 1,923 | -0.0956 | -0.0805 | -0.0800 | -0.0800 | 0 |

This is consistent with many variants landing at gross BE `0` minus one cost unit.

## 3. Empirical Mock Simulation

Dataset: `/Volumes/T9/BWE/30_DATA/cache/normalized/trade_kline_1m_event_windows.parquet`

Method:

- Used `trade_open` at `minute_offset=0` as entry price.
- Used rows from `minute_offset=0..300` as 5h approximation.
- Long-side approximation only: TP triggers when `trade_high >= entry * (1 + TP%)`.
- BE invalidates when any subsequent row after first TP has `trade_low <= entry`.
- If no TP trigger, gross outcome is 5h `close_at_hold`.
- If TP triggers and BE invalidates, gross outcome is `0`.
- Event count: 7,317.

| TP level | % events triggered TP | % all events TP+BE invalidated | % rode to close_at_hold | mean outcome gross | median gross | p10 gross | p90 gross |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.20% | 98.21% | 92.95% | 1.79% | +1.3785% | +0.0000% | +0.0000% | +0.0000% |
| 0.50% | 95.78% | 85.55% | 4.22% | +2.1279% | +0.0000% | +0.0000% | +1.2338% |
| 1.00% | 92.52% | 75.47% | 7.48% | +3.1750% | +0.0000% | +0.0000% | +15.8679% |
| 5.00% | 78.17% | 41.40% | 21.83% | +6.5345% | +0.0000% | -16.7890% | +40.0314% |
| 10.00% | 67.06% | 25.52% | 32.94% | +6.5942% | +0.0000% | -29.1196% | +44.2369% |
| 25.00% | 44.43% | 10.48% | 55.57% | +6.4014% | +2.3234% | -35.6167% | +46.3572% |
| 50.00% | 22.10% | 4.10% | 77.90% | +6.2674% | +3.5589% | -36.7633% | +46.7102% |

Note: `% all events TP+BE invalidated` is measured as share of all events, not share of triggered events. Among triggered events, invalidation drops from about 94.6% at TP=0.20% to about 18.5% at TP=50%.

## 4. R4 Grid Expectation

The working hypothesis is confirmed.

Round 3's tight TP regime, especially TP around 0.20%, triggers on almost every event and then frequently retouches entry. That makes the BE branch output gross `0`, and net becomes `-cost_pct`, producing the observed `-0.08` floor.

Under wider Round 4 TP values:

- TP trigger rate drops materially as TP widens.
- BE invalidation rate drops sharply.
- More events fall through to `close_at_hold`.
- Distribution stops being pinned to gross `0` / net `-cost_pct`.

The R4 wide-TP grid should therefore release the X100 breakeven family from the Round 3 `-0.08` floor, though the family still needs normal empirical ranking because high TP values expose more close-at-hold tail risk.

## 5. Verdict and Actions

Verdict: GREEN.

Recommended action:

- Keep X100 / `composite_exit_be_partial_runner` eligible for Round 4.
- Do not patch the kernel for this anomaly.
- Avoid interpreting the R3 `-0.08` cluster as a code bug; treat it as evidence that tight BE trigger settings are too saturated.
- Prefer R4 grids where TP starts at wider thresholds such as 5%, 10%, 25%, and above for this exit family.
- For future tuning, monitor triggered-and-invalidated rate directly; if it remains high, raise the BE activation threshold or separate BE trigger from nominal TP.

## 6. Safety Confirmation

- Did not modify kernel source files.
- Did not call exchange APIs.
- Did not access or modify secrets.
- Did not touch `/Users/ye/.hermes/`.
- Wrote output only to `/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits/x100_audit_report.md`.
