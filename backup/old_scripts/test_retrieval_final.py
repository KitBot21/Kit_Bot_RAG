#!/usr/bin/env python3
"""
임베딩 검색 성능 평가
Ground Truth 기반으로 Top-K 정확도 측정
"""
import pandas as pd
from pathlib import Path
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

# 설정
GROUND_TRUTH_DEV_CSV = DATA_DIR / "ground_truth_test.csv"
GROUND_TRUTH_TEST_CSV = DATA_DIR / "ground_truth_test.csv"
QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "kit_corpus_bge_all"
RETRIEVER_MODEL = "BAAI/bge-m3"

def calculate_metrics(ground_truth_df, collection_name, retriever, client, top_k_values=[1, 3, 5, 10]):
    """
    Retrieval 성능 측정
    
    Returns:
        dict: Top-K별 정확도
    """
    results = {k: [] for k in top_k_values}
    
    print(f"\n🔍 검색 성능 평가 시작...")
    print(f"   테스트 쿼리: {len(ground_truth_df)}개")
    print(f"   평가 지표: Recall@K (K={top_k_values})")
    
    for idx, row in tqdm(ground_truth_df.iterrows(), total=len(ground_truth_df), desc="평가"):
        query = row['query']
        expected_chunk_id = row['document_name']  # CSV 컬럼명 변경
        
        # 쿼리 임베딩
        query_vector = retriever.encode(query, normalize_embeddings=True).tolist()
        
        # 최대 K로 검색
        max_k = max(top_k_values)
        search_result = client.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=max_k
        ).points
        
        # 각 K값에 대해 평가
        for k in top_k_values:
            # Top-K 결과에서 document_name 추출
            top_k_results = search_result[:k]
            retrieved_ids = []
            
            for hit in top_k_results:
                # document_name 사용
                doc_name = hit.payload.get('document_name', '')
                retrieved_ids.append(doc_name)
            
            # 정답이 Top-K 안에 있는지 확인
            is_correct = expected_chunk_id in retrieved_ids
            results[k].append(1 if is_correct else 0)
    
    # 정확도 계산
    metrics = {}
    for k in top_k_values:
        recall = sum(results[k]) / len(results[k]) * 100
        metrics[f"Recall@{k}"] = recall
    
    return metrics

def print_failed_queries(ground_truth_df, collection_name, retriever, client, k=5):
    """
    실패한 쿼리들을 분석하여 출력
    """
    print(f"\n❌ 검색 실패 사례 분석 (Top-{k}):")
    print("=" * 100)
    
    failed_count = 0
    
    for idx, row in ground_truth_df.iterrows():
        query = row['query']
        expected_chunk_id = row['document_name']  # CSV 컬럼명 변경
        
        # 쿼리 임베딩
        query_vector = retriever.encode(query, normalize_embeddings=True).tolist()
        
        # 검색
        search_result = client.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=k
        ).points
        
        # 결과 확인
        retrieved_ids = [hit.payload.get('document_name', '') 
                        for hit in search_result]
        
        if expected_chunk_id not in retrieved_ids:
            failed_count += 1
            if failed_count <= 10:  # 상위 10개만 출력
                print(f"\n[{failed_count}] 질문: {query}")
                print(f"    예상: {expected_chunk_id}")
                print(f"    검색된 Top-{k}:")
                for i, hit in enumerate(search_result, 1):
                    doc_name = hit.payload.get('document_name', '')
                    title = hit.payload.get('title', '')
                    score = hit.score
                    print(f"      {i}. {doc_name} (score: {score:.3f}) - {title[:50]}")
    
    print(f"\n총 실패: {failed_count}/{len(ground_truth_df)}개")
    print("=" * 100)

def main():
    print("=" * 80)
    print("📊 임베딩 검색 성능 평가 (Test Set)")
    print("=" * 80)
    
    # 1. Ground Truth 로드
    print(f"\n📂 Ground Truth 로드: {GROUND_TRUTH_DEV_CSV}")
    df = pd.read_csv(GROUND_TRUTH_DEV_CSV)
    print(f"   ✅ 테스트 쿼리: {len(df)}개")
    
    # 2. Retriever 로드
    print(f"\n🤖 Retriever 로드: {RETRIEVER_MODEL}")
    retriever = SentenceTransformer(RETRIEVER_MODEL)
    print(f"   ✅ 모델 준비 완료")
    
    # 3. Qdrant 연결
    print(f"\n🔌 Qdrant 연결: {QDRANT_URL}")
    client = QdrantClient(url=QDRANT_URL)
    print(f"   컬렉션: {COLLECTION_NAME}")
    
    # 컬렉션 정보
    collection_info = client.get_collection(COLLECTION_NAME)
    print(f"   벡터 수: {collection_info.points_count:,}개")
    
    # 4. 성능 평가
    metrics = calculate_metrics(df, COLLECTION_NAME, retriever, client, top_k_values=[1, 3, 5, 10])
    
    # 5. 결과 출력
    print("\n" + "=" * 80)
    print("📈 평가 결과 (Test Set)")
    print("=" * 80)
    for metric_name, value in metrics.items():
        print(f"  {metric_name}: {value:.2f}%")
    
    # 6. 실패 사례 분석
    print_failed_queries(df, COLLECTION_NAME, retriever, client, k=5)
    
    print("\n" + "=" * 80)
    print("✅ 평가 완료!")
    print("=" * 80)
    print("\n💡 다음 단계:")
    print("  - Top-K 값 조정")
    print("  - Reranking 추가")
    print("  - 하이브리드 검색 (BM25 + Dense)")
    print("  - 최종 평가: python scripts/test_retrieval_final.py (Test Set)")
    print("=" * 80)

if __name__ == "__main__":
    main()
