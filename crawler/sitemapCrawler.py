#!/usr/bin/env python3
"""
ko_sitemap_static_crawler.py

https://www.kumoh.ac.kr/ko/ko.xml 사이트맵을 돌면서
/ko 하위의 '정적 페이지' 위주로 departmentCrawler를 이용해 크롤링하는 전용 스크립트.
"""

import sys
import time
import requests
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime

# departmentCrawler 모듈 임포트 가능하도록 경로 추가
sys.path.insert(0, str(Path(__file__).parent))

from departmentCrawler import departmentCrawler, logger

ICON_IMAGE_KEYWORDS = [
    "/_res/ko/img/icon/",
    "/res/ko/img/common/",
    "logo",
    "btn",
    "btn-",
    "bg_subvisual",
    "wa-mark",
    "bubble_tail",
    "btn_top_go",
    "icon",
    "insta",       # 인스타그램
    "youtube",     # 유튜브
    "blog",        # 블로그
    "facebook",    # 페이스북
    "twitter",     # 트위터
    "kakao",       # 카카오
    "banner",      # 배너
    "footer",      # 푸터 이미지
    "header",      # 헤더 이미지
    "arrow",       # 화살표
    "line",        # 장식선
    "bg_",         # 배경 이미지
    "common",      # 공통 이미지
]

EXCLUDED_URLS = {
    "https://www.kumoh.ac.kr/ko/sub01_02_03.do",      # 업무추진비 사용내역
    "https://www.kumoh.ac.kr/ko/sub01_05_01.do",      # KIT Projects
    "https://www.kumoh.ac.kr/ko/sub01_05_04.do",      # 보도자료
    "https://www.kumoh.ac.kr/ko/sub06_01_01_01.do",   # 공지사항 학사안내
    "https://www.kumoh.ac.kr/ko/sub06_01_01_02.do",   # 공지사항 행사안내
    "https://www.kumoh.ac.kr/ko/sub06_01_01_03.do",   # 공지사항 일반소식
    "https://www.kumoh.ac.kr/ko/sub06_03_04_02.do",   # 정보공유 금오복덕방
    "https://www.kumoh.ac.kr/ko/sub06_03_04_04.do",   # 정보공유 아르바이트정보
    "https://www.kumoh.ac.kr/ko/sub06_03_05_01.do",   # 문화예술공간 클래식감상
    "https://www.kumoh.ac.kr/ko/sub06_03_05_02.do",   # 문화예술공간 갤러리
    "https://www.kumoh.ac.kr/ko/sub06_05_02.do",      # 총장임용후보자추천위원회 공지사항
    "https://www.kumoh.ac.kr/ko/sub01_01_07_02.do",   # 대학소개 현황 재정현황
    "https://www.kumoh.ac.kr/ko/sub01_01_07_03.do",   # 대학소개 현황 재정위원회 회의록
    "https://www.kumoh.ac.kr/ko/sub01_01_07_04.do",   # 대학소개 현황 대학평의원회 회의록
    "https://www.kumoh.ac.kr/ko/sub01_01_07_05.do",   # 대학소개 현황 등록금심의위원회 회의록
    "https://www.kumoh.ac.kr/ko/sub01_01_08.do",      # 대학소개 UI
    "https://www.kumoh.ac.kr/ko/sub01_04.do",         # 대학소개 규정집
    "https://www.kumoh.ac.kr/ko/sub01_05_02.do",      # KIT People
    "https://www.kumoh.ac.kr/ko/sub01_05_03.do",      # KIT News
    "https://www.kumoh.ac.kr/ko/sub07_01_02.do",      # 금오신문고 청탁금지법자료실
    "https://www.kumoh.ac.kr/ko/sub07_01_03.do",      # 금오신문고 행동강령자료실
}

def crawl_static_from_sitemap(
    crawler: departmentCrawler,
    sitemap_url: str = "http://www.kumoh.ac.kr/ko/ko.xml",
):
    """
    /ko 사이트맵을 돌면서 정적 페이지 후보만 골라 departmentCrawler.crawl_url()에 넘긴다.
    """
    logger.info(f"\n🗺  사이트맵 크롤링 시작: {sitemap_url}")

    try:
        headers = {
            'User-Agent': 'KITBot/2.0 (CSEcapstone, contact: cdh5113@naver.com)'
        }
        resp = requests.get(sitemap_url, headers=headers, timeout=15)
        resp.raise_for_status()

        root = ET.fromstring(resp.content)

        # 네임스페이스 여부 상관없이 <loc> 태그 전부 찾기
        loc_elems = root.findall(".//{*}loc")
        raw_urls = [e.text.strip() for e in loc_elems if e.text]

        logger.info(f"   사이트맵 URL 개수: {len(raw_urls)}")

        static_urls = []
        seen = set()

        for u in raw_urls:
            # 0) 스킴 정규화 (http → https)
            if u.startswith("http://"):
                u = "https://" + u[len("http://"):]
            # 혹시 다른 도메인일 수도 있으니 /ko/만 필터
            if not u.startswith("https://www.kumoh.ac.kr/ko/"):
                continue

            # 🔹 URL 정규화 (뒤에 슬래시 정리)
            normalized = u.rstrip("/")

            # 🔹 1) 명시 제외 URL이면 바로 스킵
            if normalized in EXCLUDED_URLS:
                logger.info(f"   ⏭️ 제외 URL 스킵: {normalized}")
                continue

            # 동적/게시판/검색/로그인/파일다운로드 등 제외
            if any(pat in u for pat in [
                "mode=", "articleNo=", "search", "Search",
                "login", "Login",
                "fileDownload", "fileDown", "download=",
                "board", "bbs", "reg.do",
            ]):
                continue

            # 직접 파일 링크(ppt, pdf 등) 제외
            if any(u.lower().endswith(ext) for ext in [
                ".pdf", ".hwp", ".xls", ".xlsx",
                ".ppt", ".pptx", ".zip",
            ]):
                continue

            # 앵커(#) 포함 페이지는 중복/불필요한 경우가 많으니 제외
            if "#" in u:
                continue

            # 5) 중복 제거
            if normalized in seen:
                continue
            seen.add(normalized)
            static_urls.append(normalized)

        logger.info(f"   필터 후 정적 후보 URL 수: {len(static_urls)}")

        for url in static_urls:
            page_info = {
                "url": url,
                "name": url,           # 별도 이름이 없으니 URL 자체를 name으로 사용
                "page_type": "static_intro",
            }
            print(f"\n📍 사이트맵 정적 페이지 : [{url}]")
            print("-" * 80)
            crawler.crawl_url(url, page_info)
            time.sleep(0.5)

    except Exception as e:
        logger.error(f"❌ 사이트맵 크롤링 실패: {e}")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="KO 사이트맵 기반 정적 페이지 크롤러 (departmentCrawler 재사용)"
    )
    parser.add_argument(
        "--enable-minio",
        action="store_true",
        help="첨부파일을 MinIO에 업로드 (기본값: 메타데이터만 기록)",
    )
    parser.add_argument(
        "--sitemap-url",
        default="https://www.kumoh.ac.kr/ko/ko.xml",
        help="대상 사이트맵 URL (기본: /ko/ko.xml)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="크롤링 결과(JSON)를 저장할 디렉터리 "
             "(기본: departmentCrawler의 기본값, 예: data/raw/departments)",
    )

    args = parser.parse_args()

    # departmentCrawler 재사용 (저장 위치, 인덱스 구조, 첨부 처리 모두 그대로 활용)
    from pathlib import Path
    out_dir = Path(args.output_dir) if args.output_dir else None
    crawler = departmentCrawler(enable_minio=args.enable_minio, output_dir=out_dir)

    # departmentCrawler 재사용 (저장 위치, 인덱스 구조, 첨부 처리 모두 그대로 활용)
    crawler = departmentCrawler(enable_minio=args.enable_minio)

    print("=" * 80)
    print("KO 사이트맵 정적 페이지 크롤링 시작")
    print("=" * 80)
    print(f"사이트맵: {args.sitemap_url}")
    print("=" * 80)

    start_time = datetime.now()
    crawl_static_from_sitemap(crawler, args.sitemap_url)
    elapsed = datetime.now() - start_time

    # 인덱스 저장 (departmentCrawler와 동일 포맷)
    if crawler.saved_pages:
        index_data = {
            "crawl_date": datetime.now().isoformat(),
            "total_pages": len(crawler.saved_pages),
            "pages": crawler.saved_pages,
        }
        crawler.storage.save_index(index_data)
        logger.info(f"\n📚 first 인덱스 저장 완료: {len(crawler.saved_pages)} 페이지")

    print("\n" + "=" * 80)
    print("KO 사이트맵 정적 페이지 크롤링 완료!")
    print("=" * 80)
    print(f"총 시도: {crawler.stats['total']}")
    print(f"성공: {crawler.stats['success']}")
    print(f"건너뜀 (이미 크롤링됨): {crawler.stats['skipped']}")
    print(f"실패: {crawler.stats['failed']}")
    print(f"필터됨: {crawler.stats['filtered']}")
    print(f"\n📎 첨부파일:")
    print(f"  - 발견됨: {crawler.stats['attachments_found']}개")
    if crawler.enable_minio:
        print(f"  - MinIO 업로드 성공: {crawler.stats['attachments_uploaded']}개")
    else:
        print(f"  - 메타데이터만 기록 (MinIO 비활성화)")
    print(f"\n소요 시간: {elapsed}")
    print("=" * 80)

    output_dir = crawler.output_dir
    print(f"\n📂 결과 저장 위치: {output_dir}")
    print(f"   - 페이지: {output_dir}/pages/")
    print(f"   - 인덱스: {output_dir}/crawl_index.json")

if __name__ == "__main__":
    main()
