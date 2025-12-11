# 📎 첨부파일 처리 가이드

학교 사이트에서 다운받은 첨부파일(PDF, Word, Excel 등)을 RAG 시스템에 추가하는 방법을 안내합니다.

## 🎯 방법 선택

### 방법 1: 로컬 파일 (권장 - 간단함) ⭐

**언제 사용?**
- 개발/테스트 단계
- 첨부파일 수가 적음 (수백 개 이하)
- 단일 서버 환경

**장점:**
- ✅ 설정 간단, 추가 인프라 불필요
- ✅ 즉시 시작 가능
- ✅ 파일 관리 직관적

**단점:**
- ❌ Git 저장소 크기 증가 가능
- ❌ 서버 간 파일 공유 어려움

### 방법 2: MinIO/S3 (프로덕션용)

**언제 사용?**
- 프로덕션 환경
- 첨부파일이 많고 계속 증가
- 여러 서버/서비스에서 접근 필요
- 파일 버전 관리 필요

**장점:**
- ✅ 확장성 우수
- ✅ 여러 서버에서 접근 가능
- ✅ 파일 관리/백업 용이
- ✅ Git 저장소와 분리

**단점:**
- ❌ 추가 인프라 필요 (MinIO 서버)
- ❌ 설정 복잡도 증가

---

## 📥 방법 1: 로컬 파일 사용 (추천)

### 1단계: 첨부파일 준비

```bash
# 첨부파일 디렉토리 생성
mkdir -p data/attachments

# 학교 사이트에서 다운받은 파일들을 복사
cp ~/Downloads/*.pdf data/attachments/
cp ~/Downloads/*.docx data/attachments/
cp ~/Downloads/*.xlsx data/attachments/
```

**디렉토리 구조 예시:**
```
data/attachments/
├── 생활관_입사안내.pdf
├── 학사일정표_2025.xlsx
├── 장학금_신청안내.docx
├── 수강신청_가이드.pdf
└── ...
```

### 2단계: 필요한 라이브러리 설치

```bash
pip install -r requirements-attachments.txt
```

또는 개별 설치:
```bash
pip install PyPDF2 python-docx openpyxl python-pptx
```

### 3단계: 첨부파일 처리

```bash
python3 scripts/process_attachments.py
```

**출력 예시:**
```
================================================================================
📎 첨부파일 처리 시작
================================================================================

📊 발견된 파일: 15개

📄 처리 중: 생활관_입사안내.pdf
  ✅ 8개 청크 생성 (총 4,523자)

📄 처리 중: 학사일정표_2025.xlsx
  ✅ 3개 청크 생성 (총 1,821자)

...

✅ 첨부파일 처리 완료!
  처리된 파일: 15개
  총 청크 수: 89개
  저장 위치: data/corpus_attachments.csv
```

### 4단계: Corpus 병합

```bash
python3 scripts/merge_corpus.py
```

### 5단계: 임베딩 생성 및 업로드

```bash
# 임베딩 생성
python3 scripts/regenerate_embeddings.py --input data/corpus_merged.csv

# Qdrant에 업로드
python3 scripts/ingest_multi.py --input data/corpus_merged.csv
```

### 6단계: 테스트

```bash
python3 rag_demo.py --query "장학금 신청 방법 알려주세요"
```

---

## 🗄️ 방법 2: MinIO/S3 사용

### 사전 준비: MinIO 설치 (Docker)

```bash
# MinIO 서버 실행
docker run -d \
  -p 9000:9000 \
  -p 9001:9001 \
  --name minio \
  -e "MINIO_ROOT_USER=admin" \
  -e "MINIO_ROOT_PASSWORD=your_password_here" \
  -v ~/minio/data:/data \
  quay.io/minio/minio server /data --console-address ":9001"
```

### 1단계: MinIO 설정

1. 브라우저에서 `http://localhost:9001` 접속
2. 로그인 (admin / your_password_here)
3. 버킷 생성: `kit-attachments`
4. Access Key 생성:
   - Identity > Service Accounts > Create Service Account
   - Access Key와 Secret Key 저장

### 2단계: 파일 업로드

**방법 A: 웹 UI 사용**
1. MinIO 콘솔에서 `kit-attachments` 버킷 선택
2. Upload 버튼으로 파일들 업로드

**방법 B: MinIO Client (mc) 사용**
```bash
# mc 설치
wget https://dl.min.io/client/mc/release/linux-amd64/mc
chmod +x mc
sudo mv mc /usr/local/bin/

# MinIO 서버 등록
mc alias set local http://localhost:9000 admin your_password_here

# 파일 업로드
mc cp ~/Downloads/*.pdf local/kit-attachments/
mc cp ~/Downloads/*.docx local/kit-attachments/
```

### 3단계: 라이브러리 설치

```bash
pip install -r requirements-attachments.txt
pip install minio
```

### 4단계: MinIO에서 파일 다운로드 및 처리

```bash
python3 scripts/process_attachments.py --source minio \
  --minio-endpoint localhost:9000 \
  --minio-access-key YOUR_ACCESS_KEY \
  --minio-secret-key YOUR_SECRET_KEY \
  --minio-bucket kit-attachments
```

**HTTPS 사용 시:**
```bash
python3 scripts/process_attachments.py --source minio \
  --minio-endpoint s3.amazonaws.com \
  --minio-access-key YOUR_ACCESS_KEY \
  --minio-secret-key YOUR_SECRET_KEY \
  --minio-bucket kit-attachments \
  --minio-secure
```

### 5단계 이후

방법 1의 4~6단계와 동일합니다.

---

## 📋 지원하는 파일 형식

| 형식 | 확장자 | 라이브러리 |
|------|--------|-----------|
| PDF | `.pdf` | PyPDF2 |
| Word | `.docx`, `.doc` | python-docx |
| Excel | `.xlsx`, `.xls` | openpyxl |
| PowerPoint | `.pptx`, `.ppt` | python-pptx |
| 텍스트 | `.txt` | 내장 |

---

## 🔧 문제 해결

### 파일이 처리되지 않음

**증상:**
```
⚠️  텍스트가 너무 짧음 (길이: 0)
```

**해결:**
- PDF가 이미지 기반인 경우 → OCR 필요 (tesseract)
- 파일이 손상되었을 수 있음 → 다시 다운로드
- 암호화된 파일 → 암호 제거 후 처리

### 한글이 깨짐

**해결:**
```bash
# 인코딩 확인
file -i your_file.txt

# UTF-8로 변환
iconv -f EUC-KR -t UTF-8 your_file.txt > your_file_utf8.txt
```

### 메모리 부족

**증상:**
대용량 파일 처리 시 메모리 에러

**해결:**
- 청크 크기 줄이기: `process_attachments.py`에서 `CHARS = 800` → `400`
- 파일을 여러 번에 나눠서 처리

---

## 💡 Best Practices

1. **파일명 규칙**
   - 한글 사용 가능하지만 영문 추천
   - 공백 대신 언더스코어 사용: `학사_일정_2025.pdf`
   - 의미 있는 이름: `scholarship_guide.pdf` (O) vs `document1.pdf` (X)

2. **디렉토리 구조**
   ```
   data/attachments/
   ├── academic/        # 학사 관련
   ├── dormitory/       # 생활관 관련
   ├── scholarship/     # 장학금 관련
   └── general/         # 일반
   ```

3. **버전 관리**
   - 첨부파일은 `.gitignore`에 추가 (용량 문제)
   - MinIO/S3 사용 시 버전 관리 기능 활용

4. **주기적 업데이트**
   - 학기별로 최신 파일로 교체
   - 오래된 파일 아카이브

---

## 📊 성능 최적화

### 처리 시간 단축

```bash
# 병렬 처리 (구현 예정)
python3 scripts/process_attachments.py --workers 4
```

### 증분 업데이트

```bash
# 새로운 파일만 처리 (구현 예정)
python3 scripts/process_attachments.py --incremental
```

---

## ❓ FAQ

**Q: Git에 첨부파일을 커밋해야 하나요?**
A: 파일 크기가 작으면 (< 10MB) 괜찮지만, 일반적으로 `.gitignore`에 추가하고 MinIO나 별도 저장소 사용을 권장합니다.

**Q: 첨부파일을 수정하면 자동으로 재처리되나요?**
A: 아니요. 수동으로 `process_attachments.py`를 다시 실행해야 합니다.

**Q: OCR 지원하나요?**
A: 현재는 텍스트 기반 PDF만 지원합니다. 이미지 PDF는 tesseract를 사용한 OCR이 필요합니다.

**Q: 암호화된 PDF를 처리할 수 있나요?**
A: 암호를 제거한 후 처리해야 합니다. 또는 PyPDF2에 암호를 전달하는 기능을 추가할 수 있습니다.

---

## 🚀 다음 단계

파일 처리 후:
1. ✅ `corpus_merged.csv` 확인
2. ✅ 임베딩 생성 및 Qdrant 업로드
3. ✅ RAG 챗봇으로 테스트
4. ✅ Ground truth에 첨부파일 관련 질문 추가
