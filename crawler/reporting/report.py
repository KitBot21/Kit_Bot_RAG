from __future__ import annotations
from pathlib import Path
from urllib.parse import urlparse
from collections import Counter
import csv

def make_report_html(data_dir: Path):
    pages_csv = data_dir / "pages.csv"
    atts_csv = data_dir / "attachments.csv"

    pages = []
    if pages_csv.exists():
        with pages_csv.open("r", encoding="utf-8") as f:
            pages = list(csv.DictReader(f))

    atts = []
    if atts_csv.exists():
        with atts_csv.open("r", encoding="utf-8") as f:
            atts = list(csv.DictReader(f))

    total_pages = len(pages)
    recent = sorted(pages, key=lambda x: x.get("fetched_at", ""), reverse=True)[:20]

    def sec_key(u):
        try:
            p = urlparse(u).path.strip("/").split("/")
            return "/".join(p[:2]) if len(p) >= 2 else (p[0] if p else "")
        except Exception:
            return ""
