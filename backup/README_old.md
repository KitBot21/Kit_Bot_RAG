# Kit_Bot_RAG

금오공과대학교 RAG 챗봇 시스템

## ⚙️ 환경 설정

### Python 가상환경 (필수!)

```bash
# 1. 가상환경 생성
python3 -m venv .venv

# 2. 가상환경 활성화
source .venv/bin/activate

# 3. pip 업그레이드
pip install --upgrade pip

# 4. 기본 라이브러리 설치
pip install sentence-transformers qdrant-client openai python-dotenv pandas

# 5. 첨부파일 처리 라이브러리 설치 (선택)
pip install -r requirements-attachments.txt
```

**⚠️ 중요:** 모든 Python 명령어는 가상환경 활성화 후 실행하세요!
- 자세한 가이드: [docs/ENVIRONMENT_SETUP.md](docs/ENVIRONMENT_SETUP.md)

## 📁 프로젝트 구조

```
Kit_Bot_RAG/
├── rag_demo.py                    # 메인 RAG 챗봇 (실행 파일)
├── create_filtered_corpus.py      # 필터링된 corpus 생성
├── data/
│   ├── corpus_filtered.csv        # 필터링된 HTML 문서 corpus
│   ├── corpus_attachments.csv     # 첨부파일 corpus
│   ├── corpus_merged.csv          # 병합된 전체 corpus
│   ├── ground_truth.csv           # 평가용 정답 데이터
│   ├── queries.txt                # 테스트 쿼리 모음
│   ├── fixtures/                  # HTML 원본 데이터
│   └── attachments/               # 첨부파일 (PDF, Word, Excel 등)
├── embeddings/
│   ├── bge_filtered.npy           # BGE 임베딩 벡터
│   ├── bm25_filtered_vectorizer.pkl  # BM25 벡터화기
│   └── bm25_filtered_vectors.pkl     # BM25 sparse 벡터
├── scripts/
│   ├── clean_corpus.py            # Corpus 정제
│   ├── create_sparse_vectors.py   # Sparse 벡터 생성
│   ├── embed_providers.py         # 임베딩 제공자
│   ├── ingest_multi.py            # Qdrant 업로드
│   ├── regenerate_embeddings.py   # 임베딩 재생성
│   ├── process_attachments.py     # 첨부파일 처리 (NEW)
│   └── merge_corpus.py            # Corpus 병합 (NEW)
└── qdrant_storage/                # Qdrant DB 저장소

```

## 🚀 사용법

### 1. RAG 챗봇 실행

**대화형 모드:**
```bash
python3 rag_demo.py
```

**단일 질문 모드:**
```bash
python3 rag_demo.py --query "생활관 식당 운영시간 알려주세요"
```

**옵션:**
- `--provider`: LLM 제공자 (openai/ollama, 기본값: openai)
- `--model`: LLM 모델 (기본값: gpt-4o-mini)
- `--top-k`: 검색할 문서 수 (기본값: 5)

### 2. 데이터 파이프라인

📌 **첨부파일 처리에 대한 자세한 가이드는 [docs/ATTACHMENTS_GUIDE.md](docs/ATTACHMENTS_GUIDE.md) 참조**

**Step 1: HTML Corpus 생성 (필터링)**
```bash
python3 create_filtered_corpus.py
```

**Step 2: 첨부파일 처리 (PDF, Word, Excel, PPT 등)**

📌 **대용량 파일 (10GB+)은 MinIO 사용을 권장합니다!**
   - [MinIO 빠른 설정 가이드 →](docs/MINIO_SETUP.md)
   - [첨부파일 상세 가이드 →](docs/ATTACHMENTS_GUIDE.md)

**방법 A: 로컬 파일 사용 (소규모 - 1GB 이하)** ⭐
```bash
# 1. 라이브러리 설치
pip install -r requirements-attachments.txt

# 2. 첨부파일을 data/attachments/ 폴더에 복사
mkdir -p data/attachments
cp ~/Downloads/*.pdf data/attachments/

# 3. 처리 실행
python3 scripts/process_attachments.py
```

**방법 B: MinIO 사용 (대규모 - 1GB+)** 🗄️
```bash
# 1. MinIO 서버 실행 (Docker)
docker run -d -p 9000:9000 -p 9001:9001 --name minio-kit \
  -e "MINIO_ROOT_USER=admin" -e "MINIO_ROOT_PASSWORD=kitbot2025!" \
  -v ~/minio-data:/data \
  quay.io/minio/minio server /data --console-address ":9001"

# 2. 웹 콘솔에서 버킷 생성 및 파일 업로드
# http://localhost:9001

# 3. .env 파일 설정
echo "MINIO_ENDPOINT=localhost:9000" >> .env
echo "MINIO_ACCESS_KEY=your_key" >> .env
echo "MINIO_SECRET_KEY=your_secret" >> .env
echo "MINIO_BUCKET=kit-attachments" >> .env

# 4. 파일 업로드 (헬퍼 스크립트)
python3 scripts/upload_to_minio.py ~/Downloads/attachments/

# 5. 처리 실행
python3 scripts/process_attachments.py --source minio
```

**Step 3: Corpus 병합**
```bash
python3 scripts/merge_corpus.py
```

**Step 4: 임베딩 생성**
```bash
python3 scripts/regenerate_embeddings.py --input data/corpus_merged.csv
```

**Step 5: Qdrant 업로드**
```bash
python3 scripts/ingest_multi.py --input data/corpus_merged.csv
```

## 📦 주요 파일 설명

- **rag_demo.py**: RAG 챗봇 메인 파일. Retrieval + Generation 수행
- **create_filtered_corpus.py**: Ground truth 기반 필터링된 HTML corpus 생성
- **scripts/process_attachments.py**: PDF, Word, Excel, PPT 등 첨부파일 텍스트 추출 및 청킹
- **scripts/merge_corpus.py**: HTML corpus와 첨부파일 corpus 병합
- **scripts/embed_providers.py**: 다양한 임베딩 모델 지원 (BGE, E5, OpenAI 등)
- **scripts/ingest_multi.py**: Qdrant 벡터 DB에 데이터 업로드

## 📎 지원하는 첨부파일 형식

- **PDF**: `.pdf`
- **Word**: `.docx`, `.doc`
- **Excel**: `.xlsx`, `.xls`
- **PowerPoint**: `.pptx`, `.ppt`
- **텍스트**: `.txt`

## 🔧 환경 설정

`.env` 파일에 다음 API 키 설정:
```
OPENAI_API_KEY=your_api_key_here
```

## 📊 성능

현재 시스템은 BGE-M3 임베딩 모델과 GPT-4o-mini를 사용하여:
- Top-5 검색 정확도 기반
- 상세하고 정확한 답변 생성
- 출처 정보 포함