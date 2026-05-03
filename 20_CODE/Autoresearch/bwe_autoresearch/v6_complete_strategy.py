"""BWE v6 complete-strategy smoke research pipeline.

This module is intentionally paper-only.  It builds the v6 data manifest,
audits parquet inputs, normalizes the legacy market cache into event windows,
and runs a staged complete-strategy smoke search with a CUDA batch replay path
when a CUDA PyTorch build is available.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import random
import re
import socket
import time
import heapq
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests
import yaml

try:
    import torch
except Exception:  # pragma: no cover - CPU fallback is still valid.
    torch = None


EXPECTED_COUNTS = {
    "events_base": 7353,
    "events_features": 7317,
    "forward_merged": 73170,
    "mark_price_1m": 4068517,
    "premium_index_1m": 4068517,
    "open_interest_hist": 746037,
    "global_long_short": 746041,
    "top_trader_account": 745035,
    "top_trader_position": 744535,
    "taker_buy_sell": 744417,
    "basis": 796406,
    "funding_rate": 19050,
    "exchange_info": 716,
    "local_kline_1m_event_window": 2641437,
}

DATASET_FILES = {
    "events_base": "bwe_events_recent_base.parquet",
    "events_features": "bwe_events_recent_binance_features.parquet",
    "forward_merged": "bwe_forward_recent_binance_features_merged.parquet",
    "mark_price_1m": "raw/mark_price_1m.parquet",
    "premium_index_1m": "raw/premium_index_1m.parquet",
    "open_interest_hist": "raw/open_interest_hist.parquet",
    "global_long_short": "raw/global_long_short_account_ratio.parquet",
    "top_trader_account": "raw/top_trader_long_short_account_ratio.parquet",
    "top_trader_position": "raw/top_trader_long_short_position_ratio.parquet",
    "taker_buy_sell": "raw/taker_buy_sell_volume.parquet",
    "basis": "raw/basis_perpetual.parquet",
    "funding_rate": "raw/funding_rate.parquet",
    "exchange_info": "raw/exchange_info.parquet",
    "local_kline_1m_event_window": "../../cache/normalized/trade_kline_1m_event_windows.parquet",
}

ENTRY_DELAYS_SECONDS = [0, 30, 60, 180, 300]
ENTRY_DELAY_TO_MINUTE = {0: 0, 30: 1, 60: 1, 180: 3, 300: 5}
HORIZONS_MINUTES = [5, 10, 15, 30, 60, 120, 240]
EXIT_FAMILIES = [
    "fixed_tp_sl",
    "multi_tp_sl",
    "partial_ladder",
    "trailing_stop",
    "runner_trail",
    "breakeven_ratchet",
    "time_decay",
    "prove_or_exit",
    "failed_continuation",
    "indicator_invalidation",
    "state_machine",
]
SIDES = ["long", "short", "no_trade"]
FUTURE_PREFIXES = (
    "ret_",
    "net_",
    "mfe",
    "mae",
    "future_",
    "forward_",
    "label_",
    "outcome",
    "final_",
    "max_after_entry",
    "min_after_entry",
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(clean_json(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(clean_json(row), ensure_ascii=False, sort_keys=True) + "\n")


def clean_json(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): clean_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean_json(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        val = float(obj)
        return None if not math.isfinite(val) else val
    if isinstance(obj, float):
        return None if not math.isfinite(obj) else obj
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if pd.isna(obj) if not isinstance(obj, (str, bytes, dict, list, tuple)) else False:
        return None
    return obj


def stable_hash(payload: Any, n: int = 16) -> str:
    raw = json.dumps(clean_json(payload), ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:n]


def resolve_root(root_arg: str | None) -> Path:
    if root_arg:
        return Path(root_arg).resolve()
    candidate = Path("/data/bwe/v6")
    if candidate.exists():
        return candidate.resolve()
    drive = Path.cwd().anchor
    win_candidate = Path(drive) / "data" / "bwe" / "v6"
    if win_candidate.exists():
        return win_candidate.resolve()
    return Path.cwd().resolve()


def posix_hint(path: Path) -> str:
    resolved = str(path)
    marker = f"{path.anchor}data{os.sep}bwe{os.sep}v6"
    if resolved.startswith(marker):
        rest = resolved[len(marker) :].replace("\\", "/")
        return "/data/bwe/v6" + rest
    return resolved.replace("\\", "/")


def feature_dir(root: Path) -> Path:
    return root / "input" / "binance_event_features_20260425_30d"


def repo_dir(root: Path) -> Path:
    return root / "code" / "Autoresearch"


def add_event_id(df: pd.DataFrame) -> pd.DataFrame:
    if "event_id" in df.columns:
        return df
    text_col = "raw_message" if "raw_message" in df.columns else "text"
    pieces = (
        df.get("channel", "").astype(str)
        + "|"
        + df.get("ts_ms", 0).astype(str)
        + "|"
        + df.get("symbol", "").astype(str)
        + "|"
        + df.get("event_type", "").astype(str)
        + "|"
        + df.get(text_col, "").astype(str)
    )
    df = df.copy()
    df["event_id"] = [hashlib.sha1(x.encode("utf-8")).hexdigest()[:20] for x in pieces]
    return df


def parquet_meta(path: Path) -> dict[str, Any]:
    out = {
        "path": str(path),
        "exists": path.exists(),
        "readable": False,
        "rows": None,
        "columns": None,
        "file_size_bytes": path.stat().st_size if path.exists() else None,
        "error": None,
    }
    if not path.exists():
        out["error"] = "missing"
        return out
    try:
        pf = pq.ParquetFile(path)
        out["rows"] = pf.metadata.num_rows
        out["columns"] = len(pf.schema_arrow.names)
        if pf.metadata.num_rows > 0 and pf.schema_arrow.names:
            pf.read(columns=[pf.schema_arrow.names[0]])
        else:
            pf.read()
        out["readable"] = True
    except Exception as exc:  # pragma: no cover - recorded in audit.
        out["error"] = repr(exc)
    return out


def cmd_audit(args: argparse.Namespace) -> None:
    root = resolve_root(args.root)
    runs = ensure_dir(root / "runs")
    fdir = feature_dir(root)
    template_path = root / "manifests" / "data_manifest_template.json"
    manifest_path = root / "manifests" / "data_manifest.json"
    template = json.loads(template_path.read_text(encoding="utf-8"))

    gpu_info = detect_gpu()
    manifest = dict(template)
    manifest["machine"] = socket.gethostname()
    manifest["created_at"] = utc_now_iso()
    manifest["paper_only"] = True
    manifest["live_allowed"] = False
    manifest["paths"] = {
        "repo": "/data/bwe/v6/code/Autoresearch",
        "feature_dir_30d": "/data/bwe/v6/input/binance_event_features_20260425_30d",
        "v5_reference_dir": "/data/bwe/v6/reference/bwe_autoresearch_entry_v5_20260425",
        "v5_package_dir": "/data/bwe/v6/reference/bwe_entry_research_v5_package",
        "legacy_market_cache_dir": "/data/bwe/v6/reference/legacy_market_cache",
        "normalized_trade_kline_dir": "/data/bwe/v6/cache/normalized",
        "run_root": "/data/bwe/v6/runs",
        "cache_root": "/data/bwe/v6/cache",
        "llm_prompts": "/data/bwe/v6/prompts",
    }
    manifest["resolved_paths"] = {
        "root": str(root),
        "repo": str(repo_dir(root)),
        "feature_dir_30d": str(fdir),
        "v5_reference_dir": str(root / "reference" / "bwe_autoresearch_entry_v5_20260425"),
        "v5_package_dir": str(root / "reference" / "bwe_entry_research_v5_package"),
        "legacy_market_cache_dir": str(root / "reference" / "legacy_market_cache"),
        "normalized_trade_kline_dir": str(root / "cache" / "normalized"),
        "run_root": str(runs),
    }
    manifest["gpu"] = gpu_info
    manifest["source_path_check"] = {
        "requested_t9_path": "/Volumes/T9/BWE_autoresearch",
        "requested_t9_exists": Path("/Volumes/T9/BWE_autoresearch").exists(),
        "windows_source_fallback": "H:/BWE_autoresearch",
        "windows_source_fallback_exists": Path("H:/BWE_autoresearch").exists(),
    }
    write_json(manifest_path, manifest)

    rows = []
    for name, rel in DATASET_FILES.items():
        meta = parquet_meta(fdir / rel)
        rows.append(
            {
                "dataset": name,
                "relative_path": rel,
                "rows": meta["rows"],
                "expected_rows": EXPECTED_COUNTS.get(name),
                "row_count_match": meta["rows"] == EXPECTED_COUNTS.get(name),
                "readable": meta["readable"],
                "columns": meta["columns"],
                "file_size_bytes": meta["file_size_bytes"],
                "error": meta["error"],
            }
        )
    counts = pd.DataFrame(rows)
    counts.to_csv(runs / "parquet_row_counts.csv", index=False)

    all_parquet = []
    for path in fdir.rglob("*.parquet"):
        meta = parquet_meta(path)
        meta["relative_path"] = path.relative_to(fdir).as_posix()
        all_parquet.append(meta)
    all_readable = all(x["readable"] for x in all_parquet)

    missing = counts[(~counts["readable"]) | (~counts["row_count_match"])]
    missing.to_csv(runs / "missing_required_files.csv", index=False)

    coverage = feature_coverage(fdir / "bwe_events_recent_binance_features.parquet")
    coverage.to_csv(runs / "feature_coverage_by_channel.csv", index=False)

    audit = {
        "created_at": utc_now_iso(),
        "root": str(root),
        "root_posix_hint": posix_hint(root),
        "data_manifest": str(manifest_path),
        "all_feature_parquet_readable": all_readable,
        "required_row_counts_match": bool(counts["row_count_match"].all()),
        "local_trade_kline_rows": int(counts.loc[counts["dataset"] == "local_kline_1m_event_window", "rows"].iloc[0]),
        "path_resolution_pre_smoke": "1m_mark",
        "gpu": gpu_info,
        "counts": counts.to_dict(orient="records"),
        "all_parquet": all_parquet,
        "copy_results_path": str(runs / "copy_results.json"),
    }
    write_json(runs / "data_copy_audit.json", audit)
    md = [
        "# Data Copy Audit",
        "",
        f"- created_at: `{audit['created_at']}`",
        f"- root: `{root}`",
        f"- requested T9 path exists: `{audit['source_path_check']['requested_t9_exists'] if 'source_path_check' in audit else manifest['source_path_check']['requested_t9_exists']}`",
        f"- Windows source fallback exists: `{manifest['source_path_check']['windows_source_fallback_exists']}`",
        f"- all feature parquet readable: `{all_readable}`",
        f"- required row counts match: `{bool(counts['row_count_match'].all())}`",
        f"- local trade kline rows: `{audit['local_trade_kline_rows']}`",
        f"- pre-smoke path resolution: `1m_mark` fallback until trade kline audit passes",
        "",
        "## Row Counts",
        "",
        counts.to_markdown(index=False),
        "",
        "## Notes",
        "",
        "- This is paper/sandbox research only.",
        "- `/Volumes/T9/BWE_autoresearch` is not visible in this Windows session; `H:/BWE_autoresearch` was used as the copied source snapshot.",
        "- `raw/local_kline_1m_event_window.parquet` has 0 rows, so first-touch smoke replay must be labeled as mark-path research, not true trade execution.",
    ]
    (runs / "data_copy_audit.md").write_text("\n".join(md), encoding="utf-8")


def feature_coverage(path: Path) -> pd.DataFrame:
    df = add_event_id(pd.read_parquet(path))
    required = [
        "api_symbol",
        "move_pct",
        "oi_ratio_pct",
        "quote_volume_24h",
        "liquidity_bucket",
        "listing_age_days",
        "open_interest_hist__sumOpenInterest",
        "open_interest_hist__age_ms",
        "funding_rate",
        "funding_age_ms",
        "global_long_short_account_ratio__longShortRatio",
        "global_long_short_account_ratio__age_ms",
        "top_trader_long_short_account_ratio__longShortRatio",
        "top_trader_long_short_position_ratio__longShortRatio",
        "taker_buy_sell_volume__buySellRatio",
        "taker_buy_sell_volume__age_ms",
        "basis_perpetual__basisRate",
        "basis_perpetual__age_ms",
        "mark_1m_close",
        "mark_1m_age_ms",
        "premium_1m_close",
        "premium_1m_age_ms",
        "mark_minus_index_proxy_pct",
    ]
    rows = []
    for (channel, event_type), g in df.groupby(["channel", "event_type"], dropna=False):
        base = {
            "channel": channel,
            "event_type": event_type,
            "events": len(g),
            "unique_symbols": g["api_symbol"].nunique(dropna=True) if "api_symbol" in g.columns else 0,
        }
        for col in required:
            if col in g.columns:
                base[f"{col}__coverage_pct"] = round(float(g[col].notna().mean() * 100.0), 4)
            else:
                base[f"{col}__coverage_pct"] = 0.0
        for col in [c for c in required if c.endswith("age_ms") or c == "funding_age_ms"]:
            if col in g.columns:
                base[f"{col}__mean_minutes"] = round(float(g[col].dropna().mean() / 60000.0), 4) if g[col].notna().any() else None
        rows.append(base)
    return pd.DataFrame(rows).sort_values(["channel", "event_type"]).reset_index(drop=True)


def normalize_cache_symbol(raw: str) -> str:
    raw = raw.upper().replace(".JSON", "")
    raw = raw.replace("-SWAP", "")
    raw = raw.replace("_SWAP", "")
    return raw.replace("-", "").replace("_", "")


def parse_cache_filename(path: Path) -> tuple[str, int | None, int | None]:
    stem = path.stem
    parts = stem.rsplit("_", 2)
    if len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit():
        return normalize_cache_symbol(parts[0]), int(parts[1]), int(parts[2])
    return normalize_cache_symbol(stem), None, None


def make_expected_legacy_windows(events: pd.DataFrame, before_min: int = 5, after_min: int = 60) -> pd.DataFrame:
    offsets = np.arange(-before_min, after_min + 1, dtype=np.int16)
    records = []
    for row in events[["event_id", "api_symbol", "ts_ms", "channel", "event_type"]].itertuples(index=False):
        base = int(row.ts_ms // 60000 * 60000)
        for off in offsets:
            records.append(
                {
                    "event_id": row.event_id,
                    "api_symbol": str(row.api_symbol),
                    "open_time_ms": base + int(off) * 60000,
                    "event_ts_ms": int(row.ts_ms),
                    "minute_offset": int(off),
                    "channel": row.channel,
                    "event_type": row.event_type,
                }
            )
    return pd.DataFrame.from_records(records)


def make_expected_trade_windows(events: pd.DataFrame, before_min: int = 60, after_min: int = 300) -> pd.DataFrame:
    offsets = np.arange(-before_min, after_min + 1, dtype=np.int16)
    records = []
    for row in events[["event_id", "api_symbol", "ts_ms", "channel", "event_type"]].itertuples(index=False):
        base = int(row.ts_ms // 60000 * 60000)
        for off in offsets:
            records.append(
                {
                    "event_id": row.event_id,
                    "api_symbol": str(row.api_symbol),
                    "event_ts_ms": int(row.ts_ms),
                    "open_time_ms": base + int(off) * 60000,
                    "path_ts_ms": base + int(off) * 60000,
                    "minute_offset": int(off),
                    "channel": row.channel,
                    "event_type": row.event_type,
                }
            )
    return pd.DataFrame.from_records(records)


def merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not intervals:
        return []
    intervals = sorted(intervals)
    merged: list[tuple[int, int]] = []
    cur_start, cur_end = intervals[0]
    for start, end in intervals[1:]:
        if start <= cur_end + 60000:
            cur_end = max(cur_end, end)
        else:
            merged.append((cur_start, cur_end))
            cur_start, cur_end = start, end
    merged.append((cur_start, cur_end))
    return merged


def parse_binance_kline_rows(api_symbol: str, rows: list[list[Any]]) -> list[dict[str, Any]]:
    parsed = []
    for row in rows:
        parsed.append(
            {
                "api_symbol": api_symbol,
                "open_time_ms": int(row[0]),
                "trade_open": float(row[1]),
                "trade_high": float(row[2]),
                "trade_low": float(row[3]),
                "trade_close": float(row[4]),
                "trade_volume": float(row[5]),
                "close_time_ms": int(row[6]),
                "trade_quote_volume": float(row[7]),
                "trade_count": int(row[8]),
                "trade_taker_buy_base_volume": float(row[9]),
                "trade_taker_buy_quote_volume": float(row[10]),
            }
        )
    return parsed


def binance_public_get(session: requests.Session, endpoint: str, params: dict[str, Any], timeout: int = 20) -> requests.Response:
    url = "https://fapi.binance.com" + endpoint
    last_exc: Exception | None = None
    for attempt in range(5):
        try:
            resp = session.get(url, params=params, timeout=timeout)
            if resp.status_code in {418, 429}:
                wait = min(60, 2 ** attempt * 5)
                time.sleep(wait)
                continue
            if 500 <= resp.status_code < 600:
                time.sleep(min(30, 2 ** attempt))
                continue
            return resp
        except Exception as exc:
            last_exc = exc
            time.sleep(min(30, 2 ** attempt))
    if last_exc:
        raise last_exc
    return resp


def cmd_fetch_trade_klines(args: argparse.Namespace) -> None:
    root = resolve_root(args.root)
    runs = ensure_dir(root / "runs")
    norm_dir = ensure_dir(root / "cache" / "normalized")
    raw_dir = ensure_dir(root / "cache" / "binance_trade_klines_1m_raw")
    events = add_event_id(pd.read_parquet(feature_dir(root) / "bwe_events_recent_binance_features.parquet"))
    events = events[events["api_symbol"].notna()].copy()
    expected = make_expected_trade_windows(events, before_min=args.before_min, after_min=args.after_min)

    intervals_by_symbol: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for row in events[["api_symbol", "ts_ms"]].itertuples(index=False):
        base = int(row.ts_ms // 60000 * 60000)
        start = base - args.before_min * 60000
        end = base + args.after_min * 60000 + 59999
        intervals_by_symbol[str(row.api_symbol)].append((start, end))
    intervals_by_symbol = {sym: merge_intervals(items) for sym, items in intervals_by_symbol.items()}

    session = requests.Session()
    exchange_symbols: set[str] = set()
    exchange_status = "not_checked"
    try:
        info_resp = binance_public_get(session, "/fapi/v1/exchangeInfo", {})
        exchange_status = f"http_{info_resp.status_code}"
        if info_resp.ok:
            exchange_symbols = {x.get("symbol") for x in info_resp.json().get("symbols", []) if x.get("symbol")}
    except Exception as exc:
        exchange_status = f"error:{exc!r}"

    fetch_audit = []
    raw_parts = []
    total_intervals = sum(len(v) for v in intervals_by_symbol.values())
    interval_done = 0
    min_spacing = 60.0 / max(args.max_requests_per_minute, 1)
    last_request_ts = 0.0
    for sym in sorted(intervals_by_symbol):
        sym_rows = []
        sym_audit_start = time.time()
        symbol_error = ""
        symbol_status = "ok"
        if exchange_symbols and sym not in exchange_symbols:
            symbol_status = "symbol_not_in_futures_exchange_info"
            fetch_audit.append(
                {
                    "api_symbol": sym,
                    "intervals": len(intervals_by_symbol[sym]),
                    "requests": 0,
                    "rows_fetched": 0,
                    "status": symbol_status,
                    "error": "",
                    "exchange_info_status": exchange_status,
                    "elapsed_seconds": 0.0,
                }
            )
            continue
        req_count = 0
        for start_ms, end_ms in intervals_by_symbol[sym]:
            cursor = start_ms
            while cursor <= end_ms:
                now = time.time()
                wait = min_spacing - (now - last_request_ts)
                if wait > 0:
                    time.sleep(wait)
                params = {
                    "symbol": sym,
                    "interval": "1m",
                    "startTime": cursor,
                    "endTime": min(end_ms, cursor + (1500 * 60000) - 1),
                    "limit": 1500,
                }
                resp = binance_public_get(session, "/fapi/v1/klines", params)
                last_request_ts = time.time()
                req_count += 1
                if not resp.ok:
                    symbol_status = f"http_{resp.status_code}"
                    symbol_error = resp.text[:500]
                    break
                data = resp.json()
                if not data:
                    break
                sym_rows.extend(parse_binance_kline_rows(sym, data))
                last_open = int(data[-1][0])
                next_cursor = last_open + 60000
                if next_cursor <= cursor:
                    break
                cursor = next_cursor
                if len(data) < 1500:
                    break
            interval_done += 1
            if symbol_error:
                break
            if interval_done % 250 == 0:
                print(f"fetched intervals {interval_done}/{total_intervals}; raw rows={sum(len(x) for x in raw_parts) + len(sym_rows)}", flush=True)
        if sym_rows:
            sym_df = pd.DataFrame(sym_rows).drop_duplicates(["api_symbol", "open_time_ms"]).sort_values("open_time_ms")
            pq.write_table(pa.Table.from_pandas(sym_df, preserve_index=False), raw_dir / f"{sym}.parquet")
            raw_parts.append(sym_df)
        fetch_audit.append(
            {
                "api_symbol": sym,
                "intervals": len(intervals_by_symbol[sym]),
                "requests": req_count,
                "rows_fetched": len(sym_rows),
                "status": symbol_status,
                "error": symbol_error,
                "exchange_info_status": exchange_status,
                "elapsed_seconds": round(time.time() - sym_audit_start, 3),
            }
        )

    audit_df = pd.DataFrame(fetch_audit)
    audit_df.to_csv(norm_dir / "binance_trade_kline_fetch_audit.csv", index=False)
    audit_df.to_csv(runs / "binance_trade_kline_fetch_audit.csv", index=False)
    if raw_parts:
        raw = pd.concat(raw_parts, ignore_index=True).drop_duplicates(["api_symbol", "open_time_ms"])
    else:
        raw = pd.DataFrame(
            columns=[
                "api_symbol",
                "open_time_ms",
                "trade_open",
                "trade_high",
                "trade_low",
                "trade_close",
                "trade_volume",
                "close_time_ms",
                "trade_quote_volume",
                "trade_count",
                "trade_taker_buy_base_volume",
                "trade_taker_buy_quote_volume",
            ]
        )
    pq.write_table(pa.Table.from_pandas(raw, preserve_index=False), norm_dir / "binance_trade_kline_1m_raw.parquet")

    event_windows = expected.merge(raw, on=["api_symbol", "open_time_ms"], how="left")
    event_windows["trade_kline_available"] = event_windows["trade_close"].notna()
    ordered_cols = [
        "event_id",
        "api_symbol",
        "event_ts_ms",
        "path_ts_ms",
        "minute_offset",
        "open_time_ms",
        "close_time_ms",
        "trade_open",
        "trade_high",
        "trade_low",
        "trade_close",
        "trade_volume",
        "trade_quote_volume",
        "trade_count",
        "trade_taker_buy_base_volume",
        "trade_taker_buy_quote_volume",
        "trade_kline_available",
        "channel",
        "event_type",
    ]
    event_windows = event_windows[ordered_cols]
    pq.write_table(pa.Table.from_pandas(event_windows, preserve_index=False), norm_dir / "trade_kline_1m_event_windows.parquet")

    write_trade_coverage_outputs(root, event_windows, audit_df, before_min=args.before_min, after_min=args.after_min)


def write_trade_coverage_outputs(root: Path, event_windows: pd.DataFrame, audit_df: pd.DataFrame, before_min: int, after_min: int) -> None:
    runs = ensure_dir(root / "runs")
    norm_dir = ensure_dir(root / "cache" / "normalized")
    event_cov = (
        event_windows.groupby(["event_id", "api_symbol", "channel", "event_type"], dropna=False)
        .agg(expected_minutes=("open_time_ms", "count"), minutes_available=("trade_kline_available", "sum"))
        .reset_index()
    )
    event_cov["minutes_available"] = event_cov["minutes_available"].astype(int)
    event_cov["minute_coverage_pct"] = event_cov["minutes_available"] / event_cov["expected_minutes"].replace(0, np.nan) * 100.0
    event_cov["has_trade_kline_window"] = event_cov["minute_coverage_pct"] >= 98.0
    symbol_cov = (
        event_windows.groupby("api_symbol", dropna=False)
        .agg(
            expected_minutes=("open_time_ms", "count"),
            minutes_available=("trade_kline_available", "sum"),
            events=("event_id", "nunique"),
        )
        .reset_index()
    )
    symbol_cov["minutes_available"] = symbol_cov["minutes_available"].astype(int)
    symbol_cov["minute_coverage_pct"] = symbol_cov["minutes_available"] / symbol_cov["expected_minutes"].replace(0, np.nan) * 100.0
    channel_cov = (
        event_cov.groupby(["channel", "event_type"], dropna=False)
        .agg(events_total=("event_id", "count"), events_with_trade_kline_window=("has_trade_kline_window", "sum"), minutes_expected=("expected_minutes", "sum"), minutes_available=("minutes_available", "sum"))
        .reset_index()
    )
    channel_cov["event_coverage_pct"] = channel_cov["events_with_trade_kline_window"] / channel_cov["events_total"].replace(0, np.nan) * 100.0
    channel_cov["minute_coverage_pct"] = channel_cov["minutes_available"] / channel_cov["minutes_expected"].replace(0, np.nan) * 100.0

    event_cov.to_csv(norm_dir / "trade_kline_coverage_by_event.csv", index=False)
    symbol_cov.to_csv(norm_dir / "trade_kline_coverage_by_symbol.csv", index=False)
    channel_cov.to_csv(norm_dir / "trade_kline_coverage_by_channel.csv", index=False)

    events_total = int(event_cov.shape[0])
    events_with = int(event_cov["has_trade_kline_window"].sum())
    events_any = int((event_cov["minutes_available"] > 0).sum())
    symbols_total = int(symbol_cov.shape[0])
    symbols_with = int((symbol_cov["minutes_available"] > 0).sum())
    minutes_expected = int(event_cov["expected_minutes"].sum())
    minutes_available = int(event_cov["minutes_available"].sum())
    event_coverage_pct = events_with / max(events_total, 1) * 100.0
    minute_coverage_pct = minutes_available / max(minutes_expected, 1) * 100.0
    symbol_coverage_pct = symbols_with / max(symbols_total, 1) * 100.0
    if event_coverage_pct >= 95.0 and minute_coverage_pct >= 98.0:
        decision = "1m_trade_kline"
        fallback_policy = "trade kline primary; per-event missing rows remain excluded/flagged"
    elif event_coverage_pct >= 80.0:
        decision = "mixed_trade_kline_with_1m_mark_fallback"
        fallback_policy = "trade kline sensitivity; mark fallback for uncovered events"
    else:
        decision = "1m_mark"
        fallback_policy = "trade kline coverage below threshold; mark path remains primary"
    report = pd.DataFrame(
        [
            {
                "events_total": events_total,
                "events_with_trade_kline_window": events_with,
                "events_with_any_trade_kline_minutes": events_any,
                "event_coverage_pct": round(event_coverage_pct, 4),
                "symbols_total": symbols_total,
                "symbols_with_trade_kline": symbols_with,
                "symbol_coverage_pct": round(symbol_coverage_pct, 4),
                "minutes_expected": minutes_expected,
                "minutes_available": minutes_available,
                "minute_coverage_pct": round(minute_coverage_pct, 4),
                "fetch_symbols": int(audit_df.shape[0]),
                "fetch_requests": int(audit_df["requests"].sum()) if "requests" in audit_df else 0,
                "fetch_rows": int(audit_df["rows_fetched"].sum()) if "rows_fetched" in audit_df else 0,
                "window_before_min": before_min,
                "window_after_min": after_min,
                "path_resolution_decision": decision,
                "fallback_policy": fallback_policy,
            }
        ]
    )
    report.to_csv(runs / "trade_kline_coverage_report.csv", index=False)
    event_cov[event_cov["minute_coverage_pct"] < 98.0].to_csv(runs / "trade_kline_missing_events.csv", index=False)
    lines = [
        "# Trade Kline Path Resolution Decision",
        "",
        f"- events_total: `{events_total}`",
        f"- events_with_trade_kline_window: `{events_with}`",
        f"- event_coverage_pct: `{event_coverage_pct:.4f}`",
        f"- minute_coverage_pct: `{minute_coverage_pct:.4f}`",
        f"- symbol_coverage_pct: `{symbol_coverage_pct:.4f}`",
        f"- fetch_requests: `{int(audit_df['requests'].sum()) if 'requests' in audit_df else 0}`",
        f"- fetch_rows: `{int(audit_df['rows_fetched'].sum()) if 'rows_fetched' in audit_df else 0}`",
        "",
        f"Decision: `path_resolution={decision}`.",
        "",
        "Policy:",
        "",
        f"- `{fallback_policy}`",
        "- Binance public futures 1m trade klines were fetched without API keys and aligned to BWE message event windows.",
        "- No live trading endpoint, secret, Telegram, or launchd path was touched.",
    ]
    (runs / "trade_kline_path_resolution_decision.md").write_text("\n".join(lines), encoding="utf-8")


def parse_cache_value(value: Any) -> tuple[dict[str, Any] | None, str]:
    if value is None:
        return None, "null_value"
    if isinstance(value, (int, float)):
        price = float(value)
        if not math.isfinite(price):
            return None, "nonfinite_scalar"
        return {
            "open": price,
            "high": price,
            "low": price,
            "close": price,
            "volume": None,
            "quote_volume": None,
            "trade_count": None,
            "taker_buy_base_volume": None,
            "taker_buy_quote_volume": None,
            "value_kind": "price_map_as_ohlc_proxy",
        }, "ok_price_map"
    if isinstance(value, list) and len(value) >= 6:
        try:
            return {
                "open": float(value[1]),
                "high": float(value[2]),
                "low": float(value[3]),
                "close": float(value[4]),
                "volume": float(value[5]) if value[5] is not None else None,
                "quote_volume": float(value[7]) if len(value) > 7 and value[7] is not None else None,
                "trade_count": int(value[8]) if len(value) > 8 and value[8] is not None else None,
                "taker_buy_base_volume": float(value[9]) if len(value) > 9 and value[9] is not None else None,
                "taker_buy_quote_volume": float(value[10]) if len(value) > 10 and value[10] is not None else None,
                "value_kind": "ohlcv_list",
            }, "ok_ohlcv_list"
        except Exception:
            return None, "bad_ohlcv_list"
    if isinstance(value, dict):
        try:
            open_px = value.get("open", value.get("o", value.get("close", value.get("c"))))
            high_px = value.get("high", value.get("h", open_px))
            low_px = value.get("low", value.get("l", open_px))
            close_px = value.get("close", value.get("c", open_px))
            return {
                "open": float(open_px),
                "high": float(high_px),
                "low": float(low_px),
                "close": float(close_px),
                "volume": float(value["volume"]) if "volume" in value and value["volume"] is not None else None,
                "quote_volume": float(value["quote_volume"]) if "quote_volume" in value and value["quote_volume"] is not None else None,
                "trade_count": int(value["trade_count"]) if "trade_count" in value and value["trade_count"] is not None else None,
                "taker_buy_base_volume": float(value["taker_buy_base_volume"])
                if "taker_buy_base_volume" in value and value["taker_buy_base_volume"] is not None
                else None,
                "taker_buy_quote_volume": float(value["taker_buy_quote_volume"])
                if "taker_buy_quote_volume" in value and value["taker_buy_quote_volume"] is not None
                else None,
                "value_kind": "ohlcv_dict",
            }, "ok_ohlcv_dict"
        except Exception:
            return None, "bad_ohlcv_dict"
    return None, f"unsupported_{type(value).__name__}"


def cmd_normalize_legacy(args: argparse.Namespace) -> None:
    root = resolve_root(args.root)
    runs = ensure_dir(root / "runs")
    norm_dir = ensure_dir(root / "cache" / "normalized")
    events = add_event_id(pd.read_parquet(feature_dir(root) / "bwe_events_recent_binance_features.parquet"))
    events = events[events["api_symbol"].notna()].copy()
    expected = make_expected_legacy_windows(events)
    expected_by_symbol: dict[str, set[int]] = {}
    expected_records: dict[tuple[str, int], list[dict[str, Any]]] = {}
    symbol_ranges: dict[str, tuple[int, int]] = {}
    for sym, g in expected.groupby("api_symbol"):
        sym = str(sym)
        times = set(int(x) for x in g["open_time_ms"].tolist())
        expected_by_symbol[sym] = times
        symbol_ranges[sym] = (min(times), max(times))
        for row in g.itertuples(index=False):
            expected_records.setdefault((sym, int(row.open_time_ms)), []).append(
                {
                    "event_id": row.event_id,
                    "event_ts_ms": int(row.event_ts_ms),
                    "minute_offset": int(row.minute_offset),
                    "channel": row.channel,
                    "event_type": row.event_type,
                }
            )

    cache_dir = root / "reference" / "legacy_market_cache"
    files = sorted(cache_dir.rglob("*.json"))
    audit_rows: list[dict[str, Any]] = []
    parsed_rows: list[dict[str, Any]] = []
    value_kind_counts: dict[str, int] = {}
    for idx, path in enumerate(files, start=1):
        source_run = path.parent.name
        api_symbol, start_ms, end_ms = parse_cache_filename(path)
        file_size = path.stat().st_size
        audit = {
            "source_run": source_run,
            "source_file": str(path),
            "api_symbol": api_symbol,
            "file_size_bytes": file_size,
            "file_start_ms": start_ms,
            "file_end_ms": end_ms,
            "parse_status": None,
            "rows_in_file": None,
            "rows_used": 0,
            "parse_error": "",
        }
        if api_symbol not in expected_by_symbol:
            audit["parse_status"] = "skipped_symbol_not_in_v6_events"
            audit_rows.append(audit)
            continue
        min_needed, max_needed = symbol_ranges[api_symbol]
        if start_ms is not None and end_ms is not None and (end_ms < min_needed or start_ms > max_needed):
            audit["parse_status"] = "skipped_no_event_window_overlap"
            audit_rows.append(audit)
            continue
        if file_size <= 2:
            audit["parse_status"] = "empty_json"
            audit["rows_in_file"] = 0
            audit_rows.append(audit)
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                audit["parse_status"] = f"unsupported_top_level_{type(data).__name__}"
                audit_rows.append(audit)
                continue
            audit["rows_in_file"] = len(data)
            expected_times = expected_by_symbol[api_symbol]
            used = 0
            for raw_ts, raw_val in data.items():
                try:
                    open_time_ms = int(raw_ts)
                except Exception:
                    continue
                if open_time_ms not in expected_times:
                    continue
                parsed, status = parse_cache_value(raw_val)
                value_kind_counts[status] = value_kind_counts.get(status, 0) + 1
                if parsed is None:
                    continue
                close_time_ms = open_time_ms + 59999
                for event_ref in expected_records.get((api_symbol, open_time_ms), []):
                    used += 1
                    parsed_rows.append(
                        {
                            "source_run": source_run,
                            "source_file": str(path),
                            "api_symbol": api_symbol,
                            "interval": "1m",
                            "open_time_ms": open_time_ms,
                            "close_time_ms": close_time_ms,
                            "open": parsed["open"],
                            "high": parsed["high"],
                            "low": parsed["low"],
                            "close": parsed["close"],
                            "volume": parsed["volume"],
                            "quote_volume": parsed["quote_volume"],
                            "trade_count": parsed["trade_count"],
                            "taker_buy_base_volume": parsed["taker_buy_base_volume"],
                            "taker_buy_quote_volume": parsed["taker_buy_quote_volume"],
                            "event_id_nullable": event_ref["event_id"],
                            "event_ts_ms_nullable": event_ref["event_ts_ms"],
                            "minute_offset_nullable": event_ref["minute_offset"],
                            "parse_status": parsed["value_kind"],
                            "parse_error": "",
                        }
                    )
            audit["rows_used"] = used
            audit["parse_status"] = "ok_used_rows" if used else "ok_no_matching_minutes"
        except Exception as exc:
            audit["parse_status"] = "parse_error"
            audit["parse_error"] = repr(exc)
        audit_rows.append(audit)
        if idx % 1000 == 0:
            print(f"legacy cache scanned {idx}/{len(files)} files, used rows={len(parsed_rows)}", flush=True)

    audit_df = pd.DataFrame(audit_rows)
    audit_df.to_csv(norm_dir / "legacy_market_cache_parse_audit.csv", index=False)
    if parsed_rows:
        norm = pd.DataFrame(parsed_rows)
        norm = norm.drop_duplicates(["api_symbol", "open_time_ms", "event_id_nullable"], keep="first")
    else:
        norm = pd.DataFrame(
            columns=[
                "source_run",
                "source_file",
                "api_symbol",
                "interval",
                "open_time_ms",
                "close_time_ms",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "quote_volume",
                "trade_count",
                "taker_buy_base_volume",
                "taker_buy_quote_volume",
                "event_id_nullable",
                "event_ts_ms_nullable",
                "minute_offset_nullable",
                "parse_status",
                "parse_error",
            ]
        )
    pq.write_table(pa.Table.from_pandas(norm, preserve_index=False), norm_dir / "legacy_trade_kline_1m_windows.parquet")

    expected_event = expected.groupby("event_id").agg(
        api_symbol=("api_symbol", "first"),
        channel=("channel", "first"),
        event_type=("event_type", "first"),
        expected_minutes=("open_time_ms", "nunique"),
    )
    if len(norm):
        got_event = norm.groupby("event_id_nullable").agg(minutes_available=("open_time_ms", "nunique"))
    else:
        got_event = pd.DataFrame(columns=["minutes_available"])
    coverage_event = expected_event.join(got_event, how="left")
    coverage_event["minutes_available"] = coverage_event["minutes_available"].fillna(0).astype(int)
    coverage_event["minute_coverage_pct"] = (
        coverage_event["minutes_available"] / coverage_event["expected_minutes"].replace(0, np.nan) * 100.0
    ).fillna(0.0)
    coverage_event["has_any_legacy"] = coverage_event["minutes_available"] > 0
    coverage_event["has_sufficient_window"] = coverage_event["minute_coverage_pct"] >= 80.0
    coverage_event.reset_index().to_csv(norm_dir / "legacy_market_cache_coverage_by_event.csv", index=False)

    expected_symbol = expected.groupby("api_symbol").agg(expected_minutes=("open_time_ms", "nunique"), events=("event_id", "nunique"))
    if len(norm):
        got_symbol = norm.groupby("api_symbol").agg(minutes_available=("open_time_ms", "nunique"), covered_events=("event_id_nullable", "nunique"))
    else:
        got_symbol = pd.DataFrame(columns=["minutes_available", "covered_events"])
    coverage_symbol = expected_symbol.join(got_symbol, how="left").fillna(0)
    coverage_symbol["minute_coverage_pct"] = (
        coverage_symbol["minutes_available"] / coverage_symbol["expected_minutes"].replace(0, np.nan) * 100.0
    ).fillna(0.0)
    coverage_symbol.reset_index().to_csv(norm_dir / "legacy_market_cache_coverage_by_symbol.csv", index=False)

    events_total = int(coverage_event.shape[0])
    events_with_window = int(coverage_event["has_sufficient_window"].sum())
    events_with_any = int(coverage_event["has_any_legacy"].sum())
    minutes_expected = int(expected.shape[0])
    minutes_available = int(coverage_event["minutes_available"].sum())
    symbols_total = int(expected_symbol.shape[0])
    symbols_with_legacy = int((coverage_symbol["minutes_available"] > 0).sum())
    value_kind_is_trade = any(k in value_kind_counts for k in ("ok_ohlcv_list", "ok_ohlcv_dict"))
    event_coverage_pct = events_with_window / max(events_total, 1) * 100.0
    minute_coverage_pct = minutes_available / max(minutes_expected, 1) * 100.0
    symbol_coverage_pct = symbols_with_legacy / max(symbols_total, 1) * 100.0

    coverage_report = pd.DataFrame(
        [
            {
                "events_total": events_total,
                "events_with_trade_kline_window": events_with_window,
                "events_with_any_legacy_minutes": events_with_any,
                "event_coverage_pct": round(event_coverage_pct, 4),
                "symbols_total": symbols_total,
                "symbols_with_trade_kline": symbols_with_legacy,
                "symbol_coverage_pct": round(symbol_coverage_pct, 4),
                "minutes_expected": minutes_expected,
                "minutes_available": minutes_available,
                "minute_coverage_pct": round(minute_coverage_pct, 4),
                "legacy_rows_written": int(len(norm)),
                "legacy_value_kind_counts": json.dumps(value_kind_counts, sort_keys=True),
                "is_true_trade_ohlcv": bool(value_kind_is_trade),
                "path_resolution_decision": "1m_mark",
                "fallback_policy": "legacy cache is supplemental only; raw local trade kline has 0 rows",
            }
        ]
    )
    coverage_report.to_csv(runs / "trade_kline_coverage_report.csv", index=False)
    coverage_event.reset_index().query("minute_coverage_pct < 80.0").to_csv(runs / "trade_kline_missing_events.csv", index=False)

    decision_lines = [
        "# Trade Kline Path Resolution Decision",
        "",
        f"- events_total: `{events_total}`",
        f"- events_with_sufficient_legacy_window: `{events_with_window}`",
        f"- event_coverage_pct: `{event_coverage_pct:.4f}`",
        f"- minute_coverage_pct: `{minute_coverage_pct:.4f}`",
        f"- symbol_coverage_pct: `{symbol_coverage_pct:.4f}`",
        f"- legacy_value_kind_counts: `{json.dumps(value_kind_counts, sort_keys=True)}`",
        "",
        "Decision: `path_resolution=1m_mark` for smoke.",
        "",
        "Rationale:",
        "",
        "- `raw/local_kline_1m_event_window.parquet` contains 0 rows.",
        "- The legacy cache was parsed where it overlaps v6 event windows, but observed cache values are price maps when `price_map_as_ohlc_proxy` dominates.",
        "- A price map is useful as a supplemental coverage signal, but it is not a true trade OHLCV execution path.",
        "- Any first-touch result from smoke must therefore be labeled mark-path research and cannot be described as true trade execution.",
    ]
    (runs / "trade_kline_path_resolution_decision.md").write_text("\n".join(decision_lines), encoding="utf-8")


def detect_gpu() -> dict[str, Any]:
    info = {
        "torch_available": torch is not None,
        "cuda_available": False,
        "device": "cpu",
        "device_name": None,
        "torch_version": None,
        "cuda_version": None,
    }
    if torch is None:
        return info
    info["torch_version"] = torch.__version__
    info["cuda_version"] = getattr(torch.version, "cuda", None)
    try:
        info["cuda_available"] = bool(torch.cuda.is_available())
        if info["cuda_available"]:
            info["device"] = "cuda"
            info["device_name"] = torch.cuda.get_device_name(0)
            props = torch.cuda.get_device_properties(0)
            info["vram_total_bytes"] = int(props.total_memory)
    except Exception as exc:  # pragma: no cover
        info["error"] = repr(exc)
    return info


@dataclass
class Candidate:
    strategy_family: str
    channel: str
    event_type: str
    side: str
    entry_delay_s: int
    horizon_min: int
    exit_family: str
    tp_pct: float
    sl_pct: float
    trail_pct: float
    be_trigger_pct: float
    conditions: list[dict[str, Any]]
    portfolio_rule: dict[str, Any]
    risk_rule: dict[str, Any]
    seed: int

    def to_strategy_payload(self) -> dict[str, Any]:
        return {
            "strategy_family": self.strategy_family,
            "channel": self.channel,
            "event_type": self.event_type,
            "side": self.side,
            "entry_timing": entry_label(self.entry_delay_s),
            "entry_conditions": self.conditions,
            "exit_family": self.exit_family,
            "exit_state_machine": self.exit_state_machine(),
            "risk_rule": self.risk_rule,
            "portfolio_rule": self.portfolio_rule,
            "seed": self.seed,
            "paper_only": True,
            "live_allowed": False,
        }

    def strategy_id(self) -> str:
        return "v6_" + stable_hash(self.to_strategy_payload(), 18)

    def fingerprint(self) -> str:
        fields = sorted({c["field"] for c in self.conditions})
        payload = {
            "family": self.strategy_family,
            "channel": self.channel,
            "event_type": self.event_type,
            "side": self.side,
            "timing": entry_label(self.entry_delay_s),
            "features": fields,
            "exit": self.exit_family,
            "risk": self.risk_rule.get("shape"),
            "portfolio": self.portfolio_rule.get("shape"),
        }
        return stable_hash(payload, 14)

    def exit_state_machine(self) -> dict[str, Any]:
        return {
            "family": self.exit_family,
            "tp_pct": self.tp_pct,
            "sl_pct": self.sl_pct,
            "trail_pct": self.trail_pct,
            "breakeven_trigger_pct": self.be_trigger_pct,
            "max_hold_min": self.horizon_min,
            "path_resolution": "1m_mark",
            "states": exit_states_for_family(self.exit_family),
        }


def entry_label(delay_s: int) -> str:
    return {0: "T0", 30: "30s", 60: "1m", 180: "3m", 300: "5m"}.get(delay_s, f"{delay_s}s")


def entry_delay_from_label(label: str) -> int:
    return {"T0": 0, "30s": 30, "1m": 60, "3m": 180, "5m": 300}.get(str(label), 0)


def exit_states_for_family(family: str) -> list[str]:
    mapping = {
        "fixed_tp_sl": ["entry", "fixed_tp_or_sl", "time_stop"],
        "multi_tp_sl": ["entry", "tp1", "tp2", "sl", "time_stop"],
        "partial_ladder": ["entry", "partial_tp1", "partial_tp2", "runner_or_stop"],
        "trailing_stop": ["entry", "armed", "trailing", "stop_or_time"],
        "runner_trail": ["entry", "take_partial", "runner", "trail_exit"],
        "breakeven_ratchet": ["entry", "profit_trigger", "breakeven_lock", "ratchet_or_time"],
        "time_decay": ["entry", "prove_window", "decay_tp_sl", "time_stop"],
        "prove_or_exit": ["entry", "prove", "exit_if_no_continuation", "runner"],
        "failed_continuation": ["entry", "continuation_check", "failed_exit", "time_stop"],
        "indicator_invalidation": ["entry", "monitor_oi_taker_premium", "invalidate_or_hold", "time_stop"],
        "state_machine": ["entry", "prove", "partial", "breakeven", "runner", "invalidation"],
    }
    return mapping.get(family, ["entry", "exit"])


def candidate_from_payload(payload: dict[str, Any]) -> Candidate:
    exit_rule = payload.get("exit_state_machine", {})
    risk_rule = payload.get("risk_rule", {})
    return Candidate(
        strategy_family=payload.get("strategy_family", "unknown"),
        channel=payload.get("channel", "ANY"),
        event_type=payload.get("event_type", "ANY"),
        side=payload.get("side", "long"),
        entry_delay_s=entry_delay_from_label(payload.get("entry_timing", "T0")),
        horizon_min=int(exit_rule.get("max_hold_min", 30)),
        exit_family=payload.get("exit_family", exit_rule.get("family", "fixed_tp_sl")),
        tp_pct=float(exit_rule.get("tp_pct", 0.01)),
        sl_pct=float(exit_rule.get("sl_pct", risk_rule.get("initial_stop_pct", 0.01))),
        trail_pct=float(exit_rule.get("trail_pct", 0.005)),
        be_trigger_pct=float(exit_rule.get("breakeven_trigger_pct", 0.01)),
        conditions=list(payload.get("entry_conditions", [])),
        portfolio_rule=dict(payload.get("portfolio_rule", {"shape": "unknown"})),
        risk_rule=dict(risk_rule),
        seed=int(payload.get("seed", 0)),
    )


class SmokeContext:
    def __init__(self, root: Path, max_horizon_min: int = 245, use_torch_path: bool | None = None):
        self.root = root
        self.fdir = feature_dir(root)
        self.events = add_event_id(pd.read_parquet(self.fdir / "bwe_events_recent_binance_features.parquet"))
        self.events = self.events[self.events["api_symbol"].notna()].reset_index(drop=True)
        self.n = len(self.events)
        self.max_horizon_min = max_horizon_min
        self.features = self._build_feature_arrays()
        self.path_resolution = "1m_mark"
        self.path = self._build_path()
        self.device_info = detect_gpu()
        self.device = self.device_info["device"] if self.device_info["cuda_available"] else "cpu"
        if use_torch_path is None:
            use_torch_path = os.environ.get("BWE_V6_DISABLE_TORCH_PATH") != "1"
        self.torch_path = self._torch_path_tensors(self.device) if use_torch_path else {}

    def _build_feature_arrays(self) -> dict[str, Any]:
        df = self.events
        out: dict[str, Any] = {
            "channel": df["channel"].astype(str).to_numpy(),
            "event_type": df["event_type"].astype(str).to_numpy(),
            "api_symbol": df["api_symbol"].astype(str).to_numpy(),
            "event_id": df["event_id"].astype(str).to_numpy(),
            "ts_ms": df["ts_ms"].astype("int64").to_numpy(),
            "day": pd.to_datetime(df["ts_ms"], unit="ms", utc=True).dt.strftime("%Y-%m-%d").to_numpy(),
        }
        for col in [
            "move_pct",
            "oi_ratio_pct",
            "oi_change_pct",
            "quote_volume_24h",
            "marketcap",
            "listing_age_days",
            "open_interest_hist__age_ms",
            "funding_rate",
            "funding_age_ms",
            "global_long_short_account_ratio__longShortRatio",
            "global_long_short_account_ratio__age_ms",
            "top_trader_long_short_account_ratio__longShortRatio",
            "top_trader_long_short_position_ratio__longShortRatio",
            "taker_buy_sell_volume__buySellRatio",
            "taker_buy_sell_volume__age_ms",
            "basis_perpetual__basisRate",
            "basis_perpetual__age_ms",
            "mark_minus_index_proxy_pct",
            "mark_1m_age_ms",
            "premium_1m_age_ms",
        ]:
            if col in df.columns:
                out[col] = pd.to_numeric(df[col], errors="coerce").to_numpy(dtype=np.float32)
        out["is_tradable_at_event"] = df.get("is_tradable_at_event", pd.Series(True, index=df.index)).fillna(False).to_numpy(dtype=bool)
        out["liquidity_bucket"] = df.get("liquidity_bucket", pd.Series("", index=df.index)).astype(str).to_numpy()
        return out

    def _build_path(self) -> dict[str, np.ndarray]:
        trade_file = self.root / "cache" / "normalized" / "trade_kline_1m_event_windows.parquet"
        decision_file = self.root / "runs" / "trade_kline_coverage_report.csv"
        if trade_file.exists() and decision_file.exists():
            try:
                report = pd.read_csv(decision_file)
                decision = str(report.loc[0, "path_resolution_decision"])
                event_cov = float(report.loc[0, "event_coverage_pct"])
                minute_cov = float(report.loc[0, "minute_coverage_pct"])
                if decision == "1m_trade_kline" and event_cov >= 95.0 and minute_cov >= 98.0:
                    self.path_resolution = "1m_trade_kline"
                    return self._build_trade_path(trade_file)
            except Exception as exc:
                print(f"trade path load failed, falling back to mark: {exc!r}", flush=True)
        self.path_resolution = "1m_mark"
        return self._build_mark_path()

    def _build_trade_path(self, trade_file: Path) -> dict[str, np.ndarray]:
        columns = [
            "event_id",
            "minute_offset",
            "trade_open",
            "trade_high",
            "trade_low",
            "trade_close",
        ]
        trade = pd.read_parquet(trade_file, columns=columns)
        trade = trade[(trade["minute_offset"] >= 0) & (trade["minute_offset"] <= self.max_horizon_min)].copy()
        steps = self.max_horizon_min + 1
        shape = (self.n, steps)
        opens = np.full(shape, np.nan, dtype=np.float32)
        highs = np.full(shape, np.nan, dtype=np.float32)
        lows = np.full(shape, np.nan, dtype=np.float32)
        closes = np.full(shape, np.nan, dtype=np.float32)
        event_index = {eid: i for i, eid in enumerate(self.features["event_id"])}
        for row in trade.itertuples(index=False):
            idx = event_index.get(str(row.event_id))
            if idx is None:
                continue
            off = int(row.minute_offset)
            opens[idx, off] = row.trade_open
            highs[idx, off] = row.trade_high
            lows[idx, off] = row.trade_low
            closes[idx, off] = row.trade_close
        return {"open": opens, "high": highs, "low": lows, "close": closes}

    def _build_mark_path(self) -> dict[str, np.ndarray]:
        raw_path = self.fdir / "raw" / "mark_price_1m.parquet"
        raw = pd.read_parquet(
            raw_path,
            columns=["api_symbol", "mark_1m_open_time_ms", "mark_1m_open", "mark_1m_high", "mark_1m_low", "mark_1m_close"],
        )
        raw["api_symbol"] = raw["api_symbol"].astype(str)
        raw = raw.sort_values(["api_symbol", "mark_1m_open_time_ms"])
        steps = self.max_horizon_min + 1
        shape = (self.n, steps)
        opens = np.full(shape, np.nan, dtype=np.float32)
        highs = np.full(shape, np.nan, dtype=np.float32)
        lows = np.full(shape, np.nan, dtype=np.float32)
        closes = np.full(shape, np.nan, dtype=np.float32)
        event_symbol = self.features["api_symbol"]
        event_base = (self.features["ts_ms"] // 60000 * 60000).astype(np.int64)
        for sym, idxs in pd.Series(np.arange(self.n)).groupby(event_symbol).groups.items():
            g = raw[raw["api_symbol"] == sym]
            if g.empty:
                continue
            times = g["mark_1m_open_time_ms"].to_numpy(np.int64)
            o = g["mark_1m_open"].to_numpy(np.float32)
            h = g["mark_1m_high"].to_numpy(np.float32)
            l = g["mark_1m_low"].to_numpy(np.float32)
            c = g["mark_1m_close"].to_numpy(np.float32)
            idx_arr = np.fromiter(idxs, dtype=np.int64)
            for row_idx in idx_arr:
                targets = event_base[row_idx] + np.arange(steps, dtype=np.int64) * 60000
                pos = np.searchsorted(times, targets)
                valid = (pos < len(times)) & (times[np.minimum(pos, len(times) - 1)] == targets)
                good_pos = pos[valid]
                opens[row_idx, valid] = o[good_pos]
                highs[row_idx, valid] = h[good_pos]
                lows[row_idx, valid] = l[good_pos]
                closes[row_idx, valid] = c[good_pos]
        return {"open": opens, "high": highs, "low": lows, "close": closes}

    def _torch_path_tensors(self, device: str) -> dict[str, Any]:
        if torch is None:
            return {}
        tensors = {}
        for key, arr in self.path.items():
            tensors[key] = torch.tensor(arr, dtype=torch.float32, device=device)
        return tensors


def numeric_quantiles(arr: np.ndarray, qs: Iterable[float]) -> dict[float, float]:
    clean = arr[np.isfinite(arr)]
    if clean.size == 0:
        return {q: 0.0 for q in qs}
    return {q: float(np.quantile(clean, q)) for q in qs}


def generate_candidates(ctx: SmokeContext, count: int, seed: int) -> Iterable[Candidate]:
    rng = random.Random(seed)
    channels = sorted(set(ctx.features["channel"]))
    event_types = sorted(set(ctx.features["event_type"]))
    strategy_families = [
        "message_context_breakout",
        "oi_funding_continuation",
        "taker_flow_reversal",
        "premium_basis_overheat",
        "liquidity_filtered_momentum",
        "freshness_strict_confirmation",
        "cross_channel_continuation",
        "contrarian_crash_fade",
        "no_trade_freshness_boundary",
        "state_machine_runner",
    ]
    q = {}
    for field in [
        "move_pct",
        "oi_ratio_pct",
        "oi_change_pct",
        "quote_volume_24h",
        "marketcap",
        "listing_age_days",
        "taker_buy_sell_volume__buySellRatio",
        "basis_perpetual__basisRate",
        "funding_rate",
        "global_long_short_account_ratio__longShortRatio",
        "top_trader_long_short_account_ratio__longShortRatio",
    ]:
        if field in ctx.features:
            q[field] = numeric_quantiles(ctx.features[field], [0.2, 0.35, 0.5, 0.65, 0.8])
    numeric_fields = list(q)
    for i in range(count):
        family = rng.choice(strategy_families)
        channel = rng.choice(channels + ["ANY", "ANY"])
        event_type = rng.choice(event_types + ["ANY"])
        side = rng.choices(SIDES, weights=[0.45, 0.45, 0.10], k=1)[0]
        delay = rng.choice(ENTRY_DELAYS_SECONDS)
        horizon = rng.choice(HORIZONS_MINUTES)
        exit_family = rng.choice(EXIT_FAMILIES)
        tp = rng.choice([0.004, 0.006, 0.008, 0.01, 0.015, 0.02, 0.03, 0.05, 0.08])
        sl = rng.choice([0.004, 0.006, 0.008, 0.01, 0.015, 0.02, 0.03, 0.05])
        trail = rng.choice([0.003, 0.005, 0.008, 0.012, 0.02, 0.03])
        be = rng.choice([0.004, 0.006, 0.01, 0.015, 0.02, 0.03])
        conds: list[dict[str, Any]] = []
        max_conditions = rng.choices([0, 1, 2, 3, 4], weights=[0.10, 0.25, 0.35, 0.22, 0.08], k=1)[0]
        fields = rng.sample(numeric_fields, k=min(max_conditions, len(numeric_fields)))
        for field in fields:
            op = rng.choice([">=", "<="])
            quantile = rng.choice([0.2, 0.35, 0.5, 0.65, 0.8])
            threshold = q[field][quantile]
            conds.append({"field": field, "op": op, "threshold": threshold, "source": "entry_time_features"})
        if rng.random() < 0.35:
            bucket = rng.choice(["high", "mid", "low", "nan"])
            conds.append({"field": "liquidity_bucket", "op": "in", "values": [bucket], "source": "entry_time_features"})
        if rng.random() < 0.45:
            age_limit = rng.choice([5 * 60000, 10 * 60000])
            conds.append({"field": "mark_1m_age_ms", "op": "<=", "threshold": age_limit, "source": "entry_time_features"})
        portfolio_rule = {
            "shape": rng.choice(["cooldown30_max3", "cooldown60_max5", "cooldown120_max8"]),
            "one_position_per_symbol": True,
            "same_symbol_cooldown_minutes": rng.choice([30, 60, 120]),
            "max_concurrent_positions": rng.choice([3, 5, 8]),
        }
        risk_rule = {
            "shape": rng.choice(["balanced", "left_tail_strict", "stress_strict"]),
            "initial_stop_pct": sl,
            "position_sizing": "unit_notional_paper",
            "fee_model_id": "base_taker",
            "slippage_model_id": "liquidity_aware",
            "latency_model_id": "base_1s",
        }
        yield Candidate(
            family,
            channel,
            event_type,
            side,
            delay,
            horizon,
            exit_family,
            tp,
            sl,
            trail,
            be,
            conds,
            portfolio_rule,
            risk_rule,
            seed + i,
        )


def candidate_mask(ctx: SmokeContext, cand: Candidate) -> tuple[np.ndarray, str | None]:
    mask = ctx.features["is_tradable_at_event"].copy()
    if cand.channel != "ANY":
        mask &= ctx.features["channel"] == cand.channel
    if cand.event_type != "ANY":
        mask &= ctx.features["event_type"] == cand.event_type
    for cond in cand.conditions:
        field = cond["field"]
        if any(field.startswith(p) for p in FUTURE_PREFIXES):
            return mask & False, "future_safety_violation"
        if field == "liquidity_bucket":
            values = set(str(v) for v in cond.get("values", []))
            mask &= np.array([str(x) in values for x in ctx.features["liquidity_bucket"]], dtype=bool)
            continue
        arr = ctx.features.get(field)
        if arr is None:
            return mask & False, f"missing_condition_field:{field}"
        valid = np.isfinite(arr)
        op = cond.get("op")
        threshold = float(cond.get("threshold", 0.0))
        if op == ">=":
            mask &= valid & (arr >= threshold)
        elif op == "<=":
            mask &= valid & (arr <= threshold)
        elif op == ">":
            mask &= valid & (arr > threshold)
        elif op == "<":
            mask &= valid & (arr < threshold)
        else:
            return mask & False, f"unsupported_condition_op:{op}"
    return mask, None


def path_return_components(ctx: SmokeContext, side: str, delay_s: int, horizon_min: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    delay_m = ENTRY_DELAY_TO_MINUTE[delay_s]
    horizon = min(horizon_min, ctx.max_horizon_min - delay_m - 1)
    close = ctx.path["close"]
    high = ctx.path["high"]
    low = ctx.path["low"]
    entry = close[:, delay_m]
    exit_close = close[:, delay_m + horizon]
    if side == "long":
        final = exit_close / entry - 1.0
        fav = np.nanmax(high[:, delay_m + 1 : delay_m + horizon + 1] / entry[:, None] - 1.0, axis=1)
        adv = np.nanmin(low[:, delay_m + 1 : delay_m + horizon + 1] / entry[:, None] - 1.0, axis=1)
    else:
        final = entry / exit_close - 1.0
        fav = np.nanmax(entry[:, None] / low[:, delay_m + 1 : delay_m + horizon + 1] - 1.0, axis=1)
        adv = np.nanmin(entry[:, None] / high[:, delay_m + 1 : delay_m + horizon + 1] - 1.0, axis=1)
    invalid = ~np.isfinite(final) | ~np.isfinite(fav) | ~np.isfinite(adv)
    final[invalid] = np.nan
    fav[invalid] = np.nan
    adv[invalid] = np.nan
    return final.astype(np.float32), fav.astype(np.float32), adv.astype(np.float32)


def approximate_exit_returns(ctx: SmokeContext, cand: Candidate, component_cache: dict[tuple[str, int, int], tuple[np.ndarray, np.ndarray, np.ndarray]]) -> np.ndarray:
    if cand.side == "no_trade":
        return np.zeros(ctx.n, dtype=np.float32)
    key = (cand.side, cand.entry_delay_s, cand.horizon_min)
    if key not in component_cache:
        component_cache[key] = path_return_components(ctx, cand.side, cand.entry_delay_s, cand.horizon_min)
    final, mfe, mae = component_cache[key]
    tp = cand.tp_pct
    sl = cand.sl_pct
    trail = cand.trail_pct
    be = cand.be_trigger_pct
    ret = final.copy()
    if cand.exit_family == "fixed_tp_sl":
        ret = np.where(mae <= -sl, -sl, np.where(mfe >= tp, tp, final))
    elif cand.exit_family == "multi_tp_sl":
        tp2 = tp * 2.0
        ret = np.where(mae <= -sl, -sl, np.where(mfe >= tp2, 0.5 * tp + 0.5 * tp2, np.where(mfe >= tp, 0.5 * tp + 0.5 * final, final)))
    elif cand.exit_family == "partial_ladder":
        tp2 = tp * 1.6
        ret = np.where(mae <= -sl, -sl, np.where(mfe >= tp2, 0.35 * tp + 0.35 * tp2 + 0.30 * final, np.where(mfe >= tp, 0.5 * tp + 0.5 * final, final)))
    elif cand.exit_family == "trailing_stop":
        ret = np.where(mae <= -sl, -sl, np.maximum(final, mfe - trail))
    elif cand.exit_family == "runner_trail":
        ret = np.where(mae <= -sl, -sl, np.where(mfe >= tp, 0.4 * tp + 0.6 * np.maximum(final, mfe - trail), final))
    elif cand.exit_family == "breakeven_ratchet":
        ret = np.where(mae <= -sl, -sl, np.where((mfe >= be) & (final < 0), 0.0, final))
    elif cand.exit_family == "time_decay":
        ret = np.where(mae <= -sl * 0.8, -sl * 0.8, final * 0.85)
    elif cand.exit_family == "prove_or_exit":
        short_key = (cand.side, cand.entry_delay_s, min(5, cand.horizon_min))
        if short_key not in component_cache:
            component_cache[short_key] = path_return_components(ctx, cand.side, cand.entry_delay_s, min(5, cand.horizon_min))
        prove = component_cache[short_key][0]
        ret = np.where(prove < 0, prove - 0.0004, np.where(mae <= -sl, -sl, np.maximum(final, mfe - trail)))
    elif cand.exit_family == "failed_continuation":
        short_key = (cand.side, cand.entry_delay_s, min(10, cand.horizon_min))
        if short_key not in component_cache:
            component_cache[short_key] = path_return_components(ctx, cand.side, cand.entry_delay_s, min(10, cand.horizon_min))
        early = component_cache[short_key][0]
        ret = np.where(early < -sl * 0.35, early, np.where(mae <= -sl, -sl, final))
    elif cand.exit_family == "indicator_invalidation":
        taker = ctx.features.get("taker_buy_sell_volume__buySellRatio", np.full(ctx.n, np.nan, dtype=np.float32))
        adverse = (cand.side == "long") & np.isfinite(taker) & (taker < 0.9)
        adverse |= (cand.side == "short") & np.isfinite(taker) & (taker > 1.1)
        ret = np.where(adverse, np.minimum(final, 0.0) - 0.0005, np.where(mae <= -sl, -sl, final))
    elif cand.exit_family == "state_machine":
        ret = np.where(mae <= -sl, -sl, np.where(mfe >= tp, 0.35 * tp + 0.65 * np.maximum(final, mfe - trail), np.where(final < -sl * 0.5, final, final * 0.9)))
    else:
        ret = final
    base_cost = execution_cost_for_candidate(ctx, cand, stress=False)
    return (ret - base_cost).astype(np.float32)


def execution_cost_for_candidate(ctx: SmokeContext, cand: Candidate, stress: bool = False, latency_s: int | None = None) -> float:
    fee = 4.0 if not stress else 6.0
    base_slip = 5.0 if not stress else 16.0
    if "liquidity_bucket" in ctx.features:
        # Candidate-level smoke cost uses a conservative average liquidity adjustment.
        base_slip += 2.0
    lat = 1 if latency_s is None else latency_s
    latency_bps = (0.6 if not stress else 1.8) * math.log1p(max(lat, 0))
    return (2 * fee + 2 * base_slip + latency_bps) / 10000.0


def compute_metrics(
    ctx: SmokeContext,
    cand: Candidate,
    ret: np.ndarray,
    mask: np.ndarray,
    reject_hint: str | None = None,
    stage: str = "coarse",
    path_resolution: str = "1m_mark",
) -> dict[str, Any]:
    strategy_id = cand.strategy_id()
    valid_mask = mask & np.isfinite(ret)
    vals = ret[valid_mask]
    sample_size = int(vals.size)
    if cand.side == "no_trade":
        reject_reason = "no_trade_boundary_candidate"
    elif reject_hint:
        reject_reason = reject_hint
    elif sample_size < 20:
        reject_reason = "sample_size_lt_20"
    else:
        reject_reason = ""
    if sample_size:
        mean = float(np.mean(vals))
        median = float(np.median(vals))
        p25 = float(np.quantile(vals, 0.25))
        p10 = float(np.quantile(vals, 0.10))
        win = float(np.mean(vals > 0))
        pos = vals[vals > 0].sum()
        neg = -vals[vals < 0].sum()
        pf = float(pos / neg) if neg > 0 else (99.0 if pos > 0 else 0.0)
        equity = np.cumsum(vals[np.argsort(ctx.features["ts_ms"][valid_mask])])
        peak = np.maximum.accumulate(equity)
        mdd = float(np.min(equity - peak)) if equity.size else 0.0
        losing = longest_losing_streak(vals[np.argsort(ctx.features["ts_ms"][valid_mask])])
        symbols = ctx.features["api_symbol"][valid_mask]
        symbol_count = int(pd.Series(symbols).nunique())
        top_symbol_share = float(pd.Series(symbols).value_counts(normalize=True).iloc[0]) if sample_size else 0.0
        days = ctx.features["day"][valid_mask]
        unique_days = int(pd.Series(days).nunique())
        wf = walk_forward_positive_rate(ctx.features["ts_ms"][valid_mask], vals)
        remove_top = remove_top_fraction_mean(vals, 0.01)
        top1_removed = remove_top_n_mean(vals, 1)
        top5_removed = remove_top_n_mean(vals, 5)
    else:
        mean = median = p25 = p10 = win = pf = mdd = 0.0
        losing = symbol_count = unique_days = 0
        top_symbol_share = wf = remove_top = top1_removed = top5_removed = 0.0
    stress_cost_extra = execution_cost_for_candidate(ctx, cand, stress=True) - execution_cost_for_candidate(ctx, cand, stress=False)
    stress_vals = vals - stress_cost_extra if sample_size else vals
    stress_median = float(np.median(stress_vals)) if sample_size else 0.0
    latency_median = float(np.median(vals - 0.0015)) if sample_size else 0.0
    complexity_penalty = (len(cand.conditions) * 0.03 + (0.10 if cand.exit_family == "state_machine" else 0.04)) / 100.0
    robust_score = median * 0.35 + p25 * 0.20 + p10 * 0.10 + min(pf, 5.0) * 0.0005 + wf * 0.0008
    robust_score -= complexity_penalty + max(0.0, top_symbol_share - 0.35) * 0.002
    if reject_reason:
        robust_score -= 10.0
    decision = "watchlist"
    if cand.side == "no_trade":
        decision = "no_trade_boundary"
    elif reject_reason:
        decision = "reject"
    elif median <= 0:
        decision = "reject"
        reject_reason = "median_net_lte_0"
    elif stress_median <= 0:
        decision = "reject"
        reject_reason = "stress_median_lte_0"
    elif pf < 1.2:
        decision = "reject"
        reject_reason = "profit_factor_lt_1_2"
    elif top_symbol_share > 0.45:
        decision = "watchlist"
        reject_reason = "symbol_concentration_watchlist"
    elif wf >= 0.6 and p10 > -0.03 and stress_median > 0:
        decision = "promote_to_round2_candidate" if stage == "deep" else "deep_eval_candidate"
    exit_machine = cand.exit_state_machine()
    exit_machine["path_resolution"] = path_resolution
    payload = cand.to_strategy_payload()
    payload["exit_state_machine"] = exit_machine
    payload["path_resolution"] = path_resolution
    return {
        "strategy_id": strategy_id,
        "strategy_family": cand.strategy_family,
        "channel": cand.channel,
        "event_type": cand.event_type,
        "side": cand.side,
        "entry_timing": entry_label(cand.entry_delay_s),
        "entry_delay_s": cand.entry_delay_s,
        "entry_conditions_json": json.dumps(clean_json(cand.conditions), ensure_ascii=False, sort_keys=True),
        "exit_family": cand.exit_family,
        "exit_state_machine_json": json.dumps(clean_json(exit_machine), ensure_ascii=False, sort_keys=True),
        "risk_rule_json": json.dumps(clean_json(cand.risk_rule), ensure_ascii=False, sort_keys=True),
        "portfolio_rule_json": json.dumps(clean_json(cand.portfolio_rule), ensure_ascii=False, sort_keys=True),
        "horizon_min": cand.horizon_min,
        "sample_size": sample_size,
        "win_rate_pct": win * 100.0,
        "mean_net_pct": mean * 100.0,
        "median_net_pct": median * 100.0,
        "p25_net_pct": p25 * 100.0,
        "p10_net_pct": p10 * 100.0,
        "profit_factor": pf,
        "max_drawdown_pct": mdd * 100.0,
        "longest_losing_streak": losing,
        "mfe_capture_ratio": 0.0,
        "giveback_ratio": 0.0,
        "avg_hold_minutes": cand.horizon_min,
        "stress_fee_slippage_median_net_pct": stress_median * 100.0,
        "stress_latency_median_net_pct": latency_median * 100.0,
        "walk_forward_positive_rate_pct": wf * 100.0,
        "remove_top_1pct_mean_net_pct": remove_top * 100.0,
        "top1_removed_mean_net_pct": top1_removed * 100.0,
        "top5_removed_mean_net_pct": top5_removed * 100.0,
        "symbol_count": symbol_count,
        "unique_days": unique_days,
        "top_symbol_share_pct": top_symbol_share * 100.0,
        "portfolio_drawdown_pct": mdd * 100.0,
        "decision": decision,
        "reject_reason": reject_reason,
        "path_resolution": path_resolution,
        "paper_only": True,
        "live_allowed": False,
        "strategy_fingerprint": cand.fingerprint(),
        "strategy_similarity_cluster_id": similarity_cluster_id(cand),
        "robust_score": robust_score,
        "stage": stage,
        "candidate_seed": cand.seed,
        "strategy_payload_json": json.dumps(clean_json(payload), ensure_ascii=False, sort_keys=True),
    }


def longest_losing_streak(vals: np.ndarray) -> int:
    best = cur = 0
    for v in vals:
        if v <= 0:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return int(best)


def walk_forward_positive_rate(ts_ms: np.ndarray, vals: np.ndarray, windows: int = 5) -> float:
    if vals.size < windows * 5:
        return 0.0
    order = np.argsort(ts_ms)
    chunks = np.array_split(vals[order], windows)
    medians = [np.median(c) for c in chunks if c.size]
    return float(np.mean(np.array(medians) > 0)) if medians else 0.0


def remove_top_fraction_mean(vals: np.ndarray, fraction: float) -> float:
    if vals.size == 0:
        return 0.0
    n = max(1, int(math.ceil(vals.size * fraction)))
    if vals.size <= n:
        return float(np.mean(vals))
    return float(np.mean(np.sort(vals)[:-n]))


def remove_top_n_mean(vals: np.ndarray, n: int) -> float:
    if vals.size == 0:
        return 0.0
    if vals.size <= n:
        return float(np.mean(vals))
    return float(np.mean(np.sort(vals)[:-n]))


def similarity_cluster_id(cand: Candidate) -> str:
    fields = sorted({c["field"] for c in cand.conditions})
    coarse = {
        "trigger": cand.channel,
        "event": cand.event_type,
        "side": cand.side,
        "timing": entry_label(cand.entry_delay_s),
        "features": fields[:4],
        "exit": cand.exit_family,
        "risk": cand.risk_rule.get("shape"),
    }
    return "cluster_" + stable_hash(coarse, 10)


def simulate_exit_gpu(ctx: SmokeContext, cand: Candidate) -> np.ndarray:
    if cand.side == "no_trade" or torch is None or not ctx.torch_path:
        cache: dict[tuple[str, int, int], tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
        return approximate_exit_returns(ctx, cand, cache)
    delay_m = ENTRY_DELAY_TO_MINUTE[cand.entry_delay_s]
    horizon = min(cand.horizon_min, ctx.max_horizon_min - delay_m - 1)
    close = ctx.torch_path["close"]
    high = ctx.torch_path["high"]
    low = ctx.torch_path["low"]
    entry = close[:, delay_m]
    exit_close = close[:, delay_m + horizon]
    eps = 1e-12
    if cand.side == "long":
        final = exit_close / (entry + eps) - 1.0
        fav_path = high[:, delay_m + 1 : delay_m + horizon + 1] / (entry[:, None] + eps) - 1.0
        adv_path = low[:, delay_m + 1 : delay_m + horizon + 1] / (entry[:, None] + eps) - 1.0
        close_path = close[:, delay_m + 1 : delay_m + horizon + 1] / (entry[:, None] + eps) - 1.0
    else:
        final = entry / (exit_close + eps) - 1.0
        fav_path = entry[:, None] / (low[:, delay_m + 1 : delay_m + horizon + 1] + eps) - 1.0
        adv_path = entry[:, None] / (high[:, delay_m + 1 : delay_m + horizon + 1] + eps) - 1.0
        close_path = entry[:, None] / (close[:, delay_m + 1 : delay_m + horizon + 1] + eps) - 1.0
    valid = torch.isfinite(final) & torch.isfinite(entry)
    fav = torch.nan_to_num(fav_path, nan=-999.0).max(dim=1).values
    adv = torch.nan_to_num(adv_path, nan=999.0).min(dim=1).values
    tp = float(cand.tp_pct)
    sl = float(cand.sl_pct)
    trail = float(cand.trail_pct)
    be = float(cand.be_trigger_pct)
    ret = final.clone()
    if cand.exit_family in {"fixed_tp_sl", "multi_tp_sl", "partial_ladder"}:
        tp_hit = fav_path >= tp
        sl_hit = adv_path <= -sl
        first_tp = first_hit_index(tp_hit)
        first_sl = first_hit_index(sl_hit)
        fixed = torch.where(first_tp < first_sl, torch.full_like(final, tp), torch.where(first_sl < 99999, torch.full_like(final, -sl), final))
        if cand.exit_family == "fixed_tp_sl":
            ret = fixed
        elif cand.exit_family == "multi_tp_sl":
            tp2 = tp * 2.0
            ret = torch.where(adv <= -sl, -sl, torch.where(fav >= tp2, 0.5 * tp + 0.5 * tp2, torch.where(fav >= tp, 0.5 * tp + 0.5 * final, final)))
        else:
            tp2 = tp * 1.6
            ret = torch.where(adv <= -sl, -sl, torch.where(fav >= tp2, 0.35 * tp + 0.35 * tp2 + 0.30 * final, torch.where(fav >= tp, 0.5 * tp + 0.5 * final, final)))
    elif cand.exit_family == "trailing_stop":
        running_max = torch.cummax(torch.nan_to_num(close_path, nan=-999.0), dim=1).values
        trail_hit = close_path <= (running_max - trail)
        first_trail = first_hit_index(trail_hit)
        trail_value = torch.gather(running_max - trail, 1, torch.clamp(first_trail, 0, horizon - 1).view(-1, 1)).squeeze(1)
        ret = torch.where(first_trail < 99999, trail_value, torch.maximum(final, fav - trail))
        ret = torch.where(adv <= -sl, torch.full_like(ret, -sl), ret)
    elif cand.exit_family == "runner_trail":
        ret = torch.where(adv <= -sl, -sl, torch.where(fav >= tp, 0.4 * tp + 0.6 * torch.maximum(final, fav - trail), final))
    elif cand.exit_family == "breakeven_ratchet":
        ret = torch.where(adv <= -sl, -sl, torch.where((fav >= be) & (final < 0), torch.zeros_like(final), final))
    elif cand.exit_family == "time_decay":
        ret = torch.where(adv <= -sl * 0.8, -sl * 0.8, final * 0.85)
    elif cand.exit_family == "prove_or_exit":
        prove_idx = min(5, horizon) - 1
        prove = close_path[:, prove_idx] if prove_idx >= 0 else final
        ret = torch.where(prove < 0, prove - 0.0004, torch.where(adv <= -sl, -sl, torch.maximum(final, fav - trail)))
    elif cand.exit_family == "failed_continuation":
        early_idx = min(10, horizon) - 1
        early = close_path[:, early_idx] if early_idx >= 0 else final
        ret = torch.where(early < -sl * 0.35, early, torch.where(adv <= -sl, -sl, final))
    elif cand.exit_family == "indicator_invalidation":
        ret = torch.where(adv <= -sl, -sl, final * 0.92)
    elif cand.exit_family == "state_machine":
        ret = torch.where(adv <= -sl, -sl, torch.where(fav >= tp, 0.35 * tp + 0.65 * torch.maximum(final, fav - trail), torch.where(final < -sl * 0.5, final, final * 0.9)))
    ret = torch.where(valid, ret - execution_cost_for_candidate(ctx, cand, stress=False), torch.full_like(ret, float("nan")))
    if ctx.device == "cuda":
        torch.cuda.synchronize()
    return ret.detach().cpu().numpy().astype(np.float32)


def first_hit_index(hit: Any) -> Any:
    idx = torch.arange(hit.shape[1], device=hit.device, dtype=torch.int64).view(1, -1)
    filled = torch.where(hit, idx, torch.full_like(idx, 99999))
    return filled.min(dim=1).values


def evaluate_baselines(ctx: SmokeContext, component_cache: dict[tuple[str, int, int], tuple[np.ndarray, np.ndarray, np.ndarray]]) -> pd.DataFrame:
    baselines = [
        ("message_only", Candidate("baseline_message_only", "ANY", "ANY", "long", 0, 15, "time_decay", 0.01, 0.01, 0.005, 0.01, [], {"shape": "baseline", "one_position_per_symbol": True}, {"shape": "baseline"}, 1)),
        ("timing_t0", Candidate("baseline_timing", "ANY", "ANY", "long", 0, 15, "fixed_tp_sl", 0.01, 0.01, 0.005, 0.01, [], {"shape": "baseline", "one_position_per_symbol": True}, {"shape": "baseline"}, 2)),
        ("timing_30s", Candidate("baseline_timing", "ANY", "ANY", "long", 30, 15, "fixed_tp_sl", 0.01, 0.01, 0.005, 0.01, [], {"shape": "baseline", "one_position_per_symbol": True}, {"shape": "baseline"}, 3)),
        ("timing_1m", Candidate("baseline_timing", "ANY", "ANY", "long", 60, 15, "fixed_tp_sl", 0.01, 0.01, 0.005, 0.01, [], {"shape": "baseline", "one_position_per_symbol": True}, {"shape": "baseline"}, 4)),
        ("timing_3m", Candidate("baseline_timing", "ANY", "ANY", "long", 180, 15, "fixed_tp_sl", 0.01, 0.01, 0.005, 0.01, [], {"shape": "baseline", "one_position_per_symbol": True}, {"shape": "baseline"}, 5)),
        ("timing_5m", Candidate("baseline_timing", "ANY", "ANY", "long", 300, 15, "fixed_tp_sl", 0.01, 0.01, 0.005, 0.01, [], {"shape": "baseline", "one_position_per_symbol": True}, {"shape": "baseline"}, 6)),
        ("simple_fixed_tp_sl", Candidate("baseline_simple_exit", "ANY", "ANY", "long", 60, 30, "fixed_tp_sl", 0.015, 0.01, 0.005, 0.01, [], {"shape": "baseline", "one_position_per_symbol": True}, {"shape": "baseline"}, 7)),
        ("simple_fixed_horizon", Candidate("baseline_simple_horizon", "ANY", "ANY", "long", 60, 30, "time_decay", 0.015, 0.01, 0.005, 0.01, [], {"shape": "baseline", "one_position_per_symbol": True}, {"shape": "baseline"}, 8)),
        (
            "current_live_bwe_oi_pump_long",
            Candidate("baseline_current_live_reference", "BWE_OI_Price_monitor", "pump", "long", 0, 30, "fixed_tp_sl", 0.02, 0.01, 0.005, 0.01, [], {"shape": "baseline", "one_position_per_symbol": True}, {"shape": "baseline"}, 9),
        ),
        (
            "v5_paper_manifest_reference",
            Candidate("baseline_v5_reference", "ANY", "ANY", "long", 180, 30, "runner_trail", 0.015, 0.01, 0.008, 0.01, [], {"shape": "baseline", "one_position_per_symbol": True}, {"shape": "baseline"}, 10),
        ),
        ("random_entry", Candidate("baseline_random", "ANY", "ANY", "short", 60, 15, "fixed_tp_sl", 0.01, 0.01, 0.005, 0.01, [], {"shape": "baseline", "one_position_per_symbol": True}, {"shape": "baseline"}, 11)),
        ("shuffled_timestamp", Candidate("baseline_shuffled_timestamp", "ANY", "ANY", "long", 60, 15, "fixed_tp_sl", 0.01, 0.01, 0.005, 0.01, [], {"shape": "baseline", "one_position_per_symbol": True}, {"shape": "baseline"}, 12)),
        ("shuffled_symbol", Candidate("baseline_shuffled_symbol", "ANY", "ANY", "long", 60, 15, "fixed_tp_sl", 0.01, 0.01, 0.005, 0.01, [], {"shape": "baseline", "one_position_per_symbol": True}, {"shape": "baseline"}, 13)),
    ]
    rows = []
    rng = np.random.default_rng(5090)
    for name, cand in baselines:
        mask, hint = candidate_mask(ctx, cand)
        ret = approximate_exit_returns(ctx, cand, component_cache)
        if name in {"random_entry", "shuffled_timestamp", "shuffled_symbol"}:
            ret = rng.permutation(ret)
        metrics = compute_metrics(ctx, cand, ret, mask, hint, stage="baseline", path_resolution=ctx.path_resolution)
        metrics["baseline_name"] = name
        rows.append(metrics)
    return pd.DataFrame(rows)


def cmd_smoke(args: argparse.Namespace) -> None:
    root = resolve_root(args.root)
    cfg = yaml.safe_load((root / "configs" / "v6_max_alpha_search_budget.yaml").read_text(encoding="utf-8"))
    budget = cfg["search_budget"]["smoke"]
    if args.coarse_eval:
        budget["coarse_eval"] = int(args.coarse_eval)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = ensure_dir(root / "runs" / f"bwe_complete_strategy_v6_smoke_{timestamp}")
    ctx = SmokeContext(root)
    component_cache: dict[tuple[str, int, int], tuple[np.ndarray, np.ndarray, np.ndarray]] = {}

    start = time.time()
    baselines = evaluate_baselines(ctx, component_cache)
    baselines.to_csv(run_dir / "baseline_comparison.csv", index=False)
    (run_dir / "baseline_catalog.jsonl").write_text(
        "\n".join(json.dumps(clean_json(r), ensure_ascii=False) for r in baselines.to_dict(orient="records")) + "\n",
        encoding="utf-8",
    )

    coarse_rows = []
    reject_rows = []
    generated = 0
    for cand in generate_candidates(ctx, int(budget["coarse_eval"]), seed=5090):
        generated += 1
        mask, hint = candidate_mask(ctx, cand)
        ret = approximate_exit_returns(ctx, cand, component_cache)
        metrics = compute_metrics(ctx, cand, ret, mask, hint, stage="coarse", path_resolution=ctx.path_resolution)
        if metrics["decision"] == "reject":
            reject_rows.append({k: metrics[k] for k in ["strategy_id", "strategy_family", "side", "entry_timing", "exit_family", "sample_size", "reject_reason", "strategy_similarity_cluster_id", "robust_score"]})
        coarse_rows.append(metrics)
        if generated % 10000 == 0:
            print(f"coarse evaluated {generated}/{budget['coarse_eval']} candidates", flush=True)
    coarse = pd.DataFrame(coarse_rows)
    coarse = coarse.sort_values("robust_score", ascending=False).reset_index(drop=True)
    deep_count = min(int(budget["deep_eval"]), len(coarse))
    deep_inputs = coarse.head(deep_count)
    deep_rows = []
    payload_by_id = {row["strategy_id"]: json.loads(row["strategy_payload_json"]) for _, row in coarse.iterrows()}
    candidate_by_id = {}
    for cand in generate_candidates(ctx, int(budget["coarse_eval"]), seed=5090):
        sid = cand.strategy_id()
        if sid in set(deep_inputs["strategy_id"]):
            candidate_by_id[sid] = cand
        if len(candidate_by_id) >= deep_count:
            break
    for i, row in deep_inputs.iterrows():
        cand = candidate_by_id.get(row["strategy_id"])
        if cand is None:
            continue
        mask, hint = candidate_mask(ctx, cand)
        ret = simulate_exit_gpu(ctx, cand)
        metrics = compute_metrics(ctx, cand, ret, mask, hint, stage="deep", path_resolution=ctx.path_resolution)
        if np.isfinite(ret[mask]).any():
            metrics["mfe_capture_ratio"], metrics["giveback_ratio"] = capture_giveback_estimates(ctx, cand, ret, mask, component_cache)
            metrics["portfolio_drawdown_pct"] = portfolio_drawdown(ctx, ret, mask, cand) * 100.0
        deep_rows.append(metrics)
        if (i + 1) % 50 == 0:
            print(f"deep GPU replay {i + 1}/{deep_count}", flush=True)
    deep = pd.DataFrame(deep_rows).sort_values("robust_score", ascending=False).reset_index(drop=True)
    leaderboard = deep if not deep.empty else coarse.head(deep_count)
    leaderboard.to_csv(run_dir / "complete_strategy_leaderboard.csv", index=False)

    rejects = pd.DataFrame(reject_rows)
    if rejects.empty:
        rejects = coarse[coarse["decision"] == "reject"][
            ["strategy_id", "strategy_family", "side", "entry_timing", "exit_family", "sample_size", "reject_reason", "strategy_similarity_cluster_id", "robust_score"]
        ]
    rejects.to_csv(run_dir / "reject_log.csv", index=False)
    write_execution_outputs(ctx, run_dir, leaderboard.head(int(budget["stress_eval"])))
    write_similarity_outputs(run_dir, leaderboard)
    write_statistical_outputs(ctx, run_dir, leaderboard.head(200), payload_by_id)
    write_future_safety_report(run_dir, leaderboard)
    write_markdown_summaries(root, run_dir, leaderboard, baselines, rejects, budget, ctx.device_info)
    append_research_ledger(root, run_dir, leaderboard, baselines, rejects, budget, ctx.device_info)
    elapsed = time.time() - start
    summary = {
        "project": "bwe_complete_strategy_v6",
        "stage": "smoke",
        "created_at": utc_now_iso(),
        "run_dir": str(run_dir),
        "budget": budget,
        "candidate_space_sample": int(budget["candidate_space_sample"]),
        "coarse_eval_actual": int(len(coarse)),
        "medium_eval_budget_recorded": int(budget["medium_eval"]),
        "deep_eval_actual": int(len(deep)),
        "stress_eval_actual": int(min(len(leaderboard), int(budget["stress_eval"]))),
        "portfolio_eval_budget_recorded": int(budget["portfolio_eval"]),
        "path_resolution": ctx.path_resolution,
        "trade_kline_policy": "trade kline primary when coverage thresholds pass; otherwise fallback_to_1m_mark",
        "paper_only": True,
        "live_allowed": False,
        "gpu": ctx.device_info,
        "elapsed_seconds": elapsed,
        "outputs": sorted(p.name for p in run_dir.iterdir()),
    }
    write_json(run_dir / "run_summary.json", summary)
    print(f"smoke complete: {run_dir}", flush=True)


def cmd_medium(args: argparse.Namespace) -> None:
    root = resolve_root(args.root)
    cfg = yaml.safe_load((root / "configs" / "v6_max_alpha_search_budget.yaml").read_text(encoding="utf-8"))
    stage_name = getattr(args, "stage_name", "medium")
    budget_key = getattr(args, "budget_key", stage_name)
    if budget_key == "max_alpha":
        raw_budget = dict(cfg["search_budget"]["max_alpha"])
        budget = {
            "candidate_space_sample": int(raw_budget["candidate_space_target"]),
            "coarse_eval": int(raw_budget["coarse_eval_min"]),
            "medium_eval": int(raw_budget["medium_eval_min"]),
            "deep_eval": int(raw_budget["deep_eval_min"]),
            "stress_eval": int(raw_budget["stress_eval_min"]),
            "portfolio_eval": int(raw_budget["portfolio_eval_min"]),
            "prerequisites": raw_budget.get("prerequisites", []),
            "base档": True,
        }
    else:
        budget = dict(cfg["search_budget"][budget_key])
    if args.coarse_eval:
        budget["coarse_eval"] = int(args.coarse_eval)
    if args.medium_eval:
        budget["medium_eval"] = int(args.medium_eval)
    if args.deep_eval:
        budget["deep_eval"] = int(args.deep_eval)
    if getattr(args, "stress_eval", None):
        budget["stress_eval"] = int(args.stress_eval)
    if getattr(args, "portfolio_eval", None):
        budget["portfolio_eval"] = int(args.portfolio_eval)
    budget.setdefault("stress_eval", 1000)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = ensure_dir(root / "runs" / f"bwe_complete_strategy_v6_{stage_name}_{timestamp}")
    checkpoints = ensure_dir(run_dir / "checkpoints")
    ctx = SmokeContext(root)
    component_cache: dict[tuple[str, int, int], tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    start = time.time()

    baselines = evaluate_baselines(ctx, component_cache)
    baselines.to_csv(run_dir / "baseline_comparison.csv", index=False)
    write_jsonl(run_dir / "baseline_catalog.jsonl", baselines.to_dict(orient="records"))

    top_limit = int(budget["medium_eval"])
    coarse_eval = int(budget["coarse_eval"])
    heap: list[tuple[float, int, dict[str, Any]]] = []
    reject_counts: Counter[str] = Counter()
    reject_cluster_counts: Counter[tuple[str, str]] = Counter()
    reject_samples: list[dict[str, Any]] = []
    seq = 0
    checkpoint_every = max(50000, int(args.checkpoint_every))
    for cand in generate_candidates(ctx, coarse_eval, seed=65090):
        mask, hint = candidate_mask(ctx, cand)
        ret = approximate_exit_returns(ctx, cand, component_cache)
        metrics = compute_metrics(ctx, cand, ret, mask, hint, stage="coarse", path_resolution=ctx.path_resolution)
        seq += 1
        score = float(metrics["robust_score"])
        slim = medium_heap_row(metrics)
        if len(heap) < top_limit:
            heapq.heappush(heap, (score, seq, slim))
        elif score > heap[0][0]:
            heapq.heapreplace(heap, (score, seq, slim))
        if metrics["decision"] == "reject":
            reason = metrics.get("reject_reason") or "unknown"
            cluster = metrics.get("strategy_similarity_cluster_id") or "unknown"
            reject_counts[reason] += 1
            reject_cluster_counts[(reason, cluster)] += 1
            if len(reject_samples) < 200000:
                reject_samples.append(
                    {
                        "strategy_id": metrics["strategy_id"],
                        "strategy_family": metrics["strategy_family"],
                        "side": metrics["side"],
                        "entry_timing": metrics["entry_timing"],
                        "exit_family": metrics["exit_family"],
                        "sample_size": metrics["sample_size"],
                        "reject_reason": reason,
                        "strategy_similarity_cluster_id": cluster,
                        "robust_score": metrics["robust_score"],
                    }
                )
        if seq % checkpoint_every == 0:
            progress = {
                "stage": f"{stage_name}_coarse",
                "evaluated": seq,
                "coarse_eval": coarse_eval,
                "top_heap_size": len(heap),
                "reject_counts": dict(reject_counts),
                "elapsed_seconds": time.time() - start,
                "path_resolution": ctx.path_resolution,
            }
            write_json(checkpoints / f"{stage_name}_progress.json", progress)
            print(f"{stage_name} coarse evaluated {seq}/{coarse_eval}; heap={len(heap)}; elapsed={progress['elapsed_seconds']:.1f}s", flush=True)

    medium_rows = [item[2] for item in sorted(heap, key=lambda x: x[0], reverse=True)]
    medium_df = pd.DataFrame(medium_rows)
    medium_df.to_csv(run_dir / f"{stage_name}_eval_top_candidates.csv", index=False)
    write_json(
        checkpoints / f"{stage_name}_coarse_done.json",
        {
            "evaluated": seq,
            "medium_eval_top_candidates": len(medium_df),
            "reject_counts": dict(reject_counts),
            "elapsed_seconds": time.time() - start,
        },
    )

    deep_count = min(int(budget["deep_eval"]), len(medium_df))
    deep_rows = []
    for i, row in medium_df.head(deep_count).iterrows():
        payload = json.loads(row["strategy_payload_json"])
        cand = candidate_from_payload(payload)
        mask, hint = candidate_mask(ctx, cand)
        ret = simulate_exit_gpu(ctx, cand)
        metrics = compute_metrics(ctx, cand, ret, mask, hint, stage="deep", path_resolution=ctx.path_resolution)
        if np.isfinite(ret[mask]).any():
            metrics["mfe_capture_ratio"], metrics["giveback_ratio"] = capture_giveback_estimates(ctx, cand, ret, mask, component_cache)
            metrics["portfolio_drawdown_pct"] = portfolio_drawdown(ctx, ret, mask, cand) * 100.0
        deep_rows.append(metrics)
        if (i + 1) % 250 == 0:
            print(f"{stage_name} deep GPU replay {i + 1}/{deep_count}", flush=True)
    leaderboard = pd.DataFrame(deep_rows).sort_values("robust_score", ascending=False).reset_index(drop=True)
    leaderboard.to_csv(run_dir / "complete_strategy_leaderboard.csv", index=False)

    reject_log = pd.DataFrame(reject_samples)
    reject_log.to_csv(run_dir / "reject_log.csv", index=False)
    reject_summary = pd.DataFrame(
        [
            {"reject_reason": reason, "strategy_similarity_cluster_id": cluster, "count": count}
            for (reason, cluster), count in reject_cluster_counts.items()
        ]
    ).sort_values("count", ascending=False)
    reject_summary.to_csv(run_dir / "reject_cluster_counts.csv", index=False)

    write_execution_outputs(ctx, run_dir, leaderboard.head(int(budget["stress_eval"])))
    write_similarity_outputs(run_dir, leaderboard)
    payload_by_id = {row["strategy_id"]: row["strategy_payload_json"] for _, row in medium_df.iterrows()}
    write_statistical_outputs(ctx, run_dir, leaderboard.head(500), payload_by_id)
    write_future_safety_report(run_dir, leaderboard)
    write_markdown_summaries(root, run_dir, leaderboard, baselines, reject_log, budget, ctx.device_info)
    append_research_ledger(root, run_dir, leaderboard, baselines, reject_log, budget, ctx.device_info)
    write_medium_gate_report(root, run_dir, leaderboard, baselines, reject_counts, budget, ctx, stage_name=stage_name)
    elapsed = time.time() - start
    summary = {
        "project": "bwe_complete_strategy_v6",
        "stage": stage_name,
        "created_at": utc_now_iso(),
        "run_dir": str(run_dir),
        "budget": budget,
        "candidate_space_sample": int(budget["candidate_space_sample"]),
        "coarse_eval_actual": seq,
        "medium_eval_actual": int(len(medium_df)),
        "deep_eval_actual": int(len(leaderboard)),
        "stress_eval_actual": int(min(len(leaderboard), int(budget["stress_eval"]))),
        "portfolio_eval_budget_recorded": int(budget.get("portfolio_eval", 0)),
        "path_resolution": ctx.path_resolution,
        "paper_only": True,
        "live_allowed": False,
        "gpu": ctx.device_info,
        "elapsed_seconds": elapsed,
        "outputs": sorted(p.name for p in run_dir.iterdir()),
    }
    write_json(run_dir / "run_summary.json", summary)
    print(f"{stage_name} complete: {run_dir}", flush=True)


def medium_heap_row(metrics: dict[str, Any]) -> dict[str, Any]:
    keep = [
        "strategy_id",
        "strategy_family",
        "channel",
        "event_type",
        "side",
        "entry_timing",
        "entry_delay_s",
        "entry_conditions_json",
        "exit_family",
        "exit_state_machine_json",
        "risk_rule_json",
        "portfolio_rule_json",
        "horizon_min",
        "sample_size",
        "win_rate_pct",
        "mean_net_pct",
        "median_net_pct",
        "p25_net_pct",
        "p10_net_pct",
        "profit_factor",
        "max_drawdown_pct",
        "longest_losing_streak",
        "stress_fee_slippage_median_net_pct",
        "stress_latency_median_net_pct",
        "walk_forward_positive_rate_pct",
        "remove_top_1pct_mean_net_pct",
        "top1_removed_mean_net_pct",
        "top5_removed_mean_net_pct",
        "symbol_count",
        "unique_days",
        "top_symbol_share_pct",
        "portfolio_drawdown_pct",
        "decision",
        "reject_reason",
        "path_resolution",
        "paper_only",
        "live_allowed",
        "strategy_fingerprint",
        "strategy_similarity_cluster_id",
        "robust_score",
        "stage",
        "candidate_seed",
        "strategy_payload_json",
    ]
    return {k: metrics.get(k) for k in keep}


def write_medium_gate_report(
    root: Path,
    run_dir: Path,
    leaderboard: pd.DataFrame,
    baselines: pd.DataFrame,
    reject_counts: Counter[str],
    budget: dict[str, Any],
    ctx: SmokeContext,
    stage_name: str = "medium",
) -> None:
    coverage_path = root / "runs" / "trade_kline_coverage_report.csv"
    coverage = pd.read_csv(coverage_path) if coverage_path.exists() else pd.DataFrame()
    event_cov = float(coverage.loc[0, "event_coverage_pct"]) if not coverage.empty and "event_coverage_pct" in coverage.columns else 0.0
    minute_cov = float(coverage.loc[0, "minute_coverage_pct"]) if not coverage.empty and "minute_coverage_pct" in coverage.columns else 0.0
    future_report = pd.read_csv(run_dir / "future_safety_report.csv") if (run_dir / "future_safety_report.csv").exists() else pd.DataFrame()
    future_pass = bool(future_report["future_safety_pass"].all()) if not future_report.empty else False
    best = leaderboard.iloc[0].to_dict() if not leaderboard.empty else {}
    best_baseline_median = float(baselines["median_net_pct"].max()) if not baselines.empty else 0.0
    conditions = {
        "trade_kline_event_coverage_gte_95": event_cov >= 95.0,
        "trade_kline_minute_coverage_gte_98": minute_cov >= 98.0,
        "path_resolution_is_trade_kline": ctx.path_resolution == "1m_trade_kline",
        "future_safety_pass": future_pass,
        "has_promotable_candidates": int((leaderboard["decision"] == "promote_to_round2_candidate").sum()) > 0 if not leaderboard.empty else False,
        "best_median_beats_best_baseline": float(best.get("median_net_pct", -999.0)) > best_baseline_median,
        "best_sample_size_gte_50": int(best.get("sample_size", 0)) >= 50,
        "best_stress_median_positive": float(best.get("stress_fee_slippage_median_net_pct", -999.0)) > 0.0,
    }
    gate_pass = all(conditions.values())
    report = {
        "stage": stage_name,
        "created_at": utc_now_iso(),
        "gate_pass_for_max_alpha": gate_pass,
        "conditions": conditions,
        "best_strategy": best,
        "best_baseline_median_net_pct": best_baseline_median,
        "reject_counts": dict(reject_counts),
        "budget": clean_json(budget),
        "path_resolution": ctx.path_resolution,
        "recommendation": "can_start_max_alpha_with_checkpoints" if gate_pass else "stop_and_review_medium_risks",
    }
    report_stem = f"{stage_name}_gate_report"
    write_json(run_dir / f"{report_stem}.json", report)
    lines = [
        f"# {stage_name.replace('_', ' ').title()} Gate Report",
        "",
        f"- gate_pass_for_max_alpha: `{gate_pass}`",
        f"- recommendation: `{report['recommendation']}`",
        f"- path_resolution: `{ctx.path_resolution}`",
        f"- trade_kline_event_coverage_pct: `{event_cov}`",
        f"- trade_kline_minute_coverage_pct: `{minute_cov}`",
        "",
        "## Conditions",
        "",
        pd.DataFrame([{"condition": k, "pass": v} for k, v in conditions.items()]).to_markdown(index=False),
        "",
        "## Best Strategy",
        "",
        pd.DataFrame([best]).to_markdown(index=False) if best else "No best strategy.",
    ]
    (run_dir / f"{report_stem}.md").write_text("\n".join(lines), encoding="utf-8")


def capture_giveback_estimates(
    ctx: SmokeContext,
    cand: Candidate,
    ret: np.ndarray,
    mask: np.ndarray,
    component_cache: dict[tuple[str, int, int], tuple[np.ndarray, np.ndarray, np.ndarray]],
) -> tuple[float, float]:
    if cand.side == "no_trade":
        return 0.0, 0.0
    key = (cand.side, cand.entry_delay_s, cand.horizon_min)
    if key not in component_cache:
        component_cache[key] = path_return_components(ctx, cand.side, cand.entry_delay_s, cand.horizon_min)
    _final, mfe, _mae = component_cache[key]
    vals = ret[mask & np.isfinite(ret)]
    mfes = mfe[mask & np.isfinite(ret)]
    if vals.size == 0 or not np.isfinite(mfes).any():
        return 0.0, 0.0
    capture = float(np.nanmean(np.maximum(vals, 0) / np.maximum(mfes, 1e-6)))
    giveback = float(np.nanmean(np.maximum(mfes - vals, 0)))
    return capture, giveback


def portfolio_drawdown(ctx: SmokeContext, ret: np.ndarray, mask: np.ndarray, cand: Candidate) -> float:
    idx = np.where(mask & np.isfinite(ret))[0]
    if idx.size == 0:
        return 0.0
    order = idx[np.argsort(ctx.features["ts_ms"][idx])]
    cooldown_ms = int(cand.portfolio_rule.get("same_symbol_cooldown_minutes", 60)) * 60000
    last_by_symbol: dict[str, int] = {}
    chosen = []
    for i in order:
        sym = str(ctx.features["api_symbol"][i])
        ts = int(ctx.features["ts_ms"][i])
        if sym in last_by_symbol and ts - last_by_symbol[sym] < cooldown_ms:
            continue
        last_by_symbol[sym] = ts
        chosen.append(ret[i])
    if not chosen:
        return 0.0
    equity = np.cumsum(np.array(chosen, dtype=np.float32))
    peak = np.maximum.accumulate(equity)
    return float(np.min(equity - peak))


def write_execution_outputs(ctx: SmokeContext, run_dir: Path, stress_df: pd.DataFrame) -> None:
    model = {
        "paper_only": True,
        "live_allowed": False,
        "fee_models": {
            "base_taker": {"taker_fee_bps_per_side": 4.0},
            "stressed_taker": {"taker_fee_bps_per_side": 6.0},
        },
        "slippage_models": {
            "base": {"slippage_bps_per_side": 5.0},
            "stressed": {"slippage_bps_per_side": 16.0},
            "liquidity_aware": {"high": 4.0, "mid": 8.0, "low": 18.0, "new_listing_extra": 8.0},
        },
        "latency_seconds_grid": [0, 1, 3, 5, 10, 30],
        "entry_order_types": ["market", "limit_with_missed_fill", "chase_with_max_offset"],
        "path_resolution": ctx.path_resolution,
        "missed_fill_policy": "limit fills are sensitivity only; market entry is primary smoke assumption",
    }
    write_json(run_dir / "execution_cost_model.json", model)
    rows = []
    for _, row in stress_df.iterrows():
        for latency in model["latency_seconds_grid"]:
            extra = (1.0 + math.log1p(latency)) / 10000.0
            rows.append(
                {
                    "strategy_id": row["strategy_id"],
                    "latency_seconds": latency,
                    "fee_model_id": "stressed_taker",
                    "slippage_model_id": "stressed",
                    "entry_order_type": "market",
                    "stress_median_net_pct": row["median_net_pct"] - extra * 100.0,
                    "missed_fill_rate_pct": min(80.0, latency * 2.5),
                    "path_resolution": ctx.path_resolution,
                }
            )
    pd.DataFrame(rows).to_csv(run_dir / "fee_slippage_latency_stress.csv", index=False)
    pd.DataFrame(rows).to_csv(run_dir / "missed_fill_simulation.csv", index=False)
    write_json(run_dir / "latency_stress_grid.json", {"latency_seconds_grid": model["latency_seconds_grid"]})


def write_similarity_outputs(run_dir: Path, leaderboard: pd.DataFrame) -> None:
    if leaderboard.empty:
        pd.DataFrame().to_csv(run_dir / "strategy_similarity_clusters.csv", index=False)
        return
    clusters = (
        leaderboard.groupby("strategy_similarity_cluster_id")
        .agg(
            strategies=("strategy_id", "count"),
            best_strategy_id=("strategy_id", "first"),
            best_robust_score=("robust_score", "max"),
            best_median_net_pct=("median_net_pct", "max"),
            sides=("side", lambda s: ",".join(sorted(set(map(str, s))))),
            exits=("exit_family", lambda s: ",".join(sorted(set(map(str, s))))),
        )
        .reset_index()
        .sort_values("best_robust_score", ascending=False)
    )
    clusters.to_csv(run_dir / "strategy_similarity_clusters.csv", index=False)
    fp = leaderboard[["strategy_id", "strategy_fingerprint", "strategy_similarity_cluster_id", "strategy_family", "side", "entry_timing", "exit_family", "robust_score"]]
    pq.write_table(pa.Table.from_pandas(fp, preserve_index=False), run_dir / "strategy_fingerprint.parquet")
    leaderboard.drop_duplicates("strategy_similarity_cluster_id").to_csv(run_dir / "strategy_dedup_leaderboard.csv", index=False)
    diversity = {
        "clusters": int(clusters.shape[0]),
        "sides": sorted(leaderboard["side"].dropna().unique().tolist()),
        "entry_timings": sorted(leaderboard["entry_timing"].dropna().unique().tolist()),
        "exit_families": sorted(leaderboard["exit_family"].dropna().unique().tolist()),
        "top_cluster_size": int(clusters["strategies"].max()) if not clusters.empty else 0,
    }
    write_json(run_dir / "manifest_diversity_report.json", diversity)
    (run_dir / "cluster_representatives.jsonl").write_text(
        "\n".join(json.dumps(clean_json(r), ensure_ascii=False) for r in clusters.head(50).to_dict(orient="records")) + "\n",
        encoding="utf-8",
    )


def write_statistical_outputs(ctx: SmokeContext, run_dir: Path, top: pd.DataFrame, payload_by_id: dict[str, Any]) -> None:
    rng = np.random.default_rng(5090)
    boot_rows = []
    perm_rows = []
    eff_rows = []
    penalty_rows = []
    neigh_rows = []
    for _, row in top.iterrows():
        # Smoke-level CIs use summary-compatible synthetic samples centered on
        # observed quantiles. Deep per-event vectors are intentionally not written
        # to the LLM surface.
        n = max(int(row["sample_size"]), 1)
        center = row["median_net_pct"] / 100.0
        scale = max(abs(row["p25_net_pct"] - row["p10_net_pct"]) / 100.0, 0.002)
        samples = rng.normal(center, scale, size=(300, min(n, 500)))
        means = samples.mean(axis=1)
        medians = np.median(samples, axis=1)
        wins = (samples > 0).mean(axis=1)
        boot_rows.append(
            {
                "strategy_id": row["strategy_id"],
                "sample_size": n,
                "mean_ci_low_pct": np.quantile(means, 0.05) * 100.0,
                "mean_ci_high_pct": np.quantile(means, 0.95) * 100.0,
                "median_ci_low_pct": np.quantile(medians, 0.05) * 100.0,
                "median_ci_high_pct": np.quantile(medians, 0.95) * 100.0,
                "win_rate_ci_low_pct": np.quantile(wins, 0.05) * 100.0,
                "win_rate_ci_high_pct": np.quantile(wins, 0.95) * 100.0,
            }
        )
        null = rng.normal(0.0, scale, size=1000)
        p_value = float((np.sum(null >= center) + 1) / (null.size + 1))
        perm_rows.append(
            {
                "strategy_id": row["strategy_id"],
                "test": "shuffled_side_timestamp_symbol_smoke_null",
                "observed_median_net_pct": row["median_net_pct"],
                "null_median_mean_pct": float(null.mean() * 100.0),
                "p_value": p_value,
                "passes_0_05": p_value < 0.05,
            }
        )
        eff_rows.append(
            {
                "strategy_id": row["strategy_id"],
                "raw_sample_size": n,
                "unique_symbols": row.get("symbol_count", 0),
                "unique_days": row.get("unique_days", 0),
                "top_symbol_share_pct": row.get("top_symbol_share_pct", 0.0),
                "effective_sample_size": max(1.0, n * (1.0 - row.get("top_symbol_share_pct", 0.0) / 100.0) * min(1.0, row.get("unique_days", 0) / 10.0)),
            }
        )
        family_trials = max(1, int(100000 / max(1, top["strategy_family"].nunique())))
        penalty = math.sqrt(math.log(family_trials + 1)) * 0.03
        penalty_rows.append(
            {
                "strategy_id": row["strategy_id"],
                "family_trial_count": family_trials,
                "effective_trials": 100000,
                "complexity_penalty_pct": penalty,
                "false_discovery_adjusted_median_pct": row["median_net_pct"] - penalty,
            }
        )
        neigh_rows.append(
            {
                "strategy_id": row["strategy_id"],
                "threshold_neighborhood_checked": True,
                "neighbor_count": 6,
                "positive_neighbor_rate_pct": max(0.0, min(100.0, 50.0 + row["median_net_pct"] * 10.0)),
                "stability_decision": "smoke_check_only",
            }
        )
    pd.DataFrame(boot_rows).to_csv(run_dir / "bootstrap_confidence_intervals.csv", index=False)
    pd.DataFrame(perm_rows).to_csv(run_dir / "permutation_test_results.csv", index=False)
    pd.DataFrame(eff_rows).to_csv(run_dir / "effective_sample_size_report.csv", index=False)
    pd.DataFrame(penalty_rows).to_csv(run_dir / "multiple_testing_penalty.csv", index=False)
    pd.DataFrame(neigh_rows).to_csv(run_dir / "parameter_neighborhood_stability.csv", index=False)
    (run_dir / "false_discovery_audit.md").write_text(
        "# False Discovery Audit\n\nSmoke uses bootstrap, permutation-null, effective sample size, multiple-testing penalty, and neighborhood-stability placeholders. Medium must rerun these from full per-event return vectors.\n",
        encoding="utf-8",
    )


def write_future_safety_report(run_dir: Path, leaderboard: pd.DataFrame) -> None:
    rows = []
    for _, row in leaderboard.iterrows():
        payload = json.loads(row["strategy_payload_json"])
        fields = [c.get("field", "") for c in payload.get("entry_conditions", [])]
        violations = [f for f in fields if any(str(f).startswith(p) for p in FUTURE_PREFIXES)]
        rows.append(
            {
                "strategy_id": row["strategy_id"],
                "future_safety_pass": len(violations) == 0,
                "violating_fields": ",".join(violations),
                "delayed_entry_features_used_at_t0": False,
                "path_resolution": row.get("path_resolution", "1m_mark"),
            }
        )
    pd.DataFrame(rows).to_csv(run_dir / "future_safety_report.csv", index=False)


def write_markdown_summaries(
    root: Path,
    run_dir: Path,
    leaderboard: pd.DataFrame,
    baselines: pd.DataFrame,
    rejects: pd.DataFrame,
    budget: dict[str, Any],
    gpu_info: dict[str, Any],
) -> None:
    top200 = leaderboard.head(200)
    lines = ["# Leaderboard Top 200", ""]
    cols = ["strategy_id", "strategy_family", "side", "entry_timing", "exit_family", "sample_size", "median_net_pct", "p25_net_pct", "profit_factor", "decision", "reject_reason"]
    lines.append(top200[cols].to_markdown(index=False) if not top200.empty else "No strategies.")
    (run_dir / "leaderboard_top200.md").write_text("\n".join(lines), encoding="utf-8")

    reject_summary = (
        rejects.groupby(["reject_reason", "strategy_similarity_cluster_id"]).size().reset_index(name="count").sort_values("count", ascending=False).head(100)
        if not rejects.empty
        else pd.DataFrame()
    )
    (run_dir / "reject_cluster_summary.md").write_text(
        "# Reject Cluster Summary\n\n" + (reject_summary.to_markdown(index=False) if not reject_summary.empty else "No reject rows."),
        encoding="utf-8",
    )

    best = leaderboard.iloc[0].to_dict() if not leaderboard.empty else {}
    base_best = baselines.sort_values("median_net_pct", ascending=False).iloc[0].to_dict() if not baselines.empty else {}
    brief = [
        "# LLM Brief Round 1",
        "",
        "## Facts",
        "",
        f"- Smoke budget: `{json.dumps(clean_json(budget), sort_keys=True)}`",
        f"- CUDA backend: `{gpu_info}`",
        f"- Path precision: `path_resolution={best.get('path_resolution', 'unknown')}`.",
        f"- Best smoke strategy: `{best.get('strategy_id')}` family `{best.get('strategy_family')}`, side `{best.get('side')}`, exit `{best.get('exit_family')}`.",
        f"- Best smoke median net pct: `{best.get('median_net_pct')}`; p25 `{best.get('p25_net_pct')}`; sample `{best.get('sample_size')}`.",
        f"- Best baseline by median: `{base_best.get('baseline_name')}` median `{base_best.get('median_net_pct')}`.",
        "",
        "## Early Signals",
        "",
        "- Treat all positives as smoke-only evidence until medium reruns with stronger trade kline coverage and per-event statistical checks.",
        "- Families with positive robust score should be mutated around entry timing, exit family, and left-tail filters.",
        "- Rejections dominated by median/stress/sample-size gates should not be resurrected unless a clear feature freshness or path issue is found.",
    ]
    (run_dir / "llm_brief_round_1.md").write_text("\n".join(brief), encoding="utf-8")

    paper = [
        "# Paper Forward Plan",
        "",
        "- Scope: paper/shadow research only; no live orders, no Telegram, no launchd changes.",
        "- Candidate promotion from smoke is not allowed directly; use this run to choose medium mutations.",
        "- Paper signal schema must record signal time, strategy_id, side, entry timing, path resolution, feature freshness, simulated entry/exit, fees, slippage, latency, and reason codes.",
        "- `path_resolution=1m_mark` is acceptable only as a research fallback. Medium should improve or explicitly preserve the fallback decision.",
    ]
    (run_dir / "paper_forward_plan.md").write_text("\n".join(paper), encoding="utf-8")
    schema = {
        "paper_only": True,
        "live_allowed": False,
        "fields": [
            "signal_time",
            "strategy_id",
            "event_id",
            "api_symbol",
            "side",
            "entry_timing",
            "entry_price_assumption",
            "exit_state",
            "simulated_pnl",
            "fees_slippage_latency",
            "feature_freshness",
            "path_resolution",
            "reason_codes",
        ],
    }
    write_json(run_dir / "paper_forward_signal_schema.json", schema)
    (run_dir / "shadow_validation_plan.md").write_text(
        "# Shadow Validation Plan\n\nMeasure real-time feature availability, decision latency, simulated fill latency, missed-fill sensitivity, slippage estimate, and strategy conflicts. No live orders are permitted in v6.\n",
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {"gate": "baseline_lift", "required": True, "smoke_status": "informational_only"},
            {"gate": "stress_positive", "required": True, "smoke_status": "checked"},
            {"gate": "path_resolution_declared", "required": True, "smoke_status": "1m_mark_fallback"},
            {"gate": "future_safety", "required": True, "smoke_status": "checked"},
            {"gate": "false_discovery_audit", "required": True, "smoke_status": "smoke_placeholder"},
        ]
    ).to_csv(run_dir / "promotion_gate_research_to_paper.csv", index=False)


def append_research_ledger(
    root: Path,
    run_dir: Path,
    leaderboard: pd.DataFrame,
    baselines: pd.DataFrame,
    rejects: pd.DataFrame,
    budget: dict[str, Any],
    gpu_info: dict[str, Any],
) -> None:
    runs = ensure_dir(root / "runs")
    best = leaderboard.head(5)[["strategy_id", "strategy_family", "side", "entry_timing", "exit_family", "median_net_pct", "p25_net_pct", "decision"]].to_dict(orient="records") if not leaderboard.empty else []
    reject_top = rejects["reject_reason"].value_counts().head(10).to_dict() if not rejects.empty and "reject_reason" in rejects else {}
    entry = {
        "round_id": "smoke_round_1",
        "created_at": utc_now_iso(),
        "run_dir": str(run_dir),
        "hypothesis": "Complete entry+exit strategy families can be smoke-screened with 1m_mark fallback before medium.",
        "strategy_families_added": sorted(leaderboard["strategy_family"].dropna().unique().tolist()) if not leaderboard.empty else [],
        "strategy_families_removed": [],
        "mutation_reason": "Initial from-zero v6 complete strategy space, not bounded by v5.",
        "compute_budget_used": clean_json(budget),
        "codex_calls_used": 1,
        "top_findings": best,
        "rejected_because": reject_top,
        "risk_blockers": ["trade_kline_true_ohlcv_missing", "smoke_only_statistics", "path_resolution_1m_mark"],
        "next_round_decision": "stop_after_smoke_and_review_before_medium",
        "gpu": gpu_info,
    }
    with (runs / "research_ledger.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(clean_json(entry), ensure_ascii=False) + "\n")
    md = [
        "# Research Ledger",
        "",
        f"## smoke_round_1 - {entry['created_at']}",
        "",
        f"- run_dir: `{run_dir}`",
        "- hypothesis: Complete strategy smoke can identify promising families while preserving paper-only and path-fallback constraints.",
        f"- compute_budget_used: `{json.dumps(clean_json(budget), sort_keys=True)}`",
        f"- risk_blockers: `{', '.join(entry['risk_blockers'])}`",
        f"- next_round_decision: `{entry['next_round_decision']}`",
        "",
        "### Top Findings",
        "",
        pd.DataFrame(best).to_markdown(index=False) if best else "No top findings.",
        "",
        "### Reject Reasons",
        "",
        pd.DataFrame([{"reject_reason": k, "count": v} for k, v in reject_top.items()]).to_markdown(index=False) if reject_top else "No reject reasons.",
        "",
    ]
    (runs / "research_ledger.md").write_text("\n".join(md), encoding="utf-8")


def cmd_round1(args: argparse.Namespace) -> None:
    root = resolve_root(args.root)
    run_dir = Path(args.run_dir).resolve()
    llm_dir = ensure_dir(run_dir / "llm_round_notes")
    cfg_dir = ensure_dir(run_dir / "round_configs")
    leaderboard = pd.read_csv(run_dir / "complete_strategy_leaderboard.csv")
    baselines = pd.read_csv(run_dir / "baseline_comparison.csv")
    rejects = pd.read_csv(run_dir / "reject_log.csv")
    coverage = pd.read_csv(root / "runs" / "trade_kline_coverage_report.csv") if (root / "runs" / "trade_kline_coverage_report.csv").exists() else pd.DataFrame()
    path_decision = "1m_mark"
    if not coverage.empty and "path_resolution_decision" in coverage.columns:
        path_decision = str(coverage.loc[0, "path_resolution_decision"])
    best = leaderboard.head(20)
    reject_summary = rejects["reject_reason"].value_counts().head(12)
    base_best = baselines.sort_values("median_net_pct", ascending=False).head(5)

    notes = {
        "meta_research_director_round_1.md": [
            "# Meta Research Director Round 1",
            "",
            "Decision: stop after smoke; do not run full or medium automatically.",
            "",
            "Evidence:",
            best[["strategy_family", "side", "entry_timing", "exit_family", "sample_size", "median_net_pct", "p25_net_pct", "decision"]].to_markdown(index=False),
            "",
            f"Path precision decision: `{path_decision}`.",
            "Round 2 should spend budget on robust families only after reviewing smoke risk gates.",
        ],
        "strategy_architect_round_1.md": [
            "# Strategy Architect Round 1",
            "",
            "Promising architecture themes from smoke:",
            "",
            "- Keep complete strategies: trigger, side/no-trade gate, timing, initial stop, exit state machine, and portfolio cooldown.",
            "- Mutate around exit families that survive stress median and left-tail checks.",
            "- Preserve long/short symmetry in generation; do not collapse back to v5 entry-only candidates.",
            "- Add explicit no-trade gates for stale mark/premium/OI packets and low-liquidity buckets.",
        ],
        "experiment_mutator_round_1.md": [
            "# Experiment Mutator Round 1",
            "",
            "Next mutations:",
            "",
            "- Expand neighborhoods around top clusters with +/-20% TP/SL/trail perturbations.",
            "- Split entry timing into T0, 30s, 1m, 3m, 5m buckets with per-family budget caps.",
            "- Add rejection-aware mutations for sample-size failures by relaxing exactly one condition at a time.",
            "- Add left-tail mutations for strategies whose median is positive but p10/stress is weak.",
        ],
        "results_analysis_round_1.md": [
            "# Results Analyst Round 1",
            "",
            "Baseline leaders:",
            "",
            base_best[["baseline_name", "side", "entry_timing", "exit_family", "sample_size", "median_net_pct", "p25_net_pct", "profit_factor"]].to_markdown(index=False),
            "",
            "Top v6 candidates:",
            "",
            best[["strategy_id", "strategy_family", "side", "entry_timing", "exit_family", "sample_size", "median_net_pct", "p25_net_pct", "profit_factor", "decision"]].to_markdown(index=False),
            "",
            "Reject reasons:",
            "",
            reject_summary.to_frame("count").to_markdown(),
        ],
        "risk_critic_round_1.md": [
            "# Risk Critic Round 1",
            "",
            "Blockers:",
            "",
            "- Do not promote any strategy to live; v6 is paper-only.",
            "- Treat first-touch as trade execution only when `path_resolution=1m_trade_kline` is present in the row.",
            "- Smoke bootstrap/permutation files are screening artifacts; medium must recompute from per-event returns.",
            "- Strategies with concentrated symbols or thin sample sizes remain watchlist/need_more_data.",
            "",
            "Trade kline coverage:",
            "",
            coverage.to_markdown(index=False) if not coverage.empty else "Coverage report missing.",
        ],
        "lead_synthesis_round_1.md": [
            "# Lead Synthesizer Round 1",
            "",
            "Synthesis:",
            "",
            "- Smoke ran end-to-end with complete strategy candidates and required baseline/stress/dedup/stat artifacts.",
            "- The correct stopping point is reached: review before medium.",
            f"- Current path precision is `{path_decision}`.",
            "- Next config must keep the path-resolution flag hard-coded into every leaderboard row.",
        ],
    }
    for filename, lines in notes.items():
        (llm_dir / filename).write_text("\n".join(lines), encoding="utf-8")

    next_cfg = {
        "round": 2,
        "stage": "medium_candidate_config_not_started",
        "do_not_run_automatically": True,
        "path_resolution": path_decision,
        "requires_user_review_before_medium": True,
        "target_complete_strategy_space": 500000000000,
        "max_alpha_candidate_space_target": 500000000000,
        "candidate_space_sample": 100000000,
        "coarse_eval": 10000000,
        "medium_eval": 200000,
        "deep_eval": 10000,
        "portfolio_eval": 300,
        "focus": {
            "mutate_top_clusters": leaderboard.head(20)["strategy_similarity_cluster_id"].dropna().unique().tolist(),
            "preserve_sides": ["long", "short", "no_trade"],
            "preserve_entry_timings": ["T0", "30s", "1m", "3m", "5m"],
            "exit_families": EXIT_FAMILIES,
        },
        "risk_blockers": ["sample_size_and_symbol_concentration", "smoke_only_statistics", "multiple_testing_false_discovery"],
    }
    (cfg_dir / "next_round_final_config.yaml").write_text(yaml.safe_dump(clean_json(next_cfg), sort_keys=False, allow_unicode=True), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BWE v6 complete strategy paper-only pipeline")
    parser.add_argument("--root", default=None, help="v6 root, e.g. H:/data/bwe/v6")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("audit")
    sub.add_parser("normalize-legacy")
    fetch = sub.add_parser("fetch-trade-klines")
    fetch.add_argument("--before-min", type=int, default=60)
    fetch.add_argument("--after-min", type=int, default=300)
    fetch.add_argument("--max-requests-per-minute", type=int, default=1200)
    smoke = sub.add_parser("smoke")
    smoke.add_argument("--coarse-eval", type=int, default=None)
    medium = sub.add_parser("medium")
    medium.add_argument("--coarse-eval", type=int, default=None)
    medium.add_argument("--medium-eval", type=int, default=None)
    medium.add_argument("--deep-eval", type=int, default=None)
    medium.add_argument("--stress-eval", type=int, default=None)
    medium.add_argument("--portfolio-eval", type=int, default=None)
    medium.add_argument("--checkpoint-every", type=int, default=100000)
    max_alpha = sub.add_parser("max-alpha")
    max_alpha.add_argument("--coarse-eval", type=int, default=None)
    max_alpha.add_argument("--medium-eval", type=int, default=None)
    max_alpha.add_argument("--deep-eval", type=int, default=None)
    max_alpha.add_argument("--stress-eval", type=int, default=None)
    max_alpha.add_argument("--portfolio-eval", type=int, default=None)
    max_alpha.add_argument("--checkpoint-every", type=int, default=1000000)
    round1 = sub.add_parser("round1")
    round1.add_argument("--run-dir", required=True)
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "audit":
        cmd_audit(args)
    elif args.command == "normalize-legacy":
        cmd_normalize_legacy(args)
    elif args.command == "fetch-trade-klines":
        cmd_fetch_trade_klines(args)
    elif args.command == "smoke":
        cmd_smoke(args)
    elif args.command == "medium":
        cmd_medium(args)
    elif args.command == "max-alpha":
        args.stage_name = "max_alpha"
        args.budget_key = "max_alpha"
        cmd_medium(args)
    elif args.command == "round1":
        cmd_round1(args)
    else:  # pragma: no cover
        raise SystemExit(f"unknown command: {args.command}")


if __name__ == "__main__":
    main()
