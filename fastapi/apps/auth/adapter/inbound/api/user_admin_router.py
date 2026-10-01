"""사용자 관리 엔드포인트 — **관리자 전용**.

지금까지 사용자를 **목록으로 볼 방법이 없었다**: 프로필 조회는 `/auth/me`와
`/auth/users/{id}` 둘뿐이라 id를 이미 알 때만 한 명씩 보였다. 역할을 주는 경로는
아예 없어서 기존 관리자 계정은 사람이 DB를 고쳐 만든 것이다.

**비밀번호 해시와 OAuth 식별자는 응답에 넣지 않는다.** 관리자가 사람을 알아보는 데
필요한 것은 닉네임·로그인 아이디·이메일·역할이고, 그 이상은 화면에 둘 이유가 없다.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from auth.app.ports.input.user_admin_use_case import UserAdminUseCase
from auth.dependencies.auth_provider import get_user_admin_use_case
from core.entities.user_model import UserModel
from core.security.dependencies import RoleChecker
from core.security.role import UserRole
from core.security.token_verifier import TokenPayload

user_admin_router = APIRouter(tags=["auth-user-admin"])

_admin_only = RoleChecker(UserRole.ADMIN)


class AdminUserSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int = Field(alias="userId")
    login_id: str = Field(alias="loginId")
    nickname: str
    #: 카카오 이메일 미동의 계정은 없다.
    email: str | None = None
    role: UserRole
    oauth_provider: str | None = Field(default=None, alias="oauthProvider")


class AdminUserListSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    items: list[AdminUserSchema]
    #: **전체** 관리자 수 — `items`에서 센 값이 아니다. 화면이 이 값으로 "마지막
    #: 관리자"를 미리 알려 주므로, 검색으로 잘린 목록에서 세면 거짓으로 잠근다.
    admins: int


class ChangeRoleRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    role: UserRole


def _to_schema(user: UserModel) -> AdminUserSchema:
    return AdminUserSchema(
        userId=user.id,
        loginId=user.login_id or "",
        nickname=user.nickname,
        email=user.email,
        role=UserRole(user.role),
        oauthProvider=user.oauth_provider,
    )


@user_admin_router.get(
    "/admin/users",
    response_model=AdminUserListSchema,
    response_model_by_alias=True,
)
async def list_users(
    q: str | None = Query(
        default=None, description="닉네임·로그인 아이디·이메일 부분 일치"
    ),
    limit: int = Query(default=100, ge=1, le=500),
    _: TokenPayload = Depends(_admin_only),
    use_case: UserAdminUseCase = Depends(get_user_admin_use_case),
):
    users = await use_case.list_users(query=q, limit=limit)
    return AdminUserListSchema(
        items=[_to_schema(user) for user in users],
        admins=await use_case.count_admins(),
    )


@user_admin_router.patch(
    "/admin/users/{user_id}/role",
    response_model=AdminUserSchema,
    response_model_by_alias=True,
)
async def change_user_role(
    user_id: int,
    request: ChangeRoleRequest,
    claims: TokenPayload = Depends(_admin_only),
    use_case: UserAdminUseCase = Depends(get_user_admin_use_case),
):
    """역할 변경. 같은 역할로 바꾸면 아무것도 쓰지 않는다(멱등).

    자기 자신의 관리자 권한을 떼는 것과 마지막 관리자를 떼는 것은 **409**다 —
    아무도 관리자가 아니게 되면 이 화면으로 되돌릴 방법이 없다.
    """
    user = await use_case.change_role(
        user_id=user_id, role=request.role, actor_id=int(claims.sub)
    )
    return _to_schema(user)
