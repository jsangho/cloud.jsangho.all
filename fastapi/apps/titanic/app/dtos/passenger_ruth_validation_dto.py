from dataclasses import dataclass


@dataclass(frozen=True)
class RuthValidationQuery:
    id: int
    name: str


@dataclass(frozen=True)
class RuthValidationResponse:
    id: int
    name: str
