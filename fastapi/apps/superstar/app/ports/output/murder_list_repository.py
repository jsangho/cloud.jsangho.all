from __future__ import annotations

from abc import ABC, abstractmethod

from superstar.domain.entities.user_model import UserModel


class MurderListRepository(ABC):
    @abstractmethod
    async def find_by_id(self, user_id: int) -> UserModel | None: ...
