#!/usr/bin/env python3
"""
하이브리드 검색 평가: BGE-M3 + BM25

1단계: BGE-M3 벡터 검색 (의미 기반)
2단계: BM25 키워드 검색 (키워드 기반)
3단계: RRF (Reciprocal Rank Fusion)로 결과 결합
"""

import pandas as pd
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from rank_bm25 import BM25Okapi
import time
import warnings
warnings.filterwarnings('ignore')

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

COLLECTION_NAME = "kit_corpus_bge_all"
QDRANT_URL = "http://localhost:6333"

def prepare_bm25_index(corpus_df):
    """BM25 인덱스 준비"""
    print("\n📚 BM25 인덱스 준비 중...")
    
    # 텍스트 토큰화 (한글 포함, 공백 분리)
    tokenized_corpus = []
    for text in corpus_df['text'].fillna('').astype(str):
        # 간단한 토큰화 (공백 기준)
        tokens = text.split()
        tokenized_corpus.append(tokens)
    
    # BM25 인덱스 생성
    start = time.time()
    bm25 = BM25Okapi(tokenized_corpus)
    elapsed = time.time() - start
    
    print(f"   ✅ {len(tokenized_corpus):,}개 문서 인덱싱 완료 ({elapsed:.1f}초)")
    
    return bm25

def vector_search(query, model, client, top_k=20):
    """BGE-M3 벡터 검색"""
    query_vector = model.encode(query, normalize_embeddings=True).tolist()
    
    results = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        limit=top_k
    )
    
    return results

def bm25_search(query, bm25, corpus_df, top_k=20):
    """BM25 키워드 검색"""
    tokenized_query = query.split()
    scores = bm25.get_scores(tokenized_query)
    
    # Top-K 인덱스
    top_indices = np.argsort(scores)[::-1][:top_k]
    
    results = []
    for idx in top_indices:
        results.append({
            'index': idx,
            'score': scores[idx],
            'text': corpus_df.iloc[idx]['text'],
            'document_name': corpus_df.iloc[idx].get('document_name', ''),
            'title': corpus_df.iloc[idx].get('title', '')
        })
    
    return results

def reciprocal_rank_fusion(vector_results, bm25_results, corpus_df, 
                           doc_name_to_idx, k=60, top_n=5):
    """
    RRF (Reciprocal Rank Fusion)로 결과 결합
    
    RRF 점수 = 1 / (k + rank)
    k: 일반적으로 60 사용
    """
    rrf_scores = {}
    
    # 1. 벡터 검색 결과 점수
    for rank, hit in enumerate(vector_results, 1):
        # document_name 또는 title로 인덱스 찾기
        doc_name = hit.payload.get('document_name', '')
        if not doc_name:
            doc_name = hit.payload.get('title', '')
        
        if doc_name in doc_name_to_idx:
            # 모든 인덱스에 점수 부여 (중복 처리)
            for idx in doc_name_to_idx[doc_name]:
                rrf_scores[idx] = rrf_scores.get(idx, 0) + 1.0 / (k + rank)
    
    # 2. BM25 검색 결과 점수
    for rank, result in enumerate(bm25_results, 1):
        idx = result['index']
        rrf_scores[idx] = rrf_scores.get(idx, 0) + 1.0 / (k + rank)
    
    # 3. RRF 점수로 정렬
    sorted_indices = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    
    # 4. Top-N 추출
    top_results = []
    for idx, score in sorted_indices[:top_n]:
        top_results.append({
            'index': idx,
            'rrf_score': score,
            'text': corpus_df.iloc[idx]['text'],
            'document_name': corpus_df.iloc[idx].get('document_name', ''),
            'title': corpus_df.iloc[idx].get('title', '')
        })
    
    return top_results

def load_ground_truth():
    """Ground Truth 로드"""
    gt_path = DATA_DIR / "ground_truth_100.csv"
    gt_df = pd.read_csv(gt_path)
    
    # rank > 0인 것만 (정답 있는 것)
    gt_valid = gt_df[gt_df['rank'] > 0].copy()
    
    print(f"📋 Ground Truth: {len(gt_valid)}개")
    return gt_valid

def evaluate_hybrid():
    """하이브리드 검색 평가"""
    print("=" * 80)
    print("🔄 하이브리드 검색 평가: BGE-M3 + BM25")
    print("=" * 80)
    
    # 1. 모델 및 데이터 로드
    print("\n📦 준비 중...")
    print("   BGE-M3 모델 로드...", end='', flush=True)
    model = SentenceTransformer('BAAI/bge-m3')
    print(" ✅")
    
    print("   Qdrant 연결...", end='', flush=True)
    client = QdrantClient(url=QDRANT_URL)
    print(" ✅")
    
    print("   Corpus 로드...", end='', flush=True)
    corpus = pd.read_csv(DATA_DIR / "corpus_all.csv")
    print(f" ✅ ({len(corpus):,}개)")
    
    # document_name → index 매핑
    doc_name_to_idx = {}
    for idx, row in corpus.iterrows():
        # document_name이 있으면 사용 (첨부파일)
        if pd.notna(row.get('document_name')) and row['document_name']:
            doc_name = row['document_name']
            # 여러 인덱스를 리스트로 저장 (중복 처리)
            if doc_name not in doc_name_to_idx:
                doc_name_to_idx[doc_name] = []
            doc_name_to_idx[doc_name].append(idx)
        # document_name이 없으면 title 사용 (크롤링 데이터)
        elif pd.notna(row.get('title')) and row['title']:
            title = row['title']
            if title not in doc_name_to_idx:
                doc_name_to_idx[title] = []
            doc_name_to_idx[title].append(idx)
    
    # BM25 인덱스 준비
    bm25 = prepare_bm25_index(corpus)
    
    # GT 로드
    gt_df = load_ground_truth()
    
    # 2. 평가
    print("\n" + "=" * 80)
    print("📊 평가 진행")
    print("=" * 80)
    
    results_baseline = {'recall@1': [], 'recall@5': [], 'mrr': []}
    results_bm25 = {'recall@1': [], 'recall@5': [], 'mrr': []}
    results_hybrid = {'recall@1': [], 'recall@5': [], 'mrr': []}
    
    evaluated = 0
    
    for _, row in gt_df.iterrows():
        query = row['query']
        gt_doc_name = row['document_name']
        
        if not isinstance(query, str) or not isinstance(gt_doc_name, str):
            continue
        
        # GT 인덱스 찾기
        gt_base = gt_doc_name.replace('.pdf', '').replace('.xlsx', '').replace('.docx', '').strip()
        
        # 1. base_doc_name으로 매칭 (첨부파일)
        corpus['base_doc_name'] = corpus['document_name'].fillna('').apply(
            lambda x: x.rsplit('_chunk', 1)[0].replace('.pdf', '').replace('.xlsx', '').replace('.docx', '').strip() if x else ''
        )
        gt_indices = set(corpus[corpus['base_doc_name'] == gt_base].index.tolist())
        
        # 2. title로 매칭 (크롤링 데이터)
        if not gt_indices:
            gt_indices = set(corpus[corpus['title'] == gt_doc_name].index.tolist())
        
        if not gt_indices:
            continue
        
        # 1. Baseline: BGE-M3만
        vector_results = vector_search(query, model, client, top_k=20)
        baseline_indices = []
        for hit in vector_results[:5]:
            doc_name = hit.payload.get('document_name', '')
            if not doc_name:
                doc_name = hit.payload.get('title', '')
            if doc_name in doc_name_to_idx:
                # 리스트의 첫 번째 인덱스 사용
                baseline_indices.append(doc_name_to_idx[doc_name][0])
        
        # Baseline Recall
        found_r1 = any(idx in gt_indices for idx in baseline_indices[:1])
        found_r5 = any(idx in gt_indices for idx in baseline_indices[:5])
        results_baseline['recall@1'].append(1.0 if found_r1 else 0.0)
        results_baseline['recall@5'].append(1.0 if found_r5 else 0.0)
        
        # Baseline MRR
        rank = 0
        for i, idx in enumerate(baseline_indices[:5], 1):
            if idx in gt_indices:
                rank = i
                break
        results_baseline['mrr'].append(1.0 / rank if rank > 0 else 0.0)
        
        # 2. BM25만
        bm25_results = bm25_search(query, bm25, corpus, top_k=20)
        bm25_indices = [r['index'] for r in bm25_results[:5]]
        
        # BM25 Recall
        found_r1 = any(idx in gt_indices for idx in bm25_indices[:1])
        found_r5 = any(idx in gt_indices for idx in bm25_indices[:5])
        results_bm25['recall@1'].append(1.0 if found_r1 else 0.0)
        results_bm25['recall@5'].append(1.0 if found_r5 else 0.0)
        
        # BM25 MRR
        rank = 0
        for i, idx in enumerate(bm25_indices[:5], 1):
            if idx in gt_indices:
                rank = i
                break
        results_bm25['mrr'].append(1.0 / rank if rank > 0 else 0.0)
        
        # 3. Hybrid: RRF
        hybrid_results = reciprocal_rank_fusion(
            vector_results, bm25_results, corpus, doc_name_to_idx, 
            k=60, top_n=5
        )
        hybrid_indices = [r['index'] for r in hybrid_results]
        
        # Hybrid Recall
        found_r1 = any(idx in gt_indices for idx in hybrid_indices[:1])
        found_r5 = any(idx in gt_indices for idx in hybrid_indices[:5])
        results_hybrid['recall@1'].append(1.0 if found_r1 else 0.0)
        results_hybrid['recall@5'].append(1.0 if found_r5 else 0.0)
        
        # Hybrid MRR
        rank = 0
        for i, idx in enumerate(hybrid_indices[:5], 1):
            if idx in gt_indices:
                rank = i
                break
        results_hybrid['mrr'].append(1.0 / rank if rank > 0 else 0.0)
        
        evaluated += 1
        
        # 진행 상황 출력
        if evaluated % 10 == 0:
            print(f"   진행: {evaluated}/{len(gt_df)}...")
    
    # 3. 결과 출력
    print("\n" + "=" * 80)
    print("📊 결과")
    print("=" * 80)
    
    print(f"\n평가 쿼리: {evaluated}개\n")
    
    print("🔹 Baseline (BGE-M3만)")
    print(f"   Recall@1: {np.mean(results_baseline['recall@1']):.2%}")
    print(f"   Recall@5: {np.mean(results_baseline['recall@5']):.2%}")
    print(f"   MRR: {np.mean(results_baseline['mrr']):.4f}")
    
    print("\n🔸 BM25만 (키워드)")
    print(f"   Recall@1: {np.mean(results_bm25['recall@1']):.2%}")
    print(f"   Recall@5: {np.mean(results_bm25['recall@5']):.2%}")
    print(f"   MRR: {np.mean(results_bm25['mrr']):.4f}")
    
    print("\n🔶 Hybrid (BGE-M3 + BM25)")
    print(f"   Recall@1: {np.mean(results_hybrid['recall@1']):.2%}")
    print(f"   Recall@5: {np.mean(results_hybrid['recall@5']):.2%}")
    print(f"   MRR: {np.mean(results_hybrid['mrr']):.4f}")
    
    print("\n📈 개선도 (Hybrid vs Baseline)")
    r1_improve = np.mean(results_hybrid['recall@1']) - np.mean(results_baseline['recall@1'])
    r5_improve = np.mean(results_hybrid['recall@5']) - np.mean(results_baseline['recall@5'])
    mrr_improve = np.mean(results_hybrid['mrr']) - np.mean(results_baseline['mrr'])
    
    print(f"   Recall@1: {r1_improve:+.2%}")
    print(f"   Recall@5: {r5_improve:+.2%}")
    print(f"   MRR: {mrr_improve:+.4f}")
    
    # 결론
    print("\n" + "=" * 80)
    print("💡 결론")
    print("=" * 80)
    
    if r5_improve > 0.05:  # 5% 이상 개선
        print("\n✅ 하이브리드 검색 채택 권장!")
        print(f"   - Recall@5 개선: {r5_improve:+.2%}")
        print(f"   - 의미 검색(BGE-M3) + 키워드 검색(BM25) 시너지")
    elif r5_improve > 0:
        print("\n🟡 약간의 개선 있음")
        print(f"   - Recall@5 개선: {r5_improve:+.2%}")
        print(f"   - 복잡도 증가 대비 개선 효과 미미")
    else:
        print("\n❌ 하이브리드 효과 없음")
        print(f"   - Recall@5 변화: {r5_improve:+.2%}")
        print(f"   - BGE-M3 단독 사용 권장")
    
    print("\n" + "=" * 80)

def main():
    print("🚀 하이브리드 검색 실험 시작!\n")
    evaluate_hybrid()
    print("\n✅ 평가 완료!")

if __name__ == "__main__":
    main()
