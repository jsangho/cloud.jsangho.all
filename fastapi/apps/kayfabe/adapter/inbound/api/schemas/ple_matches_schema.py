from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from kayfabe.adapter.inbound.api.schemas.ple_events_schema import (
    PleBoardSchema,  # noqa: F401
)

__all__ = [
    "PleBoardSchema",
    "BatchResultItemSchema",
    "BatchResultsRequestSchema",
    "MatchResultUpdateSchema",
    "MatchResultKind",
    "CompetitorListResponseSchema",
    "CompetitorSummarySchema",
    "CompetitorMatchRecordSchema",
    "CompetitorProfileResponseSchema",
]

MatchResultKind = Literal["win", "loss", "no-contest", "pending"]


class BatchResultItemSchema(BaseModel):
    match_key: str = Field(..., alias="matchKey")
    winner_side: Literal["left", "right"] | None = Field(
        default=None, alias="winnerSide"
    )
    winner_index: int | None = Field(default=None, alias="winnerIndex")
    winner_name: str | None = Field(default=None, alias="winnerName")
    status: Literal["scheduled", "live", "finished"] | None = "finished"

    model_config = ConfigDict(populate_by_name=True)


class BatchResultsRequestSchema(BaseModel):
    results: list[BatchResultItemSchema] = Field(..., min_length=1)

    model_config = ConfigDict(populate_by_name=True)


class MatchResultUpdateSchema(BaseModel):
    winner_side: Literal["left", "right"] | None = Field(
        default=None, alias="winnerSide"
    )
    winner_index: int | None = Field(default=None, alias="winnerIndex")
    winner_name: str | None = Field(default=None, alias="winnerName")
    status: Literal["scheduled", "live", "finished"] | None = None

    model_config = ConfigDict(populate_by_name=True)


class CompetitorListResponseSchema(BaseModel):
    names: list[str]

    model_config = ConfigDict(populate_by_name=True)


class CompetitorSummarySchema(BaseModel):
    total: int
    wins: int
    losses: int
    no_contest: int = Field(alias="noContest")
    pending: int
    singles_total: int = Field(alias="singlesTotal")
    multi_total: int = Field(alias="multiTotal")
    champion_appearances: int = Field(alias="championAppearances")

    model_config = ConfigDict(populate_by_name=True)


class CompetitorMatchRecordSchema(BaseModel):
    slug: str
    ple_label: str = Field(alias="pleLabel")
    match_key: str = Field(alias="matchKey")
    title: str
    format: Literal["singles", "multi"]
    result: MatchResultKind
    winner_name: str | None = Field(default=None, alias="winnerName")
    opponents: list[str] = Field(default_factory=list)
    participants: list[str] = Field(default_factory=list)
    was_champion: bool = Field(default=False, alias="wasChampion")

    model_config = ConfigDict(populate_by_name=True)


class CompetitorProfileResponseSchema(BaseModel):
    name: str
    matches: list[CompetitorMatchRecordSchema]
    summary: CompetitorSummarySchema

    model_config = ConfigDict(populate_by_name=True)
