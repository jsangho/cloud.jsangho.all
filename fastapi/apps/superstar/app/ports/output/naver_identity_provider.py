from __future__ import annotations

from abc import ABC, abstractmethod

from superstar.domain.value_objects.naver_profile import NaverProfile


class NaverIdentityProvider(ABC):
    @abstractmethod
    def build_authorize_url(self, *, state: str) -> str: ...

    @abstractmethod
    async def exchange_code(self, *, code: str) -> NaverProfile: ...
