# 06. 5090 执行计划

## 机器配置假设

```text
GPU: RTX 5090, 32GB VRAM
RAM: 64GB
SSD: 4TB
```

## 相对 Mac mini 的预期提升

如果仍使用 pandas / parquet / CPU 回测：

```text
约 3-10 倍
```

如果把路径模拟改为 GPU batch engine：

```text
核心模拟 20-100 倍
整体项目 10-50 倍
```

## 推荐执行层级

### smoke

目标：验证代码、数据合同、未来函数检查。

允许使用 `1m_mark` fallback，但必须同时启动 legacy cache parser 和 trade kline 覆盖率审计。

```text
candidate_space_sample: 1M
coarse_eval: 100K
medium_eval: 5K
deep_eval: 500
portfolio_eval: 50
```

### medium

目标：验证完整流程和搜索方向。

进入 medium 前必须已有：

```text
normalized/legacy_trade_kline_1m_windows.parquet
trade_kline_coverage_report.csv
trade_kline_path_resolution_decision.md
```

```text
candidate_space_sample: 100M
coarse_eval: 10M
medium_eval: 200K
deep_eval: 10K
portfolio_eval: 300
```

### max_alpha

目标：正式搜索。

进入 max_alpha 前必须明确主路径：

```text
preferred: path_resolution=1m_trade_kline
fallback: path_resolution=1m_mark, with fallback_count and fallback_policy
```

```text
candidate_space: 10B+
coarse_eval: 100M+
medium_eval: 1M-5M
deep_eval: 50K-200K
stress_eval: 5K-20K
portfolio_eval: 500-2000
```

## 性能要求

必须支持：

- 分块生成候选
- 分块评分
- checkpoint 续跑
- stage artifact 落盘
- top-K heap 保留
- reject reason 聚合
- GPU/CPU backend 可切换
- deterministic seed
- resume from round/stage

## 不要做

- 不要一次性把 10B 候选写成 JSONL。
- 不要把所有结果都读入 pandas 内存。
- 不要在 16GB Mac mini 上跑 full。
- 不要让 LLM 进入逐策略内层循环。

## 建议后端

第一版：

- Python + pandas/pyarrow
- numpy vectorization
- multiprocessing
- parquet checkpoints

第二版：

- PyTorch batch simulation
- optional CuPy/cuDF
- GPU path tensor cache

第三版：

- distributed workers
- strategy family bandit allocation
- Bayesian/EA mutation scheduler
