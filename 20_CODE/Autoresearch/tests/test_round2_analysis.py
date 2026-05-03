from pathlib import Path

import pandas as pd
import pytest

from bwe_autoresearch.round2_analysis import (
    cooldown_rows,
    cross_channel_propagation,
    refuse_live_path,
)


def test_round2_refuses_live_paths():
    with pytest.raises(ValueError):
        refuse_live_path(Path('/tmp/bwe_live_autotrader_runtime'))


def test_cooldown_rows_keeps_one_symbol_per_window():
    df = pd.DataFrame(
        {
            'symbol': ['AAA', 'AAA', 'AAA', 'BBB'],
            'ts_ms': [0, 10 * 60_000, 70 * 60_000, 20 * 60_000],
            'value': [1, 2, 3, 4],
        }
    )
    out = cooldown_rows(df, minutes=60)
    assert out.sort_values(['symbol', 'ts_ms'])['value'].tolist() == [1, 3, 4]


def test_cross_channel_propagation_respects_forward_window(tmp_path):
    rows = []
    for i in range(25):
        base = i * 3_600_000
        rows.append(
            {
                'event_key': f'src{i}',
                'symbol': 'AAA',
                'channel': 'BWE_pricechange_monitor',
                'ts_ms': base,
                'event_type': 'pump',
                'side': 'long',
                'net_5m': 0.001,
                'net_10m': 0.001,
                'net_30m': 0.001,
                'net_60m': 0.001,
                'move_pct': 5.0,
                'oi_ratio_pct': 0.0,
                'prev_hour_quote_volume': 1_000_000,
                'marketcap_bucket_norm': '200m-1b',
                'btc_regime': 'btc_up',
                'trend_alignment': 'aligned',
            }
        )
        rows.append(
            {
                'event_key': f'tgt{i}',
                'symbol': 'AAA',
                'channel': 'BWE_OI_Price_monitor',
                'ts_ms': base + 60_000,
                'event_type': 'pump',
                'side': 'long',
                'net_5m': 0.02,
                'net_10m': 0.03,
                'net_30m': 0.04,
                'net_60m': 0.05,
                'move_pct': 6.0,
                'oi_ratio_pct': 10.0,
                'prev_hour_quote_volume': 2_000_000,
                'marketcap_bucket_norm': '200m-1b',
                'btc_regime': 'btc_up',
                'trend_alignment': 'aligned',
            }
        )
    out = cross_channel_propagation(pd.DataFrame(rows), tmp_path)
    assert not out.empty
    row = out[(out['source_channel'] == 'BWE_pricechange_monitor') & (out['target_channel'] == 'BWE_OI_Price_monitor')].iloc[0]
    assert row['sample_size'] == 25
    assert row['median_lag_s'] == 60.0
    assert row['median_net_pct'] > 0
