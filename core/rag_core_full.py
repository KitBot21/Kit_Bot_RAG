# rag_core_full.py - 하이브리드 검색 + 리랭커 (최고 성능)
import os
import json
from typing import List, Dict, Any, Tuple, Optional
from dotenv import load_dotenv
from datetime import datetime
import pytz
from sentence_transformers import SentenceTransformer, CrossEncoder
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm
from openai import OpenAI
from rank_bm25 import BM25Okapi
import re

from core.router import classify_query_intent

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
_reranker_model: CrossEncoder | None = None
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


def get_reranker_model() -> CrossEncoder:
    """BGE-reranker-v2-m3 모델 로드"""
    global _reranker_model
    if _reranker_model is None:
        print("⏳ 리랭커 모델 로딩 중... BAAI/bge-reranker-v2-m3")
        _reranker_model = CrossEncoder('BAAI/bge-reranker-v2-m3', max_length=512)
    return _reranker_model


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
    
    documents = []
    offset = None
    batch_size = 100
    
    while True:
        result = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=batch_size,
            offset=offset,
            with_payload=True,
            with_vectors=False
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
    
    tokenized_corpus = [tokenize_korean(doc['text']) for doc in documents]
    _bm25_index = BM25Okapi(tokenized_corpus)
    _bm25_documents = documents
    
    print(f"   ✅ BM25 인덱스 생성 완료")
    
    return _bm25_index, _bm25_documents


# --------------------
# 하이브리드 검색 + 리랭커
# --------------------
def hybrid_search_with_reranker(query: str, top_k: int = 5, alpha: float = 0.85) -> List[Any]:
    """
    개선된 Full 파이프라인:
    1) 개선된 하이브리드 검색 (BM25 + Semantic, alpha=0.85)
    2) CrossEncoder 리랭커로 재정렬
    3) 상위 top_k개 반환
    """
    client = get_qdrant_client()
    model = get_embed_model()
    reranker = get_reranker_model()
    
    # 1. 시맨틱 검색 (더 많이 가져오기)
    query_vec = model.encode(query).tolist()
    semantic_limit = 50  # 리랭커를 위해 충분히 많이
    
    semantic_results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vec,
        limit=semantic_limit,
        with_payload=True,
    )
    
    semantic_scores = {}
    semantic_docs = {}
    for point in semantic_results.points:
        semantic_scores[str(point.id)] = point.score
        semantic_docs[str(point.id)] = point
    
    # 2. BM25 검색
    bm25_index, bm25_documents = build_bm25_index()
    tokenized_query = tokenize_korean(query)
    bm25_scores = bm25_index.get_scores(tokenized_query)
    
    # 개선된 Min-Max 정규화
    if len(bm25_scores) > 0:
        min_score = min(bm25_scores)
        max_score = max(bm25_scores)
        
        if max_score > min_score:
            bm25_scores_normalized = (bm25_scores - min_score) / (max_score - min_score)
        else:
            bm25_scores_normalized = bm25_scores / max(max_score, 1.0)
    else:
        bm25_scores_normalized = bm25_scores
    
    # BM25 상위 문서만 선택
    top_bm25_indices = sorted(range(len(bm25_scores_normalized)), 
                               key=lambda i: bm25_scores_normalized[i], 
                               reverse=True)[:semantic_limit]
    
    bm25_score_dict = {}
    for idx in top_bm25_indices:
        doc_id = str(bm25_documents[idx]['id'])
        bm25_score_dict[doc_id] = float(bm25_scores_normalized[idx])
    
    # 3. 하이브리드 점수 계산
    all_doc_ids = set(semantic_scores.keys()) | set(bm25_score_dict.keys())
    
    hybrid_scores = {}
    for doc_id in all_doc_ids:
        sem_score = semantic_scores.get(doc_id, 0.0)
        bm25_score = bm25_score_dict.get(doc_id, 0.0)
        hybrid_scores[doc_id] = alpha * sem_score + (1 - alpha) * bm25_score
    
    # 4. 상위 후보 선택 (리랭킹 전)
    sorted_doc_ids = sorted(hybrid_scores.keys(), key=lambda x: hybrid_scores[x], reverse=True)
    
    candidates = []
    rerank_limit = 30  # 리랭커에 더 많은 후보 제공
    for doc_id in sorted_doc_ids[:rerank_limit]:
        if doc_id in semantic_docs:
            point = semantic_docs[doc_id]
            candidates.append(point)
        else:
            for bm25_doc in bm25_documents:
                if str(bm25_doc['id']) == doc_id:
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
                    candidates.append(point)
                    break
    
    if not candidates:
        return []
    
    # 5. 리랭커 적용 (텍스트 길이 증가)
    pairs = []
    for point in candidates:
        payload = point.payload or {}
        text = (
            payload.get("chunk_text") or 
            payload.get("text") or 
            payload.get("main_text") or 
            payload.get("content") or ""
        )
        # 텍스트 길이를 늘려서 더 많은 컨텍스트 제공
        pairs.append([query, text[:1024]])  # 512 → 1024
    
    reranker_scores = reranker.predict(pairs)
    
    # 6. 리랭커 점수로 최종 정렬
    scored_points = list(zip(candidates, reranker_scores))
    scored_points.sort(key=lambda x: x[1], reverse=True)
    
    final_results = []
    for point, score in scored_points[:top_k]:
        point.score = float(score)
        final_results.append(point)
    
    print(f"   🔍 Full 검색 (alpha={alpha}): 하이브리드 {len(candidates)}개 → 리랭킹 → 최종 {len(final_results)}개")
    
    return final_results


# --------------------
# 검색 단계
# --------------------
def retrieve_points(query: str, top_k: int = 5):
    """개선된 하이브리드 (alpha=0.85) + 리랭커 사용"""
    return hybrid_search_with_reranker(query, top_k, alpha=0.85)


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
def extract_schedule_info(answer_text: str):
    """
    LLM이 생성한 답변 텍스트를 분석하여 일정 제목, 시작일, 종료일을 JSON으로 추출
    (베이스라인과 동일한 방식: LLM 기반 추출)
    """
    client = get_llm_client()
    now = datetime.now()
    current_year = now.year
    today_str = now.strftime("%Y-%m-%d")

    # 일정 추출 전용 프롬프트
    extraction_prompt = (
        f"현재 연도는 {current_year}년이고, 오늘은 {today_str}입니다.\n"
        "다음 텍스트에서 **하나의 핵심 일정**을 찾아 JSON 형식으로 추출하세요.\n\n"
        f"텍스트: \"{answer_text}\"\n\n"
        "## 규칙\n"
        "1. **scheduleTitle**: 일정의 핵심 제목 (예: '2025-1학기 수강신청', '중간고사 기간').\n"
        "2. **startDate**: 시작 날짜 (YYYY-MM-DD 형식). 연도가 없으면 현재/미래 기준으로 추론.\n"
        "3. **endDate**: 종료 날짜 (YYYY-MM-DD 형식). **종료일이 명시되지 않았거나 시작일과 같다면 startDate와 동일하게 작성.**\n"
        "4. 만약 텍스트에 명확한 날짜 정보가 없다면 모든 필드를 null로 반환하세요.\n"
        "5. 오직 JSON 데이터만 출력하세요. (Markdown backticks 없이)\n\n"
        "Example output: {\"scheduleTitle\": \"수강신청\", \"startDate\": \"2025-02-10\", \"endDate\": \"2025-02-14\"}"
    )

    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You are a JSON extractor."},
                {"role": "user", "content": extraction_prompt}
            ],
            temperature=0,
        )
        
        content = resp.choices[0].message.content.strip()
        # 혹시 모를 Markdown backtick 제거 (```json ... ```)
        if content.startswith("```"):
            content = content.replace("```json", "").replace("```", "")
        
        data = json.loads(content)
        return data
        
    except Exception as e:
        print(f"⚠️ 일정 추출 실패: {e}")
        return {"scheduleTitle": None, "startDate": None, "endDate": None}


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
        "   - 정보가 없을 때는 **'죄송하지만, 해당 내용은 학교 공지나 문서에서 찾을 수가 없네요 😥. 혹시 다른 키워드로 다시 질문해 주시겠어요?'**라고 솔직하게 답변해 주세요.\n"
        "   - 윤리적으로 문제가 되거나 학교와 무관한 질문(핵무기, 정치 등)에도 정중하게 거절해 주세요.\n\n"

        "## 2. 센스 있는 시간 확인 (Time Awareness)\n"
        f"   - 문서 내용이 **올해({current_year}년)** 것인지 꼭 확인해 주세요.\n"
        f"   - 만약 올해 최신 공지가 없고 작년 자료만 있다면, **'아쉽게도 아직 {current_year}년도 공지는 올라오지 않았어요. 대신 작년({current_year-1}년) 일정을 참고용으로 알려드릴게요!'**라고 안내해 주세요.\n"
        "   - 이미 지난 일정이라면 **'해당 일정은 아쉽게도 마감되었어요.'**라고 알려주세요.\n\n"
        
        "## 3. 보기 편하고 친절한 설명\n"
        "   - 날짜, 장소, 전화번호 같은 핵심 정보는 **굵게(**)** 표시해서 눈에 잘 띄게 해주세요.\n"
        "   - 복잡한 내용은 **리스트**로 깔끔하게 정리해 주는 센스를 발휘해 주세요.\n"
        "   - 적절한 **이모지(📅, 🚌, 😊 등)**를 섞어서 답변이 딱딱해지지 않도록 해주세요.\n\n"
        
        "## 4. 마무리\n"
        "   - 답변 끝에는 **'더 궁금한 점이 있으면 언제든 물어봐 주세요!'** 멘트를 덧붙여 주세요.\n"
        "   - (단, 답변 불가능한 경우에는 출처나 응원 문구를 생략하고 간결하게 끝내세요.)"
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
