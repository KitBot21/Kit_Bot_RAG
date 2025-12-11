# rag_core_hybrid.py - 하이브리드 검색 버전 (BM25 + Semantic)
import os
import json
from typing import List, Dict, Any, Tuple, Optional
from dotenv import load_dotenv
from datetime import datetime
import pytz
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm
from openai import OpenAI
from rank_bm25 import BM25Okapi
import re

from core.router import classify_query_intent, rerank_with_boost

load_dotenv()

# --------------------
# 환경 설정
# --------------------
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "kitbot_docs_bge")
EMBED_MODEL_NAME = os.getenv("EMBED_MODEL_NAME", "BAAI/bge-m3")
OPENAI_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")

# --------------------
# 싱글톤
# --------------------
_qdrant_client: QdrantClient | None = None
_embed_model: SentenceTransformer | None = None
_llm_client: OpenAI | None = None
_bm25_index = None
_bm25_documents = None


def get_qdrant_client() -> QdrantClient:
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(url=QDRANT_URL)
    return _qdrant_client


def get_embed_model() -> SentenceTransformer:
    global _embed_model
    if _embed_model is None:
        print("⏳ 임베딩 모델 로딩 중...", EMBED_MODEL_NAME)
        _embed_model = SentenceTransformer(EMBED_MODEL_NAME)
    return _embed_model


def get_llm_client() -> OpenAI:
    global _llm_client
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY 환경변수가 없습니다.")
    if _llm_client is None:
        _llm_client = OpenAI(api_key=api_key)
    return _llm_client


# --------------------
# BM25 인덱스 구축
# --------------------
def tokenize_korean(text: str) -> List[str]:
    """개선된 한국어 토크나이저 (형태소 분석 + N-gram)"""
    # 1. 기본 정제
    text = re.sub(r'[^\w\s가-힣]', ' ', text)
    text = text.lower()
    
    # 2. 공백 기반 토큰화
    tokens = text.split()
    
    # 3. 추가 N-gram 생성 (2-3글자 단위)
    ngrams = []
    for token in tokens:
        if len(token) >= 2:
            # 2-gram
            for i in range(len(token) - 1):
                ngrams.append(token[i:i+2])
            # 3-gram
            if len(token) >= 3:
                for i in range(len(token) - 2):
                    ngrams.append(token[i:i+3])
    
    return tokens + ngrams


def build_bm25_index():
    """Qdrant에서 모든 문서를 로드하여 BM25 인덱스 구축"""
    global _bm25_index, _bm25_documents
    
    if _bm25_index is not None:
        return _bm25_index, _bm25_documents
    
    print("🔍 BM25 인덱스 구축 중...")
    client = get_qdrant_client()
    
    # Qdrant에서 모든 문서 스크롤
    documents = []
    offset = None
    batch_size = 100
    
    while True:
        result = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=batch_size,
            offset=offset,
            with_payload=True,
            with_vectors=False  # 벡터는 필요 없음
        )
        
        points, next_offset = result
        
        if not points:
            break
        
        for point in points:
            payload = point.payload or {}
            text = (
                payload.get("chunk_text") or 
                payload.get("text") or 
                payload.get("main_text") or 
                payload.get("content") or ""
            )
            
            if text.strip():
                documents.append({
                    'id': point.id,
                    'text': text,
                    'payload': payload,
                    'score': getattr(point, 'score', 0.0)
                })
        
        if next_offset is None:
            break
        offset = next_offset
    
    print(f"   ✅ {len(documents)}개 문서 로드 완료")
    
    # BM25 인덱스 생성
    tokenized_corpus = [tokenize_korean(doc['text']) for doc in documents]
    _bm25_index = BM25Okapi(tokenized_corpus)
    _bm25_documents = documents
    
    print(f"   ✅ BM25 인덱스 생성 완료")
    
    return _bm25_index, _bm25_documents


# --------------------
# 하이브리드 검색
# --------------------
def hybrid_search(query: str, top_k: int = 5, alpha: float = 0.85) -> List[Any]:
    """
    개선된 하이브리드 검색: BM25 키워드 검색 + BGE-M3 시맨틱 검색
    
    Args:
        query: 검색 쿼리
        top_k: 최종 반환할 문서 수
        alpha: 시맨틱 검색 가중치 (0~1, 0=BM25만, 1=시맨틱만, 최적값 0.85)
    
    Returns:
        재정렬된 문서 리스트
    """
    client = get_qdrant_client()
    model = get_embed_model()
    
    # 1. 시맨틱 검색 (BGE-M3)
    query_vec = model.encode(query).tolist()
    semantic_limit = top_k * 5  # 더 많이 가져와서 하이브리드 결합
    
    semantic_results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vec,
        limit=semantic_limit,
        with_payload=True,
    )
    
    # 시맨틱 검색 결과를 딕셔너리로 변환 (ID -> score)
    semantic_scores = {}
    semantic_docs = {}
    for point in semantic_results.points:
        semantic_scores[str(point.id)] = point.score
        semantic_docs[str(point.id)] = point
    
    # 2. BM25 키워드 검색
    bm25_index, bm25_documents = build_bm25_index()
    tokenized_query = tokenize_korean(query)
    bm25_scores = bm25_index.get_scores(tokenized_query)
    
    # BM25 점수 개선된 정규화 (Min-Max Scaling)
    if len(bm25_scores) > 0:
        min_score = min(bm25_scores)
        max_score = max(bm25_scores)
        
        if max_score > min_score:
            # Min-Max 정규화 (0~1)
            bm25_scores_normalized = (bm25_scores - min_score) / (max_score - min_score)
        else:
            # 모든 점수가 동일한 경우
            bm25_scores_normalized = bm25_scores / max(max_score, 1.0)
    else:
        bm25_scores_normalized = bm25_scores
    
    # BM25 상위 문서만 선택 (효율성 개선)
    top_bm25_indices = sorted(range(len(bm25_scores_normalized)), 
                               key=lambda i: bm25_scores_normalized[i], 
                               reverse=True)[:semantic_limit]
    
    # BM25 결과를 딕셔너리로 변환 (상위 문서만)
    bm25_score_dict = {}
    for idx in top_bm25_indices:
        doc_id = str(bm25_documents[idx]['id'])
        bm25_score_dict[doc_id] = float(bm25_scores_normalized[idx])
    
    # 3. 하이브리드 점수 계산 (가중 결합)
    all_doc_ids = set(semantic_scores.keys()) | set(bm25_score_dict.keys())
    
    hybrid_scores = {}
    for doc_id in all_doc_ids:
        sem_score = semantic_scores.get(doc_id, 0.0)
        bm25_score = bm25_score_dict.get(doc_id, 0.0)
        
        # 가중 결합: alpha * semantic + (1-alpha) * bm25
        hybrid_scores[doc_id] = alpha * sem_score + (1 - alpha) * bm25_score
    
    # 4. 점수 기준 정렬
    sorted_doc_ids = sorted(hybrid_scores.keys(), key=lambda x: hybrid_scores[x], reverse=True)
    
    # 5. 상위 문서 선택 및 ScoredPoint 형태로 변환
    final_results = []
    for doc_id in sorted_doc_ids[:top_k * 3]:  # boost를 위해 3배수 가져오기
        if doc_id in semantic_docs:
            point = semantic_docs[doc_id]
            # 하이브리드 점수로 업데이트
            point.score = hybrid_scores[doc_id]
            final_results.append(point)
        else:
            # BM25에만 있는 경우 (시맨틱 검색에 없었던 문서)
            # bm25_documents에서 찾아서 변환
            for bm25_doc in bm25_documents:
                if str(bm25_doc['id']) == doc_id:
                    # 임시 ScoredPoint 객체 생성
                    class TempPoint:
                        def __init__(self, id, payload, score):
                            self.id = id
                            self.payload = payload
                            self.score = score
                    
                    point = TempPoint(
                        id=bm25_doc['id'],
                        payload=bm25_doc['payload'],
                        score=hybrid_scores[doc_id]
                    )
                    final_results.append(point)
                    break
    
    # 6. Boost 재정렬 적용
    intent = classify_query_intent(query)
    boosted_hits = rerank_with_boost(final_results, intent=intent, top_k=top_k)
    
    print(f"   🔍 하이브리드 검색 (alpha={alpha}): 시맨틱 {len(semantic_results.points)}개 + BM25 상위 {len(top_bm25_indices)}개 → 최종 {len(boosted_hits)}개")
    
    return boosted_hits


# --------------------
# 검색 단계 (API용)
# --------------------
def retrieve_points(query: str, top_k: int = 5):
    """개선된 하이브리드 검색 사용 (alpha=0.85, 최적 균형점)"""
    return hybrid_search(query, top_k, alpha=0.85)


# --------------------
# 검색 결과를 텍스트 블록으로 변환
# --------------------
def build_context_blocks(points) -> str:
    blocks = []

    for i, p in enumerate(points):
        payload = p.payload or {}

        text = (
            payload.get("chunk_text")
            or payload.get("text")
            or payload.get("main_text")
            or payload.get("content")
            or ""
        )

        if not text.strip():
            continue

        meta = (
            f"[{i+1}] site={payload.get('site')} | "
            f"board={payload.get('board_name')} | "
            f"title={payload.get('title')} | "
            f"date={payload.get('created_at')} | "
            f"url={payload.get('url')}"
        )

        block = meta + "\n" + text
        blocks.append(block)

    return "\n\n---\n\n".join(blocks)


# --------------------
# LLM 호출
# --------------------
def call_llm(system_msg: str, user_msg: str, model: str = None) -> str:
    if model is None:
        model = OPENAI_MODEL

    client = get_llm_client()
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.7,
        max_tokens=1000,
    )
    return resp.choices[0].message.content


# --------------------
# 일정 정보 추출
# --------------------
def extract_schedule_info(answer: str) -> Dict[str, Optional[str]]:
    import re
    
    result = {
        "scheduleTitle": None,
        "startDate": None,
        "endDate": None
    }
    
    date_pattern = r'\d{4}[-년]\s?\d{1,2}[-월]\s?\d{1,2}일?'
    dates = re.findall(date_pattern, answer)
    
    if dates:
        result["startDate"] = dates[0].replace('년', '-').replace('월', '-').replace('일', '').replace(' ', '')
        if len(dates) > 1:
            result["endDate"] = dates[1].replace('년', '-').replace('월', '-').replace('일', '').replace(' ', '')
    
    lines = answer.split('\n')
    if lines:
        first_line = lines[0].strip()
        if len(first_line) > 0 and len(first_line) < 100:
            result["scheduleTitle"] = first_line
    
    return result


# --------------------
# RAG with Sources
# --------------------
def rag_with_sources(query: str, top_k: int = 5):
    from core.router import classify_query_intent
    intent = classify_query_intent(query)

    if intent == "chitchat":
        system_msg = "너는 금오공대 학생들을 돕는 친절한 AI 챗봇 'KIT-BOT'이야. 학생에게 다정하게 대답해줘."
        answer = call_llm(system_msg, query)
        return answer, [], {"scheduleTitle": None, "startDate": None, "endDate": None}
    
    points = retrieve_points(query, top_k)
    
    SIMILARITY_THRESHOLD = 0.4

    if not points or points[0].score < SIMILARITY_THRESHOLD:
        print(f"   📉 검색 점수 미달: {points[0].score if points else 0} < {SIMILARITY_THRESHOLD}")
        return "죄송합니다. 학교 정보와 관련이 없거나, 해당 내용을 문서에서 찾을 수 없습니다.", [], {"scheduleTitle": None, "startDate": None, "endDate": None}

    context_text = build_context_blocks(points)
    
    now = datetime.now(pytz.timezone('Asia/Seoul'))
    today_str = now.strftime("%Y년 %m월 %d일")
    current_year = now.year

    system_msg = (
        f"당신은 국립금오공과대학교 학생들을 돕는 **다정하고 친절한 AI 멘토 'KIT-BOT'**입니다.\n"
        f"현재 시각은 **{today_str}**이에요.\n\n"
        "학생의 질문에 대해 [검색된 문서]를 꼼꼼히 확인해서, **따뜻하고 상냥한 말투(해요체)**로 답변해 주세요.\n\n"
        
        "## 1. 답변 가능 여부 판단 (가장 중요!)\n"
        "   - 질문에 대한 정보가 [검색된 문서]에 **명확하게 포함되어 있지 않다면**, 억지로 지어내거나 비슷한 내용을 무리하게 연결하지 마세요.\n"
        "   - 정보가 없을 때는 **'죄송하지만, 해당 내용은 학교 공지나 문서에서 찾을 수가 없네요 😥. 혹시 다른 키워드로 다시 질문해 주시겠어요?'**라고 솔직하게 답변해 주세요.\n\n"

        "## 2. 센스 있는 시간 확인 (Time Awareness)\n"
        f"   - 문서 내용이 **올해({current_year}년)** 것인지 꼭 확인해 주세요.\n"
        f"   - 만약 올해 최신 공지가 없고 작년 자료만 있다면, **'아쉽게도 아직 {current_year}년도 공지는 올라오지 않았어요.'**라고 안내해 주세요.\n\n"
        
        "## 3. 보기 편하고 친절한 설명\n"
        "   - 날짜, 장소, 전화번호 같은 핵심 정보는 **굵게(**)** 표시해서 눈에 잘 띄게 해주세요.\n"
        "   - 복잡한 내용은 **리스트**로 깔끔하게 정리해 주는 센스를 발휘해 주세요.\n\n"
        
        "## 4. 마무리\n"
        "   - 답변 끝에는 **'더 궁금한 점이 있으면 언제든 물어봐 주세요!'** 멘트를 덧붙여 주세요.\n"
    )

    user_msg = (
        f"질문: {query}\n\n"
        f"--- 검색된 문서 시작 ---\n"
        f"{context_text}\n"
        f"--- 검색된 문서 끝 ---\n\n"
        f"위 문서를 정밀하게 분석하여 질문에 답변해줘."
    )
    
    answer = call_llm(system_msg, user_msg)

    schedule_data = {"scheduleTitle": None, "startDate": None, "endDate": None}

    negative_keywords = [
        "죄송하지만", "찾을 수 없습니다", "정보가 없습니다", "문서에 없습니다"
    ]
    
    if any(neg in answer for neg in negative_keywords):
        final_sources = []
    else:
        final_sources = []
        for p in points:
            payload = p.payload or {}
            final_sources.append({
                "title": payload.get("title"),
                "url": payload.get("url"),
                "text": payload.get("text")
            })

    if final_sources and (intent == "schedule" or "202" in answer):
        extracted = extract_schedule_info(answer)
        if extracted.get("startDate"):
            schedule_data = extracted

    return answer, final_sources, schedule_data


def generate_answer(query: str, top_k: int = 5) -> str:
    answer, _, _ = rag_with_sources(query, top_k)
    return answer
