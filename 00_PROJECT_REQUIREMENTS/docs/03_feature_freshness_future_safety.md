# 03. Freshness 与防未来函数

## Freshness 分级

所有 Binance 统计指标必须带 age 字段或可计算 age。

规则：

```text
age <= 5m      -> strong usable
5m < age <=10m -> weak usable / downgrade
age > 10m      -> cannot be strong signal
missing        -> fallback or no_trade, cannot silently pass
```

Funding 可按独立逻辑处理，因为 funding 本身更新周期更长：

```text
funding_age <= 8h   -> usable
8h < age <= 12h     -> weak usable
age > 12h / missing -> cannot be strong signal
```

## 必须记录

每条策略必须记录：

- 使用了哪些 feature packet
- 每个 packet 的覆盖率
- 平均 age
- 过旧字段占比
- 缺失字段 fallback
- freshness penalty

## 防未来函数硬规则

禁止将以下字段作为入场或退出触发条件：

```text
ret_*
net_*
mfe*
mae*
future_*
forward_*
label_*
outcome
final_*
max_after_entry
min_after_entry
```

例外：

- 在线 MFE/MAE 状态可以用于持仓中退出，但必须由入场后逐分钟路径递推得到。
- `confirm_after_*` 只能用于 delayed-entry，不能用于 T0 entry。

## 退出模拟边界

退出策略必须标注路径精度：

```text
path_resolution=1m_mark
path_resolution=1m_trade_kline
path_resolution=5m_stat_bucket
path_resolution=forward_label_only
```

如果只有 forward label，不允许模拟 first-touch。

如果只有 `1m_mark`，可以模拟 mark path first-touch，但报告必须说清楚这不是 trade execution path。

如果 `1m_trade_kline` 覆盖率不足，不能把少数已覆盖事件的 first-touch 结果外推到全样本。

## LLM 使用边界

Codex/LLM 可以读：

- leaderboard
- reject log
- diagnostics summary
- aggregated examples
- strategy DSL

Codex/LLM 不应该直接读：

- 每条未来 label 后反推条件
- 原始巨大 parquet 全量
- secrets
- live trading config
