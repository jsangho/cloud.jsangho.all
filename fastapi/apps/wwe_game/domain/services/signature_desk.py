"""이름은 돈으로 산다 (하네스 §3-D92).

§3-D88이 피니셔에 이름을 줬고 §3-D91이 시그니처를 줬는데, **둘 다 공짜였다.** 그래서
"내 기술을 갖는다"가 결정이 아니라 설정 메뉴에 가까웠다.

사용자 요청 — *"시그니처나 피니셔 등의 이름짓기를 게임 내에서 구매하는 시스템"*.

## 무엇에 값을 매기고 무엇이 공짜인가

| 자리 | 값 | 왜 |
|---|---|---|
| 피니셔를 목록에서 고르기 | **공짜** | 남들이 쓰던 기술을 그대로 쓰는 것이다 |
| 피니셔 이름 직접 짓기 | `FINISHER_NAMING` | 그 이름이 링 위에서 불린다 |
| 시그니처 한 칸 이름 짓기 | `SIGNATURE_NAMING` | 칸을 살수록 자주 나온다 (§3-D91) |

**목록을 공짜로 두는 것이 이 절의 핵심이다.** 전부 유료면 가난한 구간에 피니셔를
아예 못 바꾸고, 그건 §3-D88이 연 자리를 도로 닫는 것이다. 돈이 사는 것은 기술이 아니라
**이름**이다.

## 판정에 닿지 않는다

§3-D88이 못 박은 것을 그대로 지킨다 — 승패도 별점도 부상도 안 바뀐다. 돈으로 사는
것이 스탯이면 §13-Q13이 두 번 막은 지름길이 열린다. 여기서 사는 것은 **화면에 뭐라고
적히는가**뿐이다.

## 시그니처에는 쿨다운이 없다 — 돈이 그 자리다

피니셔는 분기마다 한 번만 바꾼다(§3-D88). 시그니처까지 그러면 규칙이 둘로 늘어나는데,
이쪽은 **값이 이미 문턱**이라 시계를 하나 더 둘 이유가 없다. 다시 지으면 다시 낸다.
"""

from __future__ import annotations

from typing import Final

from wwe_game.domain.entities.career_run import CareerRun
from wwe_game.domain.exceptions import CannotNameError
from wwe_game.domain.value_objects.finisher import custom

BASE_SLOTS: Final = 1
"""처음 가지고 시작하는 시그니처 칸 (2026-08-19 사용자 결정).

**한 칸이면 그것이 곧 내 대표 기술이다.** 데뷔하자마자 셋을 들고 시작하면 "이게 내
기술"이라는 순간이 없다 — §3-D88이 피니셔를 수플렉스에서 시작시킨 것과 같은 이유다.
"""

MAX_SLOTS: Final = 4
"""끝까지 늘려도 넷.

실존 선수의 시그니처 중앙값이 3이고 아홉을 가진 선수도 있지만, **플레이어에게는 상한이
필요하다**: 칸이 늘수록 경기에서 시그니처가 나올 확률이 오르는데(§3-D91), 여덟 칸이면
`SIGNATURE_CHANCE_MAX`에 붙어 평범한 수가 사라진다.
"""

SLOT_PRICES: Final[tuple[int, ...]] = (0, 20_000, 45_000, 80_000)
"""칸을 여는 값 — **칸 번호마다 다르다.** 첫 칸은 공짜(가지고 시작한다).

**값이 오르는 이유**: 한 칸이 늘 때마다 그 뒤의 모든 경기에서 시그니처 빈도가 오른다
(§3-D91). 같은 값을 세 번 받으면 마지막 칸이 가장 싸게 느껴지는데, 실제로 얻는 것은
그때가 가장 크다. 분기 목표 최고가($30,000, §3-D80)와 견주면 둘째 칸은 그보다 싸고
넷째 칸은 두 배 반이다 — **후반의 돈 쓸 곳**이기도 하다(§3-D48·D89).
"""

SIGNATURE_NAMING: Final = 6_000
"""시그니처 한 칸에 이름을 붙이는 값(달러).

분기 목표의 중간값(`$9,000`, §3-D80)보다 조금 싸다 — **그 분기에 목표 대신 고를 수
있는 것**이어야 저울질이 생긴다. 칸 값과 나눠 둔 이유: 칸은 자리이고 이름은 그 자리에
무엇을 새기는가다. 마음에 안 들면 이름만 다시 산다.
"""

FINISHER_NAMING: Final = 15_000
"""피니셔 이름을 직접 짓는 값(달러). 시그니처 한 칸의 두 배 반이다.

경기를 끝내는 기술이고 분기마다 한 번만 손댈 수 있으므로(§3-D88), 무게가 다르다.
"""


def slots(run: CareerRun) -> int:
    """지금 가진 칸 수. **옛 세이브는 0이라 기본값으로 읽는다** — §3-D88의 `finisher`가
    빈 문자열을 기본값으로 읽는 것과 같은 자리다."""
    return max(BASE_SLOTS, run.signature_slots)


def expand_cost(run: CareerRun) -> int | None:
    """다음 칸을 여는 값. **다 열었으면 `None`** — 화면이 그 자리를 안 낸다."""
    opened = slots(run)
    if opened >= MAX_SLOTS:
        return None
    return SLOT_PRICES[opened]


def expand(run: CareerRun) -> CareerRun:
    """칸을 하나 더 산다 (§3-D92, 2026-08-19 사용자 요청).

    **이름은 따로 산다.** 칸을 열었다고 이름이 붙지는 않는다 — 빈 칸은 계열 기술로
    채워지고(§3-D91), 거기에 이름을 새길지는 다음 결정이다.
    """
    run.require_active()
    cost = expand_cost(run)
    if cost is None:
        raise CannotNameError(f"시그니처 칸은 {MAX_SLOTS}개가 끝입니다.")
    if not can_afford(run, cost):
        raise CannotNameError(f"잔액이 모자랍니다 — ${cost:,}가 필요합니다.")
    return run.evolve(
        signature_slots=slots(run) + 1,
        money=run.money - cost,
    )


def cost_of_slot(run: CareerRun, index: int) -> int:
    """그 칸에 이름을 (다시) 새기는 값. **다시 지어도 같은 값이다** — 무르는 데 할인은 없다."""
    _require_slot(run, index)
    return SIGNATURE_NAMING


def can_afford(run: CareerRun, cost: int) -> bool:
    return run.money >= cost


def name_slot(run: CareerRun, index: int, name: str) -> CareerRun:
    """시그니처 한 칸에 이름을 붙이고 값을 치른다.

    검증은 값 객체가 한다(`finisher.custom`) — 링네임·피니셔와 같은 입구다(§3-D12).
    **같은 이름을 두 칸에 두지 않는다**: 경기 중에 같은 이름이 두 번 불리면 칸을 산
    뜻이 없다.
    """
    run.require_active()
    _require_slot(run, index)
    named = custom(name).name
    if named in _without(run.signature_names, index):
        raise CannotNameError("이미 그 이름의 시그니처가 있습니다.")
    cost = cost_of_slot(run, index)
    if not can_afford(run, cost):
        raise CannotNameError(f"잔액이 모자랍니다 — ${cost:,}가 필요합니다.")
    names = list(run.signature_names)
    while len(names) <= index:
        names.append("")
    names[index] = named
    return run.evolve(
        signature_names=tuple(name for name in names if name),
        money=run.money - cost,
    )


def drop_slot(run: CareerRun, index: int) -> CareerRun:
    """이름을 지운다. **돌려받지 않는다** — 산 것은 이름이고, 지운다고 되사지 않는다."""
    run.require_active()
    _require_slot(run, index)
    if index >= len(run.signature_names):
        raise CannotNameError("비어 있는 칸입니다.")
    return run.evolve(signature_names=_without(run.signature_names, index))


def _without(names: tuple[str, ...], index: int) -> tuple[str, ...]:
    return tuple(name for position, name in enumerate(names) if position != index)


def _require_slot(run: CareerRun, index: int) -> None:
    """**안 산 칸에는 못 새긴다.** 칸이 자리이고 이름이 그 위의 글자다."""
    if not 0 <= index < slots(run):
        raise CannotNameError(f"열려 있는 시그니처 칸은 {slots(run)}개입니다.")
