from __future__ import annotations
from pathlib import Path
import csv
from datetime import datetime
from .base import Storage
from .parser import extract_title_area_text   # 경로는 프로젝트 구조에 맞게 조정
from core.utils import trim_to_kitbot

class SaveStorage(Storage):
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.pages_csv = data_dir / "pages.csv"
        self.atts_csv = data_dir / "attachments.csv"
        self._page_title_area: dict[str, str] = {}  # ← 페이지 URL별 title_area 캐시
        self._init()

    def _init(self):
        if not self.pages_csv.exists():
            with self.pages_csv.open("w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow([
                    "url","saved_html_path","title","lastmod","fetched_at","section","out_links","text_length","title_area"
                ])
        if not self.atts_csv.exists():
            with self.atts_csv.open("w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow([
                    "page_url","file_text","href_abs","saved_path","ext",
                    "size_bytes","sha1","content_type","policy","detected_at"
                ])

    def save_page(self, *, url: str, saved_path: str, title: str, lastmod: str | None,
                  fetched_at: str, section: str, out_links: int, text_length: int, html: str) -> None:
        # 1) title-area 텍스트 추출
        title_area = extract_title_area_text(html) if html else ""

        # 2) 경로 축약: KitBot부터
        saved_path_trimmed = trim_to_kitbot(saved_path)

        # 페이지 URL → title_area 캐시 (첨부 CSV에서 사용)
        self._page_title_area[url] = title_area  # 원본 URL → 스냅샷 경로

        # 3) CSV 기록 (title_area 포함)
        with self.pages_csv.open("a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                url, saved_path_trimmed, title, lastmod or "", fetched_at,
                section, out_links, text_length, title_area
            ])
    def save_attachments(self, rows, policy: str) -> None:
        if not rows:
            return
        with self.atts_csv.open("a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            for r in rows:
                saved_path = r.get("saved_path","")
                ext = Path(saved_path or r["href_abs"]).suffix.lower()
                w.writerow([
                    r["page_url"], r["file_text"], r["href_abs"], saved_path, ext,
                    r.get("size_bytes",""), r.get("sha1",""), r.get("content_type",""),
                    policy, r["detected_at"]
                ])

    def save_document(self, **kwargs): 
        return self.save_page(**kwargs)
    def save_fragments(self, *, url: str, fragments: dict, fetched_at: str) -> None:
        return
