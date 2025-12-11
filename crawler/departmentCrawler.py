#!/usr/bin/env python3
"""
departmentCrawler.py

학과 소개 / 동아리 소개 / 교육과정(정적 페이지 위주) 1회성 크롤러
- 자주 변하지 않는 정적 정보용
- [Update] Session/Retry, 확장자 보정(.do), 아이콘 필터 적용
"""

import sys
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup, Tag
from dotenv import load_dotenv
from typing import Optional
import logging
import hashlib
import urllib.parse
from ftfy import fix_text
import mimetypes # [New] 확장자 보정용

# 환경 변수 로드
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

# crawler 모듈 임포트
sys.path.insert(0, str(Path(__file__).parent))

from filters.content_extractor import ContentExtractor
from filters.quality_filter import QualityFilter
from storage.json_storage import JSONStorage
from storage.minio_storage import MinIOStorage

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

exclude_patterns = ["/cms/fileDownload.do"]

# 아이콘 필터 (속도 향상)
ICON_IMAGE_KEYWORDS = [
    "/_res/ko/img/icon/", "/res/ko/img/common/", "logo", "btn", "btn-", 
    "bg_subvisual", "wa-mark", "bubble_tail", "btn_top_go", "icon",
    "insta", "youtube", "blog", "facebook", "twitter", "kakao", 
    "banner", "footer", "header", "arrow", "line", "bg_", "common"
]

class departmentCrawler:
    """학과/동아리/정적 소개 페이지 전용 크롤러"""

    def __init__(self, enable_minio: bool = False, output_dir: Optional[Path] = None):
        
        # [New] 세션 및 재시도 설정
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

        # ✅ 크롤링 대상 URL 목록 (기존 리스트 유지)
        self.department_static_urls = [
            # 에디슨칼리지 첨단산업융합학부
            {"url": "https://edison.kumoh.ac.kr/edison/sub0101.do", "name": "에디슨칼리지 첨단산업융합학부 소개"},
            {"url": "https://edison.kumoh.ac.kr/edison/sub0102.do", "name": "에디슨칼리지 첨단산업융합학부 교육목표"},
            {"url": "https://edison.kumoh.ac.kr/edison/sub0104.do", "name": "에디슨칼리지 첨단산업융합학부 비전"},
            # 건축토목환경공학부
            {"url": "https://archi.kumoh.ac.kr/archi/sub0102.do", "name": "건축토목환경공학부 소개"},
            {"url": "https://archi.kumoh.ac.kr/archi/sub0103.do", "name": "건축토목환경공학부 건축학전공 소개"},
            {"url": "https://archi.kumoh.ac.kr/archi/sub0104.do", "name": "건축토목환경공학부 건축공학전공 소개"},
            {"url": "https://civil.kumoh.ac.kr/civil/sub0101.do", "name": "건축토목환경공학부 토목공학전공 소개"},
            {"url": "https://env.kumoh.ac.kr/env/sub0101.do", "name": "건축토목환경공학부 환경공학전공 소개"},
            {"url": "https://env.kumoh.ac.kr/env/sub0202_01.do", "name": "건축토목환경공학부 환경공학전공 동아리 지구환경연구회 소개"},
            {"url": "https://env.kumoh.ac.kr/env/sub0202_02.do", "name": "건축토목환경공학부 환경공학전공 동아리 아름드리 소개"},
            {"url": "https://env.kumoh.ac.kr/env/sub0202_03.do", "name": "건축토목환경공학부 환경공학전공 동아리 ESC 소개"},
            {"url": "https://env.kumoh.ac.kr/env/sub0202_04.do", "name": "건축토목환경공학부 환경공학전공 동아리 BOD 소개"},
            # 기계공학부
            {"url": "https://mecheng.kumoh.ac.kr/mecheng/sub0101.do", "name": "기계공학부 기계공학전공 소개"},
            {"url": "https://mx.kumoh.ac.kr/md/sub0101.do", "name": "기계공학부 기계시스템공학전공 소개"},
            {"url": "https://mobility.kumoh.ac.kr/smartmobility/sub0101.do", "name": "기계공학부 스마트모빌리티전공 인사말"},
            {"url": "https://mobility.kumoh.ac.kr/smartmobility/sub0102.do", "name": "기계공학부 스마트모빌리티전공 교육 목표"},
            {"url": "https://mobility.kumoh.ac.kr/smartmobility/sub0301.do", "name": "기계공학부 스마트모빌리티전공 공동학과 교육 과정"},
            {"url": "https://mobility.kumoh.ac.kr/smartmobility/sub0304.do", "name": "기계공학부 스마트모빌리티전공 이수체계도"},
            # 산업빅데이터공학부
            {"url": "https://ie.kumoh.ac.kr/ie/sub0102.do", "name": "산업빅데이터공학부 산업공학전공 소개"},
            {"url": "https://ie.kumoh.ac.kr/ie/sub0603.do", "name": "산업빅데이터공학부 산업공학전공 동아리/학생회"},
            {"url": "https://www.kumoh.ac.kr/bigdata/sub0102.do", "name": "산업빅데이터공학부 수리빅데이터전공 개요 및 연혁"},
            {"url": "https://www.kumoh.ac.kr/bigdata/sub0502.do", "name": "산업빅데이터공학부 수리빅데이터전공 전공동아리"},
            # 재료공학부
            {"url": "https://polymer.kumoh.ac.kr/polymer/sub0202.do", "name": "재료공학부 고분자공학전공 전공소개"},
            {"url": "https://polymer.kumoh.ac.kr/polymer/sub0502.do", "name": "재료공학부 고분자공학전공 동아리"},
            {"url": "https://mse.kumoh.ac.kr/mse/sub0102.do", "name": "재료공학부 신소재공학전공 전공소개"},
            {"url": "https://mse.kumoh.ac.kr/mse/sub020102.do", "name": "재료공학부 신소재공학전공 교육과정 편성표"},
            {"url": "https://mse.kumoh.ac.kr/mse/sub0602.do", "name": "재료공학부 신소재공학전공 동아리"},
            # 전자공학부
            {"url": "https://see.kumoh.ac.kr/see/sub0101.do", "name": "전자공학부 반도체시스템전공 전자시스템전공 소개"},
            {"url": "https://see.kumoh.ac.kr/see/sub0501.do", "name": "전자공학부 반도체시스템전공 전자시스템전공 동아리"},
            # 컴퓨터공학부 - 소프트웨어전공
            {"url": "https://cs.kumoh.ac.kr/cs/sub0101.do", "name": "컴퓨터공학부 소프트웨어전공 소개"},
            {"url": "https://cs.kumoh.ac.kr/cs/sub0105_2.do", "name": "컴퓨터공학부 소프트웨어전공 교육과정"},
            {"url": "https://cs.kumoh.ac.kr/cs/sub0504.do", "name": "컴퓨터공학부 소프트웨어전공 동아리"},
            # 컴퓨터공학부 - 인공지능공학전공
            {"url": "https://ai.kumoh.ac.kr/ai/sub0102.do", "name": "컴퓨터공학부 인공지능공학전공 개요 및 연혁"},
            {"url": "https://ai.kumoh.ac.kr/ai/sub0302.do", "name": "컴퓨터공학부 인공지능공학전공 교육과정표"},
            {"url": "https://ai.kumoh.ac.kr/ai/sub0602.do", "name": "컴퓨터공학부 인공지능공학전공 전공동아리"},
            # 컴퓨터공학부 - 컴퓨터공학전공
            {"url": "https://ce.kumoh.ac.kr/ce/sub0102.do", "name": "컴퓨터공학부 컴퓨터공학전공 개요 및 연혁"},
            {"url": "https://ce.kumoh.ac.kr/ce/sub0205.do", "name": "컴퓨터공학부 컴퓨터공학전공 동아리"},
            {"url": "https://ce.kumoh.ac.kr/ce/sub0301.do", "name": "컴퓨터공학부 컴퓨터공학전공 교과과정"},
            # 화학소재공학부 - 소재디자인공학전공
            {"url": "https://textile.kumoh.ac.kr/textile/sub0101.do", "name": "화학소재공학부 소재디자인공학전공 전공장 인사말"},
            {"url": "https://textile.kumoh.ac.kr/textile/sub0203.do", "name": "화학소재공학부 소재디자인공학전공 교육과정"},
            {"url": "https://textile.kumoh.ac.kr/textile/sub0501.do", "name": "화학소재공학부 소재디자인공학전공 전공동아리"},
            # 화학소재공학부 - 화학공학전공
            {"url": "https://che.kumoh.ac.kr/che/sub0102.do", "name": "화학소재공학부 화학공학전공 학과소개"},
            {"url": "https://che.kumoh.ac.kr/che/sub0502.do", "name": "화학소재공학부 화학공학전공 동아리"},
            # 화학소재공학부 - 화학생명소재전공
            {"url": "https://chembio.kumoh.ac.kr/chembio/sub0102.do", "name": "화학소재공학부 화학생명소재전공 전공개요"},
            # 광시스템공학과
            {"url": "https://optics.kumoh.ac.kr/optics/sub0101.do", "name": "광시스템공학과 학과소개"},
            # 바이오메디컬공학과
            {"url": "https://medicalit.kumoh.ac.kr/medicalit/sub0101.do", "name": "바이오메디컬공학과 학과소개"},
            {"url": "https://medicalit.kumoh.ac.kr/medicalit/sub020102.do", "name": "바이오메디컬공학과 교과소개"},
            # IT융합학과
            {"url": "https://itc.kumoh.ac.kr/itc/sub0101.do", "name": "IT융합학과 학과소개"},
            {"url": "https://itc.kumoh.ac.kr/itc/sub0103.do#accordion-menu-title", "name": "IT융합학과 교과목개요"},
            # 자율전공학부
            {"url": "https://sls.kumoh.ac.kr/sls/sub0101.do", "name": "자율전공학부 소개"},
            {"url": "https://sls.kumoh.ac.kr/sls/sub0301.do", "name": "자율전공학부 교과과정"},
            {"url": "https://sls.kumoh.ac.kr/sls/sub0302.do", "name": "자율전공학부 전공선택"},
            # 경영학과
            {"url": "https://biz.kumoh.ac.kr/biz/sub0102.do", "name": "경영학과 소개"},
            {"url": "https://biz.kumoh.ac.kr/biz/sub0702.do", "name": "경영학과 동아리"},
        ]

        self.department_board_urls = [
            {"url": "https://archi.kumoh.ac.kr/archi/sub0201.do", "name": "건축토목환경공학부 건축학전공 교육과정"},
            {"url": "https://archi.kumoh.ac.kr/archi/sub0202.do", "name": "건축토목환경공학부 건축공학전공 교육과정"},
            {"url": "https://civil.kumoh.ac.kr/civil/sub030101.do", "name": "건축토목환경공학부 토목공학전공 교육과정"},
            {"url": "https://ie.kumoh.ac.kr/ie/sub030101.do", "name": "산업빅데이터공학부 산업공학전공 교육과정"},
            {"url": "https://www.kumoh.ac.kr/bigdata/sub030102.do", "name": "산업빅데이터공학부 수리빅데이터전공 교육과정표"},
            {"url": "https://polymer.kumoh.ac.kr/polymer/sub0404.do", "name": "재료공학부 고분자공학전공 교과과정"},
            {"url": "https://che.kumoh.ac.kr/che/sub0304.do", "name": "화학소재공학부 화학공학전공 교과과정"},
            {"url": "https://chembio.kumoh.ac.kr/chembio/sub030101.do", "name": "화학소재공학부 화학생명소재전공 교육과정 및 교과목 개요"},
            {"url": "https://optics.kumoh.ac.kr/optics/sub020102.do", "name": "광시스템공학과 학부교육과정"},
            {"url": "https://biz.kumoh.ac.kr/biz/sub030101.do", "name": "경영학과 교과과정"},
        ]

        # 필터 및 저장소 초기화
        self.quality_filter = QualityFilter(
            min_text_length=50,
            max_text_length=500000,
            min_word_count=10
        )

        if output_dir is None:
            output_dir = Path(__file__).parent.parent / "data" / "raw" / "departments"

        self.output_dir = Path(output_dir)
        self.storage = JSONStorage(self.output_dir, pretty_print=True)

        self.content_extractor = ContentExtractor(
            keep_links=True,
            keep_images=False
        )

        self.stats = {"total": 0, "success": 0, "failed": 0, "filtered": 0, "skipped": 0, "attachments_found": 0, "attachments_uploaded": 0}
        self.saved_pages = []
        self.existing_urls = set()
        self._load_existing_index()

    def _load_existing_index(self):
        index_file = self.output_dir / "crawl_index.json"
        if index_file.exists():
            try:
                import json
                with open(index_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for page in data.get('pages', []):
                        url = page.get('url')
                        if url:
                            self.existing_urls.add(url)
                            self.saved_pages.append(page)
                logger.info(f"📂 기존 first 크롤링 데이터 로드: {len(self.existing_urls)}개 URL")
            except Exception as e:
                logger.warning(f"기존 인덱스 로드 실패: {e}")

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

    def crawl_url(self, url: str, page_info: dict) -> bool:
        self.stats["total"] += 1
        if url in self.existing_urls:
            logger.info(f"⏭️  이미 크롤링된 URL - 건너뜀: {url}")
            self.stats["skipped"] += 1
            return False

        logger.info(f"크롤링 시작: {url}")

        try:
            headers = {'User-Agent': 'KITBot/2.0'}
            # [Update] session.get 사용
            response = self.session.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            html = response.text

            is_quality, reason = self.quality_filter.is_high_quality(html, url)
            if not is_quality:
                logger.warning(f"품질 필터 실패: {reason}")
                self.stats["filtered"] += 1
                return False

            html_with_tables = self._convert_tables_to_text(html)
            content_data = self.content_extractor.extract_with_metadata(html_with_tables)
            attachments = self._process_attachments(url, html)

            page_type = page_info.get("page_type", "static_intro")
            if page_type == "static_intro":
                board_name = content_data["title"] or page_info["name"]
                title = page_info["name"]
                display_title = title
            else:
                board_name = page_info.get("board_name") or page_info["name"]
                title = content_data["title"] or page_info["name"]
                display_title = title           

            author, view_count, created_at = None, None, None
            if "board_notice" in page_type or "latest" in page_info["name"]:
                try:
                    soup = BeautifulSoup(html, "html.parser")
                    el_author = soup.find(text="작성자")
                    if el_author and el_author.parent: author = el_author.parent.find_next().get_text(strip=True)
                    el_view = soup.find(text="조회")
                    if el_view and el_view.parent:
                        view_count = el_view.parent.find_next().get_text(strip=True)
                        view_count = int(view_count) if view_count.isdigit() else None
                    el_date = soup.find(text="작성일")
                    if el_date and el_date.parent:
                        created_raw = el_date.parent.find_next().get_text(strip=True)
                        created_at = created_raw.replace('.', '-').strip()
                        try: created_at = datetime.strptime(created_at, "%Y-%m-%d").isoformat()
                        except: created_at = None
                except: pass

            metadata = {
                "text_length": len(content_data['text']), "word_count": content_data['word_count'], "title": title,
                "board_name": board_name, "display_title": display_title, "paragraphs": content_data['paragraphs'],
                "link_count": len(content_data['links']), "attachments_count": len(attachments), "attachments": attachments,
                "images": content_data['images'], "quality_check": reason, "crawled_at": datetime.now().isoformat(),
                "source_url": url, "page_type": page_type, "name": page_info["name"],
                "author": author, "view_count": view_count, "created_at": created_at,
            }

            filepath = self.storage.save_page(url, html, metadata)
            self.saved_pages.append({"url": url, "file": filepath, "title": content_data['title'], "text_length": len(content_data['text']), "page_type": metadata["page_type"]})
            self.existing_urls.add(url)
            self.stats["success"] += 1
            logger.info(f"✅ 저장 완료: {Path(filepath).name}")
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
        attachments = []
        try:
            soup = BeautifulSoup(html, 'html.parser')
            for link in soup.find_all('a', href=True):
                href = link['href']
                link_text = link.get_text(strip=True)
                is_download = ('mode=download' in href or 'download' in href.lower() or any(href.lower().endswith(x) for x in ['.pdf','.hwp','.docx','.xlsx','.zip']))
                if any(p in href for p in exclude_patterns): is_download = False
                if not is_download: continue

                abs_url = urllib.parse.urljoin(page_url, href)
                self.stats["attachments_found"] += 1
                att_info = {"page_url": page_url, "link_text": link_text, "download_url": abs_url, "detected_at": datetime.now().isoformat()}

                if self.enable_minio and self.minio:
                    try:
                        headers = {'User-Agent': 'KITBot/2.0', 'Referer': page_url}
                        resp = self.session.get(abs_url, headers=headers, timeout=30)
                        resp.raise_for_status()
                        
                        content_type = resp.headers.get('Content-Type', '').split(';')[0].strip()
                        content_disp = resp.headers.get('Content-Disposition', '')
                        if 'filename=' in content_disp: filename = content_disp.split('filename=')[-1].strip('"\'')
                        else:
                            filename = abs_url.split('/')[-1].split('?')[0]
                            if not filename or '.' not in filename: filename = link_text if '.' in link_text else f"attachment_{hashlib.md5(abs_url.encode()).hexdigest()[:8]}.bin"
                        try: filename = urllib.parse.unquote(filename)
                        except: pass
                        filename = fix_text(filename)
                        
                        # [Update] 확장자 보정
                        if filename.lower().endswith('.do') or '.' not in filename:
                            guessed_ext = mimetypes.guess_extension(content_type)
                            if guessed_ext:
                                if guessed_ext == '.jpe': guessed_ext = '.jpg'
                                filename = Path(filename).stem + guessed_ext

                        clean_name = filename.replace('/', '_').replace('\\', '_')
                        obj_name = f"attachments/{clean_name}"
                        
                        success, res = self.minio.upload_file(resp.content, obj_name, content_type, metadata={"source_url": abs_url, "original_filename": filename})
                        if success:
                            att_info.update({"minio_url": res, "minio_object": obj_name, "filename": clean_name, "status": "uploaded"})
                            self.stats["attachments_uploaded"] += 1
                            logger.info(f"   📎 첨부파일 업로드: {clean_name}")
                        else: att_info.update({"status": "upload_failed", "error": res})
                    except Exception as e: att_info.update({"status": "download_failed", "error": str(e)})
                else: att_info["status"] = "metadata_only"
                attachments.append(att_info)

            image_exts = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg']
            for img in soup.find_all('img', src=True):
                src, alt = img['src'], img.get('alt', '').strip()
                if any(k in src for k in ICON_IMAGE_KEYWORDS): continue
                
                src_no_query = src.split('?', 1)[0].lower()
                is_image = any(src_no_query.endswith(ext) for ext in image_exts)
                is_editor = 'editorimage.do' in src_no_query
                if not (is_image or is_editor): continue

                abs_url = urllib.parse.urljoin(page_url, src)
                self.stats["attachments_found"] += 1
                att_info = {"page_url": page_url, "link_text": alt, "download_url": abs_url, "type": "image"}
                
                if self.enable_minio and self.minio:
                    try:
                        resp = self.session.get(abs_url, headers={'User-Agent': 'KITBot/2.0'}, timeout=30)
                        content_type = resp.headers.get('Content-Type', '').split(';')[0].strip()
                        fname = abs_url.split('/')[-1].split('?')[0] or "image.jpg"
                        
                        if fname.lower().endswith('.do') or '.' not in fname:
                            guessed_ext = mimetypes.guess_extension(content_type)
                            if guessed_ext: fname = Path(fname).stem + guessed_ext
                            else: fname = Path(fname).stem + ".jpg"
                        
                        clean_name = fname.replace('/', '_')
                        obj_name = f"images/{clean_name}"
                        success, res = self.minio.upload_file(resp.content, obj_name, content_type, metadata={"source_url": abs_url, "alt_text": alt, "original_filename": fname})
                        if success:
                            att_info.update({"minio_url": res, "minio_object": obj_name, "filename": clean_name, "status": "uploaded"})
                            self.stats["attachments_uploaded"] += 1
                            logger.info(f"   🖼 이미지 업로드: {clean_name}")
                    except Exception as e: att_info.update({"status": "download_failed", "error": str(e)})
                else: att_info["status"] = "metadata_only"
                attachments.append(att_info)
        except Exception as e: logger.error(f"❌ 첨부파일 처리 에러: {e}")
        return attachments

    def crawl_latest_from_department_board(self, board_info):
        url = board_info["url"]
        name = board_info["name"]
        logger.info(f"\n📘 [교육과정] {name}: {url}")
        try:
            headers = {'User-Agent': 'KITBot/2.0 (CSEcapstone)'}
            response = self.session.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            article_links = []
            for link in soup.find_all('a', href=True):
                href = link['href']
                if ('mode=view' in href) or ('articleNo' in href):
                    if href.startswith('/'):
                        site_root = url.split('/', 3)[:3]
                        base = "/".join(site_root)
                        full = base + href
                    elif href.startswith('?'): full = url.split('?')[0] + href
                    else: full = url.rsplit('/', 1)[0] + '/' + href
                    article_links.append(full)

            if not article_links:
                logger.warning(f"❌ 게시글을 찾지 못함: {url}")
                return False

            latest_url = article_links[0]
            logger.info(f"   📌 최신 게시글: {latest_url}")
            if latest_url in self.existing_urls:
                logger.info(f"   ⏭️ 최신 게시글 이미 크롤링됨 → 스킵")
                self.stats["skipped"] += 1
                return False

            page_info = {"url": latest_url, "name": f"{name} (최신 게시글)", "page_type": "board_notice", "board_name": name}
            success = self.crawl_url(latest_url, page_info)
            if success: self.existing_urls.add(latest_url)
            return success
        except Exception as e:
            logger.error(f"❌ 교육과정 게시판 최신글 크롤링 실패: {e}")
            return False

    def run(self):
        print("=" * 80); print("departmentCrawler 시작"); print("=" * 80)
        start_time = datetime.now()
        for page in self.department_static_urls:
            print(f"\n📍 대상 사이트 이름 : [{page['name']}]")
            print("-" * 80)
            self.crawl_url(page['url'], page)
            import time; time.sleep(0.5)

        print("\n" + "=" * 80); print("📘 학과별 교육과정 게시판 최신글 크롤링"); print("=" * 80)
        for board in self.department_board_urls:
            print(f"\n📍 대상 게시판 이름 : [{board['name']}]")
            print("-" * 80)
            self.crawl_latest_from_department_board(board)
            import time; time.sleep(0.5)

        if self.saved_pages:
            index_data = {"crawl_date": datetime.now().isoformat(), "total_pages": len(self.saved_pages), "pages": self.saved_pages}
            self.storage.save_index(index_data)
        
        print("\n" + "=" * 80); print("departmentCrawler 크롤링 완료!")

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--enable-minio', action='store_true')
    parser.add_argument('--output-dir', type=str)
    args = parser.parse_args()
    out = Path(args.output_dir) if args.output_dir else None
    departmentCrawler(args.enable_minio, out).run()

if __name__ == "__main__":
    main()