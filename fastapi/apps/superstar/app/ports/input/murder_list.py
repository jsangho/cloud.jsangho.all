from __future__ import annotations

from abc import ABC, abstractmethod

from superstar.domain.entities.user_model import UserModel


class MurderListUseCase(ABC):
    @abstractmethod
    async def get_user_by_id(self, *, user_id: int) -> UserModel: ...
