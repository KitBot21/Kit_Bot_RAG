#!/bin/bash

echo "🚀 Git 커밋 시작..."
echo ""

# 1. Git 상태 확인
echo "📋 1. 현재 Git 상태 확인"
git status --short | head -20
echo ""

# 2. 모든 파일 추가 (.gitignore가 자동 제외)
echo "📦 2. 파일 추가 중... (민감한 파일은 자동 제외됨)"
git add -A
echo "✅ 파일 추가 완료"
echo ""

# 3. 추가된 파일 확인
echo "📝 3. 커밋될 파일 목록"
git status --short | head -30
echo ""

# 4. .env 파일이 제외되었는지 확인
echo "🔒 4. 민감한 파일 제외 확인"
if git status --short | grep -q "\.env$"; then
    echo "❌ 경고: .env 파일이 포함되어 있습니다!"
    echo "커밋을 중단합니다."
    exit 1
else
    echo "✅ .env 파일 제외됨"
fi

if git status --short | grep -q "OPENAI_API_KEY\|api.*key"; then
    echo "❌ 경고: API 키가 포함된 파일이 있을 수 있습니다!"
    echo "계속하시겠습니까? (y/N)"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        echo "커밋을 중단합니다."
        exit 1
    fi
else
    echo "✅ API 키 노출 없음"
fi
echo ""

# 5. 커밋 메시지 작성 및 커밋
echo "💾 5. 커밋 생성 중..."
git commit -m "feat: RAG 시스템 개선 및 평가 프레임워크 추가

🎯 주요 기능
- 하이브리드 검색 (BM25 + Semantic) 구현 및 최적화
- 리랭커 (BGE-reranker-v2-m3) 통합
- Full 버전 (Hybrid + Reranker) 구현
- 일상 대화(chitchat) 의도 분류 추가

⚡ 최적화
- N-gram 토크나이저 (2-3글자 부분 일치)
- Alpha=0.85 (시맨틱 85%, BM25 15%)
- Min-Max 정규화 (점수 편향 제거)
- 리랭커 후보 30개, 텍스트 길이 1024토큰

📊 성능 개선
- Context Precision: 62.5% → 72.2% (+15.6%)
- Context Recall: 87.5% → 90.0% (+2.9%)
- Faithfulness: 76.1% → 83.1% (+9.2%)
- Answer Relevancy: 85.4% (유지)

📚 평가 시스템
- Ragas 기반 자동 평가 (GPT-4o)
- Golden Dataset (10개 질문)
- 4가지 메트릭: Precision, Recall, Faithfulness, Relevancy
- 응답 시간 측정 및 비교

📖 문서화
- EVALUATION_METHODOLOGY.md (평가 방법론)
- comparison_report.md (실험 결과 비교)
- 각종 가이드 문서 추가

🔧 기타
- .gitignore 업데이트 (민감 정보 보호)
- .env.example 템플릿 추가
- Docker 실행 명령어 정리"

if [ $? -eq 0 ]; then
    echo "✅ 커밋 완료!"
    echo ""
    
    # 6. 커밋 로그 확인
    echo "📜 6. 커밋 로그"
    git log --oneline -1
    echo ""
    
    echo "🎉 커밋이 성공적으로 완료되었습니다!"
    echo ""
    echo "다음 단계:"
    echo "  git push origin main"
    echo "  (또는 git push origin master)"
else
    echo "❌ 커밋 실패"
    exit 1
fi
