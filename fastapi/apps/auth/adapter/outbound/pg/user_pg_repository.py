from __future__ import annotations

import secrets

from core.entities.user_model import UserModel
from core.security.password import hash_password
from core.security.role import UserRole
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.app.ports.output.user_repository import UserRepository


class UserPgRepository(UserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_oauth(self, *, provider: str, oauth_id: str) -> UserModel | None:
        result = await self._session.execute(
            select(UserModel).where(
                UserModel.oauth_provider == provider,
                UserModel.oauth_id == oauth_id,
            )
        )
        return result.scalar_one_or_none()

    async def find_by_email(self, *, email: str) -> UserModel | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.email == email)
        )
        return result.scalar_one_or_none()

    async def find_by_login_id(self, *, login_id: str) -> UserModel | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.login_id == login_id)
        )
        return result.scalar_one_or_none()

    async def find_by_id(self, *, user_id: int) -> UserModel | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
        return result.scalar_one_or_none()

    async def link_oauth(
        self, *, user: UserModel, provider: str, oauth_id: str
    ) -> UserModel:
        user.oauth_provider = provider
        user.oauth_id = oauth_id
        await self._session.commit()
        await self._session.refresh(user)
        return user

    async def create_oauth_user(
        self,
        *,
        login_id: str,
        nickname: str,
        email: str,
        provider: str,
        oauth_id: str,
    ) -> UserModel:
        user = UserModel(
            login_id=login_id,
            nickname=nickname,
            email=email,
            password_hash=hash_password(secrets.token_urlsafe(32)),
            role=UserRole.USER,
            oauth_provider=provider,
            oauth_id=oauth_id,
        )
        self._session.add(user)
        await self._session.commit()
        await self._session.refresh(user)
        return user

    async def create_user(
        self,
        *,
        login_id: str,
        nickname: str,
        email: str,
        password_hash: str,
        role: str,
    ) -> UserModel:
        user = UserModel(
            login_id=login_id,
            nickname=nickname,
            email=email,
            password_hash=password_hash,
            role=role,
        )
        self._session.add(user)
        await self._session.commit()
        await self._session.refresh(user)
        return user
