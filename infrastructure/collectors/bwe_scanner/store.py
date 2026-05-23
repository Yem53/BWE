from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def append_alert(jsonl_dir: str, alert: dict, now_ms: int) -> Path:
    """Append one alert as a JSON line to alerts_YYYY-MM-DD.jsonl (UTC date)."""
    day = datetime.fromtimestamp(now_ms / 1000, timezone.utc).strftime("%Y-%m-%d")
    d = Path(jsonl_dir)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"alerts_{day}.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(alert, ensure_ascii=False) + "\n")
    return path
