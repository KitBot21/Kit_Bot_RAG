# normalize.py
import json
import hashlib
import re
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse, parse_qs

# ---------------------------------------------------------
# ftfy: 텍스트 깨짐 자동 복구
# ---------------------------------------------------------
try:
    import ftfy
    def fix_text(text: str) -> str:
        if not text: return ""
        return ftfy.fix_text(text)
except ImportError:
    print("⚠️ ftfy 모듈이 없습니다. 'pip install ftfy'를 권장합니다.")
    def fix_text(text: str) -> str:
        return text or ""

def get_valid_date(raw: dict, meta: dict):
    """
    여러 소스에서 날짜를 찾아 가장 확실한 것을 반환
    우선순위: raw['created_at'] > meta['created_at'] > meta['post_date']
    """
    candidates = [
        raw.get("created_at"),
        meta.get("created_at"),
        meta.get("post_date")
    ]
    
    for date_str in candidates:
        if not date_str: continue
        # 포맷 정규화 (YYYY.MM.DD -> YYYY-MM-DD)
        s = str(date_str).strip().replace(".", "-")
        try:
            # 시간까지 있는 경우 (ISO format) 앞부분만 절삭
            if "T" in s: s = s.split("T")[0]
            
            dt = datetime.strptime(s, "%Y-%m-%d")
            return dt.isoformat().split("T")[0], True
        except ValueError:
            continue
            
    return None, False

def extract_title_from_text(text: str):
    if not text: return None
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines: return None
    return fix_text(lines[0])

def parse_created_at_from_meta(meta: dict):
    post_date = meta.get("post_date")
    if not post_date: return None, False
    s = post_date.strip().replace(".", "-")
    try:
        dt = datetime.strptime(s, "%Y-%m-%d")
        return dt.isoformat(), True
    except ValueError:
        return None, False

def parse_header_from_text(text: str):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    author = None
    view_count = None
    created_at_str = None 
    for i, line in enumerate(lines):
        if line == "작성자" and i + 1 < len(lines):
            author = lines[i + 1]
        elif line == "조회" and i + 1 < len(lines):
            num = "".join(ch for ch in lines[i + 1] if ch.isdigit())
            view_count = int(num) if num else None
        elif line == "작성일" and i + 1 < len(lines):
            created_at_str = lines[i + 1]
    return author, view_count, created_at_str

def clean_main_text(text: str):
    """
    헤더/꼬리 제거 및 [표 데이터] 태그 정리 (내용 소실 방지 포함)
    """
    if not text: return ""
    
    # 백업용 원본
    original_text = text

    # 1) [표 데이터 시작/끝] 태그 제거
    text = text.replace("[표 데이터 시작]", "").replace("[표 데이터 끝]", "")

    lines = [l.rstrip() for l in text.splitlines()]

    # 2) 헤더 줄 스킵
    start_idx = 0
    header_keys = {"작성자", "조회", "작성일"}
    found_header = False
    for i, line in enumerate(lines):
        if line.strip() in header_keys:
            found_header = True
        if found_header and line.strip() == "작성일":
            if i + 1 < len(lines): start_idx = i + 1
            break
    body_lines = lines[start_idx:]

    # 3) 꼬리 부분 잘라내기
    tail_markers = {"이전글", "다음글", "목록"}
    end_idx = len(body_lines)
    for i, line in enumerate(body_lines):
        # 정확히 일치하거나 시작하는 경우 자름
        if any(line.strip() == marker or line.strip().startswith(marker) for marker in tail_markers):
            end_idx = i
            break
    body_lines = body_lines[:end_idx]

    cleaned_text = "\n".join([l for l in body_lines if l.strip()])

    # 🔴 [중요] 정제했더니 내용이 다 날아갔으면(10자 미만), 원본 텍스트(태그만 뗀 것) 반환
    if len(cleaned_text) < 10 and len(original_text) > 50:
        return text.strip()

    return cleaned_text

def infer_site_and_board_from_title(raw: dict):
    meta = raw.get("metadata", {})
    meta_title = fix_text(meta.get("title") or raw.get("title") or "")
    parts = [p.strip() for p in meta_title.split("|") if p.strip()]
    site = None
    board_name = None
    if parts:
        site = parts[0]
        if len(parts) >= 2: board_name = " | ".join(parts[1:])
    if not (site and board_name):
        u = urlparse(raw.get("url", ""))
        path_parts = [p for p in u.path.split("/") if p]
        if not site and path_parts: site = path_parts[0]
        if not board_name and len(path_parts) > 1: board_name = path_parts[1]
    return site, board_name

def parse_schedule_by_regex(text: str) -> str:
    """
    Regex로 날짜 패턴이 있는 라인만 추출 (표 데이터가 텍스트로 변환된 경우에도 유효)
    """
    lines = text.splitlines()
    sentences = []
    date_pattern = re.compile(r'(\d{1,2})[\./-](\d{1,2})')
    
    sentences.append("이 문서는 금오공대 학사일정 정보를 포함하고 있습니다.")
    
    for line in lines:
        line = line.strip()
        if not line: continue
        if date_pattern.search(line):
            # 파이프(|)가 있으면 그대로 살려서 구조 유지
            sentences.append(f"일정 정보: {line}")
        
    if len(sentences) <= 1:
        return text
    return "\n".join(sentences)

def normalize_schedule_main_text(doc: dict) -> dict:
    """
    학사일정 페이지 main_text를 자연어 문장으로 정규화
    (단순 줄바꿈 데이터를 '제목: 날짜' 형태로 변환)
    """
    text = (doc.get("main_text") or "").strip()
    url = (doc.get("url") or "").strip()
    board_name = (doc.get("board_name") or "").strip()
    title = (doc.get("title") or "").strip()

    # 1) 학사일정 문서 여부 판단
    is_schedule_page = (
        "schedule" in url
        or "학사일정" in board_name
        or "학사일정" in title
    )
    
    if not is_schedule_page or not text:
        return doc

    # 2) 라인 단위로 분리 (공백 라인 제거)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    # 3) '번호' 키워드 찾기
    try:
        header_idx = lines.index("번호")
    except ValueError:
        # 번호 키워드가 없으면 그냥 원본 리턴 (혹은 Regex 처리)
        return doc

    # 4) 헤더 확인 (번호, 제목, 시작일, 종료일, 등록일, 조회) -> 총 6개 컬럼 구조
    # 실제 데이터가 6줄 단위로 반복되는지 확인
    
    summary_lines = []
    summary_lines.append(f"이 문서는 {board_name} 정보입니다.")
    summary_lines.append("주요 일정은 다음과 같습니다.\n")

    # 헤더 다음부터 데이터 시작
    # 보통 헤더가 6줄(번호~조회)이라고 가정
    i = header_idx + 6 
    
    # 데이터 파싱
    while i + 5 < len(lines):
        # 6개씩 끊어서 읽기
        chunk = lines[i : i + 6]
        
        # chunk 구조: [번호, 제목, 시작일, 종료일, 등록일, 조회수]
        # 예: ['360', '2학기 개시일', '2025-09-01', '2025-09-01', '2024-11-27', '0']
        
        row_title = chunk[1]
        start_date = chunk[2]
        end_date = chunk[3]
        
        # 날짜 형식이 맞는지 간단 체크 (YYYY-MM-DD)
        if "-" in start_date:
            if start_date == end_date:
                sentence = f"• {row_title}: {start_date} (하루)"
            else:
                sentence = f"• {row_title}: {start_date} ~ {end_date}"
            summary_lines.append(sentence)
        
        i += 6 # 다음 6줄로 이동

    # 변환된 내용이 있으면 교체
    if len(summary_lines) > 2:
        print(f"📅 학사일정 변환 성공: {len(summary_lines)-2}개 일정 추출됨 ({doc['doc_id']})")
        doc["main_text"] = "\n".join(summary_lines)
        
        # 검색 키워드 보강
        extra_keywords = ["학사일정", "일정표", "주요학사일정", "개강", "종강", "시험기간"]
        existing_tags = doc.get("tags") or []
        doc["tags"] = list(dict.fromkeys(existing_tags + extra_keywords))

    return doc

def make_doc_id_from_url(raw: dict):
    url = raw.get("url", "")
    u = urlparse(url)
    path_parts = [p for p in u.path.split("/") if p]
    host = (u.netloc or "site").split(".")[0]
    slug = path_parts[-1].split(".")[0] if path_parts else "root"
    qs = parse_qs(u.query)
    
    article_no = qs.get("articleNo", [None])[0]
    if article_no: return f"{host}_{slug}_{article_no}"
    
    offset = qs.get("article.offset", [None])[0]
    if offset: return f"{host}_{slug}_offset{offset}"
    
    page = qs.get("page", [None])[0]
    if page: return f"{host}_{slug}_p{page}"
    
    if u.query:
        h = hashlib.md5(u.query.encode("utf-8")).hexdigest()[:8]
        return f"{host}_{slug}_{h}"
    return f"{host}_{slug}"

def normalize_notice(raw: dict):
    meta = raw.get("metadata", {})
    
    # [Fix] 날짜 추출 함수 교체
    created_at, has_date = get_valid_date(raw, meta)
    
    text_content = fix_text(raw.get("main_text", "") or raw.get("text", ""))  # <--- "main_text"를 먼저 찾도록 수정
    author_from_text, view_from_text, created_from_text = parse_header_from_text(text_content)

    # 메타데이터에 날짜가 없으면 텍스트에서 파싱 시도
    if not created_at and created_from_text:
        s = created_from_text.strip().replace(".", "-")
        try:
            dt = datetime.strptime(s, "%Y-%m-%d")
            created_at = dt.isoformat().split("T")[0]
            has_date = True
        except ValueError: pass

    site, board_name = infer_site_and_board_from_title(raw)
    final_title = fix_text(raw.get("title") or extract_title_from_text(text_content))
    main_text = clean_main_text(text_content)

    # 🔴 [중요 수정] attachments가 root에 있는지, metadata 안에 있는지 모두 확인
    raw_attachments = raw.get("attachments") or meta.get("attachments") or []

    unified = {
        "doc_id": make_doc_id_from_url(raw),
        "source_type": "board",
        "site": fix_text(site),
        "board_name": fix_text(board_name),
        "title": final_title,
        "display_title": final_title,
        "author": fix_text(author_from_text),
        "url": raw.get("url"),
        "created_at": created_at,
        "updated_at": None,
        "has_explicit_date": has_date,
        "view_count": view_from_text,
        "doc_type": "html",
        "main_text": fix_text(main_text),
        
        # [Fix] 수정된 첨부파일 리스트 사용
        "attachments": raw_attachments,
        
        "images": [],
        "crawled_at": meta.get("crawled_at") or raw.get("crawled_at"),
        "source_meta": {
            "text_length": meta.get("text_length"),
            "raw_title": fix_text(raw.get("title")),
        },
    }
    unified = normalize_schedule_main_text(unified)
    return unified

def normalize_directory(input_dir: str, output_dir: str):
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    skipped = 0
    # 🔴 [중요 변경] 하위 폴더까지 재귀적으로 탐색 (**/*.json)
    for path in input_dir.glob("**/*.json"):
        # [New] 이미 변환된 파일인지 확인
        out_path = output_dir / f"{path.stem}.unified.json"
        if out_path.exists():
            if path.stat().st_mtime <= out_path.stat().st_mtime:
                skipped += 1
                continue

        try:
            with path.open(encoding="utf-8") as f:
                raw = json.load(f)
            
            unified = normalize_notice(raw)

            with out_path.open("w", encoding="utf-8") as f:
                json.dump(unified, f, ensure_ascii=False, indent=2)
            
            count += 1
        except Exception as e:
            print(f"❌ Error processing {path}: {e}")

    print(f"✅ 변환 완료: {count}개 (건너뜀: {skipped}개) → {output_dir}")

if __name__ == "__main__":
    normalize_directory("data/raw", "data/unified")