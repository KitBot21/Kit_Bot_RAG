from __future__ import annotations
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from dataclasses import dataclass

@dataclass
class BoardItem:
    title: str
    url: str
    date: str | None = None

@dataclass
class MenuItem:
    date_or_meal: str
    content: str

@dataclass
class ScheduleItem:
    date: str
    title: str

def _text(el) -> str:
    return " ".join(el.get_text(" ", strip=True).split()) if el else ""

# ───────────────────────────────────────────────────────────────
def parse_board_list(html: str, base: str) -> list[BoardItem]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[BoardItem] = []

    # table형 게시판
    for tr in soup.select("table tbody tr"):
        a = tr.select_one("a[href]")
        if not a:
            continue
        title = _text(a)
        href = urljoin(base, a["href"])
        date_td = tr.select("td")[-1] if tr.select("td") else None
        date = _text(date_td)
        items.append(BoardItem(title, href, date))
    if items:
        return items

    # ul/li형
    for li in soup.select("ul li a[href]"):
        title = _text(li)
        href = urljoin(base, li["href"])
        items.append(BoardItem(title, href))
    return items

# ───────────────────────────────────────────────────────────────
def parse_menu(html: str, base: str) -> list[MenuItem]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[MenuItem] = []

    for tr in soup.select("table tr"):
        th = tr.select_one("th")
        tds = tr.select("td")
        head = _text(th)
        body = " / ".join(_text(td) for td in tds if _text(td))
        if head or body:
            items.append(MenuItem(head or "-", body))
    if items:
        return items

    # div형 메뉴
    for div in soup.select(".menu, .tbl_wrap, .contents"):
        txt = _text(div)
        if txt:
            items.append(MenuItem("-", txt))
    return items

# ───────────────────────────────────────────────────────────────
def parse_schedule(html: str, base: str) -> list[ScheduleItem]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[ScheduleItem] = []

    for td in soup.select("table td"):
        date = _text(td.select_one(".day, .date") or td)
        for li in td.select("li"):
            title = _text(li)
            if title:
                items.append(ScheduleItem(date, title))
    return items
