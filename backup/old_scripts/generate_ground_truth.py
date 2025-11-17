#!/usr/bin/env python3
"""
쿼리별로 가장 관련성 높은 문서를 찾아서 ground_truth 생성
"""
import pandas as pd
from pathlib import Path
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

# 설정
QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "kit_corpus_bge_all"
RETRIEVER_MODEL = "BAAI/bge-m3"

def generate_ground_truth(queries_file, output_file):
    """
    각 쿼리에 대해 Top-1 문서를 찾아서 ground_truth 생성
    """
    print(f"\n📂 입력: {queries_file}")
    
    # 1. 쿼리 로드
    with open(queries_file, 'r', encoding='utf-8') as f:
        queries = [line.strip() for line in f if line.strip()]
    
    print(f"   질문 수: {len(queries)}개")
    
    # 2. Retriever 로드
    print(f"\n🤖 Retriever 로드: {RETRIEVER_MODEL}")
    retriever = SentenceTransformer(RETRIEVER_MODEL)
    
    # 3. Qdrant 연결
    print(f"\n🔌 Qdrant 연결: {QDRANT_URL}")
    client = QdrantClient(url=QDRANT_URL)
    
    # 4. 각 쿼리에 대해 검색
    results = []
    
    print(f"\n🔍 검색 중...")
    for query in tqdm(queries, desc="Ground Truth 생성"):
        # 쿼리 임베딩
        query_vector = retriever.encode(query, normalize_embeddings=True).tolist()
        
        # Top-1 검색
        search_result = client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=1
        ).points
        
        if search_result:
            hit = search_result[0]
            document_name = hit.payload.get('document_name', '')
            url = hit.payload.get('url', '')
            title = hit.payload.get('title', '')
            score = hit.score
            
            results.append({
                'query': query,
                'document_name': document_name,
                'url': url,
                'title': title,
                'score': score
            })
        else:
            results.append({
                'query': query,
                'document_name': '',
                'url': '',
                'title': '',
                'score': 0.0
            })
    
    # 5. CSV 저장
    df = pd.DataFrame(results)
    df.to_csv(output_file, index=False, encoding='utf-8')
    
    print(f"\n✅ 저장 완료: {output_file}")
    print(f"   생성된 레코드: {len(df)}개")
    print(f"   평균 유사도: {df['score'].mean():.3f}")
    
    # 샘플 출력
    print(f"\n📝 샘플 (처음 5개):")
    for idx, row in df.head(5).iterrows():
        print(f"\n  [{idx+1}] 질문: {row['query']}")
        print(f"      문서: {row['document_name']}")
        print(f"      제목: {row['title'][:50]}...")
        print(f"      유사도: {row['score']:.3f}")

def main():
    print("=" * 80)
    print("📊 Ground Truth 자동 생성")
    print("=" * 80)
    
    # Dev set
    generate_ground_truth(
        DATA_DIR / "queries_dev.txt",
        DATA_DIR / "ground_truth_dev.csv"
    )
    
    print("\n" + "=" * 80)
    
    # Test set
    generate_ground_truth(
        DATA_DIR / "queries_test.txt",
        DATA_DIR / "ground_truth_test.csv"
    )
    
    print("\n" + "=" * 80)
    print("✅ 전체 완료!")
    print("=" * 80)
    print("  - data/ground_truth_dev.csv (70개)")
    print("  - data/ground_truth_test.csv (31개)")
    print("=" * 80)

if __name__ == "__main__":
    main()
