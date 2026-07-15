from __future__ import annotations

from core.matrix.grid_oracle_database_manager import get_db
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends
from superstar.app.ports.input.jason_mask import JasonMaskUseCase
from superstar.app.ports.input.jason_mask_schema import JasonMaskSchema
from superstar.domain.value_objects.role import UserRole

jason_mask_router = APIRouter(tags=["jason-mask"])


class SignupRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: str = Field(..., alias="userId", min_length=1, description="로그인 ID")
    nickname: str = Field(..., min_length=1, description="닉네임")
    email: str = Field(..., min_length=1, description="이메일")
    password: str = Field(..., min_length=1, description="비밀번호")
    password_confirm: str = Field(
        ...,
        alias="passwordConfirm",
        min_length=1,
        description="비밀번호 확인",
    )


class SignupResponse(BaseModel):
    message: str
    nickname: str
    email: str
    role: UserRole


def get_jason_mask(db: AsyncSession = Depends(get_db)) -> JasonMaskUseCase:
    from superstar.adapter.outbound.pg.jason_mask_pg_repository import (
        JasonMaskPgRepository,
    )
    from superstar.app.use_cases.jason_mask_interactor import JasonMaskInteractor

    return JasonMaskInteractor(JasonMaskPgRepository(db))


@jason_mask_router.post("/signup", response_model=SignupResponse)
async def signup(
    req: SignupRequest,
    use_case: JasonMaskUseCase = Depends(get_jason_mask),
):
    user_schema = JasonMaskSchema(
        login_id=req.user_id.strip(),
        nickname=req.nickname,
        email=req.email,
        password=req.password,
        password_confirm=req.password_confirm,
        role=UserRole.USER,
    )
    await use_case.save_user(user_schema=user_schema)
    return SignupResponse(
        message="회원가입됐습니다.",
        nickname=req.nickname,
        email=req.email,
        role=UserRole.USER,
    )
