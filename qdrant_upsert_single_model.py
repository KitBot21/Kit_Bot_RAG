# qdrant_upsert_single_model.py
import numpy as np
import pandas as pd
import uuid
from pathlib import Path
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct

def point_id_from_url(url: str) -> str:
    # URL 기반 안정적 UUID 생성
    return str(uuid.uuid5(uuid.NAMESPACE_URL, url))

QDRANT_URL = "http://localhost:6333"
TIMEOUT = 300  # 타임아웃을 5분으로 설정
# CSV_PATH는 이제 커맨드라인 인자로 받음

# 벡터 차원 정보 (실제 임베딩 파일의 차원에 맞춤)
VECTOR_DIMS = {
    "bge": 1024,
    "e5": 768,
    "openai": 3072,
    "upstage": 4096,
    "kosimcse": 768,
    "krsbert": 768
}

import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--model", required=True, choices=list(VECTOR_DIMS.keys()))
parser.add_argument("--collection", required=True)
parser.add_argument("--input", required=True)
args = parser.parse_args()

MODEL_NAME = args.model
EMBED_PATH = f"embeddings/{MODEL_NAME}.npy"
COLLECTION = args.collection
VECTOR_DIM = VECTOR_DIMS[MODEL_NAME]
BATCH = 100  # 배치 크기를 줄임

def main():
    df = pd.read_csv(args.input)
    embeds = np.load(EMBED_PATH)
    assert embeds.shape[0] == len(df), "임베딩 개수와 CSV row 수가 다름!"

    client = QdrantClient(url=QDRANT_URL, timeout=TIMEOUT)

    if not client.collection_exists(COLLECTION):
        client.recreate_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
        )

    for start in range(0, len(df), BATCH):
        end = min(start + BATCH, len(df))
        batch = []
        for idx in range(start, end):
            payload = df.iloc[idx].to_dict()
            payload.pop("text", None)   # text는 Qdrant에 저장시켜도 되지만 클라이언트 RAM 절약용으로 제거할 수 있음
            batch.append(
                PointStruct(
                    id=point_id_from_url(df.at[idx, "url"]),  # URL로부터 UUID 생성
                    vector=embeds[idx].tolist(),
                    payload=payload,
                )
            )
        client.upsert(collection_name=COLLECTION, points=batch)
        print(f"✅ upsert {end}/{len(df)}")

    print(f"\n🎉 업로드 완료: {COLLECTION}")

if __name__ == "__main__":
    main()
