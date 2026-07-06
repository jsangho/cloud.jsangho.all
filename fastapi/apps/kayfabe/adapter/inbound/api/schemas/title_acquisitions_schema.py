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

    model_config = ConfigDict(populate_by_name=True)


class CompetitorTitleHistoryResponseSchema(BaseModel):
    name: str
    acquisitions: list[TitleAcquisitionSchema]
    total: int

    model_config = ConfigDict(populate_by_name=True)
