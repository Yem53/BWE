from __future__ import annotations

import json
import time
from pathlib import Path

import requests


class Ticker24hCache:
    """Snapshot of /fapi/v1/ticker/24hr keyed by USDT-perp symbol."""

    def __init__(self, fapi_base: str):
        self._base = fapi_base
        self._data: dict[str, dict] = {}

    def refresh(self) -> None:
        r = requests.get(f"{self._base}/fapi/v1/ticker/24hr", timeout=15)
        rows = r.json()
        data = {}
        for x in rows:
            sym = x.get("symbol", "")
            if not sym.endswith("USDT"):
                continue
            data[sym] = {
                "chg_24h_pct": float(x.get("priceChangePercent", 0.0)),
                "quote_vol_24h": float(x.get("quoteVolume", 0.0)),
                "last_price": float(x.get("lastPrice", 0.0)),
            }
        self._data = data

    def get(self, symbol: str) -> dict | None:
        return self._data.get(symbol)


class MarketCapCache:
    """Market cap = cached CoinGecko circulating supply × live price (BWE parity).

    Supply changes slowly → refresh daily. cg_map: {binance_symbol: coingecko_id}.
    Unmapped symbol or missing supply → market_cap returns None (logged by caller).
    """

    def __init__(self, cg_map: dict[str, str]):
        self._cg_map = cg_map
        self._supply: dict[str, float] = {}
        self._last_refresh = 0.0

    @classmethod
    def from_file(cls, path: str) -> "MarketCapCache":
        p = Path(path)
        cg_map = json.loads(p.read_text()) if p.exists() else {}
        return cls(cg_map)

    def market_cap(self, symbol: str, price: float) -> float | None:
        cg_id = self._cg_map.get(symbol)
        if not cg_id:
            return None
        supply = self._supply.get(cg_id)
        if not supply:
            return None
        return supply * price

    def refresh_supply(self, ids: list[str] | None = None) -> None:
        """Fetch circulating supply for mapped ids from CoinGecko (paged, free API)."""
        ids = ids if ids is not None else list(set(self._cg_map.values()))
        out: dict[str, float] = {}
        for i in range(0, len(ids), 100):
            chunk = ids[i:i + 100]
            try:
                r = requests.get(
                    "https://api.coingecko.com/api/v3/coins/markets",
                    params={"vs_currency": "usd", "ids": ",".join(chunk), "per_page": 100},
                    timeout=20,
                )
                for row in r.json():
                    cs = row.get("circulating_supply")
                    if cs:
                        out[row["id"]] = float(cs)
            except Exception:
                continue
            time.sleep(2.5)
        if out:
            self._supply.update(out)
            self._last_refresh = time.time()
