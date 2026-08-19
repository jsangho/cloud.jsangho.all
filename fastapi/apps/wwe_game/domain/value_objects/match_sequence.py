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
    # ── 여기부터 §3-D81 (모멘텀 타임라인) ──
    MOVE = "move"
    """기술 하나가 들어갔다. 흐름이 그쪽으로 기운다."""
    REVERSAL = "reversal"
    """받아넘겼다 — **흐름이 뒤집히는 자리**다."""
    SIGNATURE = "signature"
    """시그니처가 나왔다 (§3-D91). **끝내지는 못하지만 그 사람의 것**인 수다.

    평범한 수와 피니셔 사이의 자리다 — 이게 없으면 경기가 *"이런저런 기술 → 갑자기
    피니셔"*로 끝나고, 그러면 "이제 끝나나?" 하는 순간이 없다.
    """
    NEARFALL = "nearfall"
    """투 카운트. 니어폴이 몇 번 나왔는지가 그 밤의 별점을 읽는 근거가 된다(§3-D56)."""
    KICKOUT = "kickout"
    """킥아웃. 니어폴 뒤에만 온다."""
    FINISHER = "finisher"
    """피니셔가 들어갔다 (§3-D88). **내 기술의 이름이 여기 실린다.**"""


@dataclass(frozen=True)
class MatchBeat:
    kind: BeatKind
    name: str
    number: int = 0
    """입장 순번. `ENTER`에만 채워진다 — 럼블의 번호이자 챔버의 포드 순서다."""
    by: str | None = None
    """누가 탈락시켰는가. `ELIMINATE`에만 채워진다."""
    momentum: int = 50
    """그 순간 **플레이어 쪽으로 기운 정도**(0~100) — §3-D81.

    50이 팽팽함이고 100이 완전한 우세다. 레슬링에서 위치는 정보가 아니라 흐름이
    정보이므로(§3-D81), 이 한 값이 2D 링을 대신한다.

    **판정이 아니다.** 승패는 이미 정해진 뒤에 이 줄이 그려진다 — 흐름이 승패를
    만들면 같은 시드가 다른 결과를 내게 된다(§3-D4).
    """


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
