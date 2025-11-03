#!/usr/bin/env python3
"""
Ground Truth 확장: LLM을 사용하여 추가 질문 생성
"""
import pandas as pd
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
import os
import random

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[1]

def generate_questions_for_chunk(client, chunk_text, chunk_id, existing_queries, num_questions=2):
    """
    특정 chunk에 대한 추가 질문 생성
    """
    existing_str = "\n".join([f"- {q}" for q in existing_queries])
    
    prompt = f"""다음 문서 내용을 읽고, 학생들이 실제로 물어볼 만한 자연스러운 질문을 {num_questions}개 생성해주세요.

<문서 내용>
{chunk_text[:800]}
</문서 내용>

<이미 있는 질문들>
{existing_str}
</이미 있는 질문들>

요구사항:
1. 이미 있는 질문과 중복되지 않게
2. 구어체로 자연스럽게 (예: "~인가요?", "~해주세요", "~어떻게 되나요?")
3. 문서 내용에서 답을 찾을 수 있는 질문만
4. 각 질문은 한 줄로, 번호 없이

질문 {num_questions}개를 줄바꿈으로 구분하여 작성하세요:"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "당신은 대학생들의 실제 질문을 생성하는 전문가입니다."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.8,
        max_tokens=300
    )
    
    questions = response.choices[0].message.content.strip().split('\n')
    # 빈 줄, 번호 제거
    questions = [q.strip() for q in questions if q.strip()]
    questions = [q.lstrip('123456789.- ') for q in questions]
    
    return questions[:num_questions]

def expand_ground_truth(target_size=100):
    """
    Ground truth를 target_size개로 확장
    """
    print(f"🚀 Ground Truth 확장 시작 (목표: {target_size}개)")
    
    # 기존 데이터 로드
    gt_df = pd.read_csv(PROJECT_ROOT / 'data/ground_truth.csv')
    corpus_df = pd.read_csv(PROJECT_ROOT / 'data/corpus_filtered.csv')
    
    print(f"  현재 queries: {len(gt_df)}개")
    print(f"  필요한 추가 queries: {target_size - len(gt_df)}개")
    
    # OpenAI 클라이언트
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    # Chunk별 기존 질문 그룹화
    chunk_queries = gt_df.groupby('chunk_id')['query'].apply(list).to_dict()
    
    # 각 chunk의 텍스트
    chunk_texts = corpus_df.set_index('chunk_id')['text'].to_dict()
    
    # 질문이 적은 chunk부터 우선 확장
    chunk_counts = gt_df['chunk_id'].value_counts()
    chunks_to_expand = chunk_counts[chunk_counts < 5].index.tolist()
    
    # 질문이 1개뿐인 chunk 우선
    chunks_to_expand.sort(key=lambda x: chunk_counts[x])
    
    new_rows = []
    needed = target_size - len(gt_df)
    
    print(f"\n📝 질문 생성 중...")
    
    while needed > 0 and chunks_to_expand:
        for chunk_id in chunks_to_expand[:]:
            if needed <= 0:
                break
            
            if chunk_id not in chunk_texts:
                chunks_to_expand.remove(chunk_id)
                continue
            
            # 각 chunk당 1-2개씩 생성
            num_to_gen = min(2, needed, 5 - len(chunk_queries.get(chunk_id, [])))
            
            if num_to_gen <= 0:
                chunks_to_expand.remove(chunk_id)
                continue
            
            try:
                new_questions = generate_questions_for_chunk(
                    client,
                    chunk_texts[chunk_id],
                    chunk_id,
                    chunk_queries.get(chunk_id, []),
                    num_questions=num_to_gen
                )
                
                for q in new_questions:
                    if q and len(q) > 5:  # 유효한 질문만
                        new_rows.append({
                            'query': q,
                            'chunk_id': chunk_id
                        })
                        chunk_queries.setdefault(chunk_id, []).append(q)
                        needed -= 1
                        print(f"  [{len(gt_df) + len(new_rows)}/{target_size}] {chunk_id[:30]}... → {q[:50]}...")
                        
                        if needed <= 0:
                            break
                
            except Exception as e:
                print(f"  ⚠️  {chunk_id} 생성 실패: {e}")
                continue
        
        # 모든 chunk를 한 번씩 돌았는데도 필요하면, 랜덤하게 추가
        if needed > 0 and not chunks_to_expand:
            chunks_to_expand = list(chunk_texts.keys())
            random.shuffle(chunks_to_expand)
    
    # 새 데이터 추가
    if new_rows:
        new_df = pd.DataFrame(new_rows)
        final_df = pd.concat([gt_df, new_df], ignore_index=True)
        
        # 저장
        final_df.to_csv(PROJECT_ROOT / 'data/ground_truth.csv', index=False)
        
        # queries.txt도 업데이트
        with open(PROJECT_ROOT / 'data/queries.txt', 'w', encoding='utf-8') as f:
            for query in final_df['query'].unique():
                f.write(query + '\n')
        
        print(f"\n✅ Ground Truth 확장 완료!")
        print(f"  최종 queries: {len(final_df)}개")
        print(f"  고유 chunk_id: {final_df['chunk_id'].nunique()}개")
        print(f"  새로 추가된 queries: {len(new_rows)}개")
        
        # 분포 확인
        final_counts = final_df['chunk_id'].value_counts()
        print(f"\n📊 Chunk별 query 분포:")
        print(f"  평균: {final_counts.mean():.1f}개")
        print(f"  최대: {final_counts.max()}개")
        print(f"  최소: {final_counts.min()}개")
    else:
        print("\n⚠️  새로운 질문을 생성하지 못했습니다.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--target', type=int, default=100, help='목표 질문 수')
    args = parser.parse_args()
    
    expand_ground_truth(args.target)
