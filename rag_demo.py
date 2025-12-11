#!/usr/bin/env python3
"""
RAG Demo: Qdrant Retrieval + LLM Generation
"""
import pandas as pd
from pathlib import Path
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from openai import OpenAI
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent

class RAGSystem:
    def __init__(self, collection_name='kit_corpus_bge_all', 
                 retriever_model='BAAI/bge-m3',
                 llm_provider='openai',  # 'openai' or 'ollama'
                 llm_model='gpt-4o-mini'):
        """
        RAG 시스템 초기화
        
        Args:
            collection_name: Qdrant 컬렉션 이름
            retriever_model: 임베딩 모델
            llm_provider: LLM 제공자 ('openai' or 'ollama')
            llm_model: LLM 모델 이름
        """
        print("🚀 RAG 시스템 초기화 중...")
        
        # Retriever 로드
        print(f"  📥 Retriever 로딩: {retriever_model}")
        self.retriever = SentenceTransformer(retriever_model)
        
        # Qdrant 클라이언트
        self.qdrant_client = QdrantClient('localhost', port=6333)
        self.collection_name = collection_name
        
        # LLM 설정
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        
        if llm_provider == 'openai':
            self.llm_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        elif llm_provider == 'ollama':
            # Ollama는 로컬에서 실행 (http://localhost:11434)
            self.llm_client = OpenAI(
                base_url='http://localhost:11434/v1',
                api_key='ollama'  # Ollama는 API 키 불필요
            )
        
        print(f"  🤖 LLM: {llm_provider}/{llm_model}")
        print("✅ RAG 시스템 준비 완료!\n")
    
    def retrieve(self, query, top_k=5):
        """
        쿼리와 관련된 문서 검색
        
        Args:
            query: 사용자 질문
            top_k: 반환할 문서 수
            
        Returns:
            List of (text, score, metadata)
        """
        # 쿼리 확장: 특정 키워드 강화
        expanded_query = query
        
        # 식당명 매핑 (검색 품질 향상)
        restaurant_keywords = {
            '분식당': '분식당 일품요리',
            '교직원식당': '교직원식당 정식',
            '신평캠퍼스식당': '신평캠퍼스식당',
            '푸름관': '푸름관 생활관 식당',
            '오름관': '오름관 생활관 식당'
        }
        
        for keyword, expansion in restaurant_keywords.items():
            if keyword in query:
                expanded_query = f"{query} {expansion}"
                break
        
        # 쿼리 임베딩
        query_vector = self.retriever.encode(expanded_query, normalize_embeddings=True).tolist()
        
        # Qdrant 검색 (더 많이 검색 후 필터링)
        search_result = self.qdrant_client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=top_k * 2  # 2배 검색 후 재순위화
        )
        
        # 결과 포맷팅 및 재순위화
        results = []
        for hit in search_result:
            score = hit.score
            title = hit.payload.get('title', '')
            
            # 제목 일치도에 따른 점수 부스트
            query_lower = query.lower()
            title_lower = title.lower()
            
            # 정확한 키워드 매칭 시 점수 증가
            if '분식당' in query_lower and '분식당' in title_lower:
                score *= 1.3
            elif '교직원식당' in query_lower and '교직원식당' in title_lower:
                score *= 1.3
            elif '학생식당' in query_lower and '학생식당' in title_lower:
                score *= 1.3
            elif '학사일정' in query_lower and '학사일정' in title_lower:
                score *= 1.4  # 학사일정은 더 높은 부스트
            elif ('일정' in query_lower or '학사' in query_lower) and '학사일정' in title_lower:
                score *= 1.3
            elif '푸름관' in query_lower and '푸름관' in title_lower:
                score *= 1.3
            elif '오름관' in query_lower and '오름관' in title_lower:
                score *= 1.3
            elif '신평' in query_lower and '신평' in title_lower:
                score *= 1.3
            
            results.append({
                'text': hit.payload.get('text', ''),
                'score': score,  # 재조정된 점수
                'original_score': hit.score,  # 원본 점수
                'chunk_id': hit.payload.get('chunk_id', ''),
                'title': title,
                'url': hit.payload.get('url', '')
            })
        
        # 점수로 재정렬
        results.sort(key=lambda x: x['score'], reverse=True)
        
        # Top-K만 반환
        return results[:top_k]
    
    def generate(self, query, contexts, stream=False):
        """
        검색된 컨텍스트를 바탕으로 LLM 답변 생성
        
        Args:
            query: 사용자 질문
            contexts: 검색된 문서 리스트
            stream: 스트리밍 여부
            
        Returns:
            LLM 생성 답변
        """
        # 현재 날짜 및 요일 정보 (한국 시간)
        from datetime import datetime
        import locale
        import pytz
        
        try:
            locale.setlocale(locale.LC_TIME, 'ko_KR.UTF-8')
        except:
            pass
        
        # 한국 시간대 (KST, UTC+9)
        kst = pytz.timezone('Asia/Seoul')
        now = datetime.now(kst)
        
        # 한국어 요일 매핑
        weekday_kr = {
            'Monday': '월요일',
            'Tuesday': '화요일', 
            'Wednesday': '수요일',
            'Thursday': '목요일',
            'Friday': '금요일',
            'Saturday': '토요일',
            'Sunday': '일요일'
        }
        weekday_en = now.strftime('%A')
        weekday = weekday_kr.get(weekday_en, weekday_en)
        
        today_info = f"{now.strftime('%Y년 %m월 %d일')} ({weekday})"
        
        # 다음주 월요일 계산
        from datetime import timedelta
        days_until_next_monday = (7 - now.weekday()) % 7
        if days_until_next_monday == 0:
            days_until_next_monday = 7
        next_monday = now + timedelta(days=days_until_next_monday)
        next_monday_info = f"{next_monday.strftime('%Y년 %m월 %d일')} ({weekday_kr.get(next_monday.strftime('%A'), next_monday.strftime('%A'))})"
        
        # 컨텍스트 문자열 생성 (출처 정보 포함)
        context_str = "\n\n".join([
            f"[문서 {i+1}]\n제목: {ctx.get('title', '제목없음')}\n내용: {ctx['text']}" 
            for i, ctx in enumerate(contexts)
        ])
        
        # 프롬프트 구성 (개선된 버전)
        system_prompt = f"""당신은 금오공과대학교 학생들을 돕는 친절하고 전문적인 AI 어시스턴트 Kit_Bot입니다.
제공된 문서 정보를 바탕으로 정확하고 상세하며 도움이 되는 답변을 제공하세요.

**현재 날짜**: {today_info} (현재 요일 코드: {now.weekday()}, 0=월요일, 6=일요일)
**다음주 월요일**: {next_monday_info}
- 질문에 "오늘", "이번주" 등의 시간 표현이 있으면 위 날짜를 기준으로 답변하세요
- "다음주 월요일"은 {next_monday_info}입니다
- 요일별 정보가 필요하면 현재 요일을 참고하세요

답변 작성 가이드라인:
1. **정확성**: 제공된 문서에 있는 정보만을 사용하여 답변하세요
2. **완성도**: 질문에 대한 완전한 답변을 제공하세요. 관련된 모든 세부사항을 포함하세요
3. **구조화**: 복잡한 정보는 번호나 글머리 기호로 구조화하여 제시하세요
4. **실용성**: 
   - 절차나 방법을 설명할 때는 단계별로 명확하게 안내하세요
   - 날짜, 시간, 금액, 연락처 등 구체적인 정보를 빠짐없이 제공하세요
   - 관련 URL이나 연락처가 있다면 반드시 포함하세요
5. **한계 인정**: 문서에 정보가 부족하면 "제공된 정보로는 [구체적 부분]을 확인할 수 없습니다"라고 명확히 밝히세요

답변 형식:
- 직접적이고 명확한 답변으로 시작하세요
- 필요시 세부 사항을 추가로 설명하세요
- 학생 입장에서 추가로 필요한 정보가 있다면 함께 안내하세요"""

        user_prompt = f"""다음 문서들을 참고하여 질문에 상세하고 완전하게 답변해주세요.

<참고 문서>
{context_str}
</참고 문서>

<학생 질문>
{query}
</학생 질문>

**중요 가이드**:
- **식당 메뉴** 질문의 경우: 문서에서 요일별 메뉴를 구분하여 답변하세요
  예: "[ 월(11.03) | 화(11.04) | ... ]" 형식에서 현재 날짜에 해당하는 요일의 메뉴만 추출
  각 " | " 구분자로 요일이 나뉘어져 있습니다
- 메뉴 항목은 쉼표나 공백 없이 붙어있을 수 있으니 의미 단위로 구분하세요
  예: "돈코츠라멘육회비빔밥라면류" → "돈코츠라멘, 육회비빔밥, 라면류"

- **학사일정** 질문의 경우: 문서 형식이 "번호 제목 시작일 종료일 등록일 조회" 패턴입니다
  예: "365 군복무 중 취득학점 등 외부기관 학점 인정 신청 2025-10-01 2025-10-03 2024-11-27 0"
  → 제목: 군복무 중 취득학점 등 외부기관 학점 인정 신청
  → 기간: 2025-10-01 ~ 2025-10-03
- 날짜별로 정리하여 일정을 명확하게 제시하세요
- 같은 날짜의 일정이 여러 개면 모두 나열하세요

답변:"""
        
        # LLM 호출
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        if stream:
            # 스트리밍 모드
            response = self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=messages,
                stream=True,
                temperature=0.3,
                max_tokens=800  # 증가: 더 상세한 답변
            )
            return response
        else:
            # 일반 모드
            response = self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=messages,
                temperature=0.3,
                max_tokens=800  # 증가: 더 상세한 답변
            )
            return response.choices[0].message.content
    
    def query(self, question, top_k=5, verbose=True):  # Top-3 → Top-5로 증가
        """
        전체 RAG 파이프라인 실행
        
        Args:
            question: 사용자 질문
            top_k: 검색할 문서 수 (기본값 5로 증가)
            verbose: 상세 정보 출력 여부
            
        Returns:
            답변 및 검색 결과
        """
        if verbose:
            print(f"\n{'='*80}")
            print(f"❓ 질문: {question}")
            print(f"{'='*80}\n")
        
        # 1. 검색
        if verbose:
            print(f"🔍 관련 문서 검색 중... (Top-{top_k})")
        
        contexts = self.retrieve(question, top_k=top_k)
        
        if verbose:
            print(f"\n📚 검색된 문서:")
            for i, ctx in enumerate(contexts):
                print(f"\n[문서 {i+1}] (유사도: {ctx['score']:.3f})")
                print(f"제목: {ctx['title']}")
                print(f"내용: {ctx['text'][:200]}...")
                if ctx['url']:
                    print(f"URL: {ctx['url']}")
        
        # 2. 답변 생성
        if verbose:
            print(f"\n🤖 LLM 답변 생성 중...")
        
        answer = self.generate(question, contexts)
        
        if verbose:
            print(f"\n{'='*80}")
            print(f"💬 답변:")
            print(f"{'='*80}")
            print(answer)
            
            # 출처 정보 추가
            print(f"\n{'='*80}")
            print(f"📎 출처:")
            print(f"{'='*80}")
            unique_sources = {}
            for ctx in contexts:
                url = ctx.get('url', '')
                title = ctx.get('title', '')
                if url and url not in unique_sources:
                    unique_sources[url] = title
            
            for i, (url, title) in enumerate(unique_sources.items(), 1):
                print(f"{i}. {title}")
                print(f"   {url}")
            print(f"{'='*80}\n")
        
        return {
            'question': question,
            'answer': answer,
            'contexts': contexts
        }

def main():
    """대화형 RAG 데모"""
    import argparse
    
    parser = argparse.ArgumentParser(description='금오공대 RAG 챗봇')
    parser.add_argument('--provider', default='openai', choices=['openai', 'ollama'],
                        help='LLM 제공자')
    parser.add_argument('--model', default='gpt-4o-mini',
                        help='LLM 모델 이름')
    parser.add_argument('--top-k', type=int, default=5,  # 기본값 3 → 5
                        help='검색할 문서 수')
    parser.add_argument('--query', type=str, default=None,
                        help='단일 질문 (지정하지 않으면 대화형 모드)')
    args = parser.parse_args()
    
    # RAG 시스템 초기화
    rag = RAGSystem(
        llm_provider=args.provider,
        llm_model=args.model
    )
    
    if args.query:
        # 단일 질문 모드
        rag.query(args.query, top_k=args.top_k)
    else:
        # 대화형 모드
        print("\n" + "="*80)
        print("🎓 금오공대 AI 어시스턴트")
        print("="*80)
        print("질문을 입력하세요 (종료: 'quit' 또는 'exit')\n")
        
        while True:
            try:
                question = input("❓ 질문: ").strip()
                
                if question.lower() in ['quit', 'exit', '종료']:
                    print("\n👋 종료합니다.")
                    break
                
                if not question:
                    continue
                
                rag.query(question, top_k=args.top_k)
                
            except KeyboardInterrupt:
                print("\n\n👋 종료합니다.")
                break
            except Exception as e:
                print(f"\n❌ 오류 발생: {e}\n")

if __name__ == "__main__":
    main()
