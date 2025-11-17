#!/usr/bin/env python3
"""
수동 Ground Truth 검증 도구
- 쿼리별로 Top-5 검색 결과 보여주기
- 사람이 직접 정답 선택
- 수동 검증된 ground truth 생성
"""

import csv
import sys
from pathlib import Path
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
import warnings
warnings.filterwarnings('ignore')

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

COLLECTION_NAME = "kit_corpus_bge_all"
QDRANT_URL = "http://localhost:6333"

def show_search_results(query, client, model, top_k=5):
    """쿼리에 대한 검색 결과 보여주기"""
    print("\n" + "=" * 80)
    print(f"🔍 쿼리: {query}")
    print("=" * 80)
    
    # 검색
    query_vector = model.encode(query, normalize_embeddings=True).tolist()
    results = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        limit=top_k
    )
    
    # 결과 출력
    for i, hit in enumerate(results, 1):
        score = hit.score
        text = hit.payload.get('text', '')[:300]
        title = hit.payload.get('title', 'N/A')
        url = hit.payload.get('url', '')
        source_type = hit.payload.get('source_type', 'N/A')
        
        print(f"\n[{i}] 스코어: {score:.4f}")
        print(f"    제목: {title}")
        print(f"    출처: {source_type}")
        if url:
            print(f"    URL: {url[:80]}")
        print(f"    내용: {text}...")
        print("-" * 80)
    
    return results

def manual_verification(queries_file, output_file):
    """수동 검증 프로세스"""
    
    print("=" * 80)
    print("🔍 수동 Ground Truth 검증")
    print("=" * 80)
    
    print(f"\n📂 쿼리 파일: {queries_file}")
    print(f"💾 출력 파일: {output_file}")
    
    # 쿼리 로드
    with queries_file.open('r', encoding='utf-8') as f:
        queries = [line.strip() for line in f if line.strip()]
    
    print(f"\n📊 총 {len(queries)}개 쿼리")
    
    # 기존 검증 결과 로드 (중단 후 재시작 가능)
    verified = {}
    if output_file.exists():
        print(f"\n⚠️  기존 검증 파일 발견: {output_file}")
        response = input("기존 결과를 이어서 진행할까요? (y/n): ").strip().lower()
        
        if response == 'y':
            with output_file.open('r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    verified[row['query']] = {
                        'document_name': row['document_name'],
                        'rank': int(row['rank']),
                        'similarity': float(row['similarity'])
                    }
            print(f"✅ {len(verified)}개 이미 검증됨")
    
    # Qdrant & 모델
    print(f"\n🔌 Qdrant 연결 중...")
    client = QdrantClient(QDRANT_URL)
    
    print(f"🤖 BGE-M3 모델 로드 중...")
    model = SentenceTransformer('BAAI/bge-m3')
    
    # 검증 시작
    print("\n" + "=" * 80)
    print("✅ 준비 완료! 검증을 시작합니다.")
    print("=" * 80)
    print("\n📝 사용법:")
    print("   - 정답 번호 입력 (1-5)")
    print("   - 'n' 입력: 정답 없음 (모두 관련 없음)")
    print("   - 's' 입력: 건너뛰기")
    print("   - 'q' 입력: 종료 (진행상황 저장)")
    
    results = []
    
    for i, query in enumerate(queries, 1):
        # 이미 검증된 쿼리 건너뛰기
        if query in verified:
            results.append({
                'query': query,
                'document_name': verified[query]['document_name'],
                'rank': verified[query]['rank'],
                'similarity': verified[query]['similarity']
            })
            continue
        
        print(f"\n\n{'='*80}")
        print(f"진행: {i}/{len(queries)} ({i/len(queries)*100:.1f}%)")
        
        # 검색 결과 보여주기
        search_results = show_search_results(query, client, model, top_k=5)
        
        # 사용자 입력
        while True:
            user_input = input(f"\n정답 선택 (1-5, n=없음, s=건너뛰기, q=종료): ").strip().lower()
            
            if user_input == 'q':
                print("\n💾 진행상황을 저장하고 종료합니다...")
                save_results(results, output_file)
                return len(results)
            
            elif user_input == 's':
                print("⏭️  건너뜀")
                break
            
            elif user_input == 'n':
                print("❌ 정답 없음으로 기록")
                results.append({
                    'query': query,
                    'document_name': 'NO_ANSWER',
                    'rank': -1,
                    'similarity': 0.0
                })
                break
            
            elif user_input.isdigit():
                rank = int(user_input)
                if 1 <= rank <= 5:
                    selected = search_results[rank - 1]
                    title = selected.payload.get('title', 'N/A')
                    score = selected.score
                    
                    print(f"✅ {rank}번 선택: {title} (스코어: {score:.4f})")
                    
                    results.append({
                        'query': query,
                        'document_name': title,
                        'rank': rank,
                        'similarity': score
                    })
                    break
                else:
                    print("❌ 1-5 사이의 숫자를 입력하세요")
            else:
                print("❌ 잘못된 입력입니다")
        
        # 10개마다 자동 저장
        if len(results) % 10 == 0:
            save_results(results, output_file)
            print(f"\n💾 자동 저장됨 ({len(results)}개)")
    
    # 최종 저장
    save_results(results, output_file)
    
    print("\n" + "=" * 80)
    print("🎉 검증 완료!")
    print("=" * 80)
    print(f"\n📊 통계:")
    print(f"   총 쿼리: {len(queries)}개")
    print(f"   검증됨: {len(results)}개")
    print(f"   건너뜀: {len(queries) - len(results)}개")
    
    # 정답 분포
    if results:
        rank_dist = {}
        for r in results:
            rank = r['rank']
            rank_dist[rank] = rank_dist.get(rank, 0) + 1
        
        print(f"\n📈 정답 순위 분포:")
        for rank in sorted(rank_dist.keys()):
            count = rank_dist[rank]
            pct = count / len(results) * 100
            if rank == -1:
                print(f"   정답 없음: {count}개 ({pct:.1f}%)")
            else:
                print(f"   {rank}위: {count}개 ({pct:.1f}%)")
    
    return len(results)

def save_results(results, output_file):
    """결과 저장"""
    if not results:
        return
    
    with output_file.open('w', encoding='utf-8', newline='') as f:
        fieldnames = ['query', 'document_name', 'rank', 'similarity']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

def main():
    print("\n" + "=" * 80)
    print("🔍 수동 Ground Truth 검증 도구")
    print("=" * 80)
    
    # 검증할 파일 선택
    print("\n어떤 쿼리 세트를 검증할까요?")
    print("1. 100개 쿼리 세트 (추천!) ⭐")
    print("2. Dev Set (70개)")
    print("3. Test Set (31개)")
    print("4. Manual Set (30개)")
    print("5. 커스텀 파일")
    
    choice = input("\n선택 (1-5): ").strip()
    
    if choice == '1':
        queries_file = DATA_DIR / "queries_100.txt"
        output_file = DATA_DIR / "ground_truth_100.csv"
    elif choice == '2':
        queries_file = DATA_DIR / "queries_dev.txt"
        output_file = DATA_DIR / "ground_truth_dev_manual.csv"
    elif choice == '3':
        queries_file = DATA_DIR / "queries_test.txt"
        output_file = DATA_DIR / "ground_truth_test_manual.csv"
    elif choice == '4':
        queries_file = DATA_DIR / "queries_manual.txt"
        output_file = DATA_DIR / "ground_truth_manual_verified.csv"
    elif choice == '5':
        queries_file = Path(input("쿼리 파일 경로: ").strip())
        output_file = Path(input("출력 파일 경로: ").strip())
    else:
        print("❌ 잘못된 선택")
        return
    
    if not queries_file.exists():
        print(f"❌ 파일이 없습니다: {queries_file}")
        return
    
    # 검증 시작
    verified_count = manual_verification(queries_file, output_file)
    
    print(f"\n✅ {verified_count}개 쿼리 검증 완료!")
    print(f"💾 저장됨: {output_file}")

if __name__ == "__main__":
    main()
