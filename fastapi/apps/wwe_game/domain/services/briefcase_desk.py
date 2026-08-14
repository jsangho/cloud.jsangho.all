"""가방을 언제 쓸까 (하네스 §3-D85).

§3-D36이 가방을 만들 때 `CASH_IN_PENDING` 표식을 함께 두었고 `week_simulation`이
그것을 읽고 있었다 — **그런데 아무도 세우지 않았다.** 52주(`BRIEFCASE_WEEKS`)가
지나면 규칙이 알아서 현금화했고, 머니 인 더 뱅크의 전부인 *"언제 뛰어드느냐"*가
통째로 자동이었다. 죽어 있던 표식을 플레이어에게 준다.

## 멈추지 않는다 — 이것이 §3-D80·D84와 다른 점이다

목표(§3-D80)와 협상(§3-D84)은 **멈춤**이다. 답하기 전에는 한 주도 안 간다.
여기는 반대다: 가방을 들고 있어도 진행은 그대로 흐르고, 안 쓰고 '다음'을 눌러도
된다. **`StopReason`을 더하지 않는 이유가 그것이다.**

멈춤을 더하면 FM의 '다음'과 반대로 간다. 저쪽은 진행을 막는 것이 아니라 **할 수
있는 일을 늘어놓고 마지막에 누르게** 한다 — 안 하고 눌러도 되지만 그러면 남는 게
없다. §11-1이 클릭 수를 걱정하고 §3-D37이 "열두 주 결장이 클릭 한두 번"을 지키는
이 게임에서, 상시 행동은 멈춤보다 이 기준에 맞는다.

## 시계가 곧 긴장이다

미루면 이득이 커질 수 있지만(챔피언이 바뀌고 내 인기가 오른다), 52주가 차면
**규칙이 대신 써 버린다** — 그때가 최악의 타이밍일 수 있다. 그 시계는 §3-D36이
이미 놓아 두었고, 여기서는 그것을 화면에 보이게만 한다.

## 챔피언의 값은 내보내지 않는다

화면에 나가는 것은 **이름과 남은 주차**뿐이다. 챔피언의 인기도를 함께 내면 그것이
곧 승률의 힌트가 되고, 그 순간 "지금 쓸까"는 판단이 아니라 계산이 된다(§11-14).
"""

from __future__ import annotations

from wwe_game.domain.constants import career_rules as rules
from wwe_game.domain.constants.career_flags import CASH_IN_PENDING
from wwe_game.domain.entities.career_run import CareerRun
from wwe_game.domain.exceptions import CannotCashInError
from wwe_game.domain.services import championship
from wwe_game.domain.value_objects.title import Title


def holds(run: CareerRun) -> bool:
    """가방을 들고 있는가. 상태는 `briefcase_week`가 든다 (표식이 아니다)."""
    return run.is_active and run.briefcase


def is_pending(run: CareerRun) -> bool:
    """이미 "쓴다"고 정했는가. **정한 뒤에는 무를 수 없다** — 다음 경기 주차에 걸린다."""
    return CASH_IN_PENDING in run.flags


def weeks_left(run: CareerRun) -> int:
    """자동 현금화까지 남은 주차. 안 들고 있으면 0이다.

    **음수가 되지 않게 자른다** — 만료 주차를 부상으로 건너뛰면 지나칠 수 있고,
    그때 화면에 음수가 뜨면 "이미 늦었다"로 읽힌다.
    """
    if not holds(run):
        return 0
    return max(0, rules.BRIEFCASE_WEEKS - (run.week - run.briefcase_week))


def target_title(run: CareerRun) -> Title | None:
    """가방이 겨누는 벨트 — 소속 브랜드의 월드 벨트 (§3-D36).

    **여기서 고르지 않는다.** 규칙(`week_simulation`)이 쓰는 것과 같은 함수를 불러
    화면과 판정이 같은 벨트를 가리키게 한다.
    """
    if not run.is_signed:
        return None
    return championship.world_title_of(run)


def can_cash_in(run: CareerRun) -> bool:
    """지금 뛰어들 수 있는가.

    **무소속은 못 쓴다** (§3-D50) — 단체의 벨트이고 계약 해지가 이미 반납시켰다.
    **이미 그 벨트를 감고 있어도 못 쓴다** — 규칙이 그 경우 도전을 만들지 않으므로
    (`week_simulation._title_shot_for`), 여기서 막지 않으면 표식만 세우고 아무 일도
    안 일어난 채 가방이 소멸한다.
    """
    if not holds(run) or is_pending(run):
        return False
    title = target_title(run)
    return title is not None and title not in run.titles_held


def cash_in(run: CareerRun) -> CareerRun:
    """가방을 쓰기로 한다 (§3-D85).

    **표식만 세운다.** 타이틀전을 여기서 걸지 않는 이유는 §3-D36이 정한 그대로다 —
    경기를 세우는 것은 주차 시뮬의 일이고, 이 신호는 **쓰일 때까지 남는다**(다음 주에
    부상으로 결장해도 결정이 사라지지 않는다).
    """
    if not can_cash_in(run):
        raise CannotCashInError("지금은 가방을 쓸 수 없습니다.")
    return run.evolve(flags=run.flags | {CASH_IN_PENDING})
