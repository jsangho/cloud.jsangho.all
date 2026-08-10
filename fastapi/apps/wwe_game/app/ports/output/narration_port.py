"""서술 출력 포트 (하네스 §3-D9 · §6).

**구현은 하나뿐이다** — `adapter/outbound/narration/rule_narrator.py`의 `RuleNarrator`.
LLM 어댑터 자리는 비워 두되 **지금 만들지 않는다**(§13-Q1): 한도(모델당 하루 20회)와
지연(턴당 1~3초)이 자동 진행형 게임과 맞지 않고, 선택지가 덱에서만 나오므로 "예상 밖
입력에 대응"이라는 LLM의 강점도 쓸 자리가 없다.

그래도 포트를 두는 이유는 방향 때문이다. 유스케이스가 어댑터를 직접 부르면 의존성이
바깥을 향하고, `lint-imports`의 클린 아키텍처 계약이 깨진다. 구현이 하나여도 경계는
있어야 한다.

**동기 함수다.** 규칙 기반 문장 생성에는 `await`할 대상이 없다(fastapi/CLAUDE.md §9).
`async`를 붙이면 비블로킹인 것처럼 보이지만 코루틴이 될 뿐이다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from wwe_game.domain.entities.career_run import CareerRun
from wwe_game.domain.value_objects.week_report import WeekReport


class NarrationPort(ABC):
    """주차 리포트 한 건을 한 줄로 옮긴다."""

    @abstractmethod
    def narrate(self, run: CareerRun, report: WeekReport) -> str:
        """`run`은 이 리포트를 **만들어 낸** 상태다 — `simulate_week(run) -> report`.

        반영된 뒤의 상태를 넘기면 승리 문장에 이미 오른 인기도가 반영돼 온도가 어긋난다.
        """
