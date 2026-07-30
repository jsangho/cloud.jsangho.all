"""PLE 예측 순위 Postgres 어댑터."""

from __future__ import annotations

from core.matrix.grid_oracle_database_manager import LAYER_LOG
from sqlalchemy import Float, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from kayfabe.adapter.outbound.pg.point_aggregation import earned_points_subquery
from kayfabe.app.dtos.ple_events_dto import MyselfQuery, MyselfResponse
from kayfabe.app.dtos.ple_match_pick_dto import LeaderboardQuery
from kayfabe.app.ports.output.ple_match_pick_repository import PleMatchPickRepository

logger = LAYER_LOG


class PleMatchPickPgRepository(PleMatchPickRepository):
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def _aggregated_subquery():
        return earned_points_subquery()

    @staticmethod
    def _rank_order(agg):
        """순위 정렬 기준 — 적중률 내림차순.

        적중률은 인터랙터의 `correct / graded`와 같은 정의다. `_aggregated_subquery`가
        `HAVING graded > 0`으로 걸러 주므로 0으로 나눌 일은 없다.
        동률은 배점 합계 → 적중 수 → 닉네임 순으로 갈라 순서를 결정적으로 만든다.
        """
        accuracy_expr = cast(agg.c.correct, Float) / agg.c.graded
        return (
            accuracy_expr.desc(),
            agg.c.score.desc(),
            agg.c.correct.desc(),
            agg.c.nickname.asc(),
        )

    async def list_ranked(self, limit: int) -> list[LeaderboardQuery]:
        agg = self._aggregated_subquery()
        rank_col = func.rank().over(order_by=self._rank_order(agg)).label("rank")

        stmt = (
            select(
                rank_col,
                agg.c.nickname,
                agg.c.score,
                agg.c.correct,
                agg.c.graded,
            )
            .select_from(agg)
            .order_by(rank_col)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        rows = [
            LeaderboardQuery(
                rank=int(rank),
                nickname=str(nickname),
                score=int(score or 0),
                correct=int(correct or 0),
                graded=int(graded or 0),
            )
            for rank, nickname, score, correct, graded in result.all()
        ]
        logger.info(
            "[PleMatchPickPgRepository] list_ranked <- Neon count=%d", len(rows)
        )
        return rows

    async def get_ranked_by_nickname(self, nickname: str) -> LeaderboardQuery | None:
        agg = self._aggregated_subquery()
        # 윈도우 함수는 같은 SELECT의 WHERE보다 나중에 평가된다. 닉네임 필터를
        # rank()와 같은 SELECT에 두면 필터로 남은 한 행만 보고 순위를 매겨 항상
        # 1위가 나온다. 그래서 전체 집합에 순위를 매긴 서브쿼리를 만든 뒤 바깥에서 거른다.
        ranked = (
            select(
                func.rank().over(order_by=self._rank_order(agg)).label("rank"),
                agg.c.nickname,
                agg.c.score,
                agg.c.correct,
                agg.c.graded,
            )
            .select_from(agg)
            .subquery()
        )

        stmt = select(
            ranked.c.rank,
            ranked.c.nickname,
            ranked.c.score,
            ranked.c.correct,
            ranked.c.graded,
        ).where(ranked.c.nickname == nickname)

        result = await self.db.execute(stmt)
        row = result.first()
        if row is None:
            return None
        rank, nick, score, correct, graded = row
        return LeaderboardQuery(
            rank=int(rank),
            nickname=str(nick),
            score=int(score or 0),
            correct=int(correct or 0),
            graded=int(graded or 0),
        )

    async def introduce_myself(self, query: MyselfQuery) -> MyselfResponse:
        return MyselfResponse(
            id=query.id * 10000,
            name=query.name + "이 레포지토리에 다녀옴",
        )
