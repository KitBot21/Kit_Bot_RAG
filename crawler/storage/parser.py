from __future__ import annotations
from bs4 import BeautifulSoup
import re

# ✅ 추가: 이메일 레드액트 유틸 (storage/pii.py에 구현되어 있어야 합니다)
try:
    from storage.pii import redact_email_text
except Exception:
    # 유틸이 아직 없으면 간단한 fallback (필요시 삭제)
    EMAIL_RE = re.compile(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[A-Za-z]{2,}\b')
    def redact_email_text(text: str, replacement: str = "[이메일 문의: 원문 참조]") -> str:
        return EMAIL_RE.sub(replacement, text)

ATTACH_EXT = re.compile(r"\.(hwpx|hwp|pdf|docx?|xlsx?|pptx?|zip|png|jpe?g)$", re.IGNORECASE)

# <div class="title-area"> 텍스트 추출
def extract_title_area_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    el = soup.select_one(".title-area")
    return el.get_text(strip=True) if el else "없음"

# 스냅샷을 요약하기 위해 사용
def extract_title_and_text(html: str,
    *,
    redact_email: bool = True,
    email_replacement: str = "[이메일 문의: 원문 참조]",
) -> tuple[str, str, int]:
    soup = BeautifulSoup(html, "html.parser")
    title = (soup.find("title").get_text(strip=True) if soup.find("title") else "")
    main = soup.select_one("article, #content, .contents, .board-view, .sub-contents")
    text = (main.get_text(" ", strip=True) if main else soup.get_text(" ", strip=True))
    text = re.sub(r"\s+", " ", text).strip()
    
    # ✅ 임베딩/요약용 텍스트에 이메일 레드액트(안전망)
    if redact_email:
        text = redact_email_text(text, email_replacement)

    return title, text, len(text)

# 스냅샷을 받아온 뒤 <a> 링크를 전부 추출할 때 사용
def detect_links(base_url: str, html: str) -> tuple[list[dict], list[str]]:
    soup = BeautifulSoup(html, "html.parser")
    attachments, followables = [], []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        text = (a.get_text() or "").strip()
        cls = " ".join(a.get("class", []))
        attachments.append({
            "href": href,
            "text": text,
            "class": cls,
        })
    all_hrefs = [a["href"].strip() for a in soup.find_all("a", href=True)]
    followables = [h for h in all_hrefs if not h.lower().startswith("mailto:")]
    return attachments, followables

# 첨부파일 인지 웹페이지 링크 인지 구분
def is_download_intent(href: str, abs_url: str, text: str, cls: str) -> bool:
    return (
        "download" in href.lower()
        or "/cms/fileDownload.do" in abs_url.lower()
        or "file-down-btn" in cls.lower()
        or ATTACH_EXT.search(href) is not None
        or ATTACH_EXT.search(text) is not None
    )