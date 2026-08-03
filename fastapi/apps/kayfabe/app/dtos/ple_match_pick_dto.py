from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CosmeticItem:
    """순위표에 노출되는 상점 아이템. `code`는 표시 규칙 매핑용, `name`은 표시용."""

    code: str
    name: str


@dataclass(frozen=True)
class EquippedCosmetics:
    """장착 중인 치장 아이템 — 카테고리별 최대 하나."""

    title: CosmeticItem | None = None
    nickname_color: CosmeticItem | None = None
    badge: CosmeticItem | None = None


@dataclass(frozen=True)
class LeaderboardQuery:
    rank: int
    nickname: str
    score: int
    correct: int
    graded: int
    cosmetics: EquippedCosmetics = field(default_factory=EquippedCosmetics)


@dataclass(frozen=True)
class RankingRowResponse:
    rank: int
    nickname: str
    score: int
    accuracy: float
    cosmetics: EquippedCosmetics = field(default_factory=EquippedCosmetics)


@dataclass(frozen=True)
class RankingsResponse:
    rows: list[RankingRowResponse]
    my_rank: RankingRowResponse | None
