#!/usr/bin/env python3
"""
시간/연도 민감 쿼리 개선

"통학버스 출발시간" → "2024년 2학기 통학버스 출발시간"
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

# 개선 규칙
IMPROVEMENTS = {
    # 통학버스
    "통학버스는 몇 시에 출발하나요?": "2024년 2학기 통학버스는 몇 시에 출발하나요?",
    "학교 셔틀버스 노선 정보 주세요": "2024년 2학기 학교 셔틀버스 노선 정보 주세요",
    "통학버스 운행 시간 알려주세요": "2024년 2학기 통학버스 운행 시간 알려주세요",
    "대구 통학버스 노선 알려주세요": "2024년 2학기 대구 통학버스 노선 알려주세요",
    
    # 기숙사 메뉴
    "오늘 기숙사 저녁 메뉴는?": "이번 주 기숙사 저녁 메뉴는?",
    "오름관 식단 알려주세요": "이번 주 오름관 식단 알려주세요",
    "오름관 1동 식당 메뉴는?": "이번 주 오름관 1동 식당 메뉴는?",
    
    # 학사 일정
    "이번 학기 학사 일정 알려주세요": "2024년 2학기 학사 일정 알려주세요",
    "학사일정 알려주세요": "2024년 2학기 학사일정 알려주세요",
    "축제는 언제 하나요?": "2024년 학교 축제는 언제 하나요?",
    
    # 수강 관련
    "계절학기 수강 가능한가요?": "2024년 겨울 계절학기 수강 가능한가요?",
    "여름방학 때 수업 들을 수 있어요?": "2024년 여름방학 때 수업 들을 수 있어요?",
    
    # 일반적 → 구체적
    "수강신청은 몇 학점까지 들을 수 있어요?": "한 학기에 수강신청은 최대 몇 학점까지 가능한가요?",
    "생활관 식사 시간이 궁금해요": "생활관 식당 운영시간과 식사 시간이 궁금해요",
    "장학금은 어떤 종류가 있나요?": "2024년 장학금은 어떤 종류가 있나요?",
}

def improve_queries():
    """쿼리 개선"""
    # 원본 로드
    input_path = DATA_DIR / "queries_100.txt"
    with input_path.open('r', encoding='utf-8') as f:
        queries = [line.strip() for line in f if line.strip()]
    
    print(f"📝 원본 쿼리: {len(queries)}개")
    
    # 개선
    improved_queries = []
    improved_count = 0
    
    for query in queries:
        if query in IMPROVEMENTS:
            improved_queries.append(IMPROVEMENTS[query])
            improved_count += 1
            print(f"\n✏️  개선:")
            print(f"   이전: {query}")
            print(f"   이후: {IMPROVEMENTS[query]}")
        else:
            improved_queries.append(query)
    
    print(f"\n\n📊 결과:")
    print(f"   전체: {len(queries)}개")
    print(f"   개선: {improved_count}개")
    print(f"   유지: {len(queries) - improved_count}개")
    
    # 저장
    output_path = DATA_DIR / "queries_100_improved.txt"
    with output_path.open('w', encoding='utf-8') as f:
        for query in improved_queries:
            f.write(query + '\n')
    
    print(f"\n💾 저장: {output_path}")
    
    # 사용자 확인
    print("\n" + "=" * 80)
    print("🤔 이 개선된 쿼리를 사용하시겠어요?")
    print("=" * 80)
    print("\n옵션:")
    print("1. 예 → queries_100.txt를 덮어쓰기")
    print("2. 아니오 → queries_100_improved.txt로 별도 저장 (현재 상태)")
    
    choice = input("\n선택 (1-2): ").strip()
    
    if choice == '1':
        # 백업
        backup_path = DATA_DIR / "queries_100_original.txt"
        import shutil
        shutil.copy(input_path, backup_path)
        print(f"\n💾 원본 백업: {backup_path}")
        
        # 덮어쓰기
        shutil.copy(output_path, input_path)
        print(f"✅ queries_100.txt 업데이트 완료!")
    else:
        print(f"\n✅ queries_100_improved.txt로 저장됨")
        print(f"   원본 queries_100.txt는 그대로 유지")

if __name__ == "__main__":
    improve_queries()
