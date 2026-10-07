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

    @abstractmethod
    async def record_board_reigns(self) -> list[tuple[str, str, str]]:
        """보드의 현 재위 중 이력에 없는 것을 기록. (선수, 벨트, 표기) 목록 반환.

        **커밋하지 않는다** — 드라이런을 지원하려면 부른 쪽이 정해야 한다.
        """
        ...
