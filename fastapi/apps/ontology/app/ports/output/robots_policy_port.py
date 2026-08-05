from __future__ import annotations

from abc import ABC, abstractmethod


class RobotsPolicyPort(ABC):
    """robots.txt 판정 출력 포트."""

    @abstractmethod
    async def is_allowed(self, url: str) -> bool:
        """이 주소를 가져가도 되는지.

        robots.txt를 읽지 못했을 때 무엇을 돌려줄지는 구현이 정한다. 다만 **모르면
        가져가지 않는 쪽**이 기본이어야 한다 — 상대 서버의 의사를 확인 못 한 상태다.
        """
