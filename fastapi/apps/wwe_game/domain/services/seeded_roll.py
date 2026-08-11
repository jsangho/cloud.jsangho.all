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
TITLE_SCENE: Final = "title_scene"
"""배경 챔피언의 재위 (§3-D38). **벨트마다 따로 굴린다** — 한 채널을 나눠 쓰면
월드 벨트의 재위가 바뀔 때 태그 벨트 계보까지 통째로 밀린다."""


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
