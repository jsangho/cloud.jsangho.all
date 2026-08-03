"""웹 OAuth `state` CSRF 방어 회귀 테스트 (하네스 §4-D).

예전에는 `state`가 `next_path` 그 자체였다. 값이 예측 가능하면 CSRF 방어가
성립하지 않는다 — 공격자가 자기 인가 코드로 피해자를 로그인시킬 수 있다.
"""

from __future__ import annotations

import fakeredis.aioredis
import pytest
from core.entities.user_model import UserModel
from fakes import FakeUsers

from auth.adapter.outbound.redis.oauth_state_redis_store import OAuthStateRedisStore
from auth.app.ports.output.oauth_identity_provider import OAuthIdentityProvider
from auth.app.use_cases.oauth_login_interactor import OAuthLoginInteractor
from auth.domain.value_objects.oauth_profile import OAuthProfile


class RecordingProvider(OAuthIdentityProvider):
    """`build_authorize_url`에 어떤 `state`가 넘어왔는지 붙잡아 둔다."""

    def __init__(self) -> None:
        self.last_state: str | None = None

    def build_authorize_url(self, *, state: str) -> str:
        self.last_state = state
        return f"https://kauth.kakao.com/oauth/authorize?state={state}"

    async def exchange_code(self, *, code: str) -> OAuthProfile:
        return OAuthProfile(oauth_id="1", email="a@b.c", name="테스터")


def _interactor() -> tuple[OAuthLoginInteractor, RecordingProvider]:
    provider = RecordingProvider()
    return (
        OAuthLoginInteractor(
            provider="kakao",
            identity_provider=provider,
            repository=FakeUsers(),
            state_store=OAuthStateRedisStore(
                fakeredis.aioredis.FakeRedis(decode_responses=True)
            ),
        ),
        provider,
    )


@pytest.mark.asyncio
async def test_state_is_not_the_next_path() -> None:
    """`state`에 `next_path`가 그대로 실리면 안 된다."""
    interactor, provider = _interactor()

    await interactor.build_authorize_url(next_path="/rankings")

    assert provider.last_state is not None
    assert provider.last_state != "/rankings"
    assert "/rankings" not in provider.last_state
    # 난수라면 충분히 길다.
    assert len(provider.last_state) >= 32


@pytest.mark.asyncio
async def test_each_login_gets_a_different_state() -> None:
    interactor, provider = _interactor()

    await interactor.build_authorize_url(next_path="/")
    first = provider.last_state
    await interactor.build_authorize_url(next_path="/")
    second = provider.last_state

    assert first != second


@pytest.mark.asyncio
async def test_valid_state_returns_the_original_next_path() -> None:
    interactor, provider = _interactor()
    await interactor.build_authorize_url(next_path="/rankings")

    assert await interactor.resolve_next_path(state=provider.last_state or "") == (
        "/rankings"
    )


@pytest.mark.asyncio
async def test_state_cannot_be_used_twice() -> None:
    """재사용을 막지 못하면 탈취된 state로 반복 공격이 가능하다."""
    interactor, provider = _interactor()
    await interactor.build_authorize_url(next_path="/")
    state = provider.last_state or ""

    assert await interactor.resolve_next_path(state=state) == "/"
    assert await interactor.resolve_next_path(state=state) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("bogus", ["", "/", "guessed-state", "../../etc/passwd"])
async def test_unknown_state_is_rejected(bogus: str) -> None:
    interactor, _ = _interactor()

    assert await interactor.resolve_next_path(state=bogus) is None


@pytest.mark.asyncio
async def test_external_next_path_is_not_stored() -> None:
    """열린 리다이렉트 방지 — 외부 URL은 `/`로 떨어뜨린다."""
    interactor, provider = _interactor()

    await interactor.build_authorize_url(next_path="https://evil.example.com/steal")

    assert await interactor.resolve_next_path(state=provider.last_state or "") == "/"


@pytest.mark.asyncio
async def test_login_still_creates_the_user() -> None:
    """CSRF 대응이 기존 로그인 동작을 깨뜨리지 않는다."""
    interactor, _ = _interactor()

    user = await interactor.login(code="code")

    assert isinstance(user, UserModel)
    assert user.oauth_provider == "kakao"
