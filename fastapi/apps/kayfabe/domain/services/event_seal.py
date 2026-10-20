"""결과가 다 들어온 대회의 `finished_at`을 봉인할지 **판정만** 한다.

## 왜 필요한가

`finished_at`의 뜻은 "결과가 기록된 시각"인데, 결과를 쓰는 경로가 둘인데 한쪽만
대회 행을 쓴다. `sync_event`는 쓰고(그것도 `status != finished`일 때만), 결과 확정
에이전트(`set_match_result`)는 **경기 행만** 쓴다. 그래서 결과가 100% 들어찬 대회가
`NULL`로 남고, 2026-10-20에 넷이 그 모양이었다.

`backfill_event_finished_at.py`가 뒤따라 메꿔 왔지만 그것은 사람이 기억해야 도는
두 번째 걸음이다. 이 판정을 도메인으로 올려 **에이전트가 스스로 봉인**하게 하고,
백필은 역사 행과 다른 경로를 위해 남긴다. 둘이 같은 뜻을 쓰는지는 서로 검산한다 —
봉인이 돌면 백필 드라이런이 0건이어야 한다.

## 규칙 넷

1. 대회 `finished_at`에 **값이 있으면 쓰지 않는다.** 백필과 같은 규칙이다.
2. 경기가 **전부** 결과를 가질 때만 봉인한다. **부분 기록은 봉인하지 않는다** —
   다 들어온 것과 일부만 들어온 것을 같은 시각으로 봉인하면 나중에 구분할 수 없다
   (백필 독스트링의 그 판단).
3. 값은 `now()`가 아니라 **`max(경기 finished_at)`** 이다. 같은 실행 안이라 밀리초
   차이뿐이지만, 백필과 **같은 뜻**을 쓰게 되고(의미가 두 벌로 갈리면 한쪽만 고친
   날 조용히 어긋난다) 재시도·부분 실패에 거짓 시각이 박히지 않는다.
4. 경기가 0건이면 보류다. 셀 것이 없으면 "다 들어왔다"가 참이 되어 버린다.

**결과 유무는 `winner_pick`으로 센다.** `winner_name`은 팀 이름 칸이라 임시 팀이면
`NULL`이 정상이고(`Danhausen & Minihausen` 꼴), 그것으로 세면 멀쩡한 경기가 미기록
으로 잡힌다.

여기에는 판정만 있다. 무엇을 읽고 쓸지는 바깥의 몫이다
(`domain/services/event_status_drift`와 같은 자리다).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class EventSealState:
    """대회 한 행과 그 경기들을 맞댄 사실. **판정의 입력이 이것뿐이다.**"""

    slug: str
    match_count: int
    #: `winner_pick`이 있는 경기 수.
    result_count: int
    #: 그 경기들의 `finished_at` 최대값. 경기에 시각이 없으면 `None`.
    latest_match_finished_at: datetime | None
    #: 대회 행이 지금 들고 있는 값.
    event_finished_at: datetime | None

    @property
    def all_results_in(self) -> bool:
        """경기가 하나 이상이고 전부 결과를 가졌는가."""
        return self.match_count > 0 and self.result_count == self.match_count


def seal_decision(state: EventSealState) -> datetime | None:
    """봉인할 시각. **봉인하지 않으면 `None`이다.**

    `None`은 넷 중 하나다 — 이미 값이 있음 · 경기 0건 · 결과가 일부만 · 경기에
    시각이 없어 재구성할 재료가 없음. 넷 다 정상이므로 부르는 쪽은 예외로 보지
    않는다.
    """
    if state.event_finished_at is not None:
        return None
    if not state.all_results_in:
        return None
    return state.latest_match_finished_at
