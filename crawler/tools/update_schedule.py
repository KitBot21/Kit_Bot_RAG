# -*- coding: utf-8 -*-
# 학사일정: 로그인 필요로 상세글 접근이 막힌 경우
# 목록(게시판) 페이지에서 제목/날짜만 추출하여 저장

from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import csv, json, time, re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from infra.config import DATA_DIR  # data/ 경로 활용

UA = "KITBot (CSEcapstone, contact: cdh5113@naver.com)"
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"})

# === 타겟 정의 ===
@dataclass(frozen=True)
class ScheduleTarget:
    name: str
    url: str

SCHEDULE_TARGETS: list[ScheduleTarget] = [
    ScheduleTarget("학사일정", "https://www.kumoh.ac.kr/ko/schedule_reg.do"),
]

# === 상태 & 출력 파일 ===
STATE_DIR = DATA_DIR / "state"
STATE_DIR.mkdir(parents=True, exist_ok=True)
STATE_PATH = STATE_DIR / "schedule_list_only.json"  # 최신 항목 해시 저장

OUT_CSV = DATA_DIR / "schedules.csv"  # 누적 저장용 (제목/날짜/타겟/목록URL/수집시각)

def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"targets": {}, "updated_at": None}

def save_state(state: dict) -> None:
    state["updated_at"] = int(time.time())
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

def ensure_csv_header():
    if not OUT_CSV.exists():
        OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
        with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["target_name","title","date","list_url","fetched_at"])

def append_csv_row(target_name: str, title: str, date: str, list_url: str):
    ensure_csv_header()
    with OUT_CSV.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([target_name, title, date, list_url, time.strftime("%Y-%m-%d %H:%M:%S")])

def get_html(url: str) -> str:
    r = SESSION.get(url, timeout=20)
    r.raise_for_status()
    return r.text

def norm_text(s: Optional[str]) -> str:
    if not s:
        return ""
    s = re.sub(r"\s+", " ", s.strip())
    return s

def extract_rows_generic(list_html: str, base_url: str):
    """
    다양한 게시판 마크업에 대응:
    - table.board_list > tbody > tr
    - ul/ol .list > li
    - div.board_list 안의 항목들
    각 항목에서 (제목, 날짜) 추출 시도.
    """
    soup = BeautifulSoup(list_html, "html.parser")
    rows = []

    # 1) table 계열
    table_rows = soup.select("table tbody tr")
    for tr in table_rows:
        a = tr.select_one("a[href]")
        if not a:
            continue
        title = norm_text(a.get_text())
        # 날짜 셀 추정
        date = ""
        # 흔한 패턴: .date, .regDate, td:nth-last-child(1) 등
        cand = tr.select_one(".date, .regDate, td:last-child, td:nth-last-child(1)")
        if cand:
            date = norm_text(cand.get_text())
        rows.append((title, date))

    # 2) ul/ol 계열
    if not rows:
        for li in soup.select("ul li, ol li"):
            a = li.select_one("a[href]")
            if not a:
                continue
            title = norm_text(a.get_text())
            # 날짜 추정: li 내부의 .date, time 태그, 마지막 span 등
            date = ""
            cand = li.select_one(".date, time, span.date, em.date")
            if cand:
                date = norm_text(cand.get_text())
            else:
                # 글자 중 YYYY-MM-DD 같은 패턴이 있으면 추출
                m = re.search(r"\d{4}[-./]\d{1,2}[-./]\d{1,2}", li.get_text(" "))
                if m:
                    date = norm_text(m.group(0))
            rows.append((title, date))

    # 3) div.board_list 계열 (fallback)
    if not rows:
        for div in soup.select("div.board_list div, div.board_list li"):
            a = div.select_one("a[href]")
            if not a:
                continue
            title = norm_text(a.get_text())
            date = ""
            cand = div.select_one(".date, time, span.date, em.date")
            if cand:
                date = norm_text(cand.get_text())
            rows.append((title, date))

    # 강건성: 중복 제거
    seen = set()
    uniq = []
    for t, d in rows:
        key = (t, d)
        if key in seen:
            continue
        seen.add(key)
        # 제목이 너무 짧거나 빈 값이면 제외
        if len(t) >= 2:
            uniq.append((t, d))
    return uniq

def hash_row(title: str, date: str) -> str:
    # 간단 해시: 제목+날짜 기준(상세 진입 불가이므로 행 텍스트 자체로 판별)
    base = f"{title}||{date}".lower().strip()
    return re.sub(r"\s+", " ", base)

def process_target(t: ScheduleTarget, state: dict) -> int:
    """
    목록에서 (제목, 날짜)만 추출. 이전 상태와 비교해 새로운 항목만 CSV에 추가.
    """
    html = get_html(t.url)
    rows = extract_rows_generic(html, t.url)
    if not rows:
        print(f"[{t.name}] 목록 파싱 결과가 없습니다.")
        return 0

    tstate = state["targets"].setdefault(t.url, {"seen_hash": []})
    seen_hash: list[str] = tstate.get("seen_hash") or []

    new_cnt = 0
    batch_hashes = []
    for title, date in rows:
        h = hash_row(title, date)
        batch_hashes.append(h)
        if h in seen_hash:
            continue
        # 신규
        append_csv_row(t.name, title, date, t.url)
        new_cnt += 1

    # 상태 업데이트: 최근 200개 정도만 유지
    merged = list(dict.fromkeys(batch_hashes + seen_hash))[:200]
    tstate["seen_hash"] = merged
    return new_cnt

def main() -> int:
    state = load_state()
    total_new = 0
    for t in SCHEDULE_TARGETS:
        try:
            n = process_target(t, state)
            total_new += n
            if n > 0:
                print(f"[{t.name}] 신규 {n}건 저장")
        except Exception as e:
            print(f"[{t.name}] 에러: {e}")

    save_state(state)
    print(f"총 신규: {total_new}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
