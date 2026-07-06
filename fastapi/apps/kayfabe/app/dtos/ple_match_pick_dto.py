from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LeaderboardQuery:
    rank: int
    nickname: str
    score: int
    correct: int
    graded: int


@dataclass(frozen=True)
class RankingRowResponse:
    rank: int
    nickname: str
    score: int
    accuracy: float


@dataclass(frozen=True)
class RankingsResponse:
    rows: list[RankingRowResponse]
    my_rank: RankingRowResponse | None
