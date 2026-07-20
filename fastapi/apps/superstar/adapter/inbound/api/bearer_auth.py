from __future__ import annotations

from typing import Any

import jwt

from fastapi import Header, HTTPException
from superstar.domain.services.jwt_token import decode_access_token
from superstar.domain.value_objects.role import UserRole


def require_auth(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="인증 토큰이 필요합니다.")

    token = authorization.removeprefix("Bearer ").strip()
    try:
        return decode_access_token(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=401, detail="인증 토큰이 유효하지 않거나 만료됐습니다."
        ) from exc


def require_self_or_admin(*, user_id: int, claims: dict[str, Any]) -> None:
    if claims.get("sub") == str(user_id) or claims.get("role") == UserRole.ADMIN.value:
        return
    raise HTTPException(status_code=403, detail="본인 프로필만 조회할 수 있습니다.")
