#!/usr/bin/env python3
"""
RAG 시스템 종합 평가

100개 쿼리로 RAG 시스템의 실제 성능을 평가합니다.
- 검색 품질
- 답변 품질 (수동 평가용 샘플)
- 응답 시간
- 오류율
"""

import pandas as pd
import time
import sys
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from rag_demo import RAGSystem

DATA_DIR = PROJECT_ROOT / "data"

def load_test_queries(query_file="queries_new_30.txt"):
    """테스트 쿼리 로드"""
    queries_path = DATA_DIR / query_file
    
    if not queries_path.exists():
        print(f"❌ {queries_path} 파일이 없습니다.")
        return []
    
    with open(queries_path, 'r', encoding='utf-8') as f:
        queries = [line.strip() for line in f if line.strip()]
    
    return queries

def evaluate_rag_system(top_k=5, num_queries=30, query_file="queries_new_30.txt"):
    """RAG 시스템 평가"""
    print("=" * 80)
    print("🔬 RAG 시스템 종합 평가 (새로운 쿼리)")
    print("=" * 80)
    
    # 테스트 쿼리 로드
    print(f"\n📋 테스트 쿼리 로드 중...")
    all_queries = load_test_queries(query_file=query_file)
    
    if not all_queries:
        print("❌ 쿼리를 로드할 수 없습니다.")
        return
    
    # 처음 num_queries개만 사용
    queries = all_queries[:num_queries]
    print(f"   ✅ {len(queries)}개 쿼리 로드 완료")
    
    # RAG 시스템 초기화
    print(f"\n🚀 RAG 시스템 초기화...")
    rag = RAGSystem(llm_provider='openai', llm_model='gpt-4o-mini')
    
    # 평가 시작
    print(f"\n{'=' * 80}")
    print(f"📊 평가 진행 중... (Top-{top_k})")
    print(f"{'=' * 80}\n")
    
    results = []
    errors = []
    retrieval_times = []
    generation_times = []
    total_times = []
    
    for i, query in enumerate(queries, 1):
        try:
            # 진행 상황 출력
            if i % 10 == 0:
                print(f"   진행: {i}/{len(queries)}... ({i/len(queries)*100:.0f}%)")
            
            # 전체 시간 측정 시작
            start_total = time.time()
            
            # 1. 검색 단계
            start_retrieval = time.time()
            contexts = rag.retrieve(query, top_k=top_k)
            retrieval_time = time.time() - start_retrieval
            
            # 2. 생성 단계
            start_generation = time.time()
            answer = rag.generate(query, contexts)
            generation_time = time.time() - start_generation
            
            total_time = time.time() - start_total
            
            # 결과 저장
            results.append({
                'query_id': i,
                'query': query,
                'answer': answer,
                'num_contexts': len(contexts),
                'top_score': contexts[0]['score'] if contexts else 0,
                'retrieval_time_ms': retrieval_time * 1000,
                'generation_time_ms': generation_time * 1000,
                'total_time_ms': total_time * 1000,
                'success': True,
                'top_title': contexts[0]['title'] if contexts else ''
            })
            
            retrieval_times.append(retrieval_time * 1000)
            generation_times.append(generation_time * 1000)
            total_times.append(total_time * 1000)
            
        except Exception as e:
            print(f"\n⚠️  쿼리 {i} 실패: {query[:50]}...")
            print(f"    오류: {str(e)}")
            
            errors.append({
                'query_id': i,
                'query': query,
                'error': str(e)
            })
            
            results.append({
                'query_id': i,
                'query': query,
                'answer': None,
                'num_contexts': 0,
                'top_score': 0,
                'retrieval_time_ms': 0,
                'generation_time_ms': 0,
                'total_time_ms': 0,
                'success': False,
                'top_title': ''
            })
    
    # 결과 저장
    results_df = pd.DataFrame(results)
    output_path = DATA_DIR / "rag_evaluation_results.csv"
    results_df.to_csv(output_path, index=False, encoding='utf-8')
    
    # 오류 저장
    if errors:
        errors_df = pd.DataFrame(errors)
        errors_path = DATA_DIR / "rag_evaluation_errors.csv"
        errors_df.to_csv(errors_path, index=False, encoding='utf-8')
    
    # 통계 계산
    print(f"\n{'=' * 80}")
    print(f"📊 평가 결과")
    print(f"{'=' * 80}\n")
    
    successful = results_df[results_df['success'] == True]
    
    print(f"🎯 실행 통계:")
    print(f"   총 쿼리: {len(results_df)}개")
    print(f"   성공: {len(successful)}개 ({len(successful)/len(results_df)*100:.1f}%)")
    print(f"   실패: {len(errors)}개 ({len(errors)/len(results_df)*100:.1f}%)")
    
    if len(successful) > 0:
        print(f"\n⏱️  응답 시간 (성공한 쿼리):")
        print(f"   검색 시간:")
        print(f"      평균: {successful['retrieval_time_ms'].mean():.1f}ms")
        print(f"      중앙값: {successful['retrieval_time_ms'].median():.1f}ms")
        print(f"      최소: {successful['retrieval_time_ms'].min():.1f}ms")
        print(f"      최대: {successful['retrieval_time_ms'].max():.1f}ms")
        
        print(f"\n   생성 시간:")
        print(f"      평균: {successful['generation_time_ms'].mean():.1f}ms")
        print(f"      중앙값: {successful['generation_time_ms'].median():.1f}ms")
        print(f"      최소: {successful['generation_time_ms'].min():.1f}ms")
        print(f"      최대: {successful['generation_time_ms'].max():.1f}ms")
        
        print(f"\n   전체 시간:")
        print(f"      평균: {successful['total_time_ms'].mean():.1f}ms")
        print(f"      중앙값: {successful['total_time_ms'].median():.1f}ms")
        print(f"      최소: {successful['total_time_ms'].min():.1f}ms")
        print(f"      최대: {successful['total_time_ms'].max():.1f}ms")
        
        print(f"\n🔍 검색 품질:")
        print(f"   평균 Top-1 유사도: {successful['top_score'].mean():.3f}")
        print(f"   유사도 >= 0.7: {(successful['top_score'] >= 0.7).sum()}개 ({(successful['top_score'] >= 0.7).sum()/len(successful)*100:.1f}%)")
        print(f"   유사도 >= 0.6: {(successful['top_score'] >= 0.6).sum()}개 ({(successful['top_score'] >= 0.6).sum()/len(successful)*100:.1f}%)")
        print(f"   유사도 < 0.5: {(successful['top_score'] < 0.5).sum()}개 ({(successful['top_score'] < 0.5).sum()/len(successful)*100:.1f}%)")
    
    # 샘플 출력 (처음 5개)
    print(f"\n{'=' * 80}")
    print(f"📝 답변 샘플 (처음 5개)")
    print(f"{'=' * 80}")
    
    for i in range(min(5, len(successful))):
        row = successful.iloc[i]
        print(f"\n[쿼리 {row['query_id']}] {row['query']}")
        print(f"답변: {row['answer'][:200]}...")
        print(f"검색 문서: {row['top_title']}")
        print(f"유사도: {row['top_score']:.3f}")
        print(f"응답 시간: {row['total_time_ms']:.0f}ms")
    
    # 저성능 쿼리 (유사도 낮음)
    if len(successful) > 0:
        low_score = successful[successful['top_score'] < 0.5]
        if len(low_score) > 0:
            print(f"\n{'=' * 80}")
            print(f"⚠️  낮은 유사도 쿼리 (< 0.5)")
            print(f"{'=' * 80}")
            
            for i in range(min(5, len(low_score))):
                row = low_score.iloc[i]
                print(f"\n[쿼리 {row['query_id']}] {row['query']}")
                print(f"유사도: {row['top_score']:.3f}")
                print(f"검색 문서: {row['top_title']}")
    
    # 긴 응답 시간 쿼리
    if len(successful) > 0:
        slow_queries = successful.nlargest(5, 'total_time_ms')
        print(f"\n{'=' * 80}")
        print(f"🐌 느린 응답 쿼리 (Top 5)")
        print(f"{'=' * 80}")
        
        for i, row in slow_queries.iterrows():
            print(f"\n[쿼리 {row['query_id']}] {row['query']}")
            print(f"응답 시간: {row['total_time_ms']:.0f}ms")
            print(f"  - 검색: {row['retrieval_time_ms']:.0f}ms")
            print(f"  - 생성: {row['generation_time_ms']:.0f}ms")
    
    print(f"\n{'=' * 80}")
    print(f"💾 결과 저장")
    print(f"{'=' * 80}")
    print(f"   전체 결과: {output_path}")
    if errors:
        print(f"   오류 로그: {errors_path}")
    
    print(f"\n{'=' * 80}")
    print(f"✅ 평가 완료!")
    print(f"{'=' * 80}\n")
    
    return results_df

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='RAG 시스템 평가')
    parser.add_argument('--top-k', type=int, default=5, help='검색할 문서 수')
    parser.add_argument('--num-queries', type=int, default=30, help='평가할 쿼리 수')
    parser.add_argument('--query-file', type=str, default='queries_new_30.txt', help='쿼리 파일명')
    args = parser.parse_args()
    
    evaluate_rag_system(top_k=args.top_k, num_queries=args.num_queries, query_file=args.query_file)

if __name__ == "__main__":
    main()
