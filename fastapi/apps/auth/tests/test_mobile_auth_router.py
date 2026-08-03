"""라우터 계층 계약 테스트 — HTTP 표면이 하네스 §7과 일치하는지 본다.

유스케이스 테스트는 로직만 본다. 여기서는 **Flutter가 실제로 받는 JSON**을 확인한다:
필드 별칭이 camelCase인지, 플랫폼 가드가 실제로 막는지, 실패가 401로 번역되는지.
한쪽만 바뀌면 앱이 조용히 깨지는 지점이라 별도로 고정한다.
"""

from __future__ import annotations

import pytest
from core.security.dependencies import get_current_user
from core.security.token_verifier import TokenPayload
from fastapi.testclient import TestClient

from auth.adapter.inbound.api.mobile_auth_router import mobile_auth_router
from auth.app.dtos.mobile_auth_dto import (
    MobileDeviceDto,
    MobileDeviceSessionDto,
    MobileLoginDto,
    MobileSessionDto,
    MobileUserDto,
)
from auth.app.ports.input.mobile_auth_use_case import MobileAuthUseCase
from auth.app.ports.output.session_store import (
    SessionNotFoundError,
    SessionReuseDetectedError,
)
from auth.dependencies.auth_provider import get_mobile_auth_use_case
from fastapi import FastAPI


class FakeUseCase(MobileAuthUseCase):
    def __init__(self, *, refresh_error: Exception | None = None) -> None:
        self.refresh_error = refresh_error
        self.calls: list[str] = []

    async def login_with_kakao(
        self, *, code: str, redirect_uri: str, device: MobileDeviceDto
    ) -> MobileLoginDto:
        self.calls.append(f"login:{device.device_id}:{device.os}")
        return MobileLoginDto(
            token="access-jwt",
            refresh_token="refresh-opaque",
            expires_in=900,
            user=MobileUserDto(user_id=7, nickname="홍길동", email=None, role="user"),
        )

    async def refresh(self, *, refresh_token: str) -> MobileSessionDto:
        if self.refresh_error is not None:
            raise self.refresh_error
        return MobileSessionDto(
            token="access-2", refresh_token="refresh-2", expires_in=900
        )

    async def logout(
        self, *, user_id: str, refresh_token: str, access_jti: str, access_exp: int
    ) -> None:
        self.calls.append(f"logout:{user_id}")

    async def logout_all(
        self, *, user_id: str, access_jti: str, access_exp: int
    ) -> None:
        self.calls.append(f"logout_all:{user_id}")

    async def list_devices(
        self, *, user_id: str, current_device_id: str
    ) -> list[MobileDeviceSessionDto]:
        self.calls.append(f"devices:{current_device_id}")
        return [
            MobileDeviceSessionDto(
                jti="jti-1",
                device_id="device-1",
                device_name="Pixel 8",
                os="android",
                app_version="1.0.0+1",
                issued_at=1785000000,
                current=True,
            )
        ]


def _client(use_case: FakeUseCase, *, claims: TokenPayload | None = None) -> TestClient:
    app = FastAPI()
    app.include_router(mobile_auth_router, prefix="/auth")
    app.dependency_overrides[get_mobile_auth_use_case] = lambda: use_case
    if claims is not None:
        app.dependency_overrides[get_current_user] = lambda: claims
    return TestClient(app)


def _claims(platform: str | None, device_id: str | None = "device-1") -> TokenPayload:
    return TokenPayload(
        sub="7",
        aud="jsangho-api",
        exp=9999999999,
        iat=0,
        jti="access-jti",
        roles=["user"],
        platform=platform,
        device_id=device_id,
    )


_LOGIN_BODY = {
    "code": "kakao-code",
    "redirectUri": "kakaoabc://oauth",
    "deviceId": "device-1",
    "deviceName": "Pixel 8",
    "os": "android",
    "appVersion": "1.0.0+1",
}


def test_login_response_uses_camel_case_aliases() -> None:
    """Flutter의 `AuthApiClient`가 읽는 키 이름 그대로여야 한다 (하네스 §7.1)."""
    use_case = FakeUseCase()
    response = _client(use_case).post("/auth/mobile/kakao", json=_LOGIN_BODY)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"token", "refreshToken", "expiresIn", "user"}
    assert body["refreshToken"] == "refresh-opaque"
    assert body["expiresIn"] == 900
    assert set(body["user"]) == {"userId", "nickname", "email", "role"}
    assert body["user"]["userId"] == 7
    # 이메일 미동의 계정은 null로 내려간다 — 앱이 이 값을 필수로 다루면 안 된다.
    assert body["user"]["email"] is None


def test_login_rejects_a_request_missing_required_fields() -> None:
    """`code`·`redirectUri`·`deviceId`는 필수다."""
    response = _client(FakeUseCase()).post(
        "/auth/mobile/kakao", json={"code": "kakao-code"}
    )
    assert response.status_code == 422


def test_login_also_accepts_snake_case_keys() -> None:
    """`populate_by_name=True`(저장소 공통 관례)라 두 표기를 모두 받는다.

    앱은 camelCase만 보내지만, 관례가 바뀌어 한쪽 표기가 막히면 알아채야 하므로
    "현재 동작이 이렇다"를 명시적으로 고정해 둔다.
    """
    response = _client(FakeUseCase()).post(
        "/auth/mobile/kakao",
        json={
            "code": "c",
            "redirect_uri": "kakaoabc://oauth",
            "device_id": "device-1",
        },
    )
    assert response.status_code == 200


def test_login_passes_device_metadata_through() -> None:
    use_case = FakeUseCase()
    _client(use_case).post("/auth/mobile/kakao", json=_LOGIN_BODY)
    assert use_case.calls == ["login:device-1:android"]


def test_refresh_response_shape() -> None:
    response = _client(FakeUseCase()).post(
        "/auth/mobile/refresh", json={"refreshToken": "refresh-1"}
    )

    assert response.status_code == 200
    assert set(response.json()) == {"token", "refreshToken", "expiresIn"}


@pytest.mark.parametrize(
    "error",
    [SessionNotFoundError(), SessionReuseDetectedError(user_id="7"), LookupError()],
)
def test_refresh_failures_all_become_401(error: Exception) -> None:
    """앱은 401 하나만 보고 재로그인으로 간다 — 실패 이유를 노출하지 않는다."""
    response = _client(FakeUseCase(refresh_error=error)).post(
        "/auth/mobile/refresh", json={"refreshToken": "refresh-1"}
    )
    assert response.status_code == 401


@pytest.mark.parametrize("path", ["/auth/mobile/logout-all", "/auth/mobile/sessions"])
def test_web_token_cannot_reach_mobile_endpoints(path: str) -> None:
    """웹 세션 토큰으로 모바일 엔드포인트를 호출할 수 없다 (D-3)."""
    client = _client(FakeUseCase(), claims=_claims("web"))
    response = (
        client.get(path) if path.endswith("sessions") else client.post(path, json={})
    )
    assert response.status_code == 401


@pytest.mark.parametrize("path", ["/auth/mobile/logout-all", "/auth/mobile/sessions"])
def test_token_without_platform_claim_is_rejected(path: str) -> None:
    """`platform` 도입 이전에 발급된 토큰도 거부한다 — 모바일 경로는 신규라 하위 호환 대상이 없다."""
    client = _client(FakeUseCase(), claims=_claims(None))
    response = (
        client.get(path) if path.endswith("sessions") else client.post(path, json={})
    )
    assert response.status_code == 401


def test_sessions_response_uses_camel_case_and_marks_current_device() -> None:
    use_case = FakeUseCase()
    client = _client(use_case, claims=_claims("mobile", device_id="device-1"))

    response = client.get("/auth/mobile/sessions")

    assert response.status_code == 200
    rows = response.json()["sessions"]
    assert set(rows[0]) == {
        "jti",
        "deviceId",
        "deviceName",
        "os",
        "appVersion",
        "issuedAt",
        "current",
    }
    assert rows[0]["current"] is True
    # 라우터가 토큰의 device_id를 유스케이스로 넘겨야 "이 기기" 표시가 맞는다.
    assert use_case.calls == ["devices:device-1"]


def test_logout_uses_the_authenticated_user_not_the_body() -> None:
    """남의 refresh token을 보내도 자기 세션만 지워진다."""
    use_case = FakeUseCase()
    client = _client(use_case, claims=_claims("mobile"))

    response = client.post(
        "/auth/mobile/logout", json={"refreshToken": "someone-elses-token"}
    )

    assert response.status_code == 200
    assert use_case.calls == ["logout:7"]
