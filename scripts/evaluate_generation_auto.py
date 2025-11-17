#!/usr/bin/env python3
"""
LLM 기반 자동 Generation 품질 평가

GPT-4를 평가자로 사용하여 4가지 기준으로 자동 채점:
1. 정확성 (Accuracy)
2. 관련성 (Relevance)
3. 완성도 (Completeness)
4. 근거성 (Groundedness)
"""

import pandas as pd
import sys
from pathlib import Path
import warnings
import time
import os
from dotenv import load_dotenv
warnings.filterwarnings('ignore')

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from openai import OpenAI

# .env 파일 로드
load_dotenv()

DATA_DIR = PROJECT_ROOT / "data"

# OpenAI API 클라이언트 초기화
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

EVALUATION_PROMPT = """당신은 대학 챗봇 답변 품질을 평가하는 전문가입니다.

다음 4가지 기준으로 답변을 평가해주세요:

1. **정확성 (Accuracy)**: 답변이 사실적으로 정확한가?
   - 5점: 모든 정보가 정확하고 검증 가능
   - 4점: 핵심은 정확하나 일부 사소한 오류
   - 3점: 일부 정보는 정확하지만 중요한 오류 포함
   - 2점: 대부분의 정보가 틀리거나 오래됨
   - 1점: 모든 정보가 틀리거나 환각(hallucination)

2. **관련성 (Relevance)**: 질문과 관련있는 답변인가?
   - 5점: 질문에 정확히 답변, 불필요한 정보 없음
   - 4점: 핵심 답변 포함, 약간의 추가 정보
   - 3점: 답변은 하지만 불필요한 정보가 많음
   - 2점: 질문과 간접적으로만 관련
   - 1점: 질문과 전혀 관련없는 답변

3. **완성도 (Completeness)**: 충분히 상세하고 완전한가?
   - 5점: 모든 필요 정보 포함, 추가 질문 불필요
   - 4점: 핵심 정보 포함, 일부 세부사항 누락
   - 3점: 기본 정보만 제공, 추가 질문 필요
   - 2점: 매우 간략, 실질적 도움 부족
   - 1점: 거의 정보 없음 또는 "모르겠습니다"

4. **근거성 (Groundedness)**: 제공된 문서에 근거하는가?
   - 5점: 모든 정보가 문서에서 추출됨
   - 4점: 대부분 문서 기반, 일부 논리적 추론
   - 3점: 문서 기반 + 일반 지식 혼합
   - 2점: 대부분 일반 지식, 문서는 부분적
   - 1점: 문서와 무관한 정보 또는 환각

---

**질문**: {query}

**답변**: {answer}

**제공된 컨텍스트** (상위 검색 문서):
{context}

---

다음 JSON 형식으로만 답변해주세요 (다른 설명 없이):
{{
  "accuracy": <1-5>,
  "relevance": <1-5>,
  "completeness": <1-5>,
  "groundedness": <1-5>,
  "reasoning": "<각 점수에 대한 간단한 이유>"
}}
"""

def evaluate_answer(query: str, answer: str, context: str) -> dict:
    """LLM을 사용하여 답변 평가"""
    
    prompt = EVALUATION_PROMPT.format(
        query=query,
        answer=answer,
        context=context[:1000]  # 컨텍스트 길이 제한
    )
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "당신은 객관적인 답변 품질 평가자입니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,  # 일관성을 위해 낮게
            response_format={"type": "json_object"}
        )
        
        import json
        result = json.loads(response.choices[0].message.content)
        
        return {
            'accuracy': result.get('accuracy', 0),
            'relevance': result.get('relevance', 0),
            'completeness': result.get('completeness', 0),
            'groundedness': result.get('groundedness', 0),
            'reasoning': result.get('reasoning', '')
        }
        
    except Exception as e:
        print(f"   ⚠️ 평가 실패: {e}")
        return {
            'accuracy': 0,
            'relevance': 0,
            'completeness': 0,
            'groundedness': 0,
            'reasoning': f'평가 실패: {str(e)}'
        }

def main():
    print("=" * 80)
    print("🤖 LLM 기반 자동 Generation 품질 평가")
    print("=" * 80)
    
    # 샘플 데이터 로드
    samples_path = DATA_DIR / "rag_generation_samples.csv"
    
    if not samples_path.exists():
        print(f"❌ 오류: {samples_path} 파일이 없습니다.")
        print("먼저 evaluate_rag_quantitative.py를 실행하세요.")
        return
    
    df = pd.read_csv(samples_path)
    print(f"\n📋 {len(df)}개 샘플 답변 평가 중...\n")
    
    results = []
    
    for idx, row in df.iterrows():
        query_id = row['query_id']
        query = row['query']
        answer = row['answer']
        context = row['top_context']
        
        print(f"[{query_id}/10] {query[:50]}...")
        
        # LLM 평가
        eval_result = evaluate_answer(query, answer, context)
        
        result = {
            'query_id': query_id,
            'query': query,
            'answer': answer,
            'accuracy': eval_result['accuracy'],
            'relevance': eval_result['relevance'],
            'completeness': eval_result['completeness'],
            'groundedness': eval_result['groundedness'],
            'overall': round(
                (eval_result['accuracy'] + eval_result['relevance'] + 
                 eval_result['completeness'] + eval_result['groundedness']) / 4, 
                2
            ),
            'reasoning': eval_result['reasoning']
        }
        
        results.append(result)
        
        print(f"   정확성: {eval_result['accuracy']}/5, "
              f"관련성: {eval_result['relevance']}/5, "
              f"완성도: {eval_result['completeness']}/5, "
              f"근거성: {eval_result['groundedness']}/5")
        print(f"   → Overall: {result['overall']}/5.0")
        print()
        
        # API 속도 제한 고려
        time.sleep(1)
    
    # 결과 저장
    results_df = pd.DataFrame(results)
    output_path = DATA_DIR / "rag_generation_evaluation_auto.csv"
    results_df.to_csv(output_path, index=False, encoding='utf-8')
    
    # 통계 계산
    print("\n" + "=" * 80)
    print("📊 평가 결과 통계")
    print("=" * 80)
    
    avg_accuracy = results_df['accuracy'].mean()
    avg_relevance = results_df['relevance'].mean()
    avg_completeness = results_df['completeness'].mean()
    avg_groundedness = results_df['groundedness'].mean()
    avg_overall = results_df['overall'].mean()
    
    print(f"\n💬 Generation 품질 (5점 만점):")
    print(f"   정확성: {avg_accuracy:.2f}/5.0", end="")
    if avg_accuracy >= 4.0:
        print(" ✅ (우수)")
    elif avg_accuracy >= 3.5:
        print(" ✅ (양호)")
    elif avg_accuracy >= 3.0:
        print(" ⚠️ (보통)")
    else:
        print(" ❌ (개선 필요)")
    
    print(f"   관련성: {avg_relevance:.2f}/5.0", end="")
    if avg_relevance >= 4.0:
        print(" ✅ (우수)")
    elif avg_relevance >= 3.5:
        print(" ✅ (양호)")
    elif avg_relevance >= 3.0:
        print(" ⚠️ (보통)")
    else:
        print(" ❌ (개선 필요)")
    
    print(f"   완성도: {avg_completeness:.2f}/5.0", end="")
    if avg_completeness >= 4.0:
        print(" ✅ (우수)")
    elif avg_completeness >= 3.5:
        print(" ✅ (양호)")
    elif avg_completeness >= 3.0:
        print(" ⚠️ (보통)")
    else:
        print(" ❌ (개선 필요)")
    
    print(f"   근거성: {avg_groundedness:.2f}/5.0", end="")
    if avg_groundedness >= 4.0:
        print(" ✅ (우수)")
    elif avg_groundedness >= 3.5:
        print(" ✅ (양호)")
    elif avg_groundedness >= 3.0:
        print(" ⚠️ (보통)")
    else:
        print(" ❌ (개선 필요)")
    
    print(f"   Overall: {avg_overall:.2f}/5.0", end="")
    if avg_overall >= 4.5:
        print(" → A등급 (우수)")
    elif avg_overall >= 4.0:
        print(" → B등급 (양호)")
    elif avg_overall >= 3.5:
        print(" → C등급 (보통)")
    elif avg_overall >= 3.0:
        print(" → D등급 (미흡)")
    else:
        print(" → F등급 (부적합)")
    
    # 개선 방향
    print("\n" + "=" * 80)
    print("💡 개선 방향")
    print("=" * 80)
    
    improvements = []
    
    if avg_groundedness < 3.5:
        improvements.append("🚨 **최우선**: 근거성 개선 - 환각 방지 필요")
        improvements.append("   - 프롬프트 강화: '문서에 없는 정보는 답변하지 마세요'")
        improvements.append("   - Temperature 낮추기: 0.3 → 0.0")
        improvements.append("   - System prompt에 근거성 강조")
    
    if avg_accuracy < 3.5:
        improvements.append("⚠️ **높음**: 정확성 개선 - 틀린 정보 제공")
        improvements.append("   - Corpus 업데이트 (최신 정보)")
        improvements.append("   - 오래된 문서 필터링")
        improvements.append("   - 문서에 날짜 메타데이터 추가")
    
    if avg_relevance < 3.5:
        improvements.append("⚠️ **높음**: 관련성 개선 - 질문 회피")
        improvements.append("   - Retrieval 성능 개선")
        improvements.append("   - 프롬프트: '질문에 직접 답변하세요'")
        improvements.append("   - 불필요한 정보 제거")
    
    if avg_completeness < 3.5:
        improvements.append("📝 **중간**: 완성도 개선 - 너무 간략")
        improvements.append("   - max_tokens 증가: 800 → 1200")
        improvements.append("   - 프롬프트: '상세하게 답변하세요'")
        improvements.append("   - Top-K 증가: 3 → 5")
    
    if improvements:
        for imp in improvements:
            print(imp)
    else:
        print("✅ 모든 기준이 양호합니다!")
        print("   현재 성능 유지 및 미세 조정 권장")
    
    # 샘플 분석
    print("\n" + "=" * 80)
    print("📝 주요 샘플 분석")
    print("=" * 80)
    
    # 최고 점수
    best = results_df.loc[results_df['overall'].idxmax()]
    print(f"\n✅ **최고 점수** ({best['overall']}/5.0):")
    print(f"   질문: {best['query'][:60]}...")
    print(f"   점수: 정확성 {best['accuracy']}, 관련성 {best['relevance']}, "
          f"완성도 {best['completeness']}, 근거성 {best['groundedness']}")
    print(f"   이유: {best['reasoning'][:100]}...")
    
    # 최저 점수
    worst = results_df.loc[results_df['overall'].idxmin()]
    print(f"\n❌ **최저 점수** ({worst['overall']}/5.0):")
    print(f"   질문: {worst['query'][:60]}...")
    print(f"   점수: 정확성 {worst['accuracy']}, 관련성 {worst['relevance']}, "
          f"완성도 {worst['completeness']}, 근거성 {worst['groundedness']}")
    print(f"   이유: {worst['reasoning'][:100]}...")
    
    print("\n" + "=" * 80)
    print("✅ 평가 완료!")
    print("=" * 80)
    print(f"\n💾 결과 저장: {output_path}")
    
    # 요약 저장
    summary = {
        'avg_accuracy': avg_accuracy,
        'avg_relevance': avg_relevance,
        'avg_completeness': avg_completeness,
        'avg_groundedness': avg_groundedness,
        'avg_overall': avg_overall
    }
    
    summary_df = pd.DataFrame([summary])
    summary_path = DATA_DIR / "rag_generation_evaluation_summary.csv"
    summary_df.to_csv(summary_path, index=False)
    print(f"💾 요약 저장: {summary_path}")

if __name__ == "__main__":
    main()
