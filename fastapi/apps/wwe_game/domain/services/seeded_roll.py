"""시드에서 파생되는 난수 (하네스 §3-D4).

같은 세이브를 같은 순서로 진행하면 결과도 이벤트도 문장도 같아야 한다. 버그 재현과
테스트가 여기에 달려 있다.

**파이썬 `hash()`를 쓰지 않는다.** 문자열 해시는 프로세스마다 소금값이 달라 재현이
깨진다 — 서버를 재시작하면 같은 세이브가 다른 커리어가 된다. `blake2b`로 고정한다.

**채널을 나누는 이유:** 경기 판정과 부상 굴림이 같은 난수열을 쓰면, 나중에 판정에
굴림을 하나 추가했을 때 그 뒤의 부상·이벤트가 통째로 밀린다. 저장된 세이브가 전부
다른 커리어가 되는 셈이다. 채널이 다르면 서로를 밀지 않는다.
"""

from __future__ import annotations

import hashlib
import random
from collections.abc import Sequence
from typing import Final

MATCH: Final = "match"
INJURY: Final = "injury"
WEAR: Final = "wear"
TITLE: Final = "title"
CARD: Final = "card"
BRAND: Final = "brand"
GROWTH: Final = "growth"
EVENT: Final = "event"
BODY: Final = "body"
RIVALRY: Final = "rivalry"
NARRATION: Final = "narration"
TEAM: Final = "team"
OPPONENT: Final = "opponent"
STIPULATION: Final = "stipulation"
ELIMINATION: Final = "elimination"
CONTRACT: Final = "contract"
"""복귀 오퍼 굴림 (§3-D50). 무소속 주차마다 한 번."""
ROSTER_STABLE: Final = "roster_stable"
"""그 판의 가상 스테이블 (§3-D64). 이름 굴림과 채널을 나눈다 — 한쪽을 손대면 다른
쪽이 밀리면 안 된다."""
ROSTER_CAST: Final = "roster_cast"
"""그 판의 가상 선수 이름 (§3-D59). **판마다 한 번만 굴린다.**"""
RATING: Final = "rating"
"""경기 별점 (§3-D56). **판정과 나눠 둔다** — 별점을 굴려도 승패가 밀리면 안 된다."""
TRADE: Final = "trade"
"""시즌 중 트레이드 (§3-D63). **드래프트와 채널을 나눈다** — 한쪽 굴림이 늘어도
다른 쪽이 밀리면 안 된다."""
DRAFT: Final = "draft"
"""연말 드래프트 (§3-D54). **명부가 쓰는 유일한 채널이다** — 해마다 한 번, 그 해에
자리를 맞바꿀 칸과 사람을 고른다."""
NEWS: Final = "news"
"""기사의 매체·본문 변주와 댓글 (§3-D87).

**판정과 완전히 나눈다.** 기사는 §3-D56의 별점과 같은 자리다 — 보는 방식이지 값이
아니고, 여기서 아무리 굴려도 커리어는 한 칸도 안 움직인다. 채널을 나눠 두지 않으면
댓글을 한 줄 더하는 것만으로 그 주차의 경기 결과가 밀린다.
"""
CALL_OUT: Final = "call_out"
"""플레이어가 시비를 걸 수 있는 상대 목록 (§3-D86).

**`RIVALRY`와 채널을 나눈다.** 같은 채널을 쓰면 화면이 후보를 뽑는 것만으로 규칙의
대립 굴림이 밀린다 — 보기만 해도 세계가 달라지는 셈이다. 목록은 세이브를 다시 열
때마다 같아야 하므로(§3-D4) 시드·주차로만 정해진다.
"""
FACING: Final = "facing"
"""대립 후보가 마주 보는 성향으로 기우는가 (§3-D95).

**`RIVALRY`와 채널을 나눈다.** 같은 채널을 쓰면 이 굴림 하나가 그 주차의 상대·열기
굴림을 통째로 밀어, 성향을 붙이는 것만으로 옛 세이브가 다른 커리어가 된다.
"""
TITLE_SCENE: Final = "title_scene"
"""배경 챔피언의 재위 (§3-D38). **벨트마다 따로 굴린다** — 한 채널을 나눠 쓰면
월드 벨트의 재위가 바뀔 때 태그 벨트 계보까지 통째로 밀린다."""
CALENDAR: Final = "calendar"
"""그 해의 달력 (§3-D71). **주차 자리에 연차를 넣는다** — 달력은 한 주가 아니라
한 해의 것이라, 해마다 한 번만 굴린다. 유동 대회의 달·서바이버의 얼굴·클래시의
개최지가 전부 이 채널에서 나온다."""


def _derive(seed: int, week: int, channel: str) -> int:
    digest = hashlib.blake2b(
        f"{seed}:{week}:{channel}".encode(), digest_size=8
    ).digest()
    return int.from_bytes(digest, "big")


class SeededRoll:
    """한 주차 · 한 채널의 난수. 같은 (seed, week, channel)이면 항상 같은 수열."""

    __slots__ = ("_rng",)

    def __init__(self, seed: int, week: int, channel: str) -> None:
        self._rng = random.Random(_derive(seed, week, channel))  # noqa: S311

    def chance(self, probability: float) -> bool:
        """0.0~1.0 확률로 참. 범위 밖 값은 조용히 넘기지 않는다."""
        if not 0.0 <= probability <= 1.0:
            raise ValueError(f"확률은 0.0~1.0이어야 합니다: {probability}")
        return self._rng.random() < probability

    def between(self, low: int, high: int) -> int:
        """양끝 포함 정수."""
        return self._rng.randint(low, high)

    def uniform(self, low: float, high: float) -> float:
        return self._rng.uniform(low, high)

    def pick[T](self, items: Sequence[T]) -> T:
        if not items:
            raise ValueError("빈 목록에서 고를 수 없습니다.")
        return items[self._rng.randrange(len(items))]
