from __future__ import annotations

from core.security.role import UserRole
from pydantic import BaseModel, ConfigDict, Field

from auth.adapter.outbound.redis.refresh_token_repository import RefreshTokenRepository
from auth.app.ports.input.login_use_case import LoginUseCase
from auth.dependencies.auth_provider import (
    get_login_use_case,
    get_refresh_token_repository,
)
from auth.domain.services.token_issuer import (
    REFRESH_TOKEN_EXPIRES_SECONDS,
    create_access_token,
    create_refresh_token,
)
from fastapi import APIRouter, Depends

login_router = APIRouter(tags=["auth-login"])


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
    token: str = Field(description="인증에 사용할 JWT 액세스 토큰")
    refresh_token: str = Field(
        alias="refreshToken", description="토큰 재발급용 리프레시 토큰"
    )


@login_router.post("/login", response_model=LoginResponse, response_model_by_alias=True)
async def login(
    req: LoginRequest,
    use_case: LoginUseCase = Depends(get_login_use_case),
    refresh_repo: RefreshTokenRepository = Depends(get_refresh_token_repository),
):
    login_id = req.user_id.strip()
    user = await use_case.login_user(login_id=login_id, password=req.password)
    role = UserRole(user.role)

    token = create_access_token(sub=str(user.id), roles=[role.value])
    refresh_token, jti = create_refresh_token(sub=str(user.id))
    await refresh_repo.store(
        sub=str(user.id), jti=jti, ttl_seconds=REFRESH_TOKEN_EXPIRES_SECONDS
    )

    return LoginResponse(
        message="로그인됐습니다.",
        id=user.id,
        login_id=user.login_id or login_id,
        nickname=user.nickname,
        email=user.email,
        role=role,
        token=token,
        refresh_token=refresh_token,
    )
