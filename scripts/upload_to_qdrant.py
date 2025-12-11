#!/usr/bin/env python3
"""
corpus_all.csv + bge_all.npy를 Qdrant에 업로드
"""
import numpy as np
import pandas as pd
from pathlib import Path
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm
import hashlib
from tqdm import tqdm

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
EMBEDDINGS_DIR = PROJECT_ROOT / "embeddings"

# 설정
CORPUS_CSV = DATA_DIR / "corpus_all.csv"
EMBEDDINGS_NPY = EMBEDDINGS_DIR / "bge_all.npy"
QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "kit_corpus_bge_all"
BATCH_SIZE = 100

def generate_id(text: str, url: str) -> str:
    """텍스트와 URL을 조합하여 고유 ID 생성"""
    combined = f"{url}::{text[:100]}"
    return hashlib.md5(combined.encode()).hexdigest()

def main():
    print("=" * 80)
    print("📤 Qdrant 업로드")
    print("=" * 80)
    
    # 1. 데이터 로드
    print(f"\n📂 데이터 로드 중...")
    print(f"   Corpus: {CORPUS_CSV}")
    print(f"   Embeddings: {EMBEDDINGS_NPY}")
    
    df = pd.read_csv(CORPUS_CSV)
    embeddings = np.load(EMBEDDINGS_NPY)
    
    # NaN 제거 (임베딩 생성 시와 동일한 필터링)
    df = df[df['text'].notna()].reset_index(drop=True)
    df['text'] = df['text'].astype(str)
    df = df[df['text'].str.strip() != ''].reset_index(drop=True)
    
    print(f"   ✅ Corpus: {len(df):,}개")
    print(f"   ✅ Embeddings: {embeddings.shape}")
    
    if len(df) != len(embeddings):
        print(f"\n❌ 오류: Corpus와 Embeddings 개수가 맞지 않습니다!")
        print(f"   Corpus: {len(df)}, Embeddings: {len(embeddings)}")
        return
    
    # 2. Qdrant 연결
    print(f"\n🔌 Qdrant 연결 중...")
    print(f"   URL: {QDRANT_URL}")
    
    client = QdrantClient(url=QDRANT_URL)
    
    # 3. 컬렉션 생성 (기존 것이 있으면 삭제)
    print(f"\n📦 컬렉션 생성 중...")
    print(f"   이름: {COLLECTION_NAME}")
    print(f"   차원: {embeddings.shape[1]}")
    
    # 기존 컬렉션 확인
    collections = client.get_collections().collections
    collection_names = [c.name for c in collections]
    
    if COLLECTION_NAME in collection_names:
        print(f"   ⚠️  기존 컬렉션 삭제 중...")
        client.delete_collection(COLLECTION_NAME)
    
    # 새 컬렉션 생성
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=qm.VectorParams(
            size=embeddings.shape[1],
            distance=qm.Distance.COSINE
        )
    )
    print(f"   ✅ 컬렉션 생성 완료")
    
    # 4. 데이터 업로드
    print(f"\n⏳ 데이터 업로드 중...")
    print(f"   배치 크기: {BATCH_SIZE}")
    
    points = []
    uploaded = 0
    
    for idx, row in tqdm(df.iterrows(), total=len(df), desc="업로드"):
        # Point 생성
        point_id = generate_id(str(row.get('text', '')), str(row.get('url', '')))
        
        payload = {
            'text': str(row.get('text', '')),
            'url': str(row.get('url', '')),
            'title': str(row.get('title', '')),
            'source_type': str(row.get('source_type', '')),
            'document_name': str(row.get('document_name', '')),
        }
        
        # NaN 값 처리
        payload = {k: (v if pd.notna(v) and v != 'nan' else '') for k, v in payload.items()}
        
        point = qm.PointStruct(
            id=point_id,
            vector=embeddings[idx].tolist(),
            payload=payload
        )
        
        points.append(point)
        
        # 배치 업로드
        if len(points) >= BATCH_SIZE:
            client.upsert(
                collection_name=COLLECTION_NAME,
                points=points,
                wait=True
            )
            uploaded += len(points)
            points = []
    
    # 남은 데이터 업로드
    if points:
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=points,
            wait=True
        )
        uploaded += len(points)
    
    print(f"\n✅ 업로드 완료!")
    
    # 5. 검증
    print(f"\n🔍 검증 중...")
    collection_info = client.get_collection(COLLECTION_NAME)
    print(f"   컬렉션: {COLLECTION_NAME}")
    print(f"   벡터 개수: {collection_info.points_count:,}개")
    print(f"   벡터 차원: {collection_info.config.params.vectors.size}")
    
    print("\n" + "=" * 80)
    print("🎉 완료!")
    print("=" * 80)
    print(f"   총 업로드: {uploaded:,}개")
    print(f"   컬렉션: {COLLECTION_NAME}")
    print(f"\n💡 다음 단계: python rag_demo.py --collection {COLLECTION_NAME}")
    print("=" * 80)

if __name__ == "__main__":
    main()
