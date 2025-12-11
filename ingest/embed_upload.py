import uuid
import hashlib
from pathlib import Path
import json
from typing import List, Dict

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

# ===== 설정 =====
QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "kitbot_docs_bge"
EMBED_MODEL_NAME = "BAAI/bge-m3"
VECTOR_DIM = 1024
BATCH_SIZE = 64

def get_project_paths():
    project_root = Path(__file__).resolve().parents[1]
    data_dir = project_root / "data"
    chunks_dir = data_dir / "chunks"
    log_path = data_dir / "embedded_log.txt"
    return project_root, data_dir, chunks_dir, log_path

def ensure_collection(client: QdrantClient, collection_name: str):
    if client.collection_exists(collection_name):
        print(f"ℹ️  컬렉션 '{collection_name}'이 이미 존재합니다. (데이터 추가/갱신 모드)")
        return

    print(f"⚠️ 컬렉션 '{collection_name}' 없음 → 새로 생성")
    client.create_collection(
        collection_name=collection_name,
        vectors_config=qm.VectorParams(
            size=VECTOR_DIM,
            distance=qm.Distance.COSINE,
        ),
    )
    print(f"✅ 컬렉션 '{collection_name}' 생성 완료")

# [Update] ID와 Content Hash를 같이 로드
def load_processed_log(log_path: Path) -> Dict[str, str]:
    if not log_path.exists():
        return {}
    
    processed = {}
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) >= 2:
                    # key: chunk_id, value: content_hash
                    processed[parts[0]] = parts[1]
    except Exception:
        pass # 파일이 깨졌거나 포맷이 다르면 무시
    return processed

# [Update] ID와 Content Hash를 같이 저장
def save_processed_log(log_path: Path, items: List[tuple]):
    with open(log_path, "a", encoding="utf-8") as f:
        for cid, chash in items:
            f.write(f"{cid}\t{chash}\n")

def calculate_content_hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()

def load_chunks(chunks_dir: Path, processed_log: Dict[str, str]):
    files = sorted(chunks_dir.glob("*.json"))
    print(f"ℹ️  청크 파일 {len(files)}개 발견")
    
    skipped = 0
    for path in files:
        try:
            with path.open(encoding="utf-8") as f:
                chunk = json.load(f)
            
            chunk_id = chunk["chunk_id"]
            text = chunk["text"]
            current_hash = calculate_content_hash(text)
            
            # [핵심] ID가 있고, 내용 해시값까지 똑같아야 스킵!
            if chunk_id in processed_log:
                if processed_log[chunk_id] == current_hash:
                    skipped += 1
                    continue
                # ID는 있는데 해시가 다르면? -> 내용이 바뀐 것! (통과 -> 업데이트 대상)

            # 해시값을 청크 객체에 임시 저장 (나중에 로그 저장용)
            chunk["_content_hash"] = current_hash
            yield chunk
            
        except Exception:
            continue
    
    if skipped > 0:
        print(f"⏭️  변경 없는 {skipped}개 청크 스킵함")

def chunks_to_batches(iterable, batch_size: int):
    batch = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch

def generate_uuid_from_string(string: str) -> str:
    hash_value = hashlib.md5(string.encode("utf-8")).hexdigest()
    return str(uuid.UUID(hash_value))

def embed_and_upload(chunks_dir: Path = None):
    project_root, data_dir, default_chunks_dir, log_path = get_project_paths()
    if chunks_dir is None:
        chunks_dir = default_chunks_dir

    if not chunks_dir.exists():
        raise FileNotFoundError(f"청크 디렉터리가 없습니다: {chunks_dir}")

    # 1) 기존 로그 로드 (ID + Hash)
    processed_log = load_processed_log(log_path)
    print(f"📋 기존 완료 기록: {len(processed_log)}개 로드됨")

    print("⏳ 임베딩 모델 로딩 중...", EMBED_MODEL_NAME)
    model = SentenceTransformer(EMBED_MODEL_NAME)

    client = QdrantClient(url=QDRANT_URL)
    ensure_collection(client, COLLECTION_NAME)

    total_new_chunks = 0
    
    # 2) 변경된 것만 골라내기
    chunk_generator = load_chunks(chunks_dir, processed_log)

    for batch in chunks_to_batches(chunk_generator, BATCH_SIZE):
        texts: List[str] = [c["text"] for c in batch]
        vectors = model.encode(texts, batch_size=BATCH_SIZE, convert_to_numpy=True)

        points = []
        log_items = [] # (id, hash) 튜플 저장

        for vec, chunk in zip(vectors, batch):
            meta = chunk.get("metadata", {})
            fixed_id = generate_uuid_from_string(chunk["chunk_id"])
            
            # 로그에 저장할 정보 준비
            log_items.append((chunk["chunk_id"], chunk["_content_hash"]))

            payload = {
                "chunk_id": chunk["chunk_id"],
                "doc_id": chunk["doc_id"],
                "chunk_index": chunk["chunk_index"],
                "text": chunk["text"],
                
                "site": meta.get("site"),
                "board_name": meta.get("board_name"),
                "title": meta.get("title"),
                "url": meta.get("url"),
                "created_at": meta.get("created_at"),
                
                "tags": meta.get("tags", []),
                "source_type": meta.get("source_type"),
                "file_name": meta.get("original_filename"),
                "parent_title": meta.get("parent_title")
            }

            points.append(
                qm.PointStruct(
                    id=fixed_id,
                    vector=vec.tolist(),
                    payload=payload,
                )
            )

        # Qdrant 업로드 (덮어쓰기)
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=points,
        )
        
        # [Update] 처리된 ID와 해시값 기록
        save_processed_log(log_path, log_items)

        total_new_chunks += len(batch)
        print(f"✅ 업데이트 배치 {len(batch)}개 완료 (누적: {total_new_chunks})")

    if total_new_chunks == 0:
        print("✨ 새로 추가/변경된 데이터가 없습니다.")
    else:
        print(f"🎉 총 {total_new_chunks}개 청크 업데이트 완료!")

if __name__ == "__main__":
    _, _, chunks_dir, _ = get_project_paths()
    embed_and_upload(chunks_dir)