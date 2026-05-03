---
type: strategy
tags: [strategy, wip]
created: {{date:YYYY-MM-DD}}
status: design
side: short
hold_min: 60
---

# Strategy: {{title}}

## 📋 Identity

- **ID**: 
- **Family**: BROAD / CHAMP / QUAL / Legacy
- **Side**: SHORT / LONG / Conditional
- **Hold**: __ min

## 🎯 Hypothesis

> 这个策略 fade 什么 / 跟随什么 / 为什么有 alpha

## 🔍 Entry Filter

```python
{
  "magnitude_min": 3,
  "magnitude_max": 10,
  "yao_min": 1,
  "top_ls_min": 0.9,
  "funding_min": 0,
  # NEW filters:
  "bar_shape_required": "TREND",
  "btc_regime": "quiet",
  "sym_6h_chg_max": 30,
}
```

## 🚪 Exit Config

```python
{
  "hold_min": 60,
  "atr_mult": 10,
  "extr_init": 35,
  "extr_final": 18,
  "lock_at": 12,
  "sustain_bars": 1,
}
```

## 📊 Backtest Results (30d)

| Metric | Value |
|---|---|
| n trades | |
| Mean PnL | |
| WR | |
| Sum | |
| Max DD | |

## 📈 Paper-LIVE Results

(更新 after 1-2 周 paper data)

## 🔗 Related

- [[../40_EXPERIMENTS/round5/specs/PAPER_BACKTEST_DRIFT_LOG|Drift Log]]
- [[../40_EXPERIMENTS/round5/specs/BWE_PROJECT_DESIGN_RULES|Design Rules]]
