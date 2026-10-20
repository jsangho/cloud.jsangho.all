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
