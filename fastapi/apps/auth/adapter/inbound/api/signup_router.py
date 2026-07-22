from __future__ import annotations

from core.security.role import UserRole
from pydantic import BaseModel, ConfigDict, Field

from auth.app.ports.input.signup_use_case import SignupUseCase
from auth.dependencies.auth_provider import get_signup_use_case
from fastapi import APIRouter, Depends

signup_router = APIRouter(tags=["auth-signup"])


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


@signup_router.post("/signup", response_model=SignupResponse)
async def signup(
    req: SignupRequest,
    use_case: SignupUseCase = Depends(get_signup_use_case),
):
    await use_case.signup(
        login_id=req.user_id.strip(),
        nickname=req.nickname,
        email=req.email,
        password=req.password,
        password_confirm=req.password_confirm,
    )
    return SignupResponse(
        message="회원가입됐습니다.",
        nickname=req.nickname,
        email=req.email,
        role=UserRole.USER,
    )
