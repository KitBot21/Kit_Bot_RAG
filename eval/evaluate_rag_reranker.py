import json
import sys
import os
import time
from pathlib import Path
from datasets import Dataset
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
)

from dotenv import load_dotenv
load_dotenv()

# 프로젝트 루트 경로 추가
sys.path.append(str(Path(__file__).parent.parent))

# 🔴 리랭커 버전 import
from core.rag_core_reranker import rag_with_sources 

def run_evaluation():
    data_path = Path("eval/golden_dataset.json")
    if not data_path.exists():
        print("❌ 평가 데이터셋이 없습니다: eval/golden_dataset.json")
        return

    with open(data_path, "r", encoding="utf-8") as f:
        test_data = json.load(f)

    print(f"📊 [리랭커] 총 {len(test_data)}개의 질문에 대해 평가를 시작합니다...")

    questions = []
    ground_truths = []
    answers = []
    contexts = []
    response_times = []

    for idx, item in enumerate(test_data):
        q = item["question"]
        gt = item["ground_truth"]
        
        print(f"   [{idx+1}/{len(test_data)}] 질문: {q}")
        
        start_time = time.time()
        try:
            answer_text, sources, schedule_info = rag_with_sources(q)
            elapsed_time = time.time() - start_time
        except Exception as e:
            elapsed_time = time.time() - start_time
            print(f"      ❌ 에러 발생: {e}")
            import traceback
            traceback.print_exc()
            answer_text = "에러 발생"
            sources = []

        print(f"      ⏱️ 응답 시간: {elapsed_time:.2f}초")
        response_times.append(elapsed_time)

        retrieved_docs = []
        for s in sources:
            try:
                if isinstance(s, dict):
                    text = s.get("text", "")
                elif hasattr(s, 'payload'):
                    text = s.payload.get("text", "")
                else:
                    text = str(s)
                
                if text and text.strip():
                    retrieved_docs.append(text)
            except Exception as e:
                print(f"      ⚠️ 소스 파싱 에러: {e}")
                continue
        
        if not retrieved_docs:
            retrieved_docs = ["관련 문서를 찾을 수 없습니다."]
            print(f"      ⚠️ 검색 결과 없음 (더미 텍스트 추가)")

        questions.append(q)
        ground_truths.append(gt) 
        answers.append(answer_text)
        contexts.append(retrieved_docs)

    eval_dict = {
        "question": questions,
        "answer": answers,
        "contexts": contexts,
        "ground_truth": ground_truths
    }
    hf_dataset = Dataset.from_dict(eval_dict)

    evaluator_llm = ChatOpenAI(model="gpt-4o") 
    evaluator_embeddings = OpenAIEmbeddings()

    print("\n⚖️  AI 심판이 채점을 시작합니다... (OpenAI 비용 발생)")

    try:
        results = evaluate(
            hf_dataset,
            metrics=[
                context_precision,
                context_recall,
                faithfulness,
                answer_relevancy,
            ],
            llm=evaluator_llm,
            embeddings=evaluator_embeddings,
        )

        print("\n" + "="*40)
        print("🏆 [리랭커] 최종 평가 점수")
        print("="*40)
        print(results)
        
        import numpy as np
        avg_time = np.mean(response_times)
        median_time = np.median(response_times)
        min_time = np.min(response_times)
        max_time = np.max(response_times)
        
        print("\n" + "="*40)
        print("⏱️  응답 시간 통계")
        print("="*40)
        print(f"평균: {avg_time:.2f}초")
        print(f"중앙값: {median_time:.2f}초")
        print(f"최소: {min_time:.2f}초")
        print(f"최대: {max_time:.2f}초")
        
        df = results.to_pandas()
        df['response_time'] = response_times
        save_path = "eval/evaluation_result_reranker.csv"
        df.to_csv(save_path, index=False, encoding="utf-8-sig")
        print(f"\n✅ 상세 결과가 저장되었습니다: {save_path}")
        
        timing_stats = {
            "version": "리랭커 (BGE-reranker)",
            "avg_response_time": avg_time,
            "median_response_time": median_time,
            "min_response_time": min_time,
            "max_response_time": max_time,
            "total_queries": len(response_times)
        }
        
        timing_path = Path("eval/timing_result_reranker.json")
        with open(timing_path, "w", encoding="utf-8") as f:
            json.dump(timing_stats, f, indent=2, ensure_ascii=False)
        print(f"✅ 응답 시간 통계 저장: {timing_path}")
        
    except Exception as e:
        print(f"\n❌ 평가 실행 중 에러 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_evaluation()
