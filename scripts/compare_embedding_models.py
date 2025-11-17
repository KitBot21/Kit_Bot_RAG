#!/usr/bin/env python3
"""
임베딩 모델 비교 평가 도구

여러 임베딩 모델의 성능을 비교하여 최적의 모델을 선택합니다.

평가 지표:
1. 검색 성능 (Recall@K, MRR)
2. 임베딩 속도
3. 벡터 크기 (메모리)
4. 임베딩 품질 (코사인 유사도 분포)
"""

import numpy as np
import pandas as pd
import time
from pathlib import Path
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm
import warnings
warnings.filterwarnings('ignore')

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

# 평가할 모델 목록
MODELS = {
    'bge-m3': {
        'name': 'BAAI/bge-m3',
        'dim': 1024,
        'description': 'BGE-M3 (다국어, 범용)'
    },
    'e5-base': {
        'name': 'intfloat/multilingual-e5-base',
        'dim': 768,
        'description': 'E5-Base (다국어, 균형)'
    },
    'kr-sbert': {
        'name': 'snunlp/KR-SBERT-V40K-klueNLI-augSTS',
        'dim': 768,
        'description': 'KR-SBERT (한국어 특화)'
    },
    'kosimcse': {
        'name': 'BM-K/KoSimCSE-roberta',
        'dim': 768,
        'description': 'KoSimCSE (한국어 특화)'
    },
}

def load_test_data(sample_size=None):
    """테스트 데이터 로드"""
    print(f"\n📂 테스트 데이터 로드")
    
    # Corpus 로드 (전체)
    corpus_path = DATA_DIR / "corpus_all.csv"
    df = pd.read_csv(corpus_path)
    df = df[df['text'].notna()].reset_index(drop=True)
    
    # document_name이 없으면 생성
    if 'document_name' not in df.columns:
        df['document_name'] = df['title'].fillna('Unknown')
    
    texts = df['text'].astype(str).tolist()
    
    # 쿼리 + Ground Truth 로드
    # 100개 GT가 있으면 사용, 없으면 Manual 사용
    if (DATA_DIR / "ground_truth_100.csv").exists():
        queries_path = DATA_DIR / "queries_100.txt"
        gt_path = DATA_DIR / "ground_truth_100.csv"
        print(f"   ✅ 100개 수동 GT 사용")
    else:
        queries_path = DATA_DIR / "queries_manual.txt"
        gt_path = DATA_DIR / "ground_truth_manual.csv"
        print(f"   ⚠️ Manual GT 사용 (참고용)")
    
    with queries_path.open('r', encoding='utf-8') as f:
        queries = [line.strip() for line in f if line.strip()]
    
    # Ground Truth 로드
    gt_df = pd.read_csv(gt_path)
    
    # Query → Document Name 매핑 (rank > 0인 것만, NaN 제외)
    query_to_doc = {}
    for _, row in gt_df.iterrows():
        # rank가 -1이면 정답 없음 (스킵)
        if 'rank' in row and row['rank'] <= 0:
            continue
        
        query = row['query']
        doc_name = row['document_name']
        
        # NaN이나 float 타입 제외
        if not isinstance(query, str) or not isinstance(doc_name, str):
            continue
        
        query_to_doc[query] = doc_name
    
    print(f"   문서: {len(texts):,}개 (전체 코퍼스)")
    print(f"   쿼리: {len(queries)}개")
    print(f"   Ground Truth: {len(query_to_doc)}개 매핑")
    
    return texts, queries, df, query_to_doc

def evaluate_embedding_speed(model, texts, batch_size=32):
    """임베딩 생성 속도 측정"""
    print(f"\n⏱️  임베딩 속도 측정...")
    
    start = time.time()
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=False,
        normalize_embeddings=True
    )
    elapsed = time.time() - start
    
    speed = len(texts) / elapsed
    
    print(f"   총 시간: {elapsed:.2f}초")
    print(f"   속도: {speed:.1f} docs/sec")
    
    return embeddings, elapsed, speed

def evaluate_embedding_quality(embeddings):
    """임베딩 품질 측정"""
    print(f"\n📊 임베딩 품질 분석...")
    
    # 코사인 유사도 분포 분석
    similarities = []
    sample_size = min(100, len(embeddings))
    
    for i in range(sample_size):
        for j in range(i+1, sample_size):
            sim = np.dot(embeddings[i], embeddings[j])
            similarities.append(sim)
    
    similarities = np.array(similarities)
    
    stats = {
        'mean': float(np.mean(similarities)),
        'std': float(np.std(similarities)),
        'min': float(np.min(similarities)),
        'max': float(np.max(similarities)),
        'median': float(np.median(similarities))
    }
    
    print(f"   평균 유사도: {stats['mean']:.4f}")
    print(f"   표준편차: {stats['std']:.4f}")
    print(f"   범위: [{stats['min']:.4f}, {stats['max']:.4f}]")
    
    return stats

def evaluate_retrieval_performance(model, texts, queries, df, query_to_doc):
    """검색 성능 측정 (Ground Truth 기반)"""
    print(f"\n🔍 검색 성능 평가...")
    
    # 문서 임베딩
    print(f"   문서 임베딩 중... ({len(texts):,}개)")
    doc_embeddings = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=True,
        normalize_embeddings=True
    )
    
    # 쿼리 임베딩
    print(f"   쿼리 임베딩 중... ({len(queries)}개)")
    query_embeddings = model.encode(
        queries,
        batch_size=32,
        show_progress_bar=False,
        normalize_embeddings=True
    )
    
    # Document name → indices 매핑
    # 청크 단위로 저장되어 있으므로 (예: "버스.pdf_chunk0")
    # 원본 문서명으로 그룹화
    doc_name_to_indices = {}
    for idx, row in df.iterrows():
        doc_name = row['document_name']
        # NaN이나 float 타입 건너뛰기
        if not isinstance(doc_name, str):
            continue
        if doc_name not in doc_name_to_indices:
            doc_name_to_indices[doc_name] = []
        doc_name_to_indices[doc_name].append(idx)
    
    # 각 쿼리에 대해 검색
    recall_at_1 = []
    recall_at_5 = []
    mrr_scores = []
    ndcg_scores = []
    
    evaluated_queries = 0
    
    for q_idx, query in enumerate(queries):
        # Ground Truth 확인
        if query not in query_to_doc:
            continue
        
        gt_doc_name = query_to_doc[query]
        
        # GT 문서의 인덱스들 찾기 (부분 매칭!)
        # GT: "2023-2학기 버스.pdf" → Corpus: "2023-2학기 버스.pdf_chunk0"
        gt_indices = set()
        for doc_name, indices in doc_name_to_indices.items():
            # NaN이나 float 타입 건너뛰기
            if not isinstance(doc_name, str):
                continue
            if not isinstance(gt_doc_name, str):
                continue
            
            # 부분 매칭: GT가 doc_name에 포함되어 있으면 OK
            if gt_doc_name in doc_name or doc_name.startswith(gt_doc_name.replace('.pdf', '')):
                gt_indices.update(indices)
        
        if not gt_indices:
            # 매칭되는 청크가 없으면 스킵
            continue
        
        # 쿼리 임베딩으로 검색
        q_emb = query_embeddings[q_idx]
        similarities = np.dot(doc_embeddings, q_emb)
        
        # Top-K 인덱스
        top_k_indices = np.argsort(similarities)[::-1][:5]
        
        # Recall@K 계산
        found_at_1 = any(idx in gt_indices for idx in top_k_indices[:1])
        found_at_5 = any(idx in gt_indices for idx in top_k_indices[:5])
        
        recall_at_1.append(1.0 if found_at_1 else 0.0)
        recall_at_5.append(1.0 if found_at_5 else 0.0)
        
        # MRR 계산
        reciprocal_rank = 0.0
        for rank, idx in enumerate(top_k_indices, 1):
            if idx in gt_indices:
                reciprocal_rank = 1.0 / rank
                break
        mrr_scores.append(reciprocal_rank)
        
        # NDCG 계산 (간단 버전)
        dcg = 0.0
        for rank, idx in enumerate(top_k_indices, 1):
            if idx in gt_indices:
                dcg += 1.0 / np.log2(rank + 1)
        
        # Ideal DCG (정답이 1위일 때)
        idcg = 1.0 / np.log2(2)
        ndcg = dcg / idcg if idcg > 0 else 0.0
        ndcg_scores.append(ndcg)
        
        evaluated_queries += 1
    
    if evaluated_queries == 0:
        print("   ⚠️ 평가 가능한 쿼리가 없습니다!")
        return {
            'recall@1': 0.0,
            'recall@5': 0.0,
            'mrr': 0.0,
            'ndcg': 0.0
        }
    
    results = {
        'recall@1': np.mean(recall_at_1),
        'recall@5': np.mean(recall_at_5),
        'mrr': np.mean(mrr_scores),
        'ndcg': np.mean(ndcg_scores)
    }
    
    print(f"   평가 쿼리: {evaluated_queries}개")
    print(f"   Recall@1: {results['recall@1']:.2%}")
    print(f"   Recall@5: {results['recall@5']:.2%}")
    print(f"   MRR: {results['mrr']:.4f}")
    print(f"   NDCG: {results['ndcg']:.4f}")
    
    return results

def calculate_memory_usage(embeddings):
    """메모리 사용량 계산"""
    memory_mb = embeddings.nbytes / 1024 / 1024
    return memory_mb

def evaluate_model(model_key, model_info, texts, queries, df, query_to_doc):
    """단일 모델 평가"""
    print("\n" + "=" * 80)
    print(f"🤖 모델: {model_key}")
    print(f"   이름: {model_info['name']}")
    print(f"   설명: {model_info['description']}")
    print(f"   차원: {model_info['dim']}")
    print("=" * 80)
    
    # 모델 로드
    print(f"\n📦 모델 로드 중...")
    model = SentenceTransformer(model_info['name'])
    
    # 1. 임베딩 속도 (샘플로 측정)
    sample_size = min(1000, len(texts))
    sample_texts = texts[:sample_size]
    embeddings, elapsed, speed = evaluate_embedding_speed(model, sample_texts)
    
    # 2. 임베딩 품질
    quality_stats = evaluate_embedding_quality(embeddings)
    
    # 3. 검색 성능 (전체 코퍼스 사용!)
    retrieval_results = evaluate_retrieval_performance(model, texts, queries, df, query_to_doc)
    
    # 4. 메모리 사용량
    memory_mb = calculate_memory_usage(embeddings)
    print(f"\n💾 메모리 사용량: {memory_mb:.2f} MB ({sample_size:,}개 문서)")
    
    # 전체 corpus 메모리 예측
    total_docs = len(texts)
    estimated_memory = memory_mb * (total_docs / sample_size)
    print(f"   전체 corpus 예상: {estimated_memory:.2f} MB ({total_docs:,}개)")
    
    return {
        'model_key': model_key,
        'model_name': model_info['name'],
        'dimension': model_info['dim'],
        'embedding_time': elapsed,
        'embedding_speed': speed,
        'memory_mb': memory_mb,
        'estimated_total_memory_mb': estimated_memory,
        'quality_mean': quality_stats['mean'],
        'quality_std': quality_stats['std'],
        'recall@1': retrieval_results['recall@1'],
        'recall@5': retrieval_results['recall@5'],
        'mrr': retrieval_results['mrr'],
        'ndcg': retrieval_results['ndcg']
    }

def compare_models(results):
    """모델 비교 및 순위"""
    print("\n" + "=" * 80)
    print("📊 모델 비교 결과")
    print("=" * 80)
    
    df = pd.DataFrame(results)
    
    # 정렬된 테이블 출력
    print("\n1️⃣ 검색 성능 (Recall@5 기준)")
    print("-" * 80)
    df_sorted = df.sort_values('recall@5', ascending=False)
    for _, row in df_sorted.iterrows():
        print(f"{row['model_key']:<20} R@1: {row['recall@1']:.2%}  R@5: {row['recall@5']:.2%}  MRR: {row['mrr']:.4f}  NDCG: {row['ndcg']:.4f}")
    
    print("\n2️⃣ 임베딩 속도")
    print("-" * 80)
    df_sorted = df.sort_values('embedding_speed', ascending=False)
    for _, row in df_sorted.iterrows():
        print(f"{row['model_key']:<20} {row['embedding_speed']:.1f} docs/sec  ({row['embedding_time']:.2f}초)")
    
    print("\n3️⃣ 메모리 효율성 (전체 corpus 기준)")
    print("-" * 80)
    df_sorted = df.sort_values('estimated_total_memory_mb', ascending=True)
    for _, row in df_sorted.iterrows():
        print(f"{row['model_key']:<20} {row['estimated_total_memory_mb']:.0f} MB  (차원: {row['dimension']})")
    
    print("\n4️⃣ 임베딩 품질 (유사도 분포)")
    print("-" * 80)
    df_sorted = df.sort_values('quality_std', ascending=False)
    for _, row in df_sorted.iterrows():
        print(f"{row['model_key']:<20} 평균: {row['quality_mean']:.4f}  표준편차: {row['quality_std']:.4f}")
    
    # 종합 점수 계산
    print("\n" + "=" * 80)
    print("🏆 종합 평가 (가중 점수)")
    print("=" * 80)
    
    # 정규화
    df['score_retrieval'] = (df['recall@1'] * 0.3 + df['recall@5'] * 0.5 + df['mrr'] * 0.2) * 40  # 40점
    df['score_speed'] = (df['embedding_speed'] / df['embedding_speed'].max()) * 30  # 30점
    df['score_memory'] = (1 - (df['estimated_total_memory_mb'] / df['estimated_total_memory_mb'].max())) * 20  # 20점
    df['score_quality'] = (df['quality_std'] / df['quality_std'].max()) * 10  # 10점
    
    df['total_score'] = df['score_retrieval'] + df['score_speed'] + df['score_memory'] + df['score_quality']
    
    df_sorted = df.sort_values('total_score', ascending=False)
    
    print(f"\n{'모델':<20} {'총점':<8} {'검색':<8} {'속도':<8} {'메모리':<8} {'품질':<8}")
    print("-" * 80)
    for _, row in df_sorted.iterrows():
        print(f"{row['model_key']:<20} {row['total_score']:.1f}    "
              f"{row['score_retrieval']:.1f}    "
              f"{row['score_speed']:.1f}    "
              f"{row['score_memory']:.1f}    "
              f"{row['score_quality']:.1f}")
    
    # 추천
    print("\n" + "=" * 80)
    print("💡 추천")
    print("=" * 80)
    
    best_overall = df_sorted.iloc[0]
    best_speed = df.loc[df['embedding_speed'].idxmax()]
    best_memory = df.loc[df['estimated_total_memory_mb'].idxmin()]
    best_retrieval = df.loc[df['recall@5'].idxmax()]
    
    print(f"\n🥇 종합 1위: {best_overall['model_key']}")
    print(f"   - Recall@1: {best_overall['recall@1']:.2%}, Recall@5: {best_overall['recall@5']:.2%}")
    print(f"   - MRR: {best_overall['mrr']:.4f}, NDCG: {best_overall['ndcg']:.4f}")
    print(f"   - 속도: {best_overall['embedding_speed']:.1f} docs/sec")
    print(f"   - 메모리: {best_overall['estimated_total_memory_mb']:.0f} MB")
    
    print(f"\n⚡ 속도 최고: {best_speed['model_key']}")
    print(f"   - 속도: {best_speed['embedding_speed']:.1f} docs/sec")
    
    print(f"\n💾 메모리 최고: {best_memory['model_key']}")
    print(f"   - 메모리: {best_memory['estimated_total_memory_mb']:.0f} MB")
    
    print(f"\n🎯 검색 최고: {best_retrieval['model_key']}")
    print(f"   - Recall@5: {best_retrieval['recall@5']:.2%}")
    print(f"   - MRR: {best_retrieval['mrr']:.4f}")
    
    return df_sorted

def main():
    print("=" * 80)
    print("🔬 임베딩 모델 비교 평가")
    print("=" * 80)
    
    print("\n📋 평가할 모델:")
    for key, info in MODELS.items():
        print(f"   • {key}: {info['description']} (dim={info['dim']})")
    
    # 테스트 데이터 로드
    texts, queries, df, query_to_doc = load_test_data()
    
    print("\n📌 평가 방법:")
    print(f"   - 전체 코퍼스 사용: {len(texts):,}개 문서")
    print(f"   - 평가 쿼리: {len(queries)}개 (Manual 세트)")
    print(f"   - Ground Truth: {len(query_to_doc)}개 매핑")
    print(f"   - 지표: Top-1, Top-5, MRR, NDCG")
    
    # 사용자 확인
    print("\n" + "=" * 80)
    response = input(f"\n{len(MODELS)}개 모델 평가를 시작할까요? (y/n): ").strip().lower()
    
    if response != 'y':
        print("취소됨")
        return
    
    # 각 모델 평가
    results = []
    
    for model_key, model_info in MODELS.items():
        try:
            result = evaluate_model(model_key, model_info, texts, queries, df, query_to_doc)
            results.append(result)
        except Exception as e:
            print(f"\n❌ {model_key} 평가 실패: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    if not results:
        print("\n❌ 평가된 모델이 없습니다")
        return
    
    # 비교 분석
    df_results = compare_models(results)
    
    # 결과 저장
    output_path = PROJECT_ROOT / "data" / "model_comparison_results.csv"
    df_results.to_csv(output_path, index=False)
    print(f"\n💾 결과 저장: {output_path}")
    
    print("\n" + "=" * 80)
    print("✅ 평가 완료!")
    print("=" * 80)

if __name__ == "__main__":
    main()
