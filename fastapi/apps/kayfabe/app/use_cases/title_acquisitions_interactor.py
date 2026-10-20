"""타이틀 획득 이력·현역 챔피언십 유스케이스."""

from __future__ import annotations

import logging
from datetime import date

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
from kayfabe.domain.services.title_event_date import parse_won_at

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
            acquisitions=_as_timeline(rows),
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


def _as_timeline(rows) -> list[TitleAcquisitionResponse]:
    """획득 행들을 **연대순(오래된 것 먼저)** 으로 세운다.

    `won_at` 에 날짜가 묻혀 있어 파서를 거쳐야 순서를 안다
    (`domain/services/title_event_date` 가 왜인지 적고 있다 — `won_at_slug` 는
    388행 전부 `NULL` 이라 조인으로는 날짜가 안 나온다).

    **날짜를 못 읽은 행은 맨 뒤로 보낸다.** 추측해서 끼워 넣으면 연대표가 거짓
    순서를 말한다. 화면은 그 행을 "날짜 미상" 으로 적으면 된다.
    """
    parsed = [(row, parse_won_at(row.won_at)) for row in rows]
    parsed.sort(key=lambda pair: (pair[1].won_on is None, pair[1].won_on or date.min))
    return [
        TitleAcquisitionResponse(
            belt_name=row.belt_name,
            won_at=row.won_at,
            won_at_slug=row.won_at_slug,
            match_key=row.match_key,
            event_label=info.event_label,
            won_on=info.won_on,
        )
        for row, info in parsed
    ]
