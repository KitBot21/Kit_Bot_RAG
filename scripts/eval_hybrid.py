#!/usr/bin/env python3
"""
Hybrid Search 평가: Dense Vector + BM25 Sparse
"""
import pickle
import pandas as pd
import numpy as np
from pathlib import Path
import sys
import argparse

sys.path.append(str(Path(__file__).parent))
from create_sparse_vectors import BM25Vectorizer
from embed_providers import get_encoder, DEFAULTS

PROJECT_ROOT = Path(__file__).resolve().parents[1]

def normalize_scores(scores):
    """점수를 0-1로 정규화"""
    min_score = np.min(scores)
    max_score = np.max(scores)
    if max_score - min_score < 1e-8:
        return np.zeros_like(scores)
    return (scores - min_score) / (max_score - min_score)

def hybrid_search(query, dense_encoder, embedder_name, corpus_dense_embeds, 
                  vectorizer, corpus_sparse_vecs, alpha=0.5, top_k=5):
    """
    하이브리드 검색: Dense + Sparse
    alpha: Dense 가중치 (0~1), Sparse 가중치는 (1-alpha)
    """
    # 1. Dense 검색
    query_dense = np.array(dense_encoder([query], embedder_name)[0])[0]
    
    # Dense 유사도 (코사인)
    query_norm = np.linalg.norm(query_dense)
    corpus_norms = np.linalg.norm(corpus_dense_embeds, axis=1)
    query_norm = np.maximum(query_norm, 1e-8)
    corpus_norms = np.maximum(corpus_norms, 1e-8)
    dense_scores = np.dot(query_dense, corpus_dense_embeds.T) / (query_norm * corpus_norms)
    
    # 2. Sparse 검색
    query_sparse = vectorizer.transform_query(query)
    sparse_scores = np.zeros(len(corpus_sparse_vecs))
    
    for i, doc_vec in enumerate(corpus_sparse_vecs):
        score = 0.0
        for idx, val in query_sparse.items():
            if idx in doc_vec:
                score += val * doc_vec[idx]
        sparse_scores[i] = score
    
    # 3. 점수 정규화
    dense_scores_norm = normalize_scores(dense_scores)
    sparse_scores_norm = normalize_scores(sparse_scores)
    
    # 4. 하이브리드 점수 계산
    hybrid_scores = alpha * dense_scores_norm + (1 - alpha) * sparse_scores_norm
    
    # 5. Top-K 반환
    top_indices = np.argsort(hybrid_scores)[::-1][:top_k]
    return top_indices, hybrid_scores[top_indices]

def evaluate_hybrid(model_name='bge', alpha=0.5, corpus_path='data/corpus_filtered.csv', 
                    embeddings_path=None, vectorizer_path=None, vectors_path=None):
    print("=" * 80)
    print(f"🔍 Hybrid Search 평가: {model_name.upper()} + BM25")
    print(f"   Alpha (Dense 가중치): {alpha:.2f}, Sparse 가중치: {1-alpha:.2f}")
    print("=" * 80)
    
    # Ground truth 로드
    gt_df = pd.read_csv(PROJECT_ROOT / 'data' / 'ground_truth.csv')
    queries = gt_df['query'].tolist()
    correct_ids = gt_df['chunk_id'].tolist()
    
    # Corpus 로드
    corpus_df = pd.read_csv(PROJECT_ROOT / corpus_path)
    chunk_ids = corpus_df['chunk_id'].tolist()
    
    # Dense 임베딩 로드
    if embeddings_path is None:
        embeddings_path = f'embeddings/{model_name}_filtered.npy'
    dense_embeds = np.load(PROJECT_ROOT / embeddings_path)
    dense_encoder = get_encoder(model_name)
    embedder_name = DEFAULTS[model_name]
    
    # Sparse 벡터 로드
    if vectorizer_path is None:
        vectorizer_path = 'embeddings/bm25_filtered_vectorizer.pkl'
    if vectors_path is None:
        vectors_path = 'embeddings/bm25_filtered_vectors.pkl'
        
    with open(PROJECT_ROOT / vectorizer_path, 'rb') as f:
        vectorizer = pickle.load(f)
    
    with open(PROJECT_ROOT / vectors_path, 'rb') as f:
        corpus_sparse_vecs = pickle.load(f)
    
    print(f"\n📊 데이터 정보")
    print(f"  쿼리: {len(queries)}개")
    print(f"  코퍼스: {len(dense_embeds)}개")
    print(f"  Dense 차원: {dense_embeds.shape[1]}")
    print(f"  Sparse 어휘: {len(vectorizer.vocab):,}개")
    
    # 평가
    top1_correct = 0
    top5_correct = 0
    mrr_sum = 0
    
    print(f"\n🔎 검색 시작...")
    
    for i, (query, correct_id) in enumerate(zip(queries, correct_ids)):
        # 하이브리드 검색
        top_indices, scores = hybrid_search(
            query, dense_encoder, embedder_name,
            dense_embeds, vectorizer, corpus_sparse_vecs,
            alpha=alpha, top_k=5
        )
        
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
        
        # 결과 출력 (매 20개마다 또는 정답 찾았을 때)
        if (i + 1) % 20 == 0:
            print(f"  Progress: {i+1}/{len(queries)}")
    
    # 최종 결과
    top1_acc = top1_correct / len(queries)
    top5_acc = top5_correct / len(queries)
    mrr = mrr_sum / len(queries)
    
    print(f"\n" + "=" * 80)
    print(f"📊 평가 결과 - Hybrid ({model_name.upper()} + BM25, α={alpha:.2f})")
    print("=" * 80)
    print(f"Top-1 Accuracy: {top1_acc:.4f} ({top1_correct}/{len(queries)})")
    print(f"Top-5 Accuracy: {top5_acc:.4f} ({top5_correct}/{len(queries)})")
    print(f"MRR:            {mrr:.4f}")
    print("=" * 80)
    
    return {
        'model': model_name,
        'alpha': alpha,
        'top1': top1_acc,
        'top5': top5_acc,
        'mrr': mrr
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default='bge', choices=['bge', 'e5', 'kosimcse', 'krsbert'])
    parser.add_argument('--alpha', type=float, default=0.5, help='Dense weight (0~1)')
    parser.add_argument('--corpus', default='data/corpus_filtered.csv', help='Corpus CSV path')
    parser.add_argument('--embeddings', default=None, help='Dense embeddings path')
    parser.add_argument('--vectorizer', default=None, help='BM25 vectorizer path')
    parser.add_argument('--vectors', default=None, help='BM25 sparse vectors path')
    args = parser.parse_args()
    
    evaluate_hybrid(args.model, args.alpha, args.corpus, args.embeddings, args.vectorizer, args.vectors)
