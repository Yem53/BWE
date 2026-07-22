# LLM Brief Round 1

## Facts

- Smoke budget: `{"candidate_space_sample": 100000000, "coarse_eval": 1000, "deep_eval": 50, "medium_eval": 200, "portfolio_eval": 300, "prerequisites": ["legacy_market_cache_normalized", "trade_kline_coverage_report", "path_resolution_decision"], "stress_eval": 1000}`
- CUDA backend: `{'torch_available': True, 'cuda_available': True, 'device': 'cuda', 'device_name': 'NVIDIA GeForce RTX 5090', 'torch_version': '2.11.0+cu128', 'cuda_version': '12.8', 'vram_total_bytes': 34190458880}`
- Path precision: `path_resolution=1m_trade_kline`.
- Best smoke strategy: `v6_6614929204ee3da5c7` family `message_context_breakout`, side `long`, exit `state_machine`.
- Best smoke median net pct: `10.911467671394348`; p25 `-2.2241588681936264`; sample `530`.
- Best baseline by median: `current_live_bwe_oi_pump_long` median `-0.4517294466495514`.

## Early Signals

- Treat all positives as smoke-only evidence until medium reruns with stronger trade kline coverage and per-event statistical checks.
- Families with positive robust score should be mutated around entry timing, exit family, and left-tail filters.
- Rejections dominated by median/stress/sample-size gates should not be resurrected unless a clear feature freshness or path issue is found.