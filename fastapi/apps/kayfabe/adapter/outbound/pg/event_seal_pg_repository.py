"""대회 `finished_at` 봉인 어댑터.

`PleEventsPgRepository`를 안에 들이지 않고 **세션으로 직접 묻는다.** 그쪽을 쥐면
`upsert_event_from_sync`가 이 객체에 딸려 오고, 포트를 좁게 낸 뜻이 사라진다
(`PendingResultPgRepository`가 같은 이유로 자기 쿼리를 쓴다).

`mark_event_finished`를 재사용하지 않는 이유는 포트 독스트링에 적었다 — 그것은
`status`와 경기 행까지 뒤집는데, 봉인 대상은 이미 `finished`인 대회라 그 쓰기가
전부 불필요하다.
"""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from kayfabe.adapter.outbound.orm.ple_orm import PleEventModel, PleMatchModel
from kayfabe.app.ports.output.event_seal_repository import EventSealRepository
from kayfabe.domain.services.event_seal import EventSealState

logger = logging.getLogger("uvicorn.error")


class EventSealPgRepository(EventSealRepository):
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def read_seal_state(self, *, event_slug: str) -> EventSealState | None:
        event = (
            await self.db.execute(
                select(PleEventModel.id, PleEventModel.finished_at).where(
                    PleEventModel.slug == event_slug
                )
            )
        ).first()
        if event is None:
            return None

        counted = (
            await self.db.execute(
                select(
                    func.count(PleMatchModel.id),
                    func.count(PleMatchModel.winner_pick),
                    func.max(PleMatchModel.finished_at),
                ).where(PleMatchModel.event_id == event.id)
            )
        ).one()

        return EventSealState(
            slug=event_slug,
            match_count=counted[0] or 0,
            result_count=counted[1] or 0,
            latest_match_finished_at=counted[2],
            event_finished_at=event.finished_at,
        )

    async def seal_event_finished_at(
        self, *, event_slug: str, finished_at: datetime
    ) -> bool:
        """**`finished_at IS NULL`을 `WHERE`에 넣어 덮어쓰기를 SQL로 막는다.**

        판정도 같은 것을 보지만(`seal_decision`), 읽고 쓰는 사이에 다른 경로가
        값을 넣었다면 이 조건이 마지막 그물이다.
        """
        result = await self.db.execute(
            update(PleEventModel)
            .where(
                PleEventModel.slug == event_slug,
                PleEventModel.finished_at.is_(None),
            )
            .values(finished_at=finished_at)
        )
        await self.db.flush()
        sealed = (result.rowcount or 0) == 1
        if sealed:
            logger.info(
                "[kayfabe.result_agent] 대회 봉인 | event=%s | finished_at=%s",
                event_slug,
                finished_at.isoformat(),
            )
        return sealed
