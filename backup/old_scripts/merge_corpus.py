#!/usr/bin/env python3
"""
여러 corpus 파일을 하나로 병합
"""
import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

def merge_corpus_files():
    """corpus_filtered.csv와 corpus_attachments.csv 병합"""
    print("=" * 80)
    print("📦 Corpus 파일 병합")
    print("=" * 80)
    
    # 파일 경로
    filtered_path = PROJECT_ROOT / "data" / "corpus_filtered.csv"
    attachments_path = PROJECT_ROOT / "data" / "corpus_attachments.csv"
    merged_path = PROJECT_ROOT / "data" / "corpus_merged.csv"
    
    dfs = []
    
    # corpus_filtered.csv 로드
    if filtered_path.exists():
        df_filtered = pd.read_csv(filtered_path)
        print(f"\n✅ corpus_filtered.csv: {len(df_filtered)}개 청크")
        dfs.append(df_filtered)
    else:
        print(f"\n⚠️  corpus_filtered.csv 없음")
    
    # corpus_attachments.csv 로드
    if attachments_path.exists():
        df_attachments = pd.read_csv(attachments_path)
        print(f"✅ corpus_attachments.csv: {len(df_attachments)}개 청크")
        dfs.append(df_attachments)
    else:
        print(f"⚠️  corpus_attachments.csv 없음 (첨부파일 처리 필요)")
    
    if not dfs:
        print("\n❌ 병합할 파일이 없습니다!")
        return
    
    # 병합
    df_merged = pd.concat(dfs, ignore_index=True)
    
    # 중복 제거 (chunk_id 기준)
    before_dedup = len(df_merged)
    df_merged = df_merged.drop_duplicates(subset=['chunk_id'], keep='first')
    after_dedup = len(df_merged)
    
    if before_dedup != after_dedup:
        print(f"\n🔄 중복 제거: {before_dedup - after_dedup}개 청크")
    
    # 저장
    df_merged.to_csv(merged_path, index=False, encoding='utf-8')
    
    print("\n" + "=" * 80)
    print("✅ 병합 완료!")
    print("=" * 80)
    print(f"  총 청크 수: {len(df_merged)}개")
    print(f"  고유 문서: {df_merged['doc_id'].nunique()}개")
    print(f"  저장 위치: {merged_path}")
    
    # 섹션별 통계
    print(f"\n📊 섹션별 분포:")
    section_counts = df_merged['section'].value_counts()
    for section, count in section_counts.items():
        print(f"  - {section}: {count}개")
    
    print("\n💡 다음 단계:")
    print("  1. python3 scripts/regenerate_embeddings.py --input data/corpus_merged.csv")
    print("  2. python3 scripts/ingest_multi.py --input data/corpus_merged.csv")

if __name__ == "__main__":
    merge_corpus_files()
