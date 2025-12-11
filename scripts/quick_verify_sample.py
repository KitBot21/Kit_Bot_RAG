#!/usr/bin/env python3
"""
빠른 샘플 검증 (5개 쿼리만)
수동 검증이 어떻게 작동하는지 테스트
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
import warnings
warnings.filterwarnings('ignore')

COLLECTION_NAME = "kit_corpus_bge_all"

def quick_verify():
    """5개 샘플 쿼리로 빠른 검증"""
    
    # 테스트 쿼리 (더 구체적으로)
    sample_queries = [
        "2024년 2학기 통학버스 운행 노선표가 필요해요",
        "이번 주 학생식당 중식 메뉴 알려주세요",
        "중소기업 취업연계 장학금 신청 방법을 알고 싶어요",
        "아름책마루 목요일 연장 운영시간이 어떻게 되나요",
        "생활관 입사 신청 기간과 절차를 알려주세요"
    ]
    
    print("=" * 80)
    print("🔍 빠른 검증 테스트 (5개 쿼리)")
    print("=" * 80)
    
    # 연결
    print("\n🔌 Qdrant 연결 중...")
    client = QdrantClient("http://localhost:6333")
    
    print("🤖 BGE-M3 모델 로드 중...")
    model = SentenceTransformer('BAAI/bge-m3')
    
    print("\n" + "=" * 80)
    print("사용법:")
    print("  - 각 쿼리에 대해 Top-3 결과를 보여줍니다")
    print("  - 정답이라고 생각하는 번호를 입력하세요 (1-3)")
    print("  - 'n' = 정답 없음, 's' = 건너뛰기")
    print("=" * 80)
    
    results = []
    
    for i, query in enumerate(sample_queries, 1):
        print(f"\n\n{'='*80}")
        print(f"[{i}/5] 쿼리: {query}")
        print("=" * 80)
        
        # 검색
        query_vector = model.encode(query, normalize_embeddings=True).tolist()
        search_results = client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            limit=3
        )
        
        # 결과 출력
        for j, hit in enumerate(search_results, 1):
            score = hit.score
            text = hit.payload.get('text', '')[:200]
            title = hit.payload.get('title', 'N/A')
            
            print(f"\n[{j}] 스코어: {score:.4f}")
            print(f"    제목: {title}")
            print(f"    내용: {text}...")
            print("-" * 80)
        
        # 사용자 입력
        while True:
            answer = input(f"\n정답 선택 (1-3, n=없음, s=건너뛰기): ").strip().lower()
            
            if answer == 's':
                print("⏭️  건너뜀")
                break
            elif answer == 'n':
                print("❌ 정답 없음")
                results.append((query, "NO_ANSWER", 0))
                break
            elif answer.isdigit() and 1 <= int(answer) <= 3:
                rank = int(answer)
                title = search_results[rank-1].payload.get('title', 'N/A')
                print(f"✅ {rank}번 선택: {title}")
                results.append((query, title, rank))
                break
            else:
                print("❌ 1-3, n, s 중 하나를 입력하세요")
    
    # 결과 요약
    print("\n\n" + "=" * 80)
    print("📊 검증 결과")
    print("=" * 80)
    
    if results:
        for query, doc, rank in results:
            if doc == "NO_ANSWER":
                print(f"\n❌ {query}")
                print(f"   → 정답 없음")
            else:
                print(f"\n✅ {query}")
                print(f"   → {rank}위: {doc}")
        
        # 통계
        print("\n" + "=" * 80)
        answered = [r for r in results if r[1] != "NO_ANSWER"]
        if answered:
            avg_rank = sum(r[2] for r in answered) / len(answered)
            rank1 = sum(1 for r in answered if r[2] == 1)
            
            print(f"검증된 쿼리: {len(results)}개")
            print(f"정답 있음: {len(answered)}개")
            print(f"정답 없음: {len(results) - len(answered)}개")
            print(f"1위 정답률: {rank1/len(answered)*100:.1f}%")
            print(f"평균 순위: {avg_rank:.2f}")
    
    print("\n💡 실제 검증은 다음 명령어로 실행:")
    print("   python scripts/manual_ground_truth_verification.py")
    print("=" * 80)

if __name__ == "__main__":
    quick_verify()
