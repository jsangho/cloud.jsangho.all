"""타이틀 획득 이력·챔피언십 Postgres 어댑터."""

from __future__ import annotations

import asyncio
import json
import logging

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from kayfabe.adapter.outbound.orm.championship_orm import ChampionshipTitleModel
from kayfabe.adapter.outbound.orm.ple_orm import PleEventModel, PleMatchModel
from kayfabe.adapter.outbound.orm.title_history_orm import TitleAcquisitionModel
from kayfabe.adapter.outbound.pg.agent_prediction_pg_repository import (
    options_from_card,
)
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
from kayfabe.app.services.title_match_classifier import is_championship_match
from kayfabe.domain.services.championship_succession import (
    FinishedTitleMatch,
    TitleReign,
    apply_results,
)

logger = logging.getLogger("uvicorn.error")

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

        # **여기서 자동 갱신이 일어난다.** 표에 든 값은 카탈로그 기준선이고, 그
        # 기준일 뒤에 끝난 타이틀 매치를 얹어 지금의 챔피언을 낸다. 사람이 카탈로그를
        # 고치지 않아도 대회 결과가 들어오는 즉시 보드가 따라온다.
        baseline = [
            TitleReign(
                belt_name=row.belt_name,
                champions=tuple(json.loads(row.champions_json)),
                team_name=row.team_name,
                won_at=row.won_at,
                won_event=row.won_event,
            )
            for row in rows
        ]
        baseline_as_of = rows[0].as_of if rows else CHAMPIONSHIP_AS_OF
        succession = apply_results(
            baseline,
            await self._finished_title_matches(after=baseline_as_of),
            baseline_as_of=baseline_as_of,
            is_title_match=is_championship_match,
        )
        _log_succession(succession, baseline_as_of)
        updated = {reign.belt_name: reign for reign in succession.reigns}

        brands_map: dict[str, list[ChampionshipTitleModel]] = {}
        for row in rows:
            brands_map.setdefault(row.brand_id, []).append(row)

        brands = [
            BrandRosterResponse(
                id=brand_id,
                label=_BRAND_META.get(brand_id, {}).get("label", brand_id),
                tagline=_BRAND_META.get(brand_id, {}).get("tagline", ""),
                accent=_BRAND_META.get(brand_id, {}).get("accent", "red"),
                titles=[_reign_response(t, updated.get(t.belt_name)) for t in titles],
            )
            for brand_id, titles in brands_map.items()
        ]
        brands.sort(
            key=lambda b: (
                _BRAND_ORDER.index(b.id) if b.id in _BRAND_ORDER else len(_BRAND_ORDER)
            )
        )

        return ChampionshipBoardResponse(as_of=succession.as_of, brands=brands)

    async def _finished_title_matches(self, *, after: str) -> list[FinishedTitleMatch]:
        """기준일 뒤에 끝난 경기. **제목을 가공하지 않고 원문 그대로 싣는다.**

        승자는 `winner_name`이 아니라 **`winner_pick`이 가리키는 카드 선택지**에서
        얻는다. `winner_name`이 비어 있는 행이 실제로 있다(WrestleMania 여성 태그전은
        `winner_pick='0'`인데 `winner_name`이 `NULL`이다). 카드 선택지는
        `options_from_card`가 읽으므로 예측·재현·확정이 전부 같은 규칙을 본다.
        """
        result = await self.db.execute(
            select(
                PleEventModel.label,
                PleEventModel.start_date,
                PleMatchModel.title,
                PleMatchModel.match_key,
                PleMatchModel.winner_pick,
                PleMatchModel.card_json,
            )
            .join(PleMatchModel, PleMatchModel.event_id == PleEventModel.id)
            .where(PleEventModel.status == FINISHED_STATUS)
            .where(PleMatchModel.winner_pick.isnot(None))
            .where(PleEventModel.start_date.isnot(None))
            .order_by(PleEventModel.start_date, PleMatchModel.match_key)
        )

        found: list[FinishedTitleMatch] = []
        for row in result.all():
            event_date = row.start_date.isoformat()
            if event_date <= after:
                continue
            winner = _winner_option(row.card_json, row.winner_pick, row.match_key)
            found.append(
                FinishedTitleMatch(
                    match_title=row.title or "",
                    match_key=row.match_key,
                    winner=winner,
                    event_label=row.label,
                    event_date=event_date,
                )
            )
        return found

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


#: 대회 상태 리터럴. `ple_events.status`가 문자열이라 여기서 한 번만 적는다.
FINISHED_STATUS = "finished"


def _winner_option(card_json: str, winner_pick: str, match_key: str) -> str:
    """`winner_pick`이 가리키는 카드 선택지 이름. 못 읽으면 빈 문자열.

    빈 문자열은 "승자를 모른다"로 다뤄져 그 경기가 보드에 반영되지 않는다 —
    추측으로 챔피언을 바꾸지 않는다.
    """
    try:
        card = json.loads(card_json)
    except (TypeError, ValueError):
        logger.warning("[championship] 카드 JSON 판독 실패 | match=%s", match_key)
        return ""
    if not isinstance(card, dict):
        return ""
    for option in options_from_card(card):
        if option.pick == winner_pick:
            return option.name
    return ""


def _reign_response(
    row: ChampionshipTitleModel, reign: TitleReign | None
) -> TitleReignResponse:
    """갱신된 재위가 있으면 그것을, 없으면 표의 값을 그대로 쓴다.

    `tier`는 표에서만 온다 — 경기 결과가 말해 주지 않는 값이고, 벨트의 성격은
    챔피언이 바뀌어도 그대로다.
    """
    if reign is None:
        return TitleReignResponse(
            belt_name=row.belt_name,
            champions=json.loads(row.champions_json),
            team_name=row.team_name,
            won_at=row.won_at,
            won_event=row.won_event,
            tier=row.tier,
        )
    return TitleReignResponse(
        belt_name=reign.belt_name,
        champions=list(reign.champions),
        team_name=reign.team_name,
        won_at=reign.won_at,
        won_event=reign.won_event,
        tier=row.tier,
    )


def _log_succession(succession, baseline_as_of: str) -> None:
    """무엇이 바뀌었고 무엇을 건너뛰었는지 남긴다.

    건너뛴 것을 조용히 삼키지 않는다 — 카탈로그에 없는 벨트가 생겼거나 경기 제목
    표기가 달라진 날, 로그가 유일한 신호다.
    """
    if succession.changes:
        logger.info(
            "[championship] 기준일 %s → %s | 변경 %d건",
            baseline_as_of,
            succession.as_of,
            len(succession.changes),
        )
    for change in succession.changes:
        logger.info(
            "[championship] %s | %s -> %s (%s %s)%s",
            change.belt_name,
            " & ".join(change.before) or "공석",
            " & ".join(change.after),
            change.at,
            change.event_label,
            " | 구성원 미상 — 카탈로그 보강 필요" if change.members_unknown else "",
        )
    for item in succession.skipped:
        logger.info("[championship] 건너뜀(%s) | %s", item.reason, item.match_title)
