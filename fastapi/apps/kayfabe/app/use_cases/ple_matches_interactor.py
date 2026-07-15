"""PLE 경기 기록 유스케이스."""

from __future__ import annotations

from core.matrix.grid_oracle_database_manager import LAYER_LOG

from kayfabe.app.dtos.ple_events_dto import MyselfQuery, MyselfResponse
from kayfabe.app.dtos.ple_matches_dto import (
    CompetitorListResponse,
    CompetitorMatchRecordResponse,
    CompetitorProfileResponse,
    CompetitorSummaryResponse,
)
from kayfabe.app.ports.input.ple_matches_use_case import PleMatchesUseCase
from kayfabe.app.ports.output.ple_matches_repository import PleMatchesRepository
from kayfabe.app.services.records_scoring import (
    competitor_name_in_card_json,
    derive_match_record_from_orm,
    normalize_name,
)

logger = LAYER_LOG


class PleMatchesInteractor(PleMatchesUseCase):
    def __init__(
        self,
        *,
        records_repository: PleMatchesRepository,
    ) -> None:
        self._records = records_repository

    async def list_competitors(self, *, q: str | None = None) -> CompetitorListResponse:
        logger.info(
            "[PleMatchesInteractor] list_competitors -> Repository q=%s", q or "-"
        )
        names = await self._records.list_competitor_names()
        if q:
            needle = q.strip().lower()
            names = [n for n in names if needle in n.lower()]
        logger.info(
            "[PleMatchesInteractor] list_competitors <- Repository count=%d", len(names)
        )
        return CompetitorListResponse(names=names)

    async def get_competitor_profile(self, name: str) -> CompetitorProfileResponse:
        normalized = normalize_name(name)
        logger.info(
            "[PleMatchesInteractor] get_competitor_profile -> Repository name=%s",
            normalized,
        )

        matches: list[CompetitorMatchRecordResponse] = []
        snapshots = await self._records.list_match_snapshots()
        for snap in snapshots:
            if not snap.card_json:
                continue
            if not competitor_name_in_card_json(
                card_json=snap.card_json, name=normalized
            ):
                continue
            rec = derive_match_record_from_orm(
                event_slug=snap.event_slug,
                event_label=snap.event_label,
                match_key=snap.match_key,
                title=snap.title,
                format=snap.format,
                card_json=snap.card_json,
                winner_pick=snap.winner_pick,
                winner_name=snap.winner_name,
                status=snap.status,
                name=normalized,
            )
            matches.append(
                CompetitorMatchRecordResponse(
                    slug=rec.slug,
                    ple_label=rec.ple_label,
                    match_key=rec.match_key,
                    title=rec.title,
                    format=rec.format,
                    result=rec.result,
                    winner_name=rec.winner_name,
                    opponents=list(rec.opponents),
                    participants=list(rec.participants),
                    was_champion=rec.was_champion,
                )
            )

        singles_total = sum(1 for m in matches if m.format == "singles")
        multi_total = sum(1 for m in matches if m.format == "multi")
        champion_appearances = sum(1 for m in matches if m.was_champion)

        summary = CompetitorSummaryResponse(
            total=len(matches),
            wins=sum(1 for m in matches if m.result == "win"),
            losses=sum(1 for m in matches if m.result == "loss"),
            no_contest=sum(1 for m in matches if m.result == "no-contest"),
            pending=sum(1 for m in matches if m.result == "pending"),
            singles_total=singles_total,
            multi_total=multi_total,
            champion_appearances=champion_appearances,
        )

        logger.info(
            "[PleMatchesInteractor] get_competitor_profile <- name=%s matches=%d",
            normalized,
            len(matches),
        )
        return CompetitorProfileResponse(
            name=normalized, matches=matches, summary=summary
        )

    async def introduce_myself(self, query: MyselfQuery) -> MyselfResponse:
        return await self._records.introduce_myself(query)
