from __future__ import annotations

from core.matrix.grid_oracle_database_manager import get_db
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends
from superstar.app.ports.input.murder_list import MurderListUseCase
from superstar.domain.value_objects.role import UserRole

murder_list_router = APIRouter(tags=["murder-list"])


class UserProfileResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int = Field(alias="userId")
    login_id: str = Field(alias="loginId")
    nickname: str
    email: str
    role: UserRole


def get_murder_list(db: AsyncSession = Depends(get_db)) -> MurderListUseCase:
    from superstar.adapter.outbound.pg.murder_list_pg_repository import (
        MurderListPgRepository,
    )
    from superstar.app.use_cases.murder_list_interactor import MurderListInteractor

    return MurderListInteractor(MurderListPgRepository(db))


@murder_list_router.get(
    "/users/{user_id}",
    response_model=UserProfileResponse,
    response_model_by_alias=True,
)
async def get_user_profile(
    user_id: int,
    use_case: MurderListUseCase = Depends(get_murder_list),
):
    user = await use_case.get_user_by_id(user_id=user_id)
    return UserProfileResponse(
        id=user.id,
        login_id=user.login_id or "",
        nickname=user.nickname,
        email=user.email,
        role=UserRole(user.role),
    )
