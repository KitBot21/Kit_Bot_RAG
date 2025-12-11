#!/usr/bin/env python3
"""
테스트 크롤러 - 2개 섹션만
1. 일정: /ko/schedule_reg.do
2. 공지사항(학사안내): /ko/sub06_01_01_01.do
"""
import sys
import requests
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

# crawler 모듈 임포트를 위한 경로 추가
sys.path.insert(0, str(Path(__file__).parent))

from filters.content_extractor import ContentExtractor
from filters.quality_filter import QualityFilter
from filters.date_filter import DateFilter
from storage.json_storage import JSONStorage
from storage.minio_storage import MinIOStorage
import logging
import hashlib

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SimpleTestCrawler:
    """간단한 테스트 크롤러"""
    
    def __init__(self, enable_minio: bool = False):
        """
        Args:
            enable_minio: MinIO 사용 여부 (True면 첨부파일을 MinIO에 업로드)
        """
        self.base_url = "https://www.kumoh.ac.kr"
        self.bus_base_url = "https://bus.kumoh.ac.kr"
        
        # MinIO 설정
        self.enable_minio = enable_minio
        if enable_minio:
            try:
                self.minio = MinIOStorage.from_env()
                logger.info("✅ MinIO 스토리지 초기화 완료")
            except Exception as e:
                logger.warning(f"⚠️  MinIO 초기화 실패: {e}")
                logger.warning("   첨부파일은 메타데이터만 기록됩니다.")
                self.enable_minio = False
                self.minio = None
        else:
            self.minio = None
        
        # 크롤링할 URL 목록
        self.target_urls = [
            # 학사일정
            "https://www.kumoh.ac.kr/ko/schedule_reg.do",
            # 교내 식당
            "https://www.kumoh.ac.kr/ko/restaurant01.do",
            "https://www.kumoh.ac.kr/ko/restaurant02.do",
            "https://www.kumoh.ac.kr/ko/restaurant04.do",
            "https://www.kumoh.ac.kr/ko/restaurant05.do",
            # 생활관 식당
            "https://www.kumoh.ac.kr/dorm/restaurant_menu01.do",
            "https://www.kumoh.ac.kr/dorm/restaurant_menu02.do",
            "https://www.kumoh.ac.kr/dorm/restaurant_menu03.do",
        ]
        
        # 게시판 URL (리스트 페이지 - 여러 게시글 크롤링)
        self.board_urls = [
            {
                "url": "https://bus.kumoh.ac.kr/bus/notice.do",
                "name": "통학버스 공지",
                "max_pages": 0,  # 0 = 전체 페이지 크롤링
                "skip_date_filter": False,  # 날짜 필터 적용 (2021-01-01 이후만)
            },
        ]
        
        # 필터 및 저장소 초기화
        self.quality_filter = QualityFilter(
            min_text_length=100,
            max_text_length=500000,
            min_word_count=20
        )
        
        # 날짜 필터 (2021-01-01 이후만)
        self.date_filter = DateFilter(cutoff_date="2021-01-01")
        
        output_dir = Path(__file__).parent.parent / "data" / "test_crawled"
        self.storage = JSONStorage(output_dir, pretty_print=True)
        
        self.content_extractor = ContentExtractor(keep_links=True, keep_images=False)
        
        # 통계
        self.stats = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "filtered": 0,
            "filtered_date": 0,  # 날짜 필터로 제외된 수
            "skipped": 0,  # 이미 크롤링된 페이지
            "attachments_found": 0,  # 발견된 첨부파일
            "attachments_uploaded": 0,  # MinIO 업로드 성공
        }
        
        self.saved_pages = []
        
        # 기존 크롤링 데이터 로드
        self.existing_urls = set()
        self.index_meta = {}  # 메타 정보 초기화
        self._load_existing_index()
    
    def _load_existing_index(self):
        """기존 크롤링 인덱스를 로드하여 중복 체크"""
        index_file = Path(__file__).parent.parent / "data" / "test_crawled" / "crawl_index.json"
        if index_file.exists():
            try:
                import json
                with open(index_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for page in data.get('pages', []):
                        self.existing_urls.add(page['url'])
                        # 기존 페이지를 saved_pages에도 추가
                        self.saved_pages.append(page)
                    
                    # 메타 정보 저장 (첫 항목, 크롤링 날짜 등)
                    self.index_meta = data.get('meta', {})
                    
                logger.info(f"✅ 기존 크롤링 데이터 로드: {len(self.existing_urls)}개 URL")
            except Exception as e:
                logger.warning(f"⚠️  기존 인덱스 로드 실패: {e}")
        
        # 기존 크롤링 데이터 로드 (중복 방지)
        self.existing_urls = set()
        self._load_existing_index()
    
    def _load_existing_index(self):
        """기존 인덱스 파일을 읽어서 이미 크롤링한 URL 목록을 가져옵니다"""
        output_dir = Path(__file__).parent.parent / "data" / "test_crawled"
        index_file = output_dir / "crawl_index.json"
        
        if index_file.exists():
            try:
                import json
                with open(index_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for page in data.get('pages', []):
                        self.existing_urls.add(page['url'])
                        # 기존 페이지도 saved_pages에 추가
                        self.saved_pages.append(page)
                logger.info(f"📂 기존 크롤링 데이터 로드: {len(self.existing_urls)}개 URL")
            except Exception as e:
                logger.warning(f"기존 인덱스 로드 실패: {e}")
    
    def crawl_url(self, url: str, skip_date_filter: bool = False) -> bool:
        """
        단일 URL 크롤링
        
        Args:
            url: 크롤링할 URL
            skip_date_filter: True면 날짜 필터 건너뛰기 (학사일정 등)
        """
        self.stats["total"] += 1
        
        logger.info(f"크롤링 시작: {url}")
        
        try:
            # 페이지 가져오기
            headers = {
                'User-Agent': 'KITBot/2.0 (CSEcapstone, contact: cdh5113@naver.com)'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            html = response.text
            
            # 날짜 필터 (학사일정은 스킵)
            if not skip_date_filter:
                # 날짜 추출 (게시글의 작성일 또는 수정일)
                date_str = self._extract_date_from_html(html)
                
                # 날짜 필터 체크 (2021-01-01 이후만)
                if date_str and not self.date_filter.is_recent(date_str):
                    logger.info(f"  ⏭️  날짜 필터: {date_str} (2021-01-01 이전)")
                    self.stats["filtered"] += 1
                    self.stats["filtered_date"] += 1
                    return False
            
            # 품질 검사
            is_quality, reason = self.quality_filter.is_high_quality(html, url)
            if not is_quality:
                logger.warning(f"품질 필터 실패: {reason}")
                self.stats["filtered"] += 1
                return False
            
            # 본문 추출
            content_data = self.content_extractor.extract_with_metadata(html)
            
            # 첨부파일 추출 및 처리
            attachments = self._process_attachments(url, html)
            
            # 메타데이터 준비
            metadata = {
                "text_length": len(content_data['text']),
                "word_count": content_data['word_count'],
                "title": content_data['title'],
                "paragraphs": content_data['paragraphs'],
                "link_count": len(content_data['links']),
                "attachments_count": len(attachments),  # 첨부파일 개수
                "attachments": attachments,  # 첨부파일 정보
                "quality_check": reason,
                "crawled_at": datetime.now().isoformat(),
            }
            
            # 저장
            filepath = self.storage.save_page(url, html, metadata)
            
            self.saved_pages.append({
                "url": url,
                "file": filepath,
                "title": content_data['title'],
                "text_length": len(content_data['text']),
            })
            
            self.stats["success"] += 1
            
            logger.info(f"✅ 저장 완료: {Path(filepath).name}")
            logger.info(f"   제목: {content_data['title'][:50]}...")
            logger.info(f"   본문 길이: {len(content_data['text'])} 문자")
            logger.info(f"   문단 수: {content_data['paragraphs']}")
            
            return True
            
        except requests.RequestException as e:
            logger.error(f"❌ 네트워크 에러: {e}")
            self.stats["failed"] += 1
            return False
        
        except Exception as e:
            logger.error(f"❌ 처리 에러: {e}")
            self.stats["failed"] += 1
            return False
    
    def _process_attachments(self, page_url: str, html: str) -> list:
        """
        HTML에서 첨부파일 링크를 추출하고 MinIO에 업로드
        
        Args:
            page_url: 현재 페이지 URL
            html: HTML 소스
            
        Returns:
            첨부파일 정보 리스트
        """
        attachments = []
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # 첨부파일 링크 찾기 (mode=download, .hwp, .pdf 등)
            for link in soup.find_all('a', href=True):
                href = link['href']
                link_text = link.get_text(strip=True)
                
                # 다운로드 패턴 확인
                is_download = (
                    'mode=download' in href or
                    'download' in href.lower() or
                    any(href.lower().endswith(ext) for ext in ['.pdf', '.hwp', '.docx', '.xlsx', '.pptx', '.zip'])
                )
                
                if not is_download:
                    continue
                
                # 절대 URL로 변환
                if href.startswith('?'):
                    abs_url = page_url.split('?')[0] + href
                elif href.startswith('/'):
                    # 도메인 결정
                    if 'bus.kumoh.ac.kr' in page_url:
                        abs_url = f"{self.bus_base_url}{href}"
                    else:
                        abs_url = f"{self.base_url}{href}"
                elif not href.startswith('http'):
                    abs_url = f"{page_url.rsplit('/', 1)[0]}/{href}"
                else:
                    abs_url = href
                
                self.stats["attachments_found"] += 1
                
                # 첨부파일 정보 기록
                attachment_info = {
                    "page_url": page_url,
                    "link_text": link_text,
                    "download_url": abs_url,
                    "detected_at": datetime.now().isoformat(),
                }
                
                # MinIO 업로드 시도
                if self.enable_minio and self.minio:
                    try:
                        # 파일 다운로드
                        headers = {
                            'User-Agent': 'KITBot/2.0 (CSEcapstone, contact: cdh5113@naver.com)',
                            'Referer': page_url
                        }
                        response = requests.get(abs_url, headers=headers, timeout=30)
                        response.raise_for_status()
                        
                        file_data = response.content
                        content_type = response.headers.get('Content-Type', 'application/octet-stream')
                        
                        # 파일명 추출
                        content_disp = response.headers.get('Content-Disposition', '')
                        if 'filename=' in content_disp:
                            filename = content_disp.split('filename=')[-1].strip('"\'')
                        else:
                            # URL에서 파일명 추출
                            filename = abs_url.split('/')[-1].split('?')[0]
                            if not filename or '.' not in filename:
                                # 링크 텍스트에서 확장자 추출 시도
                                if link_text and '.' in link_text:
                                    filename = link_text
                                else:
                                    filename = f"attachment_{hashlib.md5(abs_url.encode()).hexdigest()[:8]}.bin"
                        
                        # MinIO 객체 이름 생성 (한글 파일명 사용)
                        file_hash = hashlib.sha256(file_data).hexdigest()[:16]
                        
                        # URL 디코딩 (인코딩된 파일명이 있으면 복원)
                        import urllib.parse
                        try:
                            filename = urllib.parse.unquote(filename)
                        except:
                            pass
                        
                        # 파일명 정리 (경로 구분자만 제거)
                        clean_filename = filename.replace('/', '_').replace('\\', '_')
                        
                        # 중복 방지: 같은 이름이 있으면 해시 추가
                        object_name = f"attachments/{clean_filename}"
                        
                        # 파일 존재 여부 확인 후 중복이면 해시 추가
                        if self.minio.file_exists(object_name):
                            # 확장자 분리
                            if '.' in clean_filename:
                                name_part, ext = clean_filename.rsplit('.', 1)
                                object_name = f"attachments/{name_part}_{file_hash[:8]}.{ext}"
                            else:
                                object_name = f"attachments/{clean_filename}_{file_hash[:8]}"
                        
                        # 이미 업로드된 파일인지 확인 (해시로)
                        # MinIO에 업로드 (original_filename 추가)
                        success, result = self.minio.upload_file(
                            file_data=file_data,
                            object_name=object_name,
                            content_type=content_type,
                            original_filename=filename,
                            metadata={
                                "source_url": abs_url,
                                "page_url": page_url,
                                "link_text": link_text
                            }
                        )
                        
                        if success:
                            attachment_info["minio_url"] = result
                            attachment_info["minio_object"] = object_name
                            attachment_info["file_size"] = len(file_data)
                            attachment_info["sha256"] = file_hash
                            attachment_info["filename"] = clean_filename
                            attachment_info["status"] = "uploaded"
                            self.stats["attachments_uploaded"] += 1
                            logger.info(f"   📎 첨부파일 업로드: {clean_filename} ({len(file_data):,} bytes)")
                        else:
                            attachment_info["status"] = "upload_failed"
                            attachment_info["error"] = result
                            logger.warning(f"   ⚠️  첨부파일 업로드 실패: {filename}")
                                            except Exception as e:
                        attachment_info["status"] = "download_failed"
                        attachment_info["error"] = str(e)
                        logger.warning(f"   ⚠️  첨부파일 다운로드 실패: {link_text} - {e}")
                else:
                    attachment_info["status"] = "metadata_only"
                
                attachments.append(attachment_info)
        
        except Exception as e:
            logger.error(f"❌ 첨부파일 처리 에러: {e}")
        
        return attachments
    
    def _extract_date_from_html(self, html: str) -> str:
        """
        HTML에서 날짜 추출
        게시글의 작성일, 수정일 등을 찾습니다.
        
        Returns:
            날짜 문자열 (YYYY-MM-DD 형식) 또는 None
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        # 패턴 1: <dd> 태그에서 날짜 찾기 (금오공대 게시판 패턴)
        for dd in soup.find_all('dd'):
            text = dd.get_text(strip=True)
            # YYYY.MM.DD 또는 YYYY-MM-DD 형식
            import re
            date_match = re.search(r'(\d{4})[.-](\d{2})[.-](\d{2})', text)
            if date_match:
                year, month, day = date_match.groups()
                return f"{year}-{month}-{day}"
        
        # 패턴 2: class나 id에 'date' 포함된 요소
        for elem in soup.find_all(class_=re.compile('date|time', re.I)):
            text = elem.get_text(strip=True)
            date_match = re.search(r'(\d{4})[.-](\d{2})[.-](\d{2})', text)
            if date_match:
                year, month, day = date_match.groups()
                return f"{year}-{month}-{day}"
        
        # 패턴 3: meta 태그
        for meta in soup.find_all('meta'):
            if meta.get('property') in ['article:published_time', 'article:modified_time']:
                content = meta.get('content', '')
                date_match = re.search(r'(\d{4})[.-](\d{2})[.-](\d{2})', content)
                if date_match:
                    year, month, day = date_match.groups()
                    return f"{year}-{month}-{day}"
        
        return None
    
    def crawl_list_page(self, url: str, max_pages: int = 10, skip_date_filter: bool = False, board_name: str = "게시판"):
        """
        리스트 페이지 크롤링 (게시판 목록)
        
        Args:
            url: 게시판 목록 URL
            max_pages: 크롤링할 최대 페이지 수 (0 = 모든 페이지)
            skip_date_filter: True면 날짜 필터 건너뛰기
            board_name: 게시판 이름 (로그 출력용)
        """
        logger.info(f"\n📋 [{board_name}] 리스트 페이지 분석: {url}")
        
        page_num = 0
        total_articles = 0
        
        # base_url 결정 (통학버스는 다른 도메인)
        if 'bus.kumoh.ac.kr' in url:
            base_url = self.bus_base_url
        else:
            base_url = self.base_url
        
        while True:
            # 페이지 번호에 따른 URL 생성
            if page_num == 0:
                page_url = url
            else:
                # 페이지네이션 URL 패턴 (금오공대는 article.offset 사용)
                offset = page_num * 10  # 한 페이지에 10개씩
                if '?' in url:
                    page_url = f"{url}&article.offset={offset}"
                else:
                    page_url = f"{url}?article.offset={offset}"
            
            try:
                headers = {
                    'User-Agent': 'KITBot/2.0 (CSEcapstone, contact: cdh5113@naver.com)'
                }
                response = requests.get(page_url, headers=headers, timeout=10)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 게시글 링크 찾기
                article_links = []
                
                # 패턴: mode=view 포함
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    if 'mode=view' in href or 'articleNo' in href:
                        # 상대 경로를 절대 경로로 변환
                        if href.startswith('/'):
                            full_url = f"{base_url}{href}"
                        elif href.startswith('?'):
                            full_url = f"{url.split('?')[0]}{href}"
                        elif not href.startswith('http'):
                            # 도메인에 따라 기본 경로 다르게 설정
                            if 'bus.kumoh.ac.kr' in url:
                                full_url = f"{base_url}/bus/{href}"
                            else:
                                full_url = f"{base_url}/ko/{href}"
                        else:
                            full_url = href
                        
                        if full_url not in article_links:
                            article_links.append(full_url)
                
                if not article_links:
                    logger.info(f"   페이지 {page_num + 1}: 게시글 없음 - 종료")
                    break
                
                logger.info(f"   페이지 {page_num + 1}: {len(article_links)}개 게시글 발견")
                
                # 각 게시글 크롤링
                for i, article_url in enumerate(article_links, 1):
                    # 이미 크롤링한 URL인지 확인
                    if article_url in self.existing_urls:
                        logger.info(f"\n   [{total_articles + i}] 이미 크롤링됨 - 건너뜀: {article_url[:60]}...")
                        self.stats["skipped"] += 1
                        continue
                    
                    logger.info(f"\n   [{total_articles + i}] {article_url[:80]}...")
                    success = self.crawl_url(article_url, skip_date_filter=skip_date_filter)
                    
                    # 크롤링 성공 시 existing_urls에 추가
                    if success:
                        self.existing_urls.add(article_url)
                    
                    # 서버 부하 방지
                    import time
                    time.sleep(0.7)
                
                total_articles += len(article_links)
                page_num += 1
                
                # 최대 페이지 수 체크
                if max_pages > 0 and page_num >= max_pages:
                    logger.info(f"\n   최대 페이지 수({max_pages}) 도달 - 종료")
                    break
                
                # 다음 페이지로
                import time
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"❌ 페이지 {page_num + 1} 에러: {e}")
                break
        
        logger.info(f"\n✅ [{board_name}] 총 {total_articles}개 게시글 크롤링 완료")
    
    def crawl_schedule_lists(self, url: str, max_pages: int = 0):
        """
        학사일정 리스트 페이지들을 크롤링
        각 페이지의 일정 목록을 별도 파일로 저장
        
        Args:
            url: 학사일정 메인 URL
            max_pages: 크롤링할 최대 페이지 수 (0 = 모든 페이지)
        """
        logger.info(f"\n📋 학사일정 리스트 크롤링: {url}")
        
        page_num = 0
        
        while True:
            # 페이지 번호에 따른 URL 생성
            if page_num == 0:
                page_url = url
            else:
                # 페이지네이션 URL 패턴
                offset = page_num * 10  # 한 페이지에 10개씩
                if '?' in url:
                    page_url = f"{url}&article.offset={offset}"
                else:
                    page_url = f"{url}?article.offset={offset}"
            
            try:
                headers = {
                    'User-Agent': 'KITBot/2.0 (CSEcapstone, contact: cdh5113@naver.com)'
                }
                
                # 중복 체크
                if page_url in self.existing_urls:
                    logger.info(f"   페이지 {page_num + 1}: 이미 크롤링됨 - 건너뜀")
                    self.stats["skipped"] += 1
                    page_num += 1
                    continue
                
                response = requests.get(page_url, headers=headers, timeout=10)
                response.raise_for_status()
                
                html = response.text
                soup = BeautifulSoup(html, 'html.parser')
                
                # 학사일정 테이블이 있는지 확인
                # tbody 안에 tr이 있는지 체크
                table_rows = soup.find_all('tr')
                schedule_rows = []
                
                for row in table_rows:
                    # 학사일정 데이터 행인지 확인 (td가 있고 날짜 형식 포함)
                    tds = row.find_all('td')
                    if len(tds) >= 5:  # 번호, 제목, 시작일, 종료일, 등록일 등
                        schedule_rows.append(row)
                
                # 첫 페이지인 경우 최신 항목 체크 (효율적 중복 감지)
                if page_num == 0:
                    # 첫 항목 정보 추출
                    first_schedule = None
                    if schedule_rows:
                        first_row = schedule_rows[0]
                        cells = first_row.find_all('td')
                        if len(cells) >= 2:
                            # 번호, 제목, 시작일 등을 조합
                            first_schedule = "|".join([cell.get_text(strip=True) for cell in cells[:3]])
                    
                    # 이전 첫 항목과 비교
                    prev_first = self.index_meta.get('schedule_first_item')
                    if prev_first and first_schedule and prev_first == first_schedule:
                        logger.info(f"   ✅ 최신 일정 변경 없음 - 전체 스킵")
                        break
                    elif first_schedule:
                        logger.info(f"   🆕 새로운 일정 감지 - 전체 재크롤링")
                        # 메타 정보 업데이트
                        self.index_meta['schedule_first_item'] = first_schedule
                        self.index_meta['schedule_last_update'] = datetime.now().isoformat()
                
                if not schedule_rows:
                    logger.info(f"   페이지 {page_num + 1}: 일정 없음 - 종료")
                    break
                
                logger.info(f"   페이지 {page_num + 1}: {len(schedule_rows)}개 일정 발견")
                
                # 이 페이지 전체를 저장
                self.stats["total"] += 1
                
                # 품질 검사
                is_quality, reason = self.quality_filter.is_high_quality(html, page_url)
                if not is_quality:
                    logger.warning(f"   품질 필터 실패: {reason}")
                    self.stats["filtered"] += 1
                    page_num += 1
                    continue
                
                # 본문 추출
                content_data = self.content_extractor.extract_with_metadata(html)
                
                # 메타데이터 준비
                metadata = {
                    "text_length": len(content_data['text']),
                    "word_count": content_data['word_count'],
                    "title": f"{content_data['title']} - 페이지 {page_num + 1}",
                    "paragraphs": content_data['paragraphs'],
                    "page_number": page_num + 1,
                    "schedule_count": len(schedule_rows),
                    "type": "schedule_list",
                    "quality_check": reason,
                    "crawled_at": datetime.now().isoformat(),
                }
                
                # 저장
                filepath = self.storage.save_page(page_url, html, metadata)
                
                self.saved_pages.append({
                    "url": page_url,
                    "file": filepath,
                    "title": metadata['title'],
                    "text_length": len(content_data['text']),
                    "page_number": page_num + 1,
                    "schedule_count": len(schedule_rows),
                })
                
                self.stats["success"] += 1
                
                logger.info(f"   ✅ 저장 완료: {Path(filepath).name}")
                logger.info(f"      일정 개수: {len(schedule_rows)}")
                logger.info(f"      본문 길이: {len(content_data['text'])} 문자")
                
                page_num += 1
                
                # 최대 페이지 수 체크
                if max_pages > 0 and page_num >= max_pages:
                    logger.info(f"\n   최대 페이지 수({max_pages}) 도달 - 종료")
                    break
                
                # 다음 페이지로
                import time
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"❌ 페이지 {page_num + 1} 에러: {e}")
                break
        
        logger.info(f"\n✅ 총 {page_num}개 리스트 페이지 크롤링 완료")
    
    def crawl_restaurant_lists(self, url: str, max_pages: int = 1):
        """
        식당 메뉴 리스트 페이지들을 크롤링
        첫 페이지에만 메뉴 테이블이 있으므로 첫 페이지만 크롤링
        
        Args:
            url: 식당 메뉴 페이지 URL
            max_pages: 크롤링할 최대 페이지 수 (기본값: 1, 첫 페이지만)
        """
        logger.info(f"\n🍽️ 식당 메뉴 리스트 크롤링: {url}")
        
        page_num = 0
        
        # 첫 페이지만 크롤링 (메뉴 테이블이 첫 페이지에만 있음)
        while page_num < max_pages:
            page_url = url
            
            # 중복 체크
            if page_url in self.existing_urls:
                # 식당 메뉴는 날짜 기반으로도 체크 (매일 업데이트)
                restaurant_key = url.split('/')[-1]  # restaurant01.do 등
                last_crawl = self.index_meta.get(f'{restaurant_key}_last_crawl')
                
                if last_crawl:
                    last_date = datetime.fromisoformat(last_crawl).date()
                    today = datetime.now().date()
                    
                    if last_date >= today:
                        logger.info(f"   이미 오늘 크롤링됨 - 건너뜀")
                        self.stats["skipped"] += 1
                        break
                    else:
                        logger.info(f"   🆕 날짜 변경 감지 ({last_date} → {today}) - 재크롤링")
                        # 기존 URL 제거하고 재크롤링
                        self.existing_urls.discard(page_url)
                else:
                    logger.info(f"   이미 크롤링됨 - 건너뜀")
                    self.stats["skipped"] += 1
                    break
            
            try:
                headers = {
                    'User-Agent': 'KITBot/2.0 (CSEcapstone, contact: cdh5113@naver.com)'
                }
                response = requests.get(page_url, headers=headers, timeout=10)
                response.raise_for_status()
                
                html = response.text
                soup = BeautifulSoup(html, 'html.parser')
                
                # 메뉴 테이블이 있는지 확인
                table_rows = soup.find_all('tr')
                menu_rows = []
                
                for row in table_rows:
                    # 메뉴 데이터 행인지 확인
                    tds = row.find_all('td')
                    if len(tds) >= 3:  # 날짜, 메뉴 정보 등
                        menu_rows.append(row)
                
                # 메뉴가 없으면 종료 (단, 첫 페이지는 항상 저장)
                if not menu_rows and page_num > 0:
                    logger.info(f"   페이지 {page_num + 1}: 메뉴 없음 - 종료")
                    break
                
                logger.info(f"   페이지 {page_num + 1}: {len(menu_rows)}개 메뉴 발견")
                
                # 이 페이지 전체를 저장
                self.stats["total"] += 1
                
                # 품질 검사 (첫 페이지는 메뉴가 적어도 저장)
                is_quality, reason = self.quality_filter.is_high_quality(html, page_url)
                if not is_quality and page_num > 0:
                    logger.warning(f"   품질 필터 실패: {reason}")
                    self.stats["filtered"] += 1
                    page_num += 1
                    continue
                elif not is_quality and page_num == 0:
                    logger.warning(f"   품질 필터 경고: {reason} (첫 페이지이므로 저장)")
                    reason = "First page - saved anyway"
                
                # 본문 추출
                content_data = self.content_extractor.extract_with_metadata(html)
                
                # 식당 메뉴 테이블 추출 (특별 처리)
                menu_text = self._extract_menu_table(soup)
                if menu_text:
                    # 메뉴 테이블이 있으면 본문에 추가
                    content_data['text'] = menu_text + "\n\n" + content_data['text']
                
                # URL에서 식당 이름 추출
                restaurant_name = "식당"
                if 'restaurant01' in url:
                    restaurant_name = "학생식당"
                elif 'restaurant02' in url:
                    restaurant_name = "교직원식당"
                elif 'restaurant04' in url:
                    restaurant_name = "분식당"
                elif 'restaurant05' in url:
                    restaurant_name = "신평캠퍼스식당"
                elif 'restaurant_menu01' in url:
                    restaurant_name = "푸름관"
                elif 'restaurant_menu02' in url:
                    restaurant_name = "오름관1동"
                elif 'restaurant_menu03' in url:
                    restaurant_name = "오름관2동"
                
                # 메타데이터 준비
                metadata = {
                    "text_length": len(content_data['text']),
                    "word_count": content_data['word_count'],
                    "title": f"{restaurant_name} - 페이지 {page_num + 1}",
                    "paragraphs": content_data['paragraphs'],
                    "page_number": page_num + 1,
                    "menu_count": len(menu_rows),
                    "restaurant_name": restaurant_name,
                    "type": "restaurant_menu",
                    "quality_check": reason,
                    "crawled_at": datetime.now().isoformat(),
                }
                
                # 저장 (추출된 텍스트 전달)
                filepath = self.storage.save_page(
                    page_url, 
                    html, 
                    metadata,
                    extracted_text=content_data['text'],  # 메뉴 포함된 텍스트
                    title=metadata['title']
                )
                
                self.saved_pages.append({
                    "url": page_url,
                    "file": filepath,
                    "title": metadata['title'],
                    "text_length": len(content_data['text']),
                    "page_number": page_num + 1,
                    "menu_count": len(menu_rows),
                    "restaurant_name": restaurant_name,
                })
                
                self.stats["success"] += 1
                
                logger.info(f"   ✅ 저장 완료: {Path(filepath).name}")
                logger.info(f"      식당: {restaurant_name}")
                logger.info(f"      메뉴 개수: {len(menu_rows)}")
                logger.info(f"      본문 길이: {len(content_data['text'])} 문자")
                
                # 메타 정보 업데이트 (크롤링 날짜 저장)
                restaurant_key = url.split('/')[-1]  # restaurant01.do 등
                self.index_meta[f'{restaurant_key}_last_crawl'] = datetime.now().isoformat()
                
                # 첫 페이지만 크롤링하므로 종료
                break
                
            except Exception as e:
                logger.error(f"❌ 에러: {e}")
                break
        
        logger.info(f"\n✅ 식당 메뉴 크롤링 완료")
    
    def _extract_menu_table(self, soup: BeautifulSoup) -> str:
        """
        식당 메뉴 테이블을 텍스트로 변환
        
        Args:
            soup: BeautifulSoup 객체
            
        Returns:
            테이블을 텍스트로 변환한 문자열
        """
        tables = soup.find_all('table')
        if not tables:
            return ""
        
        menu_lines = []
        
        for table in tables:
            rows = table.find_all('tr')
            
            for row in rows:
                # th와 td 모두 추출
                cells = row.find_all(['th', 'td'])
                if not cells:
                    continue
                
                # 셀 내용 추출
                cell_texts = []
                for cell in cells:
                    text = cell.get_text(strip=True)
                    if text:
                        cell_texts.append(text)
                
                if cell_texts:
                    # 첫 번째 행은 헤더로 처리
                    if row.find('th'):
                        menu_lines.append("[ " + " | ".join(cell_texts) + " ]")
                    else:
                        menu_lines.append(" | ".join(cell_texts))
        
        return "\n".join(menu_lines) if menu_lines else ""
    
    def run(self):
        """크롤링 실행"""
        print("="*80)
        print("테스트 크롤러 시작")
        print("="*80)
        print(f"대상 섹션:")
        print(f"  1. 학사일정 (schedule_reg.do)")
        print(f"  2. 교내 식당 (restaurant01~05.do)")
        print(f"  3. 생활관 식당 (dorm/restaurant_menu01~03.do)")
        print(f"  4. 통학버스 공지 게시판 (bus.kumoh.ac.kr)")
        print("="*80)
        
        start_time = datetime.now()
        
        # 1. 단일 페이지 URL 크롤링 (학사일정, 식당 메뉴)
        for url in self.target_urls:
            print(f"\n📍 대상 URL: {url}")
            print("-"*80)
            
            # 학사일정 페이지는 날짜 필터 스킵
            skip_date = 'schedule_reg' in url
            
            # 학사일정과 식당 메뉴는 모든 페이지의 리스트를 크롤링
            if 'schedule_reg' in url:
                logger.info("\n   📋 학사일정 - 모든 페이지 리스트 크롤링 시작")
                self.crawl_schedule_lists(url)
            elif 'restaurant' in url:
                logger.info("\n   🍽️ 식당 메뉴 - 모든 페이지 리스트 크롤링 시작")
                self.crawl_restaurant_lists(url)
            
            import time
            time.sleep(1)
        
        # 2. 게시판 URL 크롤링 (통학버스 공지 등)
        for board in self.board_urls:
            url = board["url"]
            name = board["name"]
            max_pages = board.get("max_pages", 5)
            skip_date_filter = board.get("skip_date_filter", False)
            
            print(f"\n📍 게시판: {name}")
            print(f"   URL: {url}")
            print(f"   최대 페이지: {max_pages}")
            print("-"*80)
            
            logger.info(f"\n   📋 [{name}] 게시판 크롤링 시작")
            self.crawl_list_page(
                url, 
                max_pages=max_pages, 
                skip_date_filter=skip_date_filter,
                board_name=name
            )
            
            import time
            time.sleep(1)
        
        # 인덱스 저장
        if self.saved_pages:
            # 메타 정보 포함해서 저장
            index_data = {
                "crawl_date": datetime.now().isoformat(),
                "total_pages": len(self.saved_pages),
                "meta": self.index_meta,  # 첫 항목, 크롤링 날짜 등
                "pages": self.saved_pages
            }
            self.storage.save_index(index_data)
            logger.info(f"\n📚 인덱스 저장 완료: {len(self.saved_pages)} 페이지")
        
        # 최종 통계
        elapsed = datetime.now() - start_time
        
        print("\n" + "="*80)
        print("크롤링 완료!")
        print("="*80)
        print(f"총 시도: {self.stats['total']}")
        print(f"성공: {self.stats['success']}")
        print(f"건너뜀 (이미 크롤링됨): {self.stats['skipped']}")
        print(f"실패: {self.stats['failed']}")
        print(f"필터됨: {self.stats['filtered']}")
        print(f"  - 날짜 필터(2021 이전): {self.stats['filtered_date']}")
        print(f"  - 품질 필터: {self.stats['filtered'] - self.stats['filtered_date']}")
        print(f"\n📎 첨부파일:")
        print(f"  - 발견됨: {self.stats['attachments_found']}개")
        if self.enable_minio:
            print(f"  - MinIO 업로드 성공: {self.stats['attachments_uploaded']}개")
        else:
            print(f"  - 메타데이터만 기록 (MinIO 비활성화)")
        print(f"\n소요 시간: {elapsed}")
        print("="*80)
        
        # 결과 파일 위치
        output_dir = Path(__file__).parent.parent / "data" / "test_crawled"
        print(f"\n📂 결과 저장 위치: {output_dir}")
        print(f"   - 페이지: {output_dir}/pages/")
        print(f"   - 인덱스: {output_dir}/crawl_index.json")


def main():
    """메인 실행"""
    import argparse
    
    parser = argparse.ArgumentParser(description='테스트 크롤러 - 첨부파일 MinIO 업로드 지원')
    parser.add_argument('--enable-minio', action='store_true',
                        help='첨부파일을 MinIO에 업로드 (기본값: 메타데이터만 기록)')
    args = parser.parse_args()
    
    crawler = SimpleTestCrawler(enable_minio=args.enable_minio)
    crawler.run()


if __name__ == "__main__":
    main()
