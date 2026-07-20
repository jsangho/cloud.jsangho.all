from __future__ import annotations

from urllib.parse import urlencode

import httpx
from core.matrix.vault_keymaker_secret_manager import get_keymaker

from fastapi import HTTPException
from superstar.app.ports.output.naver_identity_provider import NaverIdentityProvider
from superstar.domain.value_objects.naver_profile import NaverProfile

NAVER_AUTHORIZE_URL = "https://nid.naver.com/oauth2.0/authorize"
NAVER_TOKEN_URL = "https://nid.naver.com/oauth2.0/token"
NAVER_PROFILE_URL = "https://openapi.naver.com/v1/nid/me"


class NaverOAuthClient(NaverIdentityProvider):
    """실제 네이버 로그인(OAuth 2.0) 엔드포인트를 호출하는 어댑터."""

    def __init__(self) -> None:
        keymaker = get_keymaker()
        self._client_id = keymaker.get_secret("NAVER_CLIENT_ID")
        self._client_secret = keymaker.get_secret("NAVER_CLIENT_SECRET")
        self._redirect_uri = keymaker.get_secret(
            "NAVER_OAUTH_REDIRECT_URI",
            "http://127.0.0.1:8000/api/auth/naver/callback",
        )

    def build_authorize_url(self, *, state: str) -> str:
        params = {
            "response_type": "code",
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "state": state,
        }
        return f"{NAVER_AUTHORIZE_URL}?{urlencode(params)}"

    async def exchange_code(self, *, code: str) -> NaverProfile:
        async with httpx.AsyncClient(timeout=10.0) as client:
            token_response = await client.get(
                NAVER_TOKEN_URL,
                params={
                    "grant_type": "authorization_code",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "code": code,
                },
            )
            if token_response.status_code != 200:
                raise HTTPException(
                    status_code=401, detail="네이버 인증 코드 교환에 실패했습니다."
                )
            access_token = token_response.json().get("access_token")

            profile_response = await client.get(
                NAVER_PROFILE_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if profile_response.status_code != 200:
                raise HTTPException(
                    status_code=401, detail="네이버 프로필 조회에 실패했습니다."
                )
            payload = profile_response.json()

        if payload.get("resultcode") != "00":
            raise HTTPException(
                status_code=401, detail="네이버 프로필 조회에 실패했습니다."
            )

        info = payload.get("response") or {}
        oauth_id = info.get("id")
        email = info.get("email")
        if not oauth_id or not email:
            raise HTTPException(
                status_code=401, detail="네이버 계정에서 이메일을 가져오지 못했습니다."
            )
        return NaverProfile(
            oauth_id=oauth_id,
            email=email,
            name=info.get("name", ""),
        )
