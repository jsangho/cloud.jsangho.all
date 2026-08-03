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

# 플랫폼별 리프레시 수명(하네스 §5.3). 모바일은 재로그인 비용이 커서 더 길다.
REFRESH_TTL_BY_PLATFORM = {
    "mobile": 60 * 24 * 60 * 60,
    "web": 14 * 24 * 60 * 60,
}


def refresh_ttl_seconds(platform: str) -> int:
    return REFRESH_TTL_BY_PLATFORM.get(platform, REFRESH_TOKEN_EXPIRES_SECONDS)


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
    platform: str | None = None,
    device_id: str | None = None,
) -> str:
    """`aud`는 플랫폼별로 쪼개지 않는다(§4-J) — 구분은 `platform` 클레임이 맡는다.

    `aud`를 나누면 스포크 앱들의 `verify_token(aud=기본값)`이 모바일 토큰을 전부 거부한다.
    """
    now = int(time.time())
    payload: dict[str, object] = {
        "sub": sub,
        "roles": roles,
        "aud": aud,
        "iat": now,
        "exp": now + expires_seconds,
        "jti": uuid.uuid4().hex,
    }
    if platform is not None:
        payload["platform"] = platform
    if device_id is not None:
        payload["device_id"] = device_id
    return jwt.encode(payload, _private_key(), algorithm="RS256", headers={"kid": KID})


def create_refresh_token(*, sub: str = "") -> tuple[str, str]:
    """(refresh_token, jti) — refresh_token은 Redis에 저장될 불투명 문자열, JWT가 아니다.

    `sub`는 토큰에 들어가지 않는다(호출부 가독성용 잔여 인자). 회전 시점에는 아직
    소유자를 모르므로 생략할 수 있어야 한다.
    """
    jti = uuid.uuid4().hex
    refresh_token = f"{jti}.{secrets.token_urlsafe(32)}"
    return refresh_token, jti
