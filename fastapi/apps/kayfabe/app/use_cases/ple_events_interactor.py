"""PLE 이벤트 유스케이스 (조회·쓰기·myself)."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from kayfabe.adapter.outbound.catalog.finished_event_results_catalog import (
    FINISHED_EVENT_RESULTS,
    FINISHED_EVENT_SLUGS,
)
from kayfabe.app.dtos.ple_events_dto import (
    BatchPredictionCommand,
    BatchResultsCommand,
    CompetitorResponse,
    MatchBoardResponse,
    MatchResultResponse,
    MatchResultUpdateCommand,
    MyselfQuery,
    MyselfResponse,
    PleAiStatsResponse,
    PleBoardResponse,
    PleEventSummaryResponse,
    PleEventSyncCommand,
    PleResultRowResponse,
    PleResultsResponse,
    PredictionCommand,
    VoteTotalsResponse,
)
from kayfabe.app.exceptions import PleAuthRequiredError
from kayfabe.app.ports.input.ple_events_use_case import PleEventsUseCase
from kayfabe.app.ports.output.ple_events_repository import PleEventsRepository
from kayfabe.domain.value_objects.ple_status_vo import PleEventStatus, PleMatchStatus

logger = logging.getLogger("uvicorn.error")


class PleEventsInteractor(PleEventsUseCase):
    def __init__(
        self,
        repository: PleEventsRepository,
        info_use_case: PleEventsUseCase | None = None,
    ) -> None:
        self._repo = repository
        self._info: PleEventsUseCase = info_use_case or self

    async def list_events(self) -> list[PleEventSummaryResponse]:
        logger.info("[PleEventsInteractor] list_events")
        events = await self._repo.list_events()
        return [
            PleEventSummaryResponse(
                slug=e.slug,
                label=e.label,
                month=e.month,
                year=e.year,
                status=e.status,
                match_count=len(e.matches),
            )
            for e in events
        ]

    async def get_ai_stats(self) -> PleAiStatsResponse:
        logger.info("[PleEventsInteractor] get_ai_stats")
        return await self._repo.get_ai_stats()

    async def get_board(
        self,
        *,
        slug: str,
        client_id: str | None = None,
        user_id: int | None = None,
    ) -> PleBoardResponse:
        logger.info(
            "[PleInfoInteractor] get_board | slug=%s clientId=%s userId=%s",
            slug,
            client_id or "-",
            user_id if user_id is not None else "-",
        )
        event = await self._repo.get_event_by_slug(slug)
        if event is None:
            raise LookupError(slug)

        matches_out: list[MatchBoardResponse] = []
        for row in event.matches:
            card = json.loads(row.card_json)
            vote_raw = await self._repo.aggregate_votes_for_match(
                match_id=row.id,
                fmt=row.format,
                card_json=row.card_json,
            )

            my_pick: str | None = None
            if user_id is not None:
                my_pick = await self._repo.get_prediction_pick_by_user(row.id, user_id)
            elif client_id:
                my_pick = await self._repo.get_prediction_pick(row.id, client_id)

            result = None
            if row.winner_pick or row.winner_name:
                if row.format == "multi":
                    try:
                        result = MatchResultResponse(
                            winner_index=int(row.winner_pick)
                            if row.winner_pick
                            else None,
                            winner_name=row.winner_name,
                        )
                    except ValueError:
                        result = MatchResultResponse(winner_name=row.winner_name)
                else:
                    result = MatchResultResponse(
                        winner_side=row.winner_pick
                        if row.winner_pick in ("left", "right")
                        else None,
                        winner_name=row.winner_name,
                    )

            def _competitor(raw: dict | None) -> CompetitorResponse | None:
                if not raw:
                    return None
                return CompetitorResponse(
                    name=raw.get("name", ""),
                    is_champion=raw.get("isChampion"),
                )

            matches_out.append(
                MatchBoardResponse(
                    id=row.match_key,
                    db_id=row.id,
                    title=row.title,
                    card_variant=row.card_variant,
                    format=row.format,
                    left=_competitor(card.get("left")),
                    right=_competitor(card.get("right")),
                    competitors=[_competitor(c) for c in card.get("competitors") or []]
                    or None,
                    bookmaker_decimal=card.get("bookmakerDecimal"),
                    status=row.status,
                    result=result,
                    site_votes=VoteTotalsResponse(
                        left=int(vote_raw.get("left", 0)),
                        right=int(vote_raw.get("right", 0)),
                        multi=list(vote_raw.get("multi") or []),
                    ),
                    locked=my_pick is not None,
                    my_pick=my_pick,
                    ai_pick=row.ai_pick,
                    ai_pick_name=row.ai_pick_name,
                    ai_correct=row.ai_correct,
                    point_value=row.point_value,
                )
            )

        return PleBoardResponse(
            slug=event.slug,
            label=event.label,
            month=event.month,
            year=event.year,
            status=event.status,
            finished_at=event.finished_at,
            matches=matches_out,
            updated_at=event.updated_at,
        )

    async def list_results(self, year: int) -> PleResultsResponse:
        events = await self._repo.list_events_by_year(year)
        rows: list[PleResultRowResponse] = [
            PleResultRowResponse(
                slug=ple.slug,
                label=ple.label,
                month=ple.month,
                year=ple.year,
                event_at=ple.finished_at,
                status=ple.status,  # type: ignore[arg-type]
                finished_at=ple.finished_at,
            )
            for ple in events
        ]
        return PleResultsResponse(year=year, results=rows)

    async def _require_user(self, user_id: int) -> None:
        if not await self._repo.user_exists(user_id=user_id):
            raise PleAuthRequiredError("유효한 로그인 회원이 아닙니다.")

    async def sync_event(self, *, payload: PleEventSyncCommand) -> PleBoardResponse:
        logger.info(
            "[PleInteractor] sync_event | slug=%s matches=%d",
            payload.slug,
            len(payload.matches),
        )
        snapshot = await self._repo.upsert_event_from_sync(payload)
        if payload.slug in FINISHED_EVENT_SLUGS:
            results = FINISHED_EVENT_RESULTS.get(payload.slug) or {}
            for match_key, result in results.items():
                await self._repo.set_match_result(
                    payload.slug,
                    match_key,
                    result,
                    status=PleMatchStatus.FINISHED,
                )

            if snapshot.status != PleEventStatus.FINISHED:
                await self._repo.mark_event_finished(
                    event_id=snapshot.id,
                    finished_at=datetime.now(UTC),
                )
            await self._repo.flush()

        return await self._info.get_board(slug=payload.slug)

    async def record_predictions_batch(
        self, *, slug: str, body: BatchPredictionCommand
    ) -> PleBoardResponse:
        await self._require_user(body.user_id)
        event = await self._repo.get_event_by_slug(slug)
        if event is None:
            raise LookupError(slug)

        match_by_key = {m.match_key: m for m in event.matches}
        for item in body.predictions:
            row = match_by_key.get(item.match_key)
            if row is None:
                raise LookupError(item.match_key)
            if row.status == PleMatchStatus.FINISHED:
                raise ValueError(
                    f"종료된 경기({item.match_key})에는 예측할 수 없습니다."
                )
            await self._repo.upsert_prediction(
                row.id, body.client_id, item.pick, body.user_id
            )

        logger.info(
            "[PleInteractor] record_predictions_batch | slug=%s count=%d",
            slug,
            len(body.predictions),
        )
        return await self._info.get_board(
            slug=slug, client_id=body.client_id, user_id=body.user_id
        )

    async def set_match_results_batch(
        self, *, slug: str, body: BatchResultsCommand
    ) -> PleBoardResponse:
        for item in body.results:
            result = MatchResultResponse(
                winner_side=item.winner_side,
                winner_index=item.winner_index,
                winner_name=item.winner_name,
            )
            ok = await self._repo.set_match_result(
                slug, item.match_key, result, status=item.status
            )
            if not ok:
                raise LookupError(
                    f"경기 '{item.match_key}'를 찾을 수 없습니다. PLE 카드 동기화를 다시 시도해 주세요."
                )
        logger.info(
            "[PleInteractor] set_match_results_batch | slug=%s count=%d",
            slug,
            len(body.results),
        )
        return await self._info.get_board(slug=slug)

    async def record_prediction(
        self, *, slug: str, match_key: str, body: PredictionCommand
    ) -> PleBoardResponse:
        await self._require_user(body.user_id)
        event = await self._repo.get_event_by_slug(slug)
        if event is None:
            raise LookupError(slug)

        match = next((m for m in event.matches if m.match_key == match_key), None)
        if match is None:
            raise LookupError(match_key)
        if match.status == PleMatchStatus.FINISHED:
            raise ValueError("종료된 경기에는 예측할 수 없습니다.")

        logger.info(
            "[PleInteractor] record_prediction | slug=%s match=%s userId=%s pick=%s",
            slug,
            match_key,
            body.user_id,
            body.pick,
        )
        await self._repo.upsert_prediction(
            match.id, body.client_id, body.pick, body.user_id
        )
        return await self._info.get_board(
            slug=slug, client_id=body.client_id, user_id=body.user_id
        )

    async def set_match_result(
        self, *, slug: str, match_key: str, body: MatchResultUpdateCommand
    ) -> PleBoardResponse:
        result = MatchResultResponse(
            winner_side=body.winner_side,
            winner_index=body.winner_index,
            winner_name=body.winner_name,
        )
        event = await self._repo.get_event_by_slug(slug)
        if event is None:
            raise LookupError(
                f"PLE '{slug}'를 찾을 수 없습니다. 먼저 카드를 동기화해 주세요."
            )

        ok = await self._repo.set_match_result(
            slug, match_key, result, status=body.status
        )
        if not ok:
            raise LookupError(
                f"경기 '{match_key}'를 찾을 수 없습니다. PLE 카드 동기화를 다시 시도해 주세요."
            )
        logger.info(
            "[PleInteractor] set_match_result | slug=%s match=%s", slug, match_key
        )
        return await self._info.get_board(slug=slug)

    async def introduce_myself(self, query: MyselfQuery) -> MyselfResponse:
        return await self.repository.introduce_myself(query)
