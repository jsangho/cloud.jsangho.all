"""몸값을 매긴다 (하네스 §3-D47).

**순수 함수다.** 세이브를 읽어 숫자를 돌려줄 뿐, 아무것도 바꾸지 않는다.

## 다섯 재료 (2026-08-11 사용자 결정)

| 재료 | 방향 | 근거 |
|---|---|---|
| 인기도 | 주축 (×1 ~ ×10) | 이 게임의 대전제다. 돈이 되는 선수가 돈을 받는다 |
| 챔피언 이력 | 올린다 (최대 ×4) | 벨트를 감아 본 사람에게는 값이 붙는다 |
| 경력 | 올린다 (최대 ×1.9) | 오래 버틴 것 자체가 값이다 |
| 백스테이지 평판 | **깎기만 한다** | §3-D42와 같은 모양 — 상은 안 주고 벌만 준다 |
| 마모·부상 이력 | 깎는다 (최대 −40%) | 몸이 상한 선수에게는 길게 못 준다 |

**평판이 깎기만 하는 이유**는 §3-D42에서 이미 겪었다. 배수로 상을 주면 평판이 높은
플레이만 이중으로 유리해지고, "평판이 좋다고 더 주지는 않지만 미움받으면 덜 준다"는
현실의 모양과도 어긋난다.

## 돈이 스탯을 직접 올리지 않는다

이 파일이 정하는 것은 **버는 쪽**뿐이다. 쓰는 쪽(§3-D48)은 인기도·경기력을 직접
가산하지 않는다 — 그렇게 하면 §13-Q13·§3-D41에서 두 번 겪은 사고가 세 번째로
반복된다. 돈은 **선택지를 여는 열쇠**이지 스탯 펌프가 아니다.
"""

from __future__ import annotations

from wwe_game.domain.constants import career_rules as rules
from wwe_game.domain.entities.career_run import CareerRun
from wwe_game.domain.services import career_end
from wwe_game.domain.services.seeded_roll import SeededRoll
from wwe_game.domain.value_objects.contract import WEEKS_PER_YEAR, Contract
from wwe_game.domain.value_objects.title import (
    SPEED_TITLES,
    TITLES,
    Brand,
    Title,
    TitleTier,
)

BASE_WEEKLY_PAY = 1_300
"""바닥 주급(달러). 인기도 0·무관 경력의 신인이 받는 값 — 연 $67,600.

실제 육성 계약의 감각에 맞췄다. 여기에 배수가 곱해져 정상급이 주 $9만 언저리(연
$4.7M)에 닿는다. **바닥과 천장의 비가 70배**인데, 그게 이 바닥의 실제 격차다.
"""

POPULARITY_PEAK = 16.0
POPULARITY_CURVE = 3.2
"""인기도 배수 — `1 + PEAK × (인기도/100)^CURVE`. 인기도 100이면 ×17이다.

**선형이던 것을 곡선으로 바꿨다** (2026-08-13 사용자 지적: "연봉이 터무니없이 큰 것
같은데"). 문제는 값이 아니라 **격차가 없다는 것**이었다. 배수 다섯이 곱해지는데
인기도 항만 선형이라, 평범한 커리어와 톱스타의 최고 연봉이 5.8배밖에 안 벌어졌다 —
그 바닥의 실제 격차는 그보다 훨씬 크다.

50판 실측(커리어 최고 연봉):

| | 선형 0.09 | 곡선 3.2 |
|---|---|---|
| 하위 10% | $605K | **$251K** |
| 중앙 | $1,305K | **$971K** |
| 상위 10% | $2,615K | $2,584K |
| 최대 | $3.5M | $3.9M |
| 격차 | 5.8배 | **15.5배** |

**위를 깎지 않고 아래를 깎았다.** 톱스타 $3.9M은 실제 정상급 계약의 감각 그대로이고,
평범한 커리어가 그 근처에 있던 것이 어긋남이었다. 지수를 올리면 중간이 먼저 무너지고
정점은 `PEAK`로 따로 잡을 수 있어서, 둘을 한 쌍으로 둔다.

인기도 경제(§13-Q13)를 다시 만지면 이 둘도 함께 재야 한다 — 실측 커리어 최고
인기도 중앙값 72가 이 곡선의 기준점이다.
"""

TITLE_PAY_WEIGHT: dict[TitleTier, float] = {
    TitleTier.WORLD: 0.60,
    TitleTier.SECONDARY: 0.22,
    TitleTier.TAG: 0.12,
}
"""벨트 한 번당 배수 가산. **횟수로 센다** — 같은 벨트를 두 번 감으면 두 번 쳐 준다."""

SPEED_PAY_WEIGHT = 0.06
"""스피드 벨트 한 번당 가산 (§3-D72). **표에서 가장 낮다.**

급으로 치면 2선(0.22)인데 그 값을 주면 안 된다. 관문이 15라 커리어당 평균 3.5번
감히고(40판 실측), 2선 값이면 그것만으로 상한(3.0)의 4분의 1을 채운다 — 하위 티어
벨트가 정상급 주급을 만드는 셈이다.

태그(0.12)의 절반으로 둔 이유: 태그는 파트너가 있어야 하고 관문도 두 배(30)다.
"""

TITLE_PAY_CAP = 2.0
"""챔피언 이력 가산의 상한 (배수로는 ×3).

**3.0이었다** (2026-08-13). 인기도 곡선을 세우면서 함께 낮췄다 — 벨트는 인기도가
오른 결과이기도 해서, 둘 다 후하면 같은 성취를 두 번 쳐 준다.

상한이 없으면 30년 커리어 후반이 이력만으로 천장을 뚫는다. 다섯 재료 중 유일하게
**계속 쌓이기만 하는** 값이라 여기만 뚜껑이 필요하다.
"""

TENURE_SLOPE = 0.02
"""경력 1년당 배수 증가. 30년이면 ×1.6다.

**0.03이었다** (2026-08-13). 오래 뛴 것은 누적 잔액이 이미 갚는다 — 주급까지 두 배로
올리면 "오래 산 커리어가 곧 잘한 커리어"가 되어, 실력과 수명이 한 축으로 뭉친다.
"""

WEAR_PENALTY = 0.25
"""마모 100이 깎는 비율. `wear`는 회복 선택으로 내려갈 수 있어 되돌릴 여지가 있다."""

INJURY_HISTORY_PENALTY = 0.02
"""다친 적 있는 부위 하나당 깎는 비율. **되돌아오지 않는다** — 몸은 기억한다(§3-D43)."""

BODY_PENALTY_FLOOR = 0.60
"""몸 상태가 깎을 수 있는 하한. 아무리 상해도 4할은 남는다 —
0에 닿게 두면 마모 높은 커리어가 계약 자체를 못 맺는다.
"""

DEVELOPMENTAL_FACTOR = 0.50
"""육성 브랜드의 주급 배수. **같은 인기도라도 NXT는 절반이다.**

콜업이 승진인 이유가 여기 하나 더 생긴다 — 지금까지 콜업은 벨트와 무대만 바꿨다.
"""


def _title_bonus(run: CareerRun) -> float:
    """딴 벨트가 붙이는 가산. 상한에서 자른다.

    **스피드만 급이 아니라 이름으로 값을 찾는다** (§3-D72) — 2선이면서 2선 값을
    받으면 안 되는 유일한 벨트다.
    """
    total = sum(_pay_weight_of(t) for t in run.titles_won)
    return min(TITLE_PAY_CAP, total)


def _pay_weight_of(title: Title) -> float:
    if title in SPEED_TITLES:
        return SPEED_PAY_WEIGHT
    return TITLE_PAY_WEIGHT[TITLES[title].tier]


def _body_factor(run: CareerRun) -> float:
    """몸이 깎는 배수. 마모와 부상 이력이 함께 본다."""
    penalty = (
        run.condition.wear / 100 * WEAR_PENALTY
        + len(run.injured_parts) * INJURY_HISTORY_PENALTY
    )
    return max(BODY_PENALTY_FLOOR, 1.0 - penalty)


def appraise(run: CareerRun) -> int:
    """지금 이 선수의 주급(달러). **계약을 맺지 않는다** — 값만 매긴다.

    재계약 협상도 복귀 오퍼도 이 값을 부른다. 산식이 한 곳에 있어야 "재계약이
    복귀 오퍼보다 후하다" 같은 어긋남이 생기지 않는다.
    """
    popularity = (
        1.0 + POPULARITY_PEAK * (run.stats.popularity / 100) ** POPULARITY_CURVE
    )
    titles = 1.0 + _title_bonus(run)
    tenure = 1.0 + run.week / WEEKS_PER_YEAR * TENURE_SLOPE
    # 평판은 **깎기만 한다** — 45 이상은 1.0이고 그 아래로만 떨어진다 (§3-D42).
    standing = rules.push_factor(run.stats.backstage)
    brand = DEVELOPMENTAL_FACTOR if run.brand is Brand.NXT else 1.0
    pay = (
        BASE_WEEKLY_PAY
        * popularity
        * titles
        * tenure
        * standing
        * _body_factor(run)
        * brand
    )
    return max(1, round(pay))


TERM_BANDS: tuple[tuple[int, int], ...] = (
    (5_000, 2),
    (20_000, 3),
    (0, 5),
)
"""(주급 상한, 계약 연수). **비쌀수록 길게 묶는다** — 마지막 줄이 그 위 전부다.

싼 계약을 짧게 주는 것이 이 표의 핵심이다. 미드카더는 2년마다 다시 평가받으므로
한 번 미끄러지면 금방 무소속이 되고, 정상급은 5년이 보장돼 슬럼프를 견딘다.
"""


def term_weeks(weekly_pay: int) -> int:
    """그 주급이면 몇 주짜리 계약인가."""
    for ceiling, years in TERM_BANDS:
        if ceiling == 0 or weekly_pay < ceiling:
            return years * WEEKS_PER_YEAR
    raise AssertionError("TERM_BANDS의 마지막은 상한 0이어야 합니다")


def sign(run: CareerRun) -> Contract:
    """지금 몸값으로 계약 한 장. **기간도 몸값이 정한다** (§3-D49)."""
    pay = appraise(run)
    return Contract(
        weekly_pay=pay,
        signed_week=run.week,
        ends_week=run.week + term_weeks(pay),
    )


# ── 계약이 오가는 사건 (§3-D50) ──────────────────────────────


def release(run: CareerRun) -> CareerRun:
    """계약을 끊는다. **커리어를 닫지 않는다** — 무소속이 될 뿐이다.

    벨트는 함께 반납한다. 감고 있는 채로 나가면 `CareerRun`의 불변식이 막고,
    막지 않더라도 소속 없는 챔피언이라는 상태가 생긴다. 이력(`titles_won`)은
    남는다 — §3-D40이 부상 반납에서 정한 것과 같은 규칙이다.
    """
    return run.evolve(
        contract=None,
        titles_held=frozenset(),
        release_weeks=0,
        unsigned_weeks=0,
        title_shot=False,
        briefcase_week=0,
    )


def renew(run: CareerRun) -> CareerRun:
    """지금 몸값으로 다시 맺는다. 무소속이었다면 복귀다."""
    return run.evolve(contract=sign(run), unsigned_weeks=0)


COMEBACK_BASE_CHANCE = 0.030
"""무소속 한 주에 복귀 오퍼가 올 기본 확률. 인기도·평판이 여기에 곱해진다."""

COMEBACK_FLOOR_FACTOR = 0.30
"""인기도 0에서도 남는 몫. **0으로 두지 않는 이유**가 §13-Q14와 같다 —
바닥에서 회복이 불가능하면 인디 구간이 유예가 아니라 그냥 대기실이 된다.
"""


def comeback_chance(run: CareerRun) -> float:
    """복귀 오퍼가 올 확률(주당). **인기도가 주축이고 평판이 깎는다.**

    방출은 대개 평판 때문에 일어나고 인기도 방패가 46이라(§career_rules), 잘린
    선수는 거의 다 인기도 46 미만이다. 그래서 인기도 관문을 세우면 **아무도 못
    돌아온다** — 관문 대신 기울기로 뒀다: 낮으면 오래 걸릴 뿐 막히지는 않는다.
    """
    reach = COMEBACK_FLOOR_FACTOR + run.stats.popularity / 100
    return COMEBACK_BASE_CHANCE * reach * rules.push_factor(run.stats.backstage)


def settle(run: CareerRun, roll: SeededRoll) -> CareerRun:
    """한 주차가 지난 뒤 계약이 어떻게 됐는지 (§3-D50).

    **순서가 곧 우선순위다.** 해지가 만료보다 앞선다 — 잘리는 주에 계약이 만료돼도
    재계약 협상이 열리지는 않는다.

    끝난 커리어는 손대지 않는다. 종료 판정(`career_end.close_if_ended`)이 이 뒤에
    오지만, 만기·중대 부상으로 이미 닫힌 세이브가 여기 들어올 수 있다.
    """
    if not run.is_active:
        return run
    if run.is_signed:
        if run.release_weeks >= career_end.release_grace_weeks(run):
            # 못 참아 주는 것도, 입지가 무너진 것도 계약이 끊기는 하나의 사건이다
            # (§13-Q14). 달라진 것은 **그 뒤가 있다**는 것뿐이다.
            return release(run)
        assert run.contract is not None
        if run.contract.expires_at(run.week):
            # 만료 시점에 위험권이면 오퍼가 없다. 방출과 같은 판정을 쓴다 —
            # 기준을 따로 두면 "잘리지는 않는데 재계약도 안 되는" 구간이 생긴다.
            return release(run) if career_end.is_at_release_risk(run) else renew(run)
        return run
    if roll.chance(comeback_chance(run)):
        return renew(run)
    return run.evolve(unsigned_weeks=run.unsigned_weeks + 1)
