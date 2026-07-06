from dataclasses import dataclass


@dataclass(frozen=True)
class MollyScalerQuery:
    id: int
    name: str


@dataclass(frozen=True)
class MollyScalerResponse:
    id: int
    name: str
