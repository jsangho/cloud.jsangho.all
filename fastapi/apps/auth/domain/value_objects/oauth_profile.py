from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OAuthProfile:
    """Google/Kakao/Naver 프로필 조회 응답에서 필요한 값만 추린 공통 값 객체."""

    oauth_id: str
    email: str
    name: str
