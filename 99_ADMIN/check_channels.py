import polars as pl
import sys

print("=== unique channels in kline parquet ===", flush=True)
df = pl.scan_parquet("H:/BWE/30_DATA/cache/normalized/trade_kline_1m_event_windows.parquet").select(["channel", "event_type"]).unique().collect()
print(df, flush=True)

print("\n=== unique source_channels in events parquet ===", flush=True)
ev = pl.scan_parquet("H:/BWE/30_DATA/input/binance_event_features_20260425_30d/bwe_events_recent_binance_features.parquet").select(["source_channel"]).unique().collect()
print(ev, flush=True)

print("\n=== count by channel in kline ===", flush=True)
counts = pl.scan_parquet("H:/BWE/30_DATA/cache/normalized/trade_kline_1m_event_windows.parquet").group_by("channel").agg(pl.col("event_id").n_unique().alias("n_events")).collect()
print(counts, flush=True)
