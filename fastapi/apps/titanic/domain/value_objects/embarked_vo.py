from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Port(StrEnum):
    CHERBOURG = "C"  # 쉘부르 (프랑스) — 주로 1등석 탑승
    QUEENSTOWN = "Q"  # 퀸즈타운 (아일랜드)
    SOUTHAMPTON = "S"  # 사우샘프턴 (영국) — 출항지, 탑승객 최다


@dataclass(frozen=True)
class Embarked:
    value: Port | None

    @classmethod
    def from_raw(cls, raw: str | None) -> Embarked:
        if raw is None or not str(raw).strip():
            return cls(value=None)
        upper = str(raw).strip().upper()
        try:
            return cls(value=Port(upper))
        except ValueError as e:
            raise ValueError(f"Embarked 유효하지 않은 값: '{raw}'") from e

    @property
    def is_unknown(self) -> bool:
        return self.value is None

    def __str__(self) -> str:
        return self.value.value if self.value is not None else ""
