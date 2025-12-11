from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List

# 기존 모듈 임포트
from core.rag_core import rag_with_sources
from core.router import classify_query_intent  # isDate 판단 및 키워드 추출용

app = FastAPI(title="KitBot RAG API")

# ---------------------------------------------------------
# 1. 프론트엔드 요구사항에 맞춘 데이터 모델 (Schema)
# ---------------------------------------------------------
class ChatRequest(BaseModel):
    query: str = Field(..., description="사용자 질문", example="내일 셔틀버스 시간표 알려줘")
    topk: int = Field(5, description="검색할 문서 개수")

class ChatResponse(BaseModel):
    keyword: str = Field(..., description="실시간 인기 키워드 집계용")
    message: str = Field(..., description="최종 답변")
    source: List[str] = Field(default=[], description="사용된 문서 제목 리스트")
    link: List[str] = Field(default=[], description="원본 링크 리스트")
    isDate: bool = Field(default=False, description="캘린더 UI 활성화 여부")

    class Config:
        json_schema_extra = {
            "example": {
                "keyword": "셔틀버스",
                "message": "내일 셔틀버스는 08:30에 출발합니다.",
                "source": ["2024_통학버스_안내.pdf"],
                "link": ["https://kumoh.ac.kr/..."],
                "isDate": False
            }
        }

# ---------------------------------------------------------
# 2. 헬퍼 함수: 키워드 추출 로직
# ---------------------------------------------------------
def extract_keyword(query: str, intent: str) -> str:
    """
    단순 질문 전체를 저장하면 집계가 안 되므로, 
    intent 기반으로 대표 키워드를 뽑거나 질문의 핵심 단어를 반환합니다.
    (추후 형태소 분석기 도입 시 여기서 로직만 변경하면 됨)
    """
    if intent == "bus":
        return "교통/셔틀버스"
    elif intent == "schedule":
        return "학사일정"
    
    # 일반 질문인 경우: 일단 질문 그대로 리턴하거나 앞부분만 잘라서 리턴
    # 예: "장학금 신청 기간" -> "장학금" (이건 나중에 Kiwi로 개선)
    return query.strip()

# ---------------------------------------------------------
# 3. API 엔드포인트
# ---------------------------------------------------------
@app.get("/health")
def health_check():
    return {"status": "ok", "message": "KitBot API is running"}

@app.post("/ask", response_model=ChatResponse)
def ask(req: ChatRequest):
    try:
        # 1) 의도 분류 (isDate 및 keyword 결정을 위해 먼저 실행)
        intent = classify_query_intent(req.query)

        # 2) RAG 답변 생성
        # rag_core.py의 rag_with_sources는 (answer, sources_list)를 반환
        answer, sources_raw = rag_with_sources(req.query, req.topk)

        # 3) 소스 및 링크 리스트 추출
        source_titles = []
        source_links = []
        
        for s in sources_raw:
            # title이 없으면 board_name이라도 사용
            title = s.get("title") or s.get("board_name") or "제목 없음"
            url = s.get("url") or ""
            
            source_titles.append(title)
            source_links.append(url)

        # 중복 제거 (순서 유지)
        source_titles = list(dict.fromkeys(source_titles))
        source_links = list(dict.fromkeys(filter(None, source_links))) # 빈 URL 제외

        # 4) 응답 조립
        response_data = ChatResponse(
            keyword=extract_keyword(req.query, intent),
            message=answer,
            source=source_titles,
            link=source_links,
            isDate=(intent == "schedule")  # 학사일정 관련이면 True
        )
        
        return response_data

    except Exception as e:
        print(f"Server Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))