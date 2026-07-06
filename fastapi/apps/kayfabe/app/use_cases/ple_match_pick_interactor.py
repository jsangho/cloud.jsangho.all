"""PLE 예측 순위 유스케이스."""

from __future__ import annotations

import logging

from kayfabe.app.dtos.ple_events_dto import MyselfQuery, MyselfResponse
from kayfabe.app.dtos.ple_match_pick_dto import (
    LeaderboardQuery,
    RankingRowResponse,
    RankingsResponse,
)
from kayfabe.app.ports.input.ple_match_pick_use_case import PleMatchPickUseCase
from kayfabe.app.ports.output.ple_events_repository import PleEventsRepository
from kayfabe.app.ports.output.ple_match_pick_repository import PleMatchPickRepository

logger = logging.getLogger("uvicorn.error")


class PleMatchPickInteractor(PleMatchPickUseCase):
    def __init__(
        self,
        *,
        repository: PleMatchPickRepository,
        ple_repository: PleEventsRepository,
    ) -> None:
        self._ranking_repository = repository
        self._ple_repository = ple_repository

    @staticmethod
    def _to_row_dto(row: LeaderboardQuery) -> RankingRowResponse:
        graded = row.graded
        accuracy = (row.correct / graded) if graded > 0 else 0.0
        return RankingRowResponse(
            rank=row.rank,
            nickname=row.nickname,
            score=row.score,
            accuracy=round(accuracy, 4),
        )

    async def list_rankings(
        self,
        *,
        limit: int = 120,
        nickname: str | None = None,
    ) -> RankingsResponse:
        logger.info(
            "[PleMatchPickInteractor] list_rankings | limit=%d nickname=%s",
            limit,
            nickname or "-",
        )
        capped = min(max(limit, 1), 500)
        await self._ple_repository.refresh_all_match_point_values()
        raw_rows = await self._ranking_repository.list_ranked(capped)
        rows = [self._to_row_dto(r) for r in raw_rows]

        my_rank: RankingRowResponse | None = None
        if nickname:
            my_rank = next((r for r in rows if r.nickname == nickname), None)
            if my_rank is None:
                mine = await self._ranking_repository.get_ranked_by_nickname(nickname)
                if mine is not None:
                    my_rank = self._to_row_dto(mine)

        logger.info("[PleMatchPickInteractor] list_rankings | rows=%d", len(rows))
        return RankingsResponse(rows=rows, my_rank=my_rank)

    async def introduce_myself(self, query: MyselfQuery) -> MyselfResponse:
        return await self._ranking_repository.introduce_myself(query)
