# LLM Brief Round 1

## Facts

- Smoke budget: `{"aggressive_runner": true, "candidate_space_sample": 500000000000, "coarse_elapsed_seconds_before_finalize": 6.469379663467407, "coarse_eval": 2000, "deep_eval": 10, "medium_eval": 100, "overcollect": 1.2, "portfolio_eval": 500, "shared_aggressive_dir": "H:\\data\\bwe\\v6\\runs\\bwe_complete_strategy_v6_max_alpha_aggressive_combined_20260426_105007", "stress_eval": 5, "worker_top_keep": 120, "workers": 2}`
- CUDA backend: `{'torch_available': True, 'cuda_available': True, 'device': 'cuda', 'device_name': 'NVIDIA GeForce RTX 5090', 'torch_version': '2.11.0+cu128', 'cuda_version': '12.8', 'vram_total_bytes': 34190458880}`
- Path precision: `path_resolution=1m_trade_kline`.
- Best smoke strategy: `v6_09ccae733923af3cbb` family `cross_channel_continuation`, side `long`, exit `state_machine`.
- Best smoke median net pct: `11.553239822387695`; p25 `6.739431619644165`; sample `516`.
- Best baseline by median: `current_live_bwe_oi_pump_long` median `-0.4517294466495514`.

## Early Signals

- Treat all positives as smoke-only evidence until medium reruns with stronger trade kline coverage and per-event statistical checks.
- Families with positive robust score should be mutated around entry timing, exit family, and left-tail filters.
- Rejections dominated by median/stress/sample-size gates should not be resurrected unless a clear feature freshness or path issue is found.