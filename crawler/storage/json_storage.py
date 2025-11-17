"""
JSON 포맷으로 크롤링 데이터 저장
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Optional
import hashlib

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
    
    def save_page(self, url: str, html: str, metadata: dict = None, extracted_text: str = None, title: str = None) -> str:
        """
        페이지를 JSON으로 저장
        
        Args:
            url: 페이지 URL
            html: HTML 콘텐츠
            metadata: 추가 메타데이터
            extracted_text: 이미 추출된 텍스트 (선택사항, 제공시 재추출 안함)
            title: 이미 추출된 제목 (선택사항)
        
        Returns:
            저장된 파일 경로
        """
        # URL 기반 파일명 생성
        url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
        filename = f"{url_hash}.json"
        filepath = self.pages_dir / filename
        
        # 제공된 텍스트가 없으면 추출
        if extracted_text is None:
            # 고급 본문 추출기 사용 (메뉴, 헤더, 푸터 등 제거)
            from filters.content_extractor import ContentExtractor
            extractor = ContentExtractor(keep_links=True, keep_images=False)
            content_data = extractor.extract_with_metadata(html)
            
            text = content_data['text']
            title_text = content_data['title']
        else:
            text = extracted_text
            title_text = title if title else "제목 없음"
        
        # JSON 데이터 구조
        data = {
            "url": url,
            "title": title_text,
            "text": text,
            "html": html,  # 원본 HTML도 저장 (필요시)
            "crawled_at": datetime.now().isoformat(),
            "metadata": metadata or {},
        }
        
        # JSON 저장
        with open(filepath, 'w', encoding='utf-8') as f:
            if self.pretty_print:
                json.dump(data, f, ensure_ascii=False, indent=2)
            else:
                json.dump(data, f, ensure_ascii=False)
        
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
        """JSON 파일에서 페이지 로드"""
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
