"""세션 스토어 회귀 테스트 — 하네스 T8 중 Redis 계층에 해당하는 항목.

fakeredis의 Lua 실행기(lupa)를 쓴다. 실제 Redis 없이도 회전 스크립트가 돌아야
CI에서 의미가 있고, 원자성 자체는 Redis가 스크립트를 단일 스레드로 실행한다는
전제 위에 있으므로 여기서는 "로직이 맞는가"를 본다.
"""

from __future__ import annotations

import asyncio

import fakeredis.aioredis
import pytest

from auth.adapter.outbound.redis.session_redis_store import (
    MAX_SESSIONS_PER_PLATFORM,
    SessionRedisStore,
)
from auth.app.ports.output.session_store import (
    MOBILE,
    WEB,
    SessionMeta,
    SessionNotFoundError,
    SessionReuseDetectedError,
)


@pytest.fixture
def store() -> SessionRedisStore:
    return SessionRedisStore(fakeredis.aioredis.FakeRedis(decode_responses=True))


def _meta(device_id: str = "device-1") -> SessionMeta:
    return SessionMeta(
        device_id=device_id,
        device_name="iPhone 15",
        app_version="1.0.0+1",
        os="ios",
    )


@pytest.mark.asyncio
async def test_rotate_returns_new_token_and_owner(store: SessionRedisStore) -> None:
    token, _ = await store.create_session(platform=MOBILE, user_id="7", meta=_meta())

    new_token, new_jti, user_id = await store.rotate_session(
        platform=MOBILE, refresh_token=token
    )

    assert user_id == "7"
    assert new_token != token
    assert new_token.startswith(f"{new_jti}.")


@pytest.mark.asyncio
async def test_rotation_carries_device_metadata_forward(
    store: SessionRedisStore,
) -> None:
    token, _ = await store.create_session(
        platform=MOBILE, user_id="7", meta=_meta("device-abc")
    )
    await store.rotate_session(platform=MOBILE, refresh_token=token)

    sessions = await store.list_sessions(platform=MOBILE, user_id="7")
    assert len(sessions) == 1
    assert sessions[0].device_id == "device-abc"
    assert sessions[0].device_name == "iPhone 15"


@pytest.mark.asyncio
async def test_reusing_rotated_token_revokes_every_mobile_session(
    store: SessionRedisStore,
) -> None:
    token, _ = await store.create_session(platform=MOBILE, user_id="7", meta=_meta())
    await store.create_session(platform=MOBILE, user_id="7", meta=_meta("device-2"))
    await store.rotate_session(platform=MOBILE, refresh_token=token)

    with pytest.raises(SessionReuseDetectedError) as excinfo:
        await store.rotate_session(platform=MOBILE, refresh_token=token)

    assert excinfo.value.user_id == "7"
    assert await store.list_sessions(platform=MOBILE, user_id="7") == []


@pytest.mark.asyncio
async def test_reuse_detection_leaves_web_sessions_alone(
    store: SessionRedisStore,
) -> None:
    """D-3 회귀 방지 — 한 플랫폼의 침해가 다른 플랫폼으로 번지면 안 된다."""
    mobile_token, _ = await store.create_session(
        platform=MOBILE, user_id="7", meta=_meta()
    )
    await store.create_session(platform=WEB, user_id="7", meta=SessionMeta())
    await store.rotate_session(platform=MOBILE, refresh_token=mobile_token)

    with pytest.raises(SessionReuseDetectedError):
        await store.rotate_session(platform=MOBILE, refresh_token=mobile_token)

    assert len(await store.list_sessions(platform=WEB, user_id="7")) == 1


@pytest.mark.asyncio
async def test_mobile_token_cannot_rotate_on_web_namespace(
    store: SessionRedisStore,
) -> None:
    """모바일 리프레시로 웹 세션을 갱신할 수 없다(D-3)."""
    token, _ = await store.create_session(platform=MOBILE, user_id="7", meta=_meta())

    with pytest.raises(SessionNotFoundError):
        await store.rotate_session(platform=WEB, refresh_token=token)


@pytest.mark.asyncio
async def test_forged_token_with_valid_jti_is_rejected(
    store: SessionRedisStore,
) -> None:
    """jti만 맞고 뒤쪽 시크릿이 다른 토큰은 통과하면 안 된다(§4-M)."""
    token, jti = await store.create_session(platform=MOBILE, user_id="7", meta=_meta())
    forged = f"{jti}.this-is-not-the-real-secret"
    assert forged != token

    with pytest.raises(SessionNotFoundError):
        await store.rotate_session(platform=MOBILE, refresh_token=forged)


@pytest.mark.asyncio
async def test_unknown_token_is_rejected(store: SessionRedisStore) -> None:
    with pytest.raises(SessionNotFoundError):
        await store.rotate_session(platform=MOBILE, refresh_token="nope.nothing")


@pytest.mark.asyncio
async def test_concurrent_rotation_yields_exactly_one_winner(
    store: SessionRedisStore,
) -> None:
    """같은 토큰으로 동시에 10번 리프레시하면 정확히 1건만 성공해야 한다.

    GET 후 SET 하는 비원자 구현에서는 유효한 토큰이 여러 개 만들어진다(§4-B).
    """
    token, _ = await store.create_session(platform=MOBILE, user_id="7", meta=_meta())

    results = await asyncio.gather(
        *(
            store.rotate_session(platform=MOBILE, refresh_token=token)
            for _ in range(10)
        ),
        return_exceptions=True,
    )

    successes = [r for r in results if not isinstance(r, BaseException)]
    assert len(successes) == 1


@pytest.mark.asyncio
async def test_relogin_from_same_device_replaces_its_session(
    store: SessionRedisStore,
) -> None:
    old_token, _ = await store.create_session(
        platform=MOBILE, user_id="7", meta=_meta("device-1")
    )
    await store.create_session(platform=MOBILE, user_id="7", meta=_meta("device-1"))

    assert len(await store.list_sessions(platform=MOBILE, user_id="7")) == 1
    with pytest.raises(SessionNotFoundError):
        await store.rotate_session(platform=MOBILE, refresh_token=old_token)


@pytest.mark.asyncio
async def test_sixth_device_evicts_the_oldest_session(
    store: SessionRedisStore,
) -> None:
    for index in range(MAX_SESSIONS_PER_PLATFORM):
        await store.create_session(
            platform=MOBILE, user_id="7", meta=_meta(f"device-{index}")
        )
    await store.create_session(platform=MOBILE, user_id="7", meta=_meta("device-new"))

    sessions = await store.list_sessions(platform=MOBILE, user_id="7")
    assert len(sessions) == MAX_SESSIONS_PER_PLATFORM
    device_ids = {s.device_id for s in sessions}
    assert "device-new" in device_ids
    assert "device-0" not in device_ids


@pytest.mark.asyncio
async def test_revoke_all_is_scoped_to_one_platform(
    store: SessionRedisStore,
) -> None:
    await store.create_session(platform=MOBILE, user_id="7", meta=_meta())
    await store.create_session(platform=WEB, user_id="7", meta=SessionMeta())

    await store.revoke_all(platform=MOBILE, user_id="7")

    assert await store.list_sessions(platform=MOBILE, user_id="7") == []
    assert len(await store.list_sessions(platform=WEB, user_id="7")) == 1


@pytest.mark.asyncio
async def test_revoke_session_invalidates_that_token_only(
    store: SessionRedisStore,
) -> None:
    token, jti = await store.create_session(platform=MOBILE, user_id="7", meta=_meta())
    other, _ = await store.create_session(
        platform=MOBILE, user_id="7", meta=_meta("device-2")
    )

    await store.revoke_session(platform=MOBILE, user_id="7", jti=jti)

    with pytest.raises(SessionNotFoundError):
        await store.rotate_session(platform=MOBILE, refresh_token=token)
    assert await store.rotate_session(platform=MOBILE, refresh_token=other)
