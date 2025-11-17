#!/usr/bin/env python3
"""중복 문서 확인"""

from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('BAAI/bge-m3')
client = QdrantClient(url="http://localhost:6333")

query = "버스 예약은 언제까지 가능한가요?"
query_vector = model.encode(query, normalize_embeddings=True).tolist()

results = client.search(
    collection_name="kit_corpus_bge_all",
    query_vector=query_vector,
    limit=10
)

print(f"쿼리: {query}\n")
print(f"검색 결과: {len(results)}개\n")

seen_titles = {}
for i, hit in enumerate(results, 1):
    title = hit.payload.get('title', 'NO_TITLE')
    doc_name = hit.payload.get('document_name', 'NO_DOC')
    
    if title in seen_titles:
        print(f"[{i}] ⚠️  중복! Score: {hit.score:.4f}")
    else:
        print(f"[{i}] ✅ 새문서 Score: {hit.score:.4f}")
        seen_titles[title] = i
    
    print(f"    Title: {title[:80]}")
    print(f"    Doc: {doc_name[:80]}")
    print()

print(f"\n고유 문서: {len(seen_titles)}개 / 총 {len(results)}개")
