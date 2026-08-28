"""PLE 이벤트 Postgres 어댑터 (조회·쓰기·myself)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from core.entities.user_model import UserModel
from core.matrix.grid_oracle_database_manager import LAYER_LOG
from sqlalchemy import case, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from kayfabe.adapter.outbound.catalog.ple_event_schedule_catalog import schedule_for
from kayfabe.adapter.outbound.mappers.ple_orm_mapper import (
    card_command_to_json,
    event_to_read,
    event_to_snapshot,
)
from kayfabe.adapter.outbound.orm.agent_prediction_orm import AgentPredictionModel
from kayfabe.adapter.outbound.orm.ple_orm import (
    PleEventModel,
    PleEventStatus,
    PleMatchModel,
    PleMatchStatus,
    PlePredictionModel,
)
from kayfabe.app.dtos.ple_events_dto import (
    MatchResultResponse,
    MyselfQuery,
    MyselfResponse,
    PleAiRecordResponse,
    PleAiStatsResponse,
    PleEventReadQuery,
    PleEventSnapshotQuery,
    PleEventSummaryResponse,
    PleEventSyncCommand,
)
from kayfabe.app.ports.output.ple_events_repository import PleEventsRepository
from kayfabe.app.services.ple_scoring import (
    competitor_count_from_card,
    derive_match_point_value,
)
from kayfabe.domain.entities.agent_prediction import PredictionSource

logger = LAYER_LOG

#: 적중률에서 빼는 예측. 에이전트가 아무도 답하지 못해 배당으로 대체한 것이다.
BOOKMAKER_FALLBACK_SOURCE = str(PredictionSource.BOOKMAKER_FALLBACK)


class PleEventsPgRepository(PleEventsRepository):
    """Neon(Postgres) PLE 조회 어댑터."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _load_event_model(
        self, slug: str, *, with_predictions: bool
    ) -> PleEventModel | None:
        stmt = select(PleEventModel).where(PleEventModel.slug == slug)
        if with_predictions:
            stmt = stmt.options(
                selectinload(PleEventModel.matches).selectinload(
                    PleMatchModel.predictions
                )
            )
        else:
            stmt = stmt.options(selectinload(PleEventModel.matches))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_events(self) -> list[PleEventReadQuery]:
        logger.info("[PleInfoPgRepository] list_events -> Neon")
        result = await self.db.execute(
            select(PleEventModel)
            .options(selectinload(PleEventModel.matches))
            .order_by(PleEventModel.month.asc().nulls_last())
        )
        rows = [event_to_read(e) for e in result.scalars().all()]
        logger.info("[PleInfoPgRepository] list_events <- Neon | count=%d", len(rows))
        return rows

    async def get_event_by_slug(self, slug: str) -> PleEventReadQuery | None:
        logger.info("[PleInfoPgRepository] get_event_by_slug -> Neon | slug=%s", slug)
        event = await self._load_event_model(slug, with_predictions=True)
        if event is None:
            return None
        return event_to_read(event)

    async def get_prediction_pick_by_user(
        self, match_id: int, user_id: int
    ) -> str | None:
        result = await self.db.execute(
            select(PlePredictionModel.pick).where(
                PlePredictionModel.match_id == match_id,
                PlePredictionModel.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_prediction_pick(self, match_id: int, client_id: str) -> str | None:
        result = await self.db.execute(
            select(PlePredictionModel.pick).where(
                PlePredictionModel.match_id == match_id,
                PlePredictionModel.client_id == client_id,
            )
        )
        return result.scalar_one_or_none()

    async def aggregate_votes_for_match(
        self, *, match_id: int, fmt: str, card_json: str
    ) -> dict[str, int | list[int]]:
        result = await self.db.execute(
            select(PlePredictionModel.pick).where(
                PlePredictionModel.match_id == match_id
            )
        )
        picks = list(result.scalars().all())

        if fmt == "multi":
            card = json.loads(card_json)
            count = len(card.get("competitors") or [])
            totals: list[int] = [0] * count
            for pick in picks:
                try:
                    idx = int(pick)
                    if 0 <= idx < count:
                        totals[idx] += 1
                except ValueError:
                    continue
            return {"left": 0, "right": 0, "multi": totals}

        left = sum(1 for p in picks if p == "left")
        right = sum(1 for p in picks if p == "right")
        return {"left": left, "right": right, "multi": []}

    async def get_ple_by_slug(self, slug: str) -> PleEventModel | None:
        result = await self.db.execute(
            select(PleEventModel).where(PleEventModel.slug == slug)
        )
        return result.scalar_one_or_none()

    async def list_events_by_year(self, year: int) -> list[PleEventSummaryResponse]:
        result = await self.db.execute(
            select(PleEventModel)
            .where(PleEventModel.year == year)
            .order_by(PleEventModel.month.asc().nulls_last())
        )
        return [
            PleEventSummaryResponse(
                slug=e.slug,
                label=e.label,
                month=e.month,
                year=e.year,
                status=e.status,
                match_count=0,
                finished_at=e.finished_at,
            )
            for e in result.scalars().all()
        ]

    async def get_ai_stats(self) -> PleAiStatsResponse:
        """적중률은 **에이전트가 만든 예측만** 센다.

        예전에는 `ple_matches.ai_pick`(카드 동기화 때 배당으로 파생한 값)을 셌다.
        그 기록과 멀티 에이전트 기록이 한 숫자로 섞이면 무엇의 적중률인지 말할 수
        없어, 집계 대상을 `ple_agent_predictions`로 옮겼다(하네스 §13-Q4 결정).

        **북메이커 폴백은 제외한다** — 에이전트가 아무도 답하지 못해 배당으로
        대체한 예측이라, 그것까지 세면 지우기로 한 그 숫자가 다시 섞인다.

        **사후 재현 표본도 제외한다** (Phase 3-9). 생성 시점에 결과가 시스템 밖에서
        이미 알려져 있었다고 선언된 예측이다(Phase 3-7). AI LAB의 자격 판정이
        "채점 대상 아님"이라 적은 그 표본을, 홈 화면이 적중률로 세고 있으면 안 된다.

        **이 함수가 내는 여섯 값은 전부 채점 지표다** — `total_graded`·`correct`·
        `incorrect`·`accuracy_percent`·`recent[]`·`recent[].correct`. 재고나 활동량을
        말하는 필드가 하나도 없어서, 여기서는 모집단을 통째로 좁혀도 잃는 의미가 없다.
        (`ai_lab_integrity`의 집계 넷은 재고와 채점이 한 목록을 공유해서 사정이 다르다 —
        거기서는 지표별로 갈라 걸어야 한다.)

        **`isnot(True)`여야 한다.** `== False`나 `is_(False)`로 쓰면 아무도 선언한 적
        없는 `NULL` 행이 통째로 채점에서 빠진다. `NULL`은 "모른다"가 아니라
        **"선언되지 않았다"**이고 그 표본은 채점 대상으로 남는다. SQL의 `IS NOT TRUE`가
        `ai_lab_integrity.is_scorable()`의 파이썬 `is not True`와 같은 뜻이 되는 유일한
        표현이다.

        **같은 뜻이 파이썬과 SQL 두 곳에 적혀 있다.** 이 쿼리는 행을 `PredictionRow`로
        조립하지 않고 SQL에서 바로 집계해서 `is_scorable()`을 부를 자리가 없다. 한쪽만
        바뀌면 홈 화면과 AI LAB이 서로 다른 적중률을 말하게 되므로, 둘 중 하나를 고칠
        때는 반드시 다른 하나도 함께 본다.
        """
        logger.info("[PleEventsPgRepository] get_ai_stats -> Neon")
        graded = (
            select(
                AgentPredictionModel.pick.label("pick"),
                AgentPredictionModel.pick_name.label("pick_name"),
                PleMatchModel.winner_pick.label("winner_pick"),
                PleMatchModel.winner_name.label("winner_name"),
                PleMatchModel.match_key.label("match_key"),
                PleMatchModel.title.label("title"),
                PleMatchModel.sort_order.label("sort_order"),
                PleMatchModel.id.label("match_id"),
                PleEventModel.slug.label("slug"),
                PleEventModel.label.label("label"),
                PleEventModel.year.label("year"),
                PleEventModel.month.label("month"),
            )
            .join(PleEventModel, AgentPredictionModel.event_id == PleEventModel.id)
            .join(
                PleMatchModel,
                (PleMatchModel.event_id == AgentPredictionModel.event_id)
                & (PleMatchModel.match_key == AgentPredictionModel.match_key),
            )
            .where(
                PleMatchModel.winner_pick.isnot(None),
                AgentPredictionModel.source != BOOKMAKER_FALLBACK_SOURCE,
                # `== False`가 아니다 — 위 docstring 참조. NULL은 채점 대상으로 남는다.
                AgentPredictionModel.outcome_known_externally.isnot(True),
            )
            .subquery()
        )

        agg = await self.db.execute(
            select(
                func.count(),
                func.coalesce(
                    func.sum(case((graded.c.pick == graded.c.winner_pick, 1), else_=0)),
                    0,
                ),
            ).select_from(graded)
        )
        total_graded, correct = agg.one()
        total_graded = int(total_graded or 0)
        correct = int(correct or 0)
        incorrect = max(0, total_graded - correct)
        accuracy = round(correct / total_graded * 100, 1) if total_graded > 0 else None

        recent_rows = await self.db.execute(
            select(graded).order_by(
                graded.c.year.asc(),
                graded.c.month.asc().nulls_last(),
                graded.c.slug.asc(),
                graded.c.sort_order.asc(),
                graded.c.match_id.asc(),
            )
        )
        recent = [
            PleAiRecordResponse(
                event_slug=row.slug,
                event_label=row.label,
                match_key=row.match_key,
                match_title=row.title,
                ai_pick_name=row.pick_name or "",
                winner_name=row.winner_name,
                correct=row.pick == row.winner_pick,
            )
            for row in recent_rows.all()
        ]

        stats = PleAiStatsResponse(
            total_graded=total_graded,
            correct=correct,
            incorrect=incorrect,
            accuracy_percent=accuracy,
            recent=recent,
        )
        logger.info(
            "[PleEventsPgRepository] get_ai_stats <- Neon | graded=%d", total_graded
        )
        return stats

    async def user_exists(self, *, user_id: int) -> bool:
        result = await self.db.execute(
            select(UserModel.id).where(UserModel.id == user_id)
        )
        return result.scalar_one_or_none() is not None

    async def flush(self) -> None:
        await self.db.flush()

    async def _get_event_orm(self, slug: str) -> PleEventModel | None:
        return await self._load_event_model(slug, with_predictions=False)

    async def upsert_event_from_sync(
        self, payload: PleEventSyncCommand
    ) -> PleEventSnapshotQuery:
        status_val = payload.status or PleEventStatus.UPCOMING
        # **날짜는 페이로드에서 받지 않는다** (Phase 3-12). 이 값이 평가의 시간
        # 게이트를 좌우하므로, 클라이언트가 보내는 값이 아니라 백엔드 카탈로그가
        # 정한다. 모르는 대회는 `None`이고 그대로 `NULL`로 남는다.
        start_date, end_date = schedule_for(payload.slug)
        await self.db.execute(
            pg_insert(PleEventModel)
            .values(
                slug=payload.slug,
                label=payload.label,
                month=payload.month,
                year=payload.year,
                status=status_val,
                start_date=start_date,
                end_date=end_date,
            )
            .on_conflict_do_update(
                index_elements=["slug"],
                set_={
                    "label": payload.label,
                    "month": payload.month,
                    "year": payload.year,
                    "start_date": start_date,
                    "end_date": end_date,
                },
            )
        )
        await self.db.flush()

        event = await self._get_event_orm(payload.slug)
        if event is None:
            raise RuntimeError(f"PLE event upsert failed: slug={payload.slug!r}")

        if payload.status:
            event.status = payload.status

        existing = {m.match_key: m for m in event.matches}
        seen_keys: set[str] = set()

        for order, card in enumerate(payload.matches):
            seen_keys.add(card.id)
            card_json = card_command_to_json(card)
            row = existing.get(card.id)
            if row is None:
                row = PleMatchModel(
                    event_id=event.id,
                    match_key=card.id,
                    title=card.title,
                    format=card.format,
                    card_variant=card.card_variant,
                    sort_order=order,
                    card_json=json.dumps(card_json, ensure_ascii=False),
                )
                self.db.add(row)
            else:
                row.title = card.title
                row.format = card.format
                row.card_variant = card.card_variant
                row.sort_order = order
                row.card_json = json.dumps(card_json, ensure_ascii=False)

            card_dict = json.loads(row.card_json)
            self._apply_point_value(row, card_dict)
            # 여기서 AI 예측을 파생하지 않는다. 예측은 에이전트가 만들고
            # `ple_agent_predictions`에만 남는다 — 페이지 진입이 예측을 만들던 경로다.
            if card.result:
                self._apply_result_to_row(row, card.result)

        for key, row in existing.items():
            if key not in seen_keys:
                await self.db.delete(row)

        await self.db.flush()
        refreshed = await self._get_event_orm(payload.slug)
        if refreshed is None:
            raise RuntimeError(f"PLE event upsert failed: slug={payload.slug!r}")
        return event_to_snapshot(refreshed)

    @staticmethod
    def _apply_point_value(row: PleMatchModel, card_dict: dict) -> None:
        count = competitor_count_from_card(card_dict, row.format)
        row.point_value = derive_match_point_value(
            row.title,
            row.format,
            match_key=row.match_key,
            competitor_count=count,
        )

    async def refresh_all_match_point_values(self) -> int:
        result = await self.db.execute(select(PleMatchModel))
        updated = 0
        for row in result.scalars().all():
            card_dict = json.loads(row.card_json)
            prev = row.point_value
            self._apply_point_value(row, card_dict)
            if row.point_value != prev:
                updated += 1
        await self.db.flush()
        return updated

    def _apply_result_to_row(
        self, row: PleMatchModel, result: MatchResultResponse
    ) -> None:
        if result.winner_side:
            row.winner_pick = result.winner_side
        elif result.winner_index is not None:
            row.winner_pick = str(result.winner_index)
        if result.winner_name:
            row.winner_name = result.winner_name
        if result.winner_side or result.winner_index is not None or result.winner_name:
            row.status = PleMatchStatus.FINISHED
            row.finished_at = datetime.now(UTC)

    async def set_match_result(
        self,
        slug: str,
        match_key: str,
        result: MatchResultResponse,
        status: str | None = None,
    ) -> bool:
        event = await self._get_event_orm(slug)
        if event is None:
            return False
        row = next((m for m in event.matches if m.match_key == match_key), None)
        if row is None:
            return False
        self._apply_result_to_row(row, result)
        if status:
            row.status = status
        await self.db.flush()
        return True

    async def mark_event_finished(self, *, event_id: int, finished_at) -> None:
        result = await self.db.execute(
            select(PleEventModel)
            .where(PleEventModel.id == event_id)
            .options(selectinload(PleEventModel.matches))
        )
        event = result.scalar_one_or_none()
        if event is None:
            return
        event.status = PleEventStatus.FINISHED
        event.finished_at = finished_at
        for match in event.matches:
            if match.status != PleMatchStatus.FINISHED and match.winner_pick:
                match.status = PleMatchStatus.FINISHED
                match.finished_at = finished_at
        await self.db.flush()

    async def attach_user_id_by_client(self, client_id: str, user_id: int) -> int:
        result = await self.db.execute(
            update(PlePredictionModel)
            .where(
                PlePredictionModel.client_id == client_id,
                PlePredictionModel.user_id.is_(None),
            )
            .values(user_id=user_id)
        )
        await self.db.flush()
        return result.rowcount if result.rowcount is not None else 0

    async def get_prediction_by_user(
        self, match_id: int, user_id: int
    ) -> PlePredictionModel | None:
        result = await self.db.execute(
            select(PlePredictionModel).where(
                PlePredictionModel.match_id == match_id,
                PlePredictionModel.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_prediction(
        self,
        match_id: int,
        client_id: str,
        pick: str,
        user_id: int,
    ) -> None:
        existing = await self.get_prediction_by_user(match_id, user_id)
        if existing is not None:
            existing.pick = pick
            existing.client_id = client_id
            await self.db.flush()
            return
        await self.add_prediction(match_id, client_id, pick, user_id)

    async def add_prediction(
        self,
        match_id: int,
        client_id: str,
        pick: str,
        user_id: int | None = None,
    ) -> PlePredictionModel:
        prediction = PlePredictionModel(
            match_id=match_id,
            client_id=client_id,
            user_id=user_id,
            pick=pick,
        )
        self.db.add(prediction)
        await self.db.flush()
        return prediction

    async def get_prediction(
        self, match_id: int, client_id: str
    ) -> PlePredictionModel | None:
        result = await self.db.execute(
            select(PlePredictionModel).where(
                PlePredictionModel.match_id == match_id,
                PlePredictionModel.client_id == client_id,
            )
        )
        return result.scalar_one_or_none()

    async def introduce_myself(self, query: MyselfQuery) -> MyselfResponse:
        return MyselfResponse(
            id=query.id * 10000,
            name=query.name + "이 레포지토리에 다녀옴",
        )
