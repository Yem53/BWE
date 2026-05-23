from unittest.mock import patch

from enrich import Ticker24hCache, MarketCapCache

FAKE_24H = [
    {"symbol": "ABCUSDT", "priceChangePercent": "15.0", "quoteVolume": "1234567", "lastPrice": "0.5"},
    {"symbol": "XYZUSDT", "priceChangePercent": "-3.2", "quoteVolume": "999", "lastPrice": "2.0"},
    {"symbol": "BTCUSDC", "priceChangePercent": "1.0", "quoteVolume": "5", "lastPrice": "60000"},
]


def test_ticker24h_refresh_and_get():
    c = Ticker24hCache("https://fapi.binance.com")
    with patch("enrich.requests.get") as g:
        g.return_value.json.return_value = FAKE_24H
        g.return_value.status_code = 200
        c.refresh()
    ctx = c.get("ABCUSDT")
    assert ctx["chg_24h_pct"] == 15.0
    assert ctx["quote_vol_24h"] == 1234567.0
    assert c.get("XYZUSDT")["chg_24h_pct"] == -3.2
    assert c.get("BTCUSDC") is None


def test_ticker24h_get_unknown_returns_none():
    c = Ticker24hCache("https://fapi.binance.com")
    assert c.get("NOPEUSDT") is None


def test_marketcap_from_cached_supply_times_price():
    c = MarketCapCache(cg_map={"ABCUSDT": "abc-coin"})
    c._supply = {"abc-coin": 16_000_000.0}
    assert c.market_cap("ABCUSDT", price=0.5) == 8_000_000.0


def test_marketcap_unmapped_symbol_returns_none():
    c = MarketCapCache(cg_map={})
    assert c.market_cap("NOPEUSDT", price=1.0) is None


def test_marketcap_mapped_but_no_supply_returns_none():
    c = MarketCapCache(cg_map={"ABCUSDT": "abc-coin"})
    assert c.market_cap("ABCUSDT", price=1.0) is None
