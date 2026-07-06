from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Parch:
    value: int  # 부모·자녀 수 (보모 동반 어린이의 경우 0)

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError(f"Parch는 0 이상이어야 합니다: {self.value}")

    @classmethod
    def from_raw(cls, raw: str | None) -> Parch:
        if not raw or not raw.strip():
            return cls(value=0)
        try:
            return cls(value=int(raw.strip()))
        except ValueError as e:
            raise ValueError(f"Parch 파싱 실패: '{raw}'") from e

    def __str__(self) -> str:
        return str(self.value)
