"""Pydantic Schema ↔ app DTO 변환 (HTTP 경계)."""

from __future__ import annotations

from kayfabe.adapter.inbound.api.schemas.ple_events_schema import (
    CompetitorSchema,
    MatchBoardSchema,
    MatchCardSyncSchema,
    MatchResultSchema,
    PleAiRecordSchema,
    PleAiStatsSchema,
    PleBoardSchema,
    PleEventSummarySchema,
    PleEventSyncSchema,
    VoteTotalsSchema,
)
from kayfabe.adapter.inbound.api.schemas.ple_match_pick_schema import (
    BatchPredictionRequestSchema,
    PredictionRequestSchema,
)
from kayfabe.adapter.inbound.api.schemas.ple_matches_schema import (
    BatchResultsRequestSchema,
    MatchResultUpdateSchema,
)
from kayfabe.app.dtos.ple_events_dto import (
    BatchPredictionCommand,
    BatchResultItemCommand,
    BatchResultsCommand,
    CompetitorResponse,
    MatchBoardResponse,
    MatchCardSyncCommand,
    MatchResultResponse,
    MatchResultUpdateCommand,
    PleAiStatsResponse,
    PleBoardResponse,
    PleEventSummaryResponse,
    PleEventSyncCommand,
    PredictionCommand,
    PredictionItemCommand,
)


def _competitor_from_schema(schema: CompetitorSchema) -> CompetitorResponse:
    return CompetitorResponse(name=schema.name, is_champion=schema.is_champion)


def _competitor_to_schema(dto: CompetitorResponse) -> CompetitorSchema:
    return CompetitorSchema(name=dto.name, isChampion=dto.is_champion)


def _match_result_from_schema(
    schema: MatchResultSchema | None,
) -> MatchResultResponse | None:
    if schema is None:
        return None
    return MatchResultResponse(
        winner_side=schema.winner_side,
        winner_index=schema.winner_index,
        winner_name=schema.winner_name,
    )


def _match_result_to_schema(
    dto: MatchResultResponse | None,
) -> MatchResultSchema | None:
    if dto is None:
        return None
    return MatchResultSchema(
        winnerSide=dto.winner_side,
        winnerIndex=dto.winner_index,
        winnerName=dto.winner_name,
    )


def event_sync_from_schema(schema: PleEventSyncSchema) -> PleEventSyncCommand:
    return PleEventSyncCommand(
        slug=schema.slug,
        label=schema.label,
        month=schema.month,
        year=schema.year,
        status=schema.status,
        matches=[_match_card_from_schema(m) for m in schema.matches],
    )


def _match_card_from_schema(schema: MatchCardSyncSchema) -> MatchCardSyncCommand:
    return MatchCardSyncCommand(
        id=schema.id,
        title=schema.title,
        card_variant=schema.card_variant,
        format=schema.format,
        left=_competitor_from_schema(schema.left) if schema.left else None,
        right=_competitor_from_schema(schema.right) if schema.right else None,
        competitors=[_competitor_from_schema(c) for c in schema.competitors]
        if schema.competitors
        else None,
        bookmaker_decimal=schema.bookmaker_decimal,
        result=_match_result_from_schema(schema.result),
    )


def prediction_from_schema(schema: PredictionRequestSchema) -> PredictionCommand:
    return PredictionCommand(
        pick=schema.pick,
        client_id=schema.client_id,
        user_id=schema.user_id,
    )


def batch_prediction_from_schema(
    schema: BatchPredictionRequestSchema,
) -> BatchPredictionCommand:
    return BatchPredictionCommand(
        client_id=schema.client_id,
        user_id=schema.user_id,
        predictions=[
            PredictionItemCommand(match_key=p.match_key, pick=p.pick)
            for p in schema.predictions
        ],
    )


def batch_results_from_schema(schema: BatchResultsRequestSchema) -> BatchResultsCommand:
    return BatchResultsCommand(
        results=[
            BatchResultItemCommand(
                match_key=r.match_key,
                winner_side=r.winner_side,
                winner_index=r.winner_index,
                winner_name=r.winner_name,
                status=r.status,
            )
            for r in schema.results
        ]
    )


def match_result_update_from_schema(
    schema: MatchResultUpdateSchema,
) -> MatchResultUpdateCommand:
    return MatchResultUpdateCommand(
        winner_side=schema.winner_side,
        winner_index=schema.winner_index,
        winner_name=schema.winner_name,
        status=schema.status,
    )


def board_to_schema(dto: PleBoardResponse) -> PleBoardSchema:
    return PleBoardSchema(
        slug=dto.slug,
        label=dto.label,
        month=dto.month,
        year=dto.year,
        status=dto.status,
        finishedAt=dto.finished_at,
        matches=[_match_board_to_schema(m) for m in dto.matches],
        updatedAt=dto.updated_at,
    )


def _match_board_to_schema(dto: MatchBoardResponse) -> MatchBoardSchema:
    return MatchBoardSchema(
        id=dto.id,
        db_id=dto.db_id,
        title=dto.title,
        cardVariant=dto.card_variant,
        format=dto.format,
        left=_competitor_to_schema(dto.left) if dto.left else None,
        right=_competitor_to_schema(dto.right) if dto.right else None,
        competitors=[_competitor_to_schema(c) for c in dto.competitors]
        if dto.competitors
        else None,
        bookmakerDecimal=dto.bookmaker_decimal,
        status=dto.status,
        result=_match_result_to_schema(dto.result),
        siteVotes=VoteTotalsSchema(
            left=dto.site_votes.left,
            right=dto.site_votes.right,
            multi=list(dto.site_votes.multi),
        ),
        locked=dto.locked,
        myPick=dto.my_pick,
        aiPick=dto.ai_pick,
        aiPickName=dto.ai_pick_name,
        aiCorrect=dto.ai_correct,
        pointValue=dto.point_value,
    )


def event_summary_to_schema(dto: PleEventSummaryResponse) -> PleEventSummarySchema:
    return PleEventSummarySchema(
        slug=dto.slug,
        label=dto.label,
        month=dto.month,
        year=dto.year,
        status=dto.status,
        matchCount=dto.match_count,
    )


def ai_stats_to_schema(dto: PleAiStatsResponse) -> PleAiStatsSchema:
    return PleAiStatsSchema(
        totalGraded=dto.total_graded,
        correct=dto.correct,
        incorrect=dto.incorrect,
        accuracyPercent=dto.accuracy_percent,
        recent=[
            PleAiRecordSchema(
                eventSlug=r.event_slug,
                eventLabel=r.event_label,
                matchKey=r.match_key,
                matchTitle=r.match_title,
                aiPickName=r.ai_pick_name,
                winnerName=r.winner_name,
                correct=r.correct,
            )
            for r in dto.recent
        ],
    )


def match_result_from_command(
    cmd: MatchResultUpdateCommand | BatchResultItemCommand,
) -> MatchResultResponse:
    return MatchResultResponse(
        winner_side=cmd.winner_side,
        winner_index=cmd.winner_index,
        winner_name=cmd.winner_name,
    )
