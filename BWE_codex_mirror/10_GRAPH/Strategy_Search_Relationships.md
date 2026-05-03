---
type: graph
tags: [graph, strategy-search, bwe-codex]
updated: 2026-05-03T18:30:27-04:00
status: active
---

# Strategy Search Relationships

```mermaid
graph TD
  Goal[Long + Short common yaobi strategy gates]
  Data[BWE messages + Binance 1m/microstructure data]
  MarketNative[Scanner-native market-only searches]
  FocusedV2[focused_v2 all-market microstructure]
  QualityReplay[quality-diverse exact replay]
  PortfolioCombo[portfolio-level sparse-rule combinations]
  ComboNext[Next: lower-timeframe or new feature branch]
  ExactReplay[Strict high/low exact replay]
  PaperDemo[v6_982 paper/demo runner]
  Multi9[Multi-9 paper/demo runner]
  MC[Market cap gate audit]
  ShortGrid[Short BWE event grid]
  ShortExact[Short reversal exact]
  Oracle[Short oracle MFE]
  ExitRefine[Short oracle exit refine]
  Vault[Vault sync]
  Goal --> Data
  Data --> MarketNative
  MarketNative --> FocusedV2
  FocusedV2 --> QualityReplay
  QualityReplay -->|0 hard-gate pass| Goal
  QualityReplay -->|short quality pocket, frequency too low| PortfolioCombo
  PortfolioCombo -->|0 hard-gate pass| Goal
  PortfolioCombo -->|stacking did not solve frequency-quality trade-off| ComboNext
  ComboNext --> MarketNative
  Data --> ExactReplay
  ExactReplay --> PaperDemo
  ExactReplay --> Multi9
  ShortGrid --> Multi9
  MC --> PaperDemo
  Data --> ShortGrid
  ShortGrid --> ShortExact
  ShortExact --> Oracle
  Oracle --> ExitRefine
  ExactReplay -->|5,221 long pass / 0 short pass| Goal
  ExactReplay -->|breakeven ratchet invalidated| Goal
  ExitRefine -->|0 short pass so far| Goal
  Goal --> Vault
```

## Key Links

- [[codex_discovery/runs/20260503T021854Z_exact_v6_state_machine_replay_all_objective_unique/exact_v6_state_machine_replay|Strict replay: 5,221 long pass, 0 short pass]]
- [[codex_discovery/runs/20260503T051140Z_market_native_micro_stream/market_native_micro_stream|Focused scanner-native search: 0 pass]]
- [[codex_discovery/runs/20260503T055317Z_market_native_quality_exact/market_native_quality_exact|Quality-diverse exact replay: 0 pass]]
- [[codex_discovery/runs/20260503T061922Z_market_native_portfolio_combo/market_native_portfolio_combo|Short portfolio combo: 0 pass]]
- [[codex_discovery/runs/20260503T062415Z_market_native_portfolio_combo/market_native_portfolio_combo|Long portfolio combo: 0 pass]]
- [[30_REPORTS/2026-05-02_exact_high_low_retest|Strict High/Low Retest Report]]
- [[paper_test/v6_982b322524d6a28283/README|v6_982 paper/demo runner]]
- [[paper_test/v6_982b322524d6a28283/reports/2026-05-03_marketcap_filter_impact|Market-cap filter impact]]
- [[paper_test/v6_982b322524d6a28283/reports/2026-05-03_paper_demo_setup_status|Paper/demo setup status]]
- [[paper_test/v6_multi_8/README|Multi-9 paper/demo runner]]
- [[paper_test/v6_multi_8/reports/2026-05-03_multi8_paper_setup_status|Multi-9 setup status]]
- [[codex_discovery/runs/20260503T001701Z_short_oracle_exit_refine/short_oracle_exit_refine|Short exit refine: no pass]]
- [[99_ADMIN/VAULT_SYNC_LOG|Vault sync log]]
