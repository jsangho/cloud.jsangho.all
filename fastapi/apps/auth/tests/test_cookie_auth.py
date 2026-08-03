"""액세스 토큰의 httpOnly 쿠키 전달 회귀 테스트 (하네스 §4-E, 1단계).

웹은 토큰을 URL 쿼리스트링으로 받아 localStorage에 넣고 있었다. XSS 한 번이면
토큰이 통째로 털리고, URL은 히스토리·Referer에도 남는다. 쿠키를 httpOnly로
심으면 JS가 읽을 수 없다.

**1단계는 병행 운영이다.** 쿠키를 추가로 심되 기존 URL·body 토큰을 그대로 두어,
서버와 프론트 중 한쪽만 배포돼도 로그인이 끊기지 않게 한다.
"""

from __future__ import annotations

from core.security import cookie as cookie_module
from core.security.cookie import (
    ACCESS_COOKIE_NAME,
    clear_access_cookie,
    set_access_cookie,
)
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from fastapi import FastAPI

app = FastAPI()


@app.get("/set")
def set_cookie() -> JSONResponse:
    response = JSONResponse({"ok": True})
    set_access_cookie(response, "jwt-value", max_age=900)
    return response


@app.get("/clear")
def clear_cookie() -> JSONResponse:
    response = JSONResponse({"ok": True})
    clear_access_cookie(response)
    return response


client = TestClient(app)


def _set_cookie_header() -> str:
    return client.get("/set").headers["set-cookie"]


def test_cookie_is_http_only() -> None:
    """JS가 읽을 수 있으면 쿠키로 옮긴 의미가 없다."""
    assert "httponly" in _set_cookie_header().lower()


def test_cookie_is_secure() -> None:
    """평문 http로 토큰이 흐르면 안 된다."""
    assert "secure" in _set_cookie_header().lower()


def test_cookie_is_samesite_lax() -> None:
    """프론트와 API가 같은 사이트라 lax로 충분하다. none은 CSRF 면이 넓어진다."""
    assert "samesite=lax" in _set_cookie_header().lower()


def test_cookie_carries_the_token_and_lifetime() -> None:
    header = _set_cookie_header()
    assert f"{ACCESS_COOKIE_NAME}=jwt-value" in header
    assert "max-age=900" in header.lower()


def test_clear_uses_matching_attributes() -> None:
    """지울 때 속성이 다르면 브라우저가 삭제하지 않고 쿠키가 남는다."""
    header = client.get("/clear").headers["set-cookie"].lower()
    assert f"{ACCESS_COOKIE_NAME}=" in header
    assert "httponly" in header
    assert "samesite=lax" in header


def test_cookie_is_scoped_to_the_service_domain_by_default() -> None:
    """운영에서는 `.jsangho.cloud` 하위(front·api·auth)가 쿠키를 공유해야 한다."""
    assert "domain=.jsangho.cloud" in _set_cookie_header().lower()


def test_blank_domain_produces_a_host_only_cookie(monkeypatch) -> None:
    """로컬 개발 탈출구.

    `.jsangho.cloud`가 걸려 있으면 localhost에서는 브라우저가 쿠키를 **저장조차
    하지 않는다.** `COOKIE_DOMAIN`을 비우면 호스트 전용 쿠키가 되어 개발이 가능하다.
    빈 문자열을 그대로 넘기면 유효하지 않은 도메인이 되므로 키 자체를 빼야 한다.
    """
    monkeypatch.setitem(cookie_module.COOKIE_KWARGS, "domain", "")

    header = client.get("/set").headers["set-cookie"].lower()

    assert "domain=" not in header
    assert f"{ACCESS_COOKIE_NAME}=jwt-value" in header
