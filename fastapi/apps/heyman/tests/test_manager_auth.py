"""`/api/manager/*` 는 전부 관리자 전용이다.

Next.js `requireAdmin` 은 `api.jsangho.cloud` 직통 요청을 막지 못한다. 그래서 여기서는
진짜 RS256 서명과 `get_current_user` 를 그대로 태운다 — 인증을 오버라이드하면 잘못된
토큰 거부를 시험할 수 없다. 유스케이스만 가짜라 DB·메일·텔레그램에는 닿지 않는다.
"""

from __future__ import annotations

import base64
import json
import time
from datetime import UTC, datetime
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from core.security import dependencies as security_dependencies
from core.security import token_verifier
from core.security.dependencies import RoleChecker
from core.security.role import UserRole
from heyman.adapter.inbound.api import manager_router
from heyman.app.dtos.discord_dto import DiscordResponse
from heyman.app.dtos.judge_dto import JudgeResponse
from heyman.app.dtos.juso_dto import ContactListItem, JusoResponse
from heyman.app.dtos.receiver_dto import ReceiverItem
from heyman.app.dtos.telegram_dto import TelegramResponse
from heyman.app.dtos.watcher_dto import WatcherFilterResult, WatcherResponse
from heyman.dependencies.discord_provider import get_discord_use_case
from heyman.dependencies.email_provider import get_email_use_case
from heyman.dependencies.judge_provider import get_judge_use_case
from heyman.dependencies.juso_provider import get_juso_use_case
from heyman.dependencies.receiver_provider import get_receiver_use_case
from heyman.dependencies.telegram_provider import get_telegram_use_case
from heyman.dependencies.watcher_provider import get_watcher_use_case

_AUD = token_verifier.DEFAULT_SERVICE_AUD
_MAIL = {"from_email": "a@example.com", "subject": "s", "body": "b"}

_REQUESTS: dict[tuple[str, str], dict[str, Any]] = {
    ("POST", "/api/manager/email/faker-report"): {"json": {"to": "a@example.com"}},
    ("POST", "/api/manager/telegram/send"): {"json": {"chat_id": "1", "message": "m"}},
    ("POST", "/api/manager/receiver/receive"): {"json": _MAIL},
    ("POST", "/api/manager/watcher/filter"): {"json": _MAIL},
    ("POST", "/api/manager/juso/fileupload"): {
        "files": {
            "file": (
                "contacts.csv",
                b"Name,E-mail 1 - Value\nKim,k@example.com\n",
                "text/csv",
            )
        }
    },
}


def _discovered() -> list[tuple[str, str]]:
    """라우터에서 직접 뽑는다 — 새 경로가 생기면 자동으로 아래 시험에 들어온다."""
    found = []
    for route in manager_router.routes:
        assert isinstance(route, APIRoute)
        path = "/api" + route.path.replace("{item_id}", "1")
        found.extend((method, path) for method in sorted(route.methods))
    return found


_ROUTES = _discovered()
_ids = [f"{method} {path}" for method, path in _ROUTES]


class FakeUseCase:
    """모든 유스케이스 자리를 맡는다. 호출되면 기록만 남긴다."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def list_contacts(self) -> list[ContactListItem]:
        self.calls.append("list_contacts")
        return [ContactListItem(1, "Kim", "k@example.com", "", "")]

    async def delete_all_contacts(self) -> dict[str, int]:
        self.calls.append("delete_all_contacts")
        return {"deleted": 1}

    async def upload_contacts(self, commands: list) -> dict[str, int]:
        self.calls.append("upload_contacts")
        return {"count": len(commands)}

    async def receiver(self, cmd: object) -> dict[str, int | None]:
        self.calls.append("receiver")
        return {"id": 1}

    async def list_receiver(self) -> list[ReceiverItem]:
        self.calls.append("list_receiver")
        return [
            ReceiverItem(
                id=1,
                from_email="a@example.com",
                from_name="",
                to_email="",
                subject="s",
                body="b",
                message_id="m",
                receiver_at=datetime(2026, 11, 5, tzinfo=UTC),
                is_read=False,
            )
        ]

    async def mark_read(self, item_id: int) -> None:
        self.calls.append("mark_read")

    async def send_message(self, cmd: object) -> dict[str, str]:
        self.calls.append("send_message")
        return {"status": "ok"}

    async def send_faker_report(self, to: str, name: str = "") -> dict:
        self.calls.append("send_faker_report")
        return {"status": "ok"}

    async def filter_and_forward(self, cmd: object) -> WatcherFilterResult:
        self.calls.append("filter_and_forward")
        return WatcherFilterResult(id=1, label="ham", confidence=0.9, forwarded=True)

    async def introduce_myself(self, query: Any) -> Any:
        self.calls.append("introduce_myself")
        for cls in (
            DiscordResponse,
            JudgeResponse,
            JusoResponse,
            TelegramResponse,
            WatcherResponse,
        ):
            if type(query).__name__.removesuffix("Query") in cls.__name__:
                return cls(id=query.id, name=query.name, description="")
        raise AssertionError(type(query))


class FakeRedis:
    def __init__(self) -> None:
        self.blacklisted: set[str] = set()

    async def exists(self, key: str) -> int:
        return int(key in self.blacklisted)


def _private_pem(key: rsa.RSAPrivateKey) -> bytes:
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )


_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PUBLIC_PEM = (
    _KEY.public_key()
    .public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    .decode()
)


def _claims(roles: list[str], **overrides: Any) -> dict[str, Any]:
    now = int(time.time())
    return {
        "sub": "1",
        "aud": _AUD,
        "iat": now,
        "exp": now + 300,
        "jti": "jti-1",
        "roles": roles,
    } | overrides


def _token(roles: list[str], *, key: rsa.RSAPrivateKey = _KEY, **overrides: Any) -> str:
    return jwt.encode(_claims(roles, **overrides), _private_pem(key), algorithm="RS256")


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def redis(monkeypatch: pytest.MonkeyPatch) -> FakeRedis:
    fake = FakeRedis()
    monkeypatch.setattr(security_dependencies, "_get_redis", lambda: fake)
    monkeypatch.setattr(token_verifier, "_public_key", lambda: _PUBLIC_PEM)
    return fake


@pytest.fixture
def use_case() -> FakeUseCase:
    return FakeUseCase()


@pytest.fixture
def client(redis: FakeRedis, use_case: FakeUseCase) -> TestClient:
    app = FastAPI()
    app.include_router(manager_router, prefix="/api")
    for provider in (
        get_discord_use_case,
        get_email_use_case,
        get_judge_use_case,
        get_juso_use_case,
        get_receiver_use_case,
        get_telegram_use_case,
        get_watcher_use_case,
    ):
        app.dependency_overrides[provider] = lambda: use_case
    return TestClient(app)


def _call(client: TestClient, method: str, path: str, **kwargs: Any):
    return client.request(method, path, **(_REQUESTS.get((method, path), {}) | kwargs))


def test_route_discovery_found_the_router() -> None:
    assert ("GET", "/api/manager/juso/contacts") in _ROUTES
    assert ("POST", "/api/manager/telegram/send") in _ROUTES


@pytest.mark.parametrize("route", manager_router.routes, ids=lambda r: r.path)
def test_every_route_declares_the_admin_gate(route: APIRoute) -> None:
    gates = [
        dep.call
        for dep in route.dependant.dependencies
        if isinstance(dep.call, RoleChecker)
    ]

    assert any(UserRole.ADMIN.value in gate._allowed for gate in gates)


@pytest.mark.parametrize(("method", "path"), _ROUTES, ids=_ids)
def test_anonymous_is_rejected(
    client: TestClient, use_case: FakeUseCase, method: str, path: str
) -> None:
    assert _call(client, method, path).status_code == 401
    assert use_case.calls == []


@pytest.mark.parametrize(("method", "path"), _ROUTES, ids=_ids)
def test_regular_user_is_forbidden(
    client: TestClient, use_case: FakeUseCase, method: str, path: str
) -> None:
    response = _call(client, method, path, headers=_bearer(_token(["user"])))

    assert response.status_code == 403
    assert use_case.calls == []


@pytest.mark.parametrize(("method", "path"), _ROUTES, ids=_ids)
def test_admin_reaches_the_use_case(
    client: TestClient, use_case: FakeUseCase, method: str, path: str
) -> None:
    response = _call(client, method, path, headers=_bearer(_token(["admin"])))

    assert response.status_code == 200, response.text
    assert len(use_case.calls) == 1


def test_admin_cookie_is_accepted(client: TestClient, use_case: FakeUseCase) -> None:
    client.cookies.set("access_token", _token(["admin"]))

    assert client.get("/api/manager/receiver/list").status_code == 200
    assert use_case.calls == ["list_receiver"]


def _forged_unsigned_admin() -> str:
    def part(value: dict[str, Any]) -> str:
        raw = json.dumps(value).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    return f"{part({'alg': 'none', 'typ': 'JWT'})}.{part(_claims(['admin']))}."


@pytest.mark.parametrize(
    "token",
    [
        pytest.param(_token(["admin"], exp=int(time.time()) - 60), id="expired"),
        pytest.param(_token(["admin"], key=_OTHER_KEY), id="wrong-signature"),
        pytest.param(_token(["admin"], aud="other-service"), id="wrong-audience"),
        pytest.param(
            jwt.encode(_claims(["admin"]), "s" * 40, algorithm="HS256"), id="hs256"
        ),
        pytest.param(_forged_unsigned_admin(), id="alg-none"),
        pytest.param("not-a-jwt", id="garbage"),
    ],
)
def test_invalid_admin_tokens_are_rejected(
    client: TestClient, use_case: FakeUseCase, token: str
) -> None:
    response = client.get("/api/manager/juso/contacts", headers=_bearer(token))

    assert response.status_code == 401
    assert use_case.calls == []


def test_tampered_role_claim_breaks_the_signature(
    client: TestClient, use_case: FakeUseCase
) -> None:
    header, payload, signature = _token(["user"]).split(".")
    raw = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
    claims = json.loads(raw) | {"roles": ["admin"]}
    forged_payload = (
        base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    )

    response = client.get(
        "/api/manager/juso/contacts",
        headers=_bearer(f"{header}.{forged_payload}.{signature}"),
    )

    assert response.status_code == 401
    assert use_case.calls == []


def test_blacklisted_admin_session_is_rejected(
    client: TestClient, use_case: FakeUseCase, redis: FakeRedis
) -> None:
    redis.blacklisted.add("auth:blacklist:jti-1")

    response = client.get(
        "/api/manager/juso/contacts", headers=_bearer(_token(["admin"]))
    )

    assert response.status_code == 401
    assert use_case.calls == []


@pytest.mark.parametrize(
    "headers",
    [{"X-User-Role": "admin"}, {"X-Roles": "admin"}, {"X-Service-Token": "anything"}],
    ids=["role-header", "roles-header", "service-header"],
)
def test_client_cannot_claim_admin_with_headers(
    client: TestClient, use_case: FakeUseCase, headers: dict[str, str]
) -> None:
    assert (
        client.post(
            "/api/manager/receiver/receive", json=_MAIL, headers=headers
        ).status_code
        == 401
    )
    response = client.post(
        "/api/manager/telegram/send",
        json={"chat_id": "1", "message": "m"},
        headers=_bearer(_token(["user"])) | headers,
    )

    assert response.status_code == 403
    assert use_case.calls == []
