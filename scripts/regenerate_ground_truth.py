#!/usr/bin/env python3
"""
새 컬렉션(kit_corpus_bge_all)으로 Ground Truth 재생성
"""

import csv
from pathlib import Path
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
import warnings
warnings.filterwarnings('ignore')

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

COLLECTION_NAME = "kit_corpus_bge_all"
QDRANT_URL = "http://localhost:6333"

def generate_ground_truth(queries_file, output_file):
    """쿼리에 대한 Ground Truth 생성"""
    
    print(f"\n📂 쿼리 로드: {queries_file.name}")
    
    with queries_file.open('r', encoding='utf-8') as f:
        queries = [line.strip() for line in f if line.strip()]
    
    print(f"   쿼리 수: {len(queries)}개")
    
    # Qdrant 연결
    client = QdrantClient(QDRANT_URL)
    
    # BGE-M3 모델
    print(f"\n🤖 BGE-M3 모델 로드 중...")
    model = SentenceTransformer('BAAI/bge-m3')
    
    # Ground Truth 생성
    print(f"\n⏳ Ground Truth 생성 중...")
    
    results = []
    
    for i, query in enumerate(queries, 1):
        if i % 20 == 0:
            print(f"   진행: {i}/{len(queries)}")
        
        # 쿼리 임베딩
        query_vector = model.encode(query, normalize_embeddings=True).tolist()
        
        # 검색 (Top-1)
        search_results = client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            limit=1
        )
        
        if search_results:
            top_hit = search_results[0]
            
            # title을 ground truth로 사용 (_chunk 제거된 원본 문서명)
            title = top_hit.payload.get('title', '')
            similarity = top_hit.score
            
            results.append({
                'query': query,
                'document_name': title,  # title 사용
                'similarity': similarity
            })
    
    # 저장
    with output_file.open('w', encoding='utf-8', newline='') as f:
        fieldnames = ['query', 'document_name', 'similarity']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    
    print(f"\n✅ 저장: {output_file}")
    
    # 통계
    avg_similarity = sum(r['similarity'] for r in results) / len(results)
    print(f"\n📊 통계:")
    print(f"   쿼리 수: {len(results)}개")
    print(f"   평균 유사도: {avg_similarity:.4f}")
    
    return results

def main():
    print("=" * 80)
    print("🔄 Ground Truth 재생성 - 새 컬렉션")
    print("=" * 80)
    
    print(f"\n🎯 컬렉션: {COLLECTION_NAME}")
    print(f"   - 벡터 수: 15,986개")
    print(f"   - 청크 크기: 1000자")
    
    # 1. Dev Set
    print("\n" + "=" * 80)
    print("1️⃣ Dev Set Ground Truth")
    print("=" * 80)
    
    generate_ground_truth(
        DATA_DIR / "queries_dev.txt",
        DATA_DIR / "ground_truth_dev_new.csv"
    )
    
    # 2. Test Set
    print("\n" + "=" * 80)
    print("2️⃣ Test Set Ground Truth")
    print("=" * 80)
    
    generate_ground_truth(
        DATA_DIR / "queries_test.txt",
        DATA_DIR / "ground_truth_test_new.csv"
    )
    
    # 3. Manual Set
    print("\n" + "=" * 80)
    print("3️⃣ Manual Set Ground Truth")
    print("=" * 80)
    
    generate_ground_truth(
        DATA_DIR / "queries_manual.txt",
        DATA_DIR / "ground_truth_manual_new.csv"
    )
    
    print("\n" + "=" * 80)
    print("✅ 전체 완료!")
    print("=" * 80)
    
    print("\n💡 다음 단계:")
    print("   1. 기존 파일 백업:")
    print("      mv data/ground_truth_dev.csv data/ground_truth_dev_old.csv")
    print("      mv data/ground_truth_test.csv data/ground_truth_test_old.csv")
    print("      mv data/ground_truth_manual.csv data/ground_truth_manual_old.csv")
    print("\n   2. 새 파일로 교체:")
    print("      mv data/ground_truth_dev_new.csv data/ground_truth_dev.csv")
    print("      mv data/ground_truth_test_new.csv data/ground_truth_test.csv")
    print("      mv data/ground_truth_manual_new.csv data/ground_truth_manual.csv")
    print("\n   3. 재평가:")
    print("      python scripts/evaluate_retrieval.py")

if __name__ == "__main__":
    main()
