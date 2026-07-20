from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NaverProfile:
    """네이버 로그인(회원 프로필 조회 API) 응답에서 필요한 값만 추린 값 객체."""

    oauth_id: str
    email: str
    name: str
