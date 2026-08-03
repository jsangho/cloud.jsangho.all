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
    # 카카오 이메일 미동의 계정은 email이 없다 — 화면 필수 요소로 만들면 안 된다.
    email: str | None = None
    role: UserRole
    oauth_provider: str | None = Field(default=None, alias="oauthProvider")


@profile_router.get(
    "/me", response_model=UserProfileResponse, response_model_by_alias=True
)
async def get_my_profile(
    use_case: ProfileUseCase = Depends(get_profile_use_case),
    claims: TokenPayload = Depends(get_current_user),
):
    """현재 로그인한 사용자.

    액세스 토큰이 httpOnly 쿠키에 있으면 프론트는 JS로 토큰을 읽을 수 없어
    `sub`(유저 id)를 직접 알아낼 방법이 없다. 그래서 "나는 누구인가"를
    서버에 묻는 창구가 필요하다.

    `get_current_user`가 `Authorization: Bearer`와 쿠키를 모두 받으므로
    모바일·웹이 같은 엔드포인트를 쓴다.
    """
    user = await use_case.get_user_by_id(user_id=int(claims.sub))
    return UserProfileResponse(
        id=user.id,
        login_id=user.login_id or "",
        nickname=user.nickname,
        email=user.email,
        role=UserRole(user.role),
        oauth_provider=user.oauth_provider,
    )


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
