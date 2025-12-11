# RAG 시스템 평가 방법론

## 📊 평가 개요

### 사용 프레임워크
- **Ragas** (Retrieval Augmented Generation Assessment)
- 버전: 최신 버전 (HuggingFace Datasets 기반)
- 공식 문서: https://docs.ragas.io/

### 평가 모델
- **LLM**: `gpt-4o` (OpenAI)
- **임베딩**: `OpenAIEmbeddings` (text-embedding-ada-002)
- **용도**: 자동화된 RAG 성능 평가 (사람이 직접 평가하는 대신 AI가 평가)

---

## 🎯 평가 지표 (4가지)

### 1. Context Precision (컨텍스트 정밀도)

**정의**: 검색된 문서가 실제 질문과 **얼마나 관련이 있는지** 측정

**계산 방법**:
```
Precision = (관련 있는 문서 수) / (검색된 전체 문서 수)
```

**예시**:
- 질문: "2025학년도 개강일은?"
- 검색된 문서 5개 중:
  - ✅ 관련 있음: 2025학년도 학사일정 (3개)
  - ❌ 관련 없음: 2024학년도 공지, 셔틀버스 안내 (2개)
- **Precision = 3/5 = 0.6 (60%)**

**의미**:
- 높을수록 좋음 (불필요한 문서를 덜 가져옴)
- 검색 알고리즘의 정확도를 나타냄

---

### 2. Context Recall (컨텍스트 재현율)

**정의**: **정답에 필요한 정보**가 검색된 문서에 **얼마나 포함되어 있는지** 측정

**계산 방법**:
```
Recall = (검색된 필수 정보) / (정답에 필요한 전체 정보)
```

**예시**:
- Ground Truth: "개강일은 3월 4일이고, 수강신청은 2월 13일~14일입니다."
- 필요한 정보: [개강일, 수강신청 기간] (2개)
- 검색된 문서에 포함된 정보:
  - ✅ 개강일: 3월 4일
  - ❌ 수강신청 기간: 없음
- **Recall = 1/2 = 0.5 (50%)**

**의미**:
- 높을수록 좋음 (필요한 정보를 잘 찾아옴)
- 검색 알고리즘의 완성도를 나타냄

---

### 3. Faithfulness (충실도)

**정의**: 생성된 답변이 **검색된 문서에만 근거**하고 있는지 측정 (환각 방지)

**계산 방법**:
```
Faithfulness = (문서에 근거한 문장 수) / (답변의 전체 문장 수)
```

**평가 방식** (GPT-4o가 평가):
1. 답변을 문장 단위로 분해
2. 각 문장이 검색된 문서에 근거가 있는지 확인
3. 근거가 있는 문장 비율 계산

**예시**:
- 검색된 문서: "개강일은 3월 4일입니다."
- 생성된 답변: "개강일은 3월 4일이에요. 꼭 참석하세요! 학점이 중요합니다."
  - ✅ "개강일은 3월 4일이에요." → 문서에 근거 있음
  - ❌ "꼭 참석하세요!" → 문서에 없음 (환각)
  - ❌ "학점이 중요합니다." → 문서에 없음 (환각)
- **Faithfulness = 1/3 = 0.33 (33%)**

**의미**:
- 높을수록 좋음 (환각이 적음, 신뢰할 수 있는 답변)
- **가장 중요한 지표** (사실 왜곡 방지)

---

### 4. Answer Relevancy (답변 관련성)

**정의**: 생성된 답변이 **질문과 얼마나 관련이 있는지** 측정

**계산 방법**:
1. GPT-4o가 생성된 답변을 읽고 "이 답변에 적합한 질문"을 역생성
2. 역생성된 질문과 원래 질문의 **코사인 유사도** 계산
3. 여러 번 반복해서 평균값 사용

**예시**:
- 원래 질문: "2025학년도 개강일은 언제인가요?"
- 생성된 답변: "개강일은 3월 4일입니다."
- GPT-4o가 역생성한 질문: "2025학년도 개강일은?"
- 코사인 유사도: 0.95 (매우 유사)
- **Answer Relevancy = 0.95 (95%)**

**의미**:
- 높을수록 좋음 (질문에 정확히 답변함)
- 답변이 질문의 의도를 잘 파악했는지 측정

---

## 📝 평가 데이터셋

### Golden Dataset 구조

**파일**: `eval/golden_dataset.json`

**형식**:
```json
[
  {
    "question": "2025학년도 1학기 개강일은 언제인가요?",
    "ground_truth": "2025학년도 1학기 개강일은 2025년 3월 4일(화)입니다.",
    "contexts": [
      "2025학년도 학사일정\n2025년 03월 | 03.04(화) ~ 03.04(화) | 1학기 개강"
    ]
  }
]
```

**구성 요소**:
1. **question**: 사용자 질문
2. **ground_truth**: 정답 (사람이 작성한 정확한 답변)
3. **contexts**: 정답에 필요한 참고 문서 (옵션)

**데이터 개수**: 10개
- 학사일정 관련: 5개
- 장학금/생활관: 2개
- 시설/서비스: 3개

---

## 🔄 평가 프로세스

### 1. 데이터 수집

```python
# 각 질문에 대해
for question in golden_dataset:
    # RAG 시스템 호출
    answer, sources, schedule = rag_with_sources(question)
    
    # 결과 저장
    - user_input: 질문
    - retrieved_contexts: 검색된 문서들
    - response: 생성된 답변
    - reference: 정답 (ground_truth)
```

### 2. Ragas 평가

```python
# HuggingFace Dataset 생성
dataset = Dataset.from_dict({
    "question": [질문들],
    "answer": [생성된 답변들],
    "contexts": [검색된 문서들],
    "ground_truth": [정답들]
})

# GPT-4o로 평가
results = evaluate(
    dataset,
    metrics=[
        context_precision,  # 검색 정밀도
        context_recall,     # 검색 재현율
        faithfulness,       # 답변 충실도
        answer_relevancy,   # 답변 관련성
    ],
    llm=ChatOpenAI(model="gpt-4o"),
    embeddings=OpenAIEmbeddings()
)
```

### 3. 결과 저장

**CSV 파일**: `eval/evaluation_result_*.csv`
```csv
user_input,retrieved_contexts,response,reference,context_precision,context_recall,faithfulness,answer_relevancy,response_time
질문1,문서들,답변1,정답1,0.8,0.9,0.85,0.92,7.5
질문2,문서들,답변2,정답2,0.7,0.8,0.75,0.88,6.2
...
```

**JSON 파일**: `eval/timing_result_*.json`
```json
{
  "version": "Full (Hybrid+Reranker)",
  "avg_response_time": 8.90,
  "median_response_time": 7.95,
  "min_response_time": 2.33,
  "max_response_time": 19.26,
  "total_queries": 10
}
```

---

## 📊 평가 지표 해석 가이드

### 우수한 점수 기준

| 지표 | 우수 | 양호 | 개선 필요 |
|------|------|------|-----------|
| Context Precision | ≥ 70% | 50-70% | < 50% |
| Context Recall | ≥ 85% | 70-85% | < 70% |
| Faithfulness | ≥ 80% | 65-80% | < 65% |
| Answer Relevancy | ≥ 85% | 70-85% | < 70% |
| 응답 시간 | ≤ 5초 | 5-10초 | > 10초 |

### 지표별 개선 방향

#### Context Precision 낮음
- **문제**: 불필요한 문서를 너무 많이 검색함
- **해결**: 
  - 검색 threshold 높이기
  - 리랭커 추가
  - BM25 가중치 조정

#### Context Recall 낮음
- **문제**: 필요한 정보를 찾지 못함
- **해결**:
  - top_k 증가 (더 많은 문서 검색)
  - 시맨틱 검색 가중치 높이기
  - 청크 크기 조정

#### Faithfulness 낮음
- **문제**: 환각(Hallucination) 발생
- **해결**:
  - 프롬프트에 "문서에만 근거하라" 강조
  - Temperature 낮추기 (0.2 이하)
  - 검색 품질 향상

#### Answer Relevancy 낮음
- **문제**: 질문과 동떨어진 답변
- **해결**:
  - 질문 이해 개선 (의도 분류)
  - 답변 생성 프롬프트 개선
  - 컨텍스트 길이 증가

---

## 🔍 실제 평가 예시

### 질문 1: "2025학년도 1학기 개강일은 언제인가요?"

**검색된 문서** (5개):
1. ✅ "2025년 03월 | 03.04(화) ~ 03.04(화) | 1학기 개강"
2. ✅ "2025학년도 1학기 개시일: 03.01(토)"
3. ✅ "수강신청 확인: 03.04(화) ~ 03.10(월)"
4. ❌ "2024학년도 후기 졸업예비사정"
5. ❌ "셔틀버스 운행 안내"

**생성된 답변**:
"2025학년도 1학기 개강일은 **2025년 3월 4일(화)**이에요. 더 궁금한 점이 있으면 언제든 물어봐 주세요!"

**정답 (Ground Truth)**:
"2025학년도 1학기 개강일은 2025년 3월 4일(화)입니다."

**평가 결과**:
- **Context Precision**: 3/5 = **0.6 (60%)**
  - 관련 문서: 3개, 불필요 문서: 2개
  
- **Context Recall**: 1/1 = **1.0 (100%)**
  - 필요한 정보(개강일)가 문서에 포함됨
  
- **Faithfulness**: 1/1 = **1.0 (100%)**
  - 모든 답변이 문서에 근거함 (환각 없음)
  
- **Answer Relevancy**: **0.95 (95%)**
  - 질문과 답변이 정확히 일치

**응답 시간**: 7.2초

---

## 💰 평가 비용

### OpenAI API 비용

**GPT-4o 비용** (2024년 12월 기준):
- Input: $2.50 / 1M tokens
- Output: $10.00 / 1M tokens

**평가당 예상 비용**:
- 질문 1개당 약 2,000~3,000 tokens 사용
- Context Precision + Recall: ~1,000 tokens
- Faithfulness: ~2,000 tokens (문장 분해 + 검증)
- Answer Relevancy: ~1,000 tokens (역질문 생성)

**10개 질문 평가**:
- 총 토큰: 약 20,000~30,000 tokens
- **예상 비용: $0.30~0.50 (약 400~700원)**

---

## 🎓 베스트 프랙티스

### 1. Golden Dataset 작성 팁

✅ **좋은 예**:
```json
{
  "question": "2025학년도 1학기 개강일은 언제인가요?",
  "ground_truth": "2025학년도 1학기 개강일은 2025년 3월 4일(화)입니다."
}
```

❌ **나쁜 예**:
```json
{
  "question": "개강일",  // 너무 짧음
  "ground_truth": "3월 4일"  // 정보 부족 (연도, 요일 누락)
}
```

### 2. 평가 주기

- **개발 단계**: 변경 사항마다 평가
- **실험 단계**: 버전별 비교 평가
- **프로덕션**: 주 1회 또는 월 1회 모니터링

### 3. 결과 해석

- **단일 지표만 보지 말 것** → 4가지 지표를 종합적으로 판단
- **응답 시간도 중요** → 성능이 좋아도 느리면 사용성 저하
- **실제 사용자 피드백과 비교** → AI 평가는 참고용

---

## 📚 참고 자료

- [Ragas 공식 문서](https://docs.ragas.io/)
- [Ragas GitHub](https://github.com/explodinggradients/ragas)
- [RAG 평가 논문](https://arxiv.org/abs/2309.15217)
- [LangChain Evaluation](https://python.langchain.com/docs/guides/evaluation/)

---

## 🔧 코드 위치

- **평가 스크립트**: 
  - `eval/evaluate_rag.py` (베이스라인)
  - `eval/evaluate_rag_hybrid.py` (하이브리드)
  - `eval/evaluate_rag_reranker.py` (리랭커)
  - `eval/evaluate_rag_full.py` (Full)

- **Golden Dataset**: `eval/golden_dataset.json`

- **결과 파일**:
  - CSV: `eval/evaluation_result_*.csv`
  - JSON: `eval/timing_result_*.json`
  - Markdown: `eval/comparison_report.md`
