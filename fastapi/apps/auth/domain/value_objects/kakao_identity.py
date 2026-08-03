from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KakaoTokenSet:
    """카카오 `/oauth/token` 응답 중 서버가 쓰는 값.

    `OAuthProfile`과 달리 토큰 자체를 담는다 — 카카오 refresh token은 서버에만
    남기고 클라이언트에 절대 반환하지 않는다(하네스 D-1·§3).
    """

    access_token: str
    refresh_token: str
    expires_in: int
    refresh_token_expires_in: int


@dataclass(frozen=True)
class KakaoProfile:
    """카카오 `/v2/user/me` 응답에서 추린 값.

    `email`이 `None`인 것은 오류가 아니라 정상이다 — 카카오 이메일은 선택 동의
    항목이라 동의하지 않은 계정에는 값이 없다(§4-G). 계정 식별자는 회원번호
    (`kakao_id`)이고 이메일은 식별자로 쓰지 않는다(D-5).
    """

    kakao_id: str
    nickname: str
    email: str | None
