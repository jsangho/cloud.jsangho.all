from __future__ import annotations

from abc import ABC, abstractmethod

from core.entities.user_model import UserModel


class OAuthLoginUseCase(ABC):
    """Google/Kakao/Naver 공통 소셜 로그인 입력 포트."""

    @abstractmethod
    def build_authorize_url(self, *, next_path: str) -> str: ...

    @abstractmethod
    async def login(self, *, code: str) -> UserModel: ...
