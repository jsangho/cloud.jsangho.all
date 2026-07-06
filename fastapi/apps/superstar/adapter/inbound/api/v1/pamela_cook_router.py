from __future__ import annotations

from core.matrix.grid_oracle_database_manager import get_db
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends
from superstar.app.ports.input.pamela_cook import PamelaCookUseCase
from superstar.domain.value_objects.role import UserRole

pamela_cook_router = APIRouter(tags=["pamela-cook"])


class LoginRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: str = Field(..., alias="userId", min_length=1, description="로그인 ID")
    password: str = Field(..., min_length=1, description="로그인 비밀번호")


class LoginResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    message: str
    id: int = Field(alias="userId", description="내 DB id")
    login_id: str = Field(alias="loginId", description="로그인 ID")
    nickname: str
    email: str
    role: UserRole


def get_pamela_cook(db: AsyncSession = Depends(get_db)) -> PamelaCookUseCase:
    from superstar.adapter.outbound.pg.pamela_cook_pg_repository import (
        PamelaCookPgRepository,
    )
    from superstar.app.use_cases.pamela_cook_interactor import PamelaCookInteractor

    return PamelaCookInteractor(PamelaCookPgRepository(db))


@pamela_cook_router.post(
    "/login", response_model=LoginResponse, response_model_by_alias=True
)
async def login(
    req: LoginRequest,
    use_case: PamelaCookUseCase = Depends(get_pamela_cook),
):
    login_id = req.user_id.strip()
    user = await use_case.login_user(login_id=login_id, password=req.password)
    return LoginResponse(
        message="로그인됐습니다.",
        id=user.id,
        login_id=user.login_id or login_id,
        nickname=user.nickname,
        email=user.email,
        role=UserRole(user.role),
    )
