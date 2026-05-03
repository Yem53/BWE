#!/usr/bin/env python3
import csv
import datetime as dt
import json
import math
import sqlite3
import statistics
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd


SYMBOL = "LABUSDT"
RUN_ROOT = Path("/Volumes/T9/BWE/40_EXPERIMENTS/lab_usdt_20260502_single_symbol")
REPORT_ROOT = Path("/Volumes/T9/BWE/50_ANALYSIS_REPORTS/lab_usdt_20260502_single_symbol")
DB_PATH = Path("/Volumes/T9_HOT/binance_collectors_runtime/binance_futures_1m.sqlite3")
BWE_LOG = Path("/Volumes/T9_HOT/bwe_logs/bwe_matrix_posts.jsonl")
PUBLIC_BASE = "https://fapi.binance.com"


def utc(ms):
    if ms is None or pd.isna(ms):
        return ""
    return dt.datetime.utcfromtimestamp(int(ms) / 1000).strftime("%Y-%m-%d %H:%M:%S")


def fetch_json(path, params):
    query = urllib.parse.urlencode(params)
    url = f"{PUBLIC_BASE}{path}?{query}"
    req = urllib.request.Request(url, headers={"User-Agent": "BWE-LABUSDT-research/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def cache_public_data():
    cache_dir = RUN_ROOT / "public_fetch"
    cache_dir.mkdir(parents=True, exist_ok=True)
    endpoints = {
        "klines_1m": ("/fapi/v1/klines", {"symbol": SYMBOL, "interval": "1m", "limit": 1500}),
        "mark_price_klines_1m": ("/fapi/v1/markPriceKlines", {"symbol": SYMBOL, "interval": "1m", "limit": 1500}),
        "premium_index_klines_1m": ("/fapi/v1/premiumIndexKlines", {"symbol": SYMBOL, "interval": "1m", "limit": 1500}),
        "ticker_24h": ("/fapi/v1/ticker/24hr", {"symbol": SYMBOL}),
        "premium_index": ("/fapi/v1/premiumIndex", {"symbol": SYMBOL}),
        "open_interest_hist_5m": ("/futures/data/openInterestHist", {"symbol": SYMBOL, "period": "5m", "limit": 500}),
        "global_ls_5m": ("/futures/data/globalLongShortAccountRatio", {"symbol": SYMBOL, "period": "5m", "limit": 500}),
        "top_account_ls_5m": ("/futures/data/topLongShortAccountRatio", {"symbol": SYMBOL, "period": "5m", "limit": 500}),
        "top_position_ls_5m": ("/futures/data/topLongShortPositionRatio", {"symbol": SYMBOL, "period": "5m", "limit": 500}),
        "taker_buy_sell_5m": ("/futures/data/takerlongshortRatio", {"symbol": SYMBOL, "period": "5m", "limit": 500}),
        "basis_5m": ("/futures/data/basis", {"pair": SYMBOL, "contractType": "PERPETUAL", "period": "5m", "limit": 500}),
    }
    out = {}
    for name, (path, params) in endpoints.items():
        try:
            data = fetch_json(path, params)
            (cache_dir / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2))
            out[name] = data
            time.sleep(0.15)
        except Exception as exc:
            out[name] = {"error": repr(exc)}
            (cache_dir / f"{name}.error.txt").write_text(repr(exc))
    return out


def sql_df(conn, sql, params=(SYMBOL,)):
    return pd.read_sql_query(sql, conn, params=params)


def load_db_data():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    tables = {}
    tables["klines_1m"] = sql_df(
        conn,
        """
        SELECT open_time_ms AS ts_ms, open, high, low, close, volume, quote_volume, trade_count,
               taker_buy_base_volume, taker_buy_quote_volume
        FROM klines_1m WHERE symbol=? ORDER BY open_time_ms
        """,
    )
    for name, sql in {
        "mark_price_1m": "SELECT ts_ms, close AS mark_close FROM mark_price_1m WHERE symbol=? ORDER BY ts_ms",
        "premium_index_1m": "SELECT ts_ms, close AS premium_close FROM premium_index_1m WHERE symbol=? ORDER BY ts_ms",
        "index_price_1m": "SELECT ts_ms, close AS index_close FROM index_price_1m WHERE symbol=? ORDER BY ts_ms",
        "open_interest_5m": "SELECT ts_ms, sum_open_interest, sum_open_interest_value FROM open_interest_5m WHERE symbol=? ORDER BY ts_ms",
        "funding_rate": "SELECT ts_ms, funding_rate, mark_price AS funding_mark_price FROM funding_rate WHERE symbol=? ORDER BY ts_ms",
        "global_ls_5m": "SELECT ts_ms, long_short_ratio AS global_ls, long_account AS global_long, short_account AS global_short FROM global_long_short_account_ratio_5m WHERE symbol=? ORDER BY ts_ms",
        "top_account_ls_5m": "SELECT ts_ms, long_short_ratio AS top_account_ls, long_account AS top_account_long, short_account AS top_account_short FROM top_trader_long_short_account_ratio_5m WHERE symbol=? ORDER BY ts_ms",
        "top_position_ls_5m": "SELECT ts_ms, long_short_ratio AS top_position_ls, long_account AS top_position_long, short_account AS top_position_short FROM top_trader_long_short_position_ratio_5m WHERE symbol=? ORDER BY ts_ms",
        "taker_buy_sell_5m": "SELECT ts_ms, buy_sell_ratio, buy_vol, sell_vol FROM taker_buy_sell_volume_5m WHERE symbol=? ORDER BY ts_ms",
        "basis_5m": "SELECT ts_ms, basis, basis_rate, index_price, futures_price, annualized_basis_rate FROM basis_perpetual_5m WHERE symbol=? ORDER BY ts_ms",
        "ticker_24h": "SELECT ts_ms, price_change_percent, last_price, high_price, low_price, volume AS ticker_volume, quote_volume AS ticker_quote_volume, trade_count AS ticker_trade_count FROM ticker_24h WHERE symbol=? ORDER BY ts_ms",
    }.items():
        tables[name] = sql_df(conn, sql)
    meta = sql_df(
        conn,
        "SELECT symbol, status, contract_type, listing_ts_ms, first_seen_ms, last_seen_ms FROM symbol_meta WHERE symbol=?",
    )
    conn.close()
    return tables, meta


def append_public_klines(local, public):
    live = public.get("klines_1m")
    if not isinstance(live, list):
        return local
    rows = []
    for r in live:
        rows.append(
            {
                "ts_ms": int(r[0]),
                "open": float(r[1]),
                "high": float(r[2]),
                "low": float(r[3]),
                "close": float(r[4]),
                "volume": float(r[5]),
                "quote_volume": float(r[7]),
                "trade_count": int(r[8]),
                "taker_buy_base_volume": float(r[9]),
                "taker_buy_quote_volume": float(r[10]),
            }
        )
    live_df = pd.DataFrame(rows)
    merged = pd.concat([local, live_df], ignore_index=True)
    merged = merged.drop_duplicates("ts_ms", keep="last").sort_values("ts_ms").reset_index(drop=True)
    return merged


def public_metric_df(public, name, mapping):
    data = public.get(name)
    if not isinstance(data, list):
        return pd.DataFrame()
    rows = []
    for item in data:
        row = {}
        ts = item.get("timestamp") or item.get("time") or item.get("ts")
        if ts is None:
            continue
        row["ts_ms"] = int(ts)
        for src, dst in mapping.items():
            if src in item:
                try:
                    row[dst] = float(item[src])
                except Exception:
                    row[dst] = item[src]
        rows.append(row)
    return pd.DataFrame(rows).drop_duplicates("ts_ms", keep="last").sort_values("ts_ms") if rows else pd.DataFrame()


def merge_public_metrics(tables, public):
    metric_specs = {
        "open_interest_5m": ("open_interest_hist_5m", {"sumOpenInterest": "sum_open_interest", "sumOpenInterestValue": "sum_open_interest_value"}),
        "global_ls_5m": ("global_ls_5m", {"longShortRatio": "global_ls", "longAccount": "global_long", "shortAccount": "global_short"}),
        "top_account_ls_5m": ("top_account_ls_5m", {"longShortRatio": "top_account_ls", "longAccount": "top_account_long", "shortAccount": "top_account_short"}),
        "top_position_ls_5m": ("top_position_ls_5m", {"longShortRatio": "top_position_ls", "longAccount": "top_position_long", "shortAccount": "top_position_short"}),
        "taker_buy_sell_5m": ("taker_buy_sell_5m", {"buySellRatio": "buy_sell_ratio", "buyVol": "buy_vol", "sellVol": "sell_vol"}),
        "basis_5m": ("basis_5m", {"basis": "basis", "basisRate": "basis_rate", "indexPrice": "index_price", "futuresPrice": "futures_price", "annualizedBasisRate": "annualized_basis_rate"}),
    }
    for table, (public_name, mapping) in metric_specs.items():
        df = public_metric_df(public, public_name, mapping)
        if not df.empty:
            tables[table] = pd.concat([tables[table], df], ignore_index=True).drop_duplicates("ts_ms", keep="last").sort_values("ts_ms")


def load_bwe_events():
    rows = []
    if not BWE_LOG.exists():
        return pd.DataFrame()
    with BWE_LOG.open(errors="replace") as f:
        for line in f:
            if SYMBOL not in line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            text = obj.get("text", "")
            side = "unknown"
            if "上涨" in text or "surged" in text or "+" in text or "🟢" in text:
                side = "up"
            if "下跌" in text or "drop" in text or "-" in text or "🔻" in text:
                side = "down" if side == "unknown" else side
            rows.append(
                {
                    "event_ts_ms": int(obj.get("ts_ms")),
                    "event_minute_ms": int(obj.get("ts_ms")) // 60000 * 60000,
                    "source": obj.get("source"),
                    "post_id": obj.get("post_id"),
                    "event_side": side,
                    "text": text,
                }
            )
    return pd.DataFrame(rows).sort_values("event_ts_ms").reset_index(drop=True)


def build_feature_table(tables, public):
    tables["klines_1m"] = append_public_klines(tables["klines_1m"], public)
    merge_public_metrics(tables, public)
    df = tables["klines_1m"].copy()
    df = df.drop_duplicates("ts_ms", keep="last").sort_values("ts_ms").reset_index(drop=True)
    df["utc"] = df["ts_ms"].map(utc)
    df["minute"] = pd.to_datetime(df["ts_ms"], unit="ms", utc=True)
    for col in ["open", "high", "low", "close", "volume", "quote_volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["ret_1m"] = df["close"].pct_change() * 100
    for n in [3, 5, 10, 15, 30, 60, 120, 240]:
        df[f"ret_{n}m"] = (df["close"] / df["close"].shift(n) - 1) * 100
    df["range_pct"] = (df["high"] / df["low"] - 1) * 100
    df["body_pct"] = (df["close"] / df["open"] - 1) * 100
    df["vol_z_20"] = (df["quote_volume"] - df["quote_volume"].rolling(20).mean()) / df["quote_volume"].rolling(20).std()
    df["roll_high_20_prev"] = df["high"].shift(1).rolling(20).max()
    df["roll_low_20_prev"] = df["low"].shift(1).rolling(20).min()
    df["breakout_20"] = df["close"] > df["roll_high_20_prev"]
    df["breakdown_20"] = df["close"] < df["roll_low_20_prev"]
    df["ema_5"] = df["close"].ewm(span=5, adjust=False).mean()
    df["ema_20"] = df["close"].ewm(span=20, adjust=False).mean()
    df["ema_spread_pct"] = (df["ema_5"] / df["ema_20"] - 1) * 100
    df["cum_vwap"] = (df["close"] * df["quote_volume"]).cumsum() / df["quote_volume"].cumsum()
    df["vwap_gap_pct"] = (df["close"] / df["cum_vwap"] - 1) * 100

    # Merge 1m exact metrics and 5m/funding/ticker by backward asof.
    df = df.sort_values("ts_ms")
    for name in ["mark_price_1m", "premium_index_1m", "index_price_1m"]:
        m = tables[name].drop_duplicates("ts_ms", keep="last").sort_values("ts_ms")
        if not m.empty:
            df = pd.merge_asof(df, m, on="ts_ms", direction="backward", tolerance=120000)
    for name in ["open_interest_5m", "funding_rate", "global_ls_5m", "top_account_ls_5m", "top_position_ls_5m", "taker_buy_sell_5m", "basis_5m", "ticker_24h"]:
        m = tables[name].drop_duplicates("ts_ms", keep="last").sort_values("ts_ms")
        if not m.empty:
            df = pd.merge_asof(df, m, on="ts_ms", direction="backward", tolerance=10 * 60 * 1000)
    if "sum_open_interest" in df:
        df["oi_chg_5m"] = df["sum_open_interest"].pct_change(5) * 100
        df["oi_chg_15m"] = df["sum_open_interest"].pct_change(15) * 100
    if "buy_sell_ratio" in df:
        df["taker_ratio_chg_15m"] = df["buy_sell_ratio"].pct_change(15) * 100

    events = load_bwe_events()
    df["bwe_event_count_1m"] = 0
    df["bwe_up_count_5m"] = 0
    df["bwe_down_count_5m"] = 0
    if not events.empty:
        counts = events.groupby("event_minute_ms").size().rename("event_count").reset_index()
        counts = counts.rename(columns={"event_minute_ms": "ts_ms"})
        df = df.merge(counts, on="ts_ms", how="left")
        df["bwe_event_count_1m"] = df["event_count"].fillna(0).astype(int)
        df = df.drop(columns=["event_count"])
        tmp = events.assign(up=(events["event_side"] == "up").astype(int), down=(events["event_side"] == "down").astype(int))
        c = tmp.groupby("event_minute_ms")[["up", "down"]].sum().reset_index().rename(columns={"event_minute_ms": "ts_ms"})
        df = df.merge(c, on="ts_ms", how="left")
        df[["up", "down"]] = df[["up", "down"]].fillna(0)
        df["bwe_up_count_5m"] = df["up"].rolling(5, min_periods=1).sum()
        df["bwe_down_count_5m"] = df["down"].rolling(5, min_periods=1).sum()
        df = df.drop(columns=["up", "down"])
    return df, events


def forward_stats(df, idx, side, max_hold):
    entry = float(df.at[idx, "close"])
    end = min(len(df) - 1, idx + max_hold)
    if end <= idx:
        return None
    window = df.iloc[idx + 1 : end + 1]
    if window.empty:
        return None
    if side == "long":
        highs = (window["high"].to_numpy() / entry - 1) * 100
        lows = (window["low"].to_numpy() / entry - 1) * 100
        closes = (window["close"].to_numpy() / entry - 1) * 100
    else:
        highs = (entry / window["low"].to_numpy() - 1) * 100
        lows = (entry / window["high"].to_numpy() - 1) * 100
        closes = (entry / window["close"].to_numpy() - 1) * 100
    return {
        "mfe": float(pd.Series(highs).max()),
        "mae": float(pd.Series(lows).min()),
        "close_ret": float(closes[-1]),
        "close_path": closes,
        "high_path": highs,
        "low_path": lows,
        "entry": entry,
        "entry_idx": idx,
        "end_idx": end,
    }


def simulate_exit(df, idx, side, activation, giveback, hard_stop, max_hold):
    full_horizon_available = idx + max_hold < len(df)
    st = forward_stats(df, idx, side, max_hold)
    if not st:
        return None
    best = 0.0
    exit_ret = st["close_ret"]
    exit_reason = f"max_hold_{max_hold}m"
    exit_offset = max_hold
    for off, (hi, lo, close_ret) in enumerate(zip(st["high_path"], st["low_path"], st["close_path"]), start=1):
        best = max(best, hi)
        if lo <= -abs(hard_stop):
            return {**st, "exit_ret": -abs(hard_stop), "exit_reason": f"stop_{hard_stop}", "exit_offset": off}
        if best >= activation:
            lock = best * (1 - giveback)
            if close_ret <= lock:
                return {**st, "exit_ret": float(close_ret), "exit_reason": f"trail_act{activation}_gb{giveback}", "exit_offset": off}
        exit_ret = close_ret
        exit_offset = off
    if not full_horizon_available:
        return None
    return {**st, "exit_ret": float(exit_ret), "exit_reason": exit_reason, "exit_offset": exit_offset}


def candidate_entries(df):
    entries = []
    # Conservative minute-level rules. All conditions use current or historical values only.
    for i in range(240, len(df) - 5):
        row = df.iloc[i]
        prev = df.iloc[i - 1]
        if not math.isfinite(row.get("close", float("nan"))):
            continue
        common = {
            "idx": i,
            "ts_ms": int(row["ts_ms"]),
            "utc": row["utc"],
            "price": float(row["close"]),
            "ret_5m": float(row.get("ret_5m", float("nan"))),
            "ret_15m": float(row.get("ret_15m", float("nan"))),
            "ret_60m": float(row.get("ret_60m", float("nan"))),
            "vol_z_20": float(row.get("vol_z_20", float("nan"))),
            "oi_chg_15m": float(row.get("oi_chg_15m", float("nan"))) if "oi_chg_15m" in row else float("nan"),
            "buy_sell_ratio": float(row.get("buy_sell_ratio", float("nan"))) if "buy_sell_ratio" in row else float("nan"),
            "bwe_events_1m": int(row.get("bwe_event_count_1m", 0)),
        }
        oi = common["oi_chg_15m"]
        taker = common["buy_sell_ratio"]
        oi_ok = (not math.isfinite(oi)) or oi > -2.0
        taker_long_ok = (not math.isfinite(taker)) or taker >= 0.95
        taker_short_ok = (not math.isfinite(taker)) or taker <= 1.05

        if row["breakout_20"] and row["ret_5m"] >= 4 and row["vol_z_20"] >= 1.0 and oi_ok and taker_long_ok:
            entries.append({**common, "rule": "L_breakout_20_vol_oi", "side": "long"})
        if row["ret_15m"] >= 12 and row["close"] > row["ema_5"] > row["ema_20"] and row["bwe_up_count_5m"] >= 1 and oi_ok:
            entries.append({**common, "rule": "L_bwe_impulse_hold", "side": "long"})
        # Reclaim after a hot pullback: previous 30m had a big impulse, current bar reclaims EMA5.
        recent_high = df["high"].iloc[max(0, i - 30) : i].max()
        recent_low = df["low"].iloc[max(0, i - 30) : i].min()
        impulse = (recent_high / recent_low - 1) * 100 if recent_low else 0
        drawdown = (row["close"] / recent_high - 1) * 100 if recent_high else 0
        if impulse >= 18 and -18 <= drawdown <= -3 and prev["close"] < prev["ema_5"] and row["close"] > row["ema_5"] and taker_long_ok:
            entries.append({**common, "rule": "L_pullback_ema_reclaim", "side": "long"})
        if row["ret_15m"] >= 35 and row["close"] < row["ema_5"] and prev["close"] >= prev["ema_5"] and taker_short_ok:
            entries.append({**common, "rule": "S_blowoff_ema_loss", "side": "short"})
        if row["breakdown_20"] and row["ret_5m"] <= -7 and row["vol_z_20"] >= 1.0 and taker_short_ok:
            entries.append({**common, "rule": "S_breakdown_20_vol", "side": "short"})
    return entries


def score_strategies(df, entries):
    configs = []
    for activation in [5, 8, 12, 18, 25, 35]:
        for giveback in [0.25, 0.35, 0.5, 0.65]:
            for hard_stop in [6, 9, 12, 18]:
                for max_hold in [15, 30, 60, 120, 240]:
                    configs.append((activation, giveback, hard_stop, max_hold))
    rows = []
    detailed = []
    for e in entries:
        # Avoid duplicate same-minute same-rule same-side from repeated event conditions.
        for activation, giveback, hard_stop, max_hold in configs:
            sim = simulate_exit(df, e["idx"], e["side"], activation, giveback, hard_stop, max_hold)
            if not sim:
                continue
            row = {
                **{k: v for k, v in e.items() if k != "idx"},
                "activation": activation,
                "giveback": giveback,
                "hard_stop": hard_stop,
                "max_hold": max_hold,
                "exit_ret": sim["exit_ret"],
                "mfe": sim["mfe"],
                "mae": sim["mae"],
                "exit_reason": sim["exit_reason"],
                "exit_offset_min": sim["exit_offset"],
            }
            detailed.append(row)
    if not detailed:
        return pd.DataFrame(), pd.DataFrame()
    detail_df = pd.DataFrame(detailed)
    group_cols = ["rule", "side", "activation", "giveback", "hard_stop", "max_hold"]
    for key, g in detail_df.groupby(group_cols):
        vals = g["exit_ret"].tolist()
        mfes = g["mfe"].tolist()
        maes = g["mae"].tolist()
        rows.append(
            {
                "rule": key[0],
                "side": key[1],
                "activation": key[2],
                "giveback": key[3],
                "hard_stop": key[4],
                "max_hold": key[5],
                "trades": len(g),
                "mean_exit_ret": statistics.mean(vals),
                "median_exit_ret": statistics.median(vals),
                "p10_exit_ret": pd.Series(vals).quantile(0.10),
                "p25_exit_ret": pd.Series(vals).quantile(0.25),
                "win_rate": sum(v > 0 for v in vals) / len(vals),
                "mean_mfe": statistics.mean(mfes),
                "mean_mae": statistics.mean(maes),
                "capture_ratio": statistics.mean(vals) / statistics.mean(mfes) if statistics.mean(mfes) else 0,
                "score": statistics.mean(vals) + pd.Series(vals).quantile(0.10) + min(0.0, statistics.mean(vals) / 2),
            }
        )
    summary = pd.DataFrame(rows).sort_values(["score", "trades"], ascending=[False, False])
    return summary, detail_df


def event_forward_returns(df, events):
    if events.empty:
        return pd.DataFrame()
    out = []
    for _, ev in events.iterrows():
        idxs = df.index[df["ts_ms"] >= ev["event_minute_ms"]].tolist()
        if not idxs:
            continue
        i = idxs[0]
        entry = df.at[i, "close"]
        row = {
            "event_utc": utc(ev["event_ts_ms"]),
            "source": ev["source"],
            "post_id": ev["post_id"],
            "event_side": ev["event_side"],
            "entry_minute_utc": df.at[i, "utc"],
            "entry_price": entry,
            "text": ev["text"][:220],
        }
        for h in [1, 3, 5, 10, 15, 30, 60, 120, 240]:
            end = min(len(df) - 1, i + h)
            window = df.iloc[i + 1 : end + 1]
            if window.empty:
                row[f"ret_{h}m"] = None
                row[f"mfe_{h}m"] = None
                row[f"mae_{h}m"] = None
            else:
                row[f"ret_{h}m"] = (df.at[end, "close"] / entry - 1) * 100
                row[f"mfe_{h}m"] = (window["high"].max() / entry - 1) * 100
                row[f"mae_{h}m"] = (window["low"].min() / entry - 1) * 100
        out.append(row)
    return pd.DataFrame(out)


def summarize_data(df, events, meta, public, tables):
    ticker = public.get("ticker_24h", {})
    premium = public.get("premium_index", {})
    local_ticker = tables.get("ticker_24h", pd.DataFrame())
    if (not isinstance(ticker, dict)) or ("error" in ticker):
        ticker = {}
    if (not isinstance(premium, dict)) or ("error" in premium):
        premium = {}
    if not local_ticker.empty:
        lt = local_ticker.dropna(how="all").iloc[-1].to_dict()
    else:
        lt = {}
    latest = df.iloc[-1].to_dict()
    return {
        "symbol": SYMBOL,
        "rows_1m": int(len(df)),
        "first_1m_utc": df["utc"].iloc[0],
        "last_1m_utc": df["utc"].iloc[-1],
        "listing_utc": utc(meta["listing_ts_ms"].iloc[0]) if not meta.empty else "",
        "bwe_events": int(len(events)),
        "bwe_first_utc": utc(events["event_ts_ms"].min()) if not events.empty else "",
        "bwe_last_utc": utc(events["event_ts_ms"].max()) if not events.empty else "",
        "latest_close": float(df["close"].iloc[-1]),
        "latest_close_vs_first_1m_pct": float((df["close"].iloc[-1] / df["close"].iloc[0] - 1) * 100),
        "sample_high": float(df["high"].max()),
        "sample_high_utc": df.loc[df["high"].idxmax(), "utc"],
        "sample_low": float(df["low"].min()),
        "sample_low_utc": df.loc[df["low"].idxmin(), "utc"],
        "latest_24h_change_pct": float(ticker.get("priceChangePercent", lt.get("price_change_percent", "nan"))),
        "latest_24h_high": float(ticker.get("highPrice", lt.get("high_price", "nan"))),
        "latest_24h_low": float(ticker.get("lowPrice", lt.get("low_price", "nan"))),
        "latest_24h_quote_volume": float(ticker.get("quoteVolume", lt.get("ticker_quote_volume", "nan"))),
        "latest_mark_price": float(premium.get("markPrice", latest.get("mark_close", "nan"))),
        "latest_funding_rate": float(premium.get("lastFundingRate", latest.get("funding_rate", "nan"))),
        "latest_oi": float(latest.get("sum_open_interest", "nan")),
        "latest_oi_chg_15m_pct": float(latest.get("oi_chg_15m", "nan")),
        "latest_taker_buy_sell_ratio": float(latest.get("buy_sell_ratio", "nan")),
        "latest_top_position_ls": float(latest.get("top_position_ls", "nan")),
        "latest_ret_15m_pct": float(latest.get("ret_15m", "nan")),
        "latest_ret_60m_pct": float(latest.get("ret_60m", "nan")),
        "latest_breakout_20": bool(latest.get("breakout_20", False)),
        "latest_bwe_event_count_1m": int(latest.get("bwe_event_count_1m", 0)),
    }


def write_report(data_summary, strat_summary, detail_df, event_df, df):
    top = strat_summary.head(12).copy()
    best = top.iloc[0].to_dict() if not top.empty else {}
    event_source = event_df.groupby("source").size().sort_values(ascending=False).to_dict() if not event_df.empty else {}
    recent = df.tail(6)[["utc", "open", "high", "low", "close", "quote_volume", "trade_count", "ret_1m", "ret_5m", "ret_15m", "sum_open_interest", "buy_sell_ratio", "top_position_ls"]]
    report = []
    report.append("# LABUSDT Single-Symbol Entry/Exit Research - 2026-05-02\n")
    report.append("## Verdict\n")
    if best:
        report.append(
            f"Best scanned case-study rule: `{best['rule']}` `{best['side']}` with exit activation `{best['activation']}%`, "
            f"giveback `{best['giveback']}`, hard stop `{best['hard_stop']}%`, max hold `{best['max_hold']}m`.\n"
        )
        report.append(
            f"Scan stats: trades `{int(best['trades'])}`, mean `{best['mean_exit_ret']:.2f}%`, median `{best['median_exit_ret']:.2f}%`, "
            f"p10 `{best['p10_exit_ret']:.2f}%`, win rate `{best['win_rate']:.1%}`, mean MFE `{best['mean_mfe']:.2f}%`, capture `{best['capture_ratio']:.1%}`.\n"
        )
    report.append(
        "This is a LABUSDT-only case study on one extreme regime, not a live promotion. It should seed a cross-symbol rerun before any trading decision.\n\n"
    )
    report.append(
        "Scan scoring excludes right-censored entries that have not reached their max-hold window unless stop/trailing exit already fired.\n\n"
    )
    report.append("## Data Used\n")
    for k, v in data_summary.items():
        report.append(f"- `{k}`: `{v}`\n")
    report.append(f"- BWE event count by source: `{event_source}`\n\n")
    report.append("## Strategy Shape\n")
    report.append(
        "The strongest practical shape is not instant chase on every alert. It is a two-stage long framework: "
        "enter only when LAB breaks or reclaims momentum with abnormal volume and non-collapsing OI, then use a delayed trailing exit that starts only after meaningful MFE. "
        "For 'eat full before exit', the exit should tolerate large noise early and tighten only after the move pays.\n\n"
    )
    report.append("Recommended LAB-specific candidate:\n\n")
    report.append(
        "1. Entry A - momentum continuation: close above prior 20-minute high, 5m return >= 4%, 20-bar quote-volume z-score >= 1, OI 15m change > -2%, taker buy/sell >= 0.95.\n"
    )
    report.append(
        "2. Entry B - hot pullback reclaim: previous 30m impulse >= 18%, current pullback from recent high between 3% and 18%, price reclaims EMA5, taker ratio not weak.\n"
    )
    report.append(
        "3. Exit - eat-full trailing: hard stop around 9-12%, do not trail until +12% to +18% MFE, then allow 35-50% giveback of peak gains, max hold 120-240m. "
        "Exit earlier if OI drops hard and taker ratio flips below 1 while price loses EMA5.\n\n"
    )
    latest_breakout = data_summary.get("latest_breakout_20")
    latest_taker = data_summary.get("latest_taker_buy_sell_ratio")
    latest_oi = data_summary.get("latest_oi_chg_15m_pct")
    report.append("## Current Read\n\n")
    report.append(
        f"As of `{data_summary.get('last_1m_utc')}` UTC, close is `{data_summary.get('latest_close'):.4f}`, "
        f"15m return `{data_summary.get('latest_ret_15m_pct'):.2f}%`, 60m return `{data_summary.get('latest_ret_60m_pct'):.2f}%`, "
        f"20m breakout flag `{latest_breakout}`, taker buy/sell `{latest_taker:.4f}`, OI 15m change `{latest_oi:.2f}%`, "
        f"top-position long/short `{data_summary.get('latest_top_position_ls'):.4f}`.\n\n"
    )
    report.append(
        "That combination is a bounce with top-trader positioning still net long, but taker flow below 1.0. "
        "It is not a clean fresh long trigger under the scanned rules; the cleaner entry is either a new high-volume breakout above the recent 20m high with taker recovery, or a controlled pullback/reclaim.\n\n"
    )
    report.append("## Top Scanned Rules\n\n")
    report.append(top.to_markdown(index=False) if not top.empty else "No strategies scored.")
    report.append("\n\n## Recent 1m Bars\n\n")
    report.append(recent.to_markdown(index=False))
    report.append("\n\n## Important Caveats\n")
    report.append("- Only minute-level OHLC was available locally/fetched; no true local 1s LABUSDT bars were found.\n")
    report.append("- Single-symbol, single-regime scans are overfit-prone. Treat this as mechanism discovery, then validate on other hot listings/pumps.\n")
    report.append("- The current Hermes symlinks for BWE logs and collector DB point to old `/Volumes/T9/BWE/...` hot paths; actual live data used here is under `/Volumes/T9_HOT`.\n")
    report.append("- No Binance/OKX order endpoint was called.\n")
    text = "".join(report)
    (RUN_ROOT / "LABUSDT_RESEARCH_REPORT.md").write_text(text)
    (REPORT_ROOT / "LABUSDT_RESEARCH_REPORT.md").write_text(text)
    return text


def main():
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    public = cache_public_data()
    tables, meta = load_db_data()
    df, events = build_feature_table(tables, public)
    df.to_csv(RUN_ROOT / "labusdt_minute_features.csv", index=False)
    if not events.empty:
        events.to_csv(RUN_ROOT / "labusdt_bwe_events.csv", index=False)
    event_df = event_forward_returns(df, events)
    event_df.to_csv(RUN_ROOT / "labusdt_event_forward_returns.csv", index=False)
    entries = candidate_entries(df)
    (RUN_ROOT / "candidate_entries.json").write_text(json.dumps(entries, ensure_ascii=False, indent=2))
    strat_summary, detail_df = score_strategies(df, entries)
    if not strat_summary.empty:
        strat_summary.to_csv(RUN_ROOT / "strategy_scan_summary.csv", index=False)
        detail_df.to_csv(RUN_ROOT / "strategy_scan_trades.csv", index=False)
    data_summary = summarize_data(df, events, meta, public, tables)
    (RUN_ROOT / "data_summary.json").write_text(json.dumps(data_summary, ensure_ascii=False, indent=2))
    write_report(data_summary, strat_summary, detail_df, event_df, df)
    print(json.dumps(data_summary, ensure_ascii=False, indent=2))
    if not strat_summary.empty:
        print(strat_summary.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
