"""Daily snapshot collector — exchangeInfo / leverageBracket / insuranceFund.

Runs once per day (cron 04:00 UTC). Saves JSON snapshots to T9.

NOTE: leverageBracket is PUBLIC for futures (no auth needed in our usage).
NOTE: insuranceFund — Binance doesn't have a clean public REST endpoint;
      we attempt /fapi/v1/insuranceBalance (may not exist), fall back gracefully.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

LOG = logging.getLogger("daily_snapshot")

BASE_URL = "https://fapi.binance.com"
DEFAULT_OUT = "/Volumes/T9/binance data/snapshots"


def fetch_endpoint(session: requests.Session, path: str,
                   params: dict | None = None) -> dict | None:
    try:
        r = session.get(BASE_URL + path, params=params, timeout=20)
        if r.status_code == 200:
            return r.json()
        LOG.warning("HTTP %d for %s", r.status_code, path)
        return None
    except Exception as e:
        LOG.warning("fetch %s: %s", path, e)
        return None


def save_snapshot(out_dir: Path, name: str, data: dict | list) -> Path:
    today = datetime.now(timezone.utc).strftime("%Y_%m_%d")
    path = out_dir / f"{name}_{today}.json"
    path.write_text(json.dumps(data, indent=2, default=str))
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", default=DEFAULT_OUT)
    ap.add_argument("--snapshots", default="exchangeInfo,leverageBracket,insuranceBalance",
                    help="comma list of snapshots to fetch")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(name)s] %(levelname)s %(message)s")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update({"User-Agent": "bwe-daily-snapshot/1.0"})

    snapshots = args.snapshots.split(",")
    results = {}

    if "exchangeInfo" in snapshots:
        LOG.info("fetching exchangeInfo...")
        d = fetch_endpoint(session, "/fapi/v1/exchangeInfo")
        if d:
            p = save_snapshot(out_dir, "exchangeInfo", d)
            n_syms = len(d.get("symbols", []))
            results["exchangeInfo"] = {"path": str(p), "n_symbols": n_syms}
            LOG.info("  %d symbols saved → %s", n_syms, p)

    if "leverageBracket" in snapshots:
        LOG.info("fetching leverageBracket (per-symbol public)...")
        # Public endpoint — passes pair=ALL doesn't work, must iterate
        # Alternative: /fapi/v1/leverageBracket without symbol param returns all
        d = fetch_endpoint(session, "/fapi/v1/leverageBracket")
        if d:
            p = save_snapshot(out_dir, "leverageBracket", d)
            n_syms = len(d) if isinstance(d, list) else 0
            results["leverageBracket"] = {"path": str(p), "n_symbols": n_syms}
            LOG.info("  %d symbols saved → %s", n_syms, p)

    if "insuranceBalance" in snapshots:
        LOG.info("trying insuranceBalance (uncertain endpoint)...")
        # No standard public endpoint; record attempt
        d = fetch_endpoint(session, "/fapi/v1/insuranceBalance")
        if d:
            p = save_snapshot(out_dir, "insuranceBalance", d)
            results["insuranceBalance"] = {"path": str(p)}
        else:
            results["insuranceBalance"] = {"error": "endpoint not available; skip"}
            LOG.info("  insuranceBalance not publicly available; skipping")

    LOG.info("daily snapshot done: %s", results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
