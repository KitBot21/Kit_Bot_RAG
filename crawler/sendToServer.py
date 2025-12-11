# crawler/sendToServer.py
import requests

# 안드로이드 FastAPI 서버 IP 추가
SPRING_SERVER  = "http://10.36.235.197:8080/api/crawler/notification"

# 키워드 리스트 (예: 너가 정한 규칙)
KEYWORD_MAP = {
    "장학": "SCHOLARSHIP",
    "학사": "COURSE",
    "수강": "COURSE",
    "생활관": "DORM",
    "기숙사": "DORM",
    "행사": "EVENT",
    "특강": "EVENT",
    "취업": "EMPLOYMENT",
    "인턴": "EMPLOYMENT",
    "채용": "EMPLOYMENT",
}


def send_to_spring(url: str, keyword: str, title: str):
    """Spring Boot로 알림 전송"""
    payload = {
        "url": url,
        "keyword": keyword,
        "title": title,
    }

    try:
        resp = requests.post(SPRING_SERVER, json=payload, timeout=5)
        resp.raise_for_status()
        print(f"  ✅[알림 전송 성공] {keyword}: {title[:40]}...")
        return True
    except Exception as e:
        print(f"  ❌[알림 전송 실패] {e}")
        return False


def check_and_notify(url: str, title: str):
    """
    제목에 키워드가 포함되어 있으면 Spring Boot로 알림 전송
    Returns: (matched: bool, keyword: str or None)
    """
    for search_word, enum_name in KEYWORD_MAP.items():
        if search_word in title:
            success = send_to_spring(url, enum_name, title)
            return success, enum_name
    return False, None