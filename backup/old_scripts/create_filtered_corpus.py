# create_filtered_corpus.py
# Ground truth에 등장하는 33개 문서만으로 필터링된 corpus 생성
import csv, re, os, hashlib, pandas as pd
from pathlib import Path
from bs4 import BeautifulSoup
from charset_normalizer import from_bytes

FIXTURES_DIR = Path("data/fixtures")
OUT_CSV      = Path("data/corpus_filtered.csv")
GROUND_TRUTH = Path("data/ground_truth.csv")
CHARS, OVERLAP = 800, 100   # 800자 chunk, 100자 overlap

SKIP_TAGS = {"script","style","noscript"}
DROP_SELECTORS = [
    "header","footer","nav","aside",
    "[role=banner]","[role=navigation]","[role=contentinfo]"
]

# 제거할 불필요한 텍스트 패턴
NOISE_PATTERNS = [
    r'공지사항.*?바로가기',
    r'다음\s*페이지',
    r'이전\s*페이지',
    r'페이지\s*이동',
    r'목록으로',
    r'top\s*↑',
    r'맨\s*위로',
    r'Home\s*›',
    r'sitemap',
    r'copyright.*?all\s+rights\s+reserved',
    r'개인정보처리방침',
    r'이메일무단수집거부',
    r'\[\s*인쇄\s*\]',
    r'\[\s*목록\s*\]',
]

# 제외할 URL 패턴 (목록/게시판 페이지)
EXCLUDE_URL_PATTERNS = [
    r'/sub06_01_01_01\.do',  # 공지사항 목록
    r'/sub07_04_01\.do',      # 개인정보처리방침
    r'/notice\.do$',          # 공지사항 목록 (게시판)
]

# 제외할 제목 키워드
EXCLUDE_TITLE_KEYWORDS = [
    '개인정보처리방침',
    '이메일무단수집거부',
]

def detect_enc(b: bytes) -> str:
    r = from_bytes(b).best()
    return r.encoding or "utf-8"

def sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def remove_noise(text: str) -> str:
    """불필요한 텍스트 패턴 제거"""
    for pattern in NOISE_PATTERNS:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    return text

def clean(s: str) -> str:
    s = s.replace("\u00a0"," ").replace("\t"," ")
    s = re.sub(r"[ \t]+"," ", s)
    s = re.sub(r"\n{3,}","\n\n", s)
    s = remove_noise(s)  # 노이즈 제거 추가
    return s.strip()

def chunk_text(full_text: str, size=CHARS, overlap=OVERLAP):
    """return list of (chunk_text, start, end) by char offset"""
    full_text = clean(full_text)
    n = len(full_text)
    if n == 0: return []
    out = []
    i = 0
    while i < n:
        j = min(n, i + size)
        k = j
        # 문장 경계 보정 (한글/영문 구두점 모두 고려)
        sentence_endings = ".!?。\n"
        for off in range(200):
            if j + off < n and full_text[j + off:j + off + 1] in sentence_endings:
                k = j + off + 1
                break
        
        chunk_text = full_text[i:k]
        chunk_len = len(chunk_text)
        
        # 너무 짧은 청크는 건너뛰기
        if chunk_len < 100:
            if k >= n:  # 마지막 청크인 경우에만 추가
                if chunk_len >= 40:
                    out.append((chunk_text, i, k))
            else:
                i = k
                continue
        else:
            out.append((chunk_text, i, k))
        
        if k >= n: break
        i = max(0, k - overlap)
    return out

def guess_lang(s: str) -> str:
    return "ko" if re.search(r"[가-힣]", s) else "en"

def get_meta(soup: BeautifulSoup, name=None, prop=None):
    if name:
        tag = soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"): return tag["content"].strip()
    if prop:
        tag = soup.find("meta", attrs={"property": prop})
        if tag and tag.get("content"): return tag["content"].strip()
    return ""

def extract_base_url(soup: BeautifulSoup):
    canonical = ""
    link = soup.find("link", rel="canonical")
    if link and link.get("href"): canonical = link["href"].strip()

    og_url = get_meta(soup, prop="og:url")
    base = soup.base["href"].strip() if soup.base and soup.base.get("href") else ""
    snap = ""
    for a in soup.select("div.meta a[href]"):
        if "http" in a["href"]:
            snap = a["href"].strip(); break

    url = canonical or og_url or snap or base
    return url

def extract_body_text_and_selector(soup: BeautifulSoup):
    # 방해 요소 제거
    for t in soup.find_all(SKIP_TAGS): t.decompose()
    for sel in DROP_SELECTORS:
        for t in soup.select(sel): t.decompose()

    main = soup.select_one("main") or soup.select_one("article") or soup.select_one("section")
    if not main:
        main = soup.body or soup

    body_text = main.get_text("\n", strip=True)
    selector = getattr(main, "name", "body")
    return clean(body_text), selector

def doc_fields_from_url(url: str, fname: str):
    if url:
        from urllib.parse import urlparse
        u = urlparse(url)
        domain = (u.netloc or "").lower()
        source_path = u.path or "/"
        section = source_path.strip("/").split("/")[0] if source_path.strip("/") else ""
        doc_id = re.sub(r"\W+","_", (u.netloc + u.path).lower()).strip("_")
    else:
        domain = ""
        source_path = ""
        section = ""
        doc_id = re.sub(r"\W+","_", os.path.splitext(fname)[0].lower()).strip("_")
    return domain, source_path, section, doc_id

def fetched_date(soup: BeautifulSoup):
    for m in soup.select("div.meta"):
        t = m.get_text(" ", strip=True)
        m0 = re.search(r"Fetched at:\s*([\d\-T:]+)", t)
        if m0:
            return m0.group(1).split("T")[0]
    return ""

def should_exclude_url(url: str, source_path: str) -> bool:
    """URL이나 경로가 제외 대상인지 확인"""
    for pattern in EXCLUDE_URL_PATTERNS:
        if re.search(pattern, source_path):
            return True
    return False

def should_exclude_title(title: str) -> bool:
    """제목이 제외 대상인지 확인"""
    for keyword in EXCLUDE_TITLE_KEYWORDS:
        if keyword in title:
            return True
    return False

def load_relevant_doc_ids():
    """Ground truth에서 관련 doc_id 추출"""
    df = pd.read_csv(GROUND_TRUTH)
    # chunk_id에서 doc_id 추출 (예: "dorm__index_do__113ff7aca47c2bdc_0001" -> "dorm__index_do__113ff7aca47c2bdc")
    doc_ids = set()
    for chunk_id in df['chunk_id'].unique():
        # 마지막 _숫자 부분 제거
        doc_id = '_'.join(chunk_id.split('_')[:-1])
        doc_ids.add(doc_id)
    
    print(f"Ground truth에서 추출한 관련 문서: {len(doc_ids)}개")
    return doc_ids

def main():
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    
    # Ground truth에서 관련 doc_id 로드
    relevant_doc_ids = load_relevant_doc_ids()
    
    rows = []
    errors = []
    skipped = 0
    excluded_by_url = 0
    excluded_by_title = 0

    for p in sorted(FIXTURES_DIR.glob("*")):
        if not p.is_file(): continue
        
        try:
            raw = p.read_bytes()
            html = raw.decode(detect_enc(raw), errors="ignore")
            soup = BeautifulSoup(html, "lxml")

            title = (soup.title.get_text(strip=True) if soup.title else "") or get_meta(soup, prop="og:title")
            url = extract_base_url(soup)
            domain, source_path, section, doc_id = doc_fields_from_url(url, p.name)
            
            # 관련 문서가 아니면 건너뛰기
            if doc_id not in relevant_doc_ids:
                skipped += 1
                continue
            
            # URL 패턴으로 제외
            if should_exclude_url(url, source_path):
                excluded_by_url += 1
                continue
            
            # 제목으로 제외
            if should_exclude_title(title):
                excluded_by_title += 1
                continue
            
            accessed_at = fetched_date(soup)
            page_text, selector = extract_body_text_and_selector(soup)
            
            if len(page_text) < 40:
                continue

            page_sha = sha256(page_text)
            chunks = chunk_text(page_text)
            
            if not chunks:
                continue

            for idx, (ch, s0, s1) in enumerate(chunks, start=1):
                if len(ch) < 40 or len(ch) > 5000:
                    continue
                    
                rows.append({
                    "chunk_id": f"{doc_id}_{idx:04d}",
                    "doc_id": doc_id,
                    "text": ch,
                    "title": title or p.name,
                    "url": url,
                    "canonical_url": url,
                    "snapshot_url": str(p),
                    "domain": domain,
                    "source_path": source_path,
                    "section": section,
                    "accessed_at": accessed_at,
                    "lastmod": get_meta(soup, name="lastmod") or "",
                    "publisher": get_meta(soup, prop="og:site_name") or domain,
                    "selector": selector,
                    "char_start": s0,
                    "char_end": s1,
                    "chunk_sha256": sha256(ch),
                    "page_sha256": page_sha,
                    "lang": guess_lang(ch),
                    "tags": ""
                })
        except Exception as e:
            errors.append(f"{p.name}: {str(e)}")
            continue

    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "chunk_id","doc_id","text","title","url","canonical_url","snapshot_url",
            "domain","source_path","section","accessed_at","lastmod","publisher",
            "selector","char_start","char_end","chunk_sha256","page_sha256","lang","tags"
        ])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n✅ 필터링된 corpus 생성 완료!")
    print(f"   - 총 chunk 수: {len(rows)}")
    print(f"   - 고유 doc_id: {len(set(r['doc_id'] for r in rows))}")
    print(f"   - 건너뛴 문서 (관련 없음): {skipped}개")
    print(f"   - 제외된 문서 (URL 패턴): {excluded_by_url}개")
    print(f"   - 제외된 문서 (제목 키워드): {excluded_by_title}개")
    print(f"   - 저장 위치: {OUT_CSV}")
    
    if errors:
        print(f"\n⚠️  {len(errors)} 파일에서 에러 발생:")
        for err in errors[:5]:
            print(f"   {err}")
        if len(errors) > 5:
            print(f"   ... 외 {len(errors) - 5}개")

if __name__ == "__main__":
    main()
