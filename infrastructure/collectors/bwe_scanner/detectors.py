from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone


def pct_change_over_window(
    samples: list[tuple[int, float]], now_ms: int, window_sec: int
) -> float | None:
    """Percent change of the latest price vs the price at/just before (now - window).

    `samples` is ascending by ts_ms: [(ts_ms, price), ...]. Returns None if there is
    no sample old enough to anchor the window (insufficient history) or no samples.
    """
    if not samples:
        return None
    cutoff = now_ms - window_sec * 1000
    past_price = None
    for ts, price in samples:
        if ts <= cutoff:
            past_price = price
        else:
            break
    if past_price is None or past_price == 0:
        return None
    now_price = samples[-1][1]
    # Guard glitchy external feed values (NaN → silent false-suppress; Inf → false-fire).
    if not math.isfinite(past_price) or not math.isfinite(now_price):
        return None
    return (now_price / past_price - 1.0) * 100.0


@dataclass(frozen=True)
class Detection:
    ts_ms: int
    symbol: str
    window_type: str
    window_sec: int
    price_chg_pct: float
    price: float
    oi_chg_pct: float | None = None
    oi_usd: float | None = None


def detect_price_ladder(
    symbol: str,
    samples: list[tuple[int, float]],
    now_ms: int,
    windows: dict[str, dict],
) -> list[Detection]:
    """Fire a Detection for each price window whose |Δ%| >= its threshold."""
    out: list[Detection] = []
    if not samples:
        return out
    price_now = samples[-1][1]
    for wtype, cfg in windows.items():
        chg = pct_change_over_window(samples, now_ms, cfg["sec"])
        if chg is None:
            continue
        if abs(chg) >= cfg["thr_pct"]:
            out.append(Detection(ts_ms=now_ms, symbol=symbol, window_type=wtype,
                                 window_sec=cfg["sec"], price_chg_pct=round(chg, 4),
                                 price=price_now))
    return out


def apply_cooldown(
    detections: list[Detection],
    last_fired: dict[tuple[str, str], int],
    cooldown_sec: int,
    now_ms: int,
) -> list[Detection]:
    """Drop detections whose (symbol, window_type) fired within cooldown. Mutates
    last_fired for kept detections."""
    kept: list[Detection] = []
    for d in detections:
        key = (d.symbol, d.window_type)
        prev = last_fired.get(key)
        if prev is not None and (now_ms - prev) < cooldown_sec * 1000:
            continue
        last_fired[key] = now_ms
        kept.append(d)
    return kept


def detect_oi_price_1h(
    symbol: str,
    price_samples: list[tuple[int, float]],
    oi_chg_pct: float | None,
    oi_usd: float | None,
    now_ms: int,
    price_thr: float,
    oi_thr: float,
) -> Detection | None:
    """Fire if |1h price Δ| >= price_thr OR |1h OI Δ| >= oi_thr."""
    price_chg = pct_change_over_window(price_samples, now_ms, 3600)
    price_hit = price_chg is not None and abs(price_chg) >= price_thr
    oi_hit = oi_chg_pct is not None and math.isfinite(oi_chg_pct) and abs(oi_chg_pct) >= oi_thr
    if not (price_hit or oi_hit):
        return None
    return Detection(
        ts_ms=now_ms, symbol=symbol, window_type="oi_price_1h", window_sec=3600,
        price_chg_pct=round(price_chg, 4) if price_chg is not None else 0.0,
        price=price_samples[-1][1] if price_samples else 0.0,
        oi_chg_pct=round(oi_chg_pct, 4) if oi_chg_pct is not None else None,
        oi_usd=oi_usd,
    )


@dataclass(frozen=True)
class Alert:
    ts_ms: int
    symbol: str
    window_type: str
    window_sec: int
    price_chg_pct: float
    oi_chg_pct: float | None
    price: float
    chg_24h_pct: float | None
    quote_vol_24h: float | None
    oi_usd: float | None
    market_cap_usd: float | None
    oi_mc_ratio_pct: float | None
    fired_at: str


def to_alert(det: Detection, ctx: dict, market_cap_usd: float | None) -> Alert:
    """Combine a Detection with 24h context + market cap into a storable Alert."""
    oi_mc = None
    if market_cap_usd and det.oi_usd is not None:
        oi_mc = det.oi_usd / market_cap_usd * 100.0
    return Alert(
        ts_ms=det.ts_ms, symbol=det.symbol, window_type=det.window_type,
        window_sec=det.window_sec, price_chg_pct=det.price_chg_pct,
        oi_chg_pct=det.oi_chg_pct, price=det.price,
        chg_24h_pct=ctx.get("chg_24h_pct"), quote_vol_24h=ctx.get("quote_vol_24h"),
        oi_usd=det.oi_usd, market_cap_usd=market_cap_usd, oi_mc_ratio_pct=oi_mc,
        fired_at=datetime.fromtimestamp(det.ts_ms / 1000, timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def alert_to_dict(alert: Alert) -> dict:
    return asdict(alert)
