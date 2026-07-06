from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PClassType(int, Enum):
    FIRST = 1  # 상류층
    SECOND = 2  # 중산층
    THIRD = 3  # 하류층


@dataclass(frozen=True)
class PClass:
    value: PClassType

    @classmethod
    def from_raw(cls, raw: int | str | None) -> PClass:
        if raw is None:
            raise ValueError("PClass는 필수 값입니다.")
        raw_str = str(raw).strip()
        if not raw_str:
            raise ValueError("PClass는 필수 값입니다.")
        try:
            return cls(value=PClassType(int(raw_str)))
        except (ValueError, KeyError) as e:
            raise ValueError(f"PClass 유효하지 않은 값: '{raw}'") from e

    @property
    def has_rescue_priority(self) -> bool:
        """1등석 승객은 구조 우선순위가 높았다."""
        return self.value == PClassType.FIRST

    @property
    def socioeconomic_rank(self) -> int:
        """SES 순위. 낮을수록 상류층 (1=상류, 2=중산, 3=하류)."""
        return self.value.value

    def __str__(self) -> str:
        return str(self.value.value)
