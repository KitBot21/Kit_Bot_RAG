from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Iterable

class Storage(ABC):
    @abstractmethod
    def save_page(self, *, url: str, saved_path: str, title: str, lastmod: str | None,
                  fetched_at: str, section: str, out_links: int, text_length: int, html: str) -> None:
        ...

    @abstractmethod
    def save_attachments(self, rows: Iterable[dict], policy: str) -> None:
        ...