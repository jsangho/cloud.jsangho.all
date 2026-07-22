from __future__ import annotations

from abc import ABC, abstractmethod

from core.entities.user_model import UserModel


class LoginUseCase(ABC):
    @abstractmethod
    async def login_user(self, *, login_id: str, password: str) -> UserModel:
        """로그인 (`POST /login`)."""
        ...
