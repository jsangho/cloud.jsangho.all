from dataclasses import dataclass


@dataclass(frozen=True)
class IsidorCoupleQuery:
    id: int
    name: str


@dataclass(frozen=True)
class IsidorCoupleResponse:
    id: int
    name: str
