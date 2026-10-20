"""**결과가 아직 없는 경기**를 찾는 출력 포트.

`finished` + `winner_pick IS NULL`이 그 상태다. 대회가 아니라 경기를 세는 이유는
**한 대회에서 일부만 기록된 상태가 실제로 있기** 때문이다(메인만 넣고 프리쇼를
빼먹는 식).

**`winner_pick`이 유일한 지표다.** 한때 이 자리에 `close_past_events.py`의
"`finished` + `finished_at IS NULL`이 끝났지만 결과 미기록을 정확히 말한다"를
근거로 적었는데 그 주장이 틀렸다(2026-10-20 · 결과가 100% 들어찬 대회 넷이
`finished_at IS NULL`이었다). `winner_name`도 지표가 아니다 — 팀 이름 칸이라
임시 팀이면 `NULL`이 정상이다.

**읽기 전용이다.** 쓰기는 `MatchResultWriter` 하나뿐이고, 둘을 나눈 이유는 이 포트를
쥔 쪽이 쓰기에 닿지 못하게 하는 것이다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from kayfabe.domain.entities.result_verification import MatchUnderReview


class PendingResultRepository(ABC):
    @abstractmethod
    async def list_pending(
        self, *, event_slug: str | None = None, limit: int | None = None
    ) -> tuple[MatchUnderReview, ...]:
        """결과가 없는 경기를 대회 날짜·`match_key` 순서로.

        - 아직 열리지 않은 대회는 제외한다. `status`가 `finished`인 대회만 본다 —
          열리지도 않은 경기의 승자를 찾는 일은 없다.
        - 선택지를 못 읽는 경기(카드가 비었거나 이름이 없는 경우)는 제외한다.
          선택지가 없으면 대조할 것이 없어 어차피 보류가 된다.
        - `limit`은 **자르기 전 총수를 함께 알 수 없다.** 부르는 쪽이 총수가 필요하면
          `limit` 없이 한 번 더 부른다(`count_pending`을 따로 두지 않았다).
        """
        ...
