from __future__ import annotations

from urllib.parse import urlencode

from core.matrix.grid_oracle_database_manager import get_db
from core.matrix.vault_keymaker_secret_manager import get_keymaker
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from superstar.app.ports.input.bruce_wayne import BruceWayneUseCase
from superstar.domain.services.jwt_token import create_access_token
from superstar.domain.value_objects.role import UserRole

bruce_wayne_router = APIRouter(tags=["bruce-wayne"])


def get_bruce_wayne(db: AsyncSession = Depends(get_db)) -> BruceWayneUseCase:
    from superstar.adapter.outbound.kakao_oauth_client import KakaoOAuthClient
    from superstar.adapter.outbound.pg.clark_kent_pg_repository import (
        ClarkKentPgRepository,
    )
    from superstar.app.use_cases.bruce_wayne_interactor import BruceWayneInteractor

    return BruceWayneInteractor(KakaoOAuthClient(), ClarkKentPgRepository(db))


@bruce_wayne_router.get("/auth/kakao/login")
async def kakao_login(
    next_path: str = Query(default="/", alias="next"),
    use_case: BruceWayneUseCase = Depends(get_bruce_wayne),
):
    return RedirectResponse(use_case.build_authorize_url(next_path=next_path))


@bruce_wayne_router.get("/auth/kakao/callback")
async def kakao_callback(
    code: str,
    state: str = Query(default="/"),
    use_case: BruceWayneUseCase = Depends(get_bruce_wayne),
):
    user = await use_case.login_with_kakao(code=code)
    token = create_access_token(
        user_id=user.id,
        login_id=user.login_id or "",
        nickname=user.nickname,
        email=user.email,
        role=UserRole(user.role).value,
    )

    frontend_url = get_keymaker().get_secret("FRONTEND_URL", "http://localhost:3000")
    next_path = state if state.startswith("/") else "/"
    params = urlencode({"token": token, "next": next_path})
    return RedirectResponse(f"{frontend_url}/login/oauth-callback?{params}")
