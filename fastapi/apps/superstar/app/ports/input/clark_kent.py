from __future__ import annotations

from abc import ABC, abstractmethod

from superstar.domain.entities.user_model import UserModel


class ClarkKentUseCase(ABC):
    @abstractmethod
    def build_authorize_url(self, *, next_path: str) -> str: ...

    @abstractmethod
    async def login_with_google(self, *, code: str) -> UserModel: ...
