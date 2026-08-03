from __future__ import annotations

import re
import secrets

from core.entities.user_model import UserModel

from auth.app.ports.input.oauth_login_use_case import OAuthLoginUseCase
from auth.app.ports.output.oauth_identity_provider import OAuthIdentityProvider
from auth.app.ports.output.oauth_state_store import OAuthStateStore
from auth.app.ports.output.user_repository import UserRepository

_LOGIN_ID_SAFE_CHARS = re.compile(r"[^a-zA-Z0-9_]+")


class OAuthLoginInteractor(OAuthLoginUseCase):
    """Google/Kakao/Naver 공통 소셜 로그인 유스케이스 구현체.

    provider별로 다른 부분(IdentityProvider 어댑터)만 주입받는다 — 유저 조회/생성 로직은
    provider를 인자로 받는 `UserRepository`를 통해 3개 provider가 그대로 재사용한다.
    """

    def __init__(
        self,
        *,
        provider: str,
        identity_provider: OAuthIdentityProvider,
        repository: UserRepository,
        state_store: OAuthStateStore,
    ) -> None:
        self._provider = provider
        self._identity_provider = identity_provider
        self._repository = repository
        self._state_store = state_store

    async def build_authorize_url(self, *, next_path: str) -> str:
        """`state`에 `next_path`를 싣지 않는다.

        예전에는 `state=next_path`였다. 값이 예측 가능하면 CSRF 방어가 성립하지
        않는다 — 공격자가 자기 인가 코드로 피해자를 로그인시킬 수 있다.
        이제 `state`는 난수이고 `next_path`는 서버(Redis)가 기억한다.
        """
        state = await self._state_store.issue(next_path=next_path)
        return self._identity_provider.build_authorize_url(state=state)

    async def resolve_next_path(self, *, state: str) -> str | None:
        return await self._state_store.consume(state=state)

    async def login(self, *, code: str) -> UserModel:
        profile = await self._identity_provider.exchange_code(code=code)

        user = await self._repository.find_by_oauth(
            provider=self._provider, oauth_id=profile.oauth_id
        )
        if user is not None:
            return user

        user = await self._repository.find_by_email(email=profile.email)
        if user is not None:
            return await self._repository.link_oauth(
                user=user, provider=self._provider, oauth_id=profile.oauth_id
            )

        login_id = await self._generate_unique_login_id(profile.email)
        nickname = profile.name.strip() or login_id
        return await self._repository.create_oauth_user(
            login_id=login_id,
            nickname=nickname,
            email=profile.email,
            provider=self._provider,
            oauth_id=profile.oauth_id,
        )

    async def _generate_unique_login_id(self, email: str) -> str:
        base = _LOGIN_ID_SAFE_CHARS.sub("_", email.split("@", 1)[0]).strip("_")
        base = base or "user"

        candidate = base
        while await self._repository.find_by_login_id(login_id=candidate) is not None:
            candidate = f"{base}_{secrets.token_hex(3)}"
        return candidate
