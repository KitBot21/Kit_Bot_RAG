# rag_core_reranker.py - 리랭커 버전
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
# 리랭커 기반 검색
# --------------------
def search_with_reranker(query: str, top_k: int = 5, initial_k: int = 15) -> List[Any]:
    """
    1) 시맨틱 검색으로 initial_k개 가져오기
    2) CrossEncoder 리랭커로 재정렬
    3) 상위 top_k개 반환
    """
    client = get_qdrant_client()
    model = get_embed_model()
    reranker = get_reranker_model()

    # 1. 시맨틱 검색 (더 많이 가져오기)
    query_vec = model.encode(query).tolist()
    
    res = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vec,
        limit=initial_k,
        with_payload=True,
    )

    candidates = res.points

    if not candidates:
        return []

    # 2. 리랭커 적용
    # CrossEncoder는 (query, document) 쌍의 관련성 점수를 직접 계산
    pairs = []
    for point in candidates:
        payload = point.payload or {}
        text = (
            payload.get("chunk_text") or 
            payload.get("text") or 
            payload.get("main_text") or 
            payload.get("content") or ""
        )
        pairs.append([query, text[:512]])  # 최대 512자로 제한
    
    # 리랭킹 점수 계산
    scores = reranker.predict(pairs)
    
    # 3. 점수 기준 재정렬
    scored_points = list(zip(candidates, scores))
    scored_points.sort(key=lambda x: x[1], reverse=True)
    
    # 4. 상위 top_k개 선택 및 점수 업데이트
    final_results = []
    for point, score in scored_points[:top_k]:
        point.score = float(score)  # 리랭커 점수로 업데이트
        final_results.append(point)
    
    print(f"   🔍 리랭커 검색: 초기 {len(candidates)}개 → 리랭킹 → 최종 {len(final_results)}개")
    
    return final_results


# --------------------
# 검색 단계 (API용)
# --------------------
def retrieve_points(query: str, top_k: int = 5):
    """리랭커 검색 사용"""
    return search_with_reranker(query, top_k, initial_k=15)


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
