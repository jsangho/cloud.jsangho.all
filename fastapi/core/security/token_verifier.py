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
    # 모바일/웹 세션 구분(하네스 D-3). `aud`를 쪼개면 스포크 앱들의
    # `verify_token(aud=기본값)`이 모바일 토큰을 거부하므로 클레임으로 나눈다(§4-J).
    #
    # 옵셔널인 이유: 이 클레임 도입 이전에 발급된 토큰에는 값이 없다. 그런 토큰은
    # 만료(최대 15분)까지 `None`으로 통과시킨다 — 플랫폼 전용 엔드포인트는
    # `platform`이 정확히 일치할 때만 열리므로 None은 자연히 거부된다.
    platform: str | None = None
    device_id: str | None = None


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
        platform=claims.get("platform"),
        device_id=claims.get("device_id"),
    )
