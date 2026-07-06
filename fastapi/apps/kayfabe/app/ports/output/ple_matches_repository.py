from __future__ import annotations

from abc import ABC, abstractmethod

from kayfabe.app.dtos.ple_events_dto import MatchSnapshotQuery


class PleMatchesRepository(ABC):
    """PLE 경기 정보 조회 출력 포트."""

    @abstractmethod
    async def list_competitor_names(self) -> list[str]:
        """동기화된 전체 경기 카드에서 선수명 목록(중복 제거·정렬 전)."""
        ...

    @abstractmethod
    async def list_match_snapshots(self) -> list[MatchSnapshotQuery]:
        """Records 계산에 필요한 이벤트/경기 스냅샷(예측/투표 제외)."""
        ...
