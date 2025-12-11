#!/usr/bin/env python3
"""
통합 크롤링 데이터로부터 코퍼스 생성
data/crawled_data/ → data/corpus.csv
"""
import json
import csv
import re
from pathlib import Path
from typing import List, Dict

# 설정
CRAWLED_DIR = Path("data/crawled_data/pages")
OUT_CSV = Path("data/corpus.csv")
CHUNK_SIZE = 1000  # 청크 크기 (문자)
OVERLAP = 150      # 오버랩 (문자)

# 불필요한 텍스트 패턴
NOISE_PATTERNS = [
    r'공지사항.*?바로가기',
    r'다음\s*페이지',
    r'이전\s*페이지',
    r'페이지\s*이동',
    r'목록으로',
    r'top\s*↑',
    r'맨\s*위로',
    r'Home\s*›',
    r'sitemap',
    r'copyright.*?all\s+rights\s+reserved',
    r'개인정보처리방침',
    r'이메일무단수집거부',
    r'\[\s*인쇄\s*\]',
    r'\[\s*목록\s*\]',
    r'\s{3,}',  # 3개 이상 연속 공백
]

def clean_text(text: str) -> str:
    """텍스트 정제"""
    if not text:
        return ""
    
    # 노이즈 패턴 제거
    for pattern in NOISE_PATTERNS:
        text = re.sub(pattern, ' ', text, flags=re.IGNORECASE)
    
    # 연속 공백 정리
    text = re.sub(r'\s+', ' ', text)
    
    # 앞뒤 공백 제거
    text = text.strip()
    
    return text

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = OVERLAP) -> List[str]:
    """텍스트를 청크로 분할"""
    if len(text) <= chunk_size:
        return [text] if text.strip() else []
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        
        # 마지막 청크가 아니면 문장 경계에서 자르기
        if end < len(text):
            # 마침표, 느낌표, 물음표로 끝나는 위치 찾기
            last_period = max(
                chunk.rfind('.'),
                chunk.rfind('!'),
                chunk.rfind('?'),
                chunk.rfind('。')
            )
            
            if last_period > chunk_size * 0.5:  # 청크의 절반 이상이면 사용
                end = start + last_period + 1
                chunk = text[start:end]
        
        chunk = chunk.strip()
        if chunk:
            chunks.append(chunk)
        
        # 다음 시작점 (오버랩 적용)
        start = end - overlap
        
        # 무한 루프 방지
        if start <= 0 or start >= len(text):
            break
    
    return chunks

def create_corpus():
    """크롤링 데이터로부터 코퍼스 생성"""
    print("=" * 80)
    print("📝 코퍼스 생성")
    print("=" * 80)
    
    if not CRAWLED_DIR.exists():
        print(f"❌ 크롤링 데이터 폴더가 없습니다: {CRAWLED_DIR}")
        return
    
    json_files = list(CRAWLED_DIR.glob("*.json"))
    print(f"\n📂 입력: {CRAWLED_DIR}/")
    print(f"   JSON 파일: {len(json_files)}개")
    
    print(f"\n📄 출력: {OUT_CSV}")
    print(f"   청크 크기: {CHUNK_SIZE}자")
    print(f"   오버랩: {OVERLAP}자")
    
    # CSV 파일 생성
    rows = []
    stats = {
        'total_pages': 0,
        'total_chunks': 0,
        'skipped_empty': 0,
        'skipped_short': 0,
    }
    
    print(f"\n⏳ 처리 중...")
    
    for json_file in sorted(json_files):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            url = data.get('url', '')
            title = data.get('title', '')
            text = data.get('text', '')
            metadata = data.get('metadata', {})
            
            # 텍스트 정제
            clean = clean_text(text)
            
            if not clean:
                stats['skipped_empty'] += 1
                continue
            
            if len(clean) < 50:  # 너무 짧은 텍스트 제외
                stats['skipped_short'] += 1
                continue
            
            # 청크 분할
            chunks = chunk_text(clean)
            
            for i, chunk in enumerate(chunks):
                row = {
                    'id': f"{json_file.stem}_chunk{i}",
                    'url': url,
                    'title': title,
                    'text': chunk,
                    'chunk_index': i,
                    'total_chunks': len(chunks),
                    'source': metadata.get('source', 'unknown'),
                    'domain': metadata.get('domain', ''),
                }
                
                # 첨부파일 정보 추가
                if 'attachments_count' in metadata:
                    row['attachments_count'] = metadata['attachments_count']
                
                rows.append(row)
            
            stats['total_pages'] += 1
            stats['total_chunks'] += len(chunks)
            
            if stats['total_pages'] % 50 == 0:
                print(f"   처리 중: {stats['total_pages']}개 페이지, {stats['total_chunks']}개 청크")
        
        except Exception as e:
            print(f"   ⚠️  {json_file.name}: {e}")
    
    # CSV 저장
    if rows:
        fieldnames = ['id', 'url', 'title', 'text', 'chunk_index', 'total_chunks', 
                      'source', 'domain', 'attachments_count']
        
        with open(OUT_CSV, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        print(f"\n✅ 코퍼스 생성 완료!")
    else:
        print(f"\n❌ 생성된 청크가 없습니다.")
    
    # 통계
    print("\n" + "=" * 80)
    print("📊 통계")
    print("=" * 80)
    print(f"총 페이지: {stats['total_pages']}개")
    print(f"총 청크: {stats['total_chunks']}개")
    print(f"페이지당 평균 청크: {stats['total_chunks'] / stats['total_pages']:.1f}개")
    print(f"건너뛴 페이지:")
    print(f"  - 빈 텍스트: {stats['skipped_empty']}개")
    print(f"  - 너무 짧음: {stats['skipped_short']}개")
    print("=" * 80)

def main():
    create_corpus()

if __name__ == "__main__":
    main()
