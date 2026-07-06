from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal


@dataclass(frozen=True)
class MyselfQuery:
    id: int
    name: str


@dataclass(frozen=True)
class MyselfResponse:
    id: int
    name: str


class MyselfRepository(ABC):
    @abstractmethod
    async def introduce_myself(self, query: MyselfQuery) -> MyselfResponse: ...


class MyselfUseCase(ABC):
    @abstractmethod
    async def introduce_myself(self, query: MyselfQuery) -> MyselfResponse: ...


@dataclass(frozen=True)
class CompetitorResponse:
    name: str
    is_champion: bool | None = None


@dataclass(frozen=True)
class MatchResultResponse:
    winner_side: Literal["left", "right"] | None = None
    winner_index: int | None = None
    winner_name: str | None = None


@dataclass(frozen=True)
class MatchCardSyncCommand:
    id: str
    title: str
    card_variant: Literal["sideA", "sideB"]
    format: Literal["singles", "multi"]
    left: CompetitorResponse | None = None
    right: CompetitorResponse | None = None
    competitors: list[CompetitorResponse] | None = None
    bookmaker_decimal: dict[str, Any] | list[float] | None = None
    result: MatchResultResponse | None = None


@dataclass(frozen=True)
class PleEventSyncCommand:
    slug: str
    label: str
    month: int
    year: int
    status: Literal["upcoming", "live", "finished"] | None
    matches: list[MatchCardSyncCommand]


@dataclass(frozen=True)
class PredictionCommand:
    pick: str
    client_id: str
    user_id: int


@dataclass(frozen=True)
class PredictionItemCommand:
    match_key: str
    pick: str


@dataclass(frozen=True)
class BatchPredictionCommand:
    client_id: str
    user_id: int
    predictions: list[PredictionItemCommand]


@dataclass(frozen=True)
class BatchResultItemCommand:
    match_key: str
    winner_side: Literal["left", "right"] | None = None
    winner_index: int | None = None
    winner_name: str | None = None
    status: Literal["scheduled", "live", "finished"] | None = "finished"


@dataclass(frozen=True)
class BatchResultsCommand:
    results: list[BatchResultItemCommand]


@dataclass(frozen=True)
class MatchResultUpdateCommand:
    winner_side: Literal["left", "right"] | None = None
    winner_index: int | None = None
    winner_name: str | None = None
    status: Literal["scheduled", "live", "finished"] | None = None


@dataclass(frozen=True)
class VoteTotalsResponse:
    left: int = 0
    right: int = 0
    multi: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class MatchBoardResponse:
    id: str
    db_id: int
    title: str
    card_variant: str
    format: Literal["singles", "multi"]
    left: CompetitorResponse | None
    right: CompetitorResponse | None
    competitors: list[CompetitorResponse] | None
    bookmaker_decimal: dict[str, Any] | list[float] | None
    status: str
    result: MatchResultResponse | None
    site_votes: VoteTotalsResponse
    locked: bool
    my_pick: str | None
    ai_pick: str | None
    ai_pick_name: str | None
    ai_correct: bool | None
    point_value: int = 1


@dataclass(frozen=True)
class PleBoardResponse:
    slug: str
    label: str
    month: int
    year: int
    status: str
    finished_at: datetime | None
    matches: list[MatchBoardResponse]
    updated_at: datetime


@dataclass(frozen=True)
class PleAiRecordResponse:
    event_slug: str
    event_label: str
    match_key: str
    match_title: str
    ai_pick_name: str
    winner_name: str | None
    correct: bool


@dataclass(frozen=True)
class PleAiStatsResponse:
    total_graded: int
    correct: int
    incorrect: int
    accuracy_percent: float | None
    recent: list[PleAiRecordResponse]


@dataclass(frozen=True)
class PleEventSummaryResponse:
    slug: str
    label: str
    month: int
    year: int
    status: str
    match_count: int
    finished_at: datetime | None = None


@dataclass(frozen=True)
class MatchSnapshotQuery:
    event_slug: str
    event_label: str
    match_key: str
    title: str
    format: str
    card_json: str
    winner_pick: str | None
    winner_name: str | None
    status: str


@dataclass(frozen=True)
class PleMatchSnapshotQuery:
    id: int
    match_key: str
    status: str


@dataclass(frozen=True)
class PleEventSnapshotQuery:
    id: int
    slug: str
    status: str
    finished_at: datetime | None
    matches: list[PleMatchSnapshotQuery]


@dataclass(frozen=True)
class PleMatchReadQuery:
    id: int
    match_key: str
    title: str
    format: Literal["singles", "multi"]
    card_variant: str
    sort_order: int
    card_json: str
    status: str
    winner_pick: str | None
    winner_name: str | None
    ai_pick: str | None
    ai_pick_name: str | None
    ai_correct: bool | None
    point_value: int = 1


@dataclass(frozen=True)
class PleEventReadQuery:
    slug: str
    label: str
    month: int
    year: int
    status: str
    finished_at: datetime | None
    updated_at: datetime
    matches: list[PleMatchReadQuery]


PleEventStatus = Literal["upcoming", "live", "finished"]


@dataclass(frozen=True)
class PleResultRowResponse:
    slug: str
    label: str
    month: int
    year: int
    event_at: datetime | None
    status: PleEventStatus
    finished_at: datetime | None

    def to_schema(self):
        from kayfabe.adapter.inbound.api.schemas.ple_events_schema import (
            PleResultRowSchema,
        )

        return PleResultRowSchema(
            slug=self.slug,
            label=self.label,
            month=self.month,
            year=self.year,
            eventAt=self.event_at,
            status=self.status,
            finishedAt=self.finished_at,
        )


@dataclass(frozen=True)
class PleResultsResponse:
    year: int
    results: list[PleResultRowResponse]

    def to_schema(self):
        from kayfabe.adapter.inbound.api.schemas.ple_events_schema import (
            PleResultsResponseSchema,
        )

        return PleResultsResponseSchema(
            year=self.year, results=[r.to_schema() for r in self.results]
        )
