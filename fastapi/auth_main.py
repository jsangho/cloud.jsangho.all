"""인증 게이트웨이 단독 엔트리포인트 (`apps/auth/_docs/auth-gateway-harness.md` 2.5).

`uvicorn auth_main:app`으로 단독 기동. 아직 docker-compose 서비스로는 등록하지 않았다 —
로컬 검증용. heyman/ontology 등 무거운 앱은 import하지 않는다.
"""

from __future__ import annotations

import asyncio
import os
import sys

# psycopg async는 SelectorEventLoop가 필요 — Windows 기본 ProactorEventLoop로는 DB 연결 실패 (main.py와 동일)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# `backend/apps/*`를 최상위 패키지로 import 하기 위한 경로 보정 (main.py와 동일)
_APPS_DIR = os.path.join(os.path.dirname(__file__), "apps")
if _APPS_DIR not in sys.path:
    sys.path.insert(0, _APPS_DIR)

from auth.adapter.inbound.api import auth_router
from auth.adapter.inbound.api.jwks_router import jwks_router
from fastapi import FastAPI

app = FastAPI(
    title="jsangho Auth Gateway",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.include_router(auth_router, prefix="/auth")
app.include_router(jwks_router)


@app.get("/healthz")
async def healthz():
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn

    # Windows에서 `python -m uvicorn`으로 실행하면 이벤트 루프 정책이 이미 굳어진 뒤에
    # 이 모듈이 import돼서 위쪽 WindowsSelectorEventLoopPolicy 설정이 무시된다.
    # `python auth_main.py`로 직접 실행해야 정책이 먼저 적용된다 (main.py와 동일한 이유).
    config = uvicorn.Config("auth_main:app", host="127.0.0.1", port=8001, reload=False)
    server = uvicorn.Server(config)
    asyncio.run(server.serve())
