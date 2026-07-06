from dataclasses import dataclass


@dataclass(frozen=True)
class RoseModelQuery:
    id: int
    name: str


@dataclass(frozen=True)
class RoseModelResponse:
    id: int
    name: str


@dataclass
class BookingCommand:
    pclass: str
    ticket: str
    fare: str
    cabin: str
    embarked: str


@dataclass(frozen=True)
class PassengerFeaturesQuery:
    pclass: int  # 객실 등급 (1·2·3)
    sex: str  # "male" | "female"
    age: float
    sibsp: int  # 형제자매/배우자 수
    parch: int  # 부모/자녀 수
    fare: float  # 요금
    embarked: str  # "S" | "C" | "Q"


@dataclass(frozen=True)
class SurvivalPredictionResponse:
    survived: bool
    probability: float
    algorithm: str
