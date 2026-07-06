from dataclasses import dataclass


@dataclass(frozen=True)
class CalTesterQuery:
    id: int
    name: str


@dataclass(frozen=True)
class CalPistolResponse:
    id: int
    name: str


CalTesterResponse = CalPistolResponse
