from dataclasses import dataclass


@dataclass(frozen=True)
class LoweBoatQuery:
    id: int
    name: str


@dataclass(frozen=True)
class LoweBoatResponse:
    id: int
    name: str
