from __future__ import annotations
from auto.targets import TARGETS
from auto.fetch import fetch_html
from auto.parsers import parse_board_list, parse_menu, parse_schedule
from auto.saver import save_board, save_menu, save_schedule

def run_once(verbose: bool = True):
    success = 0
    for t in TARGETS:
        html = fetch_html(t.url)
        if not html:
            if verbose:
                print(f"[FAIL] {t.name} ({t.url})")
            continue

        if t.type == "board":
            items = parse_board_list(html, t.url)
            rows = [{"title": i.title, "url": i.url, "date": i.date or ""} for i in items]
            save_board(t.name, rows)
            if verbose: print(f"[OK] {t.name} ({len(rows)}개)")

        elif t.type == "menu":
            items = parse_menu(html, t.url)
            rows = [{"key": i.date_or_meal, "content": i.content} for i in items]
            save_menu(t.name, rows)
            if verbose: print(f"[OK] {t.name} ({len(rows)}개)")

        elif t.type == "schedule":
            items = parse_schedule(html, t.url)
            rows = [{"date": i.date, "title": i.title} for i in items]
            save_schedule(t.name, rows)
            if verbose: print(f"[OK] {t.name} ({len(rows)}개)")

        success += 1
    return success

if __name__ == "__main__":
    run_once()
