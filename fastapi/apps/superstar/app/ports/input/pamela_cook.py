from __future__ import annotations

from abc import ABC, abstractmethod

from superstar.domain.entities.user_model import UserModel


class PamelaCookUseCase(ABC):
    @abstractmethod
    async def login_user(self, *, login_id: str, password: str) -> UserModel: ...
