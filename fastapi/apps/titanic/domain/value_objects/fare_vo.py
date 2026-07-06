from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Fare:
    value: float | None

    def __post_init__(self) -> None:
        if self.value is not None and self.value < 0:
            raise ValueError(f"Fare는 0 이상이어야 합니다: {self.value}")

    @classmethod
    def from_raw(cls, raw: str | float | None) -> Fare:
        if raw is None or not str(raw).strip():
            return cls(value=None)
        try:
            return cls(value=float(str(raw).strip()))
        except ValueError as e:
            raise ValueError(f"Fare 파싱 실패: '{raw}'") from e

    @property
    def is_unknown(self) -> bool:
        return self.value is None

    def __str__(self) -> str:
        return "" if self.value is None else str(self.value)
