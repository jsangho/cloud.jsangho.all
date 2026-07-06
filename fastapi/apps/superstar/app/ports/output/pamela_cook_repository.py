from __future__ import annotations

from abc import ABC, abstractmethod

from superstar.domain.entities.user_model import UserModel


class PamelaCookRepository(ABC):
    @abstractmethod
    async def find_by_login_id(self, login_id: str) -> UserModel | None: ...
