# 🤖 KIT Bot 웹 데모 사용 가이드

## 📍 접속 방법

### 현재 컴퓨터에서 접속
```
http://localhost:5000
http://127.0.0.1:5000
```

### 같은 네트워크의 다른 컴퓨터에서 접속
```
http://202.31.202.216:5000
```

> **참고**: IP 주소는 서버 실행 시 터미널에 표시됩니다.

---

## 🚀 서버 실행

### 1. 가상환경 활성화 + 서버 시작
```bash
cd /home/jhlee/Kit_Bot_RAG
source .venv/bin/activate
python3 app.py
```

### 2. 백그라운드 실행 (nohup)
```bash
cd /home/jhlee/Kit_Bot_RAG
source .venv/bin/activate
nohup python3 app.py > server.log 2>&1 &
```

서버 종료:
```bash
# 프로세스 찾기
ps aux | grep app.py

# 종료
kill <PID>
```

---

## 🔥 방화벽 설정 (필요시)

다른 컴퓨터에서 접속이 안 되면 방화벽 포트를 열어주세요:

```bash
# 자동 스크립트 실행
./open_firewall.sh

# 또는 수동으로:
sudo ufw allow 5000/tcp
sudo ufw status
```

---

## 💡 주요 기능

### 1. 채팅
- 질문 입력창에 질문 입력
- `Enter` 키 또는 `전송` 버튼 클릭
- AI가 답변 생성 (보통 5-10초 소요)

### 2. 샘플 질문
처음 접속 시 4개의 샘플 질문이 표시됩니다:
- 🍽️ 생활관 식사 시간 알려주세요
- 🚌 통학버스 노선 정보 주세요
- 📚 전공 변경 어떻게 하나요?
- 📖 도서관 운영 시간 궁금해요

클릭하면 바로 질문이 전송됩니다.

### 3. 참고 문서
답변 하단에 참고한 문서 정보가 표시됩니다:
- 문서 제목
- 유사도 점수 (%)

### 4. 대화 삭제
우측 상단 `🗑️ 대화 삭제` 버튼으로 대화 내역을 초기화할 수 있습니다.

---

## 🎨 UI 특징

### 디자인
- **그라데이션 배경**: 보라색 계열
- **사용자 메시지**: 파란색 말풍선 (우측)
- **AI 답변**: 흰색 말풍선 + 녹색 테두리 (좌측)
- **반응형**: 모바일, 태블릿, 데스크톱 모두 지원

### 애니메이션
- 메시지 등장 시 Fade-in 효과
- 버튼 호버 시 들어 올려지는 효과
- 로딩 시 회전 애니메이션
- 부드러운 스크롤

---

## 🛠️ API 엔드포인트

### POST `/api/chat`
채팅 메시지 전송

**요청**:
```json
{
  "query": "생활관 식사 시간 알려주세요"
}
```

**응답**:
```json
{
  "success": true,
  "answer": "생활관 식사 시간은...",
  "contexts": [
    {
      "title": "생활관 안내",
      "text": "...",
      "similarity": 0.85
    }
  ],
  "session_id": "uuid"
}
```

### GET `/api/history`
대화 이력 조회

**응답**:
```json
{
  "success": true,
  "history": [
    {
      "timestamp": "2025-11-04T22:00:00",
      "query": "...",
      "answer": "...",
      "contexts": [...]
    }
  ]
}
```

### POST `/api/clear`
대화 이력 삭제

**응답**:
```json
{
  "success": true,
  "message": "대화 이력이 삭제되었습니다."
}
```

### GET `/api/health`
서버 상태 확인

**응답**:
```json
{
  "success": true,
  "status": "healthy",
  "model": "BAAI/bge-m3",
  "llm": "gpt-4o-mini"
}
```

---

## 📱 모바일 접속

### QR 코드 생성 (선택)
```bash
# qrencode 설치
sudo apt-get install qrencode

# QR 코드 생성
qrencode -t ANSI "http://202.31.202.216:5000"
```

스마트폰으로 QR 코드를 스캔하면 바로 접속됩니다!

---

## 🔧 트러블슈팅

### 1. 다른 컴퓨터에서 접속 안 됨
**원인**: 방화벽이 5000 포트를 차단

**해결**:
```bash
sudo ufw allow 5000/tcp
sudo ufw reload
```

### 2. "서버 연결 실패" 오류
**원인**: 서버가 실행 중이지 않음

**해결**:
```bash
# 서버 실행 확인
ps aux | grep app.py

# 없으면 다시 실행
python3 app.py
```

### 3. 답변이 너무 느림
**원인**: LLM 생성 시간 (평균 7초)

**해결**:
- FAQ 캐싱 구현 (향후 업데이트)
- 스트리밍 응답 구현 (향후 업데이트)

### 4. "ModuleNotFoundError: No module named 'flask'"
**원인**: 가상환경 미활성화 또는 패키지 미설치

**해결**:
```bash
source .venv/bin/activate
pip install flask flask-cors
```

---

## 🌐 외부 인터넷 공개 (선택)

### ngrok 사용 (간편)
```bash
# ngrok 설치
wget https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz
tar xvzf ngrok-v3-stable-linux-amd64.tgz
sudo mv ngrok /usr/local/bin/

# 인증 (ngrok.com에서 가입 후 토큰 발급)
ngrok config add-authtoken <YOUR_TOKEN>

# 터널 생성
ngrok http 5000
```

그러면 다음과 같은 공개 URL이 생성됩니다:
```
https://1234-56-78-90-12.ngrok.io → http://localhost:5000
```

이 URL을 전 세계 어디서든 접속 가능합니다!

---

## 📊 성능 정보

### 응답 시간
- **Retrieval**: 평균 47ms (매우 빠름)
- **Generation**: 평균 7.1초 (LLM 처리 시간)
- **전체**: 평균 7.2초

### 품질
- **Retrieval Top-5 정확도**: 72.5%
- **Generation 품질**: 4.75/5.0 (A등급)
  - 정확성: 4.80/5.0
  - 관련성: 5.00/5.0
  - 완성도: 4.80/5.0
  - 근거성: 4.40/5.0

---

## 📝 로그 확인

### 실시간 로그 (터미널)
```bash
# 터미널에서 직접 실행 시
python3 app.py

# 백그라운드 실행 시
tail -f server.log
```

### 로그 예시
```
[22:02:00] 질문: 생활관 식사 시간 알려주세요
[22:02:05] 응답 완료

127.0.0.1 - - [04/Nov/2025 22:02:05] "POST /api/chat HTTP/1.1" 200 -
```

---

## 🎯 추천 질문 예시

### 학사 관련
- "전공 변경 어떻게 하나요?"
- "학점은 어떻게 계산되나요?"
- "여름방학 때 수업 들을 수 있어요?"
- "복수전공 신청 방법 알려주세요"

### 생활관
- "생활관 식사 시간 알려주세요"
- "생활관비는 얼마예요?"
- "기숙사 신청 기간이 언제인가요?"

### 교통
- "통학버스 노선 정보 주세요"
- "버스 예약은 언제까지 가능한가요?"
- "통학버스는 몇 시에 출발하나요?"

### 시설
- "도서관 운영 시간 궁금해요"
- "체육관 이용 방법 알려주세요"

---

## 🚀 프로덕션 배포 (향후)

현재는 개발 서버(`Flask debug mode`)로 실행 중입니다.  
실제 배포 시에는 다음 방법을 권장합니다:

### Gunicorn 사용
```bash
# Gunicorn 설치
pip install gunicorn

# 프로덕션 서버 실행
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Nginx + Gunicorn
```nginx
# /etc/nginx/sites-available/kitbot
server {
    listen 80;
    server_name kitbot.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

**작성자**: GitHub Copilot  
**버전**: 1.0  
**최종 수정**: 2025-11-04
