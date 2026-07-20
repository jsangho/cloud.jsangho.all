from __future__ import annotations

import time
from typing import Any

import jwt
from core.matrix.vault_keymaker_secret_manager import get_keymaker

ALGORITHM = "HS256"
EXPIRES_SECONDS = 60 * 60 * 24 * 7  # 7일


def _secret_key() -> str:
    return get_keymaker().get_secret("JWT_SECRET_KEY", "kayfabe-dev-secret-change-me")


def create_access_token(
    *, user_id: int, login_id: str, nickname: str, email: str, role: str
) -> str:
    payload = {
        "sub": str(user_id),
        "loginId": login_id,
        "nickname": nickname,
        "email": email,
        "role": role,
        "exp": int(time.time()) + EXPIRES_SECONDS,
    }
    return jwt.encode(payload, _secret_key(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, _secret_key(), algorithms=[ALGORITHM])
