from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Survived:
    survived: bool | None = None

    @classmethod
    def from_raw(cls, raw: str | None) -> Survived:
        if raw is None or not raw.strip():
            return cls(survived=None)
        stripped = raw.strip()
        if stripped == "1":
            return cls(survived=True)
        if stripped == "0":
            return cls(survived=False)
        raise ValueError(f"Survived 파싱 실패: '{raw}'")

    @property
    def is_unknown(self) -> bool:
        return self.survived is None
