#!/usr/bin/env python3
"""Collect entry-time Binance derivatives features for recent BWE events.

This is a research-only backfill. It reads BWE event artifacts and public
Binance market-data endpoints, then writes feature tables beside the existing
fullrun artifacts. It does not read secrets, place orders, or touch live config.
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import requests


BINANCE_BASE = "https://fapi.binance.com"
DEFAULT_EVENTS = Path("/Users/ye/.hermes/research/bwe_three_channel_fullrun3/events.parquet")
DEFAULT_FORWARD = Path("/Users/ye/.hermes/research/bwe_three_channel_fullrun3/forward.parquet")
DEFAULT_KLINE_DB = Path("/Users/ye/.hermes/research/binance_futures_1m_collector_runtime/binance_futures_1m.sqlite3")
DEFAULT_OUT = Path("/Users/ye/.hermes/research/bwe_three_channel_fullrun3/binance_event_features_20260425")

FIVE_MIN_MS = 5 * 60_000
ONE_HOUR_MS = 60 * 60_000
ONE_DAY_MS = 24 * 60 * 60_000


@dataclass(frozen=True)
class MetricEndpoint:
    name: str
    path: str
    symbol_param: str
    extra_params: dict[str, Any]
    timestamp_field: str
    numeric_fields: tuple[str, ...]


METRICS: tuple[MetricEndpoint, ...] = (
    MetricEndpoint(
        "open_interest_hist",
        "/futures/data/openInterestHist",
        "symbol",
        {"period": "5m", "limit": 500},
        "timestamp",
        ("sumOpenInterest", "sumOpenInterestValue", "CMCCirculatingSupply"),
    ),
    MetricEndpoint(
        "global_long_short_account_ratio",
        "/futures/data/globalLongShortAccountRatio",
        "symbol",
        {"period": "5m", "limit": 500},
        "timestamp",
        ("longShortRatio", "longAccount", "shortAccount"),
    ),
    MetricEndpoint(
        "top_trader_long_short_account_ratio",
        "/futures/data/topLongShortAccountRatio",
        "symbol",
        {"period": "5m", "limit": 500},
        "timestamp",
        ("longShortRatio", "longAccount", "shortAccount"),
    ),
    MetricEndpoint(
        "top_trader_long_short_position_ratio",
        "/futures/data/topLongShortPositionRatio",
        "symbol",
        {"period": "5m", "limit": 500},
        "timestamp",
        ("longShortRatio", "longAccount", "shortAccount"),
    ),
    MetricEndpoint(
        "taker_buy_sell_volume",
        "/futures/data/takerlongshortRatio",
        "symbol",
        {"period": "5m", "limit": 500},
        "timestamp",
        ("buySellRatio", "buyVol", "sellVol"),
    ),
    MetricEndpoint(
        "basis_perpetual",
        "/futures/data/basis",
        "pair",
        {"contractType": "PERPETUAL", "period": "5m", "limit": 500},
        "timestamp",
        ("indexPrice", "futuresPrice", "basisRate", "basis"),
    ),
)


class RateLimiter:
    def __init__(self, max_rps: float) -> None:
        self.interval = 1.0 / max(max_rps, 0.1)
        self.lock = threading.Lock()
        self.next_at = 0.0

    def wait(self) -> None:
        with self.lock:
            now = time.monotonic()
            if now < self.next_at:
                time.sleep(self.next_at - now)
            self.next_at = max(now, self.next_at) + self.interval


def request_json(session: requests.Session, limiter: RateLimiter, path: str, params: dict[str, Any], *, retries: int = 5) -> Any:
    url = BINANCE_BASE + path
    last_error: str | None = None
    for attempt in range(retries):
        limiter.wait()
        try:
            resp = session.get(url, params=params, timeout=20)
            if resp.status_code in {418, 429}:
                retry_after = float(resp.headers.get("Retry-After", "2"))
                time.sleep(max(retry_after, 2.0) * (attempt + 1))
                last_error = f"rate_limited {resp.status_code}: {resp.text[:200]}"
                continue
            if resp.status_code >= 500:
                time.sleep(1.5 * (attempt + 1))
                last_error = f"server_error {resp.status_code}: {resp.text[:200]}"
                continue
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # noqa: BLE001
            last_error = repr(exc)
            time.sleep(1.0 * (attempt + 1))
    raise RuntimeError(f"GET {path} failed after {retries} retries params={params}: {last_error}")


def load_recent_events(events_path: Path, days_from_latest_event: int) -> pd.DataFrame:
    events = pd.read_parquet(events_path)
    max_ts = int(events["ts_ms"].max())
    cutoff = max_ts - days_from_latest_event * ONE_DAY_MS
    recent = events[
        (pd.to_numeric(events["ts_ms"], errors="coerce") >= cutoff)
        & (events["exchange"].eq("binanceusdm"))
        & (events["api_symbol"].notna())
        & (events["is_tradable_at_event"].eq(True))
    ].copy()
    recent["api_symbol"] = recent["api_symbol"].astype(str)
    recent["event_key"] = (
        recent["channel"].astype(str)
        + "#"
        + recent["post_id"].astype(str)
        + "#"
        + recent["api_symbol"].astype(str)
    )
    recent["event_ts_utc"] = pd.to_datetime(recent["ts_ms"], unit="ms", utc=True).astype(str)
    return recent.sort_values(["api_symbol", "ts_ms", "post_id"]).reset_index(drop=True)


def chunk_windows(events: pd.DataFrame, rows_per_chunk: int = 500) -> list[tuple[str, int, int]]:
    out: list[tuple[str, int, int]] = []
    chunk_ms = FIVE_MIN_MS * rows_per_chunk
    for symbol, group in events.groupby("api_symbol", sort=True):
        start = int(group["ts_ms"].min()) - ONE_HOUR_MS
        end = int(group["ts_ms"].max()) + ONE_HOUR_MS
        cur = (start // FIVE_MIN_MS) * FIVE_MIN_MS
        while cur <= end:
            nxt = min(cur + chunk_ms - 1, end)
            out.append((symbol, cur, nxt))
            cur = nxt + 1
    return out


def fetch_exchange_info(session: requests.Session, limiter: RateLimiter) -> pd.DataFrame:
    payload = request_json(session, limiter, "/fapi/v1/exchangeInfo", {})
    rows: list[dict[str, Any]] = []
    for item in payload.get("symbols", []):
        rows.append(
            {
                "api_symbol": item.get("symbol"),
                "pair": item.get("pair"),
                "base_asset": item.get("baseAsset"),
                "quote_asset": item.get("quoteAsset"),
                "margin_asset": item.get("marginAsset"),
                "contract_type": item.get("contractType"),
                "status": item.get("status"),
                "onboard_ts_ms": item.get("onboardDate"),
                "delivery_ts_ms": item.get("deliveryDate"),
                "trigger_protect": item.get("triggerProtect"),
                "market_take_bound": item.get("marketTakeBound"),
            }
        )
    return pd.DataFrame(rows)


def fetch_metric(metric: MetricEndpoint, windows: list[tuple[str, int, int]], max_workers: int, limiter: RateLimiter) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    def one(window: tuple[str, int, int]) -> list[dict[str, Any]]:
        symbol, start, end = window
        session = requests.Session()
        params = {metric.symbol_param: symbol, "startTime": start, "endTime": end, **metric.extra_params}
        payload = request_json(session, limiter, metric.path, params)
        if not isinstance(payload, list):
            return []
        out: list[dict[str, Any]] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            ts = item.get(metric.timestamp_field)
            record = {"api_symbol": symbol, "metric_ts_ms": int(ts) if ts is not None else None}
            for field in metric.numeric_fields:
                record[f"{metric.name}__{field}"] = item.get(field)
            out.append(record)
        return out

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(one, w): w for w in windows}
        done = 0
        for fut in as_completed(futures):
            done += 1
            window = futures[fut]
            try:
                rows.extend(fut.result())
            except Exception as exc:  # noqa: BLE001
                errors.append({"metric": metric.name, "window": window, "error": repr(exc)})
            if done % 100 == 0 or done == len(futures):
                print(f"[{metric.name}] windows {done}/{len(futures)} rows={len(rows)} errors={len(errors)}", flush=True)

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.drop_duplicates(["api_symbol", "metric_ts_ms"]).sort_values(["api_symbol", "metric_ts_ms"])
        for col in df.columns:
            if col not in {"api_symbol", "metric_ts_ms"}:
                df[col] = pd.to_numeric(df[col], errors="coerce")
    if errors:
        df.attrs["errors"] = errors
    return df


def fetch_funding(events: pd.DataFrame, max_workers: int, limiter: RateLimiter) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    symbol_windows = [
        (symbol, int(group["ts_ms"].min()) - 12 * ONE_HOUR_MS, int(group["ts_ms"].max()) + 12 * ONE_HOUR_MS)
        for symbol, group in events.groupby("api_symbol", sort=True)
    ]

    def one(symbol: str, start: int, end: int) -> list[dict[str, Any]]:
        session = requests.Session()
        payload = request_json(
            session,
            limiter,
            "/fapi/v1/fundingRate",
            {"symbol": symbol, "startTime": start, "endTime": end, "limit": 1000},
        )
        if not isinstance(payload, list):
            return []
        out: list[dict[str, Any]] = []
        for item in payload:
            out.append(
                {
                    "api_symbol": symbol,
                    "funding_ts_ms": int(item.get("fundingTime")),
                    "funding_rate": item.get("fundingRate"),
                    "funding_mark_price": item.get("markPrice"),
                }
            )
        return out

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(one, *w): w for w in symbol_windows}
        for idx, fut in enumerate(as_completed(futures), 1):
            w = futures[fut]
            try:
                rows.extend(fut.result())
            except Exception as exc:  # noqa: BLE001
                errors.append({"symbol_window": w, "error": repr(exc)})
            if idx % 50 == 0 or idx == len(futures):
                print(f"[funding_rate] symbols {idx}/{len(futures)} rows={len(rows)} errors={len(errors)}", flush=True)
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.drop_duplicates(["api_symbol", "funding_ts_ms"]).sort_values(["api_symbol", "funding_ts_ms"])
        for col in ["funding_rate", "funding_mark_price"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if errors:
        df.attrs["errors"] = errors
    return df


def load_local_kline_features(events: pd.DataFrame, db_path: Path) -> pd.DataFrame:
    if not db_path.exists() or events.empty:
        return pd.DataFrame()
    symbols = sorted(events["api_symbol"].dropna().unique().tolist())
    start = int(events["ts_ms"].min()) - 60_000
    end = int(events["ts_ms"].max()) + 60_000
    placeholders = ",".join("?" for _ in symbols)
    query = f"""
        select symbol as api_symbol,
               open_time_ms as kline_1m_open_time_ms,
               close_time_ms as kline_1m_close_time_ms,
               open as kline_1m_open,
               high as kline_1m_high,
               low as kline_1m_low,
               close as kline_1m_close,
               volume as kline_1m_volume,
               quote_volume as kline_1m_quote_volume,
               trade_count as kline_1m_trade_count,
               taker_buy_base_volume as kline_1m_taker_buy_base_volume,
               taker_buy_quote_volume as kline_1m_taker_buy_quote_volume
        from klines_1m
        where open_time_ms between ? and ?
          and symbol in ({placeholders})
    """
    with sqlite3.connect(db_path) as con:
        df = pd.read_sql_query(query, con, params=[start, end, *symbols])
    if not df.empty:
        df = df.sort_values(["api_symbol", "kline_1m_open_time_ms"])
        numeric = [c for c in df.columns if c != "api_symbol"]
        for col in numeric:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def merge_asof_feature(events: pd.DataFrame, feature: pd.DataFrame, *, ts_col: str, tolerance_ms: int, prefix_cols: bool = False) -> pd.DataFrame:
    if feature.empty:
        return events
    left = events.sort_values(["api_symbol", "ts_ms"]).copy()
    right = feature.sort_values(["api_symbol", ts_col]).copy()
    merged_parts: list[pd.DataFrame] = []
    for symbol, left_group in left.groupby("api_symbol", sort=True):
        right_group = right[right["api_symbol"] == symbol]
        if right_group.empty:
            merged_parts.append(left_group)
            continue
        merged = pd.merge_asof(
            left_group.sort_values("ts_ms"),
            right_group.sort_values(ts_col),
            left_on="ts_ms",
            right_on=ts_col,
            direction="backward",
            tolerance=tolerance_ms,
            suffixes=("", "_feature"),
        )
        if "api_symbol_feature" in merged.columns:
            merged = merged.drop(columns=["api_symbol_feature"])
        merged_parts.append(merged)
    out = pd.concat(merged_parts, ignore_index=True).sort_values(["ts_ms", "channel", "post_id"])
    return out


def attach_features(events: pd.DataFrame, metric_frames: dict[str, pd.DataFrame], funding: pd.DataFrame, local_klines: pd.DataFrame) -> pd.DataFrame:
    out = events.copy()
    for name, frame in metric_frames.items():
        out = merge_asof_feature(out, frame, ts_col="metric_ts_ms", tolerance_ms=10 * 60_000)
        metric_cols = [c for c in out.columns if c.startswith(f"{name}__")]
        if metric_cols:
            out[f"{name}__age_ms"] = out["ts_ms"] - out["metric_ts_ms"]
            out = out.drop(columns=["metric_ts_ms"])
    out = merge_asof_feature(out, funding, ts_col="funding_ts_ms", tolerance_ms=12 * ONE_HOUR_MS)
    if "funding_ts_ms" in out.columns:
        out["funding_age_ms"] = out["ts_ms"] - out["funding_ts_ms"]
    out = merge_asof_feature(out, local_klines, ts_col="kline_1m_open_time_ms", tolerance_ms=90_000)
    if "kline_1m_open_time_ms" in out.columns:
        out["kline_1m_age_ms"] = out["ts_ms"] - out["kline_1m_open_time_ms"]
        if {"kline_1m_taker_buy_quote_volume", "kline_1m_quote_volume"} <= set(out.columns):
            out["kline_1m_taker_buy_quote_share"] = out["kline_1m_taker_buy_quote_volume"] / out["kline_1m_quote_volume"].replace(0, pd.NA)
    return out


def write_feature_registry(out_dir: Path) -> None:
    registry = {
        "schema": "bwe_binance_event_features_v1",
        "rule": "Only fields marked allowed_for_entry=true may be used by entry rules. Future returns, MFE, MAE, and labels are excluded.",
        "features": {
            "open_interest_hist": {"source": "/futures/data/openInterestHist", "period": "5m", "known_at": "latest_binance_bucket_before_message_ts", "allowed_for_entry": True},
            "global_long_short_account_ratio": {"source": "/futures/data/globalLongShortAccountRatio", "period": "5m", "known_at": "latest_binance_bucket_before_message_ts", "allowed_for_entry": True},
            "top_trader_long_short_account_ratio": {"source": "/futures/data/topLongShortAccountRatio", "period": "5m", "known_at": "latest_binance_bucket_before_message_ts", "allowed_for_entry": True},
            "top_trader_long_short_position_ratio": {"source": "/futures/data/topLongShortPositionRatio", "period": "5m", "known_at": "latest_binance_bucket_before_message_ts", "allowed_for_entry": True},
            "taker_buy_sell_volume": {"source": "/futures/data/takerlongshortRatio", "period": "5m", "known_at": "latest_binance_bucket_before_message_ts", "allowed_for_entry": True},
            "basis_perpetual": {"source": "/futures/data/basis", "period": "5m", "known_at": "latest_binance_bucket_before_message_ts", "allowed_for_entry": True},
            "funding_rate": {"source": "/fapi/v1/fundingRate", "known_at": "latest_funding_before_message_ts", "allowed_for_entry": True},
            "kline_1m_*": {"source": "local binance_futures_1m.sqlite3", "known_at": "latest_local_1m_kline_before_message_ts", "allowed_for_entry": True},
        },
    }
    (out_dir / "feature_registry.json").write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")


def coverage_report(events: pd.DataFrame, enriched: pd.DataFrame, metric_frames: dict[str, pd.DataFrame], funding: pd.DataFrame, local_klines: pd.DataFrame, out_dir: Path) -> None:
    feature_cols = [c for c in enriched.columns if "__" in c or c.startswith("funding_") or c.startswith("kline_1m_")]
    coverage = {
        "event_rows": int(len(events)),
        "unique_symbols": int(events["api_symbol"].nunique()),
        "event_range_utc": [str(pd.to_datetime(events["ts_ms"].min(), unit="ms", utc=True)), str(pd.to_datetime(events["ts_ms"].max(), unit="ms", utc=True))],
        "channels": events["channel"].value_counts().to_dict(),
        "raw_rows": {name: int(len(frame)) for name, frame in metric_frames.items()},
        "funding_rows": int(len(funding)),
        "local_kline_rows": int(len(local_klines)),
        "feature_non_null_counts": {col: int(enriched[col].notna().sum()) for col in feature_cols},
        "feature_coverage_pct": {col: round(float(enriched[col].notna().mean() * 100.0), 4) for col in feature_cols},
        "outputs": {
            "events_enriched": str(out_dir / "bwe_events_recent_binance_features.parquet"),
            "forward_recent_enriched": str(out_dir / "bwe_forward_recent_binance_features_merged.parquet"),
            "feature_registry": str(out_dir / "feature_registry.json"),
        },
    }
    (out_dir / "coverage_report.json").write_text(json.dumps(coverage, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# BWE Binance Event Feature Backfill",
        "",
        f"- events: `{coverage['event_rows']}`",
        f"- unique_symbols: `{coverage['unique_symbols']}`",
        f"- range_utc: `{coverage['event_range_utc'][0]}` -> `{coverage['event_range_utc'][1]}`",
        f"- raw_rows: `{json.dumps(coverage['raw_rows'], ensure_ascii=False)}`",
        f"- funding_rows: `{coverage['funding_rows']}`",
        f"- local_kline_rows: `{coverage['local_kline_rows']}`",
        "",
        "## Feature coverage",
    ]
    for col, pct in sorted(coverage["feature_coverage_pct"].items()):
        lines.append(f"- {col}: {pct}%")
    (out_dir / "coverage_report.md").write_text("\n".join(lines), encoding="utf-8")


def run(args: argparse.Namespace) -> None:
    out_dir = Path(args.out_dir)
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    limiter = RateLimiter(args.max_rps)

    events = load_recent_events(Path(args.events), args.days_from_latest_event)
    if args.max_events and len(events) > args.max_events:
        events = events.tail(args.max_events).copy()
    events.to_parquet(out_dir / "bwe_events_recent_base.parquet", index=False)
    print(f"[events] rows={len(events)} symbols={events['api_symbol'].nunique()}", flush=True)

    exchange_info = fetch_exchange_info(session, limiter)
    exchange_info.to_parquet(raw_dir / "exchange_info.parquet", index=False)
    active = exchange_info[(exchange_info["status"] == "TRADING") & (exchange_info["contract_type"] == "PERPETUAL")]["api_symbol"].astype(str)
    events["binance_status_active_now"] = events["api_symbol"].isin(set(active))
    events = events[events["binance_status_active_now"]].copy()
    print(f"[exchangeInfo] active_event_rows={len(events)} active_symbols={events['api_symbol'].nunique()}", flush=True)

    windows = chunk_windows(events)
    print(f"[windows] {len(windows)} windows per 5m metric endpoint", flush=True)
    metric_frames: dict[str, pd.DataFrame] = {}
    for metric in METRICS:
        df = fetch_metric(metric, windows, args.max_workers, limiter)
        metric_frames[metric.name] = df
        df.to_parquet(raw_dir / f"{metric.name}.parquet", index=False)
        if df.attrs.get("errors"):
            (raw_dir / f"{metric.name}_errors.json").write_text(json.dumps(df.attrs["errors"], ensure_ascii=False, indent=2), encoding="utf-8")

    funding = fetch_funding(events, args.max_workers, limiter)
    funding.to_parquet(raw_dir / "funding_rate.parquet", index=False)
    if funding.attrs.get("errors"):
        (raw_dir / "funding_rate_errors.json").write_text(json.dumps(funding.attrs["errors"], ensure_ascii=False, indent=2), encoding="utf-8")

    local_klines = load_local_kline_features(events, Path(args.kline_db))
    local_klines.to_parquet(raw_dir / "local_kline_1m_event_window.parquet", index=False)

    enriched = attach_features(events, metric_frames, funding, local_klines)
    enriched.to_parquet(out_dir / "bwe_events_recent_binance_features.parquet", index=False)

    forward_path = Path(args.forward)
    if forward_path.exists():
        forward = pd.read_parquet(forward_path)
        forward["event_key"] = forward["channel"].astype(str) + "#" + forward["post_id"].astype(str) + "#" + forward["api_symbol"].astype(str)
        feature_cols = [c for c in enriched.columns if c not in set(forward.columns) or c == "event_key"]
        merged = forward[forward["event_key"].isin(set(enriched["event_key"]))].merge(
            enriched[feature_cols],
            on="event_key",
            how="left",
            suffixes=("", "_binance_feature"),
        )
        merged.to_parquet(out_dir / "bwe_forward_recent_binance_features_merged.parquet", index=False)

    write_feature_registry(out_dir)
    coverage_report(events, enriched, metric_frames, funding, local_klines, out_dir)
    print(json.dumps({"out_dir": str(out_dir), "events": len(events), "symbols": int(events["api_symbol"].nunique())}, ensure_ascii=False), flush=True)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Collect Binance event-time feature pack for recent BWE events")
    p.add_argument("--events", default=str(DEFAULT_EVENTS))
    p.add_argument("--forward", default=str(DEFAULT_FORWARD))
    p.add_argument("--kline-db", default=str(DEFAULT_KLINE_DB))
    p.add_argument("--out-dir", default=str(DEFAULT_OUT))
    p.add_argument("--days-from-latest-event", type=int, default=7)
    p.add_argument("--max-events", type=int, default=0)
    p.add_argument("--max-workers", type=int, default=6)
    p.add_argument("--max-rps", type=float, default=3.0)
    return p


if __name__ == "__main__":
    run(build_parser().parse_args())
