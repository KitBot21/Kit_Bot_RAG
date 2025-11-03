#!/usr/bin/env python3
"""
100개의 ground_truth.csv 및 queries.txt 생성 스크립트
기존 30개 + 새로운 70개 = 총 100개
"""
import pandas as pd
import random

# Corpus 로드
corpus = pd.read_csv('data/corpus_with_sources.csv')

# 기존 ground_truth 로드
old_gt = pd.read_csv('data/ground_truth.csv')

# 새로운 질문-답변 쌍 (70개 추가)
new_qa_pairs = [
    # === 통학버스 관련 (10개 추가) ===
    ("통학버스 운행 시간표 알려주세요", "www_kumoh_ac_kr_bus_notice_do_0001"),
    ("대구 통학버스 요금은 얼마인가요?", "www_kumoh_ac_kr_ko_sub04_02_07_01_do_0001"),
    ("통학버스 승차 위치가 어디인가요?", "www_kumoh_ac_kr_bus_notice_do_0001"),
    ("통학버스 예약 취소 방법 알려주세요", "www_kumoh_ac_kr_bus_notice_do_0002"),
    ("통학버스 노선은 어떻게 되나요?", "www_kumoh_ac_kr_bus_notice_do_0001"),
    ("방학 중 통학버스 운행하나요?", "www_kumoh_ac_kr_bus_notice_do_0001"),
    ("통학버스 QR 체크인 어떻게 하나요?", "www_kumoh_ac_kr_bus_notice_do_0002"),
    ("통학버스 예약 시스템 사용법 알려주세요", "www_kumoh_ac_kr_bus_notice_do_0002"),
    ("통학버스 미탑승 패널티는?", "www_kumoh_ac_kr_bus_notice_do_0001"),
    ("계절학기 통학버스 운행 안내", "www_kumoh_ac_kr_bus_index_jsp_0001"),
    
    # === 기숙사/생활관 관련 (20개 추가) ===
    ("푸름관 1동 시설 안내해주세요", "www_kumoh_ac_kr_dorm_sub0201_do_0001"),
    ("오름관 입사 자격이 어떻게 되나요?", "www_kumoh_ac_kr_dorm_sub0102_do_0001"),
    ("생활관 입사신청 기간은 언제예요?", "www_kumoh_ac_kr_dorm_sub0102_do_0001"),
    ("기숙사 비용은 얼마인가요?", "www_kumoh_ac_kr_dorm_sub0103_do_0001"),
    ("생활관 입사 선발 기준 알려주세요", "www_kumoh_ac_kr_dorm_sub0102_do_0001"),
    ("기숙사 환불 규정이 궁금해요", "www_kumoh_ac_kr_dorm_sub0103_do_0001"),
    ("생활관 퇴사 절차는 어떻게 되나요?", "www_kumoh_ac_kr_dorm_sub0301_do_0001"),
    ("푸름관 2동 수용인원은?", "www_kumoh_ac_kr_dorm_sub020102_do_0001"),
    ("아름관 시설 현황 알려주세요", "www_kumoh_ac_kr_dorm_sub020105_do_0001"),
    ("생활관 규칙이 뭐가 있나요?", "www_kumoh_ac_kr_dorm_sub0301_do_0001"),
    ("기숙사 인터넷 사용 가능한가요?", "www_kumoh_ac_kr_dorm_sub0201_do_0001"),
    ("생활관 세탁실 이용 방법", "www_kumoh_ac_kr_dorm_sub0201_do_0001"),
    ("오름관3동 몇 명 수용하나요?", "www_kumoh_ac_kr_dorm_sub020203_do_0001"),
    ("생활관 식비 환불 신청은 어떻게?", "www_kumoh_ac_kr_dorm_sub0303_do_0001"),
    ("기숙사 입사 지원 서류 뭐가 필요해요?", "www_kumoh_ac_kr_dorm_sub0102_do_0001"),
    ("생활관 벌점 제도 있나요?", "www_kumoh_ac_kr_dorm_sub0301_do_0001"),
    ("푸름관4동 위치가 어디예요?", "www_kumoh_ac_kr_dorm_sub020104_do_0001"),
    ("생활관 입사 경쟁률이 어떻게 되나요?", "www_kumoh_ac_kr_dorm_sub0102_do_0001"),
    ("기숙사 방학 중 거주 가능한가요?", "www_kumoh_ac_kr_dorm_sub0102_do_0001"),
    ("생활관 전화번호 알려주세요", "www_kumoh_ac_kr_dorm_index_do_0001"),
    
    # === 학사/수강 관련 (15개 추가) ===
    ("복수전공 신청 방법 알려주세요", "www_kumoh_ac_kr_ko_sub02_03_04_01_do_0001"),
    ("부전공은 어떻게 신청하나요?", "www_kumoh_ac_kr_ko_sub02_03_04_01_do_0001"),
    ("전과 제도 있나요?", "www_kumoh_ac_kr_ko_sub02_03_02_do_0001"),
    ("졸업 요건이 어떻게 되나요?", "www_kumoh_ac_kr_ko_sub02_03_04_02_do_0001"),
    ("학점 계산 방법 알려주세요", "www_kumoh_ac_kr_ko_sub02_03_05_01_do_0001"),
    ("재수강 신청은 어떻게 하나요?", "www_kumoh_ac_kr_ko_sub02_03_03_04_do_0001"),
    ("F학점 재수강 가능한가요?", "www_kumoh_ac_kr_ko_sub02_03_05_01_do_0001"),
    ("교양필수 과목은 뭐가 있나요?", "www_kumoh_ac_kr_ko_sub02_03_04_02_do_0001"),
    ("전공필수 이수학점은?", "www_kumoh_ac_kr_ko_sub02_03_04_02_do_0001"),
    ("학사경고 기준이 어떻게 되나요?", "www_kumoh_ac_kr_ko_sub02_03_05_01_do_0001"),
    ("성적 정정 신청 기간은?", "www_kumoh_ac_kr_ko_sub02_03_05_01_do_0001"),
    ("계절학기 수강 가능한가요?", "www_kumoh_ac_kr_ko_sub02_03_03_05_do_0001"),
    ("전공 인정 학점은 몇 학점인가요?", "www_kumoh_ac_kr_ko_sub02_03_04_02_do_0001"),
    ("수업 시간표는 어디서 보나요?", "www_kumoh_ac_kr_ko_sub02_03_03_04_do_0001"),
    ("강의평가 기간 언제예요?", "www_kumoh_ac_kr_ko_sub02_03_05_02_do_0001"),
    
    # === 학부/학과 소개 (10개 추가) ===
    ("전자공학부는 어떤 곳인가요?", "www_kumoh_ac_kr_ko_sub02_01_02_do_0001"),
    ("기계공학부 커리큘럼 알려주세요", "www_kumoh_ac_kr_ko_sub02_01_08_do_0001"),
    ("컴퓨터공학과 전망이 어떤가요?", "www_kumoh_ac_kr_ko_sub02_01_04_do_0001"),
    ("건축학과 5년제인가요?", "www_kumoh_ac_kr_ko_sub02_01_10_do_0001"),
    ("신소재공학부에서 뭘 배우나요?", "www_kumoh_ac_kr_ko_sub02_01_07_do_0001"),
    ("산업경영학과 취업률은?", "www_kumoh_ac_kr_ko_sub02_01_12_do_0001"),
    ("에너지공학과는 어떤 학과예요?", "www_kumoh_ac_kr_ko_sub02_01_09_do_0001"),
    ("소프트웨어학부 정원이 몇 명이에요?", "www_kumoh_ac_kr_ko_sub02_01_05_do_0001"),
    ("응용화학과에서 취득 가능한 자격증은?", "www_kumoh_ac_kr_ko_sub02_01_06_do_0001"),
    ("학과별 전화번호 알려주세요", "www_kumoh_ac_kr_ko_sub02_01_01_do_0001"),
    
    # === 학생 활동/동아리 (10개 추가) ===
    ("총학생회 연락처 알려주세요", "www_kumoh_ac_kr_ko_sub04_01_01_do_0001"),
    ("동아리는 어떤 것들이 있나요?", "www_kumoh_ac_kr_ko_sub04_01_02_do_0001"),
    ("문화예술 동아리 종류는?", "www_kumoh_ac_kr_ko_sub04_01_02_do_0001"),
    ("체육 동아리 가입하고 싶어요", "www_kumoh_ac_kr_ko_sub04_01_02_do_0001"),
    ("학술 동아리 추천해주세요", "www_kumoh_ac_kr_ko_sub04_01_02_do_0001"),
    ("학생회 선거는 언제 하나요?", "www_kumoh_ac_kr_ko_sub04_01_01_do_0001"),
    ("동아리방은 어디 있나요?", "www_kumoh_ac_kr_ko_sub04_01_02_do_0001"),
    ("학생 자치기구 종류 알려주세요", "www_kumoh_ac_kr_ko_sub04_01_01_do_0001"),
    ("축제는 언제 하나요?", "www_kumoh_ac_kr_ko_sub04_01_03_do_0001"),
    ("봉사활동 동아리 있나요?", "www_kumoh_ac_kr_ko_sub04_01_02_do_0001"),
    
    # === 장학/취업/시설 (5개 추가) ===
    ("장학금 종류 알려주세요", "www_kumoh_ac_kr_ko_sub05_01_01_do_0001"),
    ("국가장학금 신청 방법은?", "www_kumoh_ac_kr_ko_sub05_01_01_do_0001"),
    ("성적장학금 기준이 어떻게 되나요?", "www_kumoh_ac_kr_ko_sub05_01_01_do_0001"),
    ("취업률이 어떻게 되나요?", "www_kumoh_ac_kr_ko_sub06_01_01_01_do_0001"),
    ("도서관 이용 시간 알려주세요", "www_kumoh_ac_kr_ko_sub07_04_01_do_0001"),
]

# 기존 30개와 새로운 70개 결합
all_queries = []
all_chunk_ids = []

# 기존 데이터 추가
for _, row in old_gt.iterrows():
    all_queries.append(row['query'])
    all_chunk_ids.append(row['chunk_id'])

# 새로운 데이터 추가
for query, chunk_id in new_qa_pairs:
    all_queries.append(query)
    all_chunk_ids.append(chunk_id)

# DataFrame 생성
new_gt = pd.DataFrame({
    'query': all_queries,
    'chunk_id': all_chunk_ids
})

# 저장
new_gt.to_csv('data/ground_truth.csv', index=False, encoding='utf-8')
print(f"✅ ground_truth.csv 생성 완료: {len(new_gt)}개 질문")

# queries.txt 생성
with open('data/queries.txt', 'w', encoding='utf-8') as f:
    for query in all_queries:
        f.write(query + '\n')

print(f"✅ queries.txt 생성 완료: {len(all_queries)}개 질문")

# 검증
corpus = pd.read_csv('data/corpus_with_sources.csv')
gt_ids = set(new_gt['chunk_id'].values)
corpus_ids = set(corpus['chunk_id'].values)
matched = gt_ids & corpus_ids
missing = gt_ids - corpus_ids

print(f"\n=== 검증 결과 ===")
print(f"총 질문: {len(new_gt)}개")
print(f"고유 chunk_id: {len(gt_ids)}개")
print(f"매칭된 chunk_id: {len(matched)}/{len(gt_ids)}개")

if missing:
    print(f"\n⚠️ 누락된 chunk_id ({len(missing)}개):")
    for cid in sorted(missing)[:10]:
        print(f"  - {cid}")
else:
    print("✅ 모든 chunk_id가 corpus에 존재합니다!")

# 주제별 분포
print(f"\n=== 주제별 분포 ===")
topics = {
    '통학버스': ['버스', '통학', '노쇼', 'QR', '배차', '대구'],
    '기숙사/생활관': ['식당', '메뉴', '푸름', '오름', '생활관', '기숙사', '아름', '입사', '퇴사'],
    '수강/학사': ['수강', '신청', '변경', '정정', '학점', '과목', '전공', '교양', '졸업', '성적'],
    '학부/학과': ['학부', '학과', '전자공학', '기계공학', '컴퓨터', '건축', '소프트웨어'],
    '학생활동': ['동아리', '학생회', '총학', '축제', '봉사'],
    '장학/취업': ['장학', '취업', '도서관']
}

for topic, keywords in topics.items():
    count = new_gt['query'].str.contains('|'.join(keywords)).sum()
    print(f"{topic}: {count}개")
