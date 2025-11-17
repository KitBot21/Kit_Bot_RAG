from __future__ import annotations
from .base import Storage
from datetime import datetime
import hashlib

class MongoStorage(Storage):
    def __init__(self, client, db_name: str):
        self.db = client[db_name]
        self.pages = self.db.pages
        self.atts = self.db.attachments
        self.pages.create_index([("url", 1)], unique=True)
        self.atts.create_index([("page_url", 1), ("href_abs", 1)], unique=True)

    def save_page(self, *, url: str, saved_path: str, title: str, lastmod: str | None,
                  fetched_at: str, section: str, out_links: int, text_length: int, html: str) -> None:
        sha1 = hashlib.sha1(html.encode("utf-8", "ignore")).hexdigest()
        self.pages.update_one(
            {"url": url},
            {"$set": {
                "title": title,
                "lastmod": lastmod,
                "fetched_at": fetched_at,
                "section": section,
                "text_length": text_length,
                "saved_html_path": saved_path,
                "content_sha1": sha1,
                "out_links": out_links,
            }},
            upsert=True,
        )

    def save_attachments(self, rows, policy: str) -> None:
        for r in rows:
            href = r["href_abs"]
            ext = ""
            if "." in href:
                ext = href[href.rfind("."):].lower()
            self.atts.update_one(
                {"page_url": r["page_url"], "href_abs": href},
                {"$set": {
                    "file_text": r["file_text"],
                    "ext": ext,
                    "policy": policy,
                    "detected_at": r["detected_at"],
                }},
                upsert=True,
            )
