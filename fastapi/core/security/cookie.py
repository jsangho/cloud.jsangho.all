from __future__ import annotations

import os

from fastapi import Response

ACCESS_COOKIE_NAME = "access_token"

# 도메인을 비우면 **호스트 전용 쿠키**가 된다. 로컬 개발(localhost:3000 ↔ 127.0.0.1:8001)
# 에서는 `.jsangho.cloud`가 걸리면 쿠키가 저장 자체가 되지 않으므로 비워 쓴다.
_COOKIE_DOMAIN = os.environ.get("COOKIE_DOMAIN", ".jsangho.cloud")

# `secure=True`면 https에서만 전송된다. 로컬 http 개발에서는 꺼야 하지만,
# 운영에서 꺼지면 평문으로 토큰이 흐르므로 기본값은 켜 둔다.
_COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "true").lower() != "false"

COOKIE_KWARGS: dict[str, object] = {
    "domain": _COOKIE_DOMAIN,
    "secure": _COOKIE_SECURE,
    "httponly": True,
    # 프론트(jsangho.cloud)와 API(api·auth.jsangho.cloud)는 같은 사이트라
    # lax로도 XHR에 실려 간다. none은 CSRF 노출면이 넓어져 쓰지 않는다.
    "samesite": "lax",
}


def _cookie_kwargs() -> dict[str, object]:
    """도메인이 비어 있으면 아예 넘기지 않는다 (빈 문자열은 유효한 도메인이 아니다)."""
    kwargs = dict(COOKIE_KWARGS)
    if not kwargs.get("domain"):
        kwargs.pop("domain", None)
    return kwargs


def set_access_cookie(response: Response, token: str, *, max_age: int) -> None:
    """액세스 토큰을 httpOnly 쿠키로 심는다.

    httpOnly라 JS가 읽을 수 없다 — XSS로 토큰이 통째로 털리는 경로를 막는 것이
    목적이다. 대신 프론트는 토큰을 직접 다루지 못하므로 `/auth/me`로 신원을 묻는다.
    """
    response.set_cookie(ACCESS_COOKIE_NAME, token, max_age=max_age, **_cookie_kwargs())


def clear_access_cookie(response: Response) -> None:
    """로그아웃. `set_cookie`와 **같은 속성**으로 지워야 브라우저가 실제로 삭제한다."""
    kwargs = _cookie_kwargs()
    response.delete_cookie(
        ACCESS_COOKIE_NAME,
        domain=kwargs.get("domain"),  # type: ignore[arg-type]
        secure=bool(kwargs["secure"]),
        httponly=True,
        samesite="lax",
    )
