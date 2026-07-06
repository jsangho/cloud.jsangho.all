from __future__ import annotations

from abc import ABC, abstractmethod

from superstar.app.ports.input.jason_mask_schema import JasonMaskSchema
from superstar.domain.entities.user_model import UserModel


class JasonMaskRepository(ABC):
    @abstractmethod
    async def find_by_email(self, email: str) -> UserModel | None: ...

    @abstractmethod
    async def find_by_login_id(self, login_id: str) -> UserModel | None: ...

    @abstractmethod
    async def save_user(
        self,
        user_schema: JasonMaskSchema,
        password_hash: str,
    ) -> UserModel: ...
