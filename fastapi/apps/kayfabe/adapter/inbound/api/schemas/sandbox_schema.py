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
