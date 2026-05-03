# T9 数据快照索引

本目录除了 v6 指导文件外，已经放入可迁移到 5090 机器的关键快照。

## 快照目录

```text
data_snapshot/binance_event_features_20260425_30d
data_snapshot/bwe_autoresearch_entry_v5_20260425
data_snapshot/bwe_entry_research_v5_package
data_snapshot/legacy_market_cache
code_snapshot/Autoresearch
```

## 快照用途

### `data_snapshot/binance_event_features_20260425_30d`

v6 主输入数据。包含最近 1 个月：

- BWE 三频道事件
- Binance event-time features
- forward path / labels
- mark price 1m
- premium index 1m
- OI hist
- funding
- global long/short
- top trader account/position
- taker buy/sell
- basis
- exchange info

已知缺口：

```text
raw/local_kline_1m_event_window.parquet 行数为 0
```

所以 v6 初期应使用 `path_resolution=1m_mark`，不能假装有 trade kline first-touch 精度。

### `data_snapshot/bwe_autoresearch_entry_v5_20260425`

v5 本地真实运行结果，用于：

- baseline
- reference
- 对照 v6 是否真正超过 v5 入场候选

不能用于限制 v6 搜索空间。

### `data_snapshot/bwe_entry_research_v5_package`

GPT Pro 生成的策略族和 DSL 包，用于参考：

- entry strategy family map
- threshold grid
- DSL schema
- candidate generation philosophy

不能直接当作已回测结果。

### `data_snapshot/legacy_market_cache`

本机已有 BWE 历史 run 的 OHLCV window JSON cache，已经补充复制到 T9。

包含来源：

```text
bwe_phase1_run1
bwe_phase1_smoke2
bwe_three_channel_fullrun1
bwe_three_channel_run1
bwe_three_channel_run2
bwe_three_channel_run3
bwe_three_channel_run4
bwe_three_channel_run5
bwe_v2_run1
bwe_v2_run2
```

当前快照规模：

```text
约 25G
约 30183 个普通文件
```

定位：

- 这是旧研究 run 的市场窗口缓存。
- 可用于补充审计、交叉检查和找回部分 trade OHLCV window。
- 不是 v6 主数据合同的规范化 parquet 主输入。
- 在 v6 中使用前，必须先做 cache parser、去重、event_id/symbol/time 对齐和覆盖率审计。

注意：

```text
不能因为存在 legacy_market_cache，就认为 trade kline 主路径已经完整。
```

v6 必须先按以下文档处理：

```text
docs/09_trade_kline_legacy_cache_normalization.md
```

### `code_snapshot/Autoresearch`

当前 Autoresearch 代码快照，包含 v3/v4/v5 实现和测试。

已排除：

- `.git/`
- `.venv/`
- `__pycache__/`
- `.pytest_cache/`

## 迁移到 5090 后建议路径

```text
/data/bwe/v6/code/Autoresearch
/data/bwe/v6/input/binance_event_features_20260425_30d
/data/bwe/v6/reference/bwe_autoresearch_entry_v5_20260425
/data/bwe/v6/reference/bwe_entry_research_v5_package
/data/bwe/v6/reference/legacy_market_cache
```

## 迁移命令参考

见：

```text
runbooks/START_ON_5090.md
runbooks/COPY_DATA_FROM_MACMINI.md
```
