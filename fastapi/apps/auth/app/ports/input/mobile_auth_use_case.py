from __future__ import annotations

from abc import ABC, abstractmethod

from auth.app.dtos.mobile_auth_dto import (
    MobileDeviceDto,
    MobileDeviceSessionDto,
    MobileLoginDto,
    MobileSessionDto,
)


class MobileAuthUseCase(ABC):
    """모바일(Flutter) 전용 인증 유스케이스.

    웹 세션과 완전히 분리된 네임스페이스를 쓴다 — 여기서 발급한 리프레시 토큰은
    웹 엔드포인트에서 통하지 않고, 그 역도 마찬가지다(D-3).
    """

    @abstractmethod
    async def login_with_kakao(
        self, *, code: str, redirect_uri: str, device: MobileDeviceDto
    ) -> MobileLoginDto: ...

    @abstractmethod
    async def refresh(self, *, refresh_token: str) -> MobileSessionDto: ...

    @abstractmethod
    async def logout(
        self, *, user_id: str, refresh_token: str, access_jti: str, access_exp: int
    ) -> None:
        """현재 기기 세션만 끊는다.

        세션 키에 인증된 `user_id`가 들어가므로, 남의 리프레시 토큰을 보내도
        자기 세션 외에는 지워지지 않는다.
        """

    @abstractmethod
    async def logout_all(
        self, *, user_id: str, access_jti: str, access_exp: int
    ) -> None:
        """모바일 세션 전체를 끊는다. 웹 세션은 그대로 둔다(D-4)."""

    @abstractmethod
    async def list_devices(
        self, *, user_id: str, current_device_id: str
    ) -> list[MobileDeviceSessionDto]: ...
