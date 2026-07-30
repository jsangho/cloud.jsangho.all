"""PLE 예측 획득액(score) 집계 — 순위표·상점 지갑이 같은 정의를 공유한다.

`_docs/shop-point-ledger.md` §4 — "파생_획득액은 순위표가 쓰는 것과 같은
집계여야 한다"는 제약을 지키기 위해, 원래 `PleMatchPickPgRepository`
안에만 있던 집계 쿼리를 이 모듈로 옮겨 상점 저장소도 그대로 재사용한다.
"""

from __future__ import annotations

from core.entities.user_model import UserModel
from sqlalchemy import case, func, select

from kayfabe.adapter.outbound.orm.ple_orm import (
    PleMatchModel,
    PleMatchStatus,
    PlePredictionModel,
)


def earned_points_subquery(*, user_id: int | None = None):
    """사용자별 획득액(적중 배점 합계)·적중수·채점수 집계 서브쿼리.

    `user_id`를 주면 해당 사용자만(상점 지갑용), 생략하면 전체 사용자
    (순위표용)를 집계한다. `HAVING graded > 0`이 있어 채점된 예측이 하나도
    없는 사용자는 결과 행 자체가 없다 — 호출부에서 0으로 처리해야 한다
    (`list_ranked`가 이미 `score=int(score or 0)`으로 하듯).
    """
    finished = (PleMatchModel.winner_pick.isnot(None)) & (
        PleMatchModel.status == PleMatchStatus.FINISHED
    )
    correct_pick = PlePredictionModel.pick == PleMatchModel.winner_pick

    score_expr = func.coalesce(
        func.sum(case((finished & correct_pick, PleMatchModel.point_value), else_=0)),
        0,
    )
    graded_expr = func.coalesce(func.sum(case((finished, 1), else_=0)), 0)
    correct_expr = func.coalesce(
        func.sum(case((finished & correct_pick, 1), else_=0)), 0
    )

    stmt = (
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
    )
    if user_id is not None:
        stmt = stmt.where(UserModel.id == user_id)

    return (
        stmt.group_by(UserModel.id, UserModel.nickname)
        .having(graded_expr > 0)
        .subquery()
    )
