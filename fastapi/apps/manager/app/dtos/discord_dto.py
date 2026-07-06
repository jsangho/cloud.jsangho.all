from dataclasses import dataclass


@dataclass(frozen=True)
class DiscordQuery:
    id: int
    name: str


@dataclass
class DiscordResponse:
    id: int
    name: str
    description: str
