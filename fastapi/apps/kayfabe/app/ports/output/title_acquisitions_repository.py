from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from kayfabe.app.dtos.title_acquisitions_dto import ChampionshipBoardResponse


@dataclass(frozen=True)
class TitleAcquisitionRow:
    belt_name: str
    won_at: str
    won_at_slug: str | None
    match_key: str | None


class TitleAcquisitionsRepository(ABC):
    @abstractmethod
    async def count(self) -> int: ...

    @abstractmethod
    async def needs_real_resync(self) -> bool: ...

    @abstractmethod
    async def list_by_competitor(
        self, *, competitor_name: str
    ) -> list[TitleAcquisitionRow]: ...

    @abstractmethod
    async def sync_from_real_catalog(self) -> int:
        """실제 WWE 타이틀 획득 카탈로그로 NeonDB를 재생성. 기록 건수 반환."""
        ...

    @abstractmethod
    async def get_board(self) -> ChampionshipBoardResponse: ...
