from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from superstar.app.ports.input.jason_mask_schema import JasonMaskSchema
from superstar.app.ports.output.jason_mask_repository import JasonMaskRepository
from superstar.domain.entities.user_model import UserModel


class JasonMaskPgRepository(JasonMaskRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_email(self, email: str) -> UserModel | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.email == email)
        )
        return result.scalar_one_or_none()

    async def find_by_login_id(self, login_id: str) -> UserModel | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.login_id == login_id)
        )
        return result.scalar_one_or_none()

    async def save_user(
        self,
        user_schema: JasonMaskSchema,
        password_hash: str,
    ) -> UserModel:
        user = UserModel(
            login_id=user_schema.login_id,
            nickname=user_schema.nickname,
            email=user_schema.email,
            password_hash=password_hash,
            role=user_schema.role.value,
        )
        self._session.add(user)
        await self._session.flush()
        return user
