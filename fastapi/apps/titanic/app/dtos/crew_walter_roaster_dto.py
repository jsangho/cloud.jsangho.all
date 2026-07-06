from dataclasses import dataclass


@dataclass(frozen=True)
class WalterRoasterQuery:
    id: int
    name: str


@dataclass(frozen=True)
class WalterRoasterResponse:
    id: int
    name: str
