from dataclasses import dataclass


@dataclass(frozen=True)
class JackTrainerQuery:
    id: int
    name: str


@dataclass(frozen=True)
class JackTrainerResponse:
    id: int
    name: str
