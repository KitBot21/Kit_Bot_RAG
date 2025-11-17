#!/usr/bin/env python3
"""
최적화된 크롤러
- 2021년 이후 데이터만
- JSON 저장
- 품질 필터링
- 로그인 페이지 자동 스킵
"""
import sys
from pathlib import Path
from datetime import datetime
from setting.loader import Loader
from core.crawl import Crawler as BaseCrawler
from filters.quality_filter import QualityFilter
from storage.json_storage import JSONStorage
from filters.date_filter import DateFilter
import logging

class OptimizedCrawler(BaseCrawler):
    """개선된 크롤러"""
    
    def __init__(self, settings: Loader):
        super().__init__(settings)
        
        # 품질 필터 추가
        self.quality_filter = QualityFilter(
            min_text_length=100,
            max_text_length=500000,
            min_word_count=20,
        )
        
        # JSON 저장소
        json_output_dir = Path("../data/crawled_json")
        self.json_storage = JSONStorage(json_output_dir, pretty_print=False)
        
        # 날짜 필터
        self.date_filter = DateFilter(cutoff_date="2021-01-01")
        
        # 통계
        self.stats = {
            "total_visited": 0,
            "saved": 0,
            "skipped_quality": 0,
            "skipped_login": 0,
            "skipped_date": 0,
            "errors": 0,
        }
        
        self.saved_pages_info = []  # 인덱스용
    
    def _should_skip_by_date(self, lastmod: str) -> bool:
        """날짜 기반 스킵 여부"""
        if not lastmod:
            return False  # lastmod 없으면 허용
        
        return not self.date_filter.is_recent(lastmod)
    
    def _process_page(self, url: str, html: str, lastmod: str = None):
        """페이지 처리 (필터링 + 저장)"""
        self.stats["total_visited"] += 1
        
        # 1. 날짜 필터
        if lastmod and self._should_skip_by_date(lastmod):
            self.stats["skipped_date"] += 1
            self.logger.info(f"[SKIP-DATE] {lastmod} : {url}")
            return False
        
        # 2. 로그인 페이지 감지 (기존 로직 사용)
        from core.login_detect import is_login_page_html
        if self.s.block_login_pages and is_login_page_html(html):
            self.stats["skipped_login"] += 1
            self.logger.info(f"[SKIP-LOGIN] {url}")
            return False
        
        # 3. 품질 필터
        is_quality, reason = self.quality_filter.is_high_quality(html, url)
        if not is_quality:
            self.stats["skipped_quality"] += 1
            self.logger.info(f"[SKIP-QUALITY] {reason} : {url}")
            return False
        
        # 4. JSON 저장
        try:
            metadata = self.quality_filter.extract_metadata(html)
            metadata['lastmod'] = lastmod
            metadata['quality_check'] = reason
            
            filepath = self.json_storage.save_page(url, html, metadata)
            
            self.stats["saved"] += 1
            
            # 인덱스 정보 수집
            self.saved_pages_info.append({
                "url": url,
                "file": filepath,
                "lastmod": lastmod,
                "text_length": metadata.get("text_length", 0),
                "title": metadata.get("title", ""),
            })
            
            if self.stats["saved"] % 10 == 0:
                self.logger.info(f"[SAVED] {self.stats['saved']} pages")
            
            return True
            
        except Exception as e:
            self.stats["errors"] += 1
            self.logger.error(f"[ERROR] {url}: {e}")
            return False
    
    def run(self):
        """크롤링 실행 (오버라이드)"""
        start_time = datetime.now()
        self.logger.info("="*80)
        self.logger.info(f"최적화 크롤러 시작: {start_time.isoformat()}")
        self.logger.info(f"  - 날짜 필터: 2021-01-01 이후")
        self.logger.info(f"  - 품질 필터: 최소 100자, 20단어")
        self.logger.info(f"  - 저장 형식: JSON")
        self.logger.info("="*80)
        
        # 기존 크롤링 로직 실행
        # (부모 클래스의 run() 메서드를 호출하거나, 직접 구현)
        # 여기서는 간단히 예시만 표시
        
        try:
            # 실제 크롤링 로직
            # ... (기존 Crawler의 로직 사용)
            super().run()
            
        finally:
            # 최종 통계 및 인덱스 저장
            self.logger.info("="*80)
            self.logger.info("크롤링 완료!")
            self.logger.info(f"  총 방문: {self.stats['total_visited']}")
            self.logger.info(f"  저장됨: {self.stats['saved']}")
            self.logger.info(f"  스킵(날짜): {self.stats['skipped_date']}")
            self.logger.info(f"  스킵(로그인): {self.stats['skipped_login']}")
            self.logger.info(f"  스킵(품질): {self.stats['skipped_quality']}")
            self.logger.info(f"  에러: {self.stats['errors']}")
            self.logger.info("="*80)
            
            # 인덱스 저장
            if self.saved_pages_info:
                self.json_storage.save_index(self.saved_pages_info)
                self.logger.info(f"인덱스 저장 완료: {len(self.saved_pages_info)} 페이지")
            
            elapsed = datetime.now() - start_time
            self.logger.info(f"소요 시간: {elapsed}")


def main():
    """메인 실행"""
    cfg_path = sys.argv[1] if len(sys.argv) > 1 else "config_optimized.yml"
    
    # 설정 로드
    settings = Loader.from_yaml(cfg_path)
    
    # 최적화 크롤러 실행
    crawler = OptimizedCrawler(settings)
    crawler.run()


if __name__ == "__main__":
    main()
