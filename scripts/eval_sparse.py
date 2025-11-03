#!/usr/bin/env python3
"""
BM25 Sparse Vector 검색 평가
"""
import pickle
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent))
from create_sparse_vectors import BM25Vectorizer

PROJECT_ROOT = Path(__file__).resolve().parents[1]

def sparse_search(query_vec, corpus_vecs, top_k=5):
    """Sparse vector 기반 검색 (내적 계산)"""
    scores = []
    
    for doc_vec in corpus_vecs:
        # 내적 계산
        score = 0.0
        for idx, val in query_vec.items():
            if idx in doc_vec:
                score += val * doc_vec[idx]
        scores.append(score)
    
    # Top-K 인덱스 반환
    scores = np.array(scores)
    top_indices = np.argsort(scores)[::-1][:top_k]
    return top_indices, scores[top_indices]

def evaluate_sparse():
    print("=" * 70)
    print("🔍 BM25 Sparse Vector 검색 평가")
    print("=" * 70)
    
    # Ground truth 로드
    gt_df = pd.read_csv(PROJECT_ROOT / 'data' / 'ground_truth.csv')
    queries = gt_df['query'].tolist()
    correct_ids = gt_df['chunk_id'].tolist()
    
    # Corpus 로드
    corpus_df = pd.read_csv(PROJECT_ROOT / 'data' / 'corpus_with_sources.csv')
    chunk_ids = corpus_df['chunk_id'].tolist()
    
    # BM25 벡터화기 및 sparse vectors 로드
    with open(PROJECT_ROOT / 'embeddings' / 'bm25_vectorizer.pkl', 'rb') as f:
        vectorizer = pickle.load(f)
    
    with open(PROJECT_ROOT / 'embeddings' / 'bm25_sparse_vectors.pkl', 'rb') as f:
        corpus_vecs = pickle.load(f)
    
    print(f"\n📊 데이터 정보")
    print(f"  쿼리: {len(queries)}개")
    print(f"  코퍼스: {len(corpus_vecs)}개 문서")
    print(f"  어휘: {len(vectorizer.vocab):,}개 단어")
    
    # 평가
    top1_correct = 0
    top5_correct = 0
    mrr_sum = 0
    
    print(f"\n🔎 검색 시작...")
    
    for i, (query, correct_id) in enumerate(zip(queries, correct_ids)):
        # 쿼리 벡터화
        query_vec = vectorizer.transform_query(query)
        
        # 검색
        top_indices, scores = sparse_search(query_vec, corpus_vecs, top_k=5)
        
        # 예측된 chunk_id
        pred_ids = [chunk_ids[idx] for idx in top_indices]
        
        # Top-1, Top-5 정확도
        if pred_ids[0] == correct_id:
            top1_correct += 1
            top5_correct += 1
            mrr_sum += 1.0
        elif correct_id in pred_ids:
            top5_correct += 1
            rank = pred_ids.index(correct_id) + 1
            mrr_sum += 1.0 / rank
        
        # 결과 출력 (매 10개마다)
        if (i + 1) % 10 == 0 or correct_id in pred_ids[:5]:
            status = "✅" if correct_id in pred_ids else "❌"
            print(f"{status} Query {i+1}: {query}")
            if correct_id in pred_ids:
                rank = pred_ids.index(correct_id) + 1
                print(f"   정답: {correct_id} (순위: {rank})")
            print(f"   Top-5: {pred_ids}")
    
    # 최종 결과
    top1_acc = top1_correct / len(queries)
    top5_acc = top5_correct / len(queries)
    mrr = mrr_sum / len(queries)
    
    print(f"\n" + "=" * 70)
    print(f"📊 평가 결과 - BM25 Sparse Search")
    print("=" * 70)
    print(f"Top-1 Accuracy: {top1_acc:.4f} ({top1_correct}/{len(queries)})")
    print(f"Top-5 Accuracy: {top5_acc:.4f} ({top5_correct}/{len(queries)})")
    print(f"MRR:            {mrr:.4f}")
    print("=" * 70)
    
    return {
        'top1': top1_acc,
        'top5': top5_acc,
        'mrr': mrr
    }

if __name__ == "__main__":
    evaluate_sparse()
