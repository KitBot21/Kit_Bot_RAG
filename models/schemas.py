# models/schemas.py
from pydantic import BaseModel, Field
from typing import List, Optional

class ChatRequest(BaseModel):
    query: str = Field(..., description="사용자 질문", example="내일 셔틀버스 시간표 알려줘")
    topk: int = Field(5, description="검색할 문서 개수")

class ChatResponse(BaseModel):
    keyword: str = Field(..., description="실시간 인기 키워드 집계용")
    message: str = Field(..., description="최종 답변")
    source: List[str] = Field(default=[], description="사용된 문서 제목 리스트")
    link: List[str] = Field(default=[], description="원본 링크 리스트")
    isDate: bool = Field(default=False, description="캘린더 UI 활성화 여부")
    # 🔴 캘린더 연동용 데이터 필드
    startDate: Optional[str] = Field(None, description="일정 시작일 (YYYY-MM-DD)")
    endDate: Optional[str] = Field(None, description="일정 종료일 (YYYY-MM-DD)")
    scheduleTitle: Optional[str] = Field(None, description="일정 제목")