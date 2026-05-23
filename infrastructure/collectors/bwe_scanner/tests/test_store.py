import json

from store import append_alert


def test_append_alert_writes_daily_file(tmp_path):
    alert = {"ts_ms": 1_700_000_000_000, "symbol": "ABCUSDT", "window_type": "price_60s",
             "price_chg_pct": 6.2, "fired_at": "2023-11-14T22:13:20Z"}
    path = append_alert(str(tmp_path), alert, now_ms=1_700_000_000_000)
    assert path.exists()
    assert "alerts_2023-11-14.jsonl" in path.name
    line = json.loads(path.read_text().strip())
    assert line["symbol"] == "ABCUSDT"


def test_append_alert_appends_multiple_lines(tmp_path):
    for i in range(3):
        append_alert(str(tmp_path), {"symbol": f"S{i}USDT"}, now_ms=1_700_000_000_000)
    f = list(tmp_path.glob("alerts_*.jsonl"))[0]
    assert len(f.read_text().strip().splitlines()) == 3


def test_emitted_line_is_parseable_by_live_bot_loader(tmp_path):
    alert = {"ts_ms": 1_700_000_000_000, "symbol": "ABCUSDT", "window_type": "price_60s"}
    path = append_alert(str(tmp_path), alert, now_ms=1_700_000_000_000)
    d = json.loads(path.read_text().strip())
    assert d.get("symbol", "").endswith("USDT") and int(d.get("ts_ms", 0)) > 0
