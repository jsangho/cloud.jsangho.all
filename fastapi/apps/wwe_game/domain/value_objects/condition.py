"""부상과 마모 (하네스 §3-D16).

은퇴 4조건 중 둘이 여기에 달려 있다 — "35세+ 스탯 임계치 미달"이 읽는 값이 `wear`이고,
"중대 부상"이 `CAREER_ENDING` 등급이다.

`wear`가 `WrestlerStats`가 아니라 여기 있는 이유: 부상 굴림과 같이 움직인다. 무리한
선택은 `wear`를 올리고, 높은 `wear`는 다음 부상 확률을 올린다. 둘을 갈라 놓으면 이
되먹임을 두 객체가 나눠 갖게 된다.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from wwe_game.domain.exceptions import InvalidConditionError
from wwe_game.domain.value_objects.body_part import BodyPart

WEAR_MIN = 0
WEAR_MAX = 100


class InjuryGrade(StrEnum):
    HEALTHY = "healthy"
    MINOR = "minor"
    SERIOUS = "serious"
    CAREER_ENDING = "career_ending"


@dataclass(frozen=True)
class Condition:
    """부상 등급 · 회복까지 남은 주차 · 누적 마모."""

    grade: InjuryGrade = InjuryGrade.HEALTHY
    weeks_left: int = 0
    wear: int = 0
    part: BodyPart | None = None
    """다친 곳 (§3-D43). 건강하면 None이다.

    **등급과 부위는 다른 축이다.** 등급이 얼마나 오래 빠지는지를 정하고, 부위는 그
    기간에 배수를 곱하며 다음 부상이 어디로 갈지를 바꾼다.
    """

    def __post_init__(self) -> None:
        if not WEAR_MIN <= self.wear <= WEAR_MAX:
            raise InvalidConditionError(
                f"wear는 {WEAR_MIN}~{WEAR_MAX} 범위여야 합니다: {self.wear}"
            )
        if self.weeks_left < 0:
            raise InvalidConditionError(
                f"weeks_left는 음수일 수 없습니다: {self.weeks_left}"
            )
        # 건강함과 회복 대기는 동시에 성립할 수 없다. 한쪽만 갱신하는 버그를 여기서 막는다.
        if (self.grade is InjuryGrade.HEALTHY) != (self.weeks_left == 0):
            raise InvalidConditionError(
                f"등급과 회복 주차가 어긋납니다: grade={self.grade}, weeks_left={self.weeks_left}"
            )
        # 건강한데 다친 곳이 있을 수는 없다. 회복이 부위를 안 지우면 여기서 걸린다.
        if (self.grade is InjuryGrade.HEALTHY) and self.part is not None:
            raise InvalidConditionError(f"건강한데 부위가 남아 있습니다: {self.part}")

    @property
    def is_injured(self) -> bool:
        return self.grade is not InjuryGrade.HEALTHY

    @property
    def is_career_ending(self) -> bool:
        return self.grade is InjuryGrade.CAREER_ENDING

    def recover(self, weeks: int) -> Condition:
        """주차를 진행시켜 회복시킨다. 0이 되면 등급도 함께 낫는다.

        **중대 부상은 회복하지 않는다** — 커리어가 거기서 끝나므로 회복 개념이 없다.
        """
        if weeks < 0:
            raise InvalidConditionError(f"회복 주차는 음수일 수 없습니다: {weeks}")
        if not self.is_injured or self.is_career_ending:
            return self
        remaining = max(0, self.weeks_left - weeks)
        if remaining == 0:
            # 나으면 부위도 함께 지운다 — 몸이 기억하는 것은 `CareerRun`의 이력이다.
            return replace(self, grade=InjuryGrade.HEALTHY, weeks_left=0, part=None)
        return replace(self, weeks_left=remaining)

    def with_wear(self, delta: int) -> Condition:
        """마모를 더한다. 범위를 벗어나면 자른다 — 회복 선택지는 음수 델타를 준다."""
        return replace(self, wear=min(WEAR_MAX, max(WEAR_MIN, self.wear + delta)))

    def injured(
        self, grade: InjuryGrade, weeks: int, part: BodyPart | None = None
    ) -> Condition:
        """부상을 입힌다. 마모는 그대로 남는다."""
        if grade is InjuryGrade.HEALTHY:
            raise InvalidConditionError(
                "HEALTHY로 부상시킬 수 없습니다. recover()를 쓰세요."
            )
        if grade is InjuryGrade.CAREER_ENDING:
            # 복귀가 없으므로 남은 주차가 의미를 갖지 않는다. 0으로 두면 HEALTHY와
            # 구분이 안 되는 상태가 생기니, 커리어 종료는 status로 표현한다.
            return replace(
                self, grade=grade, weeks_left=weeks if weeks > 0 else 1, part=part
            )
        if weeks <= 0:
            raise InvalidConditionError(f"부상에는 회복 주차가 있어야 합니다: {weeks}")
        return replace(self, grade=grade, weeks_left=weeks, part=part)


HEALTHY = Condition()
"""시작 상태. 새 커리어가 여기서 출발한다."""
