from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

TargetType = Literal["board", "menu", "schedule"]

@dataclass(frozen=True)
class Target:
    name: str
    url: str
    type: TargetType
    domain: str | None = None  # cross-domain 처리용(버스 공지 등)

TARGETS: list[Target] = [
    # 일정
    Target("학사일정", "https://www.kumoh.ac.kr/ko/schedule_reg.do", "schedule"),

    # 식당 메뉴
    Target("한솥1식당", "https://www.kumoh.ac.kr/ko/restaurant01.do", "menu"),
    Target("한솥2식당", "https://www.kumoh.ac.kr/ko/restaurant02.do", "menu"),
    Target("학생식당", "https://www.kumoh.ac.kr/ko/restaurant04.do", "menu"),
    Target("교직원식당", "https://www.kumoh.ac.kr/ko/restaurant05.do", "menu"),
    Target("생활관-신평1", "https://www.kumoh.ac.kr/dorm/restaurant_menu01.do", "menu"),
    Target("생활관-신평2", "https://www.kumoh.ac.kr/dorm/restaurant_menu02.do", "menu"),
    Target("생활관-상록", "https://www.kumoh.ac.kr/dorm/restaurant_menu03.do", "menu"),

    # 게시판
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
