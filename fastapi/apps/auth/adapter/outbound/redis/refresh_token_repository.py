from __future__ import annotations

import os

import redis.asyncio as redis

_REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
_REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
_REFRESH_KEY_PREFIX = "auth:refresh"
_SUB_INDEX_PREFIX = "auth:refresh:by-sub"
_BLACKLIST_KEY_PREFIX = "auth:blacklist"

REUSE_DETECTED = "__reuse_detected__"


class RefreshTokenRepository:
    """리프레시 토큰 로테이션 저장소. `auth:refresh:{jti}` = "{sub}:active|used"."""

    def __init__(self) -> None:
        self._client = redis.Redis(
            host=_REDIS_HOST, port=_REDIS_PORT, decode_responses=True
        )

    async def store(self, *, sub: str, jti: str, ttl_seconds: int) -> None:
        await self._client.set(
            f"{_REFRESH_KEY_PREFIX}:{jti}", f"{sub}:active", ex=ttl_seconds
        )
        await self._client.sadd(f"{_SUB_INDEX_PREFIX}:{sub}", jti)

    async def consume(self, *, jti: str) -> str | None:
        """정상 소비면 sub 반환, 재사용(reuse) 감지 시 REUSE_DETECTED, 없으면 None."""
        key = f"{_REFRESH_KEY_PREFIX}:{jti}"
        raw = await self._client.get(key)
        if raw is None:
            return None

        sub, status = raw.rsplit(":", 1)
        if status == "used":
            await self.revoke_all_for_sub(sub=sub)
            return REUSE_DETECTED

        await self._client.set(key, f"{sub}:used", keepttl=True)
        return sub

    async def revoke_all_for_sub(self, *, sub: str) -> None:
        index_key = f"{_SUB_INDEX_PREFIX}:{sub}"
        jtis = await self._client.smembers(index_key)
        if jtis:
            await self._client.delete(*(f"{_REFRESH_KEY_PREFIX}:{j}" for j in jtis))
        await self._client.delete(index_key)

    async def blacklist_access_token(self, *, jti: str, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return
        await self._client.set(f"{_BLACKLIST_KEY_PREFIX}:{jti}", "1", ex=ttl_seconds)
