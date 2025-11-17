from __future__ import annotations
from pathlib import Path
import csv
from datetime import datetime

DATA_DIR = Path("data/auto")
DATA_DIR.mkdir(parents=True, exist_ok=True)

def _csv(name: str) -> Path:
    safe = "".join(ch if ch.isalnum() else "_" for ch in name)
    return DATA_DIR / f"{safe}.csv"

def save_board(name: str, rows: list[dict]):
    path = _csv(name)
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["ts", "title", "url", "date"])
        if new: w.writeheader()
        for r in rows:
            w.writerow({"ts": datetime.now().isoformat(timespec="seconds"), **r})

def save_menu(name: str, rows: list[dict]):
    path = _csv(name)
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["ts", "key", "content"])
        if new: w.writeheader()
        for r in rows:
            w.writerow({"ts": datetime.now().isoformat(timespec="seconds"), **r})

def save_schedule(name: str, rows: list[dict]):
    path = _csv(name)
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["ts", "date", "title"])
        if new: w.writeheader()
        for r in rows:
            w.writerow({"ts": datetime.now().isoformat(timespec="seconds"), **r})
