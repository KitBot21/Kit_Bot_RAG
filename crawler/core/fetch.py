from __future__ import annotations
from pathlib import Path
from .utils import html_cache_path
import time
import requests

def fetch_text(url: str, headers: dict, timeout: int) -> str | None:
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        r.raise_for_status()
        return r.text
    except Exception:
        return None

def fetch_html(url: str, headers: dict, timeout: int, sleep_sec: float, cache_dir: Path, robots_delay: float) -> str | None:
    fp = html_cache_path(cache_dir, url)
    if fp.exists():
        return fp.read_text(encoding="utf-8", errors="ignore")
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        ct = r.headers.get("Content-Type", "")
        if r.status_code != 200 or ("html" not in ct and "xml" not in ct):
            return None
        html = r.text
        fp.write_text(html, encoding="utf-8")
        time.sleep(max(sleep_sec, robots_delay))
        return html
    except Exception:
        return None
    
    # core/fetch.py (추가)
def fetch_binary(url: str, headers: dict, timeout: int, sleep_sec: float, robots_delay: float):
    import requests, time
    r = requests.get(url, headers=headers, timeout=timeout, stream=True)
    r.raise_for_status()
    content_type = r.headers.get("Content-Type", "")
    content_disp = r.headers.get("Content-Disposition", "")

    filename = None
    if "filename=" in content_disp:
        filename = content_disp.split("filename=")[-1].strip('"; ')
    if not filename:
        from urllib.parse import urlparse
        filename = urlparse(url).path.split("/")[-1] or "download.bin"

    content = r.content
    time.sleep(max(sleep_sec, robots_delay))
    return filename, content, content_type