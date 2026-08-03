"""프록시 뒤 클라이언트 IP 추출 회귀 테스트.

이 스택은 cloudflared 터널 뒤라 `request.client.host`가 항상 터널 컨테이너의
내부 IP로 찍힌다. 그 값으로 감사 로그를 남기면 모든 요청이 같은 IP로 보인다.
"""

from __future__ import annotations

import pytest
from core.security.client_ip import client_ip
from fastapi.testclient import TestClient

from fastapi import FastAPI, Request

app = FastAPI()


@app.get("/whoami")
def whoami(request: Request) -> dict[str, str]:
    return {"ip": client_ip(request)}


client = TestClient(app)


def test_cloudflare_header_wins() -> None:
    """터널을 쓰면 CF-Connecting-IP에 원본이 들어온다."""
    r = client.get(
        "/whoami",
        headers={"CF-Connecting-IP": "203.0.113.7", "X-Forwarded-For": "198.51.100.9"},
    )
    assert r.json()["ip"] == "203.0.113.7"


def test_forwarded_for_takes_the_first_entry() -> None:
    """맨 앞이 원본 클라이언트다. 뒤쪽은 거쳐온 프록시들이라 쓰면 안 된다."""
    r = client.get(
        "/whoami", headers={"X-Forwarded-For": "203.0.113.7, 172.28.0.3, 10.0.0.1"}
    )
    assert r.json()["ip"] == "203.0.113.7"


def test_falls_back_to_socket_peer() -> None:
    """프록시 헤더가 없으면(직접 연결) 소켓 상대 주소를 쓴다."""
    assert client.get("/whoami").json()["ip"] == "testclient"


@pytest.mark.parametrize("blank", ["", "   ", ",", " , "])
def test_blank_headers_fall_through(blank: str) -> None:
    """빈 헤더를 IP로 착각해 빈 문자열을 저장하면 안 된다."""
    r = client.get("/whoami", headers={"X-Forwarded-For": blank})
    assert r.json()["ip"] == "testclient"


def test_cloudflare_header_is_trimmed() -> None:
    r = client.get("/whoami", headers={"CF-Connecting-IP": "  203.0.113.7  "})
    assert r.json()["ip"] == "203.0.113.7"
