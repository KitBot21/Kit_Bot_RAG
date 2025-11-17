#!/usr/bin/env python3
"""
본문 추출기 테스트 (로컬 HTML 파일 사용)
"""
import sys
sys.path.insert(0, '/home/jhlee/Kit_Bot_RAG/crawler')

from filters.content_extractor import ContentExtractor
from pathlib import Path

# 로컬 HTML 파일 사용
html_files = [
    "/home/jhlee/Kit_Bot_RAG/data/fixtures/bus__notice.do__8e6e5ebafc74f983.html",
    "/home/jhlee/Kit_Bot_RAG/data/fixtures/dorm__restaurant_menu_reg.do__0163142bed36d88e.html",
]

print("="*80)
print("본문 추출기 테스트 (로컬 파일)")
print("="*80)

for filepath in html_files:
    if not Path(filepath).exists():
        print(f"⚠️  파일 없음: {filepath}")
        continue
        
    print(f"\n📄 파일: {Path(filepath).name}")
    print("-"*80)
    
    try:
        # HTML 읽기
        with open(filepath, 'r', encoding='utf-8') as f:
            html = f.read()
        
        # HTML 읽기
        with open(filepath, 'r', encoding='utf-8') as f:
            html = f.read()
        
        # 1. 기존 방식
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        for tag in soup(['script', 'style', 'nav', 'header', 'footer']):
            tag.decompose()
        old_text = soup.get_text(separator='\n', strip=True)
        
        # 2. 새로운 방식 (고급 추출)
        extractor = ContentExtractor(keep_links=True, keep_images=False)
        new_data = extractor.extract_with_metadata(html)
        new_text = new_data['text']
        
        # 비교
        print(f"\n[기존 방식]")
        print(f"  길이: {len(old_text):,} 문자")
        print(f"  미리보기:\n{old_text[:300]}...\n")
        
        print(f"[새로운 방식 - 핵심 본문만]")
        print(f"  길이: {len(new_text):,} 문자")
        print(f"  제목: {new_data['title']}")
        print(f"  문단 수: {new_data['paragraphs']}")
        print(f"  링크 수: {len(new_data['links'])}")
        print(f"  미리보기:\n{new_text[:300]}...\n")
        
        # 개선율
        reduction = ((len(old_text) - len(new_text)) / len(old_text) * 100) if len(old_text) > 0 else 0
        print(f"✨ 불필요한 내용 제거율: {reduction:.1f}%")
        
        # 전체 본문 출력 (선택적)
        if len(sys.argv) > 1 and sys.argv[1] == '--full':
            print("\n" + "="*80)
            print("완전한 본문:")
            print("="*80)
            print(new_text)
            print("\n" + "="*80)
        
    except Exception as e:
        print(f"❌ 에러: {e}")

print("\n" + "="*80)
print("테스트 완료!")
print("="*80)
print("\n💡 전체 본문을 보려면: python3 scripts/test_content_extraction.py --full")
