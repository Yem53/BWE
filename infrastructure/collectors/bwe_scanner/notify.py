from __future__ import annotations

import requests

_LABEL = {"price_3s": "3s", "price_5s": "5s", "price_10s": "10s", "price_30s": "30s",
          "price_60s": "60s", "price_90s": "90s", "price_180s_extreme": "180s",
          "oi_price_1h": "1h OI"}


def should_push(alert: dict, push_filter: dict) -> bool:
    """High-signal subset: always-push types, plus short windows only when |Δ| is big."""
    wtype = alert.get("window_type", "")
    if wtype in push_filter.get("types", []):
        return True
    if wtype in push_filter.get("short_window_types", []):
        return abs(alert.get("price_chg_pct", 0.0)) >= push_filter.get("short_window_min_pct", 1e9)
    return False


def format_alert_msg(alert: dict) -> str:
    sym = alert.get("symbol", "?")
    win = _LABEL.get(alert.get("window_type", ""), alert.get("window_type", ""))
    chg = alert.get("price_chg_pct", 0.0)
    arrow = "🟢" if chg >= 0 else "🔻"
    parts = [f"{arrow} {sym} {chg:+.1f}% / {win}"]
    if alert.get("chg_24h_pct") is not None:
        parts.append(f"24h {alert['chg_24h_pct']:+.0f}%")
    if alert.get("oi_chg_pct") is not None:
        parts.append(f"OI {alert['oi_chg_pct']:+.0f}%")
    if alert.get("oi_mc_ratio_pct") is not None:
        parts.append(f"OI/MC {alert['oi_mc_ratio_pct']:.1f}%")
    if alert.get("quote_vol_24h"):
        parts.append(f"vol ${alert['quote_vol_24h']/1e6:.1f}M")
    return " · ".join(parts)


def send_telegram(token: str, chat_id: str, text: str) -> bool:
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        r = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=10)
        return r.status_code == 200
    except Exception:
        return False
