from ws_feed import (
    parse_markprice_array,
    PriceBuffers,
    oi_chg_from_hist,
    parse_ticker_price_array,
)


def test_parse_markprice_array_extracts_symbol_price_ts():
    msg = ('[{"e":"markPriceUpdate","E":1700000000000,"s":"ABCUSDT","p":"0.5000"},'
           '{"e":"markPriceUpdate","E":1700000000000,"s":"XYZUSDT","p":"2.0"},'
           '{"e":"markPriceUpdate","E":1700000000000,"s":"BTCUSDC","p":"60000"}]')
    rows = parse_markprice_array(msg)
    syms = {r[0] for r in rows}
    assert syms == {"ABCUSDT", "XYZUSDT"}
    abc = [r for r in rows if r[0] == "ABCUSDT"][0]
    assert abc == ("ABCUSDT", 1700000000000, 0.5)


def test_parse_markprice_ignores_malformed():
    assert parse_markprice_array("not json") == []
    assert parse_markprice_array('{"not":"array"}') == []


def test_pricebuffers_add_and_window_samples():
    pb = PriceBuffers(short_max_sec=200, long_step_sec=10, long_max_sec=3600)
    for ts in range(0, 5000, 1000):
        pb.add("ABCUSDT", ts, 100.0 + ts / 1000)
    s = pb.samples("ABCUSDT")
    assert s[0][0] == 0 and s[-1][1] == 104.0
    assert all(s[i][0] <= s[i + 1][0] for i in range(len(s) - 1))


def test_pricebuffers_evicts_old_short_samples():
    pb = PriceBuffers(short_max_sec=10, long_step_sec=10, long_max_sec=3600)
    pb.add("ABCUSDT", 0, 100.0)
    pb.add("ABCUSDT", 20_000, 110.0)
    short = pb.short_samples("ABCUSDT")
    assert short[0][0] == 20_000


def test_oi_chg_from_hist_computes_1h_change_and_usd():
    rows = [{"sumOpenInterest": "1000", "sumOpenInterestValue": "5000000"},
            {"sumOpenInterest": "1100", "sumOpenInterestValue": "5500000"},
            {"sumOpenInterest": "1200", "sumOpenInterestValue": "6000000"}]
    chg_pct, oi_usd = oi_chg_from_hist(rows)
    assert round(chg_pct, 1) == 20.0
    assert oi_usd == 6_000_000.0


def test_oi_chg_from_hist_empty_returns_none():
    assert oi_chg_from_hist([]) == (None, None)
    assert oi_chg_from_hist([{"sumOpenInterest": "0", "sumOpenInterestValue": "0"}]) == (None, None)


def test_parse_ticker_price_array_usdt_perps_only():
    rows = [{"symbol": "ABCUSDT", "price": "0.5", "time": 1700000000000},
            {"symbol": "XYZUSDT", "price": "2.0", "time": 1700000000000},
            {"symbol": "BTCUSDC", "price": "60000", "time": 1700000000000}]
    out = parse_ticker_price_array(rows, now_ms=1700000000000)
    assert {r[0] for r in out} == {"ABCUSDT", "XYZUSDT"}
    abc = [r for r in out if r[0] == "ABCUSDT"][0]
    assert abc == ("ABCUSDT", 1700000000000, 0.5)


def test_parse_ticker_price_array_falls_back_to_now_ms():
    out = parse_ticker_price_array([{"symbol": "ABCUSDT", "price": "0.5"}], now_ms=999)
    assert out == [("ABCUSDT", 999, 0.5)]
