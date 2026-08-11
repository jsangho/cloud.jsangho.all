"""자동 진행 한 주차의 결과 (하네스 §5).

**선택지가 없다.** 플레이어가 개입하는 지점은 이벤트뿐이고, 주차 리포트는 그냥 일어난
일이다. 한 번의 '다음'이 이 리포트를 여러 개 쌓는다.

`narration`은 비어 있다 — 문장은 T6의 `RuleNarrator`가 채운다. 판정 코드 안에서 문장을
만들지 않는다(§4-9).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from wwe_game.domain.constants.ple_calendar import PleShow
from wwe_game.domain.value_objects.condition import InjuryGrade
from wwe_game.domain.value_objects.match_kind import MatchKind
from wwe_game.domain.value_objects.match_sequence import MatchSequence
from wwe_game.domain.value_objects.title import Title


class WeekKind(StrEnum):
    WEEKLY_SHOW = "weekly_show"
    """주간 TV — 경기가 있는 주차."""
    PROMO = "promo"
    """주간 TV — 경기 없이 대립을 쌓는 주차 (스펙: 빌드업으로 1주를 써도 된다)."""
    PLE = "ple"
    """대형 대회. **반드시 경기가 있다** — 없으면 그 주차는 열리지 않는다."""
    SPECIAL = "special"
    """분기별 특별 방송(SNME) — **PLE와 주간 TV 사이** (§3-D21-2).

    경기는 반드시 있지만 대회는 아니다. 타이틀전 확률도 마모도 그 사이에 놓이고,
    진행은 여기서 멈추지 않는다.
    """
    OFF = "off"
    """부상 회복 중이라 나오지 않는 주차."""


class OutcomeKind(StrEnum):
    WIN = "win"
    LOSS = "loss"
    DRAW = "draw"


class TitleShotSource(StrEnum):
    """자격을 건너뛰고 타이틀전에 서는 두 경로 (§3-D36)."""

    EARNED = "earned"
    """럼블·챔버 우승으로 얻은 레슬매니아 도전권."""
    BRIEFCASE = "briefcase"
    """머니 인 더 뱅크 가방을 썼다."""


class CallUpReason(StrEnum):
    """콜업이 **어떻게** 왔는지. 남는 인기도가 갈리고, 서술도 갈린다."""

    EARNED = "earned"
    """문턱을 넘어서 올라갔다 — 실력으로 부른 것."""
    EMERGENCY = "emergency"
    """메인 로스터의 부상 공백을 메우러 대타로 올라갔다 (§3-D22-1).

    이벤트 카드에서 플레이어가 **수락했을 때만** 생긴다. 준비가 덜 된 채 올라가지만
    그 대타 출전 자체가 생중계 화제라 인기도가 덜 깎인다.
    """


@dataclass(frozen=True)
class WeekReport:
    week: int
    kind: WeekKind
    result: OutcomeKind | None = None
    """`OFF` 주차에는 경기가 없어 None이다."""
    stat_delta: dict[str, int] = field(default_factory=dict)
    wear_delta: int = 0
    injury: InjuryGrade | None = None
    """이 주차에 새로 입은 부상. 회복은 여기 안 나온다."""
    injury_weeks: int = 0
    show: PleShow | None = None
    """그 주차의 대형 대회. PLE 주차에만 채워진다 (§3-D21-1).

    이름을 리포트에 담는 이유: 서술이 "대형 대회"가 아니라 **"레슬매니아"**라고 쓸 수
    있어야 하고, 급에 따라 판정이 갈리므로 화면도 그걸 알아야 한다.
    """
    title_at_stake: Title | None = None
    """이 주차가 타이틀전이면 걸린 벨트. 대형 대회에서만 생긴다."""
    title_defended: bool = False
    """이미 들고 있던 벨트의 방어전이었는지. 도전과 방어는 같은 경로를 탄다."""
    call_up: CallUpReason | None = None
    """이 주차에 NXT에서 메인 로스터로 올라갔다면 그 경로. 아니면 None."""
    draft_night: bool = False
    """이 주차에 **드래프트가 열렸는지**. 브랜드가 실제로 바뀌었는지가 아니다.

    이동 굴림은 `apply_week`이 `championship.draft()`로 돌리고, 평소 확률은 16%다.
    이름이 `drafted`였을 때 서술이 "브랜드가 바뀌었다"로 나가 **다섯 번 중 네 번은
    사실이 아닌 문장**이 됐다. 필드가 약속하는 것과 담는 것을 맞춘다.
    """
    match_kind: MatchKind | None = None
    """그 주차 경기의 형식. 경기 없는 주차는 None이다 (§3-D32).

    **대회의 시그니처 경기는 반드시 열린다** — 로열럼블 없는 로열럼블은 그냥 1월
    대회일 뿐이다.
    """
    opponent: str | None = None
    """그 주차에 붙은 상대. 경기가 없는 주차는 None이다.

    **대립 상대가 있으면 그 사람이 먼저다** — 이야기가 쌓인 상대와 붙는 것이 대립의
    존재 이유다. 없으면 급이 맞는 명부에서 뽑는다.
    """
    cursed: bool = False
    """이 경기가 **댄하우젠의 저주로 진 경기**인지 (2026-08-10 사용자 지시 4번).

    `result`만으로는 서술이 평범한 패배와 구분할 수 없다. 저주가 소진됐다는 신호이기도
    해서 `apply_week`이 이 값을 보고 표식을 지운다.
    """
    title_shot_from: TitleShotSource | None = None
    """이 타이틀전이 **자격이 아니라 권리로** 잡혔다면 그 출처 (§3-D36).

    평소의 타이틀전은 인기도가 자격을 주고 굴림이 정한다. 이 둘은 그 과정을 건너뛴다 —
    화면도 그렇게 말해야 한다: 같은 "타이틀전"이라도 럼블을 이겨서 선 자리와 어쩌다
    걸린 자리는 다른 사건이다.
    """
    sequence: MatchSequence | None = None
    """탈락·순차 입장이 있는 경기의 진행 순서 (§3-D34). 그 밖의 경기는 None이다.

    **판정을 담지 않는다** — 승패는 `result`가 이미 들고 있고, 이쪽은 그것과 어긋나지
    않게 짜인 서술이다.
    """
    narration: str = ""

    @property
    def is_big_match_night(self) -> bool:
        """대회든 특별 방송이든 **경기가 보장된 밤**인지."""
        return self.kind in (WeekKind.PLE, WeekKind.SPECIAL)

    @property
    def is_major_show(self) -> bool:
        return self.show is not None and self.show.is_major

    @property
    def called_up(self) -> bool:
        return self.call_up is not None

    @property
    def had_match(self) -> bool:
        return self.result is not None

    @property
    def is_title_match(self) -> bool:
        return self.title_at_stake is not None
