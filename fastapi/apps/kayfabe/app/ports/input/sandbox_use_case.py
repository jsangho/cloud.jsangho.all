"""장난감 시뮬레이터 입력 포트.

**예측 유스케이스와 갈라 둔다.** `ai_prediction_use_case` 는 세 축과 누수 검사를
거친 결과를 내고, 이쪽은 공식 하나다. 같은 포트에 두면 호출하는 쪽이 둘을 구별할
이유가 사라진다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from kayfabe.app.dtos.sandbox_dto import CareerStepResponse, SimResultResponse
from kayfabe.domain.services.career_run import CareerState


class SandboxUseCase(ABC):
    @abstractmethod
    async def simulate(self, *, a: str, b: str) -> SimResultResponse | None:
        """두 선수를 붙인다. 둘 중 하나가 로스터에 없으면 `None`.

        **쓰기가 없다.** 읽기만 하고 결과는 돌려줄 뿐 어디에도 남기지 않는다.
        """
        ...

    @abstractmethod
    async def career_step(
        self, *, state: CareerState, choice: str
    ) -> CareerStepResponse:
        """커리어 한 주를 넘긴다.

        **상태를 받아 상태를 돌려줄 뿐 저장하지 않는다.** 들고 다니는 쪽은
        클라이언트다 — 그 제약이 이전 커리어 시뮬레이터가 38,326줄로 불어난 길을
        막는다(`domain/services/career_run` 독스트링 참조).
        """
        ...
