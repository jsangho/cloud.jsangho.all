"""카카오 refresh token을 AES-GCM으로 암호화해 Redis에 보관한다(§4-N).

키 부재 시 조용히 평문으로 저장하는 일이 없도록 **생성자에서 즉시 실패**한다.
하네스 문서는 "기동 실패"를 명시하지만, import 시점에 던지면 `KAKAO_RT_ENCRYPTION_KEY`가
없는 환경에서 기존 웹 로그인까지 함께 죽는다. 그래서 모바일 경로를 배선하는 순간
(= 이 클래스를 만드는 순간)에 실패하도록 좁혔다. 평문 저장을 막는다는 목적은 동일하다.
"""

from __future__ import annotations

import base64
import os

import redis.asyncio as redis
from core.matrix.vault_keymaker_secret_manager import get_keymaker
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from auth.app.ports.output.kakao_token_vault import KakaoTokenVault

_REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
_REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
_KEY_PREFIX = "auth:kakao:rt"
_NONCE_BYTES = 12


class KakaoTokenRedisVault(KakaoTokenVault):
    def __init__(self, client: redis.Redis | None = None) -> None:
        self._aesgcm = AESGCM(_encryption_key())
        # 값이 바이트라서 decode_responses를 켜지 않는다.
        self._client = client or redis.Redis(host=_REDIS_HOST, port=_REDIS_PORT)

    async def store(self, *, user_id: str, refresh_token: str) -> None:
        if not refresh_token:
            return
        nonce = os.urandom(_NONCE_BYTES)
        # user_id를 AAD로 묶어, 다른 유저 키에 암호문을 옮겨 붙이면 복호화가 실패하게 한다.
        sealed = self._aesgcm.encrypt(
            nonce, refresh_token.encode("utf-8"), user_id.encode("utf-8")
        )
        # TTL 없음 — 연결 해제(unlink) 시에만 명시적으로 지운다(§5.3).
        await self._client.set(f"{_KEY_PREFIX}:{user_id}", nonce + sealed)

    async def load(self, *, user_id: str) -> str | None:
        raw = await self._client.get(f"{_KEY_PREFIX}:{user_id}")
        if not raw or len(raw) <= _NONCE_BYTES:
            return None
        try:
            plain = self._aesgcm.decrypt(
                raw[:_NONCE_BYTES], raw[_NONCE_BYTES:], user_id.encode("utf-8")
            )
        except InvalidTag:
            # 키가 교체됐거나 값이 변조됐다. 복호화 불가한 값은 없는 것으로 다룬다.
            return None
        return plain.decode("utf-8")

    async def delete(self, *, user_id: str) -> None:
        await self._client.delete(f"{_KEY_PREFIX}:{user_id}")


def _encryption_key() -> bytes:
    raw = get_keymaker().get_secret("KAKAO_RT_ENCRYPTION_KEY")
    if not raw:
        raise RuntimeError(
            "KAKAO_RT_ENCRYPTION_KEY가 설정되지 않았습니다. "
            "카카오 refresh token을 평문으로 저장하지 않기 위해 기동을 중단합니다."
        )
    try:
        key = base64.b64decode(raw, validate=True)
    except (ValueError, TypeError) as exc:
        raise RuntimeError(
            "KAKAO_RT_ENCRYPTION_KEY는 base64로 인코딩된 값이어야 합니다."
        ) from exc
    if len(key) not in (16, 24, 32):
        raise RuntimeError(
            "KAKAO_RT_ENCRYPTION_KEY는 디코딩 후 16·24·32바이트여야 합니다 "
            f"(현재 {len(key)}바이트)."
        )
    return key
