from scanner import run_detection_tick


def test_run_detection_tick_emits_enriched_alerts():
    samples = {"ABCUSDT": [(0, 100.0), (60_000, 100.0), (120_000, 112.0)]}
    cfg = {"windows": {"price_60s": {"sec": 60, "thr_pct": 5.0}},
           "oi_price_1h": {"sec": 3600, "price_thr_pct": 5.0, "oi_thr_pct": 5.0},
           "store_cooldown_sec": 600}
    ctx = {"ABCUSDT": {"chg_24h_pct": 15.0, "quote_vol_24h": 1e6}}
    oi = {"ABCUSDT": (None, None)}
    last_fired = {}
    alerts = run_detection_tick(cfg, samples, ctx, oi, mc=None,
                                now_ms=120_000, last_fired=last_fired)
    assert len(alerts) == 1
    a = alerts[0]
    assert a["symbol"] == "ABCUSDT" and a["window_type"] == "price_60s"
    assert a["chg_24h_pct"] == 15.0
    assert run_detection_tick(cfg, samples, ctx, oi, mc=None,
                              now_ms=120_500, last_fired=last_fired) == []
