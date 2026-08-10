"""커리어의 시계 — 모든 모드가 공유하는 불변값 (하네스 §3-D15).

여기 있는 것은 튜닝 대상이 아니다. 승률·가중치처럼 조정하는 수치는 `career_rules.py`에
있고, 이 파일은 "커리어가 몇 주짜리인가"라는 구조를 정한다.

**내부 시계는 언제나 주(week)다.** 모드는 한 틱이 몇 주인지만 정한다. 달력의 달을 쓰면
1560주가 정수로 나뉘지 않아 "52주마다 한 살"이 어긋난다(§3-D15).
"""

from __future__ import annotations

START_AGE = 20
"""시작 나이. 선택지가 아니다 (§3-D10)."""

WEEKS_PER_YEAR = 52
"""나이가 오르는 주기. 달력이 아니라 게임 내 환산값이다."""

CAREER_YEARS = 30
"""커리어 길이. 네 모드 전부 같다 (§3-D15)."""

CAREER_WEEKS = CAREER_YEARS * WEEKS_PER_YEAR
"""1560주. `advance()`가 넘을 수 없는 절대 상한이다."""

RETIREMENT_AGE = START_AGE + CAREER_YEARS
"""50세. 은퇴 4조건 중 만기에 해당한다 (§3-D16)."""
