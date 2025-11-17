# crawler/storage/pii.py
from __future__ import annotations
import re
from bs4 import BeautifulSoup

EMAIL_RE = re.compile(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[A-Za-z]{2,}\b')

def redact_email_text(text: str, replacement: str = "[이메일 확인: 원문 참조]") -> str:
    return EMAIL_RE.sub(replacement, text)

def redact_email_html(html: str, replacement: str = "[이메일 확인: 원문 참조]", page_url: str | None = None) -> str:
    """HTML 내 이메일/메일토 링크까지 모두 치환"""
    soup = BeautifulSoup(html, "html.parser")

    # 1) mailto 링크 무력화 + 표시문구 치환
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if href.startswith("mailto:"):
            a.string = replacement
            # href를 원문으로 돌리거나 제거 (보수적으로 제거)
            a["href"] = page_url or "#"
            # 추가 정보
            a["data-redacted"] = "email"

    # 2) 텍스트 노드 내 이메일 치환
    #  - 간단히 전체 HTML을 문자열로 바꿔 치환 → 다시 파싱 안 함 (성능/안정성 목적)
    html_str = str(soup)
    html_str = EMAIL_RE.sub(replacement, html_str)
    return html_str
