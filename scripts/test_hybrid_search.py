#!/usr/bin/env python3
"""
하이브리드 검색 실험: KR-SBERT + BM25 + Reranking

1단계: KR-SBERT 벡터 검색
2단계: BM25 키워드 검색  
3단계: 결과 결합
4단계: Cross-Encoder 리랭킹
"""

import pandas as pd
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer, CrossEncoder
from qdrant_client import QdrantClient
from rank_bm25 import BM25Okapi
import time
import warnings
warnings.filterwarnings('ignore')

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

QDRANT_URL = "http://localhost:6333"

def prepare_bm25_index(corpus_df):
    """BM25 인덱스 준비"""
    print("\n📚 BM25 인덱스 준비 중...")
    
    # 텍스트 토큰화 (간단한 공백 분리)
    tokenized_corpus = [text.split() for text in corpus_df['text'].fillna('').astype(str)]
    
    # BM25 인덱스 생성
    bm25 = BM25Okapi(tokenized_corpus)
    
    print(f"   ✅ {len(tokenized_corpus):,}개 문서 인덱싱 완료")
    
    return bm25

def hybrid_search(query, model, client, bm25, corpus_df, 
                  vector_top_k=15, bm25_top_k=15, 
                  collection_name="kit_corpus_bge_all"):
    """하이브리드 검색: 벡터 + BM25"""
    
    results = {}
    
    # 1. 벡터 검색 (KR-SBERT)
    start = time.time()
    query_vector = model.encode(query, normalize_embeddings=True).tolist()
    vector_results = client.search(
        collection_name=collection_name,
        query_vector=query_vector,
        limit=vector_top_k
    )
    time_vector = time.time() - start
    
    # 벡터 검색 결과 저장 (점수 정규화)
    vector_scores = {}
    for hit in vector_results:
        doc_id = hit.payload.get('id', '')
        vector_scores[doc_id] = hit.score
    
    # 2. BM25 검색
    start = time.time()
    tokenized_query = query.split()
    bm25_scores = bm25.get_scores(tokenized_query)
    
    # Top-K BM25 결과
    bm25_top_indices = np.argsort(bm25_scores)[::-1][:bm25_top_k]
    bm25_results = {}
    
    for idx in bm25_top_indices:
        doc_id = corpus_df.iloc[idx]['id']
        bm25_results[doc_id] = bm25_scores[idx]
    
    time_bm25 = time.time() - start
    
    # 3. 점수 결합 (RRF: Reciprocal Rank Fusion)
    combined_scores = {}
    
    # 벡터 검색 결과
    for rank, (doc_id, score) in enumerate(vector_scores.items(), 1):
        combined_scores[doc_id] = combined_scores.get(doc_id, 0) + 1 / (rank + 60)
    
    # BM25 결과
    for rank, (doc_id, score) in enumerate(bm25_results.items(), 1):
        combined_scores[doc_id] = combined_scores.get(doc_id, 0) + 1 / (rank + 60)
    
    # 결합 점수로 정렬
    sorted_docs = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)
    
    return sorted_docs, time_vector, time_bm25

def test_hybrid_vs_single(num_queries=10):
    """하이브리드 vs 단일 검색 비교"""
    
    print("=" * 80)
    print("🔬 하이브리드 검색 실험")
    print("=" * 80)
    
    # 데이터 로드
    print("\n📂 데이터 로드 중...")
    corpus_df = pd.read_csv(DATA_DIR / "corpus_all.csv")
    corpus_df = corpus_df[corpus_df['text'].notna()].reset_index(drop=True)
    
    gt_df = pd.read_csv(DATA_DIR / "ground_truth_100.csv")
    valid_gt = gt_df[gt_df['rank'] > 0].head(num_queries)
    
    print(f"   코퍼스: {len(corpus_df):,}개")
    print(f"   테스트 쿼리: {len(valid_gt)}개")
    
    # 모델 로드
    print("\n📦 모델 로드 중...")
    kr_sbert = SentenceTransformer('snunlp/KR-SBERT-V40K-klueNLI-augSTS')
    bge_m3 = SentenceTransformer('BAAI/bge-m3')
    client = QdrantClient(url=QDRANT_URL)
    
    # BM25 준비
    bm25 = prepare_bm25_index(corpus_df)
    
    print("\n" + "=" * 80)
    print("🧪 실험 시작")
    print("=" * 80)
    
    results_comparison = []
    
    for idx, row in valid_gt.iterrows():
        query = row['query']
        gt_doc = row['document_name']
        
        print(f"\n쿼리 {idx+1}: {query[:40]}...")
        
        # 1. KR-SBERT 단독
        start = time.time()
        kr_vector = kr_sbert.encode(query, normalize_embeddings=True).tolist()
        kr_results = client.search(
            collection_name="kit_corpus_bge_all",
            query_vector=kr_vector,
            limit=5
        )
        time_kr_single = time.time() - start
        
        kr_found = any(gt_doc in hit.payload.get('document_name', '') for hit in kr_results)
        
        # 2. KR-SBERT + BM25 Hybrid
        start = time.time()
        hybrid_docs, time_vec, time_bm25 = hybrid_search(
            query, kr_sbert, client, bm25, corpus_df,
            vector_top_k=10, bm25_top_k=10
        )
        time_hybrid = time.time() - start
        
        # Top-5 확인
        hybrid_top5_ids = [doc_id for doc_id, _ in hybrid_docs[:5]]
        hybrid_found = False
        for doc_id in hybrid_top5_ids:
            match = corpus_df[corpus_df['id'] == doc_id]
            if len(match) > 0:
                doc_name = match.iloc[0]['document_name']
                if isinstance(doc_name, str) and gt_doc in doc_name:
                    hybrid_found = True
                    break
        
        # 3. BGE-M3 단독 (비교)
        start = time.time()
        bge_vector = bge_m3.encode(query, normalize_embeddings=True).tolist()
        bge_results = client.search(
            collection_name="kit_corpus_bge_all",
            query_vector=bge_vector,
            limit=5
        )
        time_bge = time.time() - start
        
        bge_found = any(gt_doc in hit.payload.get('document_name', '') for hit in bge_results)
        
        print(f"   KR-SBERT: {'✅' if kr_found else '❌'} ({time_kr_single*1000:.0f}ms)")
        print(f"   Hybrid: {'✅' if hybrid_found else '❌'} ({time_hybrid*1000:.0f}ms)")
        print(f"   BGE-M3: {'✅' if bge_found else '❌'} ({time_bge*1000:.0f}ms)")
        
        results_comparison.append({
            'query': query,
            'kr_sbert_found': kr_found,
            'hybrid_found': hybrid_found,
            'bge_m3_found': bge_found,
            'time_kr': time_kr_single * 1000,
            'time_hybrid': time_hybrid * 1000,
            'time_bge': time_bge * 1000,
        })
    
    # 결과 요약
    df_results = pd.DataFrame(results_comparison)
    
    print("\n" + "=" * 80)
    print("📊 결과 요약")
    print("=" * 80)
    
    print(f"\n정확도 (Recall@5):")
    print(f"   KR-SBERT 단독: {df_results['kr_sbert_found'].mean():.1%}")
    print(f"   KR-SBERT + BM25 Hybrid: {df_results['hybrid_found'].mean():.1%}")
    print(f"   BGE-M3 단독: {df_results['bge_m3_found'].mean():.1%}")
    
    print(f"\n평균 응답 시간:")
    print(f"   KR-SBERT: {df_results['time_kr'].mean():.0f}ms")
    print(f"   Hybrid: {df_results['time_hybrid'].mean():.0f}ms")
    print(f"   BGE-M3: {df_results['time_bge'].mean():.0f}ms")
    
    print("\n💡 결론:")
    
    hybrid_recall = df_results['hybrid_found'].mean()
    bge_recall = df_results['bge_m3_found'].mean()
    
    if hybrid_recall >= bge_recall * 0.9:
        print(f"   ✅ Hybrid가 효과적! (정확도 {hybrid_recall:.1%} vs {bge_recall:.1%})")
    else:
        print(f"   ❌ Hybrid도 BGE-M3보다 낮음 ({hybrid_recall:.1%} vs {bge_recall:.1%})")
        print(f"   → BGE-M3 단독 사용 추천")
    
    return df_results

if __name__ == "__main__":
    # rank-bm25 설치 필요
    try:
        from rank_bm25 import BM25Okapi
    except ImportError:
        print("❌ rank-bm25 패키지 설치 필요:")
        print("   pip install rank-bm25")
        exit(1)
    
    results = test_hybrid_vs_single(num_queries=10)
