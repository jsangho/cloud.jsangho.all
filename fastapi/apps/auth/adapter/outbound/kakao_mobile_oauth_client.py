"""모바일 카카오 로그인 어댑터 — 인가 코드 → 토큰 교환 → 프로필 조회.

앱은 인가 코드만 넘기고 `client_secret`을 모른다(D-1). 여기가 카카오 토큰을 만지는
유일한 지점이며, 카카오 refresh token은 이 모듈 밖으로 나가면 반드시 암호화된다.
"""

from __future__ import annotations

import httpx
from core.matrix.vault_keymaker_secret_manager import get_keymaker

from auth.app.ports.output.kakao_mobile_identity_provider import (
    KakaoMobileIdentityProvider,
)
from auth.domain.value_objects.kakao_identity import KakaoProfile, KakaoTokenSet
from fastapi import HTTPException

KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_PROFILE_URL = "https://kapi.kakao.com/v2/user/me"
KAKAO_UNLINK_URL = "https://kapi.kakao.com/v1/user/unlink"

# 카카오 장애가 곧 우리 장애가 되지 않도록 연결·읽기를 나눠 짧게 잡는다.
_TIMEOUT = httpx.Timeout(connect=3.0, read=7.0, write=7.0, pool=3.0)


class KakaoMobileOAuthClient(KakaoMobileIdentityProvider):
    def __init__(self) -> None:
        keymaker = get_keymaker()
        self._client_id = keymaker.get_secret("KAKAO_CLIENT_ID")
        self._client_secret = keymaker.get_secret("KAKAO_CLIENT_SECRET")
        # 앱이 보낸 redirect_uri를 그대로 믿지 않고 등록값과 대조한다 —
        # 임의 URI로 코드를 교환하게 두면 인가 코드 탈취 경로가 열린다.
        self._allowed_redirect_uri = keymaker.get_secret("KAKAO_MOBILE_REDIRECT_URI")

    async def exchange_code(self, *, code: str, redirect_uri: str) -> KakaoTokenSet:
        if not self._allowed_redirect_uri:
            raise HTTPException(
                status_code=500,
                detail="KAKAO_MOBILE_REDIRECT_URI가 설정되지 않았습니다.",
            )
        if redirect_uri != self._allowed_redirect_uri:
            raise HTTPException(
                status_code=400, detail="등록되지 않은 redirect_uri입니다."
            )

        data = {
            "grant_type": "authorization_code",
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "code": code,
        }
        if self._client_secret:
            data["client_secret"] = self._client_secret

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            try:
                response = await client.post(KAKAO_TOKEN_URL, data=data)
            except httpx.TimeoutException as exc:
                raise HTTPException(
                    status_code=504, detail="카카오 응답이 지연되고 있습니다."
                ) from exc
            except httpx.HTTPError as exc:
                raise HTTPException(
                    status_code=502, detail="카카오 서버와 통신하지 못했습니다."
                ) from exc

        if response.status_code == 400 or response.status_code == 401:
            # 만료·재사용된 인가 코드. 앱은 재로그인을 안내한다.
            raise HTTPException(
                status_code=401, detail="카카오 인증 코드 교환에 실패했습니다."
            )
        if response.status_code != 200:
            raise HTTPException(status_code=502, detail="카카오 서버 오류입니다.")

        payload = response.json()
        return KakaoTokenSet(
            access_token=payload.get("access_token", ""),
            refresh_token=payload.get("refresh_token", ""),
            expires_in=int(payload.get("expires_in", 0)),
            refresh_token_expires_in=int(payload.get("refresh_token_expires_in", 0)),
        )

    async def fetch_profile(self, *, access_token: str) -> KakaoProfile:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            try:
                response = await client.get(
                    KAKAO_PROFILE_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
            except httpx.TimeoutException as exc:
                raise HTTPException(
                    status_code=504, detail="카카오 응답이 지연되고 있습니다."
                ) from exc
            except httpx.HTTPError as exc:
                raise HTTPException(
                    status_code=502, detail="카카오 서버와 통신하지 못했습니다."
                ) from exc

        if response.status_code == 401:
            raise HTTPException(
                status_code=401, detail="카카오 프로필 조회에 실패했습니다."
            )
        if response.status_code != 200:
            raise HTTPException(status_code=502, detail="카카오 서버 오류입니다.")

        payload = response.json()
        kakao_id = payload.get("id")
        if not kakao_id:
            raise HTTPException(
                status_code=401, detail="카카오 회원번호를 가져오지 못했습니다."
            )

        account = payload.get("kakao_account") or {}
        profile = account.get("profile") or {}
        # 이메일 미동의는 정상 — None으로 통과시킨다(§4-G). 여기서 401을 내면
        # 선택 동의를 하지 않은 계정이 로그인 자체를 못 한다.
        return KakaoProfile(
            kakao_id=str(kakao_id),
            nickname=(profile.get("nickname") or "").strip(),
            email=account.get("email"),
        )

    async def unlink(self, *, kakao_access_token: str) -> None:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            try:
                await client.post(
                    KAKAO_UNLINK_URL,
                    headers={"Authorization": f"Bearer {kakao_access_token}"},
                )
            except httpx.HTTPError as exc:
                raise HTTPException(
                    status_code=502, detail="카카오 연결 해제에 실패했습니다."
                ) from exc
