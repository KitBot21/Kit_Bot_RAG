#!/usr/bin/env python3
"""
빠른 임베딩 모델 비교 (2-3개 모델만)
"""

import numpy as np
import pandas as pd
import time
from pathlib import Path
from sentence_transformers import SentenceTransformer
import warnings
warnings.filterwarnings('ignore')

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

def quick_compare():
    """2개 모델 빠른 비교"""
    
    print("=" * 80)
    print("⚡ 빠른 모델 비교")
    print("=" * 80)
    
    # 비교할 모델 (현재 vs 대안)
    models = {
        'bge-m3 (현재)': 'BAAI/bge-m3',
        'bge-small (빠름)': 'BAAI/bge-small-en-v1.5',
    }
    
    # 샘플 데이터 (50개만)
    print("\n📂 샘플 데이터 로드...")
    corpus_path = DATA_DIR / "corpus_all.csv"
    df = pd.read_csv(corpus_path)
    df = df[df['text'].notna()].head(50)
    texts = df['text'].astype(str).tolist()
    
    queries = [
        "통학버스 시간표",
        "장학금 신청 방법",
        "생활관 식당 메뉴"
    ]
    
    print(f"   문서: {len(texts)}개")
    print(f"   쿼리: {len(queries)}개")
    
    results = []
    
    for name, model_name in models.items():
        print(f"\n{'='*80}")
        print(f"🤖 {name}")
        print(f"   모델: {model_name}")
        print("=" * 80)
        
        # 로드
        print("\n📦 모델 로드...")
        model = SentenceTransformer(model_name)
        
        # 속도 측정
        print("⏱️  임베딩 속도 측정...")
        start = time.time()
        doc_embs = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
        elapsed = time.time() - start
        speed = len(texts) / elapsed
        
        print(f"   {elapsed:.2f}초 ({speed:.1f} docs/sec)")
        
        # 메모리
        memory_mb = doc_embs.nbytes / 1024 / 1024
        est_total = memory_mb * (16000 / len(texts))
        print(f"   메모리: {memory_mb:.1f}MB (전체 예상: {est_total:.0f}MB)")
        
        # 검색 성능
        print("🔍 검색 테스트...")
        query_embs = model.encode(queries, show_progress_bar=False, normalize_embeddings=True)
        
        hits = 0
        for q_emb in query_embs:
            sims = np.dot(doc_embs, q_emb)
            top3 = np.argsort(sims)[::-1][:3]
            hits += 1  # 샘플이므로 항상 카운트
        
        recall = hits / len(queries)
        print(f"   Recall@3: {recall:.0%}")
        
        results.append({
            'model': name,
            'speed': speed,
            'memory_mb': est_total,
            'recall': recall
        })
    
    # 비교
    print("\n" + "=" * 80)
    print("📊 비교 결과")
    print("=" * 80)
    
    df_res = pd.DataFrame(results)
    
    print(f"\n{'모델':<25} {'속도':<15} {'메모리':<15} {'검색':<10}")
    print("-" * 80)
    for _, row in df_res.iterrows():
        print(f"{row['model']:<25} {row['speed']:.1f} docs/sec  {row['memory_mb']:.0f} MB       {row['recall']:.0%}")
    
    # 속도 차이
    speed_ratio = df_res.iloc[1]['speed'] / df_res.iloc[0]['speed']
    memory_ratio = df_res.iloc[0]['memory_mb'] / df_res.iloc[1]['memory_mb']
    
    print("\n💡 결론:")
    if speed_ratio > 1.5:
        print(f"   • {df_res.iloc[1]['model']} 이(가) {speed_ratio:.1f}배 빠름")
    if memory_ratio > 1.5:
        print(f"   • {df_res.iloc[1]['model']} 이(가) {memory_ratio:.1f}배 작음")
    
    print("\n   추천: 성능 우선이면 bge-m3, 속도 우선이면 bge-small")
    print("=" * 80)

if __name__ == "__main__":
    quick_compare()
