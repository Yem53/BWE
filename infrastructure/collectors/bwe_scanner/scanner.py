from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import threading
import time

import detectors
import notify
import store
from enrich import MarketCapCache, Ticker24hCache
from ws_feed import OIPoller, PriceBuffers, RestPriceFeed, WSFeed


def run_detection_tick(cfg, samples, ctx, oi, mc, now_ms, last_fired):
    """PURE pipeline: per-symbol buffers → detections → cooldown → enriched alert dicts.

    samples: {sym: [(ts,price)]}; ctx: {sym: {chg_24h_pct, quote_vol_24h}}; oi: {sym: (chg,usd)}.
    mc: MarketCapCache | None. Returns list of alert dicts (ready to store/push)."""
    detections = []
    for sym, sm in samples.items():
        if not sm:
            continue
        detections += detectors.detect_price_ladder(sym, sm, now_ms, cfg["windows"])
        oi_chg, oi_usd = oi.get(sym, (None, None))
        oc = cfg["oi_price_1h"]
        d = detectors.detect_oi_price_1h(sym, sm, oi_chg, oi_usd, now_ms,
                                         oc["price_thr_pct"], oc["oi_thr_pct"])
        if d:
            detections.append(d)
    kept = detectors.apply_cooldown(detections, last_fired, cfg["store_cooldown_sec"], now_ms)
    alerts = []
    for d in kept:
        sym_ctx = ctx.get(d.symbol, {})
        price = d.price or sym_ctx.get("last_price", 0.0)
        mcap = mc.market_cap(d.symbol, price) if mc else None
        alerts.append(detectors.alert_to_dict(detectors.to_alert(d, sym_ctx, mcap)))
    return alerts


class Scanner:
    def __init__(self, cfg: dict, dry_run: bool = False):
        self.cfg = cfg
        self.dry_run = dry_run
        self.buffers = PriceBuffers()
        self.ticker = Ticker24hCache(cfg["fapi_base"])
        self.mc = MarketCapCache.from_file(cfg["paths"]["cg_map"])
        self.oi = OIPoller(cfg["fapi_base"], cfg.get("oi_poll_sec", 300))
        # feed_mode "rest" (default) polls fapi /ticker/price; "ws" uses the fstream
        # websocket (kept for environments where futures WS delivers data — this EC2 does not).
        if cfg.get("feed_mode", "rest") == "ws":
            self.feed = WSFeed(cfg["ws_url"], self.buffers)
        else:
            self.feed = RestPriceFeed(cfg["fapi_base"], self.buffers, cfg.get("price_poll_sec", 1.0))
        self.last_fired_store: dict = {}
        self.last_fired_push: dict = {}
        self._stop = False
        self._tg_token = os.environ.get(cfg["telegram"]["token_env"], "")
        self._tg_chat = os.environ.get(cfg["telegram"]["chat_id_env"], "")
        self._last_24h = 0.0
        self._last_supply = 0.0
        self._last_hb = 0.0
        self._alert_count = 0

    def _log(self, msg: str) -> None:
        print(f"[{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}] {msg}", flush=True)

    def _maybe_refresh(self, now: float) -> None:
        if now - self._last_24h >= self.cfg.get("ticker24h_poll_sec", 60):
            try:
                self.ticker.refresh()
            except Exception as e:
                self._log(f"24h refresh err: {e}")
            try:
                # decoupled: a ticker failure must not starve the OI universe
                self.oi.set_universe(list(self.buffers.symbols()))
            except Exception as e:
                self._log(f"oi set_universe err: {e}")
            self._last_24h = now
        if now - self._last_supply >= self.cfg.get("supply_refresh_sec", 86400):
            try:
                self.mc.refresh_supply()
            except Exception as e:
                self._log(f"supply refresh err: {e}")
            self._last_supply = now

    def _ctx_map(self) -> dict:
        out = {}
        for sym in self.buffers.symbols():
            c = self.ticker.get(sym)
            if c:
                out[sym] = c
        return out

    def _oi_map(self) -> dict:
        return {sym: self.oi.get(sym) for sym in self.buffers.symbols()}

    def tick(self) -> None:
        now_ms = int(time.time() * 1000)
        samples = {sym: self.buffers.samples(sym) for sym in self.buffers.symbols()}
        alerts = run_detection_tick(self.cfg, samples, self._ctx_map(), self._oi_map(),
                                    self.mc, now_ms, self.last_fired_store)
        for a in alerts:
            self._alert_count += 1
            store.append_alert(self.cfg["paths"]["jsonl_dir"], a, now_ms)
            if self.dry_run:
                self._log("ALERT " + notify.format_alert_msg(a))
            elif self.cfg["telegram"]["enabled"] and notify.should_push(a, self.cfg["push_filter"]):
                key = (a["symbol"], a["window_type"])
                prev = self.last_fired_push.get(key)
                if (prev is None or (now_ms - prev) >= self.cfg["push_cooldown_sec"] * 1000) \
                        and self._tg_token and self._tg_chat:
                    self.last_fired_push[key] = now_ms
                    # fire-and-forget: never let a slow Telegram POST block the 1s tick loop
                    threading.Thread(
                        target=notify.send_telegram,
                        args=(self._tg_token, self._tg_chat, notify.format_alert_msg(a)),
                        daemon=True,
                    ).start()

    def _heartbeat(self, now: float) -> None:
        if now - self._last_hb >= 300:
            age = (int(time.time() * 1000) - self.feed.last_msg_ms) / 1000 if self.feed.last_msg_ms else -1
            self._log(f"HB symbols={len(self.buffers.symbols())} alerts={self._alert_count} "
                      f"ws_age={age:.0f}s")
            self._last_hb = now

    def run(self) -> int:
        signal.signal(signal.SIGTERM, lambda *_: setattr(self, "_stop", True))
        signal.signal(signal.SIGINT, lambda *_: setattr(self, "_stop", True))
        self.feed.start()
        self.oi.start()
        self._log(f"scanner started (dry_run={self.dry_run})")
        while not self._stop:
            now = time.time()
            self._maybe_refresh(now)
            try:
                self.tick()
            except Exception as e:
                self._log(f"tick err: {e}")
            self._heartbeat(now)
            time.sleep(1.0)
        self.feed.stop()
        self.oi.stop()
        self._log("scanner stopped")
        return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    with open(args.config) as f:
        cfg = json.load(f)
    return Scanner(cfg, dry_run=args.dry_run).run()


if __name__ == "__main__":
    sys.exit(main())
