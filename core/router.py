# router.py
from __future__ import annotations
from typing import List, Dict, Any

# 1) 쿼리 → intent 분류 (아주 가벼운 룰)
# 일상 대화 키워드 (검색 없이 바로 LLM 응답)
CHITCHAT_KEYWORDS = [
    "안녕", "하이", "헬로", "hi", "hello", "반가워", "방가", "안녕하세요",
    "고마워", "감사", "thank", "땡큐", "ㄱㅅ", "ㄳ",
    "잘가", "바이", "bye", "빠이", "뿅", "종료",
    "어떻게 지내", "뭐해", "심심", "재밌", "하하", "ㅋㅋ", "ㅎㅎ",
    "이름이 뭐", "누구", "넌 뭐", "자기소개"
]

BUS_KEYWORDS = ["통학버스", "대구통학버스", "셔틀버스", "버스", "노선", "탑승", "예약", "노쇼"]
SCHEDULE_KEYWORDS = ["학사일정", "수강꾸러미", "꾸러미", "수강신청", "신청기간", "등록기간", "등록금", "휴학", "복학", "계절학기", "동계", "하계", "개강", "종강"]
MENU_KEYWORDS = ["식당", "메뉴", "학식", "밥", "점심", "저녁", "오름관", "푸름관", "분식당", "식단", "오늘의 메뉴"]
SCHOLARSHIP_KEYWORDS = ["장학", "장학금", "국가장학금", "근로장학", "성적장학", "수혜"]
DORM_KEYWORDS = ["생활관", "기숙사", "오름관", "푸름관", "입사", "퇴사", "관생", "선발"]
EMPLOYMENT_KEYWORDS = ["취업", "채용", "인턴", "일자리", "현장실습", "LINC", "진로", "구인"]
EVENT_KEYWORDS = ["행사", "특강", "축제", "세미나", "공모전", "대회", "봉사", "OT", "오티"]

def classify_query_intent(query: str) -> str:
    """
    사용자 질문을 분석하여 의도(Intent)를 반환
    
    Returns:
        - "chitchat": 일상 대화 (검색 불필요, LLM 직접 응답)
        - "bus", "schedule", "menu", etc.: 학교 정보 검색 필요
        - "general": 일반 질문
    """
    q = query.strip()
    
    # 🔴 [추가] 일상 대화 먼저 체크 (검색 생략)
    if any(kw in q for kw in CHITCHAT_KEYWORDS): 
        return "chitchat"

    # 키워드 매칭 (순서가 중요할 수 있음)
    if any(kw in q for kw in BUS_KEYWORDS): return "bus"
    if any(kw in q for kw in SCHEDULE_KEYWORDS): return "schedule"
    if any(kw in q for kw in MENU_KEYWORDS): return "menu"
    if any(kw in q for kw in SCHOLARSHIP_KEYWORDS): return "scholarship"
    if any(kw in q for kw in DORM_KEYWORDS): return "dorm"
    if any(kw in q for kw in EMPLOYMENT_KEYWORDS): return "employment"
    if any(kw in q for kw in EVENT_KEYWORDS): return "event"
    
    return "general" # 그 외 일반 질문
# ---------------------------------------------------------
# 2. 검색 점수 보정 (Boosting)
# ---------------------------------------------------------
def boost_score(raw_score: float, payload: Dict[str, Any], intent: str) -> float:
    """
    의도에 맞는 게시판/문서에 가산점 부여
    """
    score = raw_score
    
    # 메타데이터 추출 (없으면 빈 문자열)
    site = (payload.get("site") or "").strip()
    board = (payload.get("board_name") or "").strip()
    title = (payload.get("title") or "").strip()
    tags = payload.get("tags", [])

    # --- 가산점 로직 ---
    if intent == "bus":
        if "버스" in site or "버스" in board: score += 0.1
        
    elif intent == "schedule":
        if "학사일정" in board or "학사일정" in title: score += 0.15
        if "schedule" in payload.get("source_type", ""): score += 0.2 # 학사일정 전용 데이터
        
    elif intent == "menu":
        if "식당" in site or "메뉴" in title or "restaurant" in str(payload.get("url", "")):
            score += 0.2
            
    elif intent == "scholarship":
        if "장학" in board or "학생복지" in board: score += 0.1
        
    elif intent == "dorm":
        if "생활관" in site or "기숙사" in board: score += 0.1
        
    elif intent == "employment":
        if "취업" in board or "채용" in board or "현장실습" in board: score += 0.1
        
    elif intent == "event":
        if "행사" in board or "비교과" in board: score += 0.05

    return score


def rerank_with_boost(hits: List[Any], intent: str, top_k: int) -> List[Any]:
    scored = []
    for h in hits:
        payload = h.payload or {}
        boosted = boost_score(h.score, payload, intent)
        scored.append((boosted, h))

    # 점수 높은 순 정렬
    scored.sort(key=lambda x: x[0], reverse=True)
    return [h for _, h in scored[:top_k]]