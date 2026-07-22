from __future__ import annotations

import os

import jwt
import redis.asyncio as redis
from core.security.role import UserRole
from core.security.token_verifier import TokenPayload, verify_token

from fastapi import Depends, HTTPException, Request

_REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
_REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
_BLACKLIST_KEY_PREFIX = "auth:blacklist"

_redis_client: redis.Redis | None = None


def _get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis(
            host=_REDIS_HOST, port=_REDIS_PORT, decode_responses=True
        )
    return _redis_client


def _extract_token(request: Request) -> str | None:
    authorization = request.headers.get("Authorization")
    if authorization and authorization.startswith("Bearer "):
        return authorization.removeprefix("Bearer ").strip()
    return request.cookies.get("access_token")


async def get_current_user(request: Request) -> TokenPayload:
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="인증 토큰이 필요합니다.")

    try:
        payload = verify_token(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=401, detail="인증 토큰이 유효하지 않거나 만료됐습니다."
        ) from exc

    if await _get_redis().exists(f"{_BLACKLIST_KEY_PREFIX}:{payload.jti}"):
        raise HTTPException(status_code=401, detail="차단된 세션입니다.")

    return payload


def require_self_or_admin(*, user_id: int, claims: TokenPayload) -> None:
    if claims.sub == str(user_id) or UserRole.ADMIN.value in claims.roles:
        return
    raise HTTPException(status_code=403, detail="본인 프로필만 조회할 수 있습니다.")


class RoleChecker:
    def __init__(self, *allowed: UserRole) -> None:
        self._allowed = {role.value for role in allowed}

    def __call__(self, user: TokenPayload = Depends(get_current_user)) -> TokenPayload:
        if not self._allowed.intersection(user.roles):
            raise HTTPException(status_code=403, detail="권한이 없습니다.")
        return user
