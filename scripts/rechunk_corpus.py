#!/usr/bin/env python3
"""
기존 MinIO corpus 파일에 청킹 + 필터링 적용
"""

import csv
import sys
import re
from pathlib import Path
from typing import List

# CSV 필드 크기 제한 해제
csv.field_size_limit(sys.maxsize)

# 청킹 설정
CHUNK_SIZE = 1000
OVERLAP = 150
MIN_CHUNK_LENGTH = 100

# 필터링 패턴
FILTER_PATTERNS = [
    r'^\s*차\s*례\s*$',
    r'^\s*목\s*차\s*$',
    r'^\s*참고문헌\s*$',
    r'^\s*부\s*록\s*$',
    r'^\s*Copyright.*$',
    r'^\s*저작권.*$',
    r'^\s*All Rights Reserved.*$',
    r'^\s*페이지\s*\d+\s*$',
    r'^\s*\d+\s*$',
    r'^\s*-\s*\d+\s*-\s*$',
]

def clean_text(text: str) -> str:
    """텍스트 정제 및 불필요한 패턴 제거"""
    if not text:
        return ""
    
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        should_skip = False
        for pattern in FILTER_PATTERNS:
            if re.match(pattern, line.strip(), re.IGNORECASE):
                should_skip = True
                break
        
        if not should_skip and line.strip():
            cleaned_lines.append(line)
    
    text = '\n'.join(cleaned_lines)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\n\s*\n+', '\n', text)
    
    return text.strip()

def chunk_text(text: str) -> List[str]:
    """텍스트를 청크로 분할"""
    if len(text) <= CHUNK_SIZE:
        return [text] if text.strip() and len(text) >= MIN_CHUNK_LENGTH else []
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + CHUNK_SIZE
        chunk = text[start:end]
        
        if end < len(text):
            last_period = max(
                chunk.rfind('.'),
                chunk.rfind('!'),
                chunk.rfind('?'),
                chunk.rfind('。'),
                chunk.rfind('\n')
            )
            
            if last_period > CHUNK_SIZE * 0.5:
                end = start + last_period + 1
                chunk = text[start:end]
        
        chunk = chunk.strip()
        if chunk and len(chunk) >= MIN_CHUNK_LENGTH:
            chunks.append(chunk)
        
        start = end - OVERLAP
        if start <= 0 or start >= len(text):
            break
    
    return chunks

def process_corpus_file(input_file: Path, output_file: Path):
    """기존 corpus 파일에 청킹 + 필터링 적용"""
    print("=" * 80)
    print(f"📄 {input_file.name} 처리 중...")
    print("=" * 80)
    
    print(f"\n⚙️  설정:")
    print(f"   청크 크기: {CHUNK_SIZE}자")
    print(f"   오버랩: {OVERLAP}자")
    print(f"   최소 청크 길이: {MIN_CHUNK_LENGTH}자")
    
    if not input_file.exists():
        print(f"\n❌ 파일 없음: {input_file}")
        return
    
    # 원본 읽기
    with input_file.open('r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    print(f"\n📊 원본 문서: {len(rows)}개")
    
    # 텍스트 길이 분석
    text_lengths = [len(row.get('text', '')) for row in rows]
    avg_length = sum(text_lengths) / len(text_lengths) if text_lengths else 0
    max_length = max(text_lengths) if text_lengths else 0
    
    print(f"   평균 길이: {avg_length:,.0f}자")
    print(f"   최대 길이: {max_length:,}자")
    
    # 청킹 적용
    results = []
    total_chunks = 0
    skipped = 0
    
    print(f"\n⏳ 청킹 중...")
    
    for i, row in enumerate(rows, 1):
        if i % 200 == 0:
            print(f"   진행: {i}/{len(rows)} ({i/len(rows)*100:.0f}%)")
        
        text = row.get('text', '')
        
        # 텍스트 정제
        cleaned_text = clean_text(text)
        
        if not cleaned_text or len(cleaned_text) < MIN_CHUNK_LENGTH:
            skipped += 1
            continue
        
        # 청킹
        chunks = chunk_text(cleaned_text)
        
        if not chunks:
            skipped += 1
            continue
        
        # 각 청크를 개별 레코드로 저장
        for chunk_idx, chunk in enumerate(chunks):
            new_row = row.copy()
            new_row['text'] = chunk
            new_row['chunk_index'] = chunk_idx
            new_row['total_chunks'] = len(chunks)
            
            # document_name 업데이트
            if 'document_name' in new_row:
                original_name = new_row['document_name']
                new_row['document_name'] = f"{original_name}_chunk{chunk_idx}"
            
            results.append(new_row)
        
        total_chunks += len(chunks)
    
    print(f"\n✅ 처리 완료!")
    print(f"   원본 문서: {len(rows)}개")
    print(f"   제외: {skipped}개")
    print(f"   청크 생성: {total_chunks}개")
    print(f"   최종 레코드: {len(results)}개")
    
    # 저장
    if results:
        with output_file.open('w', encoding='utf-8', newline='') as f:
            fieldnames = results[0].keys()
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        
        print(f"\n💾 저장: {output_file}")
        
        # 통계
        chunk_lengths = [len(r['text']) for r in results]
        avg_chunk = sum(chunk_lengths) / len(chunk_lengths)
        
        print(f"\n📊 최종 통계:")
        print(f"   총 청크: {len(results):,}개")
        print(f"   평균 길이: {avg_chunk:.0f}자")
        print(f"   총 텍스트: {sum(chunk_lengths):,}자")
    
    print("\n" + "=" * 80)

def main():
    print("\n" + "=" * 80)
    print("🔧 Corpus 파일 청킹 + 필터링")
    print("=" * 80)
    
    # MinIO corpus
    minio_input = Path("data/corpus_minio_documents_old.csv")
    minio_output = Path("data/corpus_minio_documents.csv")
    
    if minio_input.exists():
        process_corpus_file(minio_input, minio_output)
    else:
        print(f"\n⚠️  {minio_input} 없음 - 건너뜀")
    
    print()
    
    # ZIP corpus
    zip_input = Path("data/corpus_zip_attachments_clean_old.csv")
    zip_output = Path("data/corpus_zip_attachments_clean.csv")
    
    if zip_input.exists():
        process_corpus_file(zip_input, zip_output)
    else:
        print(f"\n⚠️  {zip_input} 없음 - 건너뜀")
    
    print("\n" + "=" * 80)
    print("🎉 전체 완료!")
    print("=" * 80)

if __name__ == "__main__":
    main()
