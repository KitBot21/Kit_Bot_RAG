from __future__ import annotations
import argparse, csv, hashlib, os, uuid
from pathlib import Path
from typing import List, Dict, Tuple
from dotenv import load_dotenv
load_dotenv()   # .env 자동 로드

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
UPSTAGE_API_KEY = os.getenv("UPSTAGE_API_KEY")

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm
from embed_providers import get_encoder, DEFAULTS

# ----- 경로 기본값 -----
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR     = PROJECT_ROOT / "data"
FIXTURES_DIR = DATA_DIR / "fixtures"
PAGES_CSV    = DATA_DIR / "pages.csv"

FIELDNAMES = [
    "url", "saved_html_path", "page_title", "lastmod", "fetched_at",
    "section", "title_length", "text_length", "headline"
]

def _sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:20]

def _load_csv_rows(csv_path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with csv_path.open("r", encoding="utf-8") as f:
        peek = f.readline(); f.seek(0)
        if peek.lower().startswith(("http","https")):
            rd = csv.reader(f)
            for parts in rd:
                if not parts: continue
                parts = list(parts)
                if len(parts) < len(FIELDNAMES):
                    parts += [""] * (len(FIELDNAMES) - len(parts))
                elif len(parts) > len(FIELDNAMES):
                    head = parts[: len(FIELDNAMES) - 1]
                    tail = [",".join(parts[len(FIELDNAMES) - 1 :])]
                    parts = head + tail
                rows.append(dict(zip(FIELDNAMES, parts)))
        else:
            rd = csv.DictReader(f)
            for r in rd:
                rows.append(r)
    return rows

def _normalize_snapshot_path(p: str) -> Path:
    if not p: return Path("_not_exists_.html")
    norm = p.replace("\\","/")
    cand = Path(norm)
    if cand.exists(): return cand
    cand2 = PROJECT_ROOT / norm.lstrip("./")
    if cand2.exists(): return cand2
    fname = Path(norm).name
    cand3 = FIXTURES_DIR / fname
    if cand3.exists(): return cand3
    return cand2

def _html_to_text(html: str) -> str:
    import re
    html = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<.*?>", " ", html)
    return re.sub(r"\s+", " ", text).strip()

def _gather_texts(rows: List[Dict[str,str]], max_chars:int) -> Tuple[List[str], List[Dict[str,str]], List[str]]:
    texts: List[str] = []; metas: List[Dict[str,str]] = []; ids: List[str] = []
    for r in rows:
        url = (r.get("url") or "").strip()
        if not url: continue

        snap_path = _normalize_snapshot_path((r.get("saved_html_path") or "").strip())
        if not snap_path.exists():  # 스냅샷 파일 없으면 스킵
            continue

        # HTML 로딩 (utf-8 -> cp949 fallback)
        try:
            html = snap_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            try:
                html = snap_path.read_text(encoding="cp949", errors="ignore")
            except Exception:
                continue

        raw_text   = _html_to_text(html)
        page_title = (r.get("page_title") or "").strip()
        headline   = (r.get("headline") or "").strip()
        section    = (r.get("section") or "").strip()
        fetched_at = (r.get("fetched_at") or "").strip()
        lastmod    = (r.get("lastmod") or "").strip()

        text_for_embed = "\n".join(t for t in [page_title, headline, raw_text] if t)[:max_chars]
        if not text_for_embed: continue

        texts.append(text_for_embed)
        metas.append({
            "url": url,
            "page_title": page_title,
            "headline": headline,
            "section": section,
            "fetched_at": fetched_at,
            "lastmod": lastmod,
            "saved_html_path": str(snap_path),
            "content": text_for_embed[:1000],  # 디버깅/리랭킹용
        })
        ids.append(_sha1(url))
    return texts, metas, ids

def _ensure_collection(client: QdrantClient, name: str, dim: int):
    # 있으면 차원 일치 보장 위해 recreate (간단 루트)
    names = [c.name for c in client.get_collections().collections]
    if name in names:
        client.recreate_collection(
            collection_name=name,
            vectors_config=qm.VectorParams(size=dim, distance=qm.Distance.COSINE),
        )
    else:
        client.create_collection(
            collection_name=name,
            vectors_config=qm.VectorParams(size=dim, distance=qm.Distance.COSINE),
        )

def point_id_from_url(url: str) -> str:
    # URL 기반 안정적 UUID (형식: 8-4-4-4-12, 예: 123e4567-e89b-12d3-a456-426614174000)
    return str(uuid.uuid5(uuid.NAMESPACE_URL, url))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv",           default=str(PAGES_CSV))
    ap.add_argument("--host",          default=os.getenv("QDRANT_URL","http://localhost:6333"))
    ap.add_argument("--collection",    default="kit_pages")
    ap.add_argument("--provider",      choices=["e5","bge","openai","upstage"], default="e5")
    ap.add_argument("--limit",         type=int, default=0)
    ap.add_argument("--max_chars",     type=int, default=4000)
    ap.add_argument("--upsert-batch",  type=int, default=64)
    ap.add_argument("--prefer-grpc",   action="store_true")
    args = ap.parse_args()

    rows = _load_csv_rows(Path(args.csv))
    if args.limit > 0:
        rows = rows[:args.limit]

    texts, metas, ids = _gather_texts(rows, args.max_chars)
    if not texts:
        print("인덱싱 대상이 없습니다."); return

    # 임베더 선택 & 모델명
    encoder = get_encoder(args.provider)
    model_name = DEFAULTS[args.provider]

    # 임베딩
    vectors, dim = encoder(texts, model_name)

    # Qdrant 접속
    client = QdrantClient(url=args.host, prefer_grpc=args.prefer_grpc)

    # 컬렉션 이름: {base}__{provider}
    coll = f"{args.collection}__{args.provider}"
    _ensure_collection(client, coll, dim)

    # 업서트(배치)
    total = len(vectors); sent = 0
    batch: List[qm.PointStruct] = []

    def flush():
        nonlocal batch, sent
        if not batch: return
        client.upsert(collection_name=coll, points=batch, wait=True)
        sent += len(batch); print(f"[UPSERT] {sent}/{total}", flush=True)
        batch = []

    for i, v in enumerate(vectors):
        batch.append(qm.PointStruct(id=point_id_from_url(metas[i]["url"]), vector=v, payload=metas[i]))
        if len(batch) >= args.upsert_batch:
            flush()
    flush()
    print(f"Upsert 완료: {total}건 → {coll} (dim={dim}, model={model_name})")

if __name__ == "__main__":
    main()
