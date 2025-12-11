# infra/state.py
from __future__ import annotations
from collections import deque
from pathlib import Path
from datetime import datetime
import json

def ensure_dir(d: Path) -> None:
    d.mkdir(parents=True, exist_ok=True)

class CrawlState:
    def __init__(self, data_dir: Path):
        self.state_dir = (data_dir / "state")
        ensure_dir(self.state_dir)
        self.state_path = self.state_dir / "crawl_state.json"
        self.tmp_path = self.state_dir / "crawl_state.json.tmp"

    def load(self) -> tuple[deque[str], str|None, int, set[str]]:
        if not self.state_path.exists():
            return deque(), None, 0, set()
        j = json.loads(self.state_path.read_text(encoding="utf-8"))
        q = deque(j.get("queue", []))
        inflight = j.get("inflight")
        used = int(j.get("requests_used", 0))
        enq = j.get("enqueued_keys")
        enq_keys = set(enq) if isinstance(enq, list) else set()
        return q, inflight, used, enq_keys

    def save(self, queue, inflight, used, enq_keys: set[str] | None = None) -> None:
        payload = {
            "queue": list(queue),
            "inflight": inflight,
            "requests_used": used,
            "last_saved_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        }
        if enq_keys is not None:
            payload["enqueued_keys"] = list(enq_keys)
        self.tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self.tmp_path.replace(self.state_path)
