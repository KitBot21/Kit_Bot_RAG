#!/usr/bin/env python3
"""
RAG 답변 품질 평가
- Retrieval 성능: Top-1, Top-5 정확도
- Generation 품질: LLM 평가 기반 (정확성, 관련성, 완성도)
"""
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
import json
from rag_demo import RAGSystem
from openai import OpenAI
import os

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[1]  # scripts의 상위 폴더

class RAGEvaluator:
    def __init__(self, rag_system, evaluator_model='gpt-4o-mini'):
        """
        RAG 평가 시스템
        
        Args:
            rag_system: RAGSystem 인스턴스
            evaluator_model: 평가용 LLM 모델
        """
        self.rag = rag_system
        self.evaluator = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.evaluator_model = evaluator_model
    
    def evaluate_retrieval(self, ground_truth_path='data/ground_truth.csv'):
        """
        Retrieval 성능 평가 (기존 방식)
        
        Returns:
            dict: Top-1, Top-5 정확도, MRR
        """
        gt_df = pd.read_csv(PROJECT_ROOT / ground_truth_path)
        queries = gt_df['query'].tolist()
        correct_ids = gt_df['chunk_id'].tolist()
        
        top1_correct = 0
        top5_correct = 0
        mrr_sum = 0
        
        print("🔍 Retrieval 성능 평가 중...")
        
        for i, (query, correct_id) in enumerate(zip(queries, correct_ids)):
            contexts = self.rag.retrieve(query, top_k=5)
            retrieved_ids = [ctx['chunk_id'] for ctx in contexts]
            
            if retrieved_ids[0] == correct_id:
                top1_correct += 1
                top5_correct += 1
                mrr_sum += 1.0
            elif correct_id in retrieved_ids:
                top5_correct += 1
                rank = retrieved_ids.index(correct_id) + 1
                mrr_sum += 1.0 / rank
            
            if (i + 1) % 20 == 0:
                print(f"  Progress: {i+1}/{len(queries)}")
        
        return {
            'top1_accuracy': top1_correct / len(queries),
            'top5_accuracy': top5_correct / len(queries),
            'mrr': mrr_sum / len(queries),
            'total_queries': len(queries)
        }
    
    def evaluate_answer_quality(self, query, answer, contexts, reference_answer=None):
        """
        LLM을 사용하여 생성된 답변의 품질 평가
        
        Args:
            query: 사용자 질문
            answer: LLM 생성 답변
            contexts: 검색된 문서들
            reference_answer: 참조 답변 (있는 경우)
            
        Returns:
            dict: 평가 점수 (정확성, 관련성, 완성도)
        """
        context_str = "\n\n".join([f"[문서 {i+1}]\n{ctx['text']}" for i, ctx in enumerate(contexts)])
        
        eval_prompt = f"""다음 RAG 시스템의 답변을 평가해주세요.

<질문>
{query}
</질문>

<검색된 문서>
{context_str}
</검색된 문서>

<생성된 답변>
{answer}
</생성된 답변>

다음 기준으로 1-5점 척도로 평가하고 JSON 형식으로 답변해주세요:

1. **정확성 (Accuracy)**: 답변이 문서의 정보를 정확하게 반영하는가?
   - 5점: 완벽히 정확
   - 3점: 대체로 정확하나 일부 오류
   - 1점: 부정확하거나 잘못된 정보

2. **관련성 (Relevance)**: 답변이 질문과 관련이 있는가?
   - 5점: 질문에 직접적으로 답변
   - 3점: 관련은 있으나 부분적으로만 답변
   - 1점: 질문과 무관

3. **완성도 (Completeness)**: 답변이 충분히 상세한가?
   - 5점: 필요한 모든 정보 포함
   - 3점: 기본 정보는 있으나 부족
   - 1점: 불완전하거나 너무 간략

4. **근거성 (Groundedness)**: 답변이 제공된 문서에만 기반하는가?
   - 5점: 모든 내용이 문서에 기반
   - 3점: 대부분 문서 기반이나 일부 추론
   - 1점: 문서에 없는 내용 포함

JSON 형식으로만 답변하세요:
{{
  "accuracy": <1-5>,
  "relevance": <1-5>,
  "completeness": <1-5>,
  "groundedness": <1-5>,
  "reasoning": "<평가 이유>"
}}"""
        
        response = self.evaluator.chat.completions.create(
            model=self.evaluator_model,
            messages=[
                {"role": "system", "content": "당신은 RAG 시스템 답변을 평가하는 전문가입니다."},
                {"role": "user", "content": eval_prompt}
            ],
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        return json.loads(response.choices[0].message.content)
    
    def evaluate_all(self, sample_size=10):
        """
        전체 평가: Retrieval + Generation
        
        Args:
            sample_size: 평가할 샘플 수 (None이면 전체)
        """
        print("\n" + "="*80)
        print("📊 RAG 시스템 전체 평가")
        print("="*80)
        
        # 1. Retrieval 평가
        print("\n[1단계] Retrieval 성능 평가")
        print("-"*80)
        retrieval_metrics = self.evaluate_retrieval()
        
        print(f"\n✅ Retrieval 결과:")
        print(f"  Top-1 정확도: {retrieval_metrics['top1_accuracy']:.1%}")
        print(f"  Top-5 정확도: {retrieval_metrics['top5_accuracy']:.1%}")
        print(f"  MRR: {retrieval_metrics['mrr']:.3f}")
        
        # 2. Generation 품질 평가
        print(f"\n[2단계] Generation 품질 평가 (샘플 {sample_size}개)")
        print("-"*80)
        
        gt_df = pd.read_csv(PROJECT_ROOT / 'data/ground_truth.csv')
        if sample_size:
            gt_df = gt_df.sample(n=min(sample_size, len(gt_df)), random_state=42)
        
        all_scores = []
        
        for i, row in gt_df.iterrows():
            query = row['query']
            print(f"\n{'='*80}")
            print(f"[{i+1}/{len(gt_df)}] 질문: {query}")
            print(f"{'='*80}")
            
            # RAG 실행
            result = self.rag.query(query, top_k=5, verbose=False)
            
            # 답변 출력
            print(f"\n💬 생성된 답변:")
            print(f"{result['answer']}")
            
            # 검색된 문서 출력
            print(f"\n📚 검색된 문서 (Top-5):")
            for j, ctx in enumerate(result['contexts']):
                print(f"  [{j+1}] {ctx['chunk_id'][:40]}... (유사도: {ctx['score']:.3f})")
            
            # 답변 품질 평가
            scores = self.evaluate_answer_quality(
                query, 
                result['answer'], 
                result['contexts']
            )
            
            all_scores.append(scores)
            
            print(f"\n📊 평가 점수:")
            print(f"  정확성: {scores['accuracy']}/5")
            print(f"  관련성: {scores['relevance']}/5")
            print(f"  완성도: {scores['completeness']}/5")
            print(f"  근거성: {scores['groundedness']}/5")
            print(f"  이유: {scores['reasoning'][:100]}...")

        
        # 집계
        avg_scores = {
            'accuracy': sum(s['accuracy'] for s in all_scores) / len(all_scores),
            'relevance': sum(s['relevance'] for s in all_scores) / len(all_scores),
            'completeness': sum(s['completeness'] for s in all_scores) / len(all_scores),
            'groundedness': sum(s['groundedness'] for s in all_scores) / len(all_scores),
        }
        
        # 최종 결과
        print("\n" + "="*80)
        print("📊 최종 평가 결과")
        print("="*80)
        
        print(f"\n🔍 Retrieval 성능:")
        print(f"  Top-1 정확도: {retrieval_metrics['top1_accuracy']:.1%}")
        print(f"  Top-5 정확도: {retrieval_metrics['top5_accuracy']:.1%}")
        print(f"  MRR: {retrieval_metrics['mrr']:.3f}")
        
        print(f"\n💬 Generation 품질 (평균):")
        print(f"  정확성: {avg_scores['accuracy']:.2f}/5.0")
        print(f"  관련성: {avg_scores['relevance']:.2f}/5.0")
        print(f"  완성도: {avg_scores['completeness']:.2f}/5.0")
        print(f"  근거성: {avg_scores['groundedness']:.2f}/5.0")
        print(f"  Overall: {sum(avg_scores.values())/4:.2f}/5.0")
        
        print("="*80 + "\n")
        
        return {
            'retrieval': retrieval_metrics,
            'generation': avg_scores,
            'overall_score': sum(avg_scores.values()) / 4
        }

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='RAG 시스템 평가')
    parser.add_argument('--provider', default='openai', choices=['openai', 'ollama'])
    parser.add_argument('--model', default='gpt-4o-mini')
    parser.add_argument('--sample-size', type=int, default=10,
                        help='Generation 평가 샘플 수 (0이면 전체)')
    args = parser.parse_args()
    
    # RAG 시스템 초기화
    print("🚀 RAG 시스템 초기화 중...")
    rag = RAGSystem(
        llm_provider=args.provider,
        llm_model=args.model
    )
    
    # 평가기 초기화
    evaluator = RAGEvaluator(rag)
    
    # 전체 평가 실행
    sample_size = None if args.sample_size == 0 else args.sample_size
    results = evaluator.evaluate_all(sample_size=sample_size)

if __name__ == "__main__":
    main()
