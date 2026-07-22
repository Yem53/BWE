# LLM Brief Round 1

## Facts

- Smoke budget: `{"aggressive_runner": true, "base_full_top_pool_seed_scores": "H:\\data\\bwe\\v6\\runs\\bwe_complete_strategy_v6_max_alpha_aggressive_base_20260426_105303\\max_alpha_aggressive_base_eval_top_seed_scores.csv", "candidate_space_sample": 500000000000, "coarse_elapsed_seconds_before_finalize": 11124.436190843582, "coarse_eval": 100000000, "deep_eval": 50000, "materialized_candidate_rows_policy": "full candidate rows are materialized for the deep replay pool; full medium pools are retained as seed-score ledgers to avoid IO/memory dominating the search", "medium_eval": 1000000, "overcollect": 1.06, "portfolio_eval": 500, "shared_aggressive_dir": "H:\\data\\bwe\\v6\\runs\\bwe_complete_strategy_v6_max_alpha_aggressive_combined_20260426_105303", "stress_eval": 5000, "strong_full_top_pool_seed_scores": "H:\\data\\bwe\\v6\\runs\\bwe_complete_strategy_v6_max_alpha_aggressive_strong_20260426_105303\\max_alpha_aggressive_strong_eval_top_seed_scores.csv", "worker_top_keep": 378572, "workers": 14}`
- CUDA backend: `{'torch_available': True, 'cuda_available': True, 'device': 'cuda', 'device_name': 'NVIDIA GeForce RTX 5090', 'torch_version': '2.11.0+cu128', 'cuda_version': '12.8', 'vram_total_bytes': 34190458880}`
- Path precision: `path_resolution=1m_trade_kline`.
- Best smoke strategy: `v6_26d39455d063356304` family `liquidity_filtered_momentum`, side `short`, exit `runner_trail`.
- Best smoke median net pct: `661.9100570678711`; p25 `-5.224158987402916`; sample `39`.
- Best baseline by median: `current_live_bwe_oi_pump_long` median `-0.4517294466495514`.

## Early Signals

- Treat all positives as smoke-only evidence until medium reruns with stronger trade kline coverage and per-event statistical checks.
- Families with positive robust score should be mutated around entry timing, exit family, and left-tail filters.
- Rejections dominated by median/stress/sample-size gates should not be resurrected unless a clear feature freshness or path issue is found.