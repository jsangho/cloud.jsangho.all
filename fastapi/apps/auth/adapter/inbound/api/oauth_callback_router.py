from __future__ import annotations

from urllib.parse import urlencode

from core.matrix.vault_keymaker_secret_manager import get_keymaker
from core.security.cookie import set_access_cookie
from core.security.role import UserRole
from fastapi.responses import RedirectResponse

from auth.adapter.outbound.redis.refresh_token_repository import RefreshTokenRepository
from auth.app.ports.input.oauth_login_use_case import OAuthLoginUseCase
from auth.dependencies.auth_provider import (
    get_google_login_use_case,
    get_kakao_login_use_case,
    get_naver_login_use_case,
    get_refresh_token_repository,
)
from auth.domain.services.token_issuer import (
    ACCESS_TOKEN_EXPIRES_SECONDS,
    REFRESH_TOKEN_EXPIRES_SECONDS,
    create_access_token,
    create_refresh_token,
)
from fastapi import APIRouter, Depends, HTTPException, Query

oauth_callback_router = APIRouter(tags=["auth-oauth-callback"])


async def _complete_login(
    *,
    code: str,
    state: str,
    use_case: OAuthLoginUseCase,
    refresh_repo: RefreshTokenRepository,
) -> RedirectResponse:
    """`state` 검증 → 코드 교환 → 토큰 발급 → 프론트로 리다이렉트.

    **`state`를 먼저 검증한다.** 카카오에 코드를 교환하기 전에 막아야 CSRF 공격이
    외부 호출조차 일으키지 못한다.
    """
    next_path = await use_case.resolve_next_path(state=state)
    if next_path is None:
        # 만료됐거나(5분) 위조됐거나 이미 쓰인 state.
        raise HTTPException(
            status_code=400, detail="로그인 요청이 만료됐습니다. 다시 시도해 주세요."
        )

    user = await use_case.login(code=code)
    role = UserRole(user.role)
    token = create_access_token(sub=str(user.id), roles=[role.value])

    # 리프레시 토큰은 발급·저장만 하고 **URL에는 싣지 않는다.**
    # 프론트(`www`)는 이 값을 읽는 코드가 없어 쓰이지도 않았는데, 쿼리스트링에
    # 실리는 바람에 14일짜리 토큰이 브라우저 히스토리·Referer·중간 로그에 남았다.
    # 웹에 리프레시를 도입할 때는 httpOnly 쿠키로 내려보낸다(하네스 §4-E).
    _, jti = create_refresh_token(sub=str(user.id))
    await refresh_repo.store(
        sub=str(user.id), jti=jti, ttl_seconds=REFRESH_TOKEN_EXPIRES_SECONDS
    )

    frontend_url = get_keymaker().get_secret("FRONTEND_URL", "http://localhost:3000")
    # **토큰을 URL에 싣지 않는다.** 쿼리스트링은 브라우저 히스토리·Referer 헤더·
    # 중간 서버 로그에 그대로 남는다. 액세스 토큰은 아래 httpOnly 쿠키로만 간다.
    params = urlencode({"next": next_path})
    response = RedirectResponse(f"{frontend_url}/login/oauth-callback?{params}")
    set_access_cookie(response, token, max_age=ACCESS_TOKEN_EXPIRES_SECONDS)
    return response


@oauth_callback_router.get("/auth/google/login")
async def google_login(
    next_path: str = Query(default="/", alias="next"),
    use_case: OAuthLoginUseCase = Depends(get_google_login_use_case),
):
    return RedirectResponse(await use_case.build_authorize_url(next_path=next_path))


@oauth_callback_router.get("/auth/google/callback")
async def google_callback(
    code: str,
    state: str = Query(default=""),
    use_case: OAuthLoginUseCase = Depends(get_google_login_use_case),
    refresh_repo: RefreshTokenRepository = Depends(get_refresh_token_repository),
):
    return await _complete_login(
        code=code, state=state, use_case=use_case, refresh_repo=refresh_repo
    )


@oauth_callback_router.get("/auth/kakao/login")
async def kakao_login(
    next_path: str = Query(default="/", alias="next"),
    use_case: OAuthLoginUseCase = Depends(get_kakao_login_use_case),
):
    return RedirectResponse(await use_case.build_authorize_url(next_path=next_path))


@oauth_callback_router.get("/auth/kakao/callback")
async def kakao_callback(
    code: str,
    state: str = Query(default=""),
    use_case: OAuthLoginUseCase = Depends(get_kakao_login_use_case),
    refresh_repo: RefreshTokenRepository = Depends(get_refresh_token_repository),
):
    return await _complete_login(
        code=code, state=state, use_case=use_case, refresh_repo=refresh_repo
    )


@oauth_callback_router.get("/auth/naver/login")
async def naver_login(
    next_path: str = Query(default="/", alias="next"),
    use_case: OAuthLoginUseCase = Depends(get_naver_login_use_case),
):
    return RedirectResponse(await use_case.build_authorize_url(next_path=next_path))


@oauth_callback_router.get("/auth/naver/callback")
async def naver_callback(
    code: str,
    state: str = Query(default=""),
    use_case: OAuthLoginUseCase = Depends(get_naver_login_use_case),
    refresh_repo: RefreshTokenRepository = Depends(get_refresh_token_repository),
):
    return await _complete_login(
        code=code, state=state, use_case=use_case, refresh_repo=refresh_repo
    )
