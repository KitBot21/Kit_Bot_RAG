import csv
import time
from datetime import datetime
from fastapi import APIRouter, HTTPException
from typing import List, Optional

# 필요한 모듈 import
from models.schemas import ChatRequest, ChatResponse
from core.rag_core import rag_with_sources, extract_search_keyword_llm
from core.router import classify_query_intent

router = APIRouter()

# ---------------------------------------------------------
# [New] 로그 기록 함수 (CSV 저장)
# ---------------------------------------------------------
def log_interaction(query, answer, intent, sources):
    log_file = "rag_interaction_logs.csv"
    
    # 파일이 없으면 헤더 작성
    file_exists = False
    try:
        with open(log_file, "r", encoding="utf-8"):
            file_exists = True
    except FileNotFoundError:
        pass

    with open(log_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Timestamp", "Query", "Intent", "Sources", "Answer"])
        
        # 소스 제목만 간단히 기록
        source_titles = [s.get("title", "무제") for s in sources]
        
        writer.writerow([
            datetime.now().isoformat(),
            query,
            intent,
            str(source_titles),
            answer.replace("\n", " ")[:200] # 답변은 너무 기니까 200자로 자르고 줄바꿈 제거
        ])

# ---------------------------------------------------------
# [New] 최종 키워드 결정 함수
# ---------------------------------------------------------
def determine_final_keyword(query: str, intent: str) -> str:
    """
    의도(Intent)가 명확하면 고정 키워드를,
    아니면 LLM이 추출한 키워드를 반환합니다.
    """
    # 1. 카테고리별 고정 키워드 매핑 (규칙 기반)
    intent_map = {
        "bus": "교통/셔틀버스",
        "schedule": "학사일정",
        "menu": "식단",
        "scholarship": "장학",
        "dorm": "생활관/기숙사",
        "employment": "취업/채용",
        "event": "행사/특강",
        "chitchat": "인사/잡담"
    }
    
    if intent in intent_map:
        return intent_map[intent]
    
    # 2. 그 외(General) -> LLM 키워드 추출 사용 (안전장치 추가)
    try:
        return extract_search_keyword_llm(query)
    except Exception:
        # LLM 호출 실패 시 질문 자체를 반환 (너무 길면 자르기)
        return query[:10]

# ---------------------------------------------------------
# API 엔드포인트
# ---------------------------------------------------------
@router.post("/ask", response_model=ChatResponse)
async def ask(req: ChatRequest):
    try:
        start_time = time.time()
        
        # 1. 의도 파악
        intent = classify_query_intent(req.query)
        
        # 2. RAG 수행 (답변, 소스, 일정정보 받아옴)
        answer, sources_raw, schedule_data = rag_with_sources(req.query, req.topk)

        # 3. 키워드 결정 (규칙 + LLM 하이브리드)
        keyword = determine_final_keyword(req.query, intent)

        # 4. 소스 정리 (중복 제거 및 포맷팅)
        source_titles = []
        source_links = []
        
        # chitchat인 경우 source와 link는 빈 배열로
        if intent != "chitchat" and sources_raw:
            for src in sources_raw:
                t = src.get("title", "무제")
                u = src.get("url", "")
                if t not in source_titles:
                    source_titles.append(t)
                    source_links.append(u)

        # 5. 로그 기록 (비동기로 빼면 더 좋지만 일단 동기로 처리)
        log_interaction(req.query, answer, intent, sources_raw)

        # 6. 응답 반환
        is_date_active = bool(schedule_data.get("startDate"))

        return ChatResponse(
            keyword=keyword,      
            message=answer,       
            source=source_titles, 
            link=source_links,    
            
            isDate=is_date_active,
            startDate=schedule_data.get("startDate"),
            endDate=schedule_data.get("endDate"),
            scheduleTitle=schedule_data.get("scheduleTitle")
        )
        
    except Exception as e:
        print(f"Error in /ask: {e}")
        return ChatResponse(
            keyword="에러",
            message="죄송합니다. 시스템 오류가 발생했습니다.",
            source=[], link=[], isDate=False
        )