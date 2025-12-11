#!/usr/bin/env python3
"""
repeatCrawler.py (진짜 최종 통합본)

[기능 목록]
1. Requests Session + Retry (타임아웃 방지)
2. 아이콘 이미지 스킵 (속도 향상)
3. HTML Table -> Text 변환 (학사일정 품질)
4. articleNo 기준 중복 방지 (상단 고정 공지 해결)
5. 날짜 기준 조기 종료 (과거 데이터 스킵)
6. 식당 메뉴 크롤링 로직 포함 (누락 없음)
"""

import json
import sys
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import urllib
from urllib.parse import urljoin, parse_qs, urlparse, urlencode, urlunparse
from typing import Optional
from pathlib import Path
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from ftfy import fix_text
from dotenv import load_dotenv
import re
import time
import hashlib 
import mimetypes

# 환경 변수 로드
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

# crawler 모듈 임포트
sys.path.insert(0, str(Path(__file__).parent))

from filters.content_extractor import ContentExtractor
from filters.quality_filter import QualityFilter
from filters.date_filter import DateFilter
from storage.json_storage import JSONStorage
from storage.minio_storage import MinIOStorage
from sendToServer import check_and_notify
import logging
import hashlib

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

exclude_patterns = ["/cms/fileDownload.do"]

# 아이콘 필터
ICON_IMAGE_KEYWORDS = [
    "/_res/ko/img/icon/", "/res/ko/img/common/", "logo", "btn", "btn-", 
    "bg_subvisual", "wa-mark", "bubble_tail", "btn_top_go", "icon",
    "insta", "youtube", "blog", "facebook", "twitter", "kakao", 
    "banner", "footer", "header", "arrow", "line", "bg_", "common"
]

class SimpleTestCrawler:
    def __init__(self, enable_minio: bool = False, output_dir: Optional[Path] = None):
        self.base_url = "https://www.kumoh.ac.kr"
        self.bus_base_url = "https://bus.kumoh.ac.kr"
        
        # 세션 설정
        self.session = requests.Session()
        retries = Retry(total=5, backoff_factor=1, status_forcelist=[500, 502, 503, 504], allowed_methods=["GET"])
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        # MinIO 설정
        self.enable_minio = enable_minio
        if enable_minio:
            try:
                self.minio = MinIOStorage.from_env()
                logger.info("✅ MinIO 스토리지 초기화 완료")
            except Exception as e:
                logger.warning(f"⚠️  MinIO 초기화 실패: {e}")
                self.enable_minio = False
                self.minio = None
        else:
            self.minio = None
        
        # URL 목록
        self.target_urls = [    
            "https://www.kumoh.ac.kr/ko/restaurant01.do",
            "https://www.kumoh.ac.kr/ko/restaurant02.do",
            "https://www.kumoh.ac.kr/ko/restaurant04.do",
            "https://www.kumoh.ac.kr/ko/restaurant05.do",
            "https://www.kumoh.ac.kr/dorm/restaurant_menu01.do",
            "https://www.kumoh.ac.kr/dorm/restaurant_menu02.do",
            "https://www.kumoh.ac.kr/dorm/restaurant_menu03.do",
        ]
        
        self.board_urls = [
            {"url": "https://bus.kumoh.ac.kr/bus/notice.do", "name": "통학버스 공지", "max_pages": 0, "skip_date_filter": True},
            {"url": "https://www.kumoh.ac.kr/ko/sub06_01_01_01.do", "name": "공지사항 학사안내", "max_pages": 0},
            {"url": "https://www.kumoh.ac.kr/ko/sub01_02_03.do", "name": "업무추진비 사용내역", "max_pages": 0},
            {"url": "https://www.kumoh.ac.kr/ko/sub01_05_01.do", "name": "KIT Projects", "max_pages": 0, "skip_date_filter": True},
            {"url": "https://www.kumoh.ac.kr/ko/sub01_05_04.do", "name": "보도자료", "max_pages": 0},
            {"url": "https://www.kumoh.ac.kr/ko/sub06_01_01_02.do", "name": "공지사항 행사안내", "max_pages": 0},
            {"url": "https://www.kumoh.ac.kr/ko/sub06_01_01_03.do", "name": "공지사항 일반소식", "max_pages": 0},
            {"url": "https://www.kumoh.ac.kr/ko/sub06_03_04_02.do", "name": "정보공유 금오복덕방", "max_pages": 0},
            # {"url": "https://www.kumoh.ac.kr/ko/sub06_03_04_04.do", "name": "정보공유 아르바이트정보", "max_pages": 0, "months_limit": 3},
            {"url": "https://www.kumoh.ac.kr/ko/sub06_03_05_01.do", "name": "문화예술공간 클래식감상", "max_pages": 0},
            {"url": "https://www.kumoh.ac.kr/ko/sub06_03_05_02.do", "name": "문화예술공간 갤러리", "max_pages": 0},
            {"url": "https://www.kumoh.ac.kr/ko/sub06_05_02.do", "name": "총장임용후보자추천위원회 공지사항", "max_pages": 0},
            {"url": "https://www.kumoh.ac.kr/dorm/sub0401.do", "name": "생활관 공지사항", "max_pages": 0},
            {"url": "https://www.kumoh.ac.kr/dorm/sub0407.do", "name": "생활관 선발 공지사항", "max_pages": 0},
            {"url": "https://www.kumoh.ac.kr/dorm/sub0408.do", "name": "생활관 입퇴사 공지사항", "max_pages": 0},
            {"url": "https://www.kumoh.ac.kr/dorm/sub0603.do", "name": "신평동 신청방법", "max_pages": 0},
            {"url": "https://www.kumoh.ac.kr/ko/sub01_01_07_02.do", "name": "대학소개 현황 재정현황", "max_pages": 0},
            {"url": "https://www.kumoh.ac.kr/ko/sub01_01_07_03.do", "name": "대학소개 현황 재정위원회 회의록", "max_pages": 0},
            {"url": "https://www.kumoh.ac.kr/ko/sub01_01_07_04.do", "name": "대학소개 현황 대학평의원회 회의록", "max_pages": 0},
            {"url": "https://www.kumoh.ac.kr/ko/sub01_01_07_05.do", "name": "대학소개 현황 등록금심의위원 회의록", "max_pages": 0},
            {"url": "https://www.kumoh.ac.kr/ko/sub01_01_08.do", "name": "대학소개 UI", "max_pages": 0},
            {"url": "https://www.kumoh.ac.kr/ko/sub01_04.do", "name": "대학소개 규정집", "max_pages": 0},
            {"url": "https://www.kumoh.ac.kr/ko/sub01_05_02.do", "name": "대학소개 홍보 KIT People", "max_pages": 0},
            {"url": "https://www.kumoh.ac.kr/ko/sub01_05_03.do", "name": "대학소개 홍보 KIT News", "max_pages": 0},
            {"url": "https://www.kumoh.ac.kr/ko/sub07_01_02.do", "name": "금오신문고 청탁금지법자료실", "max_pages": 0},
            {"url": "https://www.kumoh.ac.kr/ko/sub07_01_03.do", "name": "금오신문고 행동강령자료실", "max_pages": 0}
        ]
        
        self.quality_filter = QualityFilter(min_text_length=100, max_text_length=500000, min_word_count=20)
        self.date_filter = DateFilter(cutoff_date="2024-01-01")
        
        if output_dir is None:
            output_dir = Path(__file__).parent.parent / "data" / "raw" / "core"
        self.output_dir = Path(output_dir)
        self.storage = JSONStorage(self.output_dir, pretty_print=True)
        self.content_extractor = ContentExtractor(keep_links=True, keep_images=False)
        
        self.stats = {"total": 0, "success": 0, "failed": 0, "filtered": 0, "filtered_date": 0, "skipped": 0, "attachments_found": 0, "attachments_uploaded": 0}
        self.saved_pages = []
        self.existing_urls = set()
        self.collected_article_nos = set()
        self.index_meta: dict = {}
        self._load_existing_index()

    def _clean_url(self, url: str) -> str:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        
        # 변동되는 파라미터 삭제
        for key in ['article.offset', 'articleLimit']:
            if key in qs: del qs[key]
        
        # 재조립
        new_query = urlencode(qs, doseq=True)
        return urlunparse(parsed._replace(query=new_query))
    
    def _get_article_no(self, url: str) -> Optional[str]:
        try:
            parsed = urlparse(url)
            qs = parse_qs(parsed.query)
            return qs.get('articleNo', [None])[0]
        except: return None

    def _load_existing_index(self):
        index_file = self.output_dir / "crawl_index.json"
        if index_file.exists():
            try:
                with open(index_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for page in data.get('pages', []):
                        # 저장된 URL도 세탁해서 기억
                        clean = self._clean_url(page['url'])
                        self.existing_urls.add(clean)
                        ano = self._get_article_no(clean)
                        if ano: self.collected_article_nos.add(ano)
            except: pass

    def _convert_tables_to_text(self, html_content: str) -> str:
        if not html_content: return ""
        soup = BeautifulSoup(html_content, "html.parser")
        tables = soup.find_all("table")
        if not tables: return html_content 
        for table in tables:
            rows_text = []
            for tr in table.find_all("tr"):
                cells = [cell.get_text(strip=True) for cell in tr.find_all(["th", "td"])]
                if any(cells): rows_text.append(" | ".join(cells))
            if rows_text:
                new_div = soup.new_tag("div")
                new_div.string = f"\n[표 데이터 시작]\n" + "\n".join(rows_text) + "\n[표 데이터 끝]\n"
                table.replace_with(new_div)
        return str(soup)

    def _is_file_exist(self, url: str) -> bool:
        clean = self._clean_url(url)
        url_hash = hashlib.sha256(clean.encode()).hexdigest()[:16]
        file_path = self.output_dir / "pages" / f"{url_hash}.json"
        return file_path.exists()
    
    def crawl_url(self, url: str, skip_date_filter: bool = False, context: dict | None = None) -> bool:
        # 1. [Fix] 파일 존재 여부부터 가장 먼저 확인 (로그 출력 없이 조용히 검사)
        if self._is_file_exist(url):
            logger.info(f"⏭️ 파일 존재함 - 스킵: {url}")
            self.stats["skipped"] += 1
            return True  # 이미 성공한 것으로 간주

        # 2. [Fix] 실제로 크롤링할 때만 Total 카운트 증가 및 로그 출력
        self.stats["total"] += 1
        context = context or {}
        logger.info(f"크롤링 시작: {url}")

        try:
            headers = {'User-Agent': 'KITBot/2.0'}
            response = self.session.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            html = response.text
            post_date = self._extract_post_date(html)
            
            if not skip_date_filter:
                date_str = post_date or self._extract_date_from_html(html)
                if date_str and not self.date_filter.is_recent(date_str):
                    logger.info(f"  ⏭️  날짜 필터: {date_str} (2024-01-01 이전)")
                    self.stats["filtered"] += 1
                    self.stats["filtered_date"] += 1
                    return False
            
            author, view_count, created_at = None, None, post_date
            if context.get("source_type") == "board":
                author, view_count, b_created = self._extract_board_meta(html)
                if b_created: created_at = b_created
            
            is_quality, reason = self.quality_filter.is_high_quality(html, url)
            if not is_quality:
                self.stats["filtered"] += 1
                return False
            
            html_with_tables = self._convert_tables_to_text(html)
            content_data = self.content_extractor.extract_with_metadata(html_with_tables)
            attachments = self._process_attachments(url, html)
            board_title = self._extract_board_title(html) if context.get("source_type") == "board" else None
            title_for_json = board_title or content_data['title'] or context.get("board_name")
            
            metadata = {
                "text_length": len(content_data['text']), "word_count": content_data['word_count'], "title": title_for_json,
                "paragraphs": content_data['paragraphs'], "link_count": len(content_data['links']),
                "attachments_count": len(attachments), "attachments": attachments, "images": content_data['images'],
                "quality_check": reason, "crawled_at": datetime.now().isoformat(), "source_url": url,
                "source_type": context.get("source_type", "page"), "board_name": content_data['title'],
                "author": author, "view_count": view_count, "created_at": created_at, "has_explicit_date": bool(created_at)
            }
            
            filepath = self.storage.save_page(url, html, metadata, extracted_text=content_data['text'], title=title_for_json)
            self.saved_pages.append({"url": url, "file": filepath, "title": title_for_json, "text_length": len(content_data['text'])})
            self.stats["success"] += 1
            logger.info(f"✅ 저장 완료: {Path(filepath).name}")

            try:
                # metadata['title']에는 이미 정제된 제목이 들어있습니다.
                check_and_notify(
                    url=url,
                    title=metadata["title"]
                )
            except Exception as e:
                logger.warning(f"⚠️ 안드로이드 알림 전송 실패: {e}")

            return True
            
        except Exception as e:
            logger.error(f"❌ 에러: {e}")
            self.stats["failed"] += 1
            return False

    def _extract_board_title(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        head = soup.find('div', class_='title-area')
        if not head: return None
        for tag in ['h4', 'h3', 'strong']:
            el = head.find(tag)
            if el and el.get_text(strip=True): return el.get_text(strip=True)
        return None

    def _extract_board_meta(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        info_div = soup.find('div', class_='board-view-information')
        author, view, created = None, None, None
        if not info_div: return None, None, None
        for dl in info_div.find_all('dl'):
            dt, dd = dl.find('dt'), dl.find('dd')
            if not dt or not dd: continue
            k, v = dt.get_text(strip=True), dd.get_text(strip=True)
            if '작성자' in k: author = v
            elif '조회' in k: 
                d = ''.join(c for c in v if c.isdigit())
                if d: view = int(d)
            elif '작성일' in k:
                m = re.search(r'(\d{4})[.-](\d{2})[.-](\d{2})', v)
                if m: created = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        return author, view, created

    def _process_attachments(self, page_url: str, html: str) -> list:
        # [Update] Content-Type 기반 확장자 보정 로직 추가
        attachments = []
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # 1. 첨부파일 (a 태그)
            for link in soup.find_all('a', href=True):
                href = link['href']
                link_text = link.get_text(strip=True)
                is_download = (
                    'mode=download' in href or
                    'download' in href.lower() or
                    any(href.lower().endswith(x) for x in ['.pdf','.hwp','.docx','.xlsx','.zip'])
                )
                if any(p in href for p in exclude_patterns): is_download = False
                if not is_download: continue
                
                abs_url = urljoin(page_url, href)
                self.stats["attachments_found"] += 1
                att_info = {"page_url": page_url, "link_text": link_text, "download_url": abs_url, "detected_at": datetime.now().isoformat()}
                
                if self.enable_minio and self.minio:
                    try:
                        headers = {'User-Agent': 'KITBot/2.0', 'Referer': page_url}
                        resp = self.session.get(abs_url, headers=headers, timeout=30)
                        resp.raise_for_status()
                        
                        file_data = resp.content
                        content_type = resp.headers.get('Content-Type', '').split(';')[0].strip()
                        
                        # 파일명 결정 로직
                        content_disp = resp.headers.get('Content-Disposition', '')
                        if 'filename=' in content_disp: 
                            filename = content_disp.split('filename=')[-1].strip('"\'')
                        else:
                            filename = abs_url.split('/')[-1].split('?')[0]
                            # 파일명에 확장자가 없거나 .do 인 경우
                            if '.' not in filename or filename.endswith('.do'):
                                # 링크 텍스트에 확장자가 있으면 그걸 사용 (예: "공지사항.pdf")
                                if '.' in link_text:
                                    filename = link_text
                                else:
                                    # 그것도 없으면 해시값 생성
                                    filename = f"file_{hashlib.md5(abs_url.encode()).hexdigest()[:8]}"

                        # URL 디코딩 및 정제
                        try: filename = urllib.parse.unquote(filename)
                        except: pass
                        filename = fix_text(filename)
                        
                        # [핵심] 확장자 강제 보정 (MIME Type 활용)
                        # 예: filename이 "image.do"인데 content_type이 "image/jpeg"면 -> "image.jpg"로 변경
                        if filename.lower().endswith('.do') or '.' not in filename:
                            guessed_ext = mimetypes.guess_extension(content_type)
                            if guessed_ext:
                                if guessed_ext == '.jpe': guessed_ext = '.jpg' # 윈도우 호환
                                filename = Path(filename).stem + guessed_ext

                        clean_name = filename.replace('/', '_').replace('\\', '_')
                        obj_name = f"attachments/{clean_name}"
                        
                        success, res = self.minio.upload_file(resp.content, obj_name, content_type, metadata={"source_url": abs_url, "original_filename": filename})
                        if success: 
                            att_info.update({"minio_url": res, "minio_object": obj_name, "filename": clean_name, "status": "uploaded"})
                            self.stats["attachments_uploaded"] += 1
                            logger.info(f"   📎 첨부파일 업로드: {clean_name}")
                    except Exception as e:
                        att_info.update({"status": "download_failed", "error": str(e)})
                else: att_info["status"] = "metadata_only"
                attachments.append(att_info)
                
            # 2. 이미지 (img 태그)
            image_exts = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg']
            for img in soup.find_all('img', src=True):
                src, alt = img['src'], img.get('alt', '').strip()
                if any(k in src for k in ICON_IMAGE_KEYWORDS): continue
                abs_url = urljoin(page_url, src)
                self.stats["attachments_found"] += 1
                att_info = {"page_url": page_url, "link_text": alt, "download_url": abs_url, "type": "image"}
                
                if self.enable_minio and self.minio:
                    try:
                        resp = self.session.get(abs_url, headers={'User-Agent': 'KITBot/2.0'}, timeout=30)
                        content_type = resp.headers.get('Content-Type', '').split(';')[0].strip()
                        
                        # 기본 파일명 추출
                        fname = abs_url.split('/')[-1].split('?')[0]
                        if not fname: fname = "image"
                        
                        # [핵심] 확장자 보정
                        # .do 이거나 확장자가 없으면 MIME 타입으로 추측
                        if fname.lower().endswith('.do') or '.' not in fname:
                            guessed_ext = mimetypes.guess_extension(content_type)
                            if guessed_ext:
                                if guessed_ext == '.jpe': guessed_ext = '.jpg'
                                fname = Path(fname).stem + guessed_ext
                            else:
                                # 추측 실패 시 기본값
                                fname = Path(fname).stem + ".jpg"

                        clean_name = fname.replace('/', '_').replace('\\', '_')
                        obj_name = f"images/{clean_name}"
                        
                        success, res = self.minio.upload_file(resp.content, obj_name, content_type, metadata={"source_url": abs_url, "alt_text": alt})
                        if success:
                            att_info.update({"minio_url": res, "minio_object": obj_name, "filename": clean_name, "status": "uploaded"})
                            self.stats["attachments_uploaded"] += 1
                            logger.info(f"   🖼 이미지 업로드: {clean_name}")
                    except Exception as e:
                        att_info.update({"status": "download_failed", "error": str(e)})
                else: att_info["status"] = "metadata_only"
                attachments.append(att_info)
        except Exception as e: logger.error(f"❌ 첨부파일 처리 에러: {e}")
        return attachments

    def _extract_post_date(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        info = soup.find('div', class_='board-view-information')
        if not info: return None
        for dl in info.find_all('dl'):
            if '작성일' in dl.get_text():
                m = re.search(r'(\d{4})[.-](\d{2})[.-](\d{2})', dl.get_text())
                if m: return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        return None

    def _extract_date_from_html(self, html): return self._extract_post_date(html)

    def crawl_list_page(self, url: str, max_pages: int = 10, skip_date_filter: bool = False, board_name: str = "게시판", custom_cutoff: str = None, max_items: int = 0):
        logger.info(f"\n📋 [{board_name}] 리스트 분석 시작")
        page_num = 0
        total_articles = 0
        base_url = self.bus_base_url if 'bus.kumoh.ac.kr' in url else self.base_url
        
        duplicate_strike = 0 # 연속 중복 카운터

        while True:
            if page_num == 0: page_url = url
            else:
                offset = page_num * 10
                page_url = f"{url}&article.offset={offset}" if '?' in url else f"{url}?article.offset={offset}"
            
            try:
                response = self.session.get(page_url, headers={'User-Agent': 'KITBot/2.0'}, timeout=30)
                soup = BeautifulSoup(response.text, 'html.parser')
                
                article_links = []
                
                # 1. 먼저 링크 수집 (날짜 체크 전에)
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    if 'mode=view' in href or 'articleNo' in href:
                        if href.startswith('/'): full_url = f"{base_url}{href}"
                        elif href.startswith('?'): full_url = f"{url.split('?')[0]}{href}"
                        else: full_url = href
                        
                        clean_url = self._clean_url(full_url)
                        
                        # 글번호 중복 체크
                        ano = self._get_article_no(clean_url)
                        if ano and ano in self.collected_article_nos:
                            duplicate_strike += 1
                            if duplicate_strike >= 5:
                                logger.info("🛑 [Stop] 중복 게시글 연속 발견. 최신 글 수집 완료.")
                                return
                            continue
                        
                        # 파일 존재 체크
                        if self._is_file_exist(clean_url):
                            duplicate_strike += 1
                            if duplicate_strike >= 5:
                                logger.info("🛑 [Stop] 이미 수집된 구간(파일 존재). 종료.")
                                return
                            continue

                        duplicate_strike = 0
                        if clean_url not in article_links: 
                            article_links.append(clean_url)
                
                # 2. 날짜 기준 조기 종료 체크 (링크 수집 후)
                if not skip_date_filter and article_links:
                    old_cnt = 0
                    for row in soup.select('tbody tr'):
                        txt = row.get_text()
                        m = re.search(r'(\d{4})[.-](\d{2})[.-](\d{2})', txt)
                        if m:
                            d = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
                            if custom_cutoff and d < custom_cutoff: old_cnt += 1
                            elif not custom_cutoff and not self.date_filter.is_recent(d): old_cnt += 1
                    
                    if old_cnt >= 5:
                        logger.info(f"🛑 [Stop] 과거 데이터({old_cnt}개) 구간 진입. 이번 페이지 스킵하고 종료.")
                        break
                
                if not article_links:
                    logger.info(f"   페이지 {page_num + 1}: 신규 글 없음 - 종료")
                    break

                logger.info(f"   페이지 {page_num + 1}: {len(article_links)}개 신규 글 수집")
                
                for i, article_url in enumerate(article_links, 1):
                    # crawl_url 호출 (세탁된 URL 전달)
                    success = self.crawl_url(article_url, skip_date_filter=skip_date_filter, 
                                           context={"source_type": "board", "board_name": board_name})
                    if success:
                        self.existing_urls.add(article_url)
                        ano = self._get_article_no(article_url)
                        if ano: self.collected_article_nos.add(ano)
                    time.sleep(0.5)
                
                page_num += 1
                if max_pages > 0 and page_num >= max_pages: break
                time.sleep(1)

            except Exception as e:
                logger.error(f"❌ 에러: {e}")
                break
        
        logger.info(f"\n✅ [{board_name}] 총 {total_articles}개 게시글 크롤링 완료")

    # -------------------------------------------------------------------------
    # [Fix] Selenium 기반 학사일정 크롤러 (JS 동적 로딩 완벽 대응)
    # -------------------------------------------------------------------------
    def crawl_yearly_schedule(self, target_years=[2025, 2026]):
        logger.info(f"\n📅 학사일정 연도별 수집 시작 (Selenium): {target_years}")
        base_url = "https://www.kumoh.ac.kr/ko/schedule.do"

        # 1. Selenium 옵션 설정 (헤드리스 모드)
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")  # 창 띄우지 않음
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        
        # 드라이버 실행
        try:
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        except Exception as e:
            logger.error(f"❌ Selenium 드라이버 초기화 실패: {e}")
            return

        for year in target_years:
            # srMonth=1로 설정하여 해당 연도 접근 (사이트 특성상 1월로 가면 연간 리스트가 로딩됨)
            page_url = f"{base_url}?mode=list&srYear={year}&srMonth=1"
            
            # 파일 존재 여부 확인 (중복 스킵)
            if self._is_file_exist(page_url):
                logger.info(f"   ⏭️ {year}년 학사일정 이미 존재함 - 스킵")
                continue

            try:
                logger.info(f"   🌍 접속 중... {page_url}")
                driver.get(page_url)
                
                # 2. JS 렌더링 대기 (데이터가 뜰 때까지 3초 대기)
                time.sleep(3)
                
                # 3. HTML 파싱
                html = driver.page_source
                soup = BeautifulSoup(html, 'html.parser')
                
                schedule_lines = []
                schedule_lines.append(f"{year}학년도 학사일정")
                schedule_lines.append("구조: 기간 | 내용")
                schedule_lines.append("-" * 30)
                
                count = 0
                
                # 4. 연간 일정 테이블 파싱 (.year-schedule 클래스 내부)
                # 구조: div.year-schedule > div.schedule-list > table > tbody > tr
                tbody = soup.select_one(".year-schedule .schedule-table tbody")
                
                if tbody:
                    current_month_label = ""
                    
                    for tr in tbody.select("tr"):
                        tds = tr.find_all("td")
                        
                        # case 1: 월(rowspan) / 일자 / 내용 (3칸)
                        if len(tds) == 3:
                            current_month_label = tds[0].get_text(strip=True) # 예: "2025년 01월"
                            date_text = tds[1].get_text(strip=True)           # 예: "01.01(수)"
                            content_text = tds[2].get_text(strip=True)        # 예: "신정"
                        
                        # case 2: 일자 / 내용 (2칸, 월은 위에서 상속)
                        elif len(tds) == 2:
                            date_text = tds[0].get_text(strip=True)
                            content_text = tds[1].get_text(strip=True)
                        else:
                            continue

                        if content_text:
                            # RAG가 읽기 좋은 포맷으로 변환
                            # 예: "2025년 03월 | 03.02(월) | 1학기 개강"
                            line = f"{current_month_label} | {date_text} | {content_text}"
                            schedule_lines.append(line)
                            count += 1
                
                # 5. 결과 저장
                if count > 0:
                    logger.info(f"   ✅ {year}년 일정 {count}개 수집 완료 (Selenium)")
                    final_text = "\n".join(schedule_lines)
                    
                    meta = {
                        "title": f"{year}학년도 학사일정",
                        "crawled_at": datetime.now().isoformat(),
                        "type": "schedule_year",
                        "year": year,
                        "url": page_url # 원본 링크
                    }
                    
                    fp = self.storage.save_page(page_url, html, meta, extracted_text=final_text, title=meta['title'])
                    self.saved_pages.append({"url": page_url, "file": fp})
                    self.stats["success"] += 1
                else:
                    logger.warning(f"   ⚠️ {year}년 일정 데이터를 찾을 수 없습니다. (테이블 비어있음)")

            except Exception as e:
                logger.error(f"   ❌ {year}년 수집 중 에러: {e}")

        # 브라우저 종료
        driver.quit()

    def crawl_restaurant_lists(self, url: str, max_pages: int = 1):
        logger.info(f"\n🍽️ 식당 메뉴 리스트 크롤링: {url}")
        page_num = 0
        while page_num < max_pages:
            page_url = url
            try:
                response = self.session.get(page_url, headers={'User-Agent': 'KITBot/2.0'}, timeout=30)
                html = response.text
                soup = BeautifulSoup(html, 'html.parser')
                menu_text = self._extract_menu_table(soup)
                
                restaurant_name = "식당"
                if 'restaurant01' in url: restaurant_name = "학생식당"
                elif 'restaurant02' in url: restaurant_name = "교직원식당"
                elif 'restaurant04' in url: restaurant_name = "분식당"
                elif 'restaurant05' in url: restaurant_name = "신평캠퍼스식당"
                elif 'restaurant_menu01' in url: restaurant_name = "푸름관"
                elif 'restaurant_menu02' in url: restaurant_name = "오름관1동"
                elif 'restaurant_menu03' in url: restaurant_name = "오름관2동"
                
                metadata = {"title": f"{restaurant_name} 메뉴", "crawled_at": datetime.now().isoformat(), "type": "restaurant_menu"}
                fp = self.storage.save_page(page_url, html, metadata, extracted_text=menu_text, title=metadata['title'])
                self.saved_pages.append({"url": page_url, "file": fp, "title": metadata['title']})
                self.stats["success"] += 1
                logger.info(f"   ✅ 저장 완료: {Path(fp).name} ({restaurant_name})")
                page_num += 1
            except Exception as e:
                logger.error(f"❌ 에러: {e}")
                break
    
    def _extract_menu_table(self, soup: BeautifulSoup) -> str:
        table = None
        for t in soup.find_all("table"):
            cap = t.find("caption")
            if cap and "식당 메뉴 표" in cap.get_text(strip=True):
                table = t
                break
        if table is None: table = soup.find("table")
        if table is None: return ""
        thead = table.find("thead")
        if not thead: return ""
        ths = thead.find_all("th")
        day_labels = [th.get_text(" ", strip=True) for th in ths if th.get_text(strip=True)]
        num_days = len(day_labels)
        if num_days == 0: return ""
        per_day: list[dict[str, list[str]]] = [dict() for _ in range(num_days)]
        meal_order: list[str] = []
        tbody = table.find("tbody")
        if not tbody: return ""
        for row in tbody.find_all("tr"):
            tds = row.find_all("td")
            if not tds: continue
            for col_idx, td in enumerate(tds):
                if col_idx >= num_days: break
                p = td.find("p")
                if not p: continue
                meal_name = p.get_text(strip=True)
                if not meal_name: continue
                items = [li.get_text(strip=True) for li in td.find_all("li")]
                if not items: continue
                if meal_name not in meal_order: meal_order.append(meal_name)
                day_meals = per_day[col_idx]
                if meal_name not in day_meals: day_meals[meal_name] = []
                day_meals[meal_name].extend(items)
        lines: list[str] = []
        for day_idx, day_label in enumerate(day_labels):
            lines.append(f"[{day_label}]")
            day_meals = per_day[day_idx]
            for meal_name in meal_order:
                if meal_name in day_meals and day_meals[meal_name]:
                    menu_str = " / ".join(day_meals[meal_name])
                    lines.append(f"  {meal_name}: {menu_str}")
            lines.append("")
        return "\n".join(lines).strip()

    def run(self):
        print("="*80); print("RepeatCrawler (최종 완성본)"); print("="*80)
        
        # 1. [New] 학사일정은 Selenium으로 수집
        self.crawl_yearly_schedule([2025, 2026])
        
        # 2. 식당 메뉴 (기존)
        for url in self.target_urls:
            if 'restaurant' in url: self.crawl_restaurant_lists(url)
            import time; time.sleep(1)
            
        # 3. 게시판 (기존)
        for board in self.board_urls:
            custom_cutoff = None
            if "months_limit" in board:
                limit_date = datetime.now() - timedelta(days=board["months_limit"] * 30)
                custom_cutoff = limit_date.strftime("%Y-%m-%d")
            
            self.crawl_list_page(
                board['url'], 
                board.get('max_pages', 0), 
                board.get('skip_date_filter', False), 
                board['name'], 
                custom_cutoff=custom_cutoff,
                max_items=board.get('max_items', 0)
            )
            import time; time.sleep(1)
        
        if self.saved_pages:
            self.storage.save_index({"crawl_date": datetime.now().isoformat(), "pages": self.saved_pages, "meta": self.index_meta})

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--enable-minio', action='store_true')
    parser.add_argument('--output-dir', type=str)
    args = parser.parse_args()
    out = Path(args.output_dir) if args.output_dir else None
    SimpleTestCrawler(args.enable_minio, out).run()

if __name__ == "__main__":
    main()