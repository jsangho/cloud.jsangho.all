import asyncio
import json
import logging
import os
import sys
from contextlib import asynccontextmanager

from fastapi.responses import JSONResponse as _BaseJSONResponse


class JSONResponse(_BaseJSONResponse):
    """ensure_ascii=True로 한글을 \\uXXXX escape 처리 — 모든 클라이언트 호환."""

    def render(self, content) -> bytes:
        return json.dumps(content, ensure_ascii=True, allow_nan=False).encode("utf-8")


# 테스트 커밋용
if sys.platform == "win32":
    # Anaconda(numpy/scipy) + uvicorn --reload 종료 시 forrtl error (200) 방지
    os.environ.setdefault("FOR_DISABLE_CONSOLE_CTRL_HANDLER", "1")
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# `backend/apps/*`를 최상위 패키지로 import 하기 위한 경로 보정
# (PowerShell에서 PYTHONPATH 설정 없이도 `python -m uvicorn main:app` 실행 가능)
_APPS_DIR = os.path.join(os.path.dirname(__file__), "apps")
if _APPS_DIR not in sys.path:
    sys.path.insert(0, _APPS_DIR)

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from admin.adapter.inbound.api import (
    human_resource_router,
    langchain_router,
    pdf_loader_router,
)
from auth.adapter.inbound.api import auth_router
from auth.adapter.inbound.api.docs_gate_router import docs_gate_router
from auth.adapter.inbound.api.jwks_router import jwks_router
from core.matrix.grid_architect_graph_manager import dispose_neo4j_driver
from core.matrix.grid_oracle_database_manager import (
    attach_neon_sql_logging,
    configure_db_logging,
    dispose_engine,
    engine,
    get_db,
    init_db,
)
from core.matrix.vault_keymaker_secret_manager import get_keymaker
from heyman.adapter.inbound.api import manager_router
from kayfabe.adapter.inbound.api import kayfabe_router
from lion_king.adapter.inbound.api.v1.photo_router import photo_router
from lion_king.adapter.inbound.api.v1.receipt_router import receipt_router
from ontology.adapter.inbound.api import ontology_router
from ontology.adapter.inbound.api.v1.vision_router import vision_router
from ontology.dependencies.spam_classifier_provider import get_spam_classifier_use_case
from soccer.adapter.inbound.api import soccer_router

keymaker = get_keymaker()
logger = logging.getLogger("uvicorn.error")


class ChatRequest(BaseModel):
    """채팅 요청 본문. 사용자 메시지를 JSON으로 전달합니다."""

    message: str = Field(..., min_length=1, description="사용자 메시지")


class ChatResponse(BaseModel):
    reply: str


class SeoulWeatherResponse(BaseModel):
    city: str
    temp_c: float
    description: str
    condition_id: int


class HealthzResponse(BaseModel):
    """`/healthz` 본문. 값은 아래 셋뿐이다.

    - `ok`: DB가 **설정됐는데 안 닿는** 상태가 아니면 True
    - `db`: `ok` · `unconfigured` · `error`
    - `gemini`: `ready` · `unconfigured`
    """

    ok: bool
    db: str
    gemini: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_db_logging()
    if engine is not None:
        attach_neon_sql_logging(engine)
    try:
        await init_db()
        await get_spam_classifier_use_case().initialize()
        yield
    finally:
        await dispose_engine()
        await dispose_neo4j_driver()


app = FastAPI(
    title="Jsangho Main Page",
    lifespan=lifespan,
    default_response_class=JSONResponse,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://jsangho.cloud",
        "https://www.jsangho.cloud",
        # KAYFABE는 2026-09-30에 서브도메인으로 분리됐다. 여기 없으면 브라우저가
        # 응답을 버려서 화면이 통째로 빈다 — API 자체는 200을 준다.
        "https://kayfabe.jsangho.cloud",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(docs_gate_router)
app.include_router(jwks_router)
app.include_router(auth_router, prefix="/api")
app.include_router(kayfabe_router, prefix="/api")
app.include_router(human_resource_router, prefix="/api")
app.include_router(pdf_loader_router, prefix="/api")
app.include_router(langchain_router, prefix="/api")
app.include_router(manager_router, prefix="/api")
app.include_router(ontology_router, prefix="/api")
app.include_router(vision_router, prefix="/api")
app.include_router(photo_router, prefix="/api")
app.include_router(receipt_router, prefix="/api")
app.include_router(soccer_router, prefix="/api")


@app.middleware("http")
async def log_auth_requests(request: Request, call_next):
    """로그인 요청이 들어오면 uvicorn 터미널에 먼저 표시합니다."""
    if request.url.path == "/api/login" and request.method == "POST":
        logger.info("[API] %s %s", request.method, request.url.path)
    return await call_next(request)


@app.get("/")
def read_root():
    return {"message": "FAST API 메인 페이지 ", "docs": "/docs"}


@app.get("/healthz", response_model=HealthzResponse)
async def healthz(response: Response) -> HealthzResponse:
    """probe와 외부 uptime 감시가 함께 보는 상태 점검.

    **왜 `/` 로 안 되는가**: `k8s/30-backend.yaml`의 probe가 `tcpSocket: 8000`이라
    포트만 열려 있으면 통과한다 — 앱이 모든 요청에 500을 뿜어도 Ready로 읽힌다.
    probe를 이 경로로 돌려서 ASGI 앱이 실제로 응답하는지까지 본다.

    **DB가 안 닿아도 503을 내지 않는다.** 소비자가 둘이고 목적이 다르기 때문이다:

    - probe는 *재시작·라우팅*을 결정한다. Supabase가 한 번 끊겼다고 파드를 내리면
      단일 레플리카에서는 DB를 쓰지 않는 엔드포인트까지 같이 죽는다. 재시작으로
      고쳐지지 않는 외부 의존을 readiness에 걸지 않는다.
    - 외부 uptime 감시는 *알림*을 결정한다. 그쪽은 본문의 `"ok": true` 키워드를 보게
      해 두면 파드를 건드리지 않고도 DB 이상을 알린다.

    **`unconfigured`는 고장이 아니라 선언된 모드다.** 로컬 `.env`는 `DATABASE_URL`이
    비어 있어 `engine`이 None인 채로 기동하는 것이 정상이다(루트 CLAUDE.md). 이 값을
    실패로 세면 로컬 파드가 영영 Ready가 되지 않는다.
    """
    db = "unconfigured"
    if engine is not None:
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            db = "ok"
        except Exception:
            # 본문으로 상태를 알리는 것이 이 엔드포인트의 일이므로 예외를 올리지
            # 않는다. 대신 원인을 로그에 남긴다 — 알림을 받고 들어와서 읽을 자리다.
            logger.exception("[healthz] DB 점검 실패")
            db = "error"

    # 200을 유지하는 이유는 위 docstring에 있다. 헤더는 캐시만 막는다.
    response.headers["Cache-Control"] = "no-store"

    return HealthzResponse(
        ok=db != "error",
        db=db,
        gemini="ready" if keymaker.is_gemini_ready() else "unconfigured",
    )


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """
    JSON 본문 `{"message": "..."}` 를 받아 Gemini 답변 문자열을 반환합니다.
    """
    if not keymaker.is_gemini_ready():
        if not keymaker.get_gemini_api_key():
            raise HTTPException(
                status_code=503,
                detail="GEMINI_API_KEY가 설정되지 않았습니다. backend/.env 에 키를 넣어 주세요.",
            )
        raise HTTPException(
            status_code=503,
            detail=(
                "Gemini 패키지가 설치되지 않았습니다. "
                "backend 폴더에서 `pip install -r requirements.txt` 후 서버를 재시작하세요."
            ),
        )

    client = keymaker.get_gemini_client()
    try:
        response = client.models.generate_content(
            model=keymaker.get_gemini_model_name(),
            contents=req.message,
        )
    except Exception as e:
        # google-genai는 실패를 `APIError`로 올리고 HTTP 상태를 `code`에 담는다.
        # 옛 SDK의 `ResourceExhausted` 타입명은 더 이상 나오지 않는다.
        err = str(e)
        if getattr(e, "code", None) == 429 or "quota" in err.lower():
            raise HTTPException(
                status_code=429,
                detail=(
                    "Gemini API 무료 할당량을 초과했거나, 이 프로젝트에 무료 할당량이 "
                    "활성화되지 않았습니다(limit: 0). "
                    "1~2분 후 다시 시도하거나, "
                    "https://aistudio.google.com/apikey 에서 새 키를 발급하고 "
                    "https://ai.dev/rate-limit 에서 사용량을 확인하세요. "
                    "계속되면 Google AI Studio에서 결제(빌링) 연결 후 무료 한도가 켜집니다."
                ),
            ) from e
        raise HTTPException(
            status_code=502,
            detail=f"Gemini 호출 실패: {e!s}",
        ) from e

    # google-genai의 `.text`는 `Optional[str]`이다 — 차단·빈 응답도 예외가 아니라
    # `None`으로 온다. 그래서 아래 한 분기가 옛 SDK의 ValueError 경로까지 받는다.
    text = (response.text or "").strip()

    if not text:
        reason = None
        if getattr(response, "candidates", None):
            c0 = response.candidates[0]
            reason = getattr(c0, "finish_reason", None)
        feedback = getattr(response, "prompt_feedback", None)
        raise HTTPException(
            status_code=502,
            detail=(
                "모델이 비어 있는 응답을 반환했습니다."
                + (f" (finish_reason={reason})" if reason else "")
                + (f" prompt_feedback={feedback}" if feedback else "")
            ),
        )

    return ChatResponse(reply=text)


@app.get("/weather/seoul", response_model=SeoulWeatherResponse)
def read_seoul_weather() -> SeoulWeatherResponse:
    """OpenWeatherMap으로 서울 현재 기온·날씨를 조회합니다 (`OPENWEATHER_API_KEY`)."""
    if not keymaker.is_openweather_ready():
        raise HTTPException(
            status_code=503,
            detail="OPENWEATHER_API_KEY가 설정되지 않았습니다. backend/.env 에 키를 넣어 주세요.",
        )
    try:
        data = keymaker.get_seoul_current_weather()
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return SeoulWeatherResponse(**data)


@app.get("/db-check")
async def check_db(db: AsyncSession = Depends(get_db)):
    result = await db.execute(text("SELECT NOW()"))
    return {"db_time": str(result.scalar())}


@app.get("/doro/data")
def read_doro_data():
    raise HTTPException(
        status_code=410,
        detail="프로젝트 내부 파일(CSV) 읽기 기반 엔드포인트는 제거되었습니다.",
    )


if __name__ == "__main__":
    import uvicorn

    # Windows: --reload 시 WatchFiles가 프로세스를 끊을 때 forrtl/libifcoremd 충돌 발생
    use_reload = sys.platform != "win32"

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    config = uvicorn.Config(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=use_reload,
        loop="asyncio",
    )
    server = uvicorn.Server(config)
    try:
        asyncio.run(server.serve())
    except KeyboardInterrupt:
        logger.info("서버를 종료했습니다.")
