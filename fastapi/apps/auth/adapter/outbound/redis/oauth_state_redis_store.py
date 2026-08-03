"""웹 OAuth `state` 저장소 — `auth:oauth:state:{state}` (하네스 §5.1).

값은 `next_path` 문자열이다. 콜백에서 `GETDEL`로 조회와 삭제를 한 번에 처리해
같은 `state`가 두 번 통과하는 창을 없앤다.
"""

from __future__ import annotations

import os
import secrets

import redis.asyncio as redis

from auth.app.ports.output.oauth_state_store import (
    OAUTH_STATE_TTL_SECONDS,
    OAuthStateStore,
)

_REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
_REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
_KEY_PREFIX = "auth:oauth:state"


class OAuthStateRedisStore(OAuthStateStore):
    def __init__(self, client: redis.Redis | None = None) -> None:
        self._client = client or redis.Redis(
            host=_REDIS_HOST, port=_REDIS_PORT, decode_responses=True
        )

    async def issue(self, *, next_path: str) -> str:
        # 열린 리다이렉트를 막는다 — 외부 URL은 받지 않는다.
        safe_next_path = next_path if next_path.startswith("/") else "/"
        state = secrets.token_urlsafe(32)
        await self._client.set(
            f"{_KEY_PREFIX}:{state}", safe_next_path, ex=OAUTH_STATE_TTL_SECONDS
        )
        return state

    async def consume(self, *, state: str) -> str | None:
        if not state:
            return None
        # GETDEL은 조회와 삭제가 한 연산이라 재사용 레이스가 생기지 않는다 (Redis 6.2+).
        return await self._client.getdel(f"{_KEY_PREFIX}:{state}")
