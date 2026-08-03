from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

MOBILE = "mobile"
WEB = "web"


class SessionNotFoundError(Exception):
    """토큰에 해당하는 세션이 없다(만료·폐기·위조). 클라이언트에는 401."""


class SessionReuseDetectedError(Exception):
    """이미 회전된 토큰이 다시 쓰였다 = 탈취 의심.

    해당 플랫폼 세션 전체가 폐기된 뒤 발생한다. 반대 플랫폼은 건드리지 않는다(D-3).
    """

    def __init__(self, *, user_id: str) -> None:
        super().__init__(f"refresh token reuse detected for user {user_id}")
        self.user_id = user_id


@dataclass(frozen=True)
class SessionMeta:
    """세션 HASH에 함께 적히는 발급 시점의 부가 정보(하네스 §5.2).

    모바일 전용 필드와 웹 전용 필드가 한 구조체에 있고, 쓰지 않는 쪽은 빈 문자열이다.
    플랫폼별 구조체를 나누면 스토어 인터페이스가 플랫폼 수만큼 늘어난다.
    """

    device_id: str = ""
    device_name: str = ""
    app_version: str = ""
    os: str = ""
    user_agent_hash: str = ""
    ip: str = ""


@dataclass(frozen=True)
class SessionInfo:
    """기기 목록 조회 결과 한 줄."""

    jti: str
    device_id: str
    device_name: str
    os: str
    app_version: str
    issued_at: int


class SessionStore(ABC):
    """플랫폼별로 격리된 리프레시 세션 저장소(D-3).

    유스케이스는 이 포트에만 의존한다 — Redis 키 스키마는 어댑터의 사정이다.
    """

    @abstractmethod
    async def create_session(
        self, *, platform: str, user_id: str, meta: SessionMeta
    ) -> tuple[str, str]:
        """(refresh_token, jti) 반환. 기기당 1세션·플랫폼당 상한을 여기서 강제한다."""

    @abstractmethod
    async def rotate_session(
        self, *, platform: str, refresh_token: str
    ) -> tuple[str, str, str]:
        """(new_refresh_token, new_jti, user_id).

        실패 시 `SessionNotFoundError` 또는 `SessionReuseDetectedError`를 던진다.
        """

    @abstractmethod
    async def revoke_session(
        self, *, platform: str, user_id: str, jti: str
    ) -> None: ...

    @abstractmethod
    async def revoke_all(self, *, platform: str, user_id: str) -> None:
        """해당 플랫폼 세션만 폐기한다. 반대 플랫폼은 살아 있어야 한다(D-3)."""

    @abstractmethod
    async def list_sessions(
        self, *, platform: str, user_id: str
    ) -> list[SessionInfo]: ...

    @abstractmethod
    async def blacklist_access_token(self, *, jti: str, ttl_seconds: int) -> None:
        """access token 강제 무효화. 키 이름은 기존 `auth:blacklist:*`를 유지한다(§4-K)."""
