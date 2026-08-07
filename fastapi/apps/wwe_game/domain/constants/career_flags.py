"""선택이 남기는 표식 중 **규칙이 읽는 것들** (하네스 §3-D26).

덱의 선택지는 `flags`로 표식을 남긴다. 그 표식은 두 곳에서 읽힌다.

1. **카드 조건** — `requires.flags`. "그때 그 일이 있었던 선수에게만 뜨는 카드"
2. **규칙** — 여기 모인 이름들. "그때 그 일이 그 뒤를 바꾼다"

**이름을 상수로 모으는 이유**: 문자열을 규칙 코드에 흩뿌리면 오타가 조용히 통과한다.
표식은 있는데 아무 일도 안 일어나고, 그게 정확히 2026-08-07 감사에서 나온 문제였다 —
30종 중 21종이 아무도 안 읽는 값이었고, 그중 `painkiller_habit`은 **문서가 규칙이 있다고
약속까지 해 둔 것**이었다.

여기 없는 표식은 카드 조건이 읽거나, 아직 아무도 안 읽는다. 후자는 콘텐츠 부채다.
"""

from __future__ import annotations

from typing import Final

PAINKILLER: Final = "painkiller_habit"
"""진통제를 달고 뛴다 — 부상 확률이 오른다."""

GROUNDED: Final = "grounded_style"
"""공중기를 봉인했다 — 부상 확률이 내린다."""

PUSH_FROZEN: Final = "push_frozen"
"""밀어주기가 멈췄다 — 인기도가 더디 오른다."""

GRUDGE: Final = "locker_room_grudge"
"""라커룸에 척을 졌다 — 평판 회복이 느리다."""

MANAGER: Final = "has_manager"
"""매니저가 붙었다 — 마이크웍이 빨리 는다."""

NEMESIS_LOCKED: Final = "nemesis_locked"
"""매듭짓지 못한 숙적 — 열기가 잘 안 식는다."""

EMERGENCY_CALLUP: Final = "callup_emergency"
"""대타 자리를 수락했다 — 다음 활동 주차에 콜업된다 (§3-D22-1)."""

SUSPENSION_PENDING: Final = "suspension_pending"
"""징계가 걸려 있다 — 방출 유예가 절반이다 (§3-D24)."""

WENT_INTO_BUSINESS: Final = "went_into_business_for_self"
"""각본을 어겼다 — 방출 유예가 절반이다 (§3-D24)."""

RELEASE_TRIGGER_FLAGS: Final = frozenset({SUSPENSION_PENDING, WENT_INTO_BUSINESS})
"""방출 유예를 절반으로 줄이는 표식 (§3-D24)."""

RULE_READ_FLAGS: Final = frozenset(
    {
        PAINKILLER,
        GROUNDED,
        PUSH_FROZEN,
        GRUDGE,
        MANAGER,
        NEMESIS_LOCKED,
        EMERGENCY_CALLUP,
        *RELEASE_TRIGGER_FLAGS,
    }
)
"""규칙이 읽는 표식 **전부**. 테스트가 이 목록과 덱을 대조한다.

이름이 여기 모여 있어야 감사가 정확해진다 — 흩어져 있으면 "누가 읽는가"를 세는 일이
문자열 검색이 되고, 그 검색이 놓친 것이 2026-08-07의 죽은 표식 21종이었다.
"""
