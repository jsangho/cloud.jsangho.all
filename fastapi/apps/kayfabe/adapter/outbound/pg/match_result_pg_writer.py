"""좁은 문의 구현 — `set_match_result`에 **위임한다.**

직접 `UPDATE`를 쓰지 않는 이유는 결과를 쓰는 뜻이 그 메서드에 이미 정해져 있기
때문이다(`status`를 `FINISHED`로, `finished_at`을 지금으로). 여기서 한 벌 더 쓰면
한쪽만 고친 날 두 경로가 다른 행을 만든다. 이 클래스가 하는 일은 **넓은 포트를 좁은
포트로 줄이는 것뿐**이고, 그것이 존재 이유다.
"""

from __future__ import annotations

from kayfabe.app.dtos.ple_events_dto import MatchResultResponse
from kayfabe.app.ports.output.match_result_writer import MatchResultWriter
from kayfabe.app.ports.output.ple_events_repository import PleEventsRepository


class MatchResultPgWriter(MatchResultWriter):
    def __init__(self, events: PleEventsRepository) -> None:
        self._events = events

    async def record_winner(
        self, *, event_slug: str, match_key: str, pick: str, winner_name: str
    ) -> bool:
        return await self._events.set_match_result(
            event_slug,
            match_key,
            _result(pick, winner_name),
        )


def _result(pick: str, winner_name: str) -> MatchResultResponse:
    """`pick`을 `winner_side`와 `winner_index` 중 맞는 칸에 넣는다.

    `_apply_result_to_row`가 두 칸을 다르게 읽으므로 여기서 갈라야 한다 —
    단일전은 `"left"`·`"right"` 문자열이고, 다인전은 인덱스 문자열(`"0"`·`"1"`)이다.
    `options_from_card`가 만드는 `pick` 형식이 그 둘뿐이라 이 갈림으로 충분하다.
    """
    if pick in ("left", "right"):
        return MatchResultResponse(winner_side=pick, winner_name=winner_name)
    return MatchResultResponse(winner_index=int(pick), winner_name=winner_name)
