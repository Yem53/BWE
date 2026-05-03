# Hybrid Fallback Update

Created: 2026-05-03
Scope: `/Volumes/T9/BWE_codex/paper_test/v6_multi_8`

## Change

The paper runner now uses a hybrid feature path for long BWE-triggered entries:

1. Read BWE event from `/Volumes/T9_HOT/bwe_logs/bwe_matrix_posts.jsonl`.
2. Wait until the strategy `entry_delay_s` due time.
3. Load entry features from the local collector DB.
4. If a required public feature is missing or stale, refresh only that feature from Binance public REST.
5. Re-run the strategy condition check.
6. Open only after portfolio risk checks pass; fill still uses real-time mark price and demo/testnet market-order `avgPrice` when available.

## Fallback Fields

- `top_ratio`
- `global_ratio`
- `top_position_ratio`
- `quote_volume_24h`
- `mark_1m_age_ms`

Unsupported features are not guessed. `marketcap` and `move_pct` still come from the BWE message. `listing_age_days` still comes from `symbol_meta`.

## Guardrails

- DB remains the primary path because it is faster and auditable.
- REST fallback is only called for required fields that are missing or stale.
- If fallback fails, the pending entry is rejected with `skip_binance_fallback_failed`.
- Fallback use is counted in `api_fallback_count` and logged to `runtime/decisions.jsonl`.
- The logic does not use 1m kline close as entry price.

## Verification

- Unit tests passed: `python3 paper_test/v6_multi_8/tests/test_multi_paper_runner.py`
- Compile passed: `python3 -m py_compile paper_test/v6_multi_8/scripts/multi_paper_runner.py`
- Public REST smoke passed for `BTCUSDT`:
  - top trader account ratio: available
  - global account ratio: available
  - top trader position ratio: available
  - 24h quote volume: available
  - mark freshness: available

## Operational Note

This change does not repair the upstream BWE message writer. Paper can now tolerate stale public feature rows in the DB, but long entries still require fresh BWE posts to arrive.
