from __future__ import annotations

from abc import ABC, abstractmethod

from core.entities.user_model import UserModel


class UserRepository(ABC):
    @abstractmethod
    async def find_by_oauth(
        self, *, provider: str, oauth_id: str
    ) -> UserModel | None: ...

    @abstractmethod
    async def find_by_email(self, *, email: str) -> UserModel | None: ...

    @abstractmethod
    async def find_by_login_id(self, *, login_id: str) -> UserModel | None: ...

    @abstractmethod
    async def find_by_id(self, *, user_id: int) -> UserModel | None: ...

    @abstractmethod
    async def link_oauth(
        self, *, user: UserModel, provider: str, oauth_id: str
    ) -> UserModel: ...

    @abstractmethod
    async def create_oauth_user(
        self,
        *,
        login_id: str,
        nickname: str,
        email: str,
        provider: str,
        oauth_id: str,
    ) -> UserModel: ...

    @abstractmethod
    async def create_user(
        self,
        *,
        login_id: str,
        nickname: str,
        email: str,
        password_hash: str,
        role: str,
    ) -> UserModel: ...
