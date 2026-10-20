"""장난감 시뮬레이터 입력 포트.

**예측 유스케이스와 갈라 둔다.** `ai_prediction_use_case` 는 세 축과 누수 검사를
거친 결과를 내고, 이쪽은 공식 하나다. 같은 포트에 두면 호출하는 쪽이 둘을 구별할
이유가 사라진다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from kayfabe.app.dtos.sandbox_dto import SimResultResponse


class SandboxUseCase(ABC):
    @abstractmethod
    async def simulate(self, *, a: str, b: str) -> SimResultResponse | None:
        """두 선수를 붙인다. 둘 중 하나가 로스터에 없으면 `None`.

        **쓰기가 없다.** 읽기만 하고 결과는 돌려줄 뿐 어디에도 남기지 않는다.
        """
        ...
