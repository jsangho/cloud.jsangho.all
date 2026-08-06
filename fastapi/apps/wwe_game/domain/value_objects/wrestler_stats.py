"""선수 스탯 다섯과 위험도 (하네스 §3-D18).

셋(`popularity`·`in_ring`·`mic_work`)에서 다섯으로 늘었다. `backstage`가 없으면
"선배 갈굼"·"각본 반발"의 대가를 담을 곳이 없고, `alignment`가 없으면 같은 반칙이
힐일 때와 페이스일 때 같은 뜻이 된다.

여섯 번째 값 `wear`는 여기 없다 — 부상 굴림과 함께 움직이므로 `Condition`에 있다.

**생성은 막고, 적용은 자른다.** 범위 밖 값으로 만들려 하면 예외지만, 이벤트 효과를
더할 때는 조용히 잘린다. 전자는 조작된 체험판 상태를 걸러내는 입구이고(§3-D8),
후자는 "인기도 95에 +20"이 정상 진행이기 때문이다.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from enum import StrEnum

from wwe_game.domain.exceptions import InvalidStatsError

STAT_MIN = 0
STAT_MAX = 100
ALIGNMENT_MIN = -100
ALIGNMENT_MAX = 100

HEEL_THRESHOLD = -20
FACE_THRESHOLD = 20
"""사이 구간(-19~19)은 어느 쪽도 아니다. 관중이 갈린 상태를 표현한다."""


class Risk(StrEnum):
    """선택지의 분산. 기댓값은 비슷하되 결과가 갈리는 폭이 다르다 (하네스 §5)."""

    SAFE = "safe"
    BOLD = "bold"
    RECKLESS = "reckless"


EVENT_HEADROOM_EXPONENT = 0.5
"""이벤트 이득의 체감 지수. `이득 × ((남은 여지)/100) ** 0.5`.

인기도 50에서 +16은 +11이 되고, 90에서는 +5, 99에서는 +2가 된다.
최소 1은 남긴다 — 0이 되면 선택지가 아무 일도 안 하는 것처럼 보인다.
"""


def _diminish(name: str, current: int, delta: int) -> int:
    """오르는 쪽에만 체감을 건다. `alignment`는 움직이는 방향의 한계까지를 여지로 본다."""
    if delta <= 0:
        return delta
    if name == "alignment":
        room = ALIGNMENT_MAX - current if delta > 0 else current - ALIGNMENT_MIN
        span = ALIGNMENT_MAX
    else:
        room = STAT_MAX - current
        span = STAT_MAX
    factor = max(0.0, room / span) ** EVENT_HEADROOM_EXPONENT
    return max(1, round(delta * factor))


@dataclass(frozen=True)
class WrestlerStats:
    """전부 0~100. `alignment`만 -100~+100이고 음수를 허용한다."""

    popularity: int = 10
    in_ring: int = 20
    mic_work: int = 10
    backstage: int = 50
    alignment: int = 0

    def __post_init__(self) -> None:
        for name, low, high in self._bounds():
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool):
                raise InvalidStatsError(f"{name}은 정수여야 합니다: {value!r}")
            if not low <= value <= high:
                raise InvalidStatsError(
                    f"{name}은 {low}~{high} 범위여야 합니다: {value}"
                )

    @staticmethod
    def _bounds() -> tuple[tuple[str, int, int], ...]:
        return (
            ("popularity", STAT_MIN, STAT_MAX),
            ("in_ring", STAT_MIN, STAT_MAX),
            ("mic_work", STAT_MIN, STAT_MAX),
            ("backstage", STAT_MIN, STAT_MAX),
            ("alignment", ALIGNMENT_MIN, ALIGNMENT_MAX),
        )

    @property
    def is_heel(self) -> bool:
        return self.alignment <= HEEL_THRESHOLD

    @property
    def is_face(self) -> bool:
        return self.alignment >= FACE_THRESHOLD

    def evolve(self, **changes: int) -> WrestlerStats:
        """값을 통째로 갈아끼운다. 델타가 아니라 절대값이며 범위 검사를 그대로 받는다."""
        return replace(self, **changes)

    def apply_event(self, deltas: dict[str, int]) -> WrestlerStats:
        """이벤트 효과를 **체감을 적용해** 더한다.

        기본 성장(주당 ±1)에만 체감을 걸고 이벤트에는 안 걸어 둔 것이 균형 구멍이었다 —
        곡선을 조여 놨는데 이벤트가 그 위로 +16씩 얹어 계산적 플레이의 스탯이 다시
        96~99에 붙었다.

        **오르는 쪽만 준다.** 인기도 95에서 잃는 10은 그대로 10이어야 한다 — 정상에
        가까울수록 얻기 어렵고 잃기는 쉬운 쪽이 이야기에도 맞다.
        """
        scaled = {
            name: _diminish(name, getattr(self, name), delta)
            for name, delta in deltas.items()
        }
        return self.apply(scaled)

    def apply(self, deltas: dict[str, int]) -> WrestlerStats:
        """이벤트 효과를 더한다. 범위를 벗어나면 **자른다**.

        모르는 키는 조용히 무시하지 않고 막는다 — 덱 JSON의 오타가 아무 일도 일어나지
        않는 선택지로 바뀌는 게 가장 잡기 어려운 버그다.
        """
        known = {f.name for f in fields(self)}
        unknown = set(deltas) - known
        if unknown:
            raise InvalidStatsError(f"모르는 스탯 키: {sorted(unknown)}")

        changes: dict[str, int] = {}
        for name, low, high in self._bounds():
            if name in deltas:
                changes[name] = min(high, max(low, getattr(self, name) + deltas[name]))
        return replace(self, **changes)
