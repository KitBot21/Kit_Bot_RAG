"""
필터링된 corpus에서 불필요한 텍스트 제거
"""
import pandas as pd
import re

def clean_text(text):
    """텍스트에서 불필요한 요소 제거"""
    if pd.isna(text):
        return text
    
    # 제거할 패턴들
    patterns_to_remove = [
        r'Fetched at:.*?\n',  # Fetched at 시간 정보
        r'본문 바로가기\s*',
        r'Snapshot of\s*https?://[^\s]+',
        r'HOME\s*',
        r'공지사항\s*공지사항\s*공지사항',  # 중복된 "공지사항"
        r'다음페이지\s*',
        r'이전페이지\s*',
        r'첫페이지\s*',
        r'마지막페이지\s*',
        r'페이지\s*이동\s*',
        r'\[이전글\].*?\n',
        r'\[다음글\].*?\n',
        r'목록\s*수정\s*삭제\s*',
        r'조회\s*\d+\s*날짜\s*\d{4}-\d{2}-\d{2}',  # 조회수와 날짜가 붙어있는 패턴
        r'작성자\s*\S+\s*조회\s*\d+',  # 작성자 조회수
        r'파일첨부\s*',
        r'인쇄하기\s*',
        r'페이스북\s*',
        r'트위터\s*',
        r'카카오스토리\s*',
        r'네이버밴드\s*',
        r'URL\s*복사\s*',
        # 네비게이션 메뉴
        r'QUICK\s+MENU\s*',
        r'SITEMAP\s*',
        r'TOP\s*▲\s*',
        # 반복되는 헤더/푸터
        r'더 높은 곳을 향해 도약하는 금오공과대학교.*?!',
        r'대한민국을 이끌어 나갈 우수한 인재가 기지개를 켜는 곳\s*!',
    ]
    
    cleaned = text
    for pattern in patterns_to_remove:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE | re.MULTILINE)
    
    # 연속된 공백을 하나로
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    cleaned = re.sub(r' {2,}', ' ', cleaned)
    
    # 앞뒤 공백 제거
    cleaned = cleaned.strip()
    
    return cleaned

def main():
    print("=== Corpus 텍스트 클리닝 시작 ===")
    
    # 필터링된 corpus 로드
    corpus_path = 'data/corpus_filtered.csv'
    df = pd.read_csv(corpus_path)
    print(f"원본 청크 수: {len(df)}")
    
    # 텍스트 클리닝 전 샘플 출력
    print("\n[클리닝 전 샘플]")
    print(df.iloc[0]['text'][:300])
    print("...")
    
    # 텍스트 클리닝
    df['text'] = df['text'].apply(clean_text)
    
    # 텍스트 클리닝 후 샘플 출력
    print("\n[클리닝 후 샘플]")
    print(df.iloc[0]['text'][:300])
    print("...")
    
    # 빈 텍스트나 너무 짧은 텍스트 제거
    original_len = len(df)
    df = df[df['text'].str.len() >= 40]
    print(f"\n너무 짧은 청크 제거: {original_len} -> {len(df)} ({original_len - len(df)}개 제거)")
    
    # 저장
    df.to_csv(corpus_path, index=False)
    print(f"\n클리닝된 corpus 저장 완료: {corpus_path}")
    print(f"최종 청크 수: {len(df)}")
    
    # 통계 출력
    print(f"\n=== 텍스트 길이 통계 ===")
    print(f"평균: {df['text'].str.len().mean():.1f} 글자")
    print(f"중앙값: {df['text'].str.len().median():.1f} 글자")
    print(f"최소: {df['text'].str.len().min()} 글자")
    print(f"최대: {df['text'].str.len().max()} 글자")

if __name__ == '__main__':
    main()
