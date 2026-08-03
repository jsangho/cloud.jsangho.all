"""모바일 로그인 유스케이스 회귀 테스트.

카카오·Postgres는 fake로 대체한다 — 실제 외부 호출 없이 돌아야 한다.
"""

from __future__ import annotations

import fakeredis.aioredis
import pytest
from core.entities.user_model import UserModel
from fakes import FakeKakao, FakeUsers, FakeVault

from auth.adapter.outbound.redis.session_redis_store import SessionRedisStore
from auth.app.dtos.mobile_auth_dto import MobileDeviceDto
from auth.app.ports.output.session_store import MOBILE
from auth.app.use_cases.mobile_auth_interactor import MobileAuthInteractor
from auth.domain.value_objects.kakao_identity import KakaoProfile


def _interactor(
    profile: KakaoProfile, users: FakeUsers | None = None
) -> tuple[MobileAuthInteractor, FakeUsers, FakeVault]:
    repo = users or FakeUsers()
    vault = FakeVault()
    return (
        MobileAuthInteractor(
            kakao=FakeKakao(profile),
            users=repo,
            sessions=SessionRedisStore(
                fakeredis.aioredis.FakeRedis(decode_responses=True)
            ),
            kakao_vault=vault,
        ),
        repo,
        vault,
    )


_DEVICE = MobileDeviceDto(
    device_id="device-1", device_name="Pixel 8", os="android", app_version="1.0.0+1"
)


@pytest.mark.asyncio
async def test_login_without_email_consent_succeeds() -> None:
    """카카오 이메일은 선택 동의라 없을 수 있다 — 여기서 막히면 안 된다(§4-G)."""
    interactor, users, _ = _interactor(
        KakaoProfile(kakao_id="4242", nickname="홍길동", email=None)
    )

    result = await interactor.login_with_kakao(
        code="code", redirect_uri="kakaoabc://oauth", device=_DEVICE
    )

    assert result.user.email is None
    assert result.user.nickname == "홍길동"
    assert users.rows[0].login_id == "kakao_4242"


@pytest.mark.asyncio
async def test_login_does_not_merge_into_an_account_by_email() -> None:
    """미검증 이메일로 기존 계정에 올라타면 계정 탈취다 — 폴백을 쓰지 않는다(T3)."""
    existing = UserModel(
        id=1,
        login_id="victim",
        nickname="victim",
        email="victim@example.com",
        password_hash="x",
        role="user",
    )
    interactor, users, _ = _interactor(
        KakaoProfile(kakao_id="9999", nickname="공격자", email="victim@example.com"),
        users=FakeUsers([existing]),
    )

    result = await interactor.login_with_kakao(
        code="code", redirect_uri="kakaoabc://oauth", device=_DEVICE
    )

    assert result.user.user_id != existing.id
    assert existing.oauth_id is None
    assert len(users.rows) == 2


@pytest.mark.asyncio
async def test_second_login_reuses_the_same_account() -> None:
    profile = KakaoProfile(kakao_id="4242", nickname="홍길동", email=None)
    interactor, users, _ = _interactor(profile)

    first = await interactor.login_with_kakao(
        code="c1", redirect_uri="kakaoabc://oauth", device=_DEVICE
    )
    second = await interactor.login_with_kakao(
        code="c2", redirect_uri="kakaoabc://oauth", device=_DEVICE
    )

    assert first.user.user_id == second.user.user_id
    assert len(users.rows) == 1


@pytest.mark.asyncio
async def test_kakao_refresh_token_is_kept_server_side_only() -> None:
    """카카오 refresh token이 응답에 섞여 나가면 D-1 위반이다."""
    interactor, _, vault = _interactor(
        KakaoProfile(kakao_id="4242", nickname="홍길동", email=None)
    )

    result = await interactor.login_with_kakao(
        code="code", redirect_uri="kakaoabc://oauth", device=_DEVICE
    )

    assert vault.stored["1"] == "kakao-refresh"
    assert "kakao-refresh" not in result.refresh_token
    assert "kakao-refresh" not in result.token


@pytest.mark.asyncio
async def test_access_token_carries_the_mobile_platform_claim() -> None:
    import jwt

    interactor, _, _ = _interactor(
        KakaoProfile(kakao_id="4242", nickname="홍길동", email=None)
    )

    result = await interactor.login_with_kakao(
        code="code", redirect_uri="kakaoabc://oauth", device=_DEVICE
    )

    claims = jwt.decode(result.token, options={"verify_signature": False})
    assert claims["platform"] == MOBILE
    assert claims["device_id"] == "device-1"


@pytest.mark.asyncio
async def test_refresh_rotates_and_invalidates_the_previous_token() -> None:
    interactor, _, _ = _interactor(
        KakaoProfile(kakao_id="4242", nickname="홍길동", email=None)
    )
    login = await interactor.login_with_kakao(
        code="code", redirect_uri="kakaoabc://oauth", device=_DEVICE
    )

    refreshed = await interactor.refresh(refresh_token=login.refresh_token)

    assert refreshed.refresh_token != login.refresh_token
    assert refreshed.expires_in == 900


@pytest.mark.asyncio
async def test_list_devices_marks_the_current_device() -> None:
    interactor, _, _ = _interactor(
        KakaoProfile(kakao_id="4242", nickname="홍길동", email=None)
    )
    await interactor.login_with_kakao(
        code="code", redirect_uri="kakaoabc://oauth", device=_DEVICE
    )
    await interactor.login_with_kakao(
        code="code",
        redirect_uri="kakaoabc://oauth",
        device=MobileDeviceDto(
            device_id="device-2", device_name="iPad", os="ios", app_version="1.0.0+1"
        ),
    )

    devices = await interactor.list_devices(user_id="1", current_device_id="device-2")

    assert len(devices) == 2
    assert [d.device_id for d in devices if d.current] == ["device-2"]
