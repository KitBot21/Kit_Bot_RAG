# core/login_detect.py
from __future__ import annotations
from bs4 import BeautifulSoup
import re

# URL에 login/sso/account 등 흔한 패턴이 보이면 차단
LOGIN_URL_PATTERNS = [
    "/login",
]
_login_url_re = re.compile("|".join(LOGIN_URL_PATTERNS), re.IGNORECASE)

def is_login_like_url(url: str) -> bool:
    return bool(_login_url_re.search(url))

# HTML 내부에서 로그인 화면 특징을 찾으면 차단
def is_login_page_html(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")

    # 1) 대표 컨테이너(class/id)
    candidate_classes = [
        "login-wrapper",
        "login_wrap",
    ]
    for cls in candidate_classes:
        if soup.find(True, {"class": lambda v: v and cls in v}):
            return True
    if soup.find(id=re.compile(r"^login(|-)?(wrap|wrapper|form|box)$", re.I)):
        return True
    
    return False
