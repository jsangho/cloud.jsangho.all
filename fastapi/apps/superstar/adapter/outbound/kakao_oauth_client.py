from __future__ import annotations

from urllib.parse import urlencode

import httpx
from core.matrix.vault_keymaker_secret_manager import get_keymaker

from fastapi import HTTPException
from superstar.app.ports.output.kakao_identity_provider import KakaoIdentityProvider
from superstar.domain.value_objects.kakao_profile import KakaoProfile

KAKAO_AUTHORIZE_URL = "https://kauth.kakao.com/oauth/authorize"
KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_PROFILE_URL = "https://kapi.kakao.com/v2/user/me"


class KakaoOAuthClient(KakaoIdentityProvider):
    """실제 카카오 로그인(OAuth 2.0) 엔드포인트를 호출하는 어댑터."""

    def __init__(self) -> None:
        keymaker = get_keymaker()
        self._client_id = keymaker.get_secret("KAKAO_CLIENT_ID")
        self._client_secret = keymaker.get_secret("KAKAO_CLIENT_SECRET")
        self._redirect_uri = keymaker.get_secret(
            "KAKAO_OAUTH_REDIRECT_URI",
            "http://127.0.0.1:8000/api/auth/kakao/callback",
        )

    def build_authorize_url(self, *, state: str) -> str:
        params = {
            "response_type": "code",
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "state": state,
        }
        return f"{KAKAO_AUTHORIZE_URL}?{urlencode(params)}"

    async def exchange_code(self, *, code: str) -> KakaoProfile:
        token_data = {
            "grant_type": "authorization_code",
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "code": code,
        }
        if self._client_secret:
            token_data["client_secret"] = self._client_secret

        async with httpx.AsyncClient(timeout=10.0) as client:
            token_response = await client.post(KAKAO_TOKEN_URL, data=token_data)
            if token_response.status_code != 200:
                raise HTTPException(
                    status_code=401, detail="카카오 인증 코드 교환에 실패했습니다."
                )
            access_token = token_response.json().get("access_token")

            profile_response = await client.get(
                KAKAO_PROFILE_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if profile_response.status_code != 200:
                raise HTTPException(
                    status_code=401, detail="카카오 프로필 조회에 실패했습니다."
                )
            payload = profile_response.json()

        oauth_id = payload.get("id")
        kakao_account = payload.get("kakao_account") or {}
        email = kakao_account.get("email")
        if not oauth_id or not email:
            raise HTTPException(
                status_code=401, detail="카카오 계정에서 이메일을 가져오지 못했습니다."
            )
        nickname = (kakao_account.get("profile") or {}).get("nickname", "")
        return KakaoProfile(
            oauth_id=str(oauth_id),
            email=email,
            name=nickname,
        )
