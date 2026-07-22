# LLM Brief Round 1

## Facts

- Smoke budget: `{"candidate_space_sample": 1000000, "coarse_eval": 100000, "deep_eval": 500, "medium_eval": 5000, "portfolio_eval": 50, "stress_eval": 100}`
- CUDA backend: `{'torch_available': True, 'cuda_available': True, 'device': 'cuda', 'device_name': 'NVIDIA GeForce RTX 5090', 'torch_version': '2.11.0+cu128', 'cuda_version': '12.8', 'vram_total_bytes': 34190458880}`
- Path precision: `path_resolution=1m_mark`; legacy cache is not treated as true trade OHLCV.
- Best smoke strategy: `v6_35af2e72be60038eaa` family `message_context_breakout`, side `long`, exit `state_machine`.
- Best smoke median net pct: `22.534242272377014`; p25 `13.611875474452972`; sample `78`.
- Best baseline by median: `current_live_bwe_oi_pump_long` median `-0.3390140598639846`.

## Early Signals

- Treat all positives as smoke-only evidence until medium reruns with stronger trade kline coverage and per-event statistical checks.
- Families with positive robust score should be mutated around entry timing, exit family, and left-tail filters.
- Rejections dominated by median/stress/sample-size gates should not be resurrected unless a clear feature freshness or path issue is found.