"""타이틀 획득 이력·현역 챔피언십 유스케이스."""

from __future__ import annotations

import logging

from kayfabe.app.dtos.ple_events_dto import MyselfQuery, MyselfResponse
from kayfabe.app.dtos.title_acquisitions_dto import (
    ChampionshipBoardResponse,
    CompetitorTitleHistoryResponse,
    TitleAcquisitionResponse,
)
from kayfabe.app.ports.input.title_acquisitions_use_case import TitleAcquisitionsUseCase
from kayfabe.app.ports.output.title_acquisitions_repository import (
    TitleAcquisitionsRepository,
)
from kayfabe.app.services.records_scoring import normalize_name

logger = logging.getLogger("uvicorn.error")


class TitleAcquisitionsInteractor(TitleAcquisitionsUseCase):
    def __init__(
        self, *, title_Acquisitions_repository: TitleAcquisitionsRepository
    ) -> None:
        self._title_Acquisitions = title_Acquisitions_repository

    async def sync_from_real_catalog(self) -> int:
        return await self._title_Acquisitions.sync_from_real_catalog()

    async def _ensure_catalog_loaded(self) -> None:
        if await self._title_Acquisitions.needs_real_resync():
            await self.sync_from_real_catalog()

    async def get_competitor_title_history(
        self, name: str
    ) -> CompetitorTitleHistoryResponse:
        normalized = normalize_name(name)
        await self._ensure_catalog_loaded()
        rows = await self._title_Acquisitions.list_by_competitor(
            competitor_name=normalized
        )
        return CompetitorTitleHistoryResponse(
            name=normalized,
            acquisitions=[
                TitleAcquisitionResponse(
                    belt_name=row.belt_name,
                    won_at=row.won_at,
                    won_at_slug=row.won_at_slug,
                    match_key=row.match_key,
                )
                for row in rows
            ],
        )

    async def get_board(self) -> ChampionshipBoardResponse:
        logger.info("[ChampionshipInteractor] get_board -> Repository")
        board = await self._title_Acquisitions.get_board()
        logger.info(
            "[ChampionshipInteractor] get_board <- Repository brands=%d as_of=%s",
            len(board.brands),
            board.as_of,
        )
        return board

    async def introduce_myself(self, query: MyselfQuery) -> MyselfResponse:
        return MyselfResponse(
            id=query.id * 10000,
            name=query.name + " 타이틀 레포지토리에 다녀옴",
        )
