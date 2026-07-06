"""PLE 경기 기록 Postgres 어댑터."""

from __future__ import annotations

import time

from core.matrix.grid_oracle_database_manager import LAYER_LOG
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kayfabe.adapter.outbound.orm.ple_orm import PleEventModel, PleMatchModel
from kayfabe.app.dtos.ple_events_dto import (
    MatchSnapshotQuery,
    MyselfQuery,
    MyselfResponse,
)
from kayfabe.app.ports.output.ple_matches_repository import PleMatchesRepository
from kayfabe.app.services.records_scoring import names_from_card_json, normalize_name

logger = LAYER_LOG

_CACHE_TTL_S = 20.0
_names_cache: tuple[float, list[str]] | None = None
_snapshots_cache: tuple[float, list[MatchSnapshotQuery]] | None = None


class PleMatchesPgRepository(PleMatchesRepository):
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_competitor_names(self) -> list[str]:
        global _names_cache
        now = time.monotonic()
        if _names_cache and (now - _names_cache[0]) < _CACHE_TTL_S:
            return _names_cache[1]

        logger.info("[PleMatchesPgRepository] list_competitor_names -> Neon")
        result = await self.db.execute(select(PleMatchModel.card_json))
        names: set[str] = set()
        for (card_json,) in result.all():
            if not card_json:
                continue
            for name in names_from_card_json(card_json):
                names.add(normalize_name(name))
        rows = sorted(names)
        logger.info(
            "[PleMatchesPgRepository] list_competitor_names <- Neon count=%d", len(rows)
        )
        _names_cache = (now, rows)
        return rows

    async def list_match_snapshots(self) -> list[MatchSnapshotQuery]:
        global _snapshots_cache
        now = time.monotonic()
        if _snapshots_cache and (now - _snapshots_cache[0]) < _CACHE_TTL_S:
            return _snapshots_cache[1]

        logger.info("[PleMatchesPgRepository] list_match_snapshots -> Neon")
        stmt = (
            select(PleEventModel, PleMatchModel)
            .join(PleMatchModel, PleMatchModel.event_id == PleEventModel.id)
            .order_by(PleEventModel.month.asc(), PleMatchModel.sort_order.asc())
        )
        result = await self.db.execute(stmt)
        rows = [
            MatchSnapshotQuery(
                event_slug=event.slug,
                event_label=event.label,
                match_key=match.match_key,
                title=match.title,
                format=match.format,
                card_json=match.card_json or "",
                winner_pick=match.winner_pick,
                winner_name=match.winner_name,
                status=match.status,
            )
            for event, match in result.all()
        ]
        logger.info(
            "[PleMatchesPgRepository] list_match_snapshots <- Neon count=%d", len(rows)
        )
        _snapshots_cache = (now, rows)
        return rows

    async def introduce_myself(self, query: MyselfQuery) -> MyselfResponse:
        return MyselfResponse(
            id=query.id * 10000,
            name=query.name + "이 레포지토리에 다녀옴",
        )
