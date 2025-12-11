#!/usr/bin/env python3
"""
Ground Truth 편향 검증

질문: GT가 BGE-M3에 편향되어 있는가?
방법: 각 GT 항목을 선택한 모델이 무엇인지 확인
"""

import pandas as pd
from pathlib import Path
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
import warnings
warnings.filterwarnings('ignore')

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

# 테스트할 모델들
MODELS = {
    'BGE-M3': 'BAAI/bge-m3',
    'E5-Base': 'intfloat/multilingual-e5-base',
    'KR-SBERT': 'jhgan/ko-sroberta-multitask',
    'KoSimCSE': 'BM-K/KoSimCSE-roberta',
}

def load_gt():
    """Ground Truth 로드"""
    gt_path = DATA_DIR / "ground_truth_100.csv"
    gt_df = pd.read_csv(gt_path)
    # rank > 0인 것만
    return gt_df[gt_df['rank'] > 0].copy()

def search_with_model(model_name, model, client, query, collection_name, top_k=10):
    """특정 모델로 검색"""
    # E5는 쿼리 prefix 필요
    if 'e5' in model_name.lower():
        query_text = f"query: {query}"
    else:
        query_text = query
    
    query_vector = model.encode(query_text, normalize_embeddings=True).tolist()
    
    results = client.search(
        collection_name=collection_name,
        query_vector=query_vector,
        limit=top_k
    )
    
    return results

def get_doc_titles(results):
    """검색 결과에서 문서 제목 추출"""
    titles = []
    for hit in results:
        # document_name 또는 title
        doc_name = hit.payload.get('document_name', '')
        if not doc_name:
            doc_name = hit.payload.get('title', '')
        
        # chunk 제거
        if '_chunk' in doc_name:
            doc_name = doc_name.rsplit('_chunk', 1)[0]
        
        # 확장자 제거
        doc_name = doc_name.replace('.pdf', '').replace('.xlsx', '').replace('.docx', '').strip()
        
        titles.append(doc_name)
    
    return titles

def check_gt_in_topk(gt_doc, search_results, k=5):
    """GT 문서가 Top-K에 있는지 확인"""
    titles = get_doc_titles(search_results)
    
    # GT 문서명 정규화
    gt_normalized = gt_doc.replace('.pdf', '').replace('.xlsx', '').replace('.docx', '').strip()
    
    # Top-K 확인
    for i, title in enumerate(titles[:k], 1):
        if gt_normalized == title or gt_normalized in title or title in gt_normalized:
            return True, i
    
    return False, -1

def main():
    print("=" * 80)
    print("🔬 Ground Truth 편향 검증")
    print("=" * 80)
    print("\n질문: GT가 BGE-M3에 편향되어 있는가?")
    print("방법: 각 모델이 GT 문서를 Top-5에 찾는지 확인\n")
    
    # GT 로드
    gt_df = load_gt()
    print(f"📋 Ground Truth: {len(gt_df)}개")
    
    # Qdrant 클라이언트
    client = QdrantClient(url="http://localhost:6333")
    
    # 모델별 컬렉션
    collections = {
        'BGE-M3': 'kit_corpus_bge_all',
        'E5-Base': 'kit_corpus_e5_base',
        'KR-SBERT': 'kit_corpus_kr_sbert',
        'KoSimCSE': 'kit_corpus_kosimcse',
    }
    
    # 결과 저장
    results = {model: {'found': 0, 'total': 0, 'ranks': []} for model in MODELS}
    
    print("\n🔍 모델 로드 중...")
    models = {}
    for name, path in MODELS.items():
        print(f"   {name}...", end='', flush=True)
        models[name] = SentenceTransformer(path)
        print(" ✅")
    
    print("\n📊 평가 진행 중...\n")
    
    # 각 GT 항목 평가
    for idx, row in gt_df.iterrows():
        query = row['query']
        gt_doc = row['document_name']
        
        if idx % 10 == 0:
            print(f"   진행: {idx}/{len(gt_df)}...")
        
        # 각 모델로 검색
        for model_name in MODELS:
            collection = collections[model_name]
            model = models[model_name]
            
            # 검색
            search_results = search_with_model(model_name, model, client, query, collection, top_k=10)
            
            # GT 문서가 Top-5에 있는지 확인
            found, rank = check_gt_in_topk(gt_doc, search_results, k=5)
            
            results[model_name]['total'] += 1
            if found:
                results[model_name]['found'] += 1
                results[model_name]['ranks'].append(rank)
    
    # 결과 출력
    print("\n" + "=" * 80)
    print("📊 결과")
    print("=" * 80)
    
    print("\n각 모델이 GT 문서를 Top-5에서 찾은 비율:\n")
    
    for model_name in MODELS:
        found = results[model_name]['found']
        total = results[model_name]['total']
        recall = found / total if total > 0 else 0
        
        print(f"{model_name:12} {recall:6.1%}  ({found}/{total})")
        
        if len(results[model_name]['ranks']) > 0:
            avg_rank = sum(results[model_name]['ranks']) / len(results[model_name]['ranks'])
            print(f"             평균 순위: {avg_rank:.1f}")
        print()
    
    # 분석
    print("=" * 80)
    print("📈 분석")
    print("=" * 80)
    
    bge_recall = results['BGE-M3']['found'] / results['BGE-M3']['total']
    
    print(f"\n1. BGE-M3 Recall@5: {bge_recall:.1%}")
    print(f"   → GT 선택 시 BGE-M3 검색 결과를 보고 선택했으므로")
    print(f"   → 높은 Recall은 예상된 결과 ✅")
    
    print(f"\n2. 다른 모델들:")
    for model_name in ['E5-Base', 'KR-SBERT', 'KoSimCSE']:
        recall = results[model_name]['found'] / results[model_name]['total']
        print(f"   {model_name}: {recall:.1%}")
    
    print(f"\n3. 편향 여부:")
    other_recalls = [results[m]['found'] / results[m]['total'] for m in ['E5-Base', 'KR-SBERT', 'KoSimCSE']]
    avg_other = sum(other_recalls) / len(other_recalls)
    
    bias = bge_recall - avg_other
    
    if bias > 0.3:  # 30% 이상 차이
        print(f"   ⚠️  심각한 편향 의심!")
        print(f"   BGE-M3: {bge_recall:.1%} vs 다른 모델 평균: {avg_other:.1%}")
        print(f"   차이: {bias:.1%}")
        print(f"\n   → GT가 BGE-M3 검색 결과에 편향되어 있을 가능성 높음")
        print(f"   → 공정한 평가를 위해 모델 중립적인 GT 필요")
    elif bias > 0.1:  # 10% 이상
        print(f"   ⚠️  약간의 편향 존재")
        print(f"   BGE-M3: {bge_recall:.1%} vs 다른 모델 평균: {avg_other:.1%}")
        print(f"   차이: {bias:.1%}")
    else:
        print(f"   ✅ 편향 없음 또는 미미")
        print(f"   BGE-M3: {bge_recall:.1%} vs 다른 모델 평균: {avg_other:.1%}")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    main()
