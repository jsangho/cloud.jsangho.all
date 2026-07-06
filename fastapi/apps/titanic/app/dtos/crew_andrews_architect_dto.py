from dataclasses import dataclass


@dataclass(frozen=True)
class AndrewsArchitectQuery:
    id: int
    name: str


@dataclass(frozen=True)
class AndrewsArchitectResponse:
    id: int
    name: str
