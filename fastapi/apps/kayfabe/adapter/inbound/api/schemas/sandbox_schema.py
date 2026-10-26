"""장난감 시뮬레이터 스키마."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _Camel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class SimContenderSchema(_Camel):
    name: str
    titles: int
    age: int | None = None
    #: 공식이 매긴 점수. **화면이 이 값을 보여 준다** — 근거를 숨기면 장난감
    #: 숫자가 진짜처럼 읽힌다.
    score: float


class SimResultSchema(_Camel):
    """**이것은 예측이 아니다.** 실제 예측은 `/ai-lab` 이 한다.

    `probabilityA` 는 `0.15`~`0.85` 안에 머문다 — 업셋이 항상 남는다.
    `roll` 은 두 이름에서 나온 고정값이라 **같은 쌍이면 항상 같은 결과**다.
    """

    a: SimContenderSchema
    b: SimContenderSchema
    winner: str
    probability_a: float = Field(alias="probabilityA")
    roll: float


class CareerStateSchema(_Camel):
    """런 하나의 전부. **클라이언트가 들고 다닌다** — 서버는 저장하지 않는다.

    요청에도 이 모양이 그대로 들어온다. 서버가 상태를 모르므로, 저장·세이브·버전
    호환이 애초에 생기지 않는다.
    """

    name: str = Field(min_length=1, max_length=40)
    style: str
    week: int = Field(default=1, ge=1, le=200)
    brand: str = "NXT"
    popularity: int = Field(default=20, ge=0, le=100)
    wins: int = Field(default=0, ge=0)
    losses: int = Field(default=0, ge=0)
    reigns: list[str] = Field(default_factory=list)
    held: str | None = None
    out_weeks: int = Field(default=0, ge=0, le=20, alias="outWeeks")
    outcome: str | None = None


class CareerStepRequest(_Camel):
    state: CareerStateSchema
    #: `경기` 또는 `도전`. **`휴식` 은 없다** — 득이 없는 함정이라 뺐다.
    choice: str


class CareerStepSchema(_Camel):
    state: CareerStateSchema
    week: int
    kind: str
    won: bool | None = None
    opponent: str | None = None
    belt: str | None = None
    promoted_to: str | None = Field(default=None, alias="promotedTo")
    injured_weeks: int = Field(default=0, alias="injuredWeeks")
    popularity_delta: int = Field(default=0, alias="popularityDelta")
    next_belt: str | None = Field(default=None, alias="nextBelt")
    defending: bool = False
    #: 런의 최대 주차. **화면이 이 값으로 `19 / 52` 를 적는다** — 52를 프론트에
    #: 박아 두면 서버가 시즌 길이를 바꿔도 화면만 거짓말을 한다(실제로 그랬다).
    max_weeks: int = Field(alias="maxWeeks")
