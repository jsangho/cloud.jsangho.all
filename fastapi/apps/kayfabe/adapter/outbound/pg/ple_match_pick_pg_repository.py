"""PLE 예측 순위 Postgres 어댑터."""

from __future__ import annotations

from core.matrix.grid_oracle_database_manager import LAYER_LOG
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from kayfabe.adapter.outbound.orm.ple_orm import (
    PleMatchModel,
    PleMatchStatus,
    PlePredictionModel,
)
from kayfabe.app.dtos.ple_events_dto import MyselfQuery, MyselfResponse
from kayfabe.app.dtos.ple_match_pick_dto import LeaderboardQuery
from kayfabe.app.ports.output.ple_match_pick_repository import PleMatchPickRepository
from superstar.domain.entities.user_model import UserModel

logger = LAYER_LOG


class PleMatchPickPgRepository(PleMatchPickRepository):
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def _aggregated_subquery():
        finished = (PleMatchModel.winner_pick.isnot(None)) & (
            PleMatchModel.status == PleMatchStatus.FINISHED
        )
        correct_pick = PlePredictionModel.pick == PleMatchModel.winner_pick

        score_expr = func.coalesce(
            func.sum(
                case(
                    (finished & correct_pick, PleMatchModel.point_value),
                    else_=0,
                )
            ),
            0,
        )
        graded_expr = func.coalesce(func.sum(case((finished, 1), else_=0)), 0)
        correct_expr = func.coalesce(
            func.sum(case((finished & correct_pick, 1), else_=0)), 0
        )

        return (
            select(
                UserModel.id.label("user_id"),
                UserModel.nickname.label("nickname"),
                score_expr.label("score"),
                correct_expr.label("correct"),
                graded_expr.label("graded"),
            )
            .select_from(PlePredictionModel)
            .join(PleMatchModel, PlePredictionModel.match_id == PleMatchModel.id)
            .join(UserModel, PlePredictionModel.user_id == UserModel.id)
            .where(PlePredictionModel.user_id.isnot(None))
            .group_by(UserModel.id, UserModel.nickname)
            .having(graded_expr > 0)
            .subquery()
        )

    async def list_ranked(self, limit: int) -> list[LeaderboardQuery]:
        agg = self._aggregated_subquery()
        rank_col = (
            func.rank()
            .over(
                order_by=(
                    agg.c.score.desc(),
                    agg.c.correct.desc(),
                    agg.c.nickname.asc(),
                )
            )
            .label("rank")
        )

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
        rank_col = (
            func.rank()
            .over(
                order_by=(
                    agg.c.score.desc(),
                    agg.c.correct.desc(),
                    agg.c.nickname.asc(),
                )
            )
            .label("rank")
        )

        stmt = (
            select(
                rank_col,
                agg.c.nickname,
                agg.c.score,
                agg.c.correct,
                agg.c.graded,
            )
            .select_from(agg)
            .where(agg.c.nickname == nickname)
        )

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
