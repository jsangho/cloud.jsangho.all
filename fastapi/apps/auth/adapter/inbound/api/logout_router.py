from __future__ import annotations

import time

from core.security.cookie import clear_access_cookie
from core.security.dependencies import get_current_user
from core.security.token_verifier import TokenPayload

from auth.adapter.outbound.redis.refresh_token_repository import RefreshTokenRepository
from auth.dependencies.auth_provider import get_refresh_token_repository
from fastapi import APIRouter, Depends, Response

logout_router = APIRouter(tags=["auth-logout"])


@logout_router.post("/logout")
async def logout(
    response: Response,
    user: TokenPayload = Depends(get_current_user),
    refresh_repo: RefreshTokenRepository = Depends(get_refresh_token_repository),
):
    await refresh_repo.revoke_all_for_sub(sub=user.sub)
    remaining_ttl = max(user.exp - int(time.time()), 0)
    await refresh_repo.blacklist_access_token(jti=user.jti, ttl_seconds=remaining_ttl)
    # 서버 세션을 끊었으니 브라우저에 남은 쿠키도 지운다.
    clear_access_cookie(response)
    return {"message": "로그아웃됐습니다."}
