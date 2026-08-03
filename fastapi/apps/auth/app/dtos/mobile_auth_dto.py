from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MobileDeviceDto:
    """앱이 보낸 기기 메타. 세션 HASH에 그대로 적힌다(§5.2)."""

    device_id: str
    device_name: str
    os: str
    app_version: str
    ip: str = ""


@dataclass(frozen=True)
class MobileUserDto:
    user_id: int
    nickname: str
    email: str | None
    role: str


@dataclass(frozen=True)
class MobileSessionDto:
    """리프레시가 돌려주는 토큰 한 벌. 유저 정보는 로그인 때만 내려간다."""

    token: str
    refresh_token: str
    expires_in: int


@dataclass(frozen=True)
class MobileLoginDto:
    """로그인 응답. `user`가 항상 채워지는 점이 `MobileSessionDto`와 다르다."""

    token: str
    refresh_token: str
    expires_in: int
    user: MobileUserDto


@dataclass(frozen=True)
class MobileDeviceSessionDto:
    """기기 목록 한 줄."""

    jti: str
    device_id: str
    device_name: str
    os: str
    app_version: str
    issued_at: int
    current: bool
