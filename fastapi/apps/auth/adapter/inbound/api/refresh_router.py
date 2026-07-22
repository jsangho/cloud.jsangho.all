from __future__ import annotations

from core.matrix.grid_oracle_database_manager import get_db
from core.security.role import UserRole
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from auth.adapter.outbound.pg.user_pg_repository import UserPgRepository
from auth.adapter.outbound.redis.refresh_token_repository import (
    REUSE_DETECTED,
    RefreshTokenRepository,
)
from auth.dependencies.auth_provider import get_refresh_token_repository
from auth.domain.services.token_issuer import (
    REFRESH_TOKEN_EXPIRES_SECONDS,
    create_access_token,
    create_refresh_token,
)
from fastapi import APIRouter, Depends, HTTPException

refresh_router = APIRouter(tags=["auth-refresh"])


class RefreshRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    refresh_token: str = Field(..., alias="refreshToken", min_length=1)


class RefreshResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    token: str
    refresh_token: str = Field(alias="refreshToken")


@refresh_router.post(
    "/refresh", response_model=RefreshResponse, response_model_by_alias=True
)
async def refresh(
    req: RefreshRequest,
    db: AsyncSession = Depends(get_db),
    refresh_repo: RefreshTokenRepository = Depends(get_refresh_token_repository),
):
    jti = req.refresh_token.split(".", 1)[0]

    sub = await refresh_repo.consume(jti=jti)
    if sub is None or sub == REUSE_DETECTED:
        raise HTTPException(
            status_code=401,
            detail="리프레시 토큰이 유효하지 않습니다. 다시 로그인해 주세요.",
        )

    user = await UserPgRepository(db).find_by_id(user_id=int(sub))
    if user is None:
        raise HTTPException(status_code=401, detail="유저를 찾을 수 없습니다.")

    role = UserRole(user.role)
    new_access_token = create_access_token(sub=sub, roles=[role.value])
    new_refresh_token, new_jti = create_refresh_token(sub=sub)
    await refresh_repo.store(
        sub=sub, jti=new_jti, ttl_seconds=REFRESH_TOKEN_EXPIRES_SECONDS
    )

    return RefreshResponse(token=new_access_token, refresh_token=new_refresh_token)
