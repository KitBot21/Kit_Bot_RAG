"""
JSON 포맷으로 크롤링 데이터 저장
→ 모든 JSON을 '정규화된 문서' 형태로 저장
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Optional
import hashlib
from urllib.parse import urlparse, parse_qs


def _guess_site_from_url(url: str) -> str:
    """
    URL에서 site 코드 추출
    예) https://bus.kumoh.ac.kr/...  → 'bus'
        https://mobility.kumoh.ac.kr/... → 'mobility'
    """
    parsed = urlparse(url)
    host = (parsed.hostname or "")
    parts = host.split(".")
    if len(parts) >= 3 and parts[-2:] == ["ac", "kr"]:
        return parts[0]
    return host or ""


def _slug_from_path(path: str) -> str:
    """
    /smartmobility/sub0301.do → smartmobility_sub0301
    /bus/notice.do?mode=view → bus_notice
    """
    p = path.strip("/")
    if not p:
        return "root"
    slug = p.replace("/", "_")
    slug = slug.replace(".do", "").replace(".jsp", "")
    return slug


class JSONStorage:
    def __init__(self, output_dir: Path, pretty_print: bool = False):
        """
        Args:
            output_dir: JSON 파일 저장 디렉토리
            pretty_print: JSON을 보기 좋게 포맷팅할지 여부
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.pretty_print = pretty_print
        
        # 전체 데이터를 담을 파일
        self.index_file = self.output_dir / "crawl_index.json"
        self.pages_dir = self.output_dir / "pages"
        self.pages_dir.mkdir(exist_ok=True)

    # ---------------- 정규화 문서 빌더 ---------------- #

    def _build_normalized_doc(
        self,
        url: str,
        title: str,
        text: str,
        metadata: dict,
        crawled_at: str,
    ) -> dict:
        """
        모든 크롤링 결과를 두 번째 예시 형태의 '정규화 문서'로 변환
        """
        parsed = urlparse(url)
        site = metadata.get("site") or _guess_site_from_url(url)
        page_type = metadata.get("page_type", "page")  # 기본값: 일반 페이지

        # 공통 필드 초기값
        doc = {
            "doc_id": None,
            "source_type": None,           # "board" or "page" 등
            "site": site,
            "board_name": metadata.get("board_name"),
            "title": metadata.get("title"),
            "display_title": metadata.get("display_title") or metadata.get("title"),
            "author": metadata.get("author"),
            "url": url,
            "created_at": metadata.get("created_at"),
            "updated_at": metadata.get("updated_at"),
            "has_explicit_date": bool(metadata.get("created_at")),
            "view_count": metadata.get("view_count"),
            "doc_type": "html",
            "main_text": text,
            "attachments": metadata.get("attachments", []),
            "images": metadata.get("images", []),
            "crawled_at": crawled_at,
        }

        # 1) 게시판 타입 (공지/뉴스 등) → bus_notice_514537 같은 doc_id
        if page_type == "board_notice":
            qs = parse_qs(parsed.query)
            article_no = qs.get("articleNo", [""])[0]
            if article_no:
                doc["doc_id"] = f"{site}_notice_{article_no}"
            else:
                slug = _slug_from_path(parsed.path)
                doc["doc_id"] = f"{site}_notice_{slug}"
            doc["source_type"] = "board"

        # 2) 그 외(정적 페이지 / 일반 HTML 페이지)
        else:
            slug = _slug_from_path(parsed.path)
            doc["doc_id"] = f"{site}_page_{slug}"
            doc["source_type"] = "page"

            # 텍스트가 거의 없고 이미지만 있는 페이지는 타입 구분
            if not text and metadata.get("images"):
                doc["doc_type"] = "image_html"

        return doc

    # ---------------- 실제 저장 함수 ---------------- #

    def save_page(
        self,
        url: str,
        html: str,
        metadata: dict = None,
        extracted_text: str = None,
        title: str = None,
    ) -> str:
        """
        페이지를 JSON(정규화 문서)으로 저장
        
        Args:
            url: 페이지 URL
            html: HTML 콘텐츠
            metadata: 추가 메타데이터
            extracted_text: 이미 추출된 텍스트 (있으면 재추출 안함)
            title: 이미 추출된 제목
        
        Returns:
            저장된 파일 경로
        """
        # URL 기반 파일명 생성
        url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
        filename = f"{url_hash}.json"
        filepath = self.pages_dir / filename

        # 텍스트/제목 없으면 추출
        if extracted_text is None:
            from filters.content_extractor import ContentExtractor
            extractor = ContentExtractor(keep_links=True, keep_images=False)
            content_data = extractor.extract_with_metadata(html)
            text = content_data["text"]
            title_text = content_data["title"]
        else:
            text = extracted_text
            title_text = title if title else "제목 없음"

        crawled_at = datetime.now().isoformat()

        # 메타데이터 정리
        meta = metadata.copy() if metadata else {}
        meta.setdefault("title", title_text)
        meta.setdefault("text_length", len(text))
        meta.setdefault("word_count", len(text.split()) if text else 0)
        meta.setdefault("crawled_at", crawled_at)
        meta.setdefault("source_url", url)

        # 🔹 여기서 최종 정규화 문서 생성 (두 번째 JSON 형태)
        doc = self._build_normalized_doc(
            url=url,
            title=title_text,
            text=text,
            metadata=meta,
            crawled_at=crawled_at,
        )

        # JSON 저장
        with open(filepath, "w", encoding="utf-8") as f:
            if self.pretty_print:
                json.dump(doc, f, ensure_ascii=False, indent=2)
            else:
                json.dump(doc, f, ensure_ascii=False)
        
        return str(filepath)
    
    def save_index(self, index_data):
        """
        크롤링된 모든 페이지의 인덱스 저장
        
        Args:
            index_data: dict 또는 list
                - dict면 그대로 저장 (meta 정보 포함 가능)
                - list면 pages로 감싸서 저장 (하위 호환성)
        """
        # 하위 호환성: list가 오면 dict로 변환
        if isinstance(index_data, list):
            index_data = {
                "crawl_date": datetime.now().isoformat(),
                "total_pages": len(index_data),
                "pages": index_data
            }
        
        with open(self.index_file, 'w', encoding='utf-8') as f:
            if self.pretty_print:
                json.dump(index_data, f, ensure_ascii=False, indent=2)
            else:
                json.dump(index_data, f, ensure_ascii=False)
    
    def load_page(self, filepath: str) -> Optional[dict]:
        """JSON 파일에서 정규화된 문서 로드"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None
    
    def load_index(self) -> Optional[dict]:
        """인덱스 파일 로드"""
        if not self.index_file.exists():
            return None
        
        try:
            with open(self.index_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None
