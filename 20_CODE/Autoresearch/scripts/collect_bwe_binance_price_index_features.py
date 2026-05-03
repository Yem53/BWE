#!/usr/bin/env python3
"""Collect Binance mark-price and premium-index klines for BWE event times."""

from __future__ import annotations

import argparse
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import requests


BINANCE_BASE = "https://fapi.binance.com"
DEFAULT_FEATURE_DIR = Path("/Users/ye/.hermes/research/bwe_three_channel_fullrun3/binance_event_features_20260425")
ONE_MIN_MS = 60_000
ONE_HOUR_MS = 60 * 60_000


@dataclass(frozen=True)
class KlineEndpoint:
    name: str
    path: str
    prefix: str


KLINES = (
    KlineEndpoint("mark_price_1m", "/fapi/v1/markPriceKlines", "mark_1m"),
    KlineEndpoint("premium_index_1m", "/fapi/v1/premiumIndexKlines", "premium_1m"),
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


def request_json(session: requests.Session, limiter: RateLimiter, path: str, params: dict[str, Any]) -> Any:
    url = BINANCE_BASE + path
    last_error = None
    for attempt in range(5):
        limiter.wait()
        try:
            resp = session.get(url, params=params, timeout=20)
            if resp.status_code in {418, 429}:
                time.sleep(max(float(resp.headers.get("Retry-After", "2")), 2.0) * (attempt + 1))
                last_error = resp.text[:200]
                continue
            if resp.status_code >= 500:
                time.sleep(1.5 * (attempt + 1))
                last_error = resp.text[:200]
                continue
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # noqa: BLE001
            last_error = repr(exc)
            time.sleep(1.0 * (attempt + 1))
    raise RuntimeError(f"GET {path} failed params={params}: {last_error}")


def chunk_windows(events: pd.DataFrame, rows_per_chunk: int = 1000) -> list[tuple[str, int, int]]:
    windows: list[tuple[str, int, int]] = []
    chunk_ms = rows_per_chunk * ONE_MIN_MS
    for symbol, group in events.groupby("api_symbol", sort=True):
        start = int(group["ts_ms"].min()) - ONE_HOUR_MS
        end = int(group["ts_ms"].max()) + ONE_HOUR_MS
        cur = (start // ONE_MIN_MS) * ONE_MIN_MS
        while cur <= end:
            nxt = min(cur + chunk_ms - 1, end)
            windows.append((symbol, cur, nxt))
            cur = nxt + 1
    return windows


def fetch_kline(endpoint: KlineEndpoint, windows: list[tuple[str, int, int]], max_workers: int, limiter: RateLimiter) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    def one(window: tuple[str, int, int]) -> list[dict[str, Any]]:
        symbol, start, end = window
        session = requests.Session()
        payload = request_json(
            session,
            limiter,
            endpoint.path,
            {"symbol": symbol, "interval": "1m", "startTime": start, "endTime": end, "limit": 1000},
        )
        out: list[dict[str, Any]] = []
        if not isinstance(payload, list):
            return out
        for item in payload:
            if not isinstance(item, list) or len(item) < 7:
                continue
            out.append(
                {
                    "api_symbol": symbol,
                    f"{endpoint.prefix}_open_time_ms": int(item[0]),
                    f"{endpoint.prefix}_open": item[1],
                    f"{endpoint.prefix}_high": item[2],
                    f"{endpoint.prefix}_low": item[3],
                    f"{endpoint.prefix}_close": item[4],
                    f"{endpoint.prefix}_close_time_ms": int(item[6]),
                }
            )
        return out

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(one, w): w for w in windows}
        for idx, fut in enumerate(as_completed(futures), 1):
            try:
                rows.extend(fut.result())
            except Exception as exc:  # noqa: BLE001
                errors.append({"window": futures[fut], "error": repr(exc)})
            if idx % 200 == 0 or idx == len(futures):
                print(f"[{endpoint.name}] windows {idx}/{len(futures)} rows={len(rows)} errors={len(errors)}", flush=True)
    df = pd.DataFrame(rows)
    if not df.empty:
        ts_col = f"{endpoint.prefix}_open_time_ms"
        df = df.drop_duplicates(["api_symbol", ts_col]).sort_values(["api_symbol", ts_col])
        for col in df.columns:
            if col != "api_symbol":
                df[col] = pd.to_numeric(df[col], errors="coerce")
    if errors:
        df.attrs["errors"] = errors
    return df


def merge_asof(events: pd.DataFrame, feature: pd.DataFrame, ts_col: str) -> pd.DataFrame:
    if feature.empty:
        return events
    parts: list[pd.DataFrame] = []
    for symbol, left in events.sort_values(["api_symbol", "ts_ms"]).groupby("api_symbol", sort=True):
        right = feature[feature["api_symbol"] == symbol]
        if right.empty:
            parts.append(left)
            continue
        merged = pd.merge_asof(
            left.sort_values("ts_ms"),
            right.sort_values(ts_col),
            left_on="ts_ms",
            right_on=ts_col,
            direction="backward",
            tolerance=120_000,
            suffixes=("", "_kline"),
        )
        if "api_symbol_kline" in merged.columns:
            merged = merged.drop(columns=["api_symbol_kline"])
        parts.append(merged)
    return pd.concat(parts, ignore_index=True).sort_values(["ts_ms", "channel", "post_id"])


def run(args: argparse.Namespace) -> None:
    feature_dir = Path(args.feature_dir)
    raw_dir = feature_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    events_path = feature_dir / "bwe_events_recent_binance_features.parquet"
    if not events_path.exists():
        events_path = feature_dir / "bwe_events_recent_base.parquet"
    events = pd.read_parquet(events_path)
    windows = chunk_windows(events)
    limiter = RateLimiter(args.max_rps)
    frames: dict[str, pd.DataFrame] = {}
    for endpoint in KLINES:
        df = fetch_kline(endpoint, windows, args.max_workers, limiter)
        frames[endpoint.name] = df
        df.to_parquet(raw_dir / f"{endpoint.name}.parquet", index=False)
        if df.attrs.get("errors"):
            (raw_dir / f"{endpoint.name}_errors.json").write_text(json.dumps(df.attrs["errors"], ensure_ascii=False, indent=2), encoding="utf-8")

    enriched = events.copy()
    for endpoint in KLINES:
        ts_col = f"{endpoint.prefix}_open_time_ms"
        enriched = merge_asof(enriched, frames[endpoint.name], ts_col)
        if ts_col in enriched.columns:
            enriched[f"{endpoint.prefix}_age_ms"] = enriched["ts_ms"] - enriched[ts_col]

    if {"mark_1m_close", "premium_1m_close"} <= set(enriched.columns):
        enriched["mark_minus_index_proxy_pct"] = pd.NA
        if "basis_perpetual__indexPrice" in enriched.columns:
            enriched["mark_minus_index_proxy_pct"] = (
                (pd.to_numeric(enriched["mark_1m_close"], errors="coerce") / pd.to_numeric(enriched["basis_perpetual__indexPrice"], errors="coerce") - 1.0) * 100.0
            )

    enriched.to_parquet(feature_dir / "bwe_events_recent_binance_features.parquet", index=False)

    forward_path = feature_dir / "bwe_forward_recent_binance_features_merged.parquet"
    if forward_path.exists():
        forward = pd.read_parquet(forward_path)
        feature_cols = [c for c in enriched.columns if c not in set(forward.columns) or c == "event_key"]
        if "event_key" in forward.columns and "event_key" in enriched.columns:
            merged = forward.drop(columns=[c for c in feature_cols if c in forward.columns and c != "event_key"], errors="ignore").merge(
                enriched[feature_cols],
                on="event_key",
                how="left",
            )
            merged.to_parquet(forward_path, index=False)

    coverage = json.loads((feature_dir / "coverage_report.json").read_text()) if (feature_dir / "coverage_report.json").exists() else {}
    coverage.setdefault("raw_rows", {})
    for endpoint, df in frames.items():
        coverage["raw_rows"][endpoint] = int(len(df))
    feature_cols = [c for c in enriched.columns if c.startswith("mark_1m_") or c.startswith("premium_1m_") or c == "mark_minus_index_proxy_pct"]
    coverage.setdefault("feature_non_null_counts", {})
    coverage.setdefault("feature_coverage_pct", {})
    for col in feature_cols:
        coverage["feature_non_null_counts"][col] = int(enriched[col].notna().sum())
        coverage["feature_coverage_pct"][col] = round(float(enriched[col].notna().mean() * 100.0), 4)
    (feature_dir / "coverage_report.json").write_text(json.dumps(coverage, ensure_ascii=False, indent=2), encoding="utf-8")

    report = feature_dir / "coverage_report.md"
    with report.open("a", encoding="utf-8") as f:
        f.write("\n\n## Mark/Premium kline coverage\n")
        for col in feature_cols:
            f.write(f"- {col}: {coverage['feature_coverage_pct'][col]}%\n")
    print(json.dumps({"feature_dir": str(feature_dir), "events": len(enriched), "mark_rows": len(frames["mark_price_1m"]), "premium_rows": len(frames["premium_index_1m"])}, ensure_ascii=False), flush=True)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Collect mark-price and premium-index event-time features")
    p.add_argument("--feature-dir", default=str(DEFAULT_FEATURE_DIR))
    p.add_argument("--max-workers", type=int, default=6)
    p.add_argument("--max-rps", type=float, default=4.0)
    return p


if __name__ == "__main__":
    run(build_parser().parse_args())
