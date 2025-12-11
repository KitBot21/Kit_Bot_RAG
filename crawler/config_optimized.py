#!/usr/bin/env python3
"""
개선된 크롤러 설정 및 필터링
- JSON 저장 포맷
- 2021년 이후 데이터만
- 품질 필터링 (너무 짧은 페이지 스킵)
- 로그인 페이지 자동 감지 및 스킵
"""

# config_optimized.yml과 함께 사용할 설정
CRAWL_CONFIG = {
    # 날짜 필터
    "date_filter": {
        "enabled": True,
        "cutoff_date": "2021-01-01",  # 2021년 이월 이후만
    },
    
    # 품질 필터
    "quality_filter": {
        "enabled": True,
        "min_text_length": 100,        # 최소 100자 이상
        "max_text_length": 500000,     # 최대 50만자
        "min_word_count": 20,          # 최소 20단어
        "skip_patterns": [
            "404",
            "Not Found",
            "페이지를 찾을 수 없습니다",
            "접근 권한이 없습니다",
            "Access Denied",
            "로그인이 필요합니다",
        ]
    },
    
    # 로그인 페이지 감지 패턴
    "login_detection": {
        "enabled": True,
        "url_patterns": [
            "/login",
            "/signin",
            "/auth",
            "/sso",
            "loginForm",
        ],
        "content_patterns": [
            "아이디",
            "비밀번호",
            "로그인",
            "login",
            "password",
            "username",
            "sign in",
        ],
        "min_pattern_matches": 2,  # 최소 2개 이상 매칭되면 로그인 페이지로 판단
    },
    
    # 불필요한 페이지 스킵
    "skip_urls": [
        "/cms/fileDownload.do",
        "/restaurant_menu_reg",
        "/restaurant_reg", 
        "/popup",
        "/print",
        "/share",
        "/download",
        "/search",  # 검색 페이지
    ],
    
    # 출력 형식
    "output": {
        "format": "json",  # json 또는 html
        "pretty_print": False,  # JSON 압축
        "include_metadata": True,
    }
}
