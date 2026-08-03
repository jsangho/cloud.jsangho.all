from __future__ import annotations

from abc import ABC, abstractmethod


class KakaoTokenVault(ABC):
    """카카오 refresh token 보관소.

    클라이언트에 절대 반환되지 않는 서버 전용 값이다(§3). 저장 시 암호화는 구현체의
    책임이며, 평문 저장은 계약 위반이다.
    """

    @abstractmethod
    async def store(self, *, user_id: str, refresh_token: str) -> None: ...

    @abstractmethod
    async def load(self, *, user_id: str) -> str | None: ...

    @abstractmethod
    async def delete(self, *, user_id: str) -> None: ...
