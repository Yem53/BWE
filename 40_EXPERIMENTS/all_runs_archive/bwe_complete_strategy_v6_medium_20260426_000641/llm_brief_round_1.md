# LLM Brief Round 1

## Facts

- Smoke budget: `{"candidate_space_sample": 100000000, "coarse_eval": 10000000, "deep_eval": 10000, "medium_eval": 200000, "portfolio_eval": 300, "prerequisites": ["legacy_market_cache_normalized", "trade_kline_coverage_report", "path_resolution_decision"], "stress_eval": 1000}`
- CUDA backend: `{'torch_available': True, 'cuda_available': True, 'device': 'cuda', 'device_name': 'NVIDIA GeForce RTX 5090', 'torch_version': '2.11.0+cu128', 'cuda_version': '12.8', 'vram_total_bytes': 34190458880}`
- Path precision: `path_resolution=1m_trade_kline`.
- Best smoke strategy: `v6_30f9a0c0e44c550312` family `no_trade_freshness_boundary`, side `long`, exit `breakeven_ratchet`.
- Best smoke median net pct: `53.505873680114746`; p25 `22.705352306365967`; sample `36`.
- Best baseline by median: `current_live_bwe_oi_pump_long` median `-0.4517294466495514`.

## Early Signals

- Treat all positives as smoke-only evidence until medium reruns with stronger trade kline coverage and per-event statistical checks.
- Families with positive robust score should be mutated around entry timing, exit family, and left-tail filters.
- Rejections dominated by median/stress/sample-size gates should not be resurrected unless a clear feature freshness or path issue is found.