#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
금오공대 학사일정 <article>만 추출하여 HTML로 저장
- 대상: https://www.kumoh.ac.kr/ko/schedule_reg.do?mode=list&articleLimit=10&article.offset={0,10,20,30,40}
- 저장: data/fixtures/schedule_article/schedule_article_{offset}.html
"""

from __future__ import annotations
from pathlib import Path
import sys, time
import requests
from requests.adapters import HTTPAdapter, Retry
from bs4 import BeautifulSoup

# ===== 경로 =====
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "fixtures" / "schedule_article"

# ===== 설정 =====
BASE_URL = "https://www.kumoh.ac.kr/ko/schedule_reg.do"
UA = "KITBot (CSEcapstone, contact: cdh5113@naver.com)"

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "ko,en;q=0.8",
})
SESSION.mount("https://", HTTPAdapter(max_retries=Retry(
    total=3, backoff_factor=0.4, status_forcelist=[429,500,502,503,504]
)))

def fetch_page(offset: int) -> str:
    url = f"{BASE_URL}?mode=list&articleLimit=10&article.offset={offset}"
    r = SESSION.get(url, timeout=20)
    if not r.encoding or r.encoding.lower() in ("iso-8859-1", "latin-1"):
        r.encoding = r.apparent_encoding
    r.raise_for_status()
    return r.text

def extract_article_html(full_html: str, base_href: str) -> str | None:
    soup = BeautifulSoup(full_html, "html.parser")
    article = soup.find("article")
    if not article:
        return None

    # 최소한의 문서 래퍼 + <base>로 상대경로 유지
    doc = BeautifulSoup("", "html.parser")
    html = doc.new_tag("html", lang="ko")
    head = doc.new_tag("head")
    meta = doc.new_tag("meta", charset="utf-8")
    base = doc.new_tag("base", href=base_href)
    title = doc.new_tag("title")
    title.string = "학사일정 (article only)"

    head.append(meta)
    head.append(base)
    head.append(title)

    body = doc.new_tag("body")
    # 원본 article 그대로 삽입
    body.append(article)

    html.append(head)
    html.append(body)
    doc.append(html)

    return str(doc)

def save_article_html(article_html: str, offset: int) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"schedule_article_{offset}.html"
    path.write_text(article_html, encoding="utf-8")
    return path

def main() -> int:
    offsets = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160, 170, 180, 190, 200]
    print(f"[INFO] <article> 추출 시작 (pages={len(offsets)})")

    saved = 0
    for offset in offsets:
        try:
            html = fetch_page(offset)
            base_href = f"{BASE_URL}?mode=list&articleLimit=10&article.offset={offset}"
            article_html = extract_article_html(html, base_href)
            if not article_html:
                print(f"  - offset={offset}: article 미발견")
                continue
            p = save_article_html(article_html, offset)
            print(f"  - offset={offset}: 저장 → {p}")
            saved += 1
            time.sleep(0.6)
        except Exception as e:
            print(f"  [FAIL] offset={offset} → {e}")

    if saved == 0:
        print("[WARN] 저장된 파일이 없습니다.")
        return 1

    print(f"\n✅ 완료: {saved}개 파일 저장 → {OUT_DIR}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
