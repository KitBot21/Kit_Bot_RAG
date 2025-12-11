#!/usr/bin/env python3
"""
demoCrawler.py

발표/시연용 데모 크롤러
- 미리 선정한 "게시글 상세 URL"만 크롤링
- 제목을 추출해서 안드로이드 서버로 전송(check_and_notify)만 수행
"""

import sys
import requests
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import logging

# 환경 변수 로드 (.env)
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

# crawler 모듈 임포트를 위한 경로 추가 (sendToServer.py 등)
sys.path.insert(0, str(Path(__file__).parent))

from crawler.sendToServer import check_and_notify

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 📝 시연에 사용할 "게시글 상세 페이지 URL"들을 여기에 넣어서 사용
DEMO_ARTICLE_URLS = [
    # 예시) 학사 공지 몇 개
    "https://www.kumoh.ac.kr/ko/sub06_01_01_01.do?mode=view&articleNo=545734&article.offset=0&articleLimit=10",
]


class DemoCrawler:
    """게시글 상세 페이지만 크롤링하는 데모 전용 크롤러"""

    def __init__(self, article_urls: list[str], dry_run: bool = False):
        """
        Args:
            article_urls: 시연에 사용할 게시글 상세 페이지 URL 목록
            dry_run: True 이면 안드로이드 서버로 전송하지 않고 로그만 출력
        """
        self.article_urls = article_urls
        self.dry_run = dry_run
        self.stats = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "sent": 0,   # 안드로이드 서버 전송 성공 수
        }

    def _extract_board_title(self, html: str) -> str | None:
        """
        금오 게시판 상세 페이지에서 제목만 추출
        (기존 SimpleTestCrawler._extract_board_title 그대로 가져옴)
        """
        soup = BeautifulSoup(html, "html.parser")
        head = soup.find("div", class_="title-area")
        if not head:
            return None

        for tag in ["h4", "h3", "strong"]:
            el = head.find(tag)
            if el:
                text = el.get_text(strip=True)
                if text:
                    return text

        return None

    def crawl_detail_page(self, url: str) -> bool:
        """
        단일 게시글 상세 페이지를 크롤링해서
        제목을 추출하고 안드로이드 서버로 전달
        """
        self.stats["total"] += 1
        logger.info(f"📄 상세 페이지 크롤링 시작: {url}")

        try:
            headers = {
                "User-Agent": "KITBot-Demo/1.0 (CSEcapstone, contact: cdh5113@naver.com)"
            }
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()

            html = resp.text
            title = self._extract_board_title(html)

            if not title:
                # fallback: <title> 태그 등에서라도 가져오기
                soup = BeautifulSoup(html, "html.parser")
                if soup.title:
                    title = soup.title.get_text(strip=True)
                else:
                    title = "(제목 추출 실패)"

            logger.info(f"   ✅ 추출된 제목: {title}")

            # 실제 시연용 전송
            if self.dry_run:
                logger.info("   [DRY-RUN] check_and_notify 호출 생략 (시연 테스트 모드)")
            else:
                try:
                    check_and_notify(
                        url=url,
                        title=title,
                    )
                    self.stats["sent"] += 1
                    logger.info("   📡 안드로이드 서버로 메타데이터 전송 완료")
                except Exception as e:
                    logger.warning(f"   ⚠️ 안드로이드 서버 전송 중 오류: {e}")

            self.stats["success"] += 1
            return True

        except requests.RequestException as e:
            logger.error(f"❌ 네트워크 에러: {e}")
            self.stats["failed"] += 1
            return False
        except Exception as e:
            logger.error(f"❌ 처리 에러: {e}")
            self.stats["failed"] += 1
            return False

    def run(self):
        """데모 크롤링 실행"""
        print("=" * 80)
        print("🎬 데모 크롤러 시작 (게시글 상세 페이지 전용)")
        print("=" * 80)
        print(f"대상 게시글 수: {len(self.article_urls)}")
        print(f"DRY-RUN 모드: {'ON (서버 전송 X)' if self.dry_run else 'OFF (실제 전송)'}")
        print("=" * 80)

        start_time = datetime.now()

        for idx, url in enumerate(self.article_urls, 1):
            print(f"\n[{idx}/{len(self.article_urls)}] {url}")
            print("-" * 80)
            self.crawl_detail_page(url)

        elapsed = datetime.now() - start_time

        print("\n" + "=" * 80)
        print("데모 크롤링 완료")
        print("=" * 80)
        print(f"총 시도:   {self.stats['total']}")
        print(f"성공:      {self.stats['success']}")
        print(f"실패:      {self.stats['failed']}")
        print(f"서버 전송: {self.stats['sent']} (dry-run 이면 항상 0)")
        print(f"\n소요 시간: {elapsed}")
        print("=" * 80)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="데모 크롤러 - 게시글 상세 페이지 전용")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="안드로이드 서버로 전송하지 않고 로그만 출력",
    )
    args = parser.parse_args()

    if not DEMO_ARTICLE_URLS:
        print("⚠️ DEMO_ARTICLE_URLS 에 시연에 사용할 게시글 URL을 먼저 채워주세요.")
        return

    crawler = DemoCrawler(article_urls=DEMO_ARTICLE_URLS, dry_run=args.dry_run)
    crawler.run()


if __name__ == "__main__":
    main()
