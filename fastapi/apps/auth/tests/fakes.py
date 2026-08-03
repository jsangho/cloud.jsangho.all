"""테스트용 대역(fake) 모음.

실제 카카오·Postgres 호출 없이 유스케이스를 돌리기 위한 것들이다.
Redis는 대역 대신 `fakeredis[lua]`를 써서 Lua 스크립트까지 실제로 실행한다.
"""

from __future__ import annotations

from core.entities.user_model import UserModel

from auth.app.ports.output.kakao_mobile_identity_provider import (
    KakaoMobileIdentityProvider,
)
from auth.app.ports.output.kakao_token_vault import KakaoTokenVault
from auth.app.ports.output.user_repository import UserRepository
from auth.domain.value_objects.kakao_identity import KakaoProfile, KakaoTokenSet


class FakeKakao(KakaoMobileIdentityProvider):
    def __init__(self, profile: KakaoProfile) -> None:
        self.profile = profile
        self.unlinked = False

    async def exchange_code(self, *, code: str, redirect_uri: str) -> KakaoTokenSet:
        return KakaoTokenSet(
            access_token="kakao-access",
            refresh_token="kakao-refresh",
            expires_in=21600,
            refresh_token_expires_in=5184000,
        )

    async def fetch_profile(self, *, access_token: str) -> KakaoProfile:
        return self.profile

    async def unlink(self, *, kakao_access_token: str) -> None:
        self.unlinked = True


class FakeUsers(UserRepository):
    def __init__(self, seed: list[UserModel] | None = None) -> None:
        self.rows: list[UserModel] = list(seed or [])
        self._next_id = max((u.id for u in self.rows), default=0) + 1

    async def find_by_oauth(self, *, provider: str, oauth_id: str) -> UserModel | None:
        return next(
            (
                u
                for u in self.rows
                if u.oauth_provider == provider and u.oauth_id == oauth_id
            ),
            None,
        )

    async def find_by_email(self, *, email: str) -> UserModel | None:
        return next((u for u in self.rows if u.email == email), None)

    async def find_by_login_id(self, *, login_id: str) -> UserModel | None:
        return next((u for u in self.rows if u.login_id == login_id), None)

    async def find_by_id(self, *, user_id: int) -> UserModel | None:
        return next((u for u in self.rows if u.id == user_id), None)

    async def link_oauth(
        self, *, user: UserModel, provider: str, oauth_id: str
    ) -> UserModel:
        user.oauth_provider = provider
        user.oauth_id = oauth_id
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
            id=self._next_id,
            login_id=login_id,
            nickname=nickname,
            email=email,
            password_hash="x",
            role="user",
            oauth_provider=provider,
            oauth_id=oauth_id,
        )
        self._next_id += 1
        self.rows.append(user)
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
        raise NotImplementedError


class FakeVault(KakaoTokenVault):
    def __init__(self) -> None:
        self.stored: dict[str, str] = {}

    async def store(self, *, user_id: str, refresh_token: str) -> None:
        self.stored[user_id] = refresh_token

    async def load(self, *, user_id: str) -> str | None:
        return self.stored.get(user_id)

    async def delete(self, *, user_id: str) -> None:
        self.stored.pop(user_id, None)
