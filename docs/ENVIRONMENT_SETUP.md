# 🐍 Python 가상환경 설정 가이드

## ❓ 가상환경이 필요한가요?

**답: 네, 반드시 사용하세요!** ✅

### 가상환경을 사용하는 이유

1. **의존성 격리**
   - 프로젝트별로 독립적인 라이브러리 관리
   - 다른 프로젝트와 충돌 방지

2. **버전 관리**
   - 특정 버전의 라이브러리 고정
   - 팀원들과 동일한 환경 공유

3. **시스템 보호**
   - 시스템 Python 패키지 오염 방지
   - 권한 문제 회피 (sudo 불필요)

---

## 🔍 현재 상태 확인

### 가상환경 활성화 여부 확인

```bash
# 터미널 프롬프트 확인
# (.venv) 또는 (venv)가 있으면 활성화된 상태
(.venv) jhlee@kit:~/Kit_Bot_RAG$  # ✅ 활성화됨
jhlee@kit:~/Kit_Bot_RAG$           # ❌ 비활성화

# 또는 which python으로 확인
which python3
# 가상환경: /home/jhlee/Kit_Bot_RAG/.venv/bin/python3
# 시스템: /usr/bin/python3
```

### Python 위치 확인

```bash
# 현재 사용 중인 Python
python3 --version
which python3

# 가상환경 Python인지 확인
python3 -c "import sys; print(sys.prefix)"
# /home/jhlee/Kit_Bot_RAG/.venv 이면 가상환경
# /usr 이면 시스템 Python
```

---

## 🚀 가상환경 설정 (처음 시작하는 경우)

### 1. 가상환경 생성

```bash
# 프로젝트 디렉토리로 이동
cd ~/Kit_Bot_RAG

# 가상환경 생성
python3 -m venv .venv

# 생성 확인
ls -la .venv/
```

### 2. 가상환경 활성화

```bash
# Linux/Mac
source .venv/bin/activate

# Windows (Git Bash)
source .venv/Scripts/activate

# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

# 활성화 확인 (프롬프트에 (.venv) 표시됨)
(.venv) jhlee@kit:~/Kit_Bot_RAG$
```

### 3. pip 업그레이드

```bash
# 가상환경 활성화 후
pip install --upgrade pip
```

### 4. 의존성 설치

```bash
# 기본 라이브러리
pip install -r requirements.txt  # 메인 라이브러리 (있다면)

# 첨부파일 처리 라이브러리
pip install -r requirements-attachments.txt

# 또는 개별 설치
pip install sentence-transformers qdrant-client openai python-dotenv
pip install PyPDF2 python-docx openpyxl python-pptx minio
```

### 5. 설치 확인

```bash
# 설치된 패키지 목록
pip list

# 특정 패키지 확인
pip show sentence-transformers
pip show minio
```

---

## 🔄 일상적인 사용

### 프로젝트 시작할 때마다

```bash
# 1. 프로젝트 디렉토리로 이동
cd ~/Kit_Bot_RAG

# 2. 가상환경 활성화
source .venv/bin/activate

# 3. 작업 시작
python3 rag_demo.py --query "테스트"

# 4. 작업 종료 후 비활성화
deactivate
```

### VS Code 사용 시

VS Code는 자동으로 가상환경을 감지하고 사용합니다:

1. **Python 인터프리터 선택**
   ```
   Ctrl+Shift+P → "Python: Select Interpreter"
   → "./.venv/bin/python3" 선택
   ```

2. **터미널 자동 활성화**
   - VS Code 터미널을 열면 자동으로 `.venv` 활성화
   - `.vscode/settings.json`에 설정 추가:
   ```json
   {
     "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python3",
     "python.terminal.activateEnvironment": true
   }
   ```

---

## 🐳 Docker vs 가상환경

### MinIO는 Docker, Python은 가상환경

| 구분 | 도구 | 이유 |
|------|------|------|
| **MinIO 서버** | Docker | - 완전 격리된 서비스<br>- 쉬운 설치/제거<br>- 포트 관리 간편 |
| **Python 코드** | venv | - 빠른 개발/테스트<br>- IDE 통합 쉬움<br>- 디버깅 편리 |

```bash
# 올바른 사용 예시

# MinIO: Docker로 실행
docker run -d -p 9000:9000 --name minio-kit ...

# Python: 가상환경에서 실행
source .venv/bin/activate
python3 scripts/process_attachments.py --source minio
```

---

## 📦 requirements.txt 관리

### 현재 환경 내보내기

```bash
# 가상환경 활성화 후
pip freeze > requirements.txt

# 또는 핵심 패키지만
pip list --format=freeze | grep -E "sentence-transformers|qdrant|openai|minio" > requirements-core.txt
```

### 전체 의존성 파일 구조 (권장)

```
Kit_Bot_RAG/
├── requirements.txt              # 기본 라이브러리
├── requirements-attachments.txt  # 첨부파일 처리
├── requirements-dev.txt          # 개발용 (옵션)
└── .env                          # 환경 변수
```

**requirements.txt (기본):**
```txt
sentence-transformers>=2.2.0
qdrant-client>=1.7.0
openai>=1.0.0
python-dotenv>=1.0.0
pandas>=2.0.0
numpy>=1.24.0
beautifulsoup4>=4.12.0
lxml>=4.9.0
charset-normalizer>=3.0.0
```

**requirements-dev.txt (개발용, 옵션):**
```txt
jupyter>=1.0.0
ipython>=8.0.0
pytest>=7.4.0
black>=23.0.0
flake8>=6.0.0
```

---

## 🔧 문제 해결

### 가상환경이 활성화되지 않음

**증상:**
```bash
source .venv/bin/activate
# 아무 반응 없음, (.venv) 표시 안됨
```

**해결:**
```bash
# bash 쉘 확인
echo $SHELL

# zsh 사용 시
source .venv/bin/activate

# fish 사용 시
source .venv/bin/activate.fish
```

### pip install 권한 오류

**증상:**
```
ERROR: Could not install packages due to an OSError: [Errno 13] Permission denied
```

**해결:**
```bash
# 가상환경 활성화 확인!
which pip
# /home/jhlee/Kit_Bot_RAG/.venv/bin/pip 여야 함

# 시스템 pip이면 가상환경 활성화
source .venv/bin/activate

# 절대 sudo pip install 하지 마세요!
```

### 라이브러리가 import 안됨

**증상:**
```python
ModuleNotFoundError: No module named 'minio'
```

**해결:**
```bash
# 1. 가상환경 활성화 확인
which python3

# 2. 가상환경에 설치
pip install minio

# 3. 설치 확인
pip show minio

# 4. Python 재시작
```

### VS Code에서 import 오류

**증상:**
- VS Code에서 빨간 밑줄
- "Import could not be resolved"

**해결:**
1. Python 인터프리터를 `.venv/bin/python3`로 변경
2. VS Code 재시작
3. Pylance 언어 서버 재시작: `Ctrl+Shift+P` → "Reload Window"

---

## ✅ 체크리스트

프로젝트 시작 전 확인:

- [ ] 가상환경 생성됨 (`.venv/` 디렉토리 존재)
- [ ] 가상환경 활성화됨 (프롬프트에 `(.venv)` 표시)
- [ ] pip 업그레이드 완료
- [ ] 필요한 라이브러리 설치 완료
- [ ] `which python3`로 가상환경 Python 사용 확인
- [ ] VS Code 인터프리터 설정 완료 (사용 시)

MinIO + RAG 시스템 실행 전:

```bash
# ✅ 올바른 방법
cd ~/Kit_Bot_RAG
source .venv/bin/activate
python3 scripts/upload_to_minio.py ~/Downloads/attachments/

# ❌ 잘못된 방법
cd ~/Kit_Bot_RAG
python3 scripts/upload_to_minio.py ~/Downloads/attachments/  # 가상환경 미활성화
```

---

## 🎯 빠른 참조

```bash
# === 가상환경 관련 ===
python3 -m venv .venv          # 생성
source .venv/bin/activate      # 활성화 (Linux/Mac)
deactivate                     # 비활성화
which python3                  # 확인

# === 패키지 관리 ===
pip install PACKAGE            # 설치
pip install -r requirements.txt  # 일괄 설치
pip list                       # 목록
pip show PACKAGE               # 상세 정보
pip freeze > requirements.txt  # 내보내기

# === 환경 확인 ===
python3 --version              # Python 버전
pip --version                  # pip 버전
python3 -m site                # 사이트 패키지 위치
```

---

## 💡 Best Practices

1. **항상 가상환경 활성화**
   - 프로젝트 작업 시작 시 첫 번째로 활성화
   - `.bashrc` 또는 `.zshrc`에 별칭 추가:
   ```bash
   alias kitbot="cd ~/Kit_Bot_RAG && source .venv/bin/activate"
   ```

2. **requirements.txt 최신 유지**
   - 새 패키지 설치 후 업데이트
   - Git에 커밋

3. **시스템 Python 건드리지 않기**
   - `sudo pip install` 절대 금지
   - 모든 작업은 가상환경 내에서

4. **.venv는 Git에서 제외**
   - `.gitignore`에 `.venv/` 추가 (이미 되어 있음)
   - requirements.txt만 공유

5. **여러 프로젝트 = 여러 가상환경**
   - 프로젝트마다 독립된 가상환경 사용
   - 이름 구분: `.venv`, `venv-project1` 등

---

## 🚀 전체 워크플로우 예시

```bash
# === 프로젝트 처음 설정 (1회만) ===
cd ~/Kit_Bot_RAG
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-attachments.txt

# === 매일 작업 시작 ===
cd ~/Kit_Bot_RAG
source .venv/bin/activate

# === MinIO + 첨부파일 처리 ===
# 1. MinIO 서버 실행 (Docker - 한 번만)
docker start minio-kit  # 또는 docker run ...

# 2. 파일 업로드 (가상환경에서)
python3 scripts/upload_to_minio.py ~/Downloads/attachments/

# 3. 처리 (가상환경에서)
python3 scripts/process_attachments.py --source minio
python3 scripts/merge_corpus.py
python3 scripts/regenerate_embeddings.py --input data/corpus_merged.csv
python3 scripts/ingest_multi.py --input data/corpus_merged.csv

# 4. 테스트 (가상환경에서)
python3 rag_demo.py --query "장학금 신청 방법"

# === 작업 종료 ===
deactivate
```

---

## 📞 요약

**가상환경 사용: 필수!** ✅

**이유:**
- ✅ 의존성 격리
- ✅ 버전 관리
- ✅ 권한 문제 없음
- ✅ 팀 협업 용이

**MinIO는 Docker, Python은 가상환경!**
- MinIO: `docker run ...` (서비스)
- Python: `source .venv/bin/activate` (개발)

**매번 작업 시작 시:**
```bash
cd ~/Kit_Bot_RAG
source .venv/bin/activate
# 이제 Python 명령어 실행
```
