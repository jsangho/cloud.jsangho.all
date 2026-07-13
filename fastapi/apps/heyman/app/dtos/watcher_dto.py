from dataclasses import dataclass


@dataclass(frozen=True)
class WatcherQuery:
    id: int
    name: str


@dataclass
class WatcherResponse:
    id: int
    name: str
    description: str


@dataclass
class WatcherFilterResult:
    id: int | None
    label: str
    confidence: float
    forwarded: bool
