from __future__ import annotations

import re
import secrets

from superstar.app.ports.input.clark_kent import ClarkKentUseCase
from superstar.app.ports.output.clark_kent_repository import ClarkKentRepository
from superstar.app.ports.output.google_identity_provider import GoogleIdentityProvider
from superstar.domain.entities.user_model import UserModel

GOOGLE_PROVIDER = "google"
_LOGIN_ID_SAFE_CHARS = re.compile(r"[^a-zA-Z0-9_]+")


class ClarkKentInteractor(ClarkKentUseCase):
    """Google 소셜 로그인(OAuth) 유스케이스 구현체."""

    def __init__(
        self,
        identity_provider: GoogleIdentityProvider,
        repository: ClarkKentRepository,
    ) -> None:
        self._identity_provider = identity_provider
        self._repository = repository

    def build_authorize_url(self, *, next_path: str) -> str:
        safe_next_path = next_path if next_path.startswith("/") else "/"
        return self._identity_provider.build_authorize_url(state=safe_next_path)

    async def login_with_google(self, *, code: str) -> UserModel:
        profile = await self._identity_provider.exchange_code(code=code)

        user = await self._repository.find_by_oauth(
            provider=GOOGLE_PROVIDER, oauth_id=profile.oauth_id
        )
        if user is not None:
            return user

        user = await self._repository.find_by_email(email=profile.email)
        if user is not None:
            return await self._repository.link_oauth(
                user=user, provider=GOOGLE_PROVIDER, oauth_id=profile.oauth_id
            )

        login_id = await self._generate_unique_login_id(profile.email)
        nickname = profile.name.strip() or login_id
        return await self._repository.create_oauth_user(
            login_id=login_id,
            nickname=nickname,
            email=profile.email,
            provider=GOOGLE_PROVIDER,
            oauth_id=profile.oauth_id,
        )

    async def _generate_unique_login_id(self, email: str) -> str:
        base = _LOGIN_ID_SAFE_CHARS.sub("_", email.split("@", 1)[0]).strip("_")
        base = base or "user"

        candidate = base
        while await self._repository.find_by_login_id(login_id=candidate) is not None:
            candidate = f"{base}_{secrets.token_hex(3)}"
        return candidate
