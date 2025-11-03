import os, uuid
from qdrant_client import QdrantClient
from qdrant_client.http.models import VectorParams, Distance, PointStruct

URL = os.getenv("QDRANT_URL","http://localhost:6333")
c = QdrantClient(url=URL, timeout=60)

COL = "kit_docs"
dims = 4
# 컬렉션 보장
try:
    c.get_collection(COL)
except:
    c.recreate_collection(COL, vectors_config=VectorParams(size=dims, distance=Distance.COSINE))

# 더미 포인트 업서트
pts = [
    PointStruct(id=str(uuid.uuid4()), vector=[1,0,0,0], payload={"text":"생활관 비용 납부 안내"}),
    PointStruct(id=str(uuid.uuid4()), vector=[0,1,0,0], payload={"text":"합격 여부 조회 방법"}),
]
c.upsert(COL, points=pts)

# 간단 검색 (벡터 직접)
res = c.search(collection_name=COL, query_vector=[1,0,0,0], limit=2)
print("OK:", [(r.score, r.payload) for r in res])
