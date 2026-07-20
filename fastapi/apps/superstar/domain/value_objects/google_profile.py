from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GoogleProfile:
    """Google OpenID Connect userinfo 응답에서 필요한 값만 추린 값 객체."""

    oauth_id: str
    email: str
    name: str
