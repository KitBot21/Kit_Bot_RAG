#!/usr/bin/env python3
"""
Reranking 평가: Dense Retrieval (BGE) + Cross-Encoder Reranking
"""
import pandas as pd
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer, CrossEncoder
from qdrant_client import QdrantClient
import argparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]

def evaluate_rerank(model_name='bge', collection='kit_corpus_bge_filtered', 
                    reranker_name='cross-encoder/ms-marco-MiniLM-L-6-v2',
                    retrieval_k=20, final_k=5):
    """
    Two-stage retrieval with reranking
    1. Dense retrieval: Top-K candidates (e.g., K=20)
    2. Rerank: Cross-encoder reranks to final Top-5
    """
    print("=" * 80)
    print(f"🔍 Reranking 평가")
    print(f"   Retriever: {model_name.upper()}")
    print(f"   Reranker: {reranker_name}")
    print(f"   Retrieval Top-K: {retrieval_k}, Final Top-K: {final_k}")
    print("=" * 80)
    
    # Ground truth 로드
    gt_df = pd.read_csv(PROJECT_ROOT / 'data' / 'ground_truth.csv')
    queries = gt_df['query'].tolist()
    correct_ids = gt_df['chunk_id'].tolist()
    
    # Corpus 로드
    corpus_df = pd.read_csv(PROJECT_ROOT / 'data' / 'corpus_filtered.csv')
    chunk_ids = corpus_df['chunk_id'].tolist()
    texts = corpus_df['text'].tolist()
    
    # Dense retriever 로드
    print(f"\n📥 모델 로딩 중...")
    retriever = SentenceTransformer(f'BAAI/bge-m3' if model_name == 'bge' else model_name)
    
    # Reranker 로드
    reranker = CrossEncoder(reranker_name)
    
    # Qdrant 클라이언트
    client = QdrantClient('localhost', port=6333)
    
    print(f"\n📊 데이터 정보")
    print(f"  쿼리: {len(queries)}개")
    print(f"  코퍼스: {len(texts)}개")
    
    # 평가
    top1_correct = 0
    top5_correct = 0
    mrr_sum = 0
    
    print(f"\n🔎 검색 시작...")
    
    for i, (query, correct_id) in enumerate(zip(queries, correct_ids)):
        # Stage 1: Dense retrieval (Top-K candidates)
        query_vector = retriever.encode(query, normalize_embeddings=True).tolist()
        
        search_result = client.search(
            collection_name=collection,
            query_vector=query_vector,
            limit=retrieval_k
        )
        
        # 후보 추출
        candidate_indices = [hit.id for hit in search_result]
        candidate_texts = [texts[idx] for idx in candidate_indices]
        candidate_ids = [chunk_ids[idx] for idx in candidate_indices]
        
        # Stage 2: Reranking with Cross-Encoder
        pairs = [[query, text] for text in candidate_texts]
        rerank_scores = reranker.predict(pairs)
        
        # 점수 기준 정렬
        sorted_indices = np.argsort(rerank_scores)[::-1][:final_k]
        final_ids = [candidate_ids[idx] for idx in sorted_indices]
        
        # Top-1, Top-5 정확도
        if final_ids[0] == correct_id:
            top1_correct += 1
            top5_correct += 1
            mrr_sum += 1.0
        elif correct_id in final_ids:
            top5_correct += 1
            rank = final_ids.index(correct_id) + 1
            mrr_sum += 1.0 / rank
        
        # 진행 상황 출력
        if (i + 1) % 20 == 0:
            print(f"  Progress: {i+1}/{len(queries)}")
    
    # 최종 결과
    top1_acc = top1_correct / len(queries)
    top5_acc = top5_correct / len(queries)
    mrr = mrr_sum / len(queries)
    
    print(f"\n" + "=" * 80)
    print(f"📊 평가 결과 - Reranking")
    print("=" * 80)
    print(f"Top-1 Accuracy: {top1_acc:.4f} ({top1_correct}/{len(queries)})")
    print(f"Top-5 Accuracy: {top5_acc:.4f} ({top5_correct}/{len(queries)})")
    print(f"MRR:            {mrr:.4f}")
    print("=" * 80)
    
    return {
        'model': model_name,
        'reranker': reranker_name,
        'retrieval_k': retrieval_k,
        'top1': top1_acc,
        'top5': top5_acc,
        'mrr': mrr
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default='bge', help='Retriever model name')
    parser.add_argument('--collection', default='kit_corpus_bge_filtered', help='Qdrant collection')
    parser.add_argument('--reranker', default='cross-encoder/ms-marco-MiniLM-L-6-v2', 
                        help='Reranker model name')
    parser.add_argument('--retrieval-k', type=int, default=20, help='Number of candidates from retrieval')
    parser.add_argument('--final-k', type=int, default=5, help='Final top-k after reranking')
    args = parser.parse_args()
    
    evaluate_rerank(args.model, args.collection, args.reranker, args.retrieval_k, args.final_k)
