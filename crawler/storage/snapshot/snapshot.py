from __future__ import annotations
from bs4 import BeautifulSoup
from typing import Tuple
import re

MAIN_SELECTORS = [
    "article",".content-wrap"
]

def extract_title_and_main_html(html: str) -> Tuple[str, str, int]:
    soup = BeautifulSoup(html, "html.parser")

    # <title>
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    # 본문 컨테이너 탐색
    main = None
    for sel in MAIN_SELECTORS:
        main = soup.select_one(sel)
        if main:
            break
    if not main:
        main = soup.body or soup

    # 불필요 요소 제거(원하면 추가)
    for bad in main.select("nav, header, #header, .sub-top, footer, #footer, script, style, .skip, .sr-only, #lnb, .snb.lnb-wrapper"):
        bad.decompose()

    text = re.sub(r"\s+", " ", main.get_text(" ", strip=True)).strip()
    text_len = len(text)
    article_html = str(main)

    return title, article_html, text_len

def build_minimal_snapshot_html(*, base_url: str, title: str, article_html: str, fetched_at: str) -> str:
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <base href="{base_url}"/>
  <title>{title}</title>
</head>
<body>
  <div class="meta">Fetched at: {fetched_at}</div>
  {article_html}
  <hr/>
  <div class="meta">Snapshot of <a href="{base_url}">{base_url}</a></div>
</body>
</html>"""
