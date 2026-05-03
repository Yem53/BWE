# 从 Mac mini 复制数据到 T9 或 5090

## 复制到 T9

如果还需要把当前 Mac mini 数据也放到这块硬盘，可以使用：

```bash
mkdir -p /Volumes/T9/BWE_autoresearch/data_snapshot

rsync -avh --progress \
  /Users/ye/.hermes/research/bwe_three_channel_fullrun3/binance_event_features_20260425_30d/ \
  /Volumes/T9/BWE_autoresearch/data_snapshot/binance_event_features_20260425_30d/

rsync -avh --progress \
  /Users/ye/.hermes/research/bwe_autoresearch_entry_v5_20260425/ \
  /Volumes/T9/BWE_autoresearch/data_snapshot/bwe_autoresearch_entry_v5_20260425/

rsync -avh --progress \
  /Users/ye/Downloads/bwe_entry_research_v5_package/ \
  /Volumes/T9/BWE_autoresearch/data_snapshot/bwe_entry_research_v5_package/

rsync -avh --progress \
  /Users/ye/Desktop/Github/Autoresearch/ \
  /Volumes/T9/BWE_autoresearch/code_snapshot/Autoresearch/

mkdir -p /Volumes/T9/BWE_autoresearch/data_snapshot/legacy_market_cache

for d in \
  /Users/ye/.hermes/research/bwe_phase1_run1/market_cache \
  /Users/ye/.hermes/research/bwe_phase1_smoke2/market_cache \
  /Users/ye/.hermes/research/bwe_three_channel_fullrun1/market_cache \
  /Users/ye/.hermes/research/bwe_three_channel_run1/market_cache \
  /Users/ye/.hermes/research/bwe_three_channel_run2/market_cache \
  /Users/ye/.hermes/research/bwe_three_channel_run3/market_cache \
  /Users/ye/.hermes/research/bwe_three_channel_run4/market_cache \
  /Users/ye/.hermes/research/bwe_three_channel_run5/market_cache \
  /Users/ye/.hermes/research/bwe_v2_run1/market_cache \
  /Users/ye/.hermes/research/bwe_v2_run2/market_cache; do
  name=$(basename "$(dirname "$d")")
  rsync -avh --progress "$d/" "/Volumes/T9/BWE_autoresearch/data_snapshot/legacy_market_cache/$name/"
done
```

## 复制到 5090

如果 5090 机器能读取 T9，建议在 5090 上复制到内置 4TB SSD：

```bash
mkdir -p /data/bwe/v6/input /data/bwe/v6/reference /data/bwe/v6/code

rsync -avh --progress \
  /path/to/T9/BWE_autoresearch/data_snapshot/binance_event_features_20260425_30d/ \
  /data/bwe/v6/input/binance_event_features_20260425_30d/

rsync -avh --progress \
  /path/to/T9/BWE_autoresearch/data_snapshot/bwe_autoresearch_entry_v5_20260425/ \
  /data/bwe/v6/reference/bwe_autoresearch_entry_v5_20260425/

rsync -avh --progress \
  /path/to/T9/BWE_autoresearch/data_snapshot/bwe_entry_research_v5_package/ \
  /data/bwe/v6/reference/bwe_entry_research_v5_package/

rsync -avh --progress \
  /path/to/T9/BWE_autoresearch/code_snapshot/Autoresearch/ \
  /data/bwe/v6/code/Autoresearch/

rsync -avh --progress \
  /path/to/T9/BWE_autoresearch/data_snapshot/legacy_market_cache/ \
  /data/bwe/v6/reference/legacy_market_cache/
```

## 复制后校验

至少检查：

```bash
du -sh /data/bwe/v6/input/binance_event_features_20260425_30d
find /data/bwe/v6/input/binance_event_features_20260425_30d -type f | wc -l
```

然后让 Codex/AutoResearch 生成正式 `data_copy_audit.md/json`。
