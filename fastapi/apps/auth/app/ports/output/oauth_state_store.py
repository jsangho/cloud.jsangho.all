from __future__ import annotations

from abc import ABC, abstractmethod

# 로그인 시작 → 콜백 사이에만 살아 있으면 된다. 짧을수록 재사용 창이 좁다.
OAUTH_STATE_TTL_SECONDS = 5 * 60


class OAuthStateStore(ABC):
    """웹 OAuth의 `state` 보관소.

    `state`는 **CSRF 난수**다. 예전에는 `next_path`를 그대로 실어 보냈는데, 값이
    예측 가능하면 공격자가 자기 인가 코드로 피해자를 로그인시키는 OAuth CSRF를
    막을 수 없다. 난수를 서버가 기억하고, 콜백에서 대조한 뒤 즉시 버린다.

    `next_path`는 이 저장소의 **값** 쪽에 담는다 — 클라이언트에 왕복시키지 않으므로
    변조될 수 없다.
    """

    @abstractmethod
    async def issue(self, *, next_path: str) -> str:
        """난수 `state`를 만들어 `next_path`와 함께 저장하고 그 값을 돌려준다."""

    @abstractmethod
    async def consume(self, *, state: str) -> str | None:
        """`state`가 유효하면 `next_path`를 돌려주고 **즉시 삭제**한다.

        없거나 이미 쓰인 값이면 `None`. 재사용을 막기 위해 조회와 삭제는
        원자적이어야 한다.
        """
