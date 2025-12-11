#!/usr/bin/env python3
"""
100개 쿼리 세트 준비

기존 쿼리들을 합쳐서 100개를 선택합니다.
- 다양성 확보
- 중복 제거
- 중요도 순 정렬
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

def load_queries():
    """모든 쿼리 로드"""
    all_queries = []
    
    # Dev 쿼리 (69개)
    dev_path = DATA_DIR / "queries_dev.txt"
    with dev_path.open('r', encoding='utf-8') as f:
        dev_queries = [line.strip() for line in f if line.strip()]
    
    # Test 쿼리 (30개)
    test_path = DATA_DIR / "queries_test.txt"
    with test_path.open('r', encoding='utf-8') as f:
        test_queries = [line.strip() for line in f if line.strip()]
    
    # Manual 쿼리 (30개)
    manual_path = DATA_DIR / "queries_manual.txt"
    with manual_path.open('r', encoding='utf-8') as f:
        manual_queries = [line.strip() for line in f if line.strip()]
    
    print(f"📊 쿼리 로드:")
    print(f"   Dev: {len(dev_queries)}개")
    print(f"   Test: {len(test_queries)}개")
    print(f"   Manual: {len(manual_queries)}개")
    
    # 중복 제거하면서 합치기 (순서 유지)
    seen = set()
    for query in manual_queries + dev_queries + test_queries:
        if query not in seen:
            all_queries.append(query)
            seen.add(query)
    
    print(f"\n   중복 제거 후: {len(all_queries)}개")
    
    return all_queries

def select_100_queries(queries):
    """100개 선택"""
    if len(queries) <= 100:
        return queries
    
    # 처음 100개 선택 (Manual → Dev → Test 순서)
    return queries[:100]

def save_queries(queries, filename="queries_100.txt"):
    """100개 쿼리 저장"""
    output_path = DATA_DIR / filename
    
    with output_path.open('w', encoding='utf-8') as f:
        for query in queries:
            f.write(query + '\n')
    
    print(f"\n💾 저장 완료: {output_path}")
    print(f"   쿼리 개수: {len(queries)}개")
    
    # 샘플 출력
    print(f"\n📋 첫 10개 쿼리:")
    for i, query in enumerate(queries[:10], 1):
        print(f"   {i}. {query}")

def main():
    print("=" * 80)
    print("📝 100개 쿼리 세트 준비")
    print("=" * 80)
    
    # 1. 모든 쿼리 로드
    all_queries = load_queries()
    
    # 2. 100개 선택
    selected = select_100_queries(all_queries)
    
    print(f"\n✅ 선택 완료: {len(selected)}개")
    
    # 3. 저장
    save_queries(selected)
    
    print("\n" + "=" * 80)
    print("🎯 다음 단계:")
    print("   python scripts/manual_ground_truth_verification.py --queries data/queries_100.txt")
    print("=" * 80)

if __name__ == "__main__":
    main()
