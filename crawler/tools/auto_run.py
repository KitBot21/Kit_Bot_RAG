# tools/update_changed_boards.py
from __future__ import annotations
import json, re, sys, time
from dataclasses import dataclass
from typing import Literal, Iterable
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs
import requests
from bs4 import BeautifulSoup

# 프로젝트 내부 유틸/경로 사용
from infra.config import FIXTURES_DIR, ATTACH_DIR, DATA_DIR
from core.utils import html_cache_path  # (기존 프로젝트에 존재)

# ===== 타깃 정의 =====
TargetType = Literal["board", "schedule"]

@dataclass(frozen=True)
class Target:
    name: str
    url: str
    type: TargetType
    domain: str | None = None  # cross-domain(버스공지 등) 처리용

BOARD_TARGETS: list[Target] = [
    Target("학사일정", "https://www.kumoh.ac.kr/ko/schedule_reg.do", "schedule"),
    Target("통학버스 공지", "https://bus.kumoh.ac.kr/bus/notice.do", "board", domain="bus.kumoh.ac.kr"),
    Target("업무추진비", "https://www.kumoh.ac.kr/ko/sub01_02_03.do", "board"),
    Target("KIT Projects", "https://www.kumoh.ac.kr/ko/sub01_05_01.do", "board"),
    Target("보도자료", "https://www.kumoh.ac.kr/ko/sub01_05_04.do", "board"),
    Target("공지-학사안내", "https://www.kumoh.ac.kr/ko/sub06_01_01_01.do", "board"),
    Target("공지-행사안내", "https://www.kumoh.ac.kr/ko/sub06_01_01_02.do", "board"),
    Target("공지-일반소식", "https://www.kumoh.ac.kr/ko/sub06_01_01_03.do", "board"),
    Target("정보공유-금오복덕방", "https://www.kumoh.ac.kr/ko/sub06_03_04_02.do", "board"),
    Target("정보공유-아르바이트", "https://www.kumoh.ac.kr/ko/sub06_03_04_04.do", "board"),
    Target("문화예술-클래식감상", "https://www.kumoh.ac.kr/ko/sub06_03_05_01.do", "board"),
    Target("문화예술-갤러리", "https://www.kumoh.ac.kr/ko/sub06_03_05_02.do", "board"),
    Target("총장후보추천위-공지", "https://www.kumoh.ac.kr/ko/sub06_05_02.do", "board"),
    Target("생활관-공지", "https://www.kumoh.ac.kr/dorm/sub0401.do", "board"),
    Target("생활관-선발공지", "https://www.kumoh.ac.kr/dorm/sub0407.do", "board"),
    Target("생활관-입퇴사공지", "https://www.kumoh.ac.kr/dorm/sub0408.do", "board"),
    Target("신평동-신청방법", "https://www.kumoh.ac.kr/dorm/sub0603.do", "board"),
]

# ===== 상태 보관 =====
STATE_DIR = DATA_DIR / "state"
STATE_DIR.mkdir(exist_ok=True, parents=True)
STATE_PATH = STATE_DIR / "boards.json"

UA = "KITBot (CSEcapstone, contact: cdh5113@naver.com)"
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"})

# ===== 유틸 =====
def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "boards": {
            # key: target.url, value: {"latest_ids": [id,...], "etag": "...", "last_modified": "..."}
        },
        "updated_at": None,
    }

def save_state(state: dict) -> None:
    state["updated_at"] = int(time.time())
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

def get_html(url: str) -> str:
    r = SESSION.get(url, timeout=20)
    r.raise_for_status()
    return r.text

def absolutize(base: str, href: str | None) -> str | None:
    if not href:
        return None
    return urljoin(base, href)

ARTICLE_NO_RX = re.compile(r"(?:[?&])articleNo=(\d+)", re.IGNORECASE)

def extract_article_links(list_html: str, base_url: str) -> list[str]:
    """
    1) mode=view&articleNo=xxxx 링크 우선 추출
    2) 없으면 숫자 ID가 들어간 상세 링크 추정(숫자 가장 큰 순)
    3) 최후 수단: 목록 내 a[href] 상위 n개
    """
    soup = BeautifulSoup(list_html, "html.parser")

    # 1) articleNo 패턴
    links = []
    for a in soup.select("a[href]"):
        href = absolutize(base_url, a.get("href"))
        if not href:
            continue
        if "mode=view" in href and "articleNo=" in href:
            links.append(href)

    if links:
        # articleNo 내림차순 정렬
        links = sorted(links, key=lambda u: int(ARTICLE_NO_RX.search(u).group(1)), reverse=True)
        return links

    # 2) 숫자 ID 추정(경로/쿼리에서 가장 큰 숫자)
    cand = []
    for a in soup.select("a[href]"):
        href = absolutize(base_url, a.get("href"))
        if not href:
            continue
        nums = re.findall(r"\d+", href)
        if nums:
            cand.append((max(map(int, nums)), href))
    if cand:
        cand.sort(key=lambda x: x[0], reverse=True)
        return [u for _, u in cand[:20]]

    # 3) 최후 수단: 상위 n개
    fallbacks = [absolutize(base_url, a.get("href")) for a in soup.select("a[href]")[:20]]
    return [u for u in fallbacks if u]

def article_id(u: str) -> int:
    m = ARTICLE_NO_RX.search(u)
    if m:
        return int(m.group(1))
    # fallback: 링크 내 최대 숫자
    nums = re.findall(r"\d+", u)
    return int(max(nums)) if nums else 0

ATTACH_EXT = re.compile(r"\.(pdf|hwp|hwpx|docx?|pptx?|xlsx?|zip|7z|rar|jpg|jpeg|png)$", re.IGNORECASE)

def extract_attachment_links(article_html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(article_html, "html.parser")
    out = []
    for a in soup.select("a[href]"):
        href = absolutize(base_url, a.get("href"))
        if not href:
            continue
        # 첨부 파일 확장자 기반
        if ATTACH_EXT.search(urlparse(href).path):
            out.append(href)
    # 중복 제거
    seen = set()
    uniq = []
    for h in out:
        if h in seen:
            continue
        seen.add(h)
        uniq.append(h)
    return uniq

def download_to(path: Path, url: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with SESSION.get(url, timeout=60, stream=True) as r:
        r.raise_for_status()
        with path.open("wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

def save_article_html(url: str, html: str) -> Path:
    p = html_cache_path(FIXTURES_DIR, url)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(html, encoding="utf-8")
    return p

def attach_target_path(url: str) -> Path:
    u = urlparse(url)
    name = (u.path.rsplit("/", 1)[-1] or "download.bin")
    q = parse_qs(u.query)
    if "filename" in q and q["filename"]:
        name = q["filename"][0]
    return ATTACH_DIR / name

# ===== 메인 로직 =====
def process_target(t: Target, state: dict) -> dict:
    bstate = state["boards"].setdefault(t.url, {"latest_ids": []})
    latest_ids: list[int] = bstate.get("latest_ids") or []

    list_html = get_html(t.url)
    list_links = extract_article_links(list_html, t.url)
    if not list_links:
        print(f"[{t.name}] 목록에서 상세 링크를 찾지 못했습니다.")
        return {"new_count": 0, "articles": []}

    # 최신 -> 오래된 순
    ids = [article_id(u) for u in list_links]
    if not ids:
        print(f"[{t.name}] ID 추출 실패.")
        return {"new_count": 0, "articles": []}

    max_prev = max(latest_ids) if latest_ids else 0
    new_links = [u for u in list_links if article_id(u) > max_prev]

    # 너무 많은 신규가 한 번에 발견되면(초기 실행 등) 상위 30개만
    if len(new_links) > 30:
        new_links = new_links[:30]

    new_saved = []
    for au in new_links:
        try:
            ah = get_html(au)
            ap = save_article_html(au, ah)
            new_saved.append((au, ap))

            # 첨부
            atts = extract_attachment_links(ah, au)
            for att in atts:
                tp = attach_target_path(att)
                try:
                    download_to(tp, att)
                except Exception as e:
                    print(f"  [ATTACH][FAIL] {att} -> {e}")

        except Exception as e:
            print(f"  [ARTICLE][FAIL] {au} -> {e}")

    # 상태 업데이트: 최신 상위 10개 ID만 유지(상태 파일 최소화)
    merged = sorted(set(latest_ids + [article_id(u) for u in list_links[:10]]), reverse=True)[:10]
    bstate["latest_ids"] = merged

    return {"new_count": len(new_saved), "articles": new_saved}

def main() -> int:
    state = load_state()
    total_new = 0
    by_board = []

    for t in BOARD_TARGETS:
        try:
            res = process_target(t, state)
            total_new += res["new_count"]
            by_board.append((t.name, res["new_count"]))
            if res["new_count"] > 0:
                print(f"[{t.name}] 신규 {res['new_count']}건 수집")
        except Exception as e:
            print(f"[{t.name}] 에러: {e}")

    save_state(state)
    print("\n=== 요약 ===")
    for name, cnt in by_board:
        print(f"{name}: +{cnt}")
    print(f"총 신규: {total_new}")

    # 필요하면: 신규가 있을 때만 main 전체 파이프라인을 후속 실행
    # (예: 벡터DB 인덱싱 등)
    # if total_new > 0:
    #     import subprocess, sys as _sys
    #     subprocess.call([_sys.executable, "-m", "main"])

    return 0

if __name__ == "__main__":
    sys.exit(main())
