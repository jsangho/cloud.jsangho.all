"""경기 결과를 쓰는 **좁은 문** 하나.

`PleEventsRepository`에 `set_match_result`가 이미 있는데 포트를 새로 내는 이유는
그 포트가 넓기 때문이다. 같은 객체에 `upsert_event_from_sync`가 있고, 그것은
**카드에 없는 경기를 지운다**(`ple_predictions`가 CASCADE로 함께 사라진다).
에이전트가 쥐는 손에 그 메서드가 딸려 가지 않게 한다 — `set_event_status`·
`set_event_schedule`이 좁은 문으로 따로 난 것과 같은 판단이다.

구현은 `set_match_result`에 **위임한다**. 결과를 쓰는 뜻(`status`를 `finished`로,
`finished_at`을 지금으로)이 두 벌로 갈리면 한쪽만 고친 날 조용히 어긋난다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class MatchResultWriter(ABC):
    @abstractmethod
    async def record_winner(
        self, *, event_slug: str, match_key: str, pick: str, winner_name: str
    ) -> bool:
        """승자 한 명을 쓴다. 대상 경기가 없으면 `False`.

        커밋하지 않는다 — 트랜잭션 경계는 부르는 쪽이 정한다.
        """
        ...
