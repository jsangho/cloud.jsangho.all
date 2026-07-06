from dataclasses import dataclass


@dataclass(frozen=True)
class JudgeQuery:
    id: int
    name: str


@dataclass
class JudgeResponse:
    id: int
    name: str
    description: str
