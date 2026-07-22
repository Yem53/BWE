# LLM Brief Round 1

## Facts

- Smoke budget: `{"base_full_top_pool_seed_scores": "H:\\data\\bwe\\v6\\runs\\bwe_complete_strategy_v6_max_alpha_gpu_fused_base_20260426_115115\\max_alpha_gpu_fused_base_eval_top_seed_scores.csv", "candidate_space_sample": 500000000000, "coarse_elapsed_seconds_before_finalize": 2363.6446862220764, "coarse_eval": 100000000, "coarse_fused_on_cuda": true, "deep_eval": 200000, "final_deep_uses_canonical_v6_metrics": true, "gpu_fused_runner": true, "medium_eval": 5000000, "portfolio_eval": 2000, "shared_gpu_fused_dir": "H:\\data\\bwe\\v6\\runs\\bwe_complete_strategy_v6_max_alpha_gpu_fused_combined_20260426_115115", "stress_eval": 20000, "strong_full_top_pool_seed_scores": "H:\\data\\bwe\\v6\\runs\\bwe_complete_strategy_v6_max_alpha_gpu_fused_strong_20260426_115115\\max_alpha_gpu_fused_strong_eval_top_seed_scores.csv"}`
- CUDA backend: `{'torch_available': True, 'cuda_available': True, 'device': 'cuda', 'device_name': 'NVIDIA GeForce RTX 5090', 'torch_version': '2.11.0+cu128', 'cuda_version': '12.8', 'vram_total_bytes': 34190458880}`
- Path precision: `path_resolution=1m_trade_kline`.
- Best smoke strategy: `v6_f468dea25e7faf1bcd` family `freshness_strict_confirmation`, side `long`, exit `state_machine`.
- Best smoke median net pct: `23.294341564178467`; p25 `16.143137216567993`; sample `27`.
- Best baseline by median: `current_live_bwe_oi_pump_long` median `-0.4517294466495514`.

## Early Signals

- Treat all positives as smoke-only evidence until medium reruns with stronger trade kline coverage and per-event statistical checks.
- Families with positive robust score should be mutated around entry timing, exit family, and left-tail filters.
- Rejections dominated by median/stress/sample-size gates should not be resurrected unless a clear feature freshness or path issue is found.