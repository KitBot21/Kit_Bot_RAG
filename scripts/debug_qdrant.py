#!/usr/bin/env python3
"""Qdrant 검색 결과 구조 확인"""

from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

# 모델 및 Qdrant 설정
model = SentenceTransformer('BAAI/bge-m3')
client = QdrantClient(url="http://localhost:6333")

# 테스트 쿼리
query = "통학버스는 몇 시에 출발하나요?"
query_vector = model.encode(query, normalize_embeddings=True).tolist()

# 검색
results = client.search(
    collection_name="kit_corpus_bge_all",
    query_vector=query_vector,
    limit=5
)

print(f"검색 쿼리: {query}\n")
print(f"검색 결과: {len(results)}개\n")

# 결과 상세 출력
for i, hit in enumerate(results, 1):
    print(f"[{i}] Score: {hit.score:.4f}")
    print(f"    Payload keys: {list(hit.payload.keys())}")
    print(f"    ID: {hit.payload.get('id', 'NO_ID')}")
    print(f"    Document: {hit.payload.get('document_name', 'NO_DOC')[:80]}")
    print(f"    Text: {hit.payload.get('text', 'NO_TEXT')[:100]}...")
    print()

# Corpus 로드하여 매칭 확인
corpus = pd.read_csv(DATA_DIR / "corpus_all.csv")
print(f"\n📊 Corpus 크기: {len(corpus)}개")

# 첫 번째 검색 결과의 ID로 corpus에서 찾기
first_id = results[0].payload.get('id', '')
print(f"\n첫 번째 결과 ID: '{first_id}'")

match = corpus[corpus['id'] == first_id]
if len(match) > 0:
    print(f"✅ Corpus에서 매칭됨!")
    print(f"   Index: {match.index[0]}")
    print(f"   Document: {match.iloc[0]['document_name']}")
else:
    print(f"❌ Corpus에서 매칭 실패!")
    # ID가 비슷한 것 찾기
    similar = corpus[corpus['id'].str.contains(first_id[:10], na=False)]
    if len(similar) > 0:
        print(f"   비슷한 ID: {similar.iloc[0]['id']}")
