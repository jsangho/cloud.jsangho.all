from __future__ import annotations

from urllib.parse import urlencode

import httpx
from core.matrix.vault_keymaker_secret_manager import get_keymaker

from auth.app.ports.output.oauth_identity_provider import OAuthIdentityProvider
from auth.domain.value_objects.oauth_profile import OAuthProfile
from fastapi import HTTPException

GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


class GoogleOAuthClient(OAuthIdentityProvider):
    """실제 Google OAuth 2.0 엔드포인트를 호출하는 어댑터."""

    def __init__(self) -> None:
        keymaker = get_keymaker()
        self._client_id = keymaker.get_secret("GOOGLE_CLIENT_ID")
        self._client_secret = keymaker.get_secret("GOOGLE_CLIENT_SECRET")
        self._redirect_uri = keymaker.get_secret(
            "GOOGLE_OAUTH_REDIRECT_URI",
            "http://127.0.0.1:8000/api/auth/google/callback",
        )

    def build_authorize_url(self, *, state: str) -> str:
        params = {
            "response_type": "code",
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "scope": "openid email profile",
            "state": state,
            "access_type": "online",
            "prompt": "select_account",
        }
        return f"{GOOGLE_AUTHORIZE_URL}?{urlencode(params)}"

    async def exchange_code(self, *, code: str) -> OAuthProfile:
        async with httpx.AsyncClient(timeout=10.0) as client:
            token_response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "redirect_uri": self._redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            if token_response.status_code != 200:
                raise HTTPException(
                    status_code=401, detail="Google 인증 코드 교환에 실패했습니다."
                )
            access_token = token_response.json().get("access_token")

            userinfo_response = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if userinfo_response.status_code != 200:
                raise HTTPException(
                    status_code=401, detail="Google 프로필 조회에 실패했습니다."
                )
            userinfo = userinfo_response.json()

        oauth_id = userinfo.get("sub")
        email = userinfo.get("email")
        if not oauth_id or not email:
            raise HTTPException(
                status_code=401, detail="Google 계정에서 이메일을 가져오지 못했습니다."
            )
        return OAuthProfile(
            oauth_id=oauth_id,
            email=email,
            name=userinfo.get("name", ""),
        )
