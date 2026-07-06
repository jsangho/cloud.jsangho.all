from __future__ import annotations

from dataclasses import dataclass

_MAX_AGE = 120.0


@dataclass(frozen=True)
class Age:
    value: float | None

    def __post_init__(self) -> None:
        if self.value is None:
            return
        if self.value < 0:
            raise ValueError(f"Age는 0 이상이어야 합니다: {self.value}")
        if self.value > _MAX_AGE:
            raise ValueError(f"Age는 {_MAX_AGE} 이하이어야 합니다: {self.value}")

    @classmethod
    def from_raw(cls, raw: str | None) -> Age:
        if raw is None or not raw.strip():
            return cls(value=None)
        try:
            return cls(value=float(raw.strip()))
        except ValueError as e:
            raise ValueError(f"Age 파싱 실패: '{raw}'") from e

    @property
    def is_unknown(self) -> bool:
        return self.value is None

    @property
    def is_minor(self) -> bool:
        """어린이·여성 우선 원칙 적용 대상 (18세 미만)."""
        return self.value is not None and self.value < 18.0

    def __str__(self) -> str:
        return "" if self.value is None else str(self.value)
