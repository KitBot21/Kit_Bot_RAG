# fixtures_to_corpus_with_sources.py
import csv, re, os, hashlib
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from charset_normalizer import from_bytes

FIXTURES_DIR = Path("data/fixtures")
OUT_CSV      = Path("data/corpus_with_sources.csv")
CHARS, OVERLAP = 600, 50   # ~100–200토큰 / ~8% overlap (테스트용)

SKIP_TAGS = {"script","style","noscript"}
DROP_SELECTORS = [
    "header","footer","nav","aside",
    "[role=banner]","[role=navigation]","[role=contentinfo]"
]

def detect_enc(b: bytes) -> str:
    r = from_bytes(b).best()
    return r.encoding or "utf-8"

def sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def clean(s: str) -> str:
    s = s.replace("\u00a0"," ").replace("\t"," ")
    s = re.sub(r"[ \t]+"," ", s)
    s = re.sub(r"\n{3,}","\n\n", s)
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
        
        # 청크 크기 검증
        chunk_text = full_text[i:k]
        chunk_len = len(chunk_text)
        
        # 너무 짧은 청크는 건너뛰기
        if chunk_len < 100:
            if k >= n:  # 마지막 청크인 경우에만 추가
                if chunk_len >= 40:
                    out.append((chunk_text, i, k))
            else:
                # 다음 청크와 합치기
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
    # 1) canonical 2) og:url 3) base[href] 4) 하단 Snapshot of 링크
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

    # 후보 영역
    main = soup.select_one("main") or soup.select_one("article") or soup.select_one("section")
    if not main:
        main = soup.body or soup

    # (옵션) 사이트 특화 공지 리스트를 구조화 텍스트로 앞에 추가
    notice_blk = []
    for li in soup.select(".main-board-list li a[title]"):
        title = li.get("title") or li.get_text(strip=True)
        date  = li.select_one("span").get_text(strip=True) if li.select_one("span") else ""
        notice_blk.append(f"[공지] {date} {title}")
    structured = "\n".join(notice_blk)

    body_text = main.get_text("\n", strip=True)
    merged = (structured + "\n\n" + body_text).strip() if structured else body_text

    # 간이 selector 표기(루트만 기록)
    selector = getattr(main, "name", "body")
    return clean(merged), selector

def doc_fields_from_url(url: str, fname: str):
    if url:
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
    # 페이지 상단/하단 meta에 "Fetched at:" 포맷 지원
    for m in soup.select("div.meta"):
        t = m.get_text(" ", strip=True)
        m0 = re.search(r"Fetched at:\s*([\d\-T:]+)", t)
        if m0:
            return m0.group(1).split("T")[0]
    return ""

def main():
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    errors = []

    for p in sorted(FIXTURES_DIR.glob("*")):
        if not p.is_file(): continue
        
        try:
            raw = p.read_bytes()
            html = raw.decode(detect_enc(raw), errors="ignore")
            soup = BeautifulSoup(html, "lxml")

            title = (soup.title.get_text(strip=True) if soup.title else "") or get_meta(soup, prop="og:title")
            url = extract_base_url(soup)
            domain, source_path, section, doc_id = doc_fields_from_url(url, p.name)
            accessed_at = fetched_date(soup)
            page_text, selector = extract_body_text_and_selector(soup)
            
            if len(page_text) < 40:
                continue

            page_sha = sha256(page_text)
            chunks = chunk_text(page_text)
            
            # 청크가 없으면 건너뛰기
            if not chunks:
                continue

            for idx, (ch, s0, s1) in enumerate(chunks, start=1):
                # 청크 크기 최종 검증 (최소 40자, 최대 5000자)
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

    print(f"✅ Wrote {len(rows)} chunks → {OUT_CSV}")
    if errors:
        print(f"⚠️  {len(errors)} files had errors:")
        for err in errors[:5]:  # 처음 5개 에러만 표시
            print(f"   {err}")
        if len(errors) > 5:
            print(f"   ... and {len(errors) - 5} more")

if __name__ == "__main__":
    main()
