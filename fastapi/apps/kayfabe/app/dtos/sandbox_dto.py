"""장난감 시뮬레이터 응답. **입력을 그대로 돌려준다.**

근거를 숨기면 장난감 숫자가 진짜처럼 보인다. 화면이 "타이틀 12회 vs 1회 · 나이
41 vs 21" 을 적을 수 있어야 하므로 점수와 뽑기 값까지 내보낸다.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SimContenderResponse:
    name: str
    titles: int
    age: int | None
    score: float


@dataclass(frozen=True)
class SimResultResponse:
    a: SimContenderResponse
    b: SimContenderResponse
    winner: str
    probability_a: float
    roll: float


@dataclass(frozen=True)
class CareerStateResponse:
    """런 하나의 전부. **클라이언트가 이걸 들고 다닌다** — 서버는 저장하지 않는다."""

    name: str
    style: str
    week: int
    brand: str
    popularity: int
    wins: int
    losses: int
    reigns: list[str]
    held: str | None
    out_weeks: int
    outcome: str | None


@dataclass(frozen=True)
class CareerStepResponse:
    state: CareerStateResponse
    week: int
    kind: str
    won: bool | None
    opponent: str | None
    belt: str | None
    promoted_to: str | None
    injured_weeks: int
    popularity_delta: int
    #: 다음 주에 도전 가능한 벨트. `None` 이면 경기만 할 수 있다.
    next_belt: str | None
    #: 그 도전이 방어인가.
    defending: bool
