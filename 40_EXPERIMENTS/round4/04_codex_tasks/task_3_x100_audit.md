# Codex Task #3 — X100 Composite Exit Static Audit + R4 Grid Mock Distribution

## Mission

Audit the `composite_exit_be_partial_runner` exit kernel implementation that Round 3 morning_brief flagged with "-0.08 floor" anomaly. Verify whether it's a logic bug or a parameter-regime artifact, and predict its behavior under Round 4's wide-TP grid.

This unblocks Round 4 hygiene by either confirming X100 family is OK to keep (just needs better grid) OR flagging a real bug to fix.

## Hard safety rules

- **Read-only on the kernel source files**.
- No exchange API calls. No secrets.
- Do not touch `/Users/ye/.hermes/`.
- Write output **only** to `/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits/x100_audit_report.md`.

## Required reads

1. **`/Volumes/T9/BWE/20_CODE/Autoresearch/bwe_autoresearch/bwe_loop_exit_kernels.py:103-172`** — `eval_breakeven` kernel (the X100 family). Lines 152-163 are the outcome decision logic.
2. **`/Volumes/T9/BWE/20_CODE/Autoresearch/bwe_autoresearch/bwe_loop_exit_kernels.py:313-360`** — `classify_exit_family` to confirm `composite_exit_be_partial_runner` routes to BE kernel.
3. **`/Volumes/T9/BWE/40_EXPERIMENTS/morning_brief_latest.md`** — 引用 X100 -0.08 floor 警告原文（搜索 "X100" 或 "composite_exit_be_partial_runner"）。
4. **`/Volumes/T9/BWE/40_EXPERIMENTS/analysis/20260427_194910/summary.md`** Per Exit Family 表 — breakeven family n=1923 mean=-0.0956 n_pos=0。
5. **`/Volumes/T9/BWE/30_DATA/cache/normalized/trade_kline_1m_event_windows.parquet`** — D1 数据。需要 venv: `/tmp/codex_round4_venv/bin/python` with pyarrow + polars + numpy 已装好。

## Working hypothesis (you must confirm or reject)

`eval_breakeven` line 153: `gross_be = torch.zeros(...)` — when TP triggers and post-TP adverse touches 0 (BE invalidated), outcome forced to 0. Combined with cost subtraction line 164 `gross - cost_pct`, the floor is `-cost_pct`.

For Round 3 cost_pct=0.08 and many archetypes paired with TP=0.20%, BE triggers very fast (TP=0.20% is hit within the first few minutes for most events), then SL retraces to 0 → outcome 0 → net `0 - 0.08 = -0.08`. Hence the constant -0.08 across diverse entries.

**Predict**: Under R4 grid TP ∈ {5, 10, 25, 40, ...}%, BE trigger rate drops sharply (TP=25% rarely hits in 5h for most events), so outcomes shift toward `close_at_hold` — distribution changes substantially.

## What to verify

### 5.1 Static logic audit

- Confirm `gross_be = torch.zeros(...)` is the BE outcome, not a hardcoded floor.
- Confirm cost is subtracted **once** (line 164), not multiple times.
- Confirm there's no clipping / clamping that artificially produces -0.08 across all variants.
- Compare with `eval_trailing_pct` (line 172-225) and `eval_multi_tp_50_50` (line 231-310) for consistency in cost handling.

### 5.2 Empirical mock simulation

Use venv at `/tmp/codex_round4_venv/`:

```bash
/tmp/codex_round4_venv/bin/python -c "
import polars as pl
df = pl.read_parquet('/Volumes/T9/BWE/30_DATA/cache/normalized/trade_kline_1m_event_windows.parquet')
# ...
"
```

For each event:
1. Determine `entry_price` at minute_offset=0
2. For each TP in {0.20, 0.5, 1.0, 5.0, 10.0, 25.0, 50.0}: compute the FIRST minute_offset where high reaches TP
3. For events that triggered TP, check whether subsequent low touches 0 (= entry_price) → BE invalidated → outcome 0
4. For events that did NOT trigger TP, compute close_at_hold (use 5h as approximation)
5. Compute distribution of outcomes per TP level

Output a table showing:
| TP level | % events triggered TP | % triggered AND BE invalidated | % rode to close_at_hold | mean outcome (gross) |
|---|---|---|---|---|
| 0.20% | ~99% | ~80% | ~1% | ~0.0 (hits then BE invalidated dominates) |
| 5% | ~50% | ~25% | ~50% | ... |
| 25% | ~10% | ~5% | ~90% | ... |
| 50% | ~5% | ~3% | ~95% | ... |
...

### 5.3 Verdict

- **GREEN**: Logic is sound. Round 4 grid (TP 5-500%) will naturally fix the -0.08 floor. No code changes needed. → Round 4 ready.
- **YELLOW**: Logic is sound BUT empirical simulation shows BE family still produces narrow distribution under R4 grid (e.g. always sub-1% mean). → Suggest specific archetype param tweaks (BE trigger threshold > TP, etc).
- **RED**: Found a real bug. Specify line + suggested fix. R4 must wait.

## Output file

Write to: `/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits/x100_audit_report.md`

## Output format for your final response

Concise 中文, 5 sections:
- 静态 audit 结论：logic OK / found bug at line N
- 实测 mock 表：%TP triggered / %BE invalidated / mean outcome at 5 TP levels
- R4 grid 下预期：BE family 是否会从 -0.08 floor 解放
- Verdict：GREEN / YELLOW / RED + 具体动作建议
- 安全确认：未触动 ~/.hermes/, 未改 kernel 源码, output only in T9 round4/05_audits/
