"""도메인 예외.

`app/exceptions.py`가 아니라 여기 두는 이유는 값 객체와 엔티티가 직접 던지기 때문이다.
도메인은 app 레이어를 import할 수 없다(`.importlinter` 계약 3).

검증 실패는 전부 `ValueError` 하위다 — 라우터가 `ValueError`를 400으로 변환하는
경로에 그대로 얹힌다(하네스 §8). 상태 위반은 `ValueError`가 아니며 409로 간다.
"""

from __future__ import annotations


class InvalidRingNameError(ValueError):
    """링 네임이 규칙을 어겼을 때 (하네스 §3-D12)."""


class InvalidStatsError(ValueError):
    """스탯이 허용 범위를 벗어난 값으로 만들어질 때."""


class InvalidConditionError(ValueError):
    """부상 등급과 회복 주차가 서로 맞지 않을 때."""


class UnknownGameModeError(ValueError):
    """없는 모드 코드를 요청했을 때."""


class UnknownCountryError(ValueError):
    """권역에 매핑되지 않은 국가를 골랐을 때 (하네스 §11-16)."""


class InvalidChoiceError(ValueError):
    """대기 이벤트에 없는 선택지 코드를 냈을 때 (하네스 §8 → 400).

    "이벤트가 없다"(409)와 다르다 — 이건 이벤트는 있는데 **그 항목이 없는** 경우다.
    """


class InvalidCareerRunError(ValueError):
    """세이브 자체가 규칙에 맞지 않을 때.

    체험판은 클라이언트가 상태를 들고 있어 조작될 수 있다(하네스 §3-D8).
    그 입구를 이 예외가 지킨다.
    """


class RunNotActiveError(Exception):
    """이미 끝난 커리어를 조작하려 할 때. 검증 실패가 아니라 상태 위반이라 409다."""


class NoGoalNeededError(Exception):
    """분기 목표를 고를 때가 아닌데 골랐다 (§3-D80)."""


class CannotAffordGoalError(ValueError):
    """잔액이 모자란 목표를 골랐다 (§3-D80·D48)."""


class NoOfferOpenError(Exception):
    """재계약 협상 중이 아닌데 답했다 (§3-D84)."""


class InvalidFinisherNameError(ValueError):
    """직접 지은 기술 이름이 규칙에 안 맞는다 (§3-D88).

    링네임과 같은 규칙이다(§3-D12) — 이 이름이 서술 슬롯으로 들어가기 때문이다.
    """


class CannotChangeFinisherError(Exception):
    """지금 바꿀 수 없는 피니셔를 바꾸려 했다 (§3-D88).

    쿨다운 중이거나 · 계열 밖 코드거나 · 이미 그것을 쓰고 있다.
    """


class CannotNameError(Exception):
    """이름을 살 수 없다 (§3-D92).

    잔액이 모자라거나 · 없는 칸이거나 · 이미 그 이름을 쓰고 있다. 이름 자체가 규칙에
    안 맞는 것은 `InvalidFinisherNameError`가 따로 잡는다 — **못 사는 것과 못 쓰는
    이름은 다른 실패다**(전자는 409, 후자는 400).
    """


class CannotCallOutError(Exception):
    """걸 수 없는 상대에게 시비를 걸었다 (§3-D86).

    자리가 찼거나(`MAX_ACTIVE`) · 후보 목록 밖의 이름이다.
    """


class CannotCashInError(Exception):
    """쓸 수 없는 가방을 쓰려 했다 (§3-D85).

    없거나 · 이미 쓰기로 했거나 · 무소속이거나 · 이미 그 벨트를 감고 있다.
    """
