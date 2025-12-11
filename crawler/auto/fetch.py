# auto/fetch.py
from __future__ import annotations
from pathlib import Path

# 1) core.fetch 재활용
from core.fetch import fetch_text as _fetch_text
from core.fetch import fetch_html as _fetch_html
from core.fetch import fetch_binary as _fetch_binary

# 2) 기본값(프로젝트에 있으면 가져다 쓰고, 없으면 로컬 경로 사용)
try:
    # 있으면 사용 (예: infra/config.py 등에 FIXTURES_DIR 정의)
    from infra.config import FIXTURES_DIR as _CACHE_DIR  # type: ignore
except Exception:
    _CACHE_DIR = Path("data/auto_cache")
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_HEADERS = {
    "User-Agent": "KITBot (CSEcapstone, contact: cdh5113@naver.com)",
    "Accept-Language": "ko, en;q=0.8",
}
DEFAULT_TIMEOUT = 15
DEFAULT_SLEEP = 0.5

# 3) 얇은 래퍼 (robots_delay는 auto 작업에선 0으로 둬도 됨)
def fetch_text(url: str, headers: dict | None = None, timeout: int = DEFAULT_TIMEOUT):
    return _fetch_text(url, headers or DEFAULT_HEADERS, timeout)

def fetch_html(
    url: str,
    headers: dict | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    sleep_sec: float = DEFAULT_SLEEP,
    cache_dir: Path = _CACHE_DIR,
    robots_delay: float = 0.0,
):
    return _fetch_html(url, headers or DEFAULT_HEADERS, timeout, sleep_sec, cache_dir, robots_delay)

def fetch_binary(
    url: str,
    headers: dict | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    sleep_sec: float = DEFAULT_SLEEP,
    robots_delay: float = 0.0,
):
    return _fetch_binary(url, headers or DEFAULT_HEADERS, timeout, sleep_sec, robots_delay)
