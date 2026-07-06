"""타이틀 획득 이력·챔피언십 Postgres 어댑터."""

from __future__ import annotations

import asyncio
import json

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from kayfabe.adapter.outbound.orm.championship_orm import ChampionshipTitleModel
from kayfabe.adapter.outbound.orm.title_history_orm import TitleAcquisitionModel
from kayfabe.app.dtos.ple_events_dto import MyselfQuery, MyselfResponse
from kayfabe.app.dtos.title_acquisitions_dto import (
    BrandRosterResponse,
    ChampionshipBoardResponse,
    TitleReignResponse,
)
from kayfabe.app.ports.output.title_acquisitions_repository import (
    TitleAcquisitionRow,
    TitleAcquisitionsRepository,
)
from kayfabe.app.services.competitor_roster import is_team_roster_name
from kayfabe.app.services.current_championship_catalog import (
    CHAMPIONSHIP_AS_OF,
    WWE_BRAND_CHAMPIONS,
)
from kayfabe.app.services.real_title_catalog import (
    CATALOG_REVISION,
    individual_title_acquisitions,
)

_sync_lock = asyncio.Lock()

_BRAND_ORDER = [b["id"] for b in WWE_BRAND_CHAMPIONS]
_BRAND_META = {b["id"]: b for b in WWE_BRAND_CHAMPIONS}


class TitleAcquisitionsPgRepository(TitleAcquisitionsRepository):
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def count(self) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(TitleAcquisitionModel)
        )
        return int(result.scalar_one())

    async def needs_real_resync(self) -> bool:
        if await self.count() == 0:
            return True
        result = await self.db.execute(
            select(TitleAcquisitionModel.id)
            .where(TitleAcquisitionModel.source != "real")
            .limit(1)
        )
        if result.scalar_one_or_none() is not None:
            return True
        revision = await self.db.execute(
            select(TitleAcquisitionModel.id)
            .where(TitleAcquisitionModel.source == f"real:{CATALOG_REVISION}")
            .limit(1)
        )
        if revision.scalar_one_or_none() is None:
            return True
        team_row = await self.db.execute(
            select(TitleAcquisitionModel.competitor_name).limit(500)
        )
        for (name,) in team_row.all():
            if is_team_roster_name(name):
                return True
        return False

    async def list_by_competitor(
        self, *, competitor_name: str
    ) -> list[TitleAcquisitionRow]:
        result = await self.db.execute(
            select(TitleAcquisitionModel)
            .where(TitleAcquisitionModel.competitor_name == competitor_name)
            .order_by(TitleAcquisitionModel.id.asc())
        )
        return [
            TitleAcquisitionRow(
                belt_name=row.belt_name,
                won_at=row.won_at,
                won_at_slug=row.won_at_slug,
                match_key=row.match_key,
            )
            for row in result.scalars().all()
        ]

    async def sync_from_real_catalog(self) -> int:
        async with _sync_lock:
            await self.db.execute(delete(TitleAcquisitionModel))
            await self.db.flush()

            inserted = 0
            seen: set[tuple[str, str, str]] = set()
            source = f"real:{CATALOG_REVISION}"
            for competitor, reigns in individual_title_acquisitions().items():
                for belt_name, won_at in reigns:
                    key = (competitor, belt_name, won_at)
                    if key in seen:
                        continue
                    seen.add(key)
                    self.db.add(
                        TitleAcquisitionModel(
                            competitor_name=competitor,
                            belt_name=belt_name,
                            won_at=won_at,
                            won_at_slug=None,
                            match_key=None,
                            match_id=None,
                            source=source,
                        )
                    )
                    inserted += 1
            await self.db.flush()
            return inserted

    async def get_board(self) -> ChampionshipBoardResponse:
        result = await self.db.execute(
            select(ChampionshipTitleModel).order_by(
                ChampionshipTitleModel.brand_id,
                ChampionshipTitleModel.id,
            )
        )
        rows = list(result.scalars().all())
        if not rows:
            await self.sync_from_catalog()
            result = await self.db.execute(
                select(ChampionshipTitleModel).order_by(
                    ChampionshipTitleModel.brand_id,
                    ChampionshipTitleModel.id,
                )
            )
            rows = list(result.scalars().all())

        brands_map: dict[str, list[ChampionshipTitleModel]] = {}
        for row in rows:
            brands_map.setdefault(row.brand_id, []).append(row)

        brands = [
            BrandRosterResponse(
                id=brand_id,
                label=_BRAND_META.get(brand_id, {}).get("label", brand_id),
                tagline=_BRAND_META.get(brand_id, {}).get("tagline", ""),
                accent=_BRAND_META.get(brand_id, {}).get("accent", "red"),
                titles=[
                    TitleReignResponse(
                        belt_name=t.belt_name,
                        champions=json.loads(t.champions_json),
                        team_name=t.team_name,
                        won_at=t.won_at,
                        won_event=t.won_event,
                        tier=t.tier,
                    )
                    for t in titles
                ],
            )
            for brand_id, titles in brands_map.items()
        ]
        brands.sort(
            key=lambda b: (
                _BRAND_ORDER.index(b.id) if b.id in _BRAND_ORDER else len(_BRAND_ORDER)
            )
        )

        as_of = rows[0].as_of if rows else CHAMPIONSHIP_AS_OF
        return ChampionshipBoardResponse(as_of=as_of, brands=brands)

    async def sync_from_catalog(self) -> int:
        await self.db.execute(delete(ChampionshipTitleModel))
        await self.db.flush()

        inserted = 0
        for brand in WWE_BRAND_CHAMPIONS:
            for title in brand["titles"]:
                self.db.add(
                    ChampionshipTitleModel(
                        brand_id=brand["id"],
                        belt_name=title["belt_name"],
                        champions_json=json.dumps(
                            list(title["champions"]), ensure_ascii=False
                        ),
                        team_name=title.get("team_name"),
                        won_at=title["won_at"],
                        won_event=title.get("won_event"),
                        tier=title["tier"],
                        as_of=CHAMPIONSHIP_AS_OF,
                    )
                )
                inserted += 1
        await self.db.flush()
        return inserted

    async def introduce_myself(self, query: MyselfQuery) -> MyselfResponse:
        return MyselfResponse(
            id=query.id * 10000,
            name=query.name + "이 레포지토리에 다녀옴",
        )
