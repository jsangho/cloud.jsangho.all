"""데이터 센터 Postgres 어댑터 — 읽기 전용 (Phase 2).

**세지 않는다. 읽어만 준다.** 집계는 `app/services/data_center_stats.py`가 한다.

쿼리는 넷뿐이다: `wrestlers` 전체 · `ple_matches` ⨝ `ple_events` 전체 ·
`title_acquisitions` 전체 · 카운트 둘. 지금 규모(178 · 68 · 367)에서 이게 가장 단순하고,
선수별 전적이 어차피 전체 경기를 봐야 나오므로 부분 조회로 얻을 것도 없다.
"""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from kayfabe.adapter.outbound.orm.championship_orm import ChampionshipTitleModel
from kayfabe.adapter.outbound.orm.ple_orm import PleEventModel, PleMatchModel
from kayfabe.adapter.outbound.orm.title_history_orm import TitleAcquisitionModel
from kayfabe.adapter.outbound.orm.wrestler_orm import WrestlerOrm
from kayfabe.app.ports.output.data_center_repository import DataCenterRepository
from kayfabe.app.services.data_center_stats import MatchRow, TitleRow, WrestlerRow

logger = logging.getLogger("uvicorn.error")

FINISHED = "finished"


class DataCenterPgRepository(DataCenterRepository):
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_wrestlers(self) -> list[WrestlerRow]:
        result = await self.db.execute(
            select(
                WrestlerOrm.name,
                WrestlerOrm.brand,
                WrestlerOrm.real_name,
                WrestlerOrm.birth_date,
                WrestlerOrm.finisher,
                WrestlerOrm.stable_team,
            ).order_by(WrestlerOrm.name)
        )
        rows = [
            WrestlerRow(
                name=row.name,
                brand=row.brand,
                real_name=row.real_name,
                birth_date=row.birth_date,
                finisher=row.finisher,
                stable_team=row.stable_team,
            )
            for row in result.all()
        ]
        logger.info("[DataCenterPgRepository] list_wrestlers <- count=%d", len(rows))
        return rows

    async def list_matches(self) -> list[MatchRow]:
        result = await self.db.execute(
            select(
                PleEventModel.slug,
                PleEventModel.label,
                PleEventModel.month,
                PleEventModel.year,
                PleEventModel.status.label("event_status"),
                PleMatchModel.match_key,
                PleMatchModel.title,
                PleMatchModel.format,
                PleMatchModel.card_json,
                PleMatchModel.winner_pick,
                PleMatchModel.winner_name,
                PleMatchModel.status,
            )
            .join(PleMatchModel, PleMatchModel.event_id == PleEventModel.id)
            .order_by(PleEventModel.year, PleEventModel.month, PleMatchModel.sort_order)
        )
        rows = [
            MatchRow(
                event_slug=row.slug,
                event_label=row.label,
                month=row.month,
                year=row.year,
                event_status=row.event_status,
                match_key=row.match_key,
                title=row.title,
                format=row.format,
                card_json=row.card_json,
                winner_pick=row.winner_pick,
                winner_name=row.winner_name,
                status=row.status,
            )
            for row in result.all()
        ]
        logger.info("[DataCenterPgRepository] list_matches <- count=%d", len(rows))
        return rows

    async def list_title_acquisitions(self) -> list[TitleRow]:
        result = await self.db.execute(
            select(
                TitleAcquisitionModel.competitor_name,
                TitleAcquisitionModel.belt_name,
                TitleAcquisitionModel.won_at,
            ).order_by(TitleAcquisitionModel.competitor_name)
        )
        rows = [
            TitleRow(
                competitor_name=row.competitor_name,
                belt_name=row.belt_name,
                won_at=row.won_at,
            )
            for row in result.all()
        ]
        logger.info(
            "[DataCenterPgRepository] list_title_acquisitions <- count=%d", len(rows)
        )
        return rows

    async def count_events(self) -> tuple[int, int]:
        total = await self.db.execute(select(func.count()).select_from(PleEventModel))
        finished = await self.db.execute(
            select(func.count())
            .select_from(PleEventModel)
            .where(PleEventModel.status == FINISHED)
        )
        return int(total.scalar_one()), int(finished.scalar_one())

    async def count_championship_belts(self) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(ChampionshipTitleModel)
        )
        return int(result.scalar_one())
