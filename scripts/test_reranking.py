#!/usr/bin/env python3
"""
리랭킹 성능 테스트

1단계: BGE-M3로 Top-K 검색 (빠름)
2단계: Cross-Encoder로 재정렬 (정확)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer, CrossEncoder
from qdrant_client import QdrantClient
import warnings
warnings.filterwarnings('ignore')

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

COLLECTION_NAME = "kit_corpus_bge_all"
QDRANT_URL = "http://localhost:6333"

# 리랭킹 모델 옵션
RERANKER_MODELS = {
    # BGE 리랭커 (BGE-M3와 같은 제작사, 다국어 지원)
    'bge-reranker': 'BAAI/bge-reranker-base',  # BGE 리랭커 (다국어) ⭐ 추천!
    'bge-reranker-large': 'BAAI/bge-reranker-large',  # 더 정확 (느림)
    
    # MS MARCO (다국어)
    'mmarco-multi': 'cross-encoder/mmarco-mMiniLMv2-L12-H384-v1',  # 다국어 특화
    'mmarco-korean': 'cross-encoder/ms-marco-MiniLM-L-6-v2',  # 영어 기반
    
    # MS MARCO (영어 기반, 참고용)
    'ms-marco-mini': 'cross-encoder/ms-marco-MiniLM-L-6-v2',  # 빠름
    'ms-marco-base': 'cross-encoder/ms-marco-MiniLM-L-12-v2',  # 균형
}

def load_ground_truth():
    """Ground Truth 로드"""
    gt_path = DATA_DIR / "ground_truth_100.csv"
    gt_df = pd.read_csv(gt_path)
    
    # rank > 0인 것만 (정답 있는 것)
    gt_valid = gt_df[gt_df['rank'] > 0].copy()
    
    print(f"📋 Ground Truth: {len(gt_valid)}개")
    return gt_valid

def initial_search(client, model, query, top_k=20):
    """1단계: Bi-Encoder로 초기 검색"""
    query_vector = model.encode(query, normalize_embeddings=True).tolist()
    
    results = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        limit=top_k
    )
    
    return results

def rerank_results(reranker, query, results, top_n=5):
    """2단계: Cross-Encoder로 재정렬"""
    # 쿼리-문서 쌍 생성
    pairs = []
    for hit in results:
        text = hit.payload.get('text', '')
        pairs.append([query, text])
    
    # 재점수 계산
    scores = reranker.predict(pairs)
    
    # 점수로 재정렬
    ranked_indices = np.argsort(scores)[::-1][:top_n]
    
    # 재정렬된 결과
    reranked = [results[i] for i in ranked_indices]
    reranked_scores = [scores[i] for i in ranked_indices]
    
    return reranked, reranked_scores

def evaluate_with_reranking(reranker_name='ms-marco-mini', initial_k=20, final_k=5):
    """리랭킹 포함 평가"""
    print("\n" + "=" * 80)
    print(f"🔄 리랭킹 평가: {reranker_name}")
    print("=" * 80)
    print(f"   1단계: BGE-M3 → Top-{initial_k}")
    print(f"   2단계: {reranker_name} → Top-{final_k}")
    
    # 모델 로드
    print("\n📦 모델 로드 중...")
    bi_encoder = SentenceTransformer('BAAI/bge-m3')
    reranker = CrossEncoder(RERANKER_MODELS[reranker_name])
    
    # Qdrant 클라이언트
    client = QdrantClient(url=QDRANT_URL)
    
    # Ground Truth 로드
    gt_df = load_ground_truth()
    
    # Corpus 로드 (document_name 매핑용)
    corpus = pd.read_csv(DATA_DIR / "corpus_all.csv")
    
    # Corpus에 base_document_name 컬럼 추가 (chunk 제거)
    def get_base_doc_name(doc_name):
        """chunk 접미사 제거하고 확장자도 제거"""
        if not isinstance(doc_name, str):
            return ""
        # _chunkN 제거
        base = doc_name.rsplit('_chunk', 1)[0] if '_chunk' in doc_name else doc_name
        # 확장자 제거
        base = base.replace('.pdf', '').replace('.xlsx', '').replace('.docx', '').strip()
        return base
    
    corpus['base_doc_name'] = corpus['document_name'].apply(get_base_doc_name)
    
    # document_name → corpus_index 매핑 (Qdrant 검색 결과 매핑용)
    doc_name_to_idx = {}
    for idx, row in corpus.iterrows():
        # document_name이 있으면 사용 (첨부파일)
        if isinstance(row.get('document_name'), str) and row['document_name']:
            doc_name_to_idx[row['document_name']] = idx
        # document_name이 없으면 title 사용 (크롤링 데이터)
        elif isinstance(row.get('title'), str) and row['title']:
            doc_name_to_idx[row['title']] = idx
    
    # 평가
    recall_at_1_baseline = []
    recall_at_5_baseline = []
    recall_at_1_reranked = []
    recall_at_5_reranked = []
    mrr_baseline = []
    mrr_reranked = []
    
    evaluated = 0
    
    for _, row in gt_df.iterrows():
        query = row['query']
        gt_doc_name = row['document_name']
        
        if not isinstance(query, str) or not isinstance(gt_doc_name, str):
            continue
        
        # GT 문서명 정규화 (확장자 제거)
        gt_base = gt_doc_name.replace('.pdf', '').replace('.xlsx', '').replace('.docx', '').strip()
        
        # GT에 해당하는 corpus 인덱스 찾기
        # 1. base_doc_name으로 매칭 (첨부파일)
        gt_indices = set(corpus[corpus['base_doc_name'] == gt_base].index.tolist())
        
        # 2. title로 매칭 (크롤링 데이터)
        if not gt_indices:
            gt_indices = set(corpus[corpus['title'] == gt_doc_name].index.tolist())
        
        if not gt_indices:
            # 디버깅: 매칭 실패 케이스 출력
            # print(f"⚠️ 매칭 실패: {query[:40]}...")
            # print(f"   GT: '{gt_doc_name}'")
            # print(f"   GT base: '{gt_base}'")
            continue
        
        # 1단계: 초기 검색 (Top-K)
        initial_results = initial_search(client, bi_encoder, query, top_k=initial_k)
        
        # Baseline 평가 (Top-5)
        baseline_top5 = initial_results[:final_k]
        baseline_indices = []
        for hit in baseline_top5:
            # document_name 또는 title로 매칭
            doc_name = hit.payload.get('document_name', '')
            if doc_name and doc_name in doc_name_to_idx:
                baseline_indices.append(doc_name_to_idx[doc_name])
            else:
                # title로 시도
                title = hit.payload.get('title', '')
                if title and title in doc_name_to_idx:
                    baseline_indices.append(doc_name_to_idx[title])
        
        # Baseline Recall
        found_in_baseline = any(idx in gt_indices for idx in baseline_indices[:1])
        recall_at_1_baseline.append(1.0 if found_in_baseline else 0.0)
        
        found_in_baseline_5 = any(idx in gt_indices for idx in baseline_indices[:final_k])
        recall_at_5_baseline.append(1.0 if found_in_baseline_5 else 0.0)
        
        # Baseline MRR
        rank = 0
        for i, idx in enumerate(baseline_indices[:final_k], 1):
            if idx in gt_indices:
                rank = i
                break
        mrr_baseline.append(1.0 / rank if rank > 0 else 0.0)
        
        # 2단계: 리랭킹
        reranked_results, reranked_scores = rerank_results(reranker, query, initial_results, top_n=final_k)
        
        # 리랭킹 후 평가
        reranked_indices = []
        for hit in reranked_results:
            # document_name 또는 title로 매칭
            doc_name = hit.payload.get('document_name', '')
            if doc_name and doc_name in doc_name_to_idx:
                reranked_indices.append(doc_name_to_idx[doc_name])
            else:
                # title로 시도
                title = hit.payload.get('title', '')
                if title and title in doc_name_to_idx:
                    reranked_indices.append(doc_name_to_idx[title])
        
        # Reranked Recall
        found_in_reranked = any(idx in gt_indices for idx in reranked_indices[:1])
        recall_at_1_reranked.append(1.0 if found_in_reranked else 0.0)
        
        found_in_reranked_5 = any(idx in gt_indices for idx in reranked_indices[:final_k])
        recall_at_5_reranked.append(1.0 if found_in_reranked_5 else 0.0)
        
        # Reranked MRR
        rank = 0
        for i, idx in enumerate(reranked_indices[:final_k], 1):
            if idx in gt_indices:
                rank = i
                break
        mrr_reranked.append(1.0 / rank if rank > 0 else 0.0)
        
        evaluated += 1
        
        # 첫 3개 쿼리는 상세 디버깅
        if evaluated <= 3:
            print(f"\n🔍 디버깅 #{evaluated}: {query[:50]}...")
            print(f"   GT 문서: '{gt_doc_name}' (base: '{gt_base}')")
            print(f"   GT 인덱스: {list(gt_indices)[:3]}...")
            print(f"   Baseline Top-5 인덱스: {baseline_indices}")
            print(f"   Reranked Top-5 인덱스: {reranked_indices}")
            print(f"   Baseline Hit: {any(idx in gt_indices for idx in baseline_indices)}")
            print(f"   Reranked Hit: {any(idx in gt_indices for idx in reranked_indices)}")
        
        if evaluated % 10 == 0:
            print(f"   진행: {evaluated}/{len(gt_df)}...")
    
    # 결과 출력
    print("\n" + "=" * 80)
    print("📊 결과")
    print("=" * 80)
    
    print(f"\n평가 쿼리: {evaluated}개")
    
    print("\n🔹 Baseline (BGE-M3만)")
    print(f"   Recall@1: {np.mean(recall_at_1_baseline):.2%}")
    print(f"   Recall@5: {np.mean(recall_at_5_baseline):.2%}")
    print(f"   MRR: {np.mean(mrr_baseline):.4f}")
    
    print(f"\n🔸 Reranked (BGE-M3 + {reranker_name})")
    print(f"   Recall@1: {np.mean(recall_at_1_reranked):.2%}")
    print(f"   Recall@5: {np.mean(recall_at_5_reranked):.2%}")
    print(f"   MRR: {np.mean(mrr_reranked):.4f}")
    
    print("\n📈 개선도")
    r1_improve = np.mean(recall_at_1_reranked) - np.mean(recall_at_1_baseline)
    r5_improve = np.mean(recall_at_5_reranked) - np.mean(recall_at_5_baseline)
    mrr_improve = np.mean(mrr_reranked) - np.mean(mrr_baseline)
    
    print(f"   Recall@1: {r1_improve:+.2%}")
    print(f"   Recall@5: {r5_improve:+.2%}")
    print(f"   MRR: {mrr_improve:+.4f}")
    
    return {
        'baseline_r1': np.mean(recall_at_1_baseline),
        'baseline_r5': np.mean(recall_at_5_baseline),
        'baseline_mrr': np.mean(mrr_baseline),
        'reranked_r1': np.mean(recall_at_1_reranked),
        'reranked_r5': np.mean(recall_at_5_reranked),
        'reranked_mrr': np.mean(mrr_reranked),
    }

def main():
    print("=" * 80)
    print("🔄 리랭킹 성능 테스트")
    print("=" * 80)
    
    print("\n리랭킹 모델 옵션:")
    print("\n🔥 BGE 리랭커 (추천! BGE-M3와 같은 제작사):")
    print("   1. bge-reranker ⭐ - BGE-M3와 호환성 최고, 다국어 지원")
    print("   2. bge-reranker-large - 더 정확 (느림)")
    
    print("\n🇰🇷 MS MARCO 다국어:")
    print("   3. mmarco-multi - 다국어 특화")
    print("   4. mmarco-korean - 영어 기반")
    
    print("\n🇺🇸 MS MARCO 영어 (참고):")
    print("   5. ms-marco-mini - 빠름")
    print("   6. ms-marco-base - 더 정확")
    
    print("\n추천: bge-reranker (BGE-M3와 최고 호환)")
    
    choice = input("\n선택 (1-6 또는 모델명) [Enter=1]: ").strip() or '1'
    
    # 숫자 선택 처리
    model_map = {
        '1': 'bge-reranker',
        '2': 'bge-reranker-large',
        '3': 'mmarco-multi',
        '4': 'mmarco-korean',
        '5': 'ms-marco-mini',
        '6': 'ms-marco-base',
    }
    
    if choice in model_map:
        choice = model_map[choice]
    
    if choice not in RERANKER_MODELS:
        print(f"❌ 잘못된 선택. bge-reranker 사용")
        choice = 'bge-reranker'
    
    # 평가 실행
    results = evaluate_with_reranking(
        reranker_name=choice,
        initial_k=20,  # 1단계: Top-20
        final_k=5      # 2단계: Top-5
    )
    
    print("\n" + "=" * 80)
    print("✅ 평가 완료!")
    print("=" * 80)

if __name__ == "__main__":
    main()
