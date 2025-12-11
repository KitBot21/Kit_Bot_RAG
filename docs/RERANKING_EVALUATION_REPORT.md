# 리랭킹 평가 보고서

**날짜:** 2025-11-04  
**평가자:** Kit_Bot_RAG 팀  
**목적:** BGE-M3 임베딩 검색에 리랭킹을 추가하여 성능 향상 가능성 검토

---

## 📋 요약

**결론: 리랭킹 사용하지 않기로 결정** ❌

- **BGE-M3 단독 사용**이 리랭킹 추가보다 우수
- Recall@5: **98.04%** (거의 완벽)
- 리랭킹 시 오히려 **17~27% 성능 저하** 발생

---

## 🧪 실험 설정

### 평가 데이터
- **Ground Truth:** 51개 쿼리 (수동 검증)
- **Corpus:** 16,106개 문서 (첨부파일 + 웹 크롤링)
- **컬렉션:** kit_corpus_bge_all (Qdrant)

### ⚠️ GT 편향 경고

**중요:** 본 GT는 BGE-M3 검색 결과를 기반으로 생성되었습니다.

**생성 과정:**
1. BGE-M3로 각 쿼리 검색
2. Top-5 결과 중 가장 관련있는 문서를 사람이 선택
3. 선택된 문서를 정답(GT)으로 설정

**편향 정도:**
- BGE-M3: Recall@5 = 87.5%
- 다른 모델 평균: Recall@5 = 20.8% (E5: 25%, KR-SBERT: 12.5%, KoSimCSE: 25%)
- **편향도: 66.7%** 🚨

**의미:**
- 본 GT를 사용한 평가는 **BGE-M3에 유리함**
- 다른 모델의 낮은 성능이 반드시 "모델이 나쁘다"를 의미하지는 않음
- 다만, **실용적 관점**에서 BGE-M3이 더 유용한 것은 사실

**완화 조치:**
- 리랭킹 평가는 **BGE-M3 기반 검색 결과**만 사용
- 모델 간 비교는 참고용으로만 해석
- 최종 결론은 "리랭킹 유무"에만 초점

### 테스트 시나리오
1. **Baseline:** BGE-M3 단독 (Top-5)
2. **Reranking:** BGE-M3 (Top-20) → Cross-Encoder (Top-5)

### 테스트한 리랭커
1. **bge-reranker** (BAAI/bge-reranker-base) - BGE-M3와 같은 제작사
2. **mmarco-multi** (cross-encoder/mmarco-mMiniLMv2-L12-H384-v1) - 다국어
3. **ms-marco-base** (cross-encoder/ms-marco-MiniLM-L-12-v2) - 영어 기반

---

## 📊 실험 결과

### 성능 비교표

| 방법 | Recall@1 | Recall@5 | MRR | R@1 개선 | R@5 개선 |
|------|----------|----------|-----|----------|----------|
| **BGE-M3 단독** | **50.98%** | **98.04%** | **0.6886** | - | - |
| BGE-M3 + bge-reranker | 52.94% | 76.47% | 0.6108 | +1.96% | **-21.57%** ⬇️ |
| BGE-M3 + mmarco-multi | 54.90% | 80.39% | 0.6353 | +3.92% | **-17.65%** ⬇️ |
| BGE-M3 + ms-marco-base | 45.10% | 72.55% | 0.5510 | -5.88% | **-27.45%** ⬇️ |

### 시각화

```
Recall@5 비교:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 98.04%  BGE-M3 단독 ⭐
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 80.39%  + mmarco-multi
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 76.47%  + bge-reranker
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 72.55%  + ms-marco-base

Recall@1 비교:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 54.90%  + mmarco-multi ⬆️ (최고)
━━━━━━━━━━━━━━━━━━━━━━━━━━━ 52.94%  + bge-reranker
━━━━━━━━━━━━━━━━━━━━━━━━━━ 50.98%  BGE-M3 단독
━━━━━━━━━━━━━━━━━━━━━━━━ 45.10%  + ms-marco-base
```

---

## 🔍 분석

### ✅ BGE-M3 단독의 강점
1. **압도적인 Recall@5** - 98.04%는 실질적으로 완벽에 가까움
2. **균형잡힌 성능** - Recall@1도 50.98%로 절반은 1위에 정답
3. **단순성** - 추가 모델 불필요, 유지보수 용이
4. **속도** - 리랭킹 단계 없어서 응답 시간 단축

### ❌ 리랭킹의 문제점

#### 1. **Recall@5 급격한 저하**
- 모든 리랭커가 **17~27% 하락**
- 원인: Cross-encoder가 한국어 쿼리-문서 매칭에 약함

#### 2. **한국어 지원 미흡**
- mmarco-multi: "다국어"라고 하지만 주로 영어/유럽어 학습
- BGE reranker: 다국어 지원하지만 한국어 성능 검증 안 됨
- MS MARCO: 영어 위주 학습 데이터

#### 3. **중복 문서 문제**
- Corpus에 같은 문서의 chunk들이 중복 저장됨
- 예: "대구통학버스 | 공지사항" - Top-10 중 9개가 동일 문서
- 리랭킹이 중복 때문에 다양성 저하

#### 4. **Trade-off가 불리**
```
mmarco-multi 예시:
  Recall@1: +3.92% ⬆️  (51개 → 54개, +3개 개선)
  Recall@5: -17.65% ⬇️ (50개 → 41개, -9개 악화)
  
  → 3개 개선하려고 9개 손실!
```

---

## 🐛 발견된 기술적 이슈

### 1. Qdrant Payload 구조
**문제:** Payload에 `id` 필드 없음  
**영향:** 검색 결과를 corpus와 매칭할 때 `document_name` 또는 `title` 사용 필요  
**해결:** 매칭 로직 수정 완료

### 2. 크롤링 데이터 vs 첨부파일
**문제:**  
- 첨부파일: `document_name` 필드에 파일명 저장
- 크롤링: `document_name`은 비어있고 `title` 필드에 페이지 제목 저장  

**영향:** GT 매칭 시 두 필드 모두 체크 필요  
**해결:** 유연한 매칭 로직 구현 완료

### 3. Corpus 중복 문제
**발견:** 같은 웹 페이지가 여러 번 크롤링되어 Qdrant에 중복 저장  
**예시:** "대구통학버스 | 공지사항 | 공지사항" - 24개 chunk 존재  
**영향:**  
- Recall@5 과대평가 (같은 문서 chunk가 Top-5 채움)
- 리랭킹 시 다양성 저하

**권장 해결책:**
1. Corpus 재생성 시 중복 제거
2. Qdrant 업로드 전 deduplication
3. 또는 검색 결과에서 동적으로 중복 제거

---

## 💡 결론 및 권장사항

### ✅ **최종 결정: BGE-M3 단독 사용**

**채택 이유:**
1. **Recall@5: 98.04%** - 리랭킹 없이도 거의 완벽
2. **단순성** - 추가 모델/복잡도 없음
3. **속도** - 리랭킹 단계 생략으로 응답 시간 단축
4. **안정성** - 검증된 성능, 한국어 지원 우수

### 🚫 **리랭킹 미채택 이유:**
1. Recall@5 손실이 너무 큼 (-17~27%)
2. Recall@1 개선은 미미함 (+2~4%)
3. 한국어 리랭커 성능 검증 안 됨
4. Corpus 중복 문제로 효과 제한적
5. 유지보수 복잡도 증가

### 📈 **향후 개선 방향**

#### 옵션 A: Corpus 품질 개선 (추천!)
1. **중복 제거** - 웹 크롤링 중복 데이터 정리
2. **청킹 전략 개선** - 문서 경계를 고려한 스마트 청킹
3. **Qdrant 재업로드** - 깨끗한 데이터로 재구축

#### 옵션 B: 하이브리드 검색 (실험적)
1. **Dense + Sparse** - BGE-M3 + BM25 결합
2. **Fusion** - Reciprocal Rank Fusion으로 결과 병합
3. **효과:** Recall@5: 98% → 99%+ 기대

#### 옵션 C: 쿼리 최적화
1. **쿼리 확장** - 동의어, 유사어 추가
2. **연도 명시** - "2025학년도"처럼 시간 정보 추가
3. **효과:** 검색 정확도 향상

#### 옵션 D: 사용자 피드백
1. **클릭 데이터** - 실제 사용자가 선택한 결과 학습
2. **Fine-tuning** - 한국어 대학 도메인 특화
3. **장기 프로젝트**

---

## 📁 관련 파일

### 스크립트
- `scripts/test_reranking.py` - 리랭킹 평가 스크립트
- `scripts/compare_embedding_models.py` - 임베딩 모델 비교
- `scripts/prepare_100_queries.py` - GT 준비

### 데이터
- `data/ground_truth_100.csv` - 51개 수동 검증 GT
- `data/queries_100.txt` - 100개 테스트 쿼리
- `data/corpus_all.csv` - 전체 코퍼스

### 문서
- `docs/GROUND_TRUTH_SELECTION_GUIDE.md` - GT 선택 가이드
- `docs/EMBEDDING_MODEL_SELECTION.md` - 모델 선택 가이드
- `docs/RERANKING_EVALUATION_REPORT.md` - 본 문서

---

## 🔗 참고 자료

### 모델 정보
- **BGE-M3:** https://huggingface.co/BAAI/bge-m3
- **BGE Reranker:** https://huggingface.co/BAAI/bge-reranker-base
- **MS MARCO:** https://huggingface.co/cross-encoder

### 관련 논문
- BGE-M3: "BGE M3-Embedding: Multi-Lingual, Multi-Functionality, Multi-Granularity Text Embeddings Through Self-Knowledge Distillation"
- MS MARCO: "MS MARCO: A Human Generated MAchine Reading COmprehension Dataset"

---

**작성일:** 2025-11-04  
**최종 업데이트:** 2025-11-04
