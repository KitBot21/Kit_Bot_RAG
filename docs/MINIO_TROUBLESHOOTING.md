# 🔧 MinIO 웹 콘솔 접속 문제 해결

## ✅ 현재 상태

MinIO 서버가 정상 실행 중입니다:
- ✅ Docker 컨테이너 실행 중
- ✅ 포트 9001 리스닝 중
- ✅ HTTP 응답 정상

## 🌐 브라우저 접속 방법

### 1️⃣ 로컬 환경 (직접 서버에서 작업 중)

**접속 URL:**
```
http://localhost:9001
```

**또는:**
```
http://127.0.0.1:9001
```

### 2️⃣ 원격 환경 (SSH로 접속한 경우)

현재 SSH로 서버에 접속해서 작업 중이신 것 같습니다!

**해결 방법 A: SSH 포트 포워딩 (권장)** ⭐

```bash
# 로컬 컴퓨터에서 새 터미널 열고:
ssh -L 9001:localhost:9001 -L 9000:localhost:9000 jhlee@서버주소

# 그 다음 로컬 브라우저에서:
http://localhost:9001
```

**해결 방법 B: VS Code Remote SSH 사용**

1. VS Code에서 Remote SSH로 서버 접속
2. VS Code가 자동으로 포트 포워딩
3. VS Code 하단 "PORTS" 탭 확인
4. 9001 포트 우클릭 → "Open in Browser"

**해결 방법 C: 서버 방화벽 열기 (공개 서버인 경우)**

```bash
# 방화벽 확인
sudo ufw status

# 9000, 9001 포트 열기
sudo ufw allow 9000/tcp
sudo ufw allow 9001/tcp

# 그 다음 브라우저에서:
http://서버_IP주소:9001
```

**⚠️ 보안 주의:** 공개 IP로 열 경우 반드시 강력한 비밀번호 사용!

### 3️⃣ WSL2 환경

**Windows에서 WSL2 사용 중이라면:**

```
http://localhost:9001
```

**또는:**
```bash
# WSL2에서 Windows IP 확인
ip route | grep default | awk '{print $3}'

# 출력된 IP로 접속 (Windows 브라우저에서)
http://172.x.x.x:9001
```

---

## 🔍 진단 명령어

### 1. MinIO 컨테이너 상태 확인

```bash
docker ps | grep minio
```

**정상 출력 예시:**
```
minio-kit ... Up X minutes ... 0.0.0.0:9000-9001->9000-9001/tcp
```

### 2. MinIO 로그 확인

```bash
docker logs minio-kit --tail 20
```

**정상 출력에 포함되어야 할 내용:**
```
API: http://127.0.0.1:9000
WebUI: http://127.0.0.1:9001
```

### 3. 포트 리스닝 확인

```bash
sudo netstat -tlnp | grep 9001
# 또는
sudo ss -tlnp | grep 9001
```

**정상 출력:**
```
tcp  0  0  0.0.0.0:9001  0.0.0.0:*  LISTEN  xxxx/docker-proxy
```

### 4. HTTP 응답 테스트

```bash
curl -I http://localhost:9001
```

**정상 출력:**
```
HTTP/1.1 200 OK
Content-Type: text/html
...
```

### 5. 방화벽 확인

```bash
sudo ufw status
```

---

## 🐛 흔한 문제와 해결책

### 문제 1: "사이트에 연결할 수 없음" (Chrome)

**원인:** SSH 원격 접속 중 + 포트 포워딩 미설정

**해결:**
```bash
# 로컬 컴퓨터에서 SSH 재접속 (포트 포워딩 포함)
ssh -L 9001:localhost:9001 jhlee@서버주소

# 브라우저에서
http://localhost:9001
```

### 문제 2: "연결 시간 초과"

**원인:** 방화벽 차단

**해결:**
```bash
# 방화벽 상태 확인
sudo ufw status

# MinIO 포트 허용
sudo ufw allow 9000/tcp
sudo ufw allow 9001/tcp
sudo ufw reload
```

### 문제 3: "ERR_CONNECTION_REFUSED"

**원인:** MinIO 컨테이너 미실행

**해결:**
```bash
# 컨테이너 재시작
docker restart minio-kit

# 또는 다시 실행
docker stop minio-kit
docker rm minio-kit

docker run -d \
  -p 9000:9000 -p 9001:9001 \
  --name minio-kit \
  --restart unless-stopped \
  -e "MINIO_ROOT_USER=admin" \
  -e "MINIO_ROOT_PASSWORD=kitbot2025!" \
  -v ~/minio-data:/data \
  quay.io/minio/minio server /data --console-address ":9001"
```

### 문제 4: "This site can't provide a secure connection" (HTTPS 오류)

**원인:** `https://` 대신 `http://` 사용해야 함

**해결:**
```
❌ https://localhost:9001
✅ http://localhost:9001
```

### 문제 5: 로그인 실패 (Credentials 오류)

**원인:** 잘못된 로그인 정보

**기본 로그인 정보:**
- Username: `admin`
- Password: `kitbot2025!`

**변경한 경우:**
```bash
# 컨테이너 환경 변수 확인
docker inspect minio-kit | grep -A 5 Env

# 비밀번호 재설정
docker stop minio-kit
docker rm minio-kit

# 새 비밀번호로 재실행
docker run -d \
  -p 9000:9000 -p 9001:9001 \
  --name minio-kit \
  -e "MINIO_ROOT_USER=admin" \
  -e "MINIO_ROOT_PASSWORD=새비밀번호" \
  -v ~/minio-data:/data \
  quay.io/minio/minio server /data --console-address ":9001"
```

### 문제 6: 포트 충돌

**원인:** 9000 또는 9001 포트가 이미 사용 중

**확인:**
```bash
sudo netstat -tlnp | grep -E '9000|9001'
```

**해결:**
```bash
# 다른 포트 사용
docker run -d \
  -p 9010:9000 -p 9011:9001 \
  --name minio-kit \
  ...

# 접속: http://localhost:9011
```

---

## 🎯 빠른 체크리스트

### SSH 원격 접속 중이라면:

- [ ] SSH 포트 포워딩 설정
  ```bash
  ssh -L 9001:localhost:9001 jhlee@서버주소
  ```
- [ ] 로컬 브라우저에서 `http://localhost:9001` 접속

### 로컬 환경이라면:

- [ ] MinIO 컨테이너 실행 확인: `docker ps | grep minio`
- [ ] 포트 리스닝 확인: `sudo netstat -tlnp | grep 9001`
- [ ] `http://` 사용 (https 아님!)
- [ ] `localhost:9001` 또는 `127.0.0.1:9001` 접속

### VS Code Remote SSH 사용 시:

- [ ] VS Code로 원격 서버 접속
- [ ] 하단 "PORTS" 탭 열기
- [ ] 9001 포트 확인
- [ ] 우클릭 → "Open in Browser"

---

## 🔑 완벽한 설정 예시

### 상황 1: 로컬 개발 환경

```bash
# 1. MinIO 실행
docker run -d \
  -p 9000:9000 -p 9001:9001 \
  --name minio-kit \
  -e "MINIO_ROOT_USER=admin" \
  -e "MINIO_ROOT_PASSWORD=kitbot2025!" \
  -v ~/minio-data:/data \
  quay.io/minio/minio server /data --console-address ":9001"

# 2. 브라우저에서
# http://localhost:9001

# 3. 로그인
# Username: admin
# Password: kitbot2025!
```

### 상황 2: SSH 원격 서버

**서버에서:**
```bash
# MinIO 실행
docker run -d \
  -p 9000:9000 -p 9001:9001 \
  --name minio-kit \
  -e "MINIO_ROOT_USER=admin" \
  -e "MINIO_ROOT_PASSWORD=kitbot2025!" \
  -v ~/minio-data:/data \
  quay.io/minio/minio server /data --console-address ":9001"
```

**로컬 컴퓨터에서:**
```bash
# SSH 포트 포워딩으로 접속
ssh -L 9001:localhost:9001 -L 9000:localhost:9000 jhlee@서버주소

# 브라우저에서 (로컬 컴퓨터)
# http://localhost:9001
```

### 상황 3: VS Code Remote SSH

**VS Code에서:**
1. `Ctrl+Shift+P` → "Remote-SSH: Connect to Host"
2. 서버 접속
3. 터미널에서 MinIO 실행
4. 하단 "PORTS" 탭 클릭
5. 9001 포트 우클릭 → "Open in Browser"

---

## 📱 브라우저별 팁

### Chrome/Edge
- 시크릿 모드 시도: `Ctrl+Shift+N`
- 캐시 삭제 후 새로고침: `Ctrl+Shift+R`

### Firefox
- 프라이빗 윈도우: `Ctrl+Shift+P`
- 캐시 무시: `Ctrl+F5`

### Safari
- 프라이빗 브라우징: `Cmd+Shift+N`
- 캐시 삭제: `Cmd+Option+E`

---

## 🎓 추가 도움

### MinIO 상태 확인 스크립트

```bash
#!/bin/bash
echo "=== MinIO 상태 확인 ==="
echo ""

echo "1. 컨테이너 실행 상태:"
docker ps -a | grep minio
echo ""

echo "2. 포트 리스닝:"
sudo netstat -tlnp | grep -E '9000|9001'
echo ""

echo "3. HTTP 응답:"
curl -I http://localhost:9001 2>&1 | head -5
echo ""

echo "4. 최근 로그:"
docker logs minio-kit --tail 10
echo ""
```

저장: `check_minio.sh`
```bash
chmod +x check_minio.sh
./check_minio.sh
```

---

## 💡 요약

**가장 흔한 원인: SSH 원격 접속 + 포트 포워딩 미설정**

**해결:**
```bash
# 로컬 컴퓨터에서
ssh -L 9001:localhost:9001 jhlee@서버주소

# 브라우저
http://localhost:9001

# 로그인
admin / kitbot2025!
```

그래도 안 되면:
1. `docker logs minio-kit` 확인
2. `curl http://localhost:9001` 테스트
3. 방화벽 확인
4. 다른 브라우저 시도
