from __future__ import annotations

import os
from dataclasses import dataclass, field

import jwt
from core.matrix.vault_keymaker_secret_manager import get_keymaker

DEFAULT_SERVICE_AUD = os.environ.get("SERVICE_AUD", "jsangho-api")


@dataclass(frozen=True)
class TokenPayload:
    sub: str
    aud: str
    exp: int
    iat: int
    jti: str
    roles: list[str] = field(default_factory=list)


def _public_key() -> str:
    """`JWT_PUBLIC_KEY`만 읽는다 — 이 파일에 개인키 참조가 생기면 절대 규칙 위반."""
    key = get_keymaker().get_secret("JWT_PUBLIC_KEY")
    if not key:
        raise RuntimeError("JWT_PUBLIC_KEY가 설정되지 않았습니다 (.env 확인).")
    return key.replace("\\n", "\n")


def verify_token(token: str, *, aud: str = DEFAULT_SERVICE_AUD) -> TokenPayload:
    claims = jwt.decode(token, _public_key(), algorithms=["RS256"], audience=aud)
    return TokenPayload(
        sub=claims["sub"],
        roles=list(claims.get("roles", [])),
        aud=claims["aud"],
        exp=claims["exp"],
        iat=claims["iat"],
        jti=claims["jti"],
    )
