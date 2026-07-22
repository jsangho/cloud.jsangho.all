from __future__ import annotations

import secrets
import time
import uuid

import jwt
from core.matrix.vault_keymaker_secret_manager import get_keymaker
from core.security.token_verifier import DEFAULT_SERVICE_AUD

ACCESS_TOKEN_EXPIRES_SECONDS = 15 * 60
REFRESH_TOKEN_EXPIRES_SECONDS = 14 * 24 * 60 * 60
KID = "jsangho-auth-1"


def _private_key() -> str:
    """`JWT_PRIVATE_KEY`를 읽는 유일한 함수. 다른 곳에서 이 값을 다시 읽으면 안 된다."""
    key = get_keymaker().get_secret("JWT_PRIVATE_KEY")
    if not key:
        raise RuntimeError("JWT_PRIVATE_KEY가 설정되지 않았습니다 (.env 확인).")
    return key.replace("\\n", "\n")


def create_access_token(
    *,
    sub: str,
    roles: list[str],
    aud: str = DEFAULT_SERVICE_AUD,
    expires_seconds: int = ACCESS_TOKEN_EXPIRES_SECONDS,
) -> str:
    now = int(time.time())
    payload = {
        "sub": sub,
        "roles": roles,
        "aud": aud,
        "iat": now,
        "exp": now + expires_seconds,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, _private_key(), algorithm="RS256", headers={"kid": KID})


def create_refresh_token(*, sub: str) -> tuple[str, str]:
    """(refresh_token, jti) — refresh_token은 Redis에 저장될 불투명 문자열, JWT가 아니다."""
    jti = uuid.uuid4().hex
    refresh_token = f"{jti}.{secrets.token_urlsafe(32)}"
    return refresh_token, jti
