from __future__ import annotations

from abc import ABC, abstractmethod

from kayfabe.app.dtos.ple_events_dto import (
    BatchPredictionCommand,
    BatchResultsCommand,
    MatchResultUpdateCommand,
    PleAiStatsResponse,
    PleBoardResponse,
    PleEventSummaryResponse,
    PleEventSyncCommand,
    PleResultsResponse,
    PredictionCommand,
)


class PleEventsUseCase(ABC):
    """`/ple/*` GET inbound(ple_events_router) 조회 입력 포트."""

    @abstractmethod
    async def list_events(self) -> list[PleEventSummaryResponse]: ...

    @abstractmethod
    async def get_ai_stats(self) -> PleAiStatsResponse: ...

    @abstractmethod
    async def get_board(
        self,
        *,
        slug: str,
        client_id: str | None = None,
        user_id: int | None = None,
    ) -> PleBoardResponse: ...

    @abstractmethod
    async def list_results(self, year: int) -> PleResultsResponse: ...

    @abstractmethod
    async def sync_event(self, *, payload: PleEventSyncCommand) -> PleBoardResponse: ...

    @abstractmethod
    async def record_predictions_batch(
        self, *, slug: str, body: BatchPredictionCommand
    ) -> PleBoardResponse: ...

    @abstractmethod
    async def set_match_results_batch(
        self, *, slug: str, body: BatchResultsCommand
    ) -> PleBoardResponse: ...

    @abstractmethod
    async def record_prediction(
        self, *, slug: str, match_key: str, body: PredictionCommand
    ) -> PleBoardResponse: ...

    @abstractmethod
    async def set_match_result(
        self, *, slug: str, match_key: str, body: MatchResultUpdateCommand
    ) -> PleBoardResponse: ...
