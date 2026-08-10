"""모드 네 종 (하네스 §3-D15).

**모드는 커리어 길이를 정하지 않는다.** 넷 다 1560주다. 정하는 것은 해상도 둘뿐이다 —
한 틱이 몇 주인지, 커리어 전체에 이벤트를 몇 번 뿌릴지.

`MONTHLY`는 달력의 달이 아니라 **4주**다. 달력 달(30.4일)로는 1560주가 정수로 나뉘지
않아 "52주마다 한 살"이 어긋난다. 그래서 틱 수가 360이 아니라 390이다.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from wwe_game.domain.constants.career_clock import CAREER_WEEKS
from wwe_game.domain.exceptions import UnknownGameModeError


class GameModeCode(StrEnum):
    YEARLY = "yearly"
    QUARTERLY = "quarterly"
    MONTHLY = "monthly"
    WEEKLY = "weekly"


@dataclass(frozen=True)
class GameMode:
    code: GameModeCode
    weeks_per_tick: int
    event_budget: int
    """커리어 전체에 뿌릴 이벤트 총량. 매 주차 추첨 확률이 여기서 파생된다."""
    guest_allowed: bool
    """비로그인 체험판 허용 여부. 틱이 적어 상태가 브라우저에 들어가는 모드만 True (§3-D8)."""

    @property
    def total_ticks(self) -> int:
        return CAREER_WEEKS // self.weeks_per_tick

    @property
    def weeks_per_event(self) -> float:
        """이벤트 사이 평균 간격(주). 밀도를 눈으로 확인할 때 쓴다."""
        return CAREER_WEEKS / self.event_budget


GAME_MODES: dict[GameModeCode, GameMode] = {
    GameModeCode.YEARLY: GameMode(GameModeCode.YEARLY, 52, 30, guest_allowed=True),
    GameModeCode.QUARTERLY: GameMode(
        GameModeCode.QUARTERLY, 13, 160, guest_allowed=True
    ),
    GameModeCode.MONTHLY: GameMode(GameModeCode.MONTHLY, 4, 200, guest_allowed=False),
    GameModeCode.WEEKLY: GameMode(GameModeCode.WEEKLY, 1, 320, guest_allowed=False),
}

# 틱이 1560주를 정확히 나눠야 마지막 틱이 잘리지 않는다. 나눠떨어지지 않는 값을 넣으면
# 커리어가 1560주 전에 끝나거나 넘어가므로, 임포트 시점에 터뜨린다 (§4-16·17).
for _mode in GAME_MODES.values():  # pragma: no cover - 임포트 시 구조 검증
    if CAREER_WEEKS % _mode.weeks_per_tick != 0:
        raise RuntimeError(
            f"{_mode.code}: {CAREER_WEEKS}주가 {_mode.weeks_per_tick}주 틱으로 "
            "정확히 나뉘지 않습니다"
        )


def game_mode_of(code: str) -> GameMode:
    """모드 코드를 값 객체로. 없는 코드는 400으로 이어진다."""
    try:
        return GAME_MODES[GameModeCode(code)]
    except ValueError as exc:
        raise UnknownGameModeError(f"없는 모드입니다: {code}") from exc


def guest_modes() -> tuple[GameMode, ...]:
    """비로그인이 고를 수 있는 모드. `/guest/*`가 이 목록으로 400을 판정한다."""
    return tuple(m for m in GAME_MODES.values() if m.guest_allowed)
