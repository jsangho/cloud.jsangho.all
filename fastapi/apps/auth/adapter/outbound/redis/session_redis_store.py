"""플랫폼 격리 리프레시 세션 저장소 — 하네스 §5 키 스키마의 구현체.

키 구조(문서 §5.1에 더해 `auth:rt:owner:*` 포인터 하나를 추가했다):

    auth:rt:{platform}:{user_id}:{jti}   HASH   세션 본체
    auth:rt:index:{platform}:{user_id}   SET    유저별 활성 jti 목록
    auth:rt:owner:{platform}:{jti}       STRING jti -> user_id 역인덱스
    auth:rt:used:{platform}:{jti}        STRING 회전 완료 마커, 값 = user_id
    auth:rt:seq                          INT    발급 순서 카운터(세션 상한 정리용)
    auth:blacklist:{jti}                 STRING access token 강제 무효화(기존 이름 유지)

`owner` 포인터가 필요한 이유: 클라이언트는 `{jti}.{secret}` 토큰만 보내므로 jti는 알아도
user_id를 모른다. 세션 본체 키에 user_id가 들어 있어 역인덱스 없이는 키를 조립할 수 없다.

`used` 마커의 값을 `"1"`이 아니라 user_id로 둔 것도 같은 이유다 — 회전 시 구 owner 키를
지우기 때문에, 재사용이 탐지된 시점에는 마커만 남아 있고 그 값으로 유저를 특정한다.

⚠️ Lua 안에서 키 이름을 조립하므로 Redis Cluster의 키 슬롯 규칙을 만족하지 않는다.
현재 배포는 단일 노드 Redis(`docker-compose.yaml`)이며, 클러스터로 옮긴다면 해시태그를
도입해야 한다.
"""

from __future__ import annotations

import os
import time

import redis.asyncio as redis

from auth.app.ports.output.session_store import (
    SessionInfo,
    SessionMeta,
    SessionNotFoundError,
    SessionReuseDetectedError,
    SessionStore,
)
from auth.domain.services.token_hasher import hash_token
from auth.domain.services.token_issuer import create_refresh_token, refresh_ttl_seconds

_REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
_REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
_BLACKLIST_KEY_PREFIX = "auth:blacklist"

# 플랫폼당 동시 활성 세션 상한(§5.3). 초과 시 issued_at이 가장 오래된 것부터 폐기한다.
MAX_SESSIONS_PER_PLATFORM = 5

# 같은 기기(device_id)에서 다시 로그인하면 기존 세션을 대체한다. 상한 계산 전에
# 기기 중복을 먼저 정리해야, 재로그인만 반복해도 상한에 걸리지 않는다.
_CREATE_SCRIPT = """
local platform = ARGV[1]
local user_id = ARGV[2]
local jti = ARGV[3]
local token_hash = ARGV[4]
local ttl = tonumber(ARGV[5])
local now = ARGV[6]
local device_id = ARGV[7]
local max_sessions = tonumber(ARGV[8])

local index_key = 'auth:rt:index:' .. platform .. ':' .. user_id
local function session_key(j) return 'auth:rt:' .. platform .. ':' .. user_id .. ':' .. j end
local function drop(j)
  redis.call('DEL', session_key(j))
  redis.call('DEL', 'auth:rt:owner:' .. platform .. ':' .. j)
  redis.call('SREM', index_key, j)
end

-- 인덱스에 남아 있지만 본체가 TTL로 사라진 jti를 함께 정리한다.
local live = {}
for _, j in ipairs(redis.call('SMEMBERS', index_key)) do
  local seq = redis.call('HGET', session_key(j), 'seq')
  if not seq then
    redis.call('SREM', index_key, j)
  elseif device_id ~= '' and redis.call('HGET', session_key(j), 'device_id') == device_id then
    drop(j)
  else
    table.insert(live, {j, tonumber(seq) or 0})
  end
end

-- issued_at(초 단위)으로 정렬하면 같은 초에 만들어진 세션끼리 순서가 정해지지 않아
-- 상한 초과 시 엉뚱한 세션이 폐기된다. 전역 INCR 값으로 발급 순서를 확정한다.
table.sort(live, function(a, b) return a[2] < b[2] end)
local overflow = #live - (max_sessions - 1)
for i = 1, overflow do
  drop(live[i][1])
end

local key = session_key(jti)
redis.call('HSET', key,
  'token_hash', token_hash,
  'user_id', user_id,
  'platform', platform,
  'device_id', device_id,
  'device_name', ARGV[9],
  'app_version', ARGV[10],
  'os', ARGV[11],
  'user_agent_hash', ARGV[12],
  'ip', ARGV[13],
  'issued_at', now,
  'seq', redis.call('INCR', 'auth:rt:seq'),
  'rotated_from', '',
  'rotation_count', '0')
redis.call('EXPIRE', key, ttl)
redis.call('SET', 'auth:rt:owner:' .. platform .. ':' .. jti, user_id, 'EX', ttl)
redis.call('SADD', index_key, jti)
redis.call('EXPIRE', index_key, ttl)
return 1
"""

# 회전 전체를 한 번의 원자 실행으로 처리한다. GET 후 SET 하는 2회 왕복 구조는
# 동시 요청에서 유효한 토큰을 두 개 만들어낸다(§4-B).
_ROTATE_SCRIPT = """
local platform = ARGV[1]
local jti = ARGV[2]
local token_hash = ARGV[3]
local new_jti = ARGV[4]
local new_token_hash = ARGV[5]
local ttl = tonumber(ARGV[6])

local used_key = 'auth:rt:used:' .. platform .. ':' .. jti
local reused_owner = redis.call('GET', used_key)
if reused_owner then
  -- 이미 회전된 토큰이 다시 왔다 = 탈취 의심. 해당 플랫폼 세션만 전부 폐기한다(D-3).
  local index_key = 'auth:rt:index:' .. platform .. ':' .. reused_owner
  for _, j in ipairs(redis.call('SMEMBERS', index_key)) do
    redis.call('DEL', 'auth:rt:' .. platform .. ':' .. reused_owner .. ':' .. j)
    redis.call('DEL', 'auth:rt:owner:' .. platform .. ':' .. j)
  end
  redis.call('DEL', index_key)
  return {'REUSE', reused_owner}
end

local owner_key = 'auth:rt:owner:' .. platform .. ':' .. jti
local user_id = redis.call('GET', owner_key)
if not user_id then return {'MISSING', ''} end

local key = 'auth:rt:' .. platform .. ':' .. user_id .. ':' .. jti
local stored = redis.call('HGET', key, 'token_hash')
if not stored then return {'MISSING', ''} end
-- jti만 맞고 뒤쪽 시크릿이 다른 위조 토큰은 여기서 걸린다(§4-M).
if stored ~= token_hash then return {'MISMATCH', ''} end

local new_key = 'auth:rt:' .. platform .. ':' .. user_id .. ':' .. new_jti
local fields = redis.call('HGETALL', key)
for i = 1, #fields, 2 do
  redis.call('HSET', new_key, fields[i], fields[i + 1])
end
-- issued_at은 최초 로그인 시각이라 회전해도 그대로 둔다(기기 목록·상한 정리 기준).
redis.call('HSET', new_key,
  'token_hash', new_token_hash,
  'rotated_from', jti,
  'rotation_count', tonumber(redis.call('HGET', key, 'rotation_count') or '0') + 1)
redis.call('EXPIRE', new_key, ttl)
redis.call('SET', 'auth:rt:owner:' .. platform .. ':' .. new_jti, user_id, 'EX', ttl)

redis.call('SET', used_key, user_id, 'EX', ttl)
redis.call('DEL', key)
redis.call('DEL', owner_key)

local index_key = 'auth:rt:index:' .. platform .. ':' .. user_id
redis.call('SREM', index_key, jti)
redis.call('SADD', index_key, new_jti)
redis.call('EXPIRE', index_key, ttl)
return {'OK', user_id}
"""


class SessionRedisStore(SessionStore):
    def __init__(self, client: redis.Redis | None = None) -> None:
        self._client = client or redis.Redis(
            host=_REDIS_HOST, port=_REDIS_PORT, decode_responses=True
        )
        self._create = self._client.register_script(_CREATE_SCRIPT)
        self._rotate = self._client.register_script(_ROTATE_SCRIPT)

    async def create_session(
        self, *, platform: str, user_id: str, meta: SessionMeta
    ) -> tuple[str, str]:
        refresh_token, jti = create_refresh_token(sub=user_id)
        ttl = refresh_ttl_seconds(platform)
        await self._create(
            keys=[],
            args=[
                platform,
                user_id,
                jti,
                hash_token(refresh_token),
                ttl,
                int(time.time()),
                meta.device_id,
                MAX_SESSIONS_PER_PLATFORM,
                meta.device_name,
                meta.app_version,
                meta.os,
                meta.user_agent_hash,
                meta.ip,
            ],
        )
        return refresh_token, jti

    async def rotate_session(
        self, *, platform: str, refresh_token: str
    ) -> tuple[str, str, str]:
        jti = refresh_token.split(".", 1)[0]
        new_token, new_jti = create_refresh_token()
        status, user_id = await self._rotate(
            keys=[],
            args=[
                platform,
                jti,
                hash_token(refresh_token),
                new_jti,
                hash_token(new_token),
                refresh_ttl_seconds(platform),
            ],
        )

        if status == "REUSE":
            raise SessionReuseDetectedError(user_id=user_id)
        if status != "OK":
            raise SessionNotFoundError
        return new_token, new_jti, user_id

    async def revoke_session(self, *, platform: str, user_id: str, jti: str) -> None:
        await self._client.delete(f"auth:rt:{platform}:{user_id}:{jti}")
        await self._client.delete(f"auth:rt:owner:{platform}:{jti}")
        await self._client.srem(f"auth:rt:index:{platform}:{user_id}", jti)

    async def revoke_all(self, *, platform: str, user_id: str) -> None:
        index_key = f"auth:rt:index:{platform}:{user_id}"
        jtis = await self._client.smembers(index_key)
        if jtis:
            await self._client.delete(
                *(f"auth:rt:{platform}:{user_id}:{j}" for j in jtis),
                *(f"auth:rt:owner:{platform}:{j}" for j in jtis),
            )
        await self._client.delete(index_key)

    async def list_sessions(self, *, platform: str, user_id: str) -> list[SessionInfo]:
        index_key = f"auth:rt:index:{platform}:{user_id}"
        jtis = await self._client.smembers(index_key)

        sessions: list[SessionInfo] = []
        for jti in jtis:
            fields = await self._client.hgetall(f"auth:rt:{platform}:{user_id}:{jti}")
            if not fields:
                # 본체가 TTL로 사라졌는데 인덱스에만 남은 유령 항목.
                await self._client.srem(index_key, jti)
                continue
            sessions.append(
                SessionInfo(
                    jti=jti,
                    device_id=fields.get("device_id", ""),
                    device_name=fields.get("device_name", ""),
                    os=fields.get("os", ""),
                    app_version=fields.get("app_version", ""),
                    issued_at=int(fields.get("issued_at", 0)),
                )
            )
        sessions.sort(key=lambda s: s.issued_at, reverse=True)
        return sessions

    async def blacklist_access_token(self, *, jti: str, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return
        await self._client.set(f"{_BLACKLIST_KEY_PREFIX}:{jti}", "1", ex=ttl_seconds)
