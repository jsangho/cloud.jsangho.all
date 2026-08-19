"""그 사람의 무기고 — 이름 있는 수 (하네스 §3-D91).

경기 안에서 나오는 수는 세 층이다.

| 층 | 어디서 오나 |
|---|---|
| 평범한 한 수 | 계열 기술 뱅크 (§3-D81-4) — 누구나 쓴다 |
| **시그니처** | **이 파일** — 그 사람의 것이고, 많을수록 자주 나온다 |
| 피니셔 | 나는 §3-D88이 고르고, 상대는 여기서 이름을 얻는다 |

## 데이터가 없으면 굴린다 (2026-08-19 사용자 결정)

원본 CSV의 `Not Yet`은 *"아직 없다"*는 뜻이지 *"영영 없다"*가 아니다. 그리고 서른
해가 흐르면 링에 서는 사람 대부분이 가상 선수라(§3-D59) 데이터가 아예 없는 쪽이 다수가
된다 — 이름 있는 수를 데이터 있는 사람만 쓰게 두면 그 감각이 커리어 후반에 통째로
사라진다.

그래서 **없으면 계열 뱅크에서 뽑아 준다.** 이름으로만 굴리므로 같은 사람은 판이
달라져도 같은 무기고를 갖는다 — 무기고가 주차마다 바뀌면 "그 사람의 것"이 아니게 된다.

**생성기는 여전히 아무것도 지어내지 않는다** (§3-D10-1). CSV의 빈 칸은 빈 채로 남고,
채우는 일은 링 위에서만 일어난다. 나중에 사용자가 그 칸을 채우면 굴림이 데이터로
대체될 뿐, 고칠 코드가 없다.
"""

from __future__ import annotations

from typing import Final

from wwe_game.domain.constants import roster
from wwe_game.domain.services.seeded_roll import SeededRoll
from wwe_game.domain.value_objects.finisher import MOVES, MoveFamily

CHANNEL: Final = "arsenal"
"""이름으로만 굴리는 채널. 시드·주차를 안 쓰므로 **한 사람의 무기고는 늘 같다.**"""

ROLLED_RANGE: Final = (1, 3)
"""굴려서 주는 시그니처 수.

데이터가 있는 선수의 중앙값은 3이고 많게는 9다 — 굴림을 그 아래에 둬야 **실제로 대표
기술이 많은 선수**가 화면에서 더 자주 자기 기술을 쓴다(`match_flow.signature_chance`).
"""

_ALL_MOVES: Final[tuple[str, ...]] = tuple(
    move for family in MOVES for move in MOVES[family]
)


def signatures_of(name: str, family: MoveFamily | None = None) -> tuple[str, ...]:
    """그 사람의 시그니처들. 데이터가 없으면 계열 뱅크에서 굴려 준다.

    `family`는 아는 경우에만 넘긴다 — 플레이어는 자기 스타일을 알지만(§3-D29) 명부의
    상대는 계열을 안 들고 있다. 모르면 전체 뱅크에서 뽑는다.
    """
    known = roster.signatures_of(name)
    if known:
        return known
    roll = _roll_for(name)
    bank = MOVES[family] if family is not None else _ALL_MOVES
    count = min(roll.between(*ROLLED_RANGE), len(bank))
    picked: list[str] = []
    for _ in range(count):
        remaining = tuple(move for move in bank if move not in picked)
        picked.append(roll.pick(remaining))
    return tuple(picked)


def finisher_of(name: str) -> str:
    """상대가 나를 끝낼 때 부를 기술 이름 (§3-D91).

    **하나 이상인 선수가 있다** — 그럴 때는 굴려서 하나를 고른다. 그 밤마다 다른 것이
    나오지 않게 이름으로만 굴리므로, 같은 상대는 늘 같은 기술로 끝낸다.
    """
    known = roster.finishers_of(name)
    roll = _roll_for(name)
    if known:
        return roll.pick(known)
    return roll.pick(_ALL_MOVES)


def _roll_for(name: str) -> SeededRoll:
    """이름 하나로 고정된 굴림. 채널에 이름을 실어 사람마다 다른 수열을 얻는다."""
    return SeededRoll(0, 0, f"{CHANNEL}:{name}")
