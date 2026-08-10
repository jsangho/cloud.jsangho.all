"""은퇴 4조건 (하네스 §3-D16).

| 조건 | 판정 | 성격 |
|---|---|---|
| 50세 도달 | 여기 | 만기 — 항상 도달 가능한 종착점 |
| 중대 부상 | 여기 | 한 번의 선택으로 끝난다 |
| 35세+ 부진 | 여기 | 반년 유예를 거쳐 밀려난다 |
| **방출** | 여기 | 평판이 바닥나면 잘린다. 나이 제한 없음 |
| 플레이어 선택 | `DELETE /runs/{id}` | 언제든 스스로 닫는다 |

**부진과 방출은 다른 실패다.** 부진은 *관중이 안 찾아서* 밀려나는 것이라 인기도·경기력을
보고, 방출은 *단체가 못 참아서* 잘리는 것이라 백스테이지 평판을 본다. 부진은 35세부터지만
방출은 신인에게도 온다.

두 판정 모두에서 **인기도가 우선한다** — 입지 계산에서 인기도가 경기력의 세 배 무게를
갖고, 방출은 인기가 일정 수준을 넘으면 아예 면제된다. 돈이 되면 참아준다.
"""

from __future__ import annotations

from wwe_game.domain.constants import career_rules as rules
from wwe_game.domain.constants.career_clock import CAREER_WEEKS
from wwe_game.domain.entities.career_run import CareerRun, EndReason
from wwe_game.domain.value_objects.title import Brand


def standing_of(run: CareerRun) -> float:
    """단체 안에서의 입지. 인기도 ×1.5 + 경기력 ×0.5 − 마모 ×0.5."""
    return (
        run.stats.popularity * rules.DECLINE_POPULARITY_WEIGHT
        + run.stats.in_ring * rules.DECLINE_IN_RING_WEIGHT
        - run.condition.wear * rules.DECLINE_WEAR_WEIGHT
    )


def is_declining(run: CareerRun) -> bool:
    """지금 이 주차에 입지가 임계 아래인지. 누적은 세지 않는다."""
    return (
        run.age >= rules.DECLINE_CHECK_AGE
        and standing_of(run) < rules.DECLINE_THRESHOLD
    )


def track_decline(run: CareerRun) -> CareerRun:
    """부진 누적을 갱신한다. 입지를 회복하면 0으로 되돌아간다.

    되돌아가게 두는 이유: 유예가 누적만 되면 서른다섯 이후 한 번이라도 흔들린 선수는
    결국 전부 밀려난다. 살아 돌아올 길이 있어야 선택에 의미가 생긴다.
    """
    weeks = run.decline_weeks + 1 if is_declining(run) else 0
    return run if weeks == run.decline_weeks else run.evolve(decline_weeks=weeks)


def is_at_release_risk(run: CareerRun) -> bool:
    """평판이 바닥이고, 그걸 덮을 만큼 인기가 있지도 않은 상태."""
    # **육성 브랜드에 있는 동안은 자르지 않는다** (2026-08-10 사용자 결정).
    # §3-D24가 말하는 방출은 "단체가 못 참아서 미드카더를 잘라내는 것"이다. NXT는
    # 다듬는 자리라 평판이 흔들리는 게 정상이고, 여기서 자르면 1년차 신인이 즉사한다 —
    # 실측에서 과감한 플레이가 0.8년 만에 끝났다.
    if run.brand is Brand.NXT:
        return False
    return (
        run.stats.backstage < rules.RELEASE_BACKSTAGE_FLOOR
        and run.stats.popularity < rules.RELEASE_POPULARITY_SHIELD
    )


def release_grace_weeks(run: CareerRun) -> int:
    """이미 선을 넘은 적이 있으면 인내가 절반이다."""
    if rules.RELEASE_TRIGGER_FLAGS & set(run.flags):
        return max(1, rules.RELEASE_GRACE_WEEKS // rules.RELEASE_FLAG_GRACE_DIVISOR)
    return rules.RELEASE_GRACE_WEEKS


def track_release(run: CareerRun) -> CareerRun:
    """방출 위험 누적을 갱신한다. 평판을 회복하면 0으로 되돌아간다."""
    weeks = run.release_weeks + 1 if is_at_release_risk(run) else 0
    return run if weeks == run.release_weeks else run.evolve(release_weeks=weeks)


def check_end(run: CareerRun) -> EndReason | None:
    """끝났으면 이유를, 아니면 None.

    순서가 곧 우선순위다 — 만기가 나머지 셋보다 앞선다. 1560주에 도달한 커리어는
    무슨 상태였든 완주한 것으로 본다. 방출이 부진보다 앞서는 이유: 잘린 선수는
    밀려날 기회조차 없다.
    """
    if not run.is_active:
        return None
    if run.week >= CAREER_WEEKS:
        return EndReason.AGE_50
    if run.condition.is_career_ending:
        return EndReason.INJURY
    if run.release_weeks >= release_grace_weeks(run):
        return EndReason.RELEASED
    if run.decline_weeks >= rules.DECLINE_GRACE_WEEKS:
        return EndReason.DECLINE
    return None


def close_if_ended(run: CareerRun) -> CareerRun:
    """종료 조건을 만났으면 닫고, 아니면 그대로 돌려준다."""
    reason = check_end(run)
    return run.ended(reason) if reason is not None else run
