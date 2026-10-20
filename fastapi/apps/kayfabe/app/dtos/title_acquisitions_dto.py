from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

from kayfabe.adapter.inbound.api.schemas.title_acquisitions_schema import (
    BrandRosterSchema,
    ChampionshipBoardResponseSchema,
    CompetitorTitleHistoryResponseSchema,
    TitleAcquisitionSchema,
    TitleReignSchema,
)

ChampionshipTier = Literal["main", "secondary", "tag", "other"]
BrandId = Literal["raw", "smackdown", "nxt", "global"]
BrandAccent = Literal["red", "blue", "gold", "purple"]


@dataclass(frozen=True)
class TitleReignResponse:
    belt_name: str
    champions: list[str]
    won_at: str
    tier: ChampionshipTier
    team_name: str | None = None
    won_event: str | None = None

    def to_schema(self):
        return TitleReignSchema(
            belt_name=self.belt_name,
            champions=list(self.champions),
            team_name=self.team_name,
            won_at=self.won_at,
            won_event=self.won_event,
            tier=self.tier,
        )


@dataclass(frozen=True)
class BrandRosterResponse:
    id: BrandId
    label: str
    tagline: str
    accent: BrandAccent
    titles: list[TitleReignResponse]

    def to_schema(self):
        return BrandRosterSchema(
            id=self.id,
            label=self.label,
            tagline=self.tagline,
            accent=self.accent,
            titles=[t.to_schema() for t in self.titles],
        )


@dataclass(frozen=True)
class ChampionshipBoardResponse:
    as_of: str
    brands: list[BrandRosterResponse]

    def to_schema(self):
        return ChampionshipBoardResponseSchema(
            as_of=self.as_of,
            brands=[b.to_schema() for b in self.brands],
        )


@dataclass(frozen=True)
class TitleAcquisitionResponse:
    belt_name: str
    won_at: str
    won_at_slug: str | None
    match_key: str | None
    #: `won_at` 을 가른 결과. `None` 은 "못 읽었다" 이고 정상이다
    #: (`domain/services/title_event_date`).
    event_label: str | None = None
    won_on: date | None = None

    def to_schema(self):
        return TitleAcquisitionSchema(
            belt_name=self.belt_name,
            won_at=self.won_at,
            won_at_slug=self.won_at_slug,
            match_key=self.match_key,
            event_label=self.event_label,
            won_on=self.won_on.isoformat() if self.won_on else None,
        )


@dataclass(frozen=True)
class CompetitorTitleHistoryResponse:
    name: str
    acquisitions: list[TitleAcquisitionResponse]

    def to_schema(self):
        items = [a.to_schema() for a in self.acquisitions]
        return CompetitorTitleHistoryResponseSchema(
            name=self.name,
            acquisitions=items,
            total=len(items),
        )
