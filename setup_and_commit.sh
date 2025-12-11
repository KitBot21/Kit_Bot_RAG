#!/bin/bash

echo "🔧 Git 설정 시작..."

# 1. Git 사용자 정보 설정
echo "📝 Git 사용자 정보 설정..."
git config --global user.name "KitBot21"
git config --global user.email "kitbot21@example.com"
echo "✅ 사용자 정보 설정 완료"
echo ""

# 2. 원격 저장소 연결
echo "🔗 GitHub 원격 저장소 연결..."
git remote add origin https://github.com/KitBot21/Kit_Bot_RAG.git
echo "✅ 원격 저장소 연결 완료"
echo ""

# 3. 현재 브랜치 확인 및 변경
echo "🌿 브랜치 확인..."
current_branch=$(git branch --show-current)
if [ -z "$current_branch" ]; then
    echo "기본 브랜치를 main으로 설정..."
    git checkout -b main
else
    echo "현재 브랜치: $current_branch"
fi
echo ""

# 4. 파일 추가
echo "📦 파일 추가 중..."
git add -A
echo "✅ 파일 추가 완료"
echo ""

# 5. 커밋
echo "💾 커밋 생성 중..."
git commit -m "feat: RAG system improvements and evaluation framework

🎯 Features
- Hybrid search (BM25 + Semantic) implementation
- Reranker (BGE-reranker-v2-m3) integration
- Full version (Hybrid + Reranker)
- Chitchat intent classification

⚡ Optimizations
- N-gram tokenizer (2-3 character partial matching)
- Alpha=0.85 (Semantic 85%, BM25 15%)
- Min-Max normalization
- Reranker: 30 candidates, 1024 token context

📊 Performance Improvements
- Context Precision: 62.5% → 72.2% (+15.6%)
- Context Recall: 87.5% → 90.0% (+2.9%)
- Faithfulness: 76.1% → 83.1% (+9.2%)
- Answer Relevancy: 85.4% (maintained)

📚 Evaluation System
- Ragas-based automated evaluation (GPT-4o)
- Golden Dataset (10 questions)
- 4 metrics: Precision, Recall, Faithfulness, Relevancy
- Response time measurement and comparison

📖 Documentation
- EVALUATION_METHODOLOGY.md (evaluation methodology)
- comparison_report.md (experiment results)
- Various guide documents

🔧 Others
- Updated .gitignore (sensitive data protection)
- Added .env.example template
- Docker command documentation"

echo "✅ 커밋 완료!"
echo ""

# 6. 커밋 로그 확인
echo "📜 커밋 정보:"
git log --oneline -1
echo ""

# 7. 푸시
echo "🚀 GitHub에 푸시 중..."
git push -u origin main

if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 성공! GitHub에 업로드되었습니다!"
    echo "🔗 https://github.com/KitBot21/Kit_Bot_RAG"
else
    echo ""
    echo "⚠️ 푸시 실패. 인증이 필요할 수 있습니다."
    echo ""
    echo "해결 방법:"
    echo "1. GitHub Personal Access Token 생성:"
    echo "   https://github.com/settings/tokens"
    echo ""
    echo "2. 다음 명령어로 다시 푸시:"
    echo "   git push -u origin main"
    echo ""
    echo "3. Username: KitBot21"
    echo "4. Password: (Personal Access Token 입력)"
fi
