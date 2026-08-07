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
from wwe_game.domain.value_objects.title import Title


class WeekKind(StrEnum):
    WEEKLY_SHOW = "weekly_show"
    """주간 TV — 경기가 있는 주차."""
    PROMO = "promo"
    """주간 TV — 경기 없이 대립을 쌓는 주차 (스펙: 빌드업으로 1주를 써도 된다)."""
    PLE = "ple"
    """대형 대회. **반드시 경기가 있다** — 없으면 그 주차는 열리지 않는다."""
    OFF = "off"
    """부상 회복 중이라 나오지 않는 주차."""


class OutcomeKind(StrEnum):
    WIN = "win"
    LOSS = "loss"
    DRAW = "draw"


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
    narration: str = ""

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
