from __future__ import annotations

from urllib.parse import urlencode

from core.entities.user_model import UserModel
from core.matrix.vault_keymaker_secret_manager import get_keymaker
from core.security.role import UserRole

from auth.adapter.outbound.redis.refresh_token_repository import RefreshTokenRepository
from auth.app.ports.input.oauth_login_use_case import OAuthLoginUseCase
from auth.dependencies.auth_provider import (
    get_google_login_use_case,
    get_kakao_login_use_case,
    get_naver_login_use_case,
    get_refresh_token_repository,
)
from auth.domain.services.token_issuer import (
    REFRESH_TOKEN_EXPIRES_SECONDS,
    create_access_token,
    create_refresh_token,
)
from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse

oauth_callback_router = APIRouter(tags=["auth-oauth-callback"])


async def _issue_and_redirect(
    user: UserModel, state: str, refresh_repo: RefreshTokenRepository
) -> RedirectResponse:
    role = UserRole(user.role)
    token = create_access_token(sub=str(user.id), roles=[role.value])
    refresh_token, jti = create_refresh_token(sub=str(user.id))
    await refresh_repo.store(
        sub=str(user.id), jti=jti, ttl_seconds=REFRESH_TOKEN_EXPIRES_SECONDS
    )

    frontend_url = get_keymaker().get_secret("FRONTEND_URL", "http://localhost:3000")
    next_path = state if state.startswith("/") else "/"
    params = urlencode(
        {"token": token, "refreshToken": refresh_token, "next": next_path}
    )
    return RedirectResponse(f"{frontend_url}/login/oauth-callback?{params}")


@oauth_callback_router.get("/auth/google/login")
async def google_login(
    next_path: str = Query(default="/", alias="next"),
    use_case: OAuthLoginUseCase = Depends(get_google_login_use_case),
):
    return RedirectResponse(use_case.build_authorize_url(next_path=next_path))


@oauth_callback_router.get("/auth/google/callback")
async def google_callback(
    code: str,
    state: str = Query(default="/"),
    use_case: OAuthLoginUseCase = Depends(get_google_login_use_case),
    refresh_repo: RefreshTokenRepository = Depends(get_refresh_token_repository),
):
    user = await use_case.login(code=code)
    return await _issue_and_redirect(user, state, refresh_repo)


@oauth_callback_router.get("/auth/kakao/login")
async def kakao_login(
    next_path: str = Query(default="/", alias="next"),
    use_case: OAuthLoginUseCase = Depends(get_kakao_login_use_case),
):
    return RedirectResponse(use_case.build_authorize_url(next_path=next_path))


@oauth_callback_router.get("/auth/kakao/callback")
async def kakao_callback(
    code: str,
    state: str = Query(default="/"),
    use_case: OAuthLoginUseCase = Depends(get_kakao_login_use_case),
    refresh_repo: RefreshTokenRepository = Depends(get_refresh_token_repository),
):
    user = await use_case.login(code=code)
    return await _issue_and_redirect(user, state, refresh_repo)


@oauth_callback_router.get("/auth/naver/login")
async def naver_login(
    next_path: str = Query(default="/", alias="next"),
    use_case: OAuthLoginUseCase = Depends(get_naver_login_use_case),
):
    return RedirectResponse(use_case.build_authorize_url(next_path=next_path))


@oauth_callback_router.get("/auth/naver/callback")
async def naver_callback(
    code: str,
    state: str = Query(default="/"),
    use_case: OAuthLoginUseCase = Depends(get_naver_login_use_case),
    refresh_repo: RefreshTokenRepository = Depends(get_refresh_token_repository),
):
    user = await use_case.login(code=code)
    return await _issue_and_redirect(user, state, refresh_repo)
