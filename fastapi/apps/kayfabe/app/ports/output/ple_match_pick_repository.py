from __future__ import annotations

from abc import ABC, abstractmethod

from kayfabe.app.dtos.ple_match_pick_dto import LeaderboardQuery


class PleMatchPickRepository(ABC):
    """PLE 예측 순위 조회 출력 포트."""

    @abstractmethod
    async def list_ranked(self, limit: int) -> list[LeaderboardQuery]:
        """점수 순 랭킹 목록."""
        ...

    @abstractmethod
    async def get_ranked_by_nickname(self, nickname: str) -> LeaderboardQuery | None:
        """닉네임으로 단일 랭킹 행 조회."""
        ...
