from __future__ import annotations

from abc import ABC, abstractmethod

from core.entities.user_model import UserModel


class OAuthLoginUseCase(ABC):
    """Google/Kakao/Naver 공통 소셜 로그인 입력 포트."""

    @abstractmethod
    async def build_authorize_url(self, *, next_path: str) -> str:
        """인가 URL을 만든다. `state`(CSRF 난수) 저장이 필요해 비동기다."""

    @abstractmethod
    async def resolve_next_path(self, *, state: str) -> str | None:
        """콜백의 `state`를 검증하고 원래 `next_path`를 돌려준다.

        유효하지 않으면 `None` — 호출부는 로그인을 거부해야 한다.
        """

    @abstractmethod
    async def login(self, *, code: str) -> UserModel: ...
