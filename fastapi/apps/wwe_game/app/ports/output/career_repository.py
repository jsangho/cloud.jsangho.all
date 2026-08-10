"""세이브 저장소 출력 포트 (하네스 §6).

유스케이스는 PostgreSQL을 모른다. **체험판이 이 포트의 두 번째 구현이다**(§3-D8) —
로그인 플레이는 DB에, 비로그인 플레이는 요청 본문에서 읽고 아무 데도 안 쓴다. 규칙을
한 곳에 두려고 리포지토리를 갈아 끼우는 구조라, 이 포트가 좁을수록 그 대체가 쉬워진다.

**진행 중인 세이브는 하나뿐이다**(§3-D8·§13-Q4). 그래서 목록 조회가 없고
`find_active(user_id)`가 그 자리를 대신한다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from wwe_game.app.dtos.career_dto import WeekReportView
from wwe_game.domain.entities.career_run import CareerRun


class RunNotFoundError(Exception):
    """세이브가 없거나 **남의 것**일 때 (하네스 §8 → 404).

    둘을 구분하지 않는 것이 계약이다 — 남의 `run_id`에 403을 주면 그 세이브가 존재한다는
    사실이 새어 나간다(§11-12).
    """


class CareerRepository(ABC):
    """세이브 · 주차 로그 저장소.

    로그를 같은 포트에 둔 이유: 진행 한 번이 세이브 갱신과 로그 추가를 **함께** 일으키고
    (§3-D6 저장은 진행 단위로 한 번), 둘이 갈리면 어느 한쪽만 저장되는 창이 생긴다.
    """

    @abstractmethod
    async def find_active(self, user_id: int) -> CareerRun | None:
        """진행 중인 세이브. 없으면 None — 없는 게 정상이라 예외로 만들지 않는다."""

    @abstractmethod
    async def get(self, run_id: int, user_id: int) -> CareerRun:
        """본인 세이브를 읽는다. 없거나 남의 것이면 `RunNotFoundError`."""

    @abstractmethod
    async def save(
        self, run: CareerRun, weeks: tuple[WeekReportView, ...] = ()
    ) -> CareerRun:
        """세이브를 갱신하고 주차 로그를 이어 붙인다. 새 세이브면 `id`가 채워져 돌아온다.

        **한 번의 호출로 끝나야 한다.** 진행 결과가 여러 주차라도 저장은 한 번이다.
        """

    @abstractmethod
    async def read_log(
        self, run_id: int, user_id: int, *, offset: int = 0, limit: int = 50
    ) -> tuple[tuple[WeekReportView, ...], int]:
        """(그 페이지, 전체 개수). 없거나 남의 것이면 `RunNotFoundError`."""
