# Round 4 Per-Symbol Strategy — Archive

**Date range**: 2026-04-28 → 2026-04-29
**Project**: BWE Autoresearch — 妖币 trading strategy with per-symbol differentiation

This archive freezes every stage's findings + raw data + scripts so we can:
- 复盘 (retrospective): see how each design decision was made and why
- 回溯 (rollback): if any future change degrades performance, compare to baseline
- 复现 (reproduce): re-run any analysis from same inputs

---

## Master Timeline (chronological)

| Phase | When | Doc | TLDR |
|---|---|---|---|
| **1 — Initial brainstorm** | 04-28 morning | [01_phase1_initial_brainstorm.md](01_phase1_initial_brainstorm.md) | exit_v2 module + 5d data + 7-rule engine |
| **2 — 30d data validation** | 04-28 night → 04-29 morning | [02_phase2_30d_validation.md](02_phase2_30d_validation.md) | Full-market 30d backfill + 4 analyses re-run |
| **3 — L1-L4 layer validation** | 04-29 morning | [03_phase3_layer_validation.md](03_phase3_layer_validation.md) | Apples-to-apples comparison Hermes + broader market |
| **4 — Optimization tests** | 04-29 noon | [04_phase4_optimization.md](04_phase4_optimization.md) | Tuned BWE L2 + Broader L4 variants → final picks |

---

## Final decisions (locked-in 2026-04-29)

1. **BWE entry layer**: **L2-per-lifecycle** (sustained/late_burst → wider trail; spike_decay → tighter)
2. **Broader market entry layer**: **L4-tier-3-5-8-12** (rule-derived direction + 4-bucket pos sizing)
3. **Hybrid**: BWE 信号 → L2-per-lifecycle exit; 市场扫描信号 → L4-tier exit/sizing

详见 [00_decision_log.md](00_decision_log.md) 的完整决策时间线。

---

## File index

### Specs
- `archive/per_symbol_design_v1.md` — old spec (rule engine focus,decommissioned)
- `../per_symbol_design_v2.md` — **NEW final spec** with hybrid architecture

### Phase findings (this archive)
- `00_decision_log.md` — every user decision + rationale
- `01_phase1_initial_brainstorm.md`
- `02_phase2_30d_validation.md`
- `03_phase3_layer_validation.md`
- `04_phase4_optimization.md`

### Raw data outputs (in `/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits/`)
- `yaobi_score_v0.json` — 5d initial score (535 syms)
- `yaobi_score_v1_30d.json` — 30d final score (530 syms)
- `yaobi_per_symbol_dive.json` — 5d per-symbol deep dive (top 100)
- `yaobi_per_symbol_dive_v1_30d.json` — 30d per-symbol deep dive (top 100, 1407 waves)
- `rule_discovery.json` / `rule_discovery_v1_30d.json` — data-driven rule discovery
- `rule_engine_simulation.json` / `rule_engine_simulation_v1_30d.json` — rule engine PnL sim
- `three_layer_v3_l35.json` — L1/L2/L3/L3.5/L3.5b on Hermes 82+210 trades
- `market_layers_v3.json` — L1/L2/L3/L3.5/L3.5b/L4 on 1425 broader-market events
- `exit_v2_backtest_results.json` — 13 ExitConfig variants on Hermes
- `market_scan_exit_v2.json` — original 226-event market scan (5d)

### Scripts (in `/Volumes/T9/BWE/40_EXPERIMENTS/round4/scripts/`)
**Production**:
- `pull_binance_parallel.py` — 30d kline + OI + 3 long-short backfill (all 530 syms via Proton VPN, 4 workers)

**Analysis (research-only, throwaway)**:
- `yaobi_score_explorer.py` (5d) / `yaobi_score_explorer_v2.py` (30d)
- `yaobi_per_symbol_deep_dive.py` (5d) / `_v2.py` (30d)
- `rule_discovery.py` (5d) / `_v2.py` (30d)
- `rule_engine_simulation.py` (5d) / `_v2.py` (30d)
- `three_layer_comparison.py` (5d) / `_v2.py` (30d) / `_v3.py` (with L3.5/L3.5b)
- `market_scan_exit_v2.py` — 5d 226 events
- `market_layers_validation.py` — 30d 1425 events L1-L4
- `optimization_tests.py` — final L2/L4 variant tests

**Live system (Hermes)**:
- `binance_24h_ticker_collector.py` — new 24h ticker collector
- `collectors_watchdog.sh` — auto-recovery for collectors

### exit_v2 module (production-ready)
- `/Volumes/T9/BWE/40_EXPERIMENTS/round4/exit_v2/exit_v2.py` — with G2 TRADOOR-saver
- `exit_v2/integration_spec.md` — how to plug into live bot
- `exit_v2/通俗解释_策略改进.md` — Chinese plain-language explanation

---

## Quick rollback playbook

If a future change breaks something, refer to:
1. **Decision log** — what was the original rationale?
2. **Phase findings** — what data drove the decision?
3. **Raw JSONs** — re-run any analysis with same input

Compare new metric to archived baseline:
- Baseline mean_cap on Hermes LIVE (L2-base): **+0.091% per trade**
- Baseline total_cap on Hermes LIVE (L2-per-lifecycle): **+5.07%** ⚠️ (less than base, see PAPER trade-off)
- Baseline total_cap on Broader market (L4-tier): **+89.70%** (1425 events, raw +1147.6%)
