# tools/refresh_then_run.py
from __future__ import annotations
from pathlib import Path
from infra.config import FIXTURES_DIR
from core.utils import html_cache_path
import subprocess, sys

# === 강제 갱신 타겟 URL 목록 ===
TARGETS = [
    # # 일정
    # "https://www.kumoh.ac.kr/ko/schedule_reg.do",
    # 식당
    "https://www.kumoh.ac.kr/ko/restaurant01.do",
    "https://www.kumoh.ac.kr/ko/restaurant02.do",
    "https://www.kumoh.ac.kr/ko/restaurant04.do",
    "https://www.kumoh.ac.kr/ko/restaurant05.do",
    "https://www.kumoh.ac.kr/dorm/restaurant_menu01.do",
    "https://www.kumoh.ac.kr/dorm/restaurant_menu02.do",
    "https://www.kumoh.ac.kr/dorm/restaurant_menu03.do",
    # # 게시판 리스트
    # "https://bus.kumoh.ac.kr/bus/notice.do",
    # "https://www.kumoh.ac.kr/ko/sub01_02_03.do",
    # "https://www.kumoh.ac.kr/ko/sub01_05_01.do",
    # "https://www.kumoh.ac.kr/ko/sub01_05_04.do",
    # "https://www.kumoh.ac.kr/ko/sub06_01_01_01.do",
    # "https://www.kumoh.ac.kr/ko/sub06_01_01_02.do",
    # "https://www.kumoh.ac.kr/ko/sub06_01_01_03.do",
    # "https://www.kumoh.ac.kr/ko/sub06_03_04_02.do",
    # "https://www.kumoh.ac.kr/ko/sub06_03_04_04.do",
    # "https://www.kumoh.ac.kr/ko/sub06_03_05_01.do",
    # "https://www.kumoh.ac.kr/ko/sub06_03_05_02.do",
    # "https://www.kumoh.ac.kr/ko/sub06_05_02.do",
    # "https://www.kumoh.ac.kr/dorm/sub0401.do",
    # "https://www.kumoh.ac.kr/dorm/sub0407.do",
    # "https://www.kumoh.ac.kr/dorm/sub0408.do",
    # "https://www.kumoh.ac.kr/dorm/sub0603.do",
]

def force_refresh(urls: list[str]) -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    removed = 0
    for u in urls:
        p = html_cache_path(FIXTURES_DIR, u)
        if p.exists():
            try:
                p.unlink()
                removed += 1
                print(f"[REFRESH] removed: {p}")
            except Exception as e:
                print(f"[WARN] cannot remove {p}: {e}")
    print(f"[REFRESH] done. removed={removed}, total_targets={len(urls)}")

def run_main(cfg_path: str) -> int:
    return subprocess.call([sys.executable, "-m", "main", cfg_path])

if __name__ == "__main__":
    force_refresh(TARGETS)
    sys.exit(run_main("config_restaurant_menu.yml"))
