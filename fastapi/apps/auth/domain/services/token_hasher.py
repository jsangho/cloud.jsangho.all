from __future__ import annotations

import hashlib
import hmac

__all__ = ["hash_token", "tokens_match"]


def hash_token(token: str) -> str:
    """리프레시 토큰 전체의 SHA-256 hex.

    Redis에는 이 값만 저장한다 — 평문 저장 금지(하네스 §3).
    기존 `{jti}.{secret}` 형식에서 jti만 대조하던 구조는 jti를 아는 것만으로
    통과하므로, 뒤쪽 시크릿까지 포함한 토큰 전체를 해싱한다(하네스 §4-M).
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def tokens_match(*, token: str, expected_hash: str) -> bool:
    """타이밍 공격을 피하려고 상수 시간 비교를 쓴다."""
    return hmac.compare_digest(hash_token(token), expected_hash)
