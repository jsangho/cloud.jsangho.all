from __future__ import annotations

from urllib.parse import urlencode

from core.matrix.grid_oracle_database_manager import get_db
from core.matrix.vault_keymaker_secret_manager import get_keymaker
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from superstar.app.ports.input.peter_parker import PeterParkerUseCase
from superstar.domain.services.jwt_token import create_access_token
from superstar.domain.value_objects.role import UserRole

peter_parker_router = APIRouter(tags=["peter-parker"])


def get_peter_parker(db: AsyncSession = Depends(get_db)) -> PeterParkerUseCase:
    from superstar.adapter.outbound.naver_oauth_client import NaverOAuthClient
    from superstar.adapter.outbound.pg.clark_kent_pg_repository import (
        ClarkKentPgRepository,
    )
    from superstar.app.use_cases.peter_parker_interactor import PeterParkerInteractor

    return PeterParkerInteractor(NaverOAuthClient(), ClarkKentPgRepository(db))


@peter_parker_router.get("/auth/naver/login")
async def naver_login(
    next_path: str = Query(default="/", alias="next"),
    use_case: PeterParkerUseCase = Depends(get_peter_parker),
):
    return RedirectResponse(use_case.build_authorize_url(next_path=next_path))


@peter_parker_router.get("/auth/naver/callback")
async def naver_callback(
    code: str,
    state: str = Query(default="/"),
    use_case: PeterParkerUseCase = Depends(get_peter_parker),
):
    user = await use_case.login_with_naver(code=code)
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
