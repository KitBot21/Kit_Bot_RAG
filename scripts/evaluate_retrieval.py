#!/usr/bin/env python3
"""
검색 성능 평가: Recall@K, MRR
새로운 청킹된 컬렉션(kit_corpus_bge_all) 테스트
"""

import csv
import sys
from pathlib import Path
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
import warnings
warnings.filterwarnings('ignore')

# CSV 필드 크기 제한 해제
csv.field_size_limit(sys.maxsize)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

# 설정
COLLECTION_NAME = "kit_corpus_bge_all"
QDRANT_URL = "http://localhost:6333"

def match_document(retrieved_doc, ground_truth_doc):
    """문서 매칭: document_name 또는 title 기준"""
    # 정확히 일치
    if retrieved_doc == ground_truth_doc:
        return True
    
    # _chunk 제거 후 비교 (청킹된 문서 대응)
    retrieved_base = retrieved_doc.replace('_chunk0', '').replace('_chunk1', '').replace('_chunk2', '').replace('_chunk3', '').replace('_chunk4', '').replace('_chunk5', '').replace('_chunk6', '').replace('_chunk7', '').replace('_chunk8', '').replace('_chunk9', '')
    for i in range(10, 100):
        retrieved_base = retrieved_base.replace(f'_chunk{i}', '')
    
    if retrieved_base == ground_truth_doc:
        return True
    
    return False

def calculate_recall_at_k(retrieved_docs, ground_truth_doc, k):
    """Recall@K 계산 (청킹 문서 대응)"""
    top_k = retrieved_docs[:k]
    for doc in top_k:
        if match_document(doc, ground_truth_doc):
            return 1.0
    return 0.0

def calculate_mrr(retrieved_docs, ground_truth_doc):
    """MRR (Mean Reciprocal Rank) 계산 (청킹 문서 대응)"""
    for rank, doc in enumerate(retrieved_docs, 1):
        if match_document(doc, ground_truth_doc):
            return 1.0 / rank
    return 0.0

def evaluate_on_dataset(queries_file, ground_truth_file, collection_name):
    """데이터셋에 대한 검색 성능 평가"""
    
    print(f"\n📂 데이터 로드:")
    print(f"   쿼리: {queries_file.name}")
    print(f"   정답: {ground_truth_file.name}")
    
    # 쿼리 로드
    with queries_file.open('r', encoding='utf-8') as f:
        queries = [line.strip() for line in f if line.strip()]
    
    # Ground truth 로드
    ground_truth = {}
    with ground_truth_file.open('r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            query = row['query']
            doc_name = row['document_name']
            ground_truth[query] = doc_name
    
    print(f"   쿼리 수: {len(queries)}개")
    print(f"   정답 수: {len(ground_truth)}개")
    
    # Qdrant 연결
    client = QdrantClient(QDRANT_URL)
    
    # BGE-M3 모델 로드
    print(f"\n🤖 BGE-M3 모델 로드 중...")
    model = SentenceTransformer('BAAI/bge-m3')
    
    # 평가
    print(f"\n🔍 검색 평가 중...")
    
    recall_at_1 = []
    recall_at_3 = []
    recall_at_5 = []
    recall_at_10 = []
    mrr_scores = []
    
    queries_with_gt = [q for q in queries if q in ground_truth]
    
    for i, query in enumerate(queries_with_gt, 1):
        if i % 20 == 0:
            print(f"   진행: {i}/{len(queries_with_gt)}")
        
        gt_doc = ground_truth[query]
        
        # 쿼리 임베딩
        query_vector = model.encode(query, normalize_embeddings=True).tolist()
        
        # 검색 (Top-10)
        results = client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=10
        )
        
        # 검색된 문서 이름 리스트 (document_name과 title 모두 사용)
        retrieved_docs = []
        for hit in results:
            doc_name = hit.payload.get('document_name', '')
            title = hit.payload.get('title', '')
            # 둘 다 추가 (매칭 가능성 높이기)
            retrieved_docs.append(doc_name)
            if title and title != doc_name:
                retrieved_docs.append(title)
        
        # Recall@K 계산
        recall_at_1.append(calculate_recall_at_k(retrieved_docs, gt_doc, 1))
        recall_at_3.append(calculate_recall_at_k(retrieved_docs, gt_doc, 3))
        recall_at_5.append(calculate_recall_at_k(retrieved_docs, gt_doc, 5))
        recall_at_10.append(calculate_recall_at_k(retrieved_docs, gt_doc, 10))
        
        # MRR 계산
        mrr_scores.append(calculate_mrr(retrieved_docs, gt_doc))
    
    # 결과 계산
    results = {
        'recall@1': sum(recall_at_1) / len(recall_at_1) * 100 if recall_at_1 else 0,
        'recall@3': sum(recall_at_3) / len(recall_at_3) * 100 if recall_at_3 else 0,
        'recall@5': sum(recall_at_5) / len(recall_at_5) * 100 if recall_at_5 else 0,
        'recall@10': sum(recall_at_10) / len(recall_at_10) * 100 if recall_at_10 else 0,
        'mrr': sum(mrr_scores) / len(mrr_scores) if mrr_scores else 0,
        'total_queries': len(queries_with_gt)
    }
    
    return results

def main():
    print("=" * 80)
    print("📊 검색 성능 평가 - 새 컬렉션 (kit_corpus_bge_all)")
    print("=" * 80)
    
    print(f"\n🎯 컬렉션: {COLLECTION_NAME}")
    print(f"   - 벡터 수: 15,986개")
    print(f"   - 청크 크기: 1000자 (오버랩 150자)")
    print(f"   - 필터링: 차례/목차/참고문헌 제거")
    
    # 1. Dev 셋 평가
    print("\n" + "=" * 80)
    print("1️⃣ Dev Set 평가 (70개 쿼리)")
    print("=" * 80)
    
    dev_results = evaluate_on_dataset(
        DATA_DIR / "queries_dev.txt",
        DATA_DIR / "ground_truth_dev.csv",
        COLLECTION_NAME
    )
    
    print(f"\n📊 결과:")
    print(f"   Recall@1:  {dev_results['recall@1']:.2f}%")
    print(f"   Recall@3:  {dev_results['recall@3']:.2f}%")
    print(f"   Recall@5:  {dev_results['recall@5']:.2f}%")
    print(f"   Recall@10: {dev_results['recall@10']:.2f}%")
    print(f"   MRR:       {dev_results['mrr']:.4f}")
    
    # 2. Test 셋 평가
    print("\n" + "=" * 80)
    print("2️⃣ Test Set 평가 (31개 쿼리)")
    print("=" * 80)
    
    test_results = evaluate_on_dataset(
        DATA_DIR / "queries_test.txt",
        DATA_DIR / "ground_truth_test.csv",
        COLLECTION_NAME
    )
    
    print(f"\n📊 결과:")
    print(f"   Recall@1:  {test_results['recall@1']:.2f}%")
    print(f"   Recall@3:  {test_results['recall@3']:.2f}%")
    print(f"   Recall@5:  {test_results['recall@5']:.2f}%")
    print(f"   Recall@10: {test_results['recall@10']:.2f}%")
    print(f"   MRR:       {test_results['mrr']:.4f}")
    
    # 3. Manual 셋 평가
    print("\n" + "=" * 80)
    print("3️⃣ Manual Set 평가 (30개 쿼리)")
    print("=" * 80)
    
    manual_results = evaluate_on_dataset(
        DATA_DIR / "queries_manual.txt",
        DATA_DIR / "ground_truth_manual.csv",
        COLLECTION_NAME
    )
    
    print(f"\n📊 결과:")
    print(f"   Recall@1:  {manual_results['recall@1']:.2f}%")
    print(f"   Recall@3:  {manual_results['recall@3']:.2f}%")
    print(f"   Recall@5:  {manual_results['recall@5']:.2f}%")
    print(f"   Recall@10: {manual_results['recall@10']:.2f}%")
    print(f"   MRR:       {manual_results['mrr']:.4f}")
    
    # 4. 전체 요약
    print("\n" + "=" * 80)
    print("📈 전체 요약")
    print("=" * 80)
    
    print(f"\n{'Dataset':<15} {'Queries':<10} {'R@1':<10} {'R@3':<10} {'R@5':<10} {'R@10':<10} {'MRR':<10}")
    print("-" * 80)
    print(f"{'Dev Set':<15} {dev_results['total_queries']:<10} {dev_results['recall@1']:<10.2f} {dev_results['recall@3']:<10.2f} {dev_results['recall@5']:<10.2f} {dev_results['recall@10']:<10.2f} {dev_results['mrr']:<10.4f}")
    print(f"{'Test Set':<15} {test_results['total_queries']:<10} {test_results['recall@1']:<10.2f} {test_results['recall@3']:<10.2f} {test_results['recall@5']:<10.2f} {test_results['recall@10']:<10.2f} {test_results['mrr']:<10.4f}")
    print(f"{'Manual Set':<15} {manual_results['total_queries']:<10} {manual_results['recall@1']:<10.2f} {manual_results['recall@3']:<10.2f} {manual_results['recall@5']:<10.2f} {manual_results['recall@10']:<10.2f} {manual_results['mrr']:<10.4f}")
    
    print("\n" + "=" * 80)
    print("✅ 평가 완료!")
    print("=" * 80)
    
    print("\n💡 참고:")
    print("   - Recall@K: Top-K 결과에 정답이 포함된 비율")
    print("   - MRR: 정답의 평균 역순위 (높을수록 좋음, 최대 1.0)")
    print("   - 현재 ground_truth는 자동 생성되어 100%에 가까울 수 있음")
    print("   - 실제 성능은 수동 검증 필요")

if __name__ == "__main__":
    main()
