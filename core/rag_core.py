# rag_core.py
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
# Boost 기반 검색
# --------------------
def search_with_boost(query: str, top_k: int = 5) -> List[Any]:
    """
    1) 쿼리 임베딩
    2) Qdrant에서 top_k*3개 query_points로 검색
    3) router.rerank_with_boost로 재정렬
    """
    intent = classify_query_intent(query)
    client = get_qdrant_client()
    model = get_embed_model()

    query_vec = model.encode(query).tolist()
    limit = max(top_k * 3, top_k)

    # qdrant-client 1.16.0 에서는 search가 아니라 query_points 사용
    res = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vec,          # 예전 버전 시그니처: query=
        limit=limit,
        with_payload=True,
    )

    raw_hits = res.points  # ScoredPoint 리스트

    # boost 후 재정렬
    boosted_hits = rerank_with_boost(raw_hits, intent=intent, top_k=top_k)
    return boosted_hits


# --------------------
# 검색 단계 (기존 API용)
# --------------------
def retrieve_points(query: str, top_k: int = 5):
    """
    API / CLI 모두에서 사용하는 실제 검색 함수
    → 이제 boost 검색을 항상 사용하도록 통일
    """
    return search_with_boost(query, top_k)


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

# 🔴 [New] LLM을 이용한 스마트 키워드 추출 함수
def extract_search_keyword_llm(query: str) -> str:
    """
    사용자 질문에서 검색용 '핵심 명사 키워드' 1개를 추출합니다.
    (비용 절약을 위해 짧은 프롬프트 사용)
    """
    client = get_llm_client()
    prompt = (
        f"질문: \"{query}\"\n"
        "위 질문의 핵심 의도를 나타내는 **가장 중요한 명사 단어 1개**만 추출해.\n"
        "조사나 서술어는 빼고 단어만 출력해.\n"
        "예시:\n"
        "- 셔틀버스 시간표 -> 셔틀버스\n"
        "- 국가장학금 언제 들어와? -> 국가장학금\n"
        "- 안녕 반가워 -> 인사\n"
        "키워드:"
    )
    
    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL, # gpt-4o 또는 gpt-3.5-turbo
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=20, 
        )
        return resp.choices[0].message.content.strip()
    except:
        return "검색" # 실패 시 기본값
    
# --------------------
# LLM 호출
# --------------------
def call_llm(system_msg: str, user_msg: str) -> str:
    client = get_llm_client()

    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.2,
    )
    
    answer = resp.choices[0].message.content.strip()
    
    # 🔴 [Fix] 줄바꿈 문자(\n)가 텍스트 그대로 출력되는 현상 방지
    # (LLM이 가끔 "\\n"으로 이스케이프해서 줄 때가 있음)
    answer = answer.replace("\\n", "\n")

    return answer

# ---------------------------------------------------------
# [New] 답변에서 일정 정보(JSON) 추출 함수
# ---------------------------------------------------------
def extract_schedule_info(answer_text: str):
    """
    LLM이 생성한 답변 텍스트를 분석하여 일정 제목, 시작일, 종료일을 JSON으로 추출
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
            model=OPENAI_MODEL, # gpt-4o 또는 gpt-3.5-turbo
            messages=[
                {"role": "system", "content": "You are a JSON extractor."},
                {"role": "user", "content": extraction_prompt}
            ],
            temperature=0, # 정확성을 위해 0
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
# 출처 + 답변 생성
# --------------------
def rag_with_sources(query: str, top_k: int = 5):
    # 0. 의도 파악
    from core.router import classify_query_intent
    intent = classify_query_intent(query)

    # 1. 일상 대화(Chit-chat) 처리 (검색 생략)
    if intent == "chitchat":
        system_msg = "너는 금오공대 학생들을 돕는 친절한 AI 챗봇 'KIT-Bot'이야. 학생에게 다정하게 대답해줘."
        answer = call_llm(system_msg, query)
        # 일상 대화는 출처 없음
        return answer, [], {"scheduleTitle": None, "startDate": None, "endDate": None}
    
    # 2. 검색 (기존 로직 유지)
    points = retrieve_points(query, top_k)
    
    SIMILARITY_THRESHOLD = 0.4

    if not points or points[0].score < SIMILARITY_THRESHOLD:
        # 관련성 높은 문서가 없으면 바로 종료
        print(f"   📉 검색 점수 미달: {points[0].score if points else 0} < {SIMILARITY_THRESHOLD}")
        return "죄송합니다. 학교 정보와 관련이 없거나, 해당 내용을 문서에서 찾을 수 없습니다.", [], {"scheduleTitle": None, "startDate": None, "endDate": None}

    context_text = build_context_blocks(points)
    
    # 1. 오늘 날짜 및 현재 연도 구하기 (한국 시간 기준)
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)
    today_str = now.strftime("%Y년 %m월 %d일")
    current_year = now.year

    # 2. 시스템 프롬프트에 '기준 시간'과 '엄격한 연도 비교 지침' 주입
    # ---------------------------------------------------------
    # [Prompt Engineering] 프롬프트 고도화 (Time Awareness 강화)
    # ---------------------------------------------------------
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
    
    # 3. LLM 호출 (기존 로직 유지)
    answer = call_llm(system_msg, user_msg)

    # ---------------------------------------------------------
    # [New] 의도가 'schedule'이거나 답변에 날짜가 포함된 경우 -> 일정 추출 시도
    # ---------------------------------------------------------
    schedule_data = {"scheduleTitle": None, "startDate": None, "endDate": None}

    # 학사일정 의도이거나, 답변에 "202X-" 같은 날짜 패턴이 보이면 추출 시도
    negative_keywords = [
        "죄송하지만", "찾을 수 없습니다", "정보가 없습니다", "문서에 없습니다", "도와드릴 수 없어요", "제공할 수 없어요", "정보를 찾을 수 없어요"
    ]
    
    if any(neg in answer for neg in negative_keywords):
        final_sources = [] # 출처 숨김
    else:
        # 정상 답변이면 출처 정리
        final_sources = []
        for p in points:
            payload = p.payload or {}
            final_sources.append({
                "title": payload.get("title"),
                "url": payload.get("url"),
                "text": payload.get("text")
            })

    # 6. 일정 정보 추출 (기존 로직)
    schedule_data = {"scheduleTitle": None, "startDate": None, "endDate": None}
    # 답변이 성공했을 때만 일정 추출 시도
    if final_sources and (intent == "schedule" or "202" in answer):
        extracted = extract_schedule_info(answer)
        if extracted.get("startDate"):
            schedule_data = extracted

    return answer, final_sources, schedule_data


# --------------------
# CLI용 간단 래퍼
# --------------------
def generate_answer(query: str, top_k: int = 5) -> str:
    answer, _ = rag_with_sources(query, top_k)
    return answer