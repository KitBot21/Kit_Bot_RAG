"""
고품질 페이지 필터링
- 너무 짧은 페이지 제외
- 에러 페이지 감지
- 실질적 내용 유무 판단
"""
from bs4 import BeautifulSoup
import re

class QualityFilter:
    def __init__(self, 
                 min_text_length=100,
                 max_text_length=500000,
                 min_word_count=20,
                 skip_patterns=None):
        """
        Args:
            min_text_length: 최소 텍스트 길이 (문자)
            max_text_length: 최대 텍스트 길이 (문자)
            min_word_count: 최소 단어 수
            skip_patterns: 스킵할 패턴 리스트
        """
        self.min_text_length = min_text_length
        self.max_text_length = max_text_length
        self.min_word_count = min_word_count
        
        # 에러 패턴 (더 정확한 패턴 사용)
        self.skip_patterns = skip_patterns or [
            "404 Not Found",
            "404 error",
            "페이지를 찾을 수 없습니다",
            "요청하신 페이지가 존재하지 않습니다",
            "접근 권한이 없습니다",
            "Access Denied",
            "로그인이 필요합니다",
            "세션이 만료되었습니다",
        ]
    
    def is_high_quality(self, html: str, url: str = "") -> tuple[bool, str]:
        """
        페이지가 고품질인지 판단
        
        Returns:
            (is_quality, reason) 튜플
        """
        try:
            soup = BeautifulSoup(html, "html.parser")
            
            # 본문 텍스트 추출
            # script, style 태그 제거
            for tag in soup(['script', 'style', 'nav', 'header', 'footer']):
                tag.decompose()
            
            text = soup.get_text(separator=' ', strip=True)
            
            # 1. 길이 체크
            if len(text) < self.min_text_length:
                return False, f"Too short: {len(text)} chars"
            
            if len(text) > self.max_text_length:
                return False, f"Too long: {len(text)} chars"
            
            # 2. 단어 수 체크
            words = re.findall(r'\S+', text)
            if len(words) < self.min_word_count:
                return False, f"Too few words: {len(words)}"
            
            # 3. 에러 페이지 감지
            for pattern in self.skip_patterns:
                if pattern.lower() in text.lower():
                    return False, f"Error pattern detected: {pattern}"
            
            # 4. 제목 존재 여부
            title = soup.find('title')
            if not title or len(title.get_text(strip=True)) < 2:
                return False, "No valid title"
            
            # 5. 실질적 내용 비율 체크
            # 전체 텍스트 대비 공백/반복 문자 비율
            non_whitespace = len(text.replace(' ', '').replace('\n', ''))
            if non_whitespace < self.min_text_length * 0.5:
                return False, "Too much whitespace"
            
            return True, "OK"
            
        except Exception as e:
            return False, f"Parse error: {str(e)}"
    
    def extract_metadata(self, html: str) -> dict:
        """메타데이터 추출 (JSON 저장용)"""
        try:
            soup = BeautifulSoup(html, "html.parser")
            
            # script, style 제거
            for tag in soup(['script', 'style', 'nav', 'header', 'footer']):
                tag.decompose()
            
            text = soup.get_text(separator=' ', strip=True)
            
            return {
                "text_length": len(text),
                "word_count": len(re.findall(r'\S+', text)),
                "has_title": bool(soup.find('title')),
                "title": soup.find('title').get_text(strip=True) if soup.find('title') else "",
                "has_main": bool(soup.find(['main', 'article'])),
                "image_count": len(soup.find_all('img')),
                "link_count": len(soup.find_all('a')),
            }
        except Exception:
            return {}