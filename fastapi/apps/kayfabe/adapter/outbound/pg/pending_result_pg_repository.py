"""결과가 없는 경기를 읽는 어댑터.

**선택지는 `options_from_card`로 읽는다.** 카드 JSON을 읽는 규칙이 두 벌로 갈리면,
에이전트가 대조하는 선택지와 예측·재현이 보는 선택지가 달라진다. 그 함수가 공개인
이유가 이것이고(`agent_prediction_pg_repository`의 독스트링), 여기서도 같은 함수를 쓴다.
"""

from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kayfabe.adapter.outbound.orm.ple_orm import (
    PleEventModel,
    PleEventStatus,
    PleMatchModel,
)
from kayfabe.adapter.outbound.pg.agent_prediction_pg_repository import (
    options_from_card,
)
from kayfabe.app.ports.output.pending_result_repository import PendingResultRepository
from kayfabe.domain.entities.result_verification import (
    MatchUnderReview,
    ReviewOption,
)

logger = logging.getLogger("uvicorn.error")


class PendingResultPgRepository(PendingResultRepository):
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_pending(
        self, *, event_slug: str | None = None, limit: int | None = None
    ) -> tuple[MatchUnderReview, ...]:
        statement = (
            select(
                PleEventModel.slug,
                PleEventModel.label,
                PleMatchModel.match_key,
                PleMatchModel.title,
                PleMatchModel.format,
                PleMatchModel.card_json,
            )
            .join(PleMatchModel, PleMatchModel.event_id == PleEventModel.id)
            # **끝난 대회만 본다.** 열리지도 않은 경기의 승자를 찾는 일은 없다.
            .where(PleEventModel.status == PleEventStatus.FINISHED)
            .where(PleMatchModel.winner_pick.is_(None))
            # 날짜가 빈 대회(`bad-blood` 등)가 뒤로 가도록 slug를 함께 정렬 열에 둔다.
            .order_by(
                PleEventModel.start_date,
                PleEventModel.slug,
                PleMatchModel.match_key,
            )
        )
        if event_slug:
            statement = statement.where(PleEventModel.slug == event_slug)

        rows = (await self.db.execute(statement)).all()

        found: list[MatchUnderReview] = []
        for row in rows:
            options = _options(row.card_json, row.match_key)
            if not options:
                # 선택지를 못 읽으면 대조할 것이 없어 어차피 보류가 된다. 모델을
                # 부르기 전에 걸러 비용을 아낀다.
                continue
            found.append(
                MatchUnderReview(
                    event_slug=row.slug,
                    event_label=row.label,
                    match_key=row.match_key,
                    title=row.title or row.match_key,
                    options=options,
                )
            )
            if limit is not None and len(found) >= limit:
                break

        return tuple(found)


def _options(card_json: str, match_key: str) -> tuple[ReviewOption, ...]:
    """카드 JSON → 도메인 선택지. 못 읽으면 빈 튜플."""
    try:
        card = json.loads(card_json)
    except (TypeError, ValueError):
        logger.warning(
            "[kayfabe.pending_result] 카드 JSON 판독 실패 | match=%s", match_key
        )
        return ()
    if not isinstance(card, dict):
        return ()

    return tuple(
        ReviewOption(pick=option.pick, name=option.name)
        for option in options_from_card(card)
    )
