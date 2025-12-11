from __future__ import annotations
from urllib.parse import urljoin, urlparse, urlunparse, urldefrag, parse_qsl, urlencode
from pathlib import Path
import hashlib

def normalize_url(url: str, base: str) -> str:
    abs_url = urljoin(base, url)
    abs_url, _ = urldefrag(abs_url)
    u = urlparse(abs_url)
    qs_pairs = parse_qsl(u.query, keep_blank_values=True)
        # article.offset 제거
    filtered = [(k, v) for k, v in qs_pairs if k != "article.offset"]

    filtered.sort()
    canon_qs = urlencode(filtered, doseq=True)

    return urlunparse((u.scheme, u.netloc, u.path, u.params, canon_qs, ""))

def trim_to_kitbot(path: str | Path) -> str:
    p = Path(path)
    for i, part in enumerate(p.parts):
        if part.lower() == "kitbot":
            return str(Path(*p.parts[i:]))
    return str(p)

def html_cache_path(fixtures_dir: Path, url: str) -> Path:
    u = urlparse(url)
    raw = (u.path or "/") + ("?" + u.query if u.query else "")
    h = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    safe = (u.path.strip("/").replace("/", "__") or "index") + f"__{h}.html"
    return fixtures_dir / safe

def is_already_crawled(fixtures_dir: Path, url: str) -> bool:
    # 스냅샷 HTML 존재 여부만으로 멱등성 보장 (첨부까지 보려면 확장)
    return html_cache_path(fixtures_dir, url).exists()