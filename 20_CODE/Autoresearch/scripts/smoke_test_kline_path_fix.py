"""Smoke test for Day 1.1: verify kline path fix in v6_complete_strategy.py.

Validates:
- DATASET_FILES["local_kline_1m_event_window"] resolves to a real parquet
- Row count matches EXPECTED_COUNTS
- Schema contains the expected columns

Run from repo root:
    python scripts/smoke_test_kline_path_fix.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from bwe_autoresearch.v6_complete_strategy import (
    DATASET_FILES,
    EXPECTED_COUNTS,
    feature_dir,
)

DATA_ROOT = Path("H:/BWE/30_DATA")
EXPECTED_COLS = {
    "event_id",
    "api_symbol",
    "event_ts_ms",
    "minute_offset",
    "trade_open",
    "trade_high",
    "trade_low",
    "trade_close",
    "trade_volume",
}


def main() -> int:
    fdir = feature_dir(DATA_ROOT)
    rel = DATASET_FILES["local_kline_1m_event_window"]
    expected_rows = EXPECTED_COUNTS["local_kline_1m_event_window"]
    target = (fdir / rel).resolve()

    print(f"fdir              = {fdir}")
    print(f"relative path     = {rel}")
    print(f"resolved target   = {target}")
    print(f"target exists     = {target.exists()}")
    if not target.exists():
        print("FAIL: resolved path does not exist", file=sys.stderr)
        return 1

    pf = pq.ParquetFile(target)
    actual_rows = pf.metadata.num_rows
    actual_cols = set(pf.schema_arrow.names)

    print(f"actual rows       = {actual_rows:,}")
    print(f"expected rows     = {expected_rows:,}")
    print(f"row match         = {actual_rows == expected_rows}")
    print(f"missing required cols = {sorted(EXPECTED_COLS - actual_cols)}")

    ok = actual_rows == expected_rows and EXPECTED_COLS.issubset(actual_cols)
    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
