#!/usr/bin/env python3
import argparse
import concurrent.futures as cf
import html
import json
import os
import re
import sys
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

import requests
import websocket

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
BWE_WS_URL = "wss://bwenews-api.bwe-ws.com/ws"
BWE_HISTORY_URL = "https://news.treeofalpha.com/api/news?limit=100"

CHANNELS = {
    "BWEnews": {"kind": "telegram", "priority": "high"},
    "BWEtradfi": {"kind": "telegram", "priority": "high"},
    "BWE_pricechange_monitor": {"kind": "telegram", "priority": "high"},
    "BWE_OI_Price_monitor": {"kind": "telegram", "priority": "high"},
    "BWE_Reserved6": {"kind": "telegram", "priority": "high"},
    "BWE_tier2_monitor": {"kind": "telegram", "priority": "medium"},
    "BWE_Binance_monitor": {"kind": "telegram", "priority": "high"},
    "BWE_reserved1": {"kind": "telegram", "priority": "medium"},
    "bwe_earn": {"kind": "telegram", "priority": "low"},
    "bwe_tier3_monitor": {"kind": "telegram", "priority": "medium"},
    "bwe_korean_monitor": {"kind": "telegram", "priority": "high"},
    "bwe_reserved4": {"kind": "telegram", "priority": "medium"},
    "bwe_reserved3": {"kind": "telegram", "priority": "low"},
    "bwe_reserved7": {"kind": "telegram", "priority": "low"},
}


class State:
    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.Lock()
        self.data = {
            "seen": {},
            "ws_seen": {},
            "started_at": int(time.time()),
        }
        if path.exists():
            try:
                self.data.update(json.loads(path.read_text()))
            except Exception:
                pass

    def save(self) -> None:
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2))

    def seen_post(self, source: str, post_id: str) -> bool:
        with self.lock:
            return post_id in set(self.data.setdefault("seen", {}).get(source, []))

    def remember_post(self, source: str, post_id: str) -> None:
        with self.lock:
            arr = self.data.setdefault("seen", {}).setdefault(source, [])
            arr.append(post_id)
            self.data["seen"][source] = arr[-300:]

    def seen_ws(self, item_id: str) -> bool:
        with self.lock:
            return item_id in set(self.data.setdefault("ws_seen", {}).get("BWEnews_ws", []))

    def remember_ws(self, item_id: str) -> None:
        with self.lock:
            arr = self.data.setdefault("ws_seen", {}).setdefault("BWEnews_ws", [])
            arr.append(item_id)
            self.data["ws_seen"]["BWEnews_ws"] = arr[-500:]

    def has_seen_state(self) -> bool:
        with self.lock:
            seen = self.data.get("seen", {})
            ws_seen = self.data.get("ws_seen", {})
            return any(seen.values()) or any(ws_seen.values())


class Logger:
    def __init__(self, posts_path: Path, health_path: Path):
        self.posts_path = posts_path
        self.health_path = health_path
        self.lock = threading.Lock()
        self.posts_path.parent.mkdir(parents=True, exist_ok=True)
        self.health_path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, event: Dict) -> None:
        line = json.dumps(event, ensure_ascii=False)
        target = self.posts_path if event.get("type") == "post" else self.health_path
        with self.lock:
            with target.open("a", encoding="utf-8") as f:
                f.write(line + "\n")


class BWEHybridMonitor:
    def __init__(self, state_path: Path, posts_path: Path, health_path: Path, interval: float, heartbeat_seconds: int):
        self.state = State(state_path)
        self.logger = Logger(posts_path, health_path)
        self.interval = interval
        self.heartbeat_seconds = heartbeat_seconds
        self.stop_event = threading.Event()
        self.last_heartbeat = 0.0
        self.http = requests.Session()
        self.http.headers.update({"User-Agent": USER_AGENT})

    def bootstrap_channel(self, username: str) -> None:
        posts = self.fetch_channel(username)
        for post in posts:
            self.state.remember_post(username, post["id"])

    def bootstrap_ws(self) -> None:
        try:
            resp = self.http.get(BWE_HISTORY_URL, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                for item in data:
                    item_id = str(item.get("_id") or item.get("id") or "")
                    if item_id:
                        self.state.remember_ws(item_id)
        except Exception as exc:
            self.logger.write({"ts_ms": int(time.time()*1000), "type": "bootstrap_error", "source": "BWEnews_ws", "error": str(exc)})

    def fetch_channel(self, username: str) -> List[Dict[str, str]]:
        url = f"https://t.me/s/{username}"
        resp = self.http.get(url, timeout=10)
        resp.raise_for_status()
        html_text = resp.text
        matches = re.findall(
            r'data-post="[^\"]+/(\d+)"[\s\S]*?<div class="tgme_widget_message_text[^>]*>([\s\S]*?)</div>',
            html_text,
            re.I,
        )
        posts = []
        for post_id, frag in matches[-12:]:
            text = self.clean_html(frag)
            if text:
                posts.append({"id": post_id, "text": text})
        return posts

    @staticmethod
    def clean_html(fragment: str) -> str:
        fragment = re.sub(r"<br\s*/?>", "\n", fragment, flags=re.I)
        fragment = re.sub(r"<a [^>]*>(.*?)</a>", r"\1", fragment, flags=re.I | re.S)
        fragment = re.sub(r"<[^>]+>", "", fragment)
        fragment = html.unescape(fragment)
        fragment = re.sub(r"\s+", " ", fragment).strip()
        return fragment

    def log_post(self, source: str, post_id: str, text: str, via: str) -> None:
        self.logger.write({
            "ts_ms": int(time.time() * 1000),
            "type": "post",
            "via": via,
            "source": source,
            "post_id": post_id,
            "text": text,
        })

    def poll_once(self, username: str) -> None:
        try:
            posts = self.fetch_channel(username)
            for post in posts:
                if not self.state.seen_post(username, post["id"]):
                    self.log_post(username, post["id"], post["text"], via="telegram_public_poll")
                    self.state.remember_post(username, post["id"])
            self.state.save()
        except Exception as exc:
            self.logger.write({"ts_ms": int(time.time()*1000), "type": "poll_error", "source": username, "error": str(exc)})

    def poll_loop(self) -> None:
        usernames = list(CHANNELS.keys())
        while not self.stop_event.is_set():
            start = time.time()
            with cf.ThreadPoolExecutor(max_workers=min(8, len(usernames))) as pool:
                list(pool.map(self.poll_once, usernames))
            self.heartbeat(via="poll")
            elapsed = time.time() - start
            time.sleep(max(0.05, self.interval - elapsed))

    def heartbeat(self, via: str) -> None:
        now = time.time()
        if self.heartbeat_seconds and now - self.last_heartbeat >= self.heartbeat_seconds:
            counts = {k: len(v) for k, v in self.state.data.get("seen", {}).items()}
            self.logger.write({
                "ts_ms": int(now * 1000),
                "type": "heartbeat",
                "via": via,
                "tracked_channels": len(CHANNELS),
                "seen_counts": counts,
            })
            print(json.dumps({"ts": int(now), "status": "ok", "via": via, "tracked": len(CHANNELS)}), flush=True)
            self.last_heartbeat = now

    def ws_loop(self) -> None:
        backoff = 1
        while not self.stop_event.is_set():
            try:
                ws = websocket.WebSocketApp(
                    BWE_WS_URL,
                    on_open=self._on_ws_open,
                    on_message=self._on_ws_message,
                    on_error=self._on_ws_error,
                    on_close=self._on_ws_close,
                )
                ws.run_forever(ping_interval=15, ping_timeout=8)
            except Exception as exc:
                self.logger.write({"ts_ms": int(time.time()*1000), "type": "ws_error", "source": "BWEnews_ws", "error": str(exc)})
            time.sleep(backoff)
            backoff = min(backoff * 2, 10)

    def _on_ws_open(self, ws) -> None:
        self.logger.write({"ts_ms": int(time.time()*1000), "type": "ws_open", "source": "BWEnews_ws"})

    def _on_ws_message(self, ws, message: str) -> None:
        try:
            item = json.loads(message)
        except Exception:
            return
        if not isinstance(item, dict):
            return
        if "user" in item and len(item.keys()) <= 2:
            return
        item_id = str(item.get("_id") or item.get("id") or item.get("time") or "")
        if not item_id or self.state.seen_ws(item_id):
            return
        text = " | ".join([v.strip() for k, v in (("en", item.get("en")), ("title", item.get("title")), ("body", item.get("body"))) if isinstance(v, str) and v.strip()])
        self.logger.write({
            "ts_ms": int(time.time()*1000),
            "type": "post",
            "via": "bwe_websocket",
            "source": "BWEnews_ws",
            "post_id": item_id,
            "payload": item,
            "text": text,
        })
        self.state.remember_ws(item_id)
        self.state.save()
        self.heartbeat(via="ws")

    def _on_ws_error(self, ws, error) -> None:
        self.logger.write({"ts_ms": int(time.time()*1000), "type": "ws_error", "source": "BWEnews_ws", "error": str(error)})

    def _on_ws_close(self, ws, code, msg) -> None:
        self.logger.write({"ts_ms": int(time.time()*1000), "type": "ws_close", "source": "BWEnews_ws", "code": code, "message": msg})

    def run(self) -> int:
        if not self.state.has_seen_state():
            self.bootstrap_ws()
            for username in CHANNELS:
                self.bootstrap_channel(username)
            self.state.save()
        t = threading.Thread(target=self.ws_loop, daemon=True)
        t.start()
        self.poll_loop()
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Low-latency monitor for BWE channel matrix")
    parser.add_argument("--interval", type=float, default=1.0, help="Public Telegram poll interval in seconds")
    parser.add_argument("--heartbeat-seconds", type=int, default=30)
    parser.add_argument("--state", default=str(Path.home()/'.hermes'/'state'/'bwe_matrix_monitor_state.json'))
    parser.add_argument("--posts-log", default=str(Path.home()/'.hermes'/'logs'/'bwe_matrix_posts.jsonl'))
    parser.add_argument("--health-log", default=str(Path.home()/'.hermes'/'logs'/'bwe_matrix_health.jsonl'))
    parser.add_argument(
        "--log",
        default=None,
        help="Deprecated alias for --posts-log. If provided, post events are written here.",
    )
    args = parser.parse_args()
    posts_path = Path(args.log or args.posts_log).expanduser()
    health_path = Path(args.health_log).expanduser()

    mon = BWEHybridMonitor(
        state_path=Path(args.state).expanduser(),
        posts_path=posts_path,
        health_path=health_path,
        interval=args.interval,
        heartbeat_seconds=args.heartbeat_seconds,
    )
    try:
        return mon.run()
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
