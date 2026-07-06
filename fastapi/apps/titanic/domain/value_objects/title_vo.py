from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TitleCategory(StrEnum):
    MR = "Mr"
    MISS = "Miss"
    MRS = "Mrs"
    MASTER = "Master"
    ROYAL = "Royal"
    RARE = "Rare"
    UNKNOWN = "Unknown"


_RARE_RAW: frozenset[str] = frozenset(
    ["Capt", "Col", "Don", "Dr", "Major", "Rev", "Jonkheer", "Dona", "Mme"]
)
_ROYAL_RAW: frozenset[str] = frozenset(["Countess", "Lady", "Sir"])
_ALIAS: dict[str, TitleCategory] = {
    "Mlle": TitleCategory.MR,  # crew_lowe_boat_interactor 정의에 따름
    "Ms": TitleCategory.MISS,
}
_ENCODING: dict[TitleCategory, int] = {
    TitleCategory.MR: 1,
    TitleCategory.MISS: 2,
    TitleCategory.MRS: 3,
    TitleCategory.MASTER: 4,
    TitleCategory.ROYAL: 5,
    TitleCategory.RARE: 6,
    TitleCategory.UNKNOWN: 0,
}


@dataclass(frozen=True)
class Title:
    value: TitleCategory

    @classmethod
    def from_raw(cls, raw: str | None) -> Title:
        if raw is None or not raw.strip():
            return cls(value=TitleCategory.UNKNOWN)

        title = raw.strip()

        if title in _RARE_RAW:
            return cls(value=TitleCategory.RARE)
        if title in _ROYAL_RAW:
            return cls(value=TitleCategory.ROYAL)
        if title in _ALIAS:
            return cls(value=_ALIAS[title])
        try:
            return cls(value=TitleCategory(title))
        except ValueError:
            return cls(value=TitleCategory.UNKNOWN)

    @property
    def encoded(self) -> int:
        """수치 인코딩. crew_lowe_boat_interactor title_mapping 기준."""
        return _ENCODING[self.value]

    @property
    def is_unknown(self) -> bool:
        return self.value == TitleCategory.UNKNOWN

    def __str__(self) -> str:
        return self.value.value
