from __future__ import annotations

import secrets

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from auth.app.ports.output.user_admin_repository import UserAdminRepository
from auth.app.ports.output.user_repository import UserRepository
from core.entities.user_model import UserModel
from core.security.password import hash_password
from core.security.role import UserRole


class UserPgRepository(UserRepository, UserAdminRepository):
    """포트 둘을 겸한다 — 로그인이 쓰는 넓은 면과, 사용자 관리가 쓰는 좁은 면.

    `find_by_id`가 양쪽에 다 있지만 구현은 하나다.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_users(
        self, *, query: str | None = None, limit: int = 100
    ) -> tuple[UserModel, ...]:
        stmt = select(UserModel).order_by(UserModel.id.asc()).limit(limit)
        if query:
            # 부분 일치 셋 중 하나. 이메일은 없을 수 있으므로(카카오 선택 동의)
            # `ilike`가 NULL에서 조용히 거짓이 되는 것에 의존한다.
            like = f"%{query}%"
            stmt = stmt.where(
                or_(
                    UserModel.nickname.ilike(like),
                    UserModel.login_id.ilike(like),
                    UserModel.email.ilike(like),
                )
            )
        return tuple((await self._session.scalars(stmt)).all())

    async def count_by_role(self, *, role: str) -> int:
        return int(
            (
                await self._session.scalar(
                    select(func.count())
                    .select_from(UserModel)
                    .where(UserModel.role == role)
                )
            )
            or 0
        )

    async def set_role(self, *, user_id: int, role: str) -> bool:
        """`role` 한 칸만 쓴다. 행을 세션에 올리지 않고 컬럼 하나만 지정해 보낸다 —
        비밀번호 해시나 OAuth 식별자가 실수로 함께 실릴 자리를 만들지 않는다.
        """
        result = await self._session.execute(
            update(UserModel).where(UserModel.id == user_id).values(role=role)
        )
        if result.rowcount == 0:
            return False
        await self._session.flush()
        return True

    async def find_by_oauth(self, *, provider: str, oauth_id: str) -> UserModel | None:
        result = await self._session.execute(
            select(UserModel).where(
                UserModel.oauth_provider == provider,
                UserModel.oauth_id == oauth_id,
            )
        )
        return result.scalar_one_or_none()

    async def find_by_email(self, *, email: str) -> UserModel | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.email == email)
        )
        return result.scalar_one_or_none()

    async def find_by_login_id(self, *, login_id: str) -> UserModel | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.login_id == login_id)
        )
        return result.scalar_one_or_none()

    async def find_by_id(self, *, user_id: int) -> UserModel | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
        return result.scalar_one_or_none()

    async def link_oauth(
        self, *, user: UserModel, provider: str, oauth_id: str
    ) -> UserModel:
        user.oauth_provider = provider
        user.oauth_id = oauth_id
        await self._session.commit()
        await self._session.refresh(user)
        return user

    async def create_oauth_user(
        self,
        *,
        login_id: str,
        nickname: str,
        email: str | None,
        provider: str,
        oauth_id: str,
    ) -> UserModel:
        user = UserModel(
            login_id=login_id,
            nickname=nickname,
            email=email,
            password_hash=hash_password(secrets.token_urlsafe(32)),
            role=UserRole.USER,
            oauth_provider=provider,
            oauth_id=oauth_id,
        )
        self._session.add(user)
        await self._session.commit()
        await self._session.refresh(user)
        return user

    async def create_user(
        self,
        *,
        login_id: str,
        nickname: str,
        email: str,
        password_hash: str,
        role: str,
    ) -> UserModel:
        user = UserModel(
            login_id=login_id,
            nickname=nickname,
            email=email,
            password_hash=password_hash,
            role=role,
        )
        self._session.add(user)
        await self._session.commit()
        await self._session.refresh(user)
        return user
