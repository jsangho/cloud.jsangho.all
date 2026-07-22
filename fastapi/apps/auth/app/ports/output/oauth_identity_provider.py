from __future__ import annotations

from abc import ABC, abstractmethod

from auth.domain.value_objects.oauth_profile import OAuthProfile


class OAuthIdentityProvider(ABC):
    """Google/Kakao/Naver 공통 소셜 로그인 출력 포트."""

    @abstractmethod
    def build_authorize_url(self, *, state: str) -> str: ...

    @abstractmethod
    async def exchange_code(self, *, code: str) -> OAuthProfile: ...
