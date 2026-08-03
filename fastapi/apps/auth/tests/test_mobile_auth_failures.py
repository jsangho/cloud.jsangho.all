"""실패 경로 회귀 테스트 — 하네스 T8 중 부분 상태·만료에 해당하는 항목.

정상 경로는 `test_mobile_auth_interactor.py`가 본다. 여기서는 카카오가 죽거나
세션이 만료됐을 때 **아무것도 남기지 않는지**를 확인한다.
"""

from __future__ import annotations

import fakeredis.aioredis
import pytest
from fakes import FakeUsers, FakeVault

from auth.adapter.outbound.redis.session_redis_store import SessionRedisStore
from auth.app.dtos.mobile_auth_dto import MobileDeviceDto
from auth.app.ports.output.kakao_mobile_identity_provider import (
    KakaoMobileIdentityProvider,
)
from auth.app.ports.output.session_store import (
    MOBILE,
    WEB,
    SessionMeta,
    SessionNotFoundError,
)
from auth.app.use_cases.mobile_auth_interactor import MobileAuthInteractor
from auth.domain.value_objects.kakao_identity import KakaoProfile, KakaoTokenSet
from fastapi import HTTPException

_DEVICE = MobileDeviceDto(
    device_id="device-1", device_name="Pixel 8", os="android", app_version="1.0.0+1"
)


class ExplodingKakao(KakaoMobileIdentityProvider):
    """지정한 단계에서 카카오 호출이 실패하는 어댑터."""

    def __init__(self, *, fail_on: str, status: int = 504) -> None:
        self._fail_on = fail_on
        self._status = status

    async def exchange_code(self, *, code: str, redirect_uri: str) -> KakaoTokenSet:
        if self._fail_on == "exchange":
            raise HTTPException(status_code=self._status, detail="카카오 지연")
        return KakaoTokenSet(
            access_token="kakao-access",
            refresh_token="kakao-refresh",
            expires_in=21600,
            refresh_token_expires_in=5184000,
        )

    async def fetch_profile(self, *, access_token: str) -> KakaoProfile:
        if self._fail_on == "profile":
            raise HTTPException(status_code=self._status, detail="카카오 지연")
        return KakaoProfile(kakao_id="4242", nickname="홍길동", email=None)

    async def unlink(self, *, kakao_access_token: str) -> None:
        raise NotImplementedError


def _interactor(kakao: KakaoMobileIdentityProvider):
    users = FakeUsers()
    vault = FakeVault()
    store = SessionRedisStore(fakeredis.aioredis.FakeRedis(decode_responses=True))
    interactor = MobileAuthInteractor(
        kakao=kakao, users=users, sessions=store, kakao_vault=vault
    )
    return interactor, users, vault, store


@pytest.mark.parametrize("stage", ["exchange", "profile"])
@pytest.mark.asyncio
async def test_kakao_failure_leaves_no_partial_state(stage: str) -> None:
    """카카오가 죽으면 유저도 세션도 카카오 토큰도 만들어지지 않아야 한다."""
    interactor, users, vault, store = _interactor(ExplodingKakao(fail_on=stage))

    with pytest.raises(HTTPException) as excinfo:
        await interactor.login_with_kakao(
            code="code", redirect_uri="kakaoabc://oauth", device=_DEVICE
        )

    assert excinfo.value.status_code == 504
    assert users.rows == []
    assert vault.stored == {}
    assert await store.list_sessions(platform=MOBILE, user_id="1") == []


@pytest.mark.asyncio
async def test_expired_session_cannot_be_refreshed() -> None:
    """TTL이 지난 세션은 리프레시되지 않는다.

    fakeredis에서 TTL을 실제로 흘려보낼 수 없어, 만료된 상태와 동일한 결과인
    "키가 사라진 상태"를 직접 만들어 검증한다.
    """
    interactor, _, _, store = _interactor(ExplodingKakao(fail_on="none"))
    login = await interactor.login_with_kakao(
        code="code", redirect_uri="kakaoabc://oauth", device=_DEVICE
    )

    # TTL 만료가 지우는 것과 같은 키들을 걷어낸다.
    jti = login.refresh_token.split(".", 1)[0]
    await store.revoke_session(platform=MOBILE, user_id="1", jti=jti)

    with pytest.raises(SessionNotFoundError):
        await interactor.refresh(refresh_token=login.refresh_token)


@pytest.mark.asyncio
async def test_refresh_fails_when_the_user_row_disappeared() -> None:
    """세션은 살아 있는데 유저가 지워졌으면 세션도 함께 정리한다."""
    interactor, users, _, store = _interactor(ExplodingKakao(fail_on="none"))
    login = await interactor.login_with_kakao(
        code="code", redirect_uri="kakaoabc://oauth", device=_DEVICE
    )
    users.rows.clear()

    with pytest.raises(LookupError):
        await interactor.refresh(refresh_token=login.refresh_token)

    assert await store.list_sessions(platform=MOBILE, user_id="1") == []


@pytest.mark.asyncio
async def test_logout_all_clears_only_this_users_mobile_sessions() -> None:
    interactor, _, _, store = _interactor(ExplodingKakao(fail_on="none"))
    await interactor.login_with_kakao(
        code="code", redirect_uri="kakaoabc://oauth", device=_DEVICE
    )
    # 같은 유저의 웹 세션 — 모바일 전체 로그아웃이 건드리면 안 된다 (D-4).
    await store.create_session(platform=WEB, user_id="1", meta=SessionMeta())

    await interactor.logout_all(user_id="1", access_jti="jti-1", access_exp=0)

    assert await store.list_sessions(platform=MOBILE, user_id="1") == []
    assert len(await store.list_sessions(platform=WEB, user_id="1")) == 1
