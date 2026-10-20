from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

from kayfabe.adapter.inbound.api.schemas.ple_matches_schema import (
    CompetitorListResponseSchema,
    CompetitorMatchRecordSchema,
    CompetitorProfileResponseSchema,
    CompetitorSummarySchema,
)

MatchResultKind = Literal["win", "loss", "no-contest", "pending"]


@dataclass(frozen=True)
class CompetitorMatchRecordResponse:
    slug: str
    ple_label: str
    match_key: str
    title: str
    format: Literal["singles", "multi"]
    result: MatchResultKind
    winner_name: str | None
    opponents: list[str]
    participants: list[str]
    was_champion: bool
    #: 대회 날짜. **`derive_match_record_from_orm` 은 건드리지 않았다** — 그 함수는
    #: 데이터 센터와 공유하고 날짜를 쓸 자리가 없어서, 이 칸만 스냅샷에서 직접 받는다.
    #: 기본값이 있으므로 **필드 맨 뒤여야 한다**(dataclass 규칙).
    event_date: date | None = None

    def to_schema(self):
        return CompetitorMatchRecordSchema(
            slug=self.slug,
            ple_label=self.ple_label,
            match_key=self.match_key,
            title=self.title,
            format=self.format,
            result=self.result,
            winner_name=self.winner_name,
            opponents=list(self.opponents),
            participants=list(self.participants),
            was_champion=self.was_champion,
            event_date=self.event_date.isoformat() if self.event_date else None,
        )


@dataclass(frozen=True)
class CompetitorSummaryResponse:
    total: int
    wins: int
    losses: int
    no_contest: int
    pending: int
    singles_total: int
    multi_total: int
    champion_appearances: int

    def to_schema(self):
        return CompetitorSummarySchema(
            total=self.total,
            wins=self.wins,
            losses=self.losses,
            no_contest=self.no_contest,
            pending=self.pending,
            singles_total=self.singles_total,
            multi_total=self.multi_total,
            champion_appearances=self.champion_appearances,
        )


@dataclass(frozen=True)
class CompetitorProfileResponse:
    name: str
    matches: list[CompetitorMatchRecordResponse]
    summary: CompetitorSummaryResponse
    real_name: str | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    birth_date: str | None = None

    def to_schema(self):
        return CompetitorProfileResponseSchema(
            name=self.name,
            matches=[m.to_schema() for m in self.matches],
            summary=self.summary.to_schema(),
            real_name=self.real_name,
            height_cm=self.height_cm,
            weight_kg=self.weight_kg,
            birth_date=self.birth_date,
        )


@dataclass(frozen=True)
class CompetitorListResponse:
    names: list[str]

    def to_schema(self):
        return CompetitorListResponseSchema(names=list(self.names))
