from __future__ import annotations

from dataclasses import dataclass

_PASSENGER_DECKS = frozenset("ABCDEFG")


@dataclass(frozen=True)
class Cabin:
    value: str | None

    @classmethod
    def from_raw(cls, raw: str | None) -> Cabin:
        if raw is None or not str(raw).strip():
            return cls(value=None)
        return cls(value=str(raw).strip())

    @property
    def is_unknown(self) -> bool:
        return self.value is None

    @property
    def deck(self) -> str | None:
        """갑판 구역 (A~G). 객실 번호 첫 알파벳에서 추출."""
        if self.value is None:
            return None
        first = self.value[0].upper()
        return first if first in _PASSENGER_DECKS else None

    @property
    def has_deck_info(self) -> bool:
        """갑판 정보 추출 가능 여부. 선박 내 위치 및 구조선 거리 추정에 활용."""
        return self.deck is not None

    def __str__(self) -> str:
        return self.value if self.value is not None else ""
