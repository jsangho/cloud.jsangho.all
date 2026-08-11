"""탈락 경기의 진행 순서 — 입장과 탈락 (하네스 §3-D34).

럼블·챔버는 **한 번의 승패가 아니라 한 시간짜리 이야기**다. "이겼다" 한 줄로 끝내면
17번으로 들어와 넷을 넘기고 마지막에 당한 밤과, 1번으로 들어와 끝까지 버틴 밤이
화면에서 같은 것이 된다.

**여기 담기는 것은 구조뿐이다.** "3번으로 입장"이라는 문장은 화면이 만든다 — 숫자와
이름과 관계만 들고 있으면 화면이 플레이어 이름을 강조하든 줄을 접든 자유롭다.
예외는 `summary` 하나인데, 그것만 세이브의 한 칸에 문자열로 남기 때문이다(§3-D34).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class BeatKind(StrEnum):
    ENTER = "enter"
    ELIMINATE = "eliminate"
    WIN = "win"


@dataclass(frozen=True)
class MatchBeat:
    kind: BeatKind
    name: str
    number: int = 0
    """입장 순번. `ENTER`에만 채워진다 — 럼블의 번호이자 챔버의 포드 순서다."""
    by: str | None = None
    """누가 탈락시켰는가. `ELIMINATE`에만 채워진다."""


@dataclass(frozen=True)
class MatchSequence:
    """한 경기의 전체 진행. 플레이어 기준 요약을 함께 든다."""

    beats: tuple[MatchBeat, ...]
    summary: str
    """세이브에 남는 한 줄. **이것만 저장한다** — 럼블 하나가 59비트라 전부 담으면
    커리어당 2천 줄이 된다 (2026-08-11 사용자 결정).
    """
    entry_number: int
    """플레이어가 몇 번으로 들어왔는가."""
    place: int
    """플레이어의 최종 순위. 1이면 우승이다."""
    field: int
    """참가 인원. 순위를 읽으려면 분모가 필요하다."""
    eliminated_by_player: int
    """플레이어가 떨어뜨린 사람 수."""

    @property
    def won(self) -> bool:
        return self.place == 1
