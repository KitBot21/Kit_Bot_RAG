"""
핵심 본문만 추출하는 고급 필터
메뉴, 헤더, 푸터, 광고 등 불필요한 요소 제거
"""
from bs4 import BeautifulSoup, Comment
import re

class ContentExtractor:
    """HTML에서 핵심 본문만 스마트하게 추출"""
    
    # 제거할 태그 목록
    REMOVE_TAGS = [
        'script', 'style', 'noscript', 'iframe',
        'nav', 'header', 'footer', 'aside',
        'form', 'button', 'input', 'select', 'textarea',
    ]
    
    # 제거할 클래스/ID 패턴 (정규식)
    REMOVE_PATTERNS = [
        r'nav', r'sidebar', r'header', r'footer',
        r'breadcrumb', r'share', r'social', r'comment',
        r'ad', r'advertisement', r'banner', r'popup',
        r'login', r'search', r'pagination', r'paging',
        r'related', r'recommend', r'popular', r'recent',
        r'copyright', r'privacy', r'terms',
        r'gnb', r'lnb', r'snb',  # 한국 웹사이트용
        r'top-menu', r'bottom-menu', r'side-menu',
        r'util-menu', r'quick-menu', r'floating',
        r'footer-wrapper',
    ]
    
    # 본문일 가능성이 높은 클래스/ID 패턴
    CONTENT_PATTERNS = [
        r'content', r'article', r'main', r'body',
        r'post', r'entry', r'text', r'detail',
        r'board', r'notice', r'view',  # 한국 게시판용
    ]
    
    def __init__(self, keep_links=True, keep_images=False):
        """
        Args:
            keep_links: 링크 텍스트 유지 (True) vs 제거 (False)
            keep_images: 이미지 alt 텍스트 유지
        """
        self.keep_links = keep_links
        self.keep_images = keep_images
    
    def extract_clean_text(self, html: str) -> str:
        """
        HTML에서 핵심 본문만 추출
        
        Args:
            html: 원본 HTML
        
        Returns:
            정제된 텍스트
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        # 1단계: 명백히 불필요한 요소 제거
        self._remove_unnecessary_elements(soup)
        
        # 2단계: 본문 영역 찾기
        main_content = self._find_main_content(soup)
        
        if main_content:
            soup = main_content
        
        # 3단계: 패턴 기반 제거
        self._remove_by_patterns(soup)
        
        # 4단계: 링크/이미지 처리
        if not self.keep_links:
            for a in soup.find_all('a'):
                a.unwrap()  # 링크만 제거, 텍스트 유지
        
        if not self.keep_images:
            for img in soup.find_all('img'):
                img.decompose()
        
        # 5단계: 텍스트 추출 및 정제
        text = soup.get_text(separator='\n', strip=True)
        text = self._clean_text(text)
        
        return text
    
    def _remove_unnecessary_elements(self, soup: BeautifulSoup):
        """명백히 불필요한 요소 제거"""
        
        # 1. 특정 태그 제거
        for tag_name in self.REMOVE_TAGS:
            for tag in soup.find_all(tag_name):
                tag.decompose()
        
        # 2. HTML 주석 제거
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()
        
        # 3. 숨겨진 요소 제거
        for tag in soup.find_all(style=re.compile(r'display\s*:\s*none', re.I)):
            tag.decompose()
        
        for tag in soup.find_all(attrs={'hidden': True}):
            tag.decompose()
    
    def _find_main_content(self, soup: BeautifulSoup):
        """본문 영역 찾기 (휴리스틱)"""
        
        # 0순위: 금오공대 CMS 전용 - jwxe_main_content가 여러 개 있을 때 처리
        jwxe_candidates = soup.find_all(id='jwxe_main_content')
        if jwxe_candidates:
            def score(el):
                # main 태그는 패널/레이아웃일 가능성이 높으니 약간 패널티
                penalty = 1000 if el.name == 'main' else 0
                return len(el.get_text(strip=True)) - penalty

            best = max(jwxe_candidates, key=score)
            return best

        # 1순위: <main> 태그
        main = soup.find('main')
        if main:
            return main
        
        # 2순위: <article> 태그
        article = soup.find('article')
        if article:
            return article
        
        # 3순위: role="main" 속성
        role_main = soup.find(attrs={'role': 'main'})
        if role_main:
            return role_main
        
        # 4순위: 본문 패턴이 있는 div (가장 큰 것)
        content_divs = []
        for pattern in self.CONTENT_PATTERNS:
            regex = re.compile(pattern, re.I)
            for div in soup.find_all(['div', 'section'], class_=regex):
                content_divs.append(div)
            for div in soup.find_all(['div', 'section'], id=regex):
                content_divs.append(div)
        
        if content_divs:
            # 텍스트가 가장 많은 div 선택
            return max(content_divs, key=lambda d: len(d.get_text(strip=True)))
        
        # 못 찾으면 전체 body 사용
        return soup.find('body') or soup
    
    def _remove_by_patterns(self, soup: BeautifulSoup):
        """패턴 기반 불필요한 요소 제거"""
        
        for pattern in self.REMOVE_PATTERNS:
            regex = re.compile(pattern, re.I)
            
            # class 속성 매칭
            for tag in soup.find_all(class_=regex):
                tag.decompose()
            
            # id 속성 매칭
            for tag in soup.find_all(id=regex):
                tag.decompose()
    
    def _clean_text(self, text: str) -> str:
        """텍스트 후처리"""
        
        # 1. 연속된 공백/줄바꿈 정리
        text = re.sub(r'\n\s*\n+', '\n\n', text)  # 3개 이상 줄바꿈 -> 2개
        text = re.sub(r' +', ' ', text)  # 연속 공백 -> 1개
        
        # 2. 앞뒤 공백 제거
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(line for line in lines if line)
        
        # 3. 특수문자 정리 (선택적)
        # text = re.sub(r'[^\w\s가-힣.,!?()[\]{}\-:;"\']', '', text)
        
        return text.strip()
    
    def extract_with_metadata(self, html: str) -> dict:
        """
        텍스트와 함께 메타데이터도 추출
        
        Returns:
            {
                'text': '본문',
                'title': '제목',
                'paragraphs': 10,
                'links': [...],
                'images': [...]
            }
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        # 제목 추출
        title = ''
        if soup.title:
            title = soup.title.get_text(strip=True)
        elif soup.h1:
            title = soup.h1.get_text(strip=True)
        
        # 링크 수집
        links = []
        for a in soup.find_all('a', href=True):
            links.append({
                'text': a.get_text(strip=True),
                'href': a['href']
            })
        
        main_area = self._find_main_content(soup)

        # 이미지 수집
        images = []
        for img in main_area.find_all('img', src=True):
            images.append({
                'src': img['src'],
                'alt': img.get('alt', '')
            })
        
        # 본문 추출
        clean_text = self.extract_clean_text(html)
        
        # 문단 수
        paragraphs = len([p for p in clean_text.split('\n\n') if p.strip()])
        
        return {
            'text': clean_text,
            'title': title,
            'paragraphs': paragraphs,
            'links': links[:10],  # 상위 10개만
            'images': images[:10],  # 상위 5개만
            'char_count': len(clean_text),
            'word_count': len(clean_text.split()),
        }


# 편의 함수
def extract_clean_text(html: str, keep_links=True) -> str:
    """간단한 사용을 위한 헬퍼 함수"""
    extractor = ContentExtractor(keep_links=keep_links)
    return extractor.extract_clean_text(html)


# 테스트용
if __name__ == "__main__":
    sample_html = """
    <!DOCTYPE html>
    <html>
    <head><title>테스트 페이지</title></head>
    <body>
        <header>
            <nav class="gnb">
                <ul>
                    <li>메뉴1</li>
                    <li>메뉴2</li>
                </ul>
            </nav>
        </header>
        
        <div class="sidebar">
            광고 영역
        </div>
        
        <main>
            <article>
                <h1>본문 제목</h1>
                <p>이것은 실제 본문 내용입니다. 중요한 정보가 담겨있습니다.</p>
                <p>두 번째 문단입니다. 더 많은 정보가 있습니다.</p>
            </article>
        </main>
        
        <footer>
            <p>Copyright 2025</p>
        </footer>
    </body>
    </html>
    """
    
    extractor = ContentExtractor()
    clean = extractor.extract_clean_text(sample_html)
    
    print("=== 추출된 본문 ===")
    print(clean)
    print("\n=== 메타데이터 포함 ===")
    print(extractor.extract_with_metadata(sample_html))