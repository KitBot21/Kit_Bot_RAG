# 🗄️ MinIO 빠른 설정 가이드 (11GB+ 파일용)

대용량 첨부파일(11GB)을 처리하기 위한 MinIO 설정 가이드입니다.

## ⚡ 빠른 시작 (5분 완료)

### 1단계: MinIO 서버 실행 (Docker)

```bash
# MinIO 컨테이너 실행
docker run -d \
  -p 9000:9000 \
  -p 9001:9001 \
  --name minio-kit \
  --restart unless-stopped \
  -e "MINIO_ROOT_USER=admin" \
  -e "MINIO_ROOT_PASSWORD=kitbot2025!" \
  -v ~/minio-data:/data \
  quay.io/minio/minio server /data --console-address ":9001"

# 실행 확인
docker ps | grep minio
```

**주요 포트:**
- `9000`: API 포트 (파일 업로드/다운로드)
- `9001`: 웹 콘솔 (관리 UI)

**데이터 저장 위치:**
- `~/minio-data` (호스트 디렉토리)

### 2단계: 웹 콘솔 접속 및 설정

1. **브라우저에서 접속**
   ```
   http://localhost:9001
   ```

2. **로그인**
   - Username: `admin`
   - Password: `kitbot2025!`

3. **버킷 생성**
   - 좌측 메뉴: `Buckets` → `Create Bucket`
   - Bucket Name: `kit-attachments`
   - Versioning: `Enabled` (권장 - 파일 이력 관리)
   - `Create Bucket` 클릭

4. **Access Key 생성**
   - 좌측 메뉴: `Identity` → `Service Accounts`
   - `Create Service Account` 클릭
   - Access Key와 Secret Key **반드시 저장** (다시 볼 수 없음!)
   
   예시:
   ```
   Access Key: kitbot_access_key_123
   Secret Key: kitbot_secret_key_456_very_long_string
   ```

### 3단계: 환경 변수 설정

`.env` 파일에 MinIO 설정 추가:

```bash
# OpenAI (기존)
OPENAI_API_KEY=your_openai_key

# MinIO 설정 (추가)
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=kitbot_access_key_123
MINIO_SECRET_KEY=kitbot_secret_key_456_very_long_string
MINIO_BUCKET=kit-attachments
MINIO_SECURE=false
```

### 4단계: 파일 업로드

**방법 A: 웹 UI 사용 (권장 - 간편함)**

1. MinIO 콘솔에서 `kit-attachments` 버킷 선택
2. `Upload` 버튼 클릭
3. 파일/폴더 선택 (11GB 전체 가능)
4. 업로드 진행 상황 확인

**방법 B: MinIO Client (mc) 사용 (대량 파일에 유리)**

```bash
# mc 설치
wget https://dl.min.io/client/mc/release/linux-amd64/mc
chmod +x mc
sudo mv mc /usr/local/bin/

# MinIO 서버 등록
mc alias set local http://localhost:9000 admin kitbot2025!

# 파일 업로드 (폴더 전체)
mc cp --recursive ~/Downloads/attachments/ local/kit-attachments/

# 업로드 확인
mc ls local/kit-attachments/
```

**방법 C: Python 스크립트로 업로드**

```bash
# 업로드 스크립트 실행
python3 scripts/upload_to_minio.py ~/Downloads/attachments/
```

### 5단계: 첨부파일 처리

```bash
# MinIO에서 파일 다운로드 후 처리
python3 scripts/process_attachments.py \
  --source minio \
  --minio-endpoint localhost:9000 \
  --minio-access-key kitbot_access_key_123 \
  --minio-secret-key kitbot_secret_key_456_very_long_string \
  --minio-bucket kit-attachments
```

또는 `.env` 파일 사용:

```bash
# .env에서 자동으로 읽기
python3 scripts/process_attachments.py --source minio
```

---

## 🚀 프로덕션 설정 (선택사항)

### 1. HTTPS 설정

```bash
# Let's Encrypt 인증서 사용
docker run -d \
  -p 443:9000 \
  -p 9001:9001 \
  --name minio-kit \
  -e "MINIO_ROOT_USER=admin" \
  -e "MINIO_ROOT_PASSWORD=kitbot2025!" \
  -v ~/minio-data:/data \
  -v ~/minio-certs:/root/.minio/certs \
  quay.io/minio/minio server /data --console-address ":9001"
```

### 2. 외부 접속 허용

```bash
# 방화벽 설정
sudo ufw allow 9000/tcp
sudo ufw allow 9001/tcp

# Nginx 리버스 프록시 (권장)
# /etc/nginx/sites-available/minio
server {
    listen 80;
    server_name minio.yourdomain.com;

    location / {
        proxy_pass http://localhost:9001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 3. 자동 백업

```bash
# Cron 작업으로 매일 백업
0 2 * * * mc mirror local/kit-attachments /backup/minio/
```

---

## 💾 디스크 공간 관리

### 현재 사용량 확인

```bash
# MinIO 데이터 크기
du -sh ~/minio-data

# 버킷별 크기
mc du local/kit-attachments
```

### 오래된 파일 정리

```bash
# 90일 이상 된 파일 삭제
mc rm --recursive --older-than 90d local/kit-attachments/old/
```

### 버전 관리 정책

MinIO 콘솔에서:
1. `kit-attachments` 버킷 선택
2. `Lifecycle` → `Add Lifecycle Rule`
3. 30일 후 이전 버전 삭제 설정

---

## 🔧 성능 최적화

### 대용량 파일 업로드 최적화

```bash
# 멀티파트 업로드 크기 조정 (기본 5MB → 100MB)
mc admin config set local api requests_max=1000
mc admin service restart local
```

### 네트워크 대역폭 제한

```bash
# 업로드 속도 제한 (서버 부하 방지)
mc cp --limit-upload 10MB/s ~/large-file.pdf local/kit-attachments/
```

---

## 📊 모니터링

### MinIO 콘솔 대시보드

- URL: `http://localhost:9001`
- Monitoring → Metrics
  - 저장 공간 사용량
  - API 요청 통계
  - 대역폭 사용량

### Prometheus + Grafana (고급)

```bash
# MinIO Prometheus 엔드포인트
curl http://localhost:9000/minio/v2/metrics/cluster
```

---

## 🛠️ 문제 해결

### MinIO 컨테이너 상태 확인

```bash
# 로그 확인
docker logs minio-kit

# 재시작
docker restart minio-kit

# 완전 재설치
docker stop minio-kit
docker rm minio-kit
# (위 1단계 다시 실행)
```

### 연결 오류

```bash
# MinIO 서버 응답 확인
curl http://localhost:9000/minio/health/live

# 포트 사용 확인
sudo netstat -tlnp | grep 9000
```

### 디스크 부족

```bash
# 디스크 공간 확인
df -h ~/minio-data

# 임시 파일 정리
docker system prune -a
```

---

## 🔐 보안 Best Practices

### 1. 강력한 비밀번호 사용

```bash
# 랜덤 비밀번호 생성
openssl rand -base64 32
```

### 2. Access Key 주기적 갱신

- 3개월마다 새 Service Account 생성
- 이전 키 비활성화

### 3. 네트워크 격리

```bash
# MinIO를 내부 네트워크에만 노출
docker run -d \
  --network internal \
  -p 127.0.0.1:9000:9000 \
  ...
```

### 4. 감사 로그 활성화

```bash
mc admin config set local audit webhook \
  enable=on endpoint=http://your-audit-server/api
```

---

## 📈 용량 계획

### 현재: 11GB

- MinIO 데이터: ~11GB
- 메타데이터: ~100MB
- **총 필요 공간: ~15GB** (여유분 포함)

### 예상 증가율

| 기간 | 예상 크기 | 필요 디스크 |
|------|----------|------------|
| 현재 | 11GB | 20GB |
| 6개월 | 20GB | 30GB |
| 1년 | 30GB | 50GB |
| 2년 | 50GB | 100GB |

### 권장 서버 스펙

**최소 (현재):**
- CPU: 2 cores
- RAM: 4GB
- 디스크: 50GB SSD

**권장 (1년 후):**
- CPU: 4 cores
- RAM: 8GB
- 디스크: 200GB SSD

---

## 🎯 체크리스트

설정 완료 확인:

- [ ] MinIO Docker 컨테이너 실행 중
- [ ] 웹 콘솔 접속 가능 (http://localhost:9001)
- [ ] `kit-attachments` 버킷 생성
- [ ] Service Account (Access Key) 생성
- [ ] `.env` 파일에 MinIO 설정 추가
- [ ] 첨부파일 업로드 완료 (11GB)
- [ ] `process_attachments.py` 테스트 성공
- [ ] 백업 계획 수립

---

## 📞 다음 단계

1. ✅ MinIO 서버 실행 및 파일 업로드
2. ✅ `process_attachments.py` 실행
3. ✅ `merge_corpus.py`로 corpus 병합
4. ✅ 임베딩 생성 및 Qdrant 업로드
5. ✅ RAG 챗봇으로 테스트

**예상 소요 시간:**
- MinIO 설정: 10분
- 11GB 업로드: 30-60분 (네트워크 속도에 따라)
- 파일 처리: 1-2시간 (파일 형식에 따라)
- 임베딩 생성: 30분-1시간
- **총 소요 시간: 약 3-5시간**
