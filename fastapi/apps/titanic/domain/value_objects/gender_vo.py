from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar


class GenderType(StrEnum):
    MALE = "male"
    FEMALE = "female"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Gender:
    value: GenderType

    _NORMALIZE_MAP: ClassVar[dict[str, GenderType]] = {
        "male": GenderType.MALE,
        "m": GenderType.MALE,
        "female": GenderType.FEMALE,
        "f": GenderType.FEMALE,
    }

    @classmethod
    def from_raw(cls, raw: str | None) -> Gender:
        if raw is None:
            return cls(value=GenderType.UNKNOWN)
        normalized = raw.strip().lower()
        return cls(value=cls._NORMALIZE_MAP.get(normalized, GenderType.UNKNOWN))

    def is_female(self) -> bool:
        return self.value == GenderType.FEMALE

    def __str__(self) -> str:
        return self.value.value
