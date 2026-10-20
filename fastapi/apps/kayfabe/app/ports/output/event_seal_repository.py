"""대회 행의 `finished_at`을 봉인하는 **좁은 문** 하나.

`PleEventsRepository`에 `mark_event_finished`가 이미 있는데 포트를 새로 내는 이유는
둘이다.

1. **그 포트가 넓다.** 같은 객체에 `upsert_event_from_sync`가 있고 그것은 카드에
   없는 경기를 지운다(`ple_predictions`가 CASCADE로 함께 사라진다). 에이전트가 쥐는
   손에 그 메서드가 딸려 가지 않게 한다 — `MatchResultWriter`가 난 것과 같은 판단이고,
   `set_event_status`·`set_event_schedule`도 그 이유로 좁은 문이다.
2. **`mark_event_finished`가 하는 일이 더 많다.** `status`를 쓰고 `winner_pick`이
   있는 경기의 `status`·`finished_at`까지 뒤집는다. 봉인 대상은 **이미 `finished`인
   대회**이므로 그 쓰기가 전부 불필요하다. 이 포트는 **한 칸만** 쓴다.

판정은 여기 없다 — `domain/services/event_seal.seal_decision`이 한다. 이 포트는
그 판정의 입력을 읽어 주고, 결론이 나오면 그 한 칸을 쓴다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from kayfabe.domain.services.event_seal import EventSealState


class EventSealRepository(ABC):
    @abstractmethod
    async def read_seal_state(self, *, event_slug: str) -> EventSealState | None:
        """판정에 필요한 사실만. 대회 행이 없으면 `None`.

        **읽기 전용이다.** 결과 유무는 `winner_pick`으로 센다.
        """
        ...

    @abstractmethod
    async def seal_event_finished_at(
        self, *, event_slug: str, finished_at: datetime
    ) -> bool:
        """`finished_at` 한 칸만 쓴다. 쓰지 않았으면 `False`.

        계약:

        - **이미 값이 있으면 쓰지 않고 `False`.** 덮어쓰기는 어떤 경우에도 없다.
        - 없는 slug면 `False`. 행을 만들지 않는다.
        - `status`·`ple_matches`·`ple_predictions`·`ple_agent_predictions`를
          읽지도 쓰지도 않는다.
        - 커밋하지 않는다 — 트랜잭션 경계는 부르는 쪽이 정한다.
        """
        ...
