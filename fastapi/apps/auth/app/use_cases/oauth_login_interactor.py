from __future__ import annotations

import re
import secrets

from core.entities.user_model import UserModel

from auth.app.ports.input.oauth_login_use_case import OAuthLoginUseCase
from auth.app.ports.output.oauth_identity_provider import OAuthIdentityProvider
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
    ) -> None:
        self._provider = provider
        self._identity_provider = identity_provider
        self._repository = repository

    def build_authorize_url(self, *, next_path: str) -> str:
        safe_next_path = next_path if next_path.startswith("/") else "/"
        return self._identity_provider.build_authorize_url(state=safe_next_path)

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
