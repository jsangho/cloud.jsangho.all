from __future__ import annotations

from abc import ABC, abstractmethod

from superstar.domain.value_objects.kakao_profile import KakaoProfile


class KakaoIdentityProvider(ABC):
    @abstractmethod
    def build_authorize_url(self, *, state: str) -> str: ...

    @abstractmethod
    async def exchange_code(self, *, code: str) -> KakaoProfile: ...
