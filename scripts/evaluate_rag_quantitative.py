#!/usr/bin/env python3
"""
RAG 시스템 정량적 평가

1. Retrieval 성능: Recall@K, MRR
2. Generation 품질: 정확성, 관련성, 완성도, 근거성 (수동 평가용 샘플)
"""

import pandas as pd
import numpy as np
import sys
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from rag_demo import RAGSystem

DATA_DIR = PROJECT_ROOT / "data"

def load_ground_truth():
    """Ground Truth 로드"""
    gt_path = DATA_DIR / "ground_truth_100.csv"
    gt_df = pd.read_csv(gt_path)
    
    # rank > 0인 것만 (정답 있는 것)
    gt_valid = gt_df[gt_df['rank'] > 0].copy()
    
    return gt_valid

def evaluate_retrieval():
    """Retrieval 성능 평가"""
    print("=" * 80)
    print("📊 RAG 시스템 정량적 평가")
    print("=" * 80)
    
    # Ground Truth 로드
    print("\n📋 Ground Truth 로드 중...")
    gt_df = load_ground_truth()
    print(f"   ✅ {len(gt_df)}개 쿼리 (정답 있는 것만)")
    
    # RAG 시스템 초기화 (Retrieval만)
    print(f"\n🚀 RAG 시스템 초기화...")
    rag = RAGSystem(llm_provider='openai', llm_model='gpt-4o-mini')
    
    # Corpus 로드
    print(f"\n📚 Corpus 로드...")
    corpus = pd.read_csv(DATA_DIR / "corpus_all.csv")
    
    # Document name → indices 매핑
    doc_name_to_idx = {}
    for idx, row in corpus.iterrows():
        # document_name 우선
        if pd.notna(row.get('document_name')) and row['document_name']:
            doc_name = row['document_name']
            if doc_name not in doc_name_to_idx:
                doc_name_to_idx[doc_name] = []
            doc_name_to_idx[doc_name].append(idx)
        # title 대체
        elif pd.notna(row.get('title')) and row['title']:
            title = row['title']
            if title not in doc_name_to_idx:
                doc_name_to_idx[title] = []
            doc_name_to_idx[title].append(idx)
    
    print(f"   ✅ {len(corpus):,}개 문서")
    
    # 평가 시작
    print("\n" + "=" * 80)
    print("🔍 Retrieval 성능 평가")
    print("=" * 80)
    
    recall_at_1 = []
    recall_at_3 = []
    recall_at_5 = []
    mrr_scores = []
    
    generation_results = []  # LLM 답변 샘플 저장
    
    evaluated = 0
    
    for _, row in gt_df.iterrows():
        query = row['query']
        gt_doc_name = row['document_name']
        
        if not isinstance(query, str) or not isinstance(gt_doc_name, str):
            continue
        
        # GT 인덱스 찾기
        gt_base = gt_doc_name.replace('.pdf', '').replace('.xlsx', '').replace('.docx', '').strip()
        
        # 1. base_doc_name으로 매칭
        corpus['base_doc_name'] = corpus['document_name'].fillna('').apply(
            lambda x: x.rsplit('_chunk', 1)[0].replace('.pdf', '').replace('.xlsx', '').replace('.docx', '').strip() if x else ''
        )
        gt_indices = set(corpus[corpus['base_doc_name'] == gt_base].index.tolist())
        
        # 2. title로 매칭
        if not gt_indices:
            gt_indices = set(corpus[corpus['title'] == gt_doc_name].index.tolist())
        
        if not gt_indices:
            continue
        
        # Retrieval
        contexts = rag.retrieve(query, top_k=5)
        
        # 검색된 문서의 인덱스 찾기
        retrieved_indices = []
        for ctx in contexts:
            doc_name = ctx.get('title', '')
            if doc_name in doc_name_to_idx:
                # 첫 번째 인덱스만 사용
                retrieved_indices.append(doc_name_to_idx[doc_name][0])
        
        # Recall 계산
        found_at_1 = any(idx in gt_indices for idx in retrieved_indices[:1])
        found_at_3 = any(idx in gt_indices for idx in retrieved_indices[:3])
        found_at_5 = any(idx in gt_indices for idx in retrieved_indices[:5])
        
        recall_at_1.append(1.0 if found_at_1 else 0.0)
        recall_at_3.append(1.0 if found_at_3 else 0.0)
        recall_at_5.append(1.0 if found_at_5 else 0.0)
        
        # MRR 계산
        rank = 0
        for i, idx in enumerate(retrieved_indices[:5], 1):
            if idx in gt_indices:
                rank = i
                break
        mrr_scores.append(1.0 / rank if rank > 0 else 0.0)
        
        evaluated += 1
        
        # 진행 상황
        if evaluated % 10 == 0:
            print(f"   진행: {evaluated}/{len(gt_df)}...")
        
        # 처음 10개는 LLM 답변도 생성 (수동 평가용)
        if evaluated <= 10:
            answer = rag.generate(query, contexts)
            generation_results.append({
                'query_id': evaluated,
                'query': query,
                'answer': answer,
                'top_context': contexts[0]['text'][:200] if contexts else '',
                'found_in_top1': found_at_1,
                'found_in_top5': found_at_5
            })
    
    # 결과 출력
    print("\n" + "=" * 80)
    print("📊 Retrieval 성능 결과")
    print("=" * 80)
    
    print(f"\n평가 쿼리: {evaluated}개\n")
    
    recall_1 = np.mean(recall_at_1)
    recall_3 = np.mean(recall_at_3)
    recall_5 = np.mean(recall_at_5)
    mrr = np.mean(mrr_scores)
    
    print("🔍 Retrieval 성능:")
    print(f"   Top-1 정확도: {recall_1:.1%} (1위에서 정답 찾기)")
    print(f"   Top-3 정확도: {recall_3:.1%} (상위 3개 중 정답 포함)")
    print(f"   Top-5 정확도: {recall_5:.1%} (상위 5개 중 정답 포함)")
    print(f"   MRR: {mrr:.3f}")
    
    # 평가 기준
    print("\n📏 평가 기준:")
    if recall_5 >= 0.9:
        print(f"   Top-5: ⭐⭐⭐⭐⭐ 우수 ({recall_5:.1%})")
    elif recall_5 >= 0.7:
        print(f"   Top-5: ⭐⭐⭐⭐ 양호 ({recall_5:.1%})")
    elif recall_5 >= 0.5:
        print(f"   Top-5: ⭐⭐⭐ 보통 ({recall_5:.1%})")
    else:
        print(f"   Top-5: ⭐⭐ 개선 필요 ({recall_5:.1%})")
    
    # Generation 샘플 저장
    if generation_results:
        gen_df = pd.DataFrame(generation_results)
        gen_path = DATA_DIR / "rag_generation_samples.csv"
        gen_df.to_csv(gen_path, index=False, encoding='utf-8')
        
        print("\n" + "=" * 80)
        print("💬 Generation 품질 평가 (수동)")
        print("=" * 80)
        print(f"\n{len(generation_results)}개 샘플 답변이 생성되었습니다.")
        print(f"파일: {gen_path}")
        print("\n다음 기준으로 수동 평가해주세요 (5점 척도):")
        print("   1. 정확성: 답변이 사실적으로 정확한가?")
        print("   2. 관련성: 질문과 관련있는 답변인가?")
        print("   3. 완성도: 충분히 상세하고 완전한가?")
        print("   4. 근거성: 제공된 문서에 근거하는가?")
        
        # 샘플 출력
        print("\n📝 답변 샘플 (처음 3개):")
        for i in range(min(3, len(generation_results))):
            sample = generation_results[i]
            print(f"\n[{i+1}] {sample['query']}")
            print(f"답변: {sample['answer'][:150]}...")
            print(f"Top-1 정답: {'✅' if sample['found_in_top1'] else '❌'}")
            print(f"Top-5 정답: {'✅' if sample['found_in_top5'] else '❌'}")
    
    # 개선 방향 제시
    print("\n" + "=" * 80)
    print("💡 개선 방향")
    print("=" * 80)
    
    improvements = []
    
    if recall_1 < 0.4:
        improvements.append(f"1. Top-1 정확도 개선: {recall_1:.1%} → 40%+ 목표")
        improvements.append("   - 검색 모델 fine-tuning")
        improvements.append("   - 쿼리 확장 (동의어, 유사어)")
        improvements.append("   - 문서 메타데이터 활용")
    
    if recall_5 < 0.8:
        improvements.append(f"2. Top-5 정확도 개선: {recall_5:.1%} → 80%+ 목표")
        improvements.append("   - 더 많은 관련 문서 수집")
        improvements.append("   - 청크 크기 재조정")
        improvements.append("   - 하이브리드 검색 고려")
    
    if mrr < 0.5:
        improvements.append(f"3. MRR 개선: {mrr:.3f} → 0.5+ 목표")
        improvements.append("   - 리랭킹 재검토 (다른 모델)")
        improvements.append("   - 쿼리-문서 유사도 가중치 조정")
    
    improvements.append("4. Generation 품질 개선:")
    improvements.append("   - 프롬프트 개선: LLM에게 더 상세한 답변 요청")
    improvements.append("   - 컨텍스트 확장: Top-3 → Top-5 문서 제공")
    improvements.append("   - max_tokens 증가: 800 → 1200 (더 완성도 높은 답변)")
    
    if improvements:
        for imp in improvements:
            print(imp)
    else:
        print("✅ 현재 성능 우수! 유지 권장")
    
    print("\n" + "=" * 80)
    print("✅ 평가 완료!")
    print("=" * 80)
    
    # 결과 요약 저장
    summary = {
        'evaluated_queries': evaluated,
        'recall_at_1': recall_1,
        'recall_at_3': recall_3,
        'recall_at_5': recall_5,
        'mrr': mrr
    }
    
    summary_df = pd.DataFrame([summary])
    summary_path = DATA_DIR / "rag_quantitative_evaluation.csv"
    summary_df.to_csv(summary_path, index=False)
    print(f"\n💾 평가 결과 저장: {summary_path}")
    
    return summary

def main():
    evaluate_retrieval()

if __name__ == "__main__":
    main()
