from __future__ import annotations

from abc import ABC, abstractmethod

from superstar.domain.value_objects.google_profile import GoogleProfile


class GoogleIdentityProvider(ABC):
    @abstractmethod
    def build_authorize_url(self, *, state: str) -> str: ...

    @abstractmethod
    async def exchange_code(self, *, code: str) -> GoogleProfile: ...
