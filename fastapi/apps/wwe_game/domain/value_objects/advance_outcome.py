"""'다음' 한 번의 형태 (하네스 §3-D2·D17 · §5).

**app이 아니라 도메인에 있다.** 진행 루프가 순수 함수라(§3-D1) 멈춘 이유를 도메인이
직접 정하고, DTO는 그 값을 그대로 실어 나른다. 같은 열거형을 두 레이어에 두면 값이
갈릴 때 어느 쪽이 맞는지 알 수 없다 — 도메인이 원본이다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from wwe_game.domain.entities.career_run import CareerRun
from wwe_game.domain.value_objects.week_report import WeekReport


class StepMode(StrEnum):
    """'다음' 한 번이 얼마나 가는지 (§3-D17)."""

    AUTO = "auto"
    """이벤트·PLE·종료를 만날 때까지. 기본값이다 — `weekly`가 클릭 1560번이 되지 않게."""
    TICK = "tick"
    """정확히 `weeks_per_tick` 주만. 촘촘히 보고 싶을 때 쓴다."""


class StopReason(StrEnum):
    """진행이 멈춘 이유. **어디서 멈췄는지가 곧 화면의 상태다.**"""

    EVENT = "event"
    """대기 이벤트를 만났다 — 답하기 전에는 더 못 간다 (§3-D2)."""
    OFFER = "offer"
    """재계약 협상이 열렸다 (§3-D84). 만료 주차에 서면 답해야 간다.

    §3-D80의 목표와 나란한 세 번째 멈춤이다 — 셋 다 "먼저 정하는 것"이고,
    그래서 §11-1이 *"'다음'과 선택만으로 끝까지"*로 바뀌었다.
    """
    GOAL = "goal"
    """새 분기가 열렸다 — **이번 석 달에 무엇을 걸지** 정해야 간다 (§3-D80).

    이벤트와 같은 자리를 쓰되 성격이 반대다: 이벤트는 벌어진 일에 답하는 것이고
    이것은 **먼저 정하는 것**이다. 그 하나 때문에 만든 멈춤이다.
    """
    PLE = "ple"
    """대형 대회에서 한 번 끊었다. 굵은 틱을 쓰는 모드는 끊지 않는다 (§3-D17)."""
    ENDED = "ended"
    """커리어가 끝났다 (§3-D16 은퇴 5조건)."""
    RECOVERED = "recovered"
    """부상에서 돌아왔다 (§3-D37).

    부상 구간(평균 10주 · 최장 30주)은 **한 번의 '다음'으로 통째로 흘러간다** — 그
    사이에 할 수 있는 일이 없기 때문이다. 대신 복귀하는 주차에서 한 번 끊는다:
    안 끊으면 다음 이벤트까지 그대로 지나가 **언제 돌아왔는지가 로그에 묻힌다.**
    """
    TICK = "tick"
    """요청한 만큼 갔다 (`step: tick`)."""
    MAX_WEEKS = "max_weeks"
    """안전 상한에 걸렸다 (§3-D5). **버그가 아니라 계약이다** — 이벤트가 마른 구간에서
    한 번의 호출이 1560주를 돌지 않게 막는다."""
    READY = "ready"
    """진행하지 않았다 — 막 시작했거나 조회만 했다.

    시작 화면과 "한 틱 갔다"를 같은 값으로 두면 프론트가 둘을 구분하지 못한다.
    """


@dataclass(frozen=True)
class AdvanceOutcome:
    """진행 루프의 결과. **서술은 없다** — 문장은 어댑터가 나중에 붙인다(§3-D3)."""

    run: CareerRun
    reports: tuple[WeekReport, ...] = field(default_factory=tuple)
    stop_reason: StopReason = StopReason.READY

    @property
    def weeks_advanced(self) -> int:
        return len(self.reports)
