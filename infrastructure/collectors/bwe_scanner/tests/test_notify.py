from unittest.mock import patch

from notify import should_push, format_alert_msg, send_telegram

FILTER = {"types": ["price_180s_extreme", "oi_price_1h"],
          "min_pct_by_type": {"oi_price_1h": 10.0},
          "short_window_types": ["price_60s", "price_90s"], "short_window_min_pct": 8.0}


def test_push_extreme_180s_always():
    # extreme pumps have no extra magnitude gate (detection already requires >=8%)
    assert should_push({"window_type": "price_180s_extreme", "price_chg_pct": 8.1}, FILTER)


def test_push_oi_price_1h_only_when_big():
    # archived at 5% but NOT pushed unless max(|price|,|oi|) >= 10
    assert not should_push({"window_type": "oi_price_1h", "price_chg_pct": 6.0, "oi_chg_pct": 3.0}, FILTER)
    assert should_push({"window_type": "oi_price_1h", "price_chg_pct": -12.0, "oi_chg_pct": 1.0}, FILTER)
    assert should_push({"window_type": "oi_price_1h", "price_chg_pct": 2.0, "oi_chg_pct": 15.0}, FILTER)
    assert should_push({"window_type": "oi_price_1h", "price_chg_pct": 11.0, "oi_chg_pct": None}, FILTER)


def test_push_short_window_only_if_big():
    assert should_push({"window_type": "price_60s", "price_chg_pct": 9.0}, FILTER)
    assert should_push({"window_type": "price_60s", "price_chg_pct": -8.5}, FILTER)
    assert not should_push({"window_type": "price_60s", "price_chg_pct": 6.0}, FILTER)


def test_no_push_for_micro_windows():
    assert not should_push({"window_type": "price_3s", "price_chg_pct": 4.0}, FILTER)


def test_format_alert_msg_contains_key_fields():
    msg = format_alert_msg({"symbol": "ABCUSDT", "window_type": "price_180s_extreme",
                            "window_sec": 180, "price_chg_pct": 8.4, "chg_24h_pct": 15.0,
                            "quote_vol_24h": 1_200_000.0, "oi_mc_ratio_pct": None})
    assert "ABCUSDT" in msg and "8.4" in msg and "180" in msg


def test_send_telegram_posts_and_returns_true_on_200():
    class Resp:
        status_code = 200
    with patch("notify.requests.post", return_value=Resp()) as p:
        ok = send_telegram("tok", "chat123", "hello")
    assert ok is True
    assert "tok" in p.call_args[0][0]


def test_send_telegram_returns_false_on_error():
    with patch("notify.requests.post", side_effect=Exception("net")):
        assert send_telegram("tok", "chat123", "hello") is False
