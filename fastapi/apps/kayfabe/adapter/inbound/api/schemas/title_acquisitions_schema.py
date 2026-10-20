from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ChampionshipTier = Literal["main", "secondary", "tag", "other"]
BrandId = Literal["raw", "smackdown", "nxt", "global"]
BrandAccent = Literal["red", "blue", "gold", "purple"]


class TitleReignSchema(BaseModel):
    belt_name: str = Field(alias="beltName")
    champions: list[str]
    team_name: str | None = Field(default=None, alias="teamName")
    won_at: str = Field(alias="wonAt")
    won_event: str | None = Field(default=None, alias="wonEvent")
    tier: ChampionshipTier

    model_config = ConfigDict(populate_by_name=True)


class BrandRosterSchema(BaseModel):
    id: BrandId
    label: str
    tagline: str
    accent: BrandAccent
    titles: list[TitleReignSchema]

    model_config = ConfigDict(populate_by_name=True)


class ChampionshipBoardResponseSchema(BaseModel):
    as_of: str = Field(alias="asOf")
    brands: list[BrandRosterSchema]

    model_config = ConfigDict(populate_by_name=True)


class TitleAcquisitionSchema(BaseModel):
    belt_name: str = Field(alias="beltName")
    won_at: str = Field(alias="wonAt")
    won_at_slug: str | None = Field(default=None, alias="wonAtSlug")
    match_key: str | None = Field(default=None, alias="matchKey")
    #: `won_at` 에서 가른 값들. **`won_at` 은 그대로 둔다** — 화면이 이미 그것을
    #: 쓰고 있고, 파서가 못 읽은 행에서는 원문이 유일한 정보다.
    event_label: str | None = Field(default=None, alias="eventLabel")
    #: ISO 날짜(`2009-04-05`). 못 읽으면 `None` — 지어내지 않는다.
    won_on: str | None = Field(default=None, alias="wonOn")

    model_config = ConfigDict(populate_by_name=True)


class CompetitorTitleHistoryResponseSchema(BaseModel):
    name: str
    acquisitions: list[TitleAcquisitionSchema]
    total: int

    model_config = ConfigDict(populate_by_name=True)
