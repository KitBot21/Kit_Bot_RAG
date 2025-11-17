#!/usr/bin/env python3
"""
모든 corpus 파일을 하나로 병합
- corpus.csv (크롤링 페이지)
- corpus_zip_attachments_clean.csv (ZIP 파일 첨부)
- corpus_minio_documents.csv (MinIO 문서)
"""
import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

def merge_all_corpus():
    """모든 corpus 파일 병합"""
    print("=" * 80)
    print("📦 모든 Corpus 파일 병합")
    print("=" * 80)
    
    # 병합할 파일들
    corpus_files = [
        ("corpus.csv", "크롤링 페이지"),
        ("corpus_zip_attachments_clean.csv", "ZIP 첨부파일"),
        ("corpus_minio_documents.csv", "MinIO 문서"),
    ]
    
    merged_path = DATA_DIR / "corpus_all.csv"
    
    dfs = []
    total_stats = {}
    
    print("\n📂 입력 파일:")
    
    for filename, description in corpus_files:
        file_path = DATA_DIR / filename
        if file_path.exists():
            df = pd.read_csv(file_path)
            print(f"  ✅ {filename}: {len(df):,}개 ({description})")
            total_stats[description] = len(df)
            
            # 공통 컬럼으로 정규화
            normalized_df = pd.DataFrame()
            
            if 'text' in df.columns:
                normalized_df['text'] = df['text']
            else:
                print(f"     ⚠️  'text' 컬럼이 없습니다!")
                continue
            
            # URL
            if 'url' in df.columns:
                normalized_df['url'] = df['url']
            else:
                normalized_df['url'] = ''
            
            # 제목
            if 'title' in df.columns:
                normalized_df['title'] = df['title']
            else:
                normalized_df['title'] = ''
            
            # 출처 타입
            if 'source_type' in df.columns:
                normalized_df['source_type'] = df['source_type']
            elif 'source' in df.columns:
                normalized_df['source_type'] = df['source']
            else:
                normalized_df['source_type'] = description
            
            # 문서명 (첨부파일용)
            if 'document_name' in df.columns:
                normalized_df['document_name'] = df['document_name']
            elif 'id' in df.columns:
                normalized_df['document_name'] = df['id']
            else:
                normalized_df['document_name'] = ''
            
            dfs.append(normalized_df)
        else:
            print(f"  ❌ {filename}: 파일 없음")
    
    if not dfs:
        print("\n❌ 병합할 파일이 없습니다!")
        return
    
    # 병합
    print("\n⏳ 병합 중...")
    df_merged = pd.concat(dfs, ignore_index=True)
    
    # 중복 제거 (텍스트 기준 - 정확히 같은 텍스트만)
    before_dedup = len(df_merged)
    df_merged = df_merged.drop_duplicates(subset=['text'], keep='first')
    after_dedup = len(df_merged)
    
    if before_dedup != after_dedup:
        print(f"   중복 제거: {before_dedup - after_dedup:,}개")
    
    # 빈 텍스트 제거
    before_clean = len(df_merged)
    df_merged = df_merged[df_merged['text'].notna() & (df_merged['text'].str.strip() != '')]
    after_clean = len(df_merged)
    
    if before_clean != after_clean:
        print(f"   빈 텍스트 제거: {before_clean - after_clean:,}개")
    
    # 저장
    df_merged.to_csv(merged_path, index=False, encoding='utf-8')
    
    print("\n" + "=" * 80)
    print("✅ 병합 완료!")
    print("=" * 80)
    print(f"  총 문서: {len(df_merged):,}개")
    print(f"  총 텍스트 길이: {df_merged['text'].str.len().sum():,}자")
    print(f"  평균 길이: {df_merged['text'].str.len().mean():.0f}자")
    print(f"  저장 위치: {merged_path}")
    
    # 출처별 통계
    print(f"\n📊 출처별 분포:")
    source_counts = df_merged['source_type'].value_counts()
    for source, count in source_counts.items():
        print(f"  - {source}: {count:,}개")
    
    # 파일 크기
    file_size_mb = merged_path.stat().st_size / (1024 * 1024)
    print(f"\n💾 파일 크기: {file_size_mb:.1f} MB")
    
    print("\n💡 다음 단계:")
    print("  1. python scripts/regenerate_embeddings.py  # 임베딩 생성")
    print("  2. python scripts/ingest_multi.py           # Qdrant에 업로드")
    print("=" * 80)

if __name__ == "__main__":
    merge_all_corpus()
