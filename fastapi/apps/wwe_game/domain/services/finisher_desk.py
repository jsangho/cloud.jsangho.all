"""피니셔를 바꾼다 (하네스 §3-D88).

§3-D85(가방) · §3-D86(시비)와 같은 **상시 행동**이다 — 안 바꾸고 '다음'을 눌러도
되고, `StopReason`을 더하지 않는다.

## 값은 시간이다

돈을 물리지 않는다. §13-Q13이 막는 것("돈이 스탯을 산다")에 걸리지는 않지만, 피니셔는
판정에 안 닿으므로 **돈을 받으면 그냥 돈만 사라지는 버튼**이 된다. 그건 소비처가
아니라 벌금이다.

대신 **한 번 바꾸면 한동안 못 바꾼다**(`COOLDOWN_WEEKS`). 실제로도 피니셔는 커리어에
두어 번 바뀌는 것이고, 매주 바꿀 수 있으면 그건 정체성이 아니라 설정 메뉴다.

## 판정에 한 톨도 안 닿는다

승패·별점·부상 어느 것도 안 본다. 바뀌는 것은 그 경기가 **어떻게 끝났다고 적히는가**
하나다(§3-D88). 그래서 밸런스를 재지 않아도 되는 유일한 상시 행동이다.
"""

from __future__ import annotations

from wwe_game.domain.constants.career_clock import CAREER_WEEKS
from wwe_game.domain.entities.career_run import CareerRun
from wwe_game.domain.exceptions import CannotChangeFinisherError
from wwe_game.domain.value_objects.finisher import (
    CUSTOM_CODE,
    Finisher,
    custom,
    options_for,
    resolve,
)
from wwe_game.domain.value_objects.quarter_goal import QUARTER_WEEKS

COOLDOWN_WEEKS = QUARTER_WEEKS
"""바꾸고 다시 바꾸기까지 기다리는 주차 — **한 분기** (2026-08-14 사용자 결정).

§3-D80의 분기와 같은 리듬이다. 매주 바꿀 수 있으면 정체성이 아니라 설정 메뉴가 되고,
한 해로 묶으면 데뷔 때의 기본기를 너무 오래 들고 간다.

**데뷔 직후에도 이 값이 걸린다.** `finisher_week`가 0이면 아직 한 번도 안 바꾼
것이고, 그때 남은 주차는 `COOLDOWN_WEEKS - run.week`가 된다 — 곧 *"첫 분기가 지나면
바꿀 수 있다"*가 같은 식 하나로 나온다.
"""


def current(run: CareerRun) -> Finisher:
    """지금 쓰는 피니셔. 안 골랐으면 **수플렉스**다."""
    return resolve(run.finisher, run.finisher_name, run.identity.play_style)


def options(run: CareerRun) -> tuple[Finisher, ...]:
    """고를 수 있는 피니셔들 — 기본기(수플렉스) + 내 계열 전부.

    **지금 쓰는 것도 목록에 남는다** — 무엇을 쓰고 있는지가 목록에서 읽혀야 한다."""
    return options_for(run.identity.play_style)


HOLD_QUARTER = COOLDOWN_WEEKS
HOLD_YEAR = 52
"""다시 묻기까지의 간격 — 한 분기 · 한 해 (2026-08-14 사용자 요청)."""

HOLD_FOREVER = CAREER_WEEKS + 1
"""**평생 쓴다.** 커리어 끝 너머의 주차라 다시 묻는 날이 오지 않는다.

따로 불리언을 두지 않는 이유: "언제 다시 물을 것인가" 하나로 셋이 전부 표현되고,
칸이 늘면 그 둘을 영원히 맞춰 줘야 한다(§3-D29가 파생값을 안 저장한 것과 같은 결).
"""


def weeks_until_change(run: CareerRun) -> int:
    """다시 바꿀 수 있을 때까지 남은 주차. 0이면 지금 바꿀 수 있다.

    **아직 아무것도 안 정했으면 첫 분기 규칙이다** — 데뷔(0주차)부터 센다.
    """
    if run.finisher_ask_week <= 0:
        return max(0, COOLDOWN_WEEKS - run.week)
    return max(0, run.finisher_ask_week - run.week)


def is_settled(run: CareerRun) -> bool:
    """평생 쓰기로 못 박았는가. **화면이 '바꾸기'를 아예 안 낸다.**"""
    return run.finisher_ask_week > CAREER_WEEKS


def hold(run: CareerRun, weeks: int) -> CareerRun:
    """지금 것을 그대로 쓰고 **다시 묻는 날만 미룬다** (2026-08-14 사용자 요청).

    **바꾸는 것만이 선택이 아니다.** 분기마다 자리가 열리므로 화면이 계속 물어보게
    되는데, "이대로 간다"도 한 번의 결정이다.

    `pick`이 같은 코드를 거절하는 것과 어긋나지 않는다: 저쪽은 **바꾸려다 같은 것을
    고른 실수**이고 이쪽은 **안 바꾸겠다는 선언**이다.
    """
    _require_changeable(run)
    return run.evolve(
        finisher_week=run.week,
        finisher_ask_week=min(HOLD_FOREVER, run.week + max(1, weeks)),
    )


def can_change(run: CareerRun) -> bool:
    return run.is_active and weeks_until_change(run) == 0


def pick(run: CareerRun, code: str) -> CareerRun:
    """목록에서 고른다 (§3-D88) — 기존 선수들이 쓰는 기술 쪽이다.

    **같은 것을 다시 고르는 것은 거절한다** — 쿨다운만 태우고 아무것도 안 바뀐다.
    """
    _require_changeable(run)
    chosen = resolve(code, "", run.identity.play_style)
    if chosen.code != code:
        raise CannotChangeFinisherError(f"고를 수 없는 피니셔입니다: {code}")
    if chosen.code == current(run).code:
        raise CannotChangeFinisherError("이미 그 피니셔를 쓰고 있습니다.")
    return run.evolve(
        finisher=chosen.code,
        finisher_name="",
        finisher_week=run.week,
        finisher_ask_week=run.week + HOLD_QUARTER,
    )


def name_it(run: CareerRun, name: str) -> CareerRun:
    """이름을 직접 짓는다 (§3-D88).

    검증은 값 객체(`finisher.custom`)가 한다 — 링네임과 같은 자리다(§3-D12).
    """
    _require_changeable(run)
    named = custom(name)
    if named.name == current(run).name:
        raise CannotChangeFinisherError("이미 그 이름을 쓰고 있습니다.")
    return run.evolve(
        finisher=CUSTOM_CODE,
        finisher_name=named.name,
        finisher_week=run.week,
        finisher_ask_week=run.week + HOLD_QUARTER,
    )


def _require_changeable(run: CareerRun) -> None:
    if not can_change(run):
        raise CannotChangeFinisherError("지금은 피니셔를 바꿀 수 없습니다.")
