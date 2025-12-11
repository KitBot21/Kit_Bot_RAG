import os
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from dotenv import load_dotenv
load_dotenv()

# 테스트용 가짜 데이터 1개
data = {
    "question": ["대한민국의 수도는?"],
    "answer": ["서울입니다."],
    "contexts": [["서울은 대한민국의 수도이며..."]],
    "ground_truth": ["서울"]
}
dataset = Dataset.from_dict(data)

print("⚖️ 채점 테스트 시작...")
try:
    # API 키 확인
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ 오류: OPENAI_API_KEY 환경변수가 없습니다!")
    else:
        print(f"ℹ️ API Key 감지됨: {api_key[:5]}***")

    # 평가 실행
    results = evaluate(dataset, metrics=[faithfulness])
    print("\n✅ 채점 성공! 점수:", results)
    
except Exception as e:
    print(f"\n❌ 채점 실패! 원인:\n{e}")