from __future__ import annotations

from abc import ABC, abstractmethod

from core.entities.user_model import UserModel


class ProfileUseCase(ABC):
    @abstractmethod
    async def get_user_by_id(self, *, user_id: int) -> UserModel:
        """프로필 조회 (`GET /users/{user_id}`)."""
        ...
