from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class MyselfSchema(BaseModel):
    id: int
    name: str


class CompetitorSchema(BaseModel):
    name: str
    is_champion: bool | None = Field(default=None, alias="isChampion")

    model_config = ConfigDict(populate_by_name=True)


class MatchResultSchema(BaseModel):
    winner_side: Literal["left", "right"] | None = Field(
        default=None, alias="winnerSide"
    )
    winner_index: int | None = Field(default=None, alias="winnerIndex")
    winner_name: str | None = Field(default=None, alias="winnerName")

    model_config = ConfigDict(populate_by_name=True)


class MatchCardSyncSchema(BaseModel):
    id: str
    title: str
    card_variant: Literal["sideA", "sideB"] = Field(alias="cardVariant")
    format: Literal["singles", "multi"]
    left: CompetitorSchema | None = None
    right: CompetitorSchema | None = None
    competitors: list[CompetitorSchema] | None = None
    bookmaker_decimal: dict[str, Any] | list[float] | None = Field(
        default=None, alias="bookmakerDecimal"
    )
    result: MatchResultSchema | None = None

    model_config = ConfigDict(populate_by_name=True)


class PleEventSyncSchema(BaseModel):
    slug: str
    label: str
    month: int
    year: int = 2026
    status: Literal["upcoming", "live", "finished"] | None = None
    matches: list[MatchCardSyncSchema]


class VoteTotalsSchema(BaseModel):
    left: int = 0
    right: int = 0
    multi: list[int] = Field(default_factory=list)


class MatchBoardSchema(BaseModel):
    id: str
    db_id: int
    title: str
    card_variant: str = Field(alias="cardVariant")
    format: Literal["singles", "multi"]
    left: CompetitorSchema | None = None
    right: CompetitorSchema | None = None
    competitors: list[CompetitorSchema] | None = None
    bookmaker_decimal: dict[str, Any] | list[float] | None = Field(
        default=None, alias="bookmakerDecimal"
    )
    status: str
    result: MatchResultSchema | None = None
    site_votes: VoteTotalsSchema = Field(alias="siteVotes")
    locked: bool = False
    my_pick: str | None = Field(default=None, alias="myPick")
    ai_pick: str | None = Field(default=None, alias="aiPick")
    ai_pick_name: str | None = Field(default=None, alias="aiPickName")
    ai_correct: bool | None = Field(default=None, alias="aiCorrect")
    point_value: int = Field(default=1, alias="pointValue")

    model_config = ConfigDict(populate_by_name=True)


class PleBoardSchema(BaseModel):
    slug: str
    label: str
    month: int
    year: int
    status: str
    finished_at: datetime | None = Field(default=None, alias="finishedAt")
    matches: list[MatchBoardSchema]
    updated_at: datetime = Field(alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)


class PleAiRecordSchema(BaseModel):
    event_slug: str = Field(alias="eventSlug")
    event_label: str = Field(alias="eventLabel")
    match_key: str = Field(alias="matchKey")
    match_title: str = Field(alias="matchTitle")
    ai_pick_name: str = Field(alias="aiPickName")
    winner_name: str | None = Field(default=None, alias="winnerName")
    correct: bool

    model_config = ConfigDict(populate_by_name=True)


class PleAiStatsSchema(BaseModel):
    total_graded: int = Field(alias="totalGraded")
    correct: int
    incorrect: int
    accuracy_percent: float | None = Field(default=None, alias="accuracyPercent")
    recent: list[PleAiRecordSchema] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class PleEventSummarySchema(BaseModel):
    slug: str
    label: str
    month: int
    year: int
    status: str
    match_count: int = Field(alias="matchCount")

    model_config = ConfigDict(populate_by_name=True)


class PleResultRowSchema(BaseModel):
    slug: str
    label: str
    month: int
    year: int
    eventAt: datetime | None = None
    status: Literal["upcoming", "live", "finished"] = "upcoming"
    finishedAt: datetime | None = None


class PleResultsResponseSchema(BaseModel):
    year: int
    results: list[PleResultRowSchema]
