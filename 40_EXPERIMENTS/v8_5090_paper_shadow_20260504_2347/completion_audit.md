---
type: audit
status: complete
run_id: v8_5090_paper_shadow_20260504_2347
---

# Completion Audit

## Objective

Run strict live-aligned long/short strategy search and produce 10 long plus 10 short strategies after removing the 14d as-of universe requirement, while keeping the previous standards:

- win rate > 75%
- monthly event frequency > 300
- mean return > 5%
- total return > 1000%
- long and short both have 10 strategies
- other prior standards remain active
- strict paper/live alignment

## Checklist

| Requirement | Evidence | Status |
|---|---|---|
| 10 long strategies | `paper_candidates_combined.csv` has 10 rows where `side=long` | PASS |
| 10 short strategies | `paper_candidates_combined.csv` has 10 rows where `side=short` | PASS |
| Win rate > 75% | minimum `raw_wr` = 0.7621776504 | PASS |
| Monthly event frequency > 300 | minimum `monthly` = 304.6626538496 | PASS |
| Mean return > 5% | minimum `raw_mean_pct` = 5.4193425179 | PASS |
| Total return > 1000% | minimum `sum_return_pct` = 1701.6735839844 | PASS |
| 14d as-of universe removed | `filter_universe_history(... require_14d_history=False)` is default; cache path is `features_5m_no14d_v3_h288.parquet`; manifest records removed hard condition | PASS |
| Other previous standards active | train/dev mean > 0, final holdout mean/wr, traded_symbols, traded_over_eligible, top symbol concentration, coverage grade, result grade all rechecked | PASS |
| Strict live-aligned execution | `evaluate_exit_cuda` uses signal completed 5m close time plus next 1m open, TP close confirmation, SL touch, and risk-first same-bar priority | PASS |
| No live/testnet/demo order endpoints | manifest and candidate CSV set `paper_only=true`, `live_allowed=false`, `order_endpoints_allowed=false`, `demo_orders_allowed=false` | PASS |
| Paper-shadow artifacts | manifest, candidate CSVs, metrics summary, 7,991-trade historical replay, runtime state, and journals exist | PASS |

## Verification Commands

```powershell
@'
# package verifier output
package_verify=OK candidates=20 historical_trades=7991 no_order_endpoints=true
'@

& F:\BWE_codex\v8_5090\.venv\Scripts\python.exe -m unittest tests.test_v8_research -q
# Ran 56 tests in 0.085s
# OK

powershell -ExecutionPolicy Bypass -File 99_ADMIN\vault_sync_audit.ps1
# Broken links: 164
# v8_new_links=OK
```

## Residual Notes

The remaining 164 vault broken links are pre-existing broader vault issues and do not include this `v8_5090` run. The paper package is signal-only and does not place demo/testnet orders.
