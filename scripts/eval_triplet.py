import argparse
import numpy as np
import pandas as pd
from pathlib import Path
from qdrant_client import QdrantClient
from embed_providers import get_encoder, DEFAULTS

PROJECT_ROOT = Path(__file__).resolve().parents[1]

def compute_similarity(query_embed, corpus_embeds):
    if len(corpus_embeds) == 0:
        return np.array([])
        
    # 벡터들이 정규화되어 있지 않다고 가정하고 정규화 수행
    query_norm = np.linalg.norm(query_embed)
    corpus_norms = np.linalg.norm(corpus_embeds, axis=1)
    
    # 0으로 나누는 것을 방지
    query_norm = np.maximum(query_norm, 1e-8)
    corpus_norms = np.maximum(corpus_norms, 1e-8)
    
    # 정규화된 벡터로 코사인 유사도 계산
    similarities = np.dot(query_embed, corpus_embeds.T) / (query_norm * corpus_norms)
    return similarities

def evaluate_model(model_name, ground_truth_df, collection_override=None):
    # 임베딩 모델 준비
    encoder = get_encoder(model_name)
    embedder_name = DEFAULTS[model_name]
    
    # 쿼리 임베딩
    queries = ground_truth_df['query'].tolist()
    query_embeds = np.array(encoder(queries, embedder_name)[0])
    print(f"Query embeds shape: {query_embeds.shape}")
    
    # 정답 문서 ID
    correct_ids = ground_truth_df['chunk_id'].tolist()
    
    # Qdrant에서 전체 문서 임베딩 가져오기
    client = QdrantClient("localhost", port=6333)
    collection_name = collection_override or f"kit_corpus_{model_name}_v2"
    print(f"Searching in collection: {collection_name}")
    
    try:
        # 컬렉션 정보 확인
        collection_info = client.get_collection(collection_name)
        print(f"Collection info: {collection_info}")
    except Exception as e:
        print(f"Error getting collection info: {e}")
        return None
    
    # 전체 포인트 검색
    all_points = []
    offset = None
    try:
        while True:
            batch = client.scroll(
                collection_name=collection_name,
                limit=100,
                offset=offset,
                with_vectors=True,  # 벡터 데이터 포함
                with_payload=True   # payload 데이터 포함
            )
            points, offset = batch
            print(f"Retrieved {len(points)} points")
            if points:
                print(f"First point example - id: {points[0].id}, payload: {points[0].payload}")
            all_points.extend(points)
            if offset is None:
                break
    except Exception as e:
        print(f"Error during scroll: {e}")
        return None
            
    corpus_ids = []
    corpus_embeds = []
    id_to_chunk_id = {}  # UUID to chunk_id mapping
    
    for point in all_points:
        try:
            # 벡터가 리스트나 numpy 배열인지 확인
            vector = np.array(point.vector)
            if len(vector.shape) == 1:  # 1차원 벡터인 경우만 추가
                corpus_ids.append(str(point.id))
                corpus_embeds.append(vector)
                # payload에서 original_chunk_id 또는 chunk_id 저장
                if point.payload:
                    # original_chunk_id가 있으면 우선 사용, 없으면 chunk_id 사용
                    chunk_id = point.payload.get('original_chunk_id') or point.payload.get('chunk_id')
                    if chunk_id:
                        id_to_chunk_id[str(point.id)] = chunk_id
        except:
            continue
            
    corpus_embeds = np.array(corpus_embeds)
    print(f"Corpus embeds shape: {corpus_embeds.shape}")
    print(f"Found {len(id_to_chunk_id)} chunk_id mappings")
    
    # 정확도 계산
    top1_correct = 0
    top5_correct = 0
    mrr_sum = 0
    
    for i, query_embed in enumerate(query_embeds):
        # 유사도 계산
        similarities = compute_similarity(query_embed, corpus_embeds)
        
        # 상위 K개 결과
        top_k = 5
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        # Top-1, Top-5 정확도
        correct_id = correct_ids[i]
        
        # 중복 제거된 예측 결과 생성
        seen_chunk_ids = set()
        pred_ids = []
        for idx in top_indices:
            chunk_id = id_to_chunk_id.get(corpus_ids[idx], "")
            if chunk_id not in seen_chunk_ids:
                seen_chunk_ids.add(chunk_id)
                pred_ids.append(chunk_id)
            if len(pred_ids) >= 5:  # 최대 5개까지만
                break
                
        if pred_ids[0] == correct_id:
            top1_correct += 1
            top5_correct += 1
        elif correct_id in pred_ids:
            top5_correct += 1
            
        # 모든 쿼리에 대한 결과 출력
        print(f"\nQuery {i+1}: {queries[i]}")
        print(f"Expected: {correct_id}")
        print(f"Top 5 predictions: {pred_ids}")
        
        # 정답이 있는 경우 순위 표시
        if correct_id in pred_ids:
            rank = pred_ids.index(correct_id) + 1
            print(f"✅ Found at rank {rank}")
        else:
            print("❌ Not found in top 5")
            
        # MRR 계산
        try:
            rank = pred_ids.index(correct_id) + 1
            mrr_sum += 1/rank
        except ValueError:
            pass
            
    num_queries = len(queries)
    results = {
        'model': model_name,
        'top1_accuracy': top1_correct / num_queries,
        'top5_accuracy': top5_correct / num_queries,
        'mrr': mrr_sum / num_queries
    }
    
    return results

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', required=True, choices=['bge', 'e5', 'openai', 'upstage', 'kosimcse', 'krsbert'])
    parser.add_argument('--input', default=str(PROJECT_ROOT/'data'/'ground_truth.csv'))
    parser.add_argument('--collection', default=None, help='Collection name override (default: kit_corpus_{model}_v2)')
    args = parser.parse_args()
    
    # 데이터 로드
    ground_truth_df = pd.read_csv(args.input)
    
    # 평가
    results = evaluate_model(args.model, ground_truth_df, args.collection)
    
    # 결과 출력
    print(f"\n평가 결과 - {results['model']} 모델")
    print(f"Top-1 Accuracy: {results['top1_accuracy']:.4f}")
    print(f"Top-5 Accuracy: {results['top5_accuracy']:.4f}")
    print(f"MRR: {results['mrr']:.4f}")

if __name__ == "__main__":
    main()
