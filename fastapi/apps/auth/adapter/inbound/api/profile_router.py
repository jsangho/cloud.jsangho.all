from __future__ import annotations

from core.security.dependencies import get_current_user, require_self_or_admin
from core.security.role import UserRole
from core.security.token_verifier import TokenPayload
from pydantic import BaseModel, ConfigDict, Field

from auth.app.ports.input.profile_use_case import ProfileUseCase
from auth.dependencies.auth_provider import get_profile_use_case
from fastapi import APIRouter, Depends

profile_router = APIRouter(tags=["auth-profile"])


class UserProfileResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int = Field(alias="userId")
    login_id: str = Field(alias="loginId")
    nickname: str
    email: str
    role: UserRole
    oauth_provider: str | None = Field(default=None, alias="oauthProvider")


@profile_router.get(
    "/users/{user_id}",
    response_model=UserProfileResponse,
    response_model_by_alias=True,
)
async def get_user_profile(
    user_id: int,
    use_case: ProfileUseCase = Depends(get_profile_use_case),
    claims: TokenPayload = Depends(get_current_user),
):
    require_self_or_admin(user_id=user_id, claims=claims)
    user = await use_case.get_user_by_id(user_id=user_id)
    return UserProfileResponse(
        id=user.id,
        login_id=user.login_id or "",
        nickname=user.nickname,
        email=user.email,
        role=UserRole(user.role),
        oauth_provider=user.oauth_provider,
    )
