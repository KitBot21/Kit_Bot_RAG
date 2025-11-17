#!/bin/bash
# Kit_Bot RAG 프로젝트 빠른 시작 스크립트

echo "🚀 Kit_Bot RAG 환경 설정 중..."
echo ""

# 프로젝트 디렉토리로 이동
cd "$(dirname "$0")"

# 가상환경 존재 확인
if [ ! -d ".venv" ]; then
    echo "❌ 가상환경이 없습니다. 생성 중..."
    python3 -m venv .venv
    echo "✅ 가상환경 생성 완료"
fi

# 가상환경 활성화
echo "🔧 가상환경 활성화 중..."
source .venv/bin/activate

# Python 경로 확인
echo "📍 Python 위치: $(which python3)"
echo ""

# pip 업그레이드
echo "⬆️  pip 업그레이드 중..."
pip install --upgrade pip -q

# 기본 패키지 확인
echo "📦 패키지 확인 중..."
PACKAGES=("sentence-transformers" "qdrant-client" "openai" "python-dotenv" "pandas")
MISSING=()

for pkg in "${PACKAGES[@]}"; do
    if ! pip show "$pkg" &> /dev/null; then
        MISSING+=("$pkg")
    fi
done

if [ ${#MISSING[@]} -ne 0 ]; then
    echo "⚠️  누락된 패키지: ${MISSING[*]}"
    echo "📥 설치 중..."
    pip install "${MISSING[@]}" -q
    echo "✅ 패키지 설치 완료"
else
    echo "✅ 모든 기본 패키지 설치됨"
fi

echo ""
echo "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "="
echo "🎉 환경 설정 완료!"
echo "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "="
echo ""
echo "💡 사용 가능한 명령어:"
echo ""
echo "  # RAG 챗봇 실행"
echo "  python3 rag_demo.py"
echo ""
echo "  # 첨부파일 처리 (MinIO)"
echo "  python3 scripts/process_attachments.py --source minio"
echo ""
echo "  # MinIO 파일 업로드"
echo "  python3 scripts/upload_to_minio.py ~/Downloads/attachments/"
echo ""
echo "작업 종료 후 'deactivate' 명령으로 가상환경을 비활성화하세요."
echo ""
echo "현재 쉘에서 가상환경을 활성화하려면:"
echo "  source .venv/bin/activate"
echo ""
