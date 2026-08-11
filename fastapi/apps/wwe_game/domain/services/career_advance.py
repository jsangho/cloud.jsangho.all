"""진행 루프 — '다음' 한 번 (하네스 §3-D2·D5·D17 · §5 · T8).

**순수 함수다.** 저장도 서술도 하지 않는다 — 세이브를 받아 다음 세이브와 주차 리포트를
돌려줄 뿐이다. 유스케이스(`career_interactor`)가 이걸 부르고, 결과에 문장을 붙이고,
한 번에 저장한다(§3-D6).

이렇게 가른 이유: 로그인 플레이와 체험판이 **같은 규칙**을 써야 하는데(§11-25), 둘의
차이는 세이브를 어디서 읽고 어디에 쓰는가뿐이다. 규칙을 순수 함수로 떼어 두면 그 공유가
저절로 된다 — 유스케이스가 규칙을 품고 있으면 언젠가 한쪽만 고쳐진다.

한 주차의 순서는 이렇다.

1. `simulate_week` — 무슨 일이 일어났는지 계산
2. `apply_week` — 세이브에 반영 (이벤트 추첨도 여기서 일어난다)
3. `track_release` · `track_decline` — 방출·부진 누적 갱신
4. `close_if_ended` — 은퇴 조건 판정

대회가 연 4회에서 13회로 늘어(§3-D21-1) **멈춤은 대형 대회에서만** 일어난다. 전부
끊으면 클릭이 세 배가 되고, 멈춤은 "보고 싶은 것"일 때만 의미가 있다.

3번을 2번 뒤에 두는 이유: 누적은 **반영된 상태**를 봐야 한다. 반영 전 상태로 세면 그 주차의
결장·패배가 한 주 늦게 반영돼, 유예 기간이 실제보다 한 주씩 길어진다.
"""

from __future__ import annotations

from wwe_game.domain.constants import career_rules as rules
from wwe_game.domain.entities.career_run import CareerRun
from wwe_game.domain.services import career_end
from wwe_game.domain.services.week_simulation import apply_week, simulate_week
from wwe_game.domain.value_objects.advance_outcome import (
    AdvanceOutcome,
    StepMode,
    StopReason,
)
from wwe_game.domain.value_objects.week_report import WeekKind, WeekReport

MAX_WEEKS_PER_ADVANCE = 156
"""한 번의 '다음'이 갈 수 있는 최대 **주** 수 — 3년 (§3-D5).

틱이 아니라 주로 세는 이유: `yearly`의 한 틱이 이미 52주라, 틱으로 상한을 걸면 모드마다
상한의 뜻이 달라진다.

**이벤트가 마른 구간이 있다.** 예산을 다 쓴 커리어는 멈출 이유를 못 만나 한 번의 호출이
1560주를 돌 수 있고, 그러면 응답에 리포트 1560개가 실린다. 상한은 그걸 막는다. 3년으로
잡은 근거: 이벤트 간격이 가장 성긴 `yearly`가 52주쯤이므로 평소에는 걸리지 않는다.
"""


def stops_at_ple(run: CareerRun) -> bool:
    """이 모드가 대회에서 진행을 끊는지 (§3-D17).

    굵은 틱을 쓰는 모드는 끊지 않는다 — `yearly`의 한 틱(52주)에는 대회가 열세 번
    들어 있어 끊으면 틱이 완성되지 않는다.
    """
    return run.mode.weeks_per_tick <= rules.PLE_STOP_MAX_TICK_WEEKS


def advance(
    run: CareerRun,
    *,
    step: StepMode = StepMode.AUTO,
    max_weeks: int = MAX_WEEKS_PER_ADVANCE,
) -> AdvanceOutcome:
    """멈춤 조건을 만날 때까지 주차를 돌린다. **반드시 유한하다**(§3-D5).

    끝난 세이브를 넘기면 `RunNotActiveError`, 대기 이벤트가 있으면 한 주도 가지 않고
    `EVENT`로 돌아온다 — 답하기 전에는 진행이 막힌다(§3-D2). 막힌 것을 예외로 만들지
    않는 이유: 화면이 물어보는 것은 "지금 어디에 서 있나"이고, 그 답이 곧 `stop_reason`이다.
    유스케이스는 이 값을 보고 409로 바꾼다.
    """
    run.require_active()
    if run.is_blocked:
        return AdvanceOutcome(run=run, stop_reason=StopReason.EVENT)
    if max_weeks < 1:
        raise ValueError(f"최대 주차는 1 이상이어야 합니다: {max_weeks}")

    reports: list[WeekReport] = []
    limit = min(max_weeks, run.weeks_remaining)
    while True:
        report = simulate_week(run)
        run = apply_week(run, report)
        run = career_end.track_decline(career_end.track_release(run))
        run = career_end.close_if_ended(run)
        reports.append(report)

        stop = _stop_reason(run, report, step, len(reports), limit)
        if stop is not None:
            return AdvanceOutcome(run=run, reports=tuple(reports), stop_reason=stop)


def _stop_reason(
    run: CareerRun,
    report: WeekReport,
    step: StepMode,
    advanced: int,
    limit: int,
) -> StopReason | None:
    """이 주차에서 멈출 이유. 없으면 None.

    순서가 곧 우선순위다 — **끝난 커리어가 가장 앞이다.** 종료와 이벤트가 같은 주에
    겹치면 이벤트는 답할 사람이 없다(`CareerRun.ended`가 대기 이벤트를 지운다).
    """
    if not run.is_active:
        return StopReason.ENDED
    if run.is_blocked:
        return StopReason.EVENT
    if report.is_major_show and stops_at_ple(run):
        return StopReason.PLE
    if report.kind is WeekKind.OFF and not run.condition.is_injured:
        # 결장 주차는 부상 주차와 같은 말이다(`week_kind_of`). 그 주차를 끝으로
        # 몸이 나았다면 **여기가 복귀 지점이다** (§3-D37).
        return StopReason.RECOVERED
    if step is StepMode.TICK and advanced >= run.mode.weeks_per_tick:
        return StopReason.TICK
    if advanced >= limit:
        return StopReason.MAX_WEEKS
    return None
