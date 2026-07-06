from dataclasses import dataclass


@dataclass(frozen=True)
class HartleyViolinQuery:
    id: int
    name: str


@dataclass(frozen=True)
class HartleyViolinResponse:
    id: int
    name: str
