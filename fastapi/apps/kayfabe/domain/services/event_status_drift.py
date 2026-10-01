"""대회 `status`와 날짜가 어긋났는지 판정한다.

**원래 이 판정은 `scripts/close_past_events.py` 안에 있었다.** 같은 판정을 화면
(`/admin`)에서도 불러야 해서 도메인으로 올렸다 — 스크립트와 유스케이스가 각자
"지났다"를 구현하면, 한쪽을 고친 날 둘이 서로 다른 날짜를 말하기 시작한다.
그 스크립트의 docstring이 경계하던 것과 같은 종류의 드리프트다.

여기에는 **판정만** 있다. 무엇을 읽고 무엇을 쓸지는 바깥의 몫이다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from kayfabe.domain.value_objects.ple_status_vo import PleEventStatus


@dataclass(frozen=True)
class StatusChange:
    """대회 한 행을 오늘과 맞댄 결과."""

    slug: str
    status: str
    start_date: date | None
    end_date: date | None
    today: date

    @property
    def last_day(self) -> date | None:
        """대회의 마지막 날. 이틀짜리면 `end_date`가 그것이다."""
        return self.end_date or self.start_date

    @property
    def held(self) -> bool:
        """날짜를 모르면 판정하지 않는다 — 통과가 아니라 보류다."""
        return self.last_day is None

    @property
    def is_past(self) -> bool:
        """마지막 날이 오늘보다 앞설 때만 지난 것이다. 당일은 아니다.

        대회는 각자의 현지 시각에 열리므로, 하루를 양보하는 편이 열리지도 않은
        대회를 끝난 것으로 표시하는 것보다 안전하다.
        """
        last = self.last_day
        return last is not None and last < self.today

    @property
    def needs_write(self) -> bool:
        """`finished`가 아닌 채로 날짜가 지난 행만 쓴다.

        `upcoming`뿐 아니라 `live`도 대상이다 — 둘 다 "아직 안 끝났다"는 주장이고
        날짜가 지났으면 거짓이다. `finished`는 어느 쪽으로도 되돌리지 않는다.
        """
        return self.status != PleEventStatus.FINISHED and self.is_past

    @property
    def verdict(self) -> str:
        """화면·로그가 그대로 쓰는 한 단어. 넷 중 하나다.

        `needs_write`를 먼저 본다 — 날짜 미상(`held`)과 겹치지 않으므로 순서가
        결과를 바꾸지는 않지만, 읽는 사람이 "쓸 것"을 가장 먼저 보게 한다.
        """
        if self.needs_write:
            return "needs_close"
        if self.held:
            return "unknown_date"
        if self.status == PleEventStatus.FINISHED:
            return "already_finished"
        return "upcoming"
