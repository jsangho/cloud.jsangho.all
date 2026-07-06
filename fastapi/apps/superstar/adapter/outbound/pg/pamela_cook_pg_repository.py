from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from superstar.app.ports.output.pamela_cook_repository import PamelaCookRepository
from superstar.domain.entities.user_model import UserModel


class PamelaCookPgRepository(PamelaCookRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_login_id(self, login_id: str) -> UserModel | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.login_id == login_id)
        )
        return result.scalar_one_or_none()
