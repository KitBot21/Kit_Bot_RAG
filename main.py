import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from core.rag_core import get_embed_model, get_qdrant_client

# 수명 주기 관리 (앱 켜질 때 모델 로딩)
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🤖 모델 로딩 중...")
    get_embed_model()   # 임베딩 모델 미리 로드
    get_qdrant_client() # DB 연결 미리 확인
    print("✅ 준비 완료!")
    yield
    print("🛑 서버 종료")

app = FastAPI(title="KitBot RAG Server", lifespan=lifespan)

# ---------------------------------------------------------
# [New] CORS 미들웨어 설정 (프론트엔드 연동 필수)
# ---------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    # 보안상 배포 시에는 프론트엔드 도메인(예: "http://localhost:3000")만 넣는 게 좋음
    # 개발 단계에서는 "*"로 모든 접근을 허용
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
from api.routers import chat
app.include_router(chat.router)

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    # host="0.0.0.0"은 외부 접속 허용, reload=True는 코드 수정 시 자동 재시작
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)