import json

from detectors import (
    Alert,
    Detection,
    alert_to_dict,
    apply_cooldown,
    detect_oi_price_1h,
    detect_price_ladder,
    pct_change_over_window,
    to_alert,
)


def test_pct_change_basic_rise():
    samples = [(4000, 100.0), (7000, 100.0), (8000, 105.0), (10000, 110.0)]
    assert pct_change_over_window(samples, now_ms=10000, window_sec=3) == 10.0


def test_pct_change_negative():
    samples = [(0, 200.0), (5000, 180.0)]
    assert pct_change_over_window(samples, now_ms=5000, window_sec=5) == -10.0


def test_pct_change_insufficient_history_returns_none():
    samples = [(9000, 100.0), (10000, 101.0)]
    assert pct_change_over_window(samples, now_ms=10000, window_sec=3) is None


def test_pct_change_empty_returns_none():
    assert pct_change_over_window([], now_ms=10000, window_sec=3) is None


def test_detect_price_ladder_fires_windows_over_threshold():
    samples = [(0, 100.0), (60_000, 100.0), (120_000, 100.0), (180_000, 112.0)]
    windows = {"price_60s": {"sec": 60, "thr_pct": 5.0},
               "price_180s_extreme": {"sec": 180, "thr_pct": 8.0}}
    dets = detect_price_ladder("ABCUSDT", samples, now_ms=180_000, windows=windows)
    by_type = {d.window_type: d for d in dets}
    assert set(by_type) == {"price_60s", "price_180s_extreme"}
    assert by_type["price_60s"].price_chg_pct == 12.0
    assert by_type["price_60s"].price == 112.0
    assert by_type["price_60s"].symbol == "ABCUSDT"
    assert by_type["price_180s_extreme"].window_sec == 180


def test_detect_price_ladder_below_threshold_no_fire():
    samples = [(0, 100.0), (180_000, 103.0)]
    windows = {"price_180s_extreme": {"sec": 180, "thr_pct": 8.0}}
    assert detect_price_ladder("ABCUSDT", samples, now_ms=180_000, windows=windows) == []


def _det(sym, wtype, ts):
    return Detection(ts_ms=ts, symbol=sym, window_type=wtype, window_sec=60,
                     price_chg_pct=6.0, price=1.0)


def test_apply_cooldown_first_fire_passes_and_records():
    last_fired = {}
    dets = [_det("A", "price_60s", 1000)]
    kept = apply_cooldown(dets, last_fired, cooldown_sec=600, now_ms=1000)
    assert len(kept) == 1
    assert last_fired[("A", "price_60s")] == 1000


def test_apply_cooldown_suppresses_within_window():
    last_fired = {("A", "price_60s"): 1000}
    dets = [_det("A", "price_60s", 300_000)]
    kept = apply_cooldown(dets, last_fired, cooldown_sec=600, now_ms=300_000)
    assert kept == []
    assert last_fired[("A", "price_60s")] == 1000


def test_apply_cooldown_passes_after_window():
    last_fired = {("A", "price_60s"): 1000}
    dets = [_det("A", "price_60s", 601_001)]
    kept = apply_cooldown(dets, last_fired, cooldown_sec=600, now_ms=601_001)
    assert len(kept) == 1
    assert last_fired[("A", "price_60s")] == 601_001


def test_oi_price_1h_fires_on_price_only():
    samples = [(0, 100.0), (3_600_000, 106.0)]
    d = detect_oi_price_1h("ABCUSDT", samples, oi_chg_pct=1.0, oi_usd=5e6,
                           now_ms=3_600_000, price_thr=5.0, oi_thr=5.0)
    assert d is not None
    assert d.window_type == "oi_price_1h"
    assert d.price_chg_pct == 6.0
    assert d.oi_chg_pct == 1.0
    assert d.oi_usd == 5e6


def test_oi_price_1h_fires_on_oi_only():
    samples = [(0, 100.0), (3_600_000, 101.0)]
    d = detect_oi_price_1h("ABCUSDT", samples, oi_chg_pct=12.0, oi_usd=5e6,
                           now_ms=3_600_000, price_thr=5.0, oi_thr=5.0)
    assert d is not None and d.oi_chg_pct == 12.0


def test_oi_price_1h_no_fire_when_both_below():
    samples = [(0, 100.0), (3_600_000, 102.0)]
    d = detect_oi_price_1h("ABCUSDT", samples, oi_chg_pct=2.0, oi_usd=5e6,
                           now_ms=3_600_000, price_thr=5.0, oi_thr=5.0)
    assert d is None


def test_oi_price_1h_handles_missing_oi():
    samples = [(0, 100.0), (3_600_000, 107.0)]
    d = detect_oi_price_1h("ABCUSDT", samples, oi_chg_pct=None, oi_usd=None,
                           now_ms=3_600_000, price_thr=5.0, oi_thr=5.0)
    assert d is not None and d.oi_chg_pct is None


def test_to_alert_merges_context_and_marketcap():
    det = Detection(ts_ms=1_700_000_000_000, symbol="ABCUSDT", window_type="price_60s",
                    window_sec=60, price_chg_pct=6.2, price=0.5, oi_usd=4.9e6)
    ctx = {"chg_24h_pct": 15.0, "quote_vol_24h": 1_234_567.0}
    a = to_alert(det, ctx, market_cap_usd=8_000_000.0)
    assert isinstance(a, Alert)
    assert a.symbol == "ABCUSDT"
    assert a.chg_24h_pct == 15.0
    assert a.market_cap_usd == 8_000_000.0
    assert round(a.oi_mc_ratio_pct, 1) == round(4.9e6 / 8e6 * 100, 1)
    assert a.fired_at.endswith("Z")


def test_to_alert_null_marketcap_keeps_ratio_none():
    det = Detection(ts_ms=1_700_000_000_000, symbol="ABCUSDT", window_type="price_3s",
                    window_sec=3, price_chg_pct=2.5, price=0.5)
    a = to_alert(det, {"chg_24h_pct": None, "quote_vol_24h": None}, market_cap_usd=None)
    assert a.market_cap_usd is None and a.oi_mc_ratio_pct is None


def test_alert_to_dict_is_json_round_trippable():
    det = Detection(ts_ms=1, symbol="ABCUSDT", window_type="price_3s", window_sec=3,
                    price_chg_pct=2.5, price=0.5)
    a = to_alert(det, {"chg_24h_pct": None, "quote_vol_24h": None}, market_cap_usd=None)
    d = alert_to_dict(a)
    assert json.loads(json.dumps(d))["symbol"] == "ABCUSDT"
    assert set(d) >= {"ts_ms", "symbol", "window_type", "price_chg_pct", "fired_at"}
