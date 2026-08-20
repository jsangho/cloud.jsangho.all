"""배경 세계의 챔피언 — 벨트는 늘 누군가의 것이다 (하네스 §3-D38).

지금까지 이 게임에 **챔피언이 없었다.** 벨트는 "걸려 있다 / 내가 갖고 있다" 두 상태
뿐이라, 레슬매니아에서 로만 레인즈와 붙는데 **벨트는 허공에서 왔다.** 실제 타이틀전은
"코디 로즈의 벨트에 도전한다"이지 "벨트에 도전한다"가 아니다.

## 저장하지 않는다

시드와 주차에서 매번 되짚는다 — `team_engine.chronicle`과 같은 방식이다(§3-D30).
재위 목록을 세이브에 담으면, 진행 한 번이 세이브를 통째로 다시 쓰는 구조(§3-D6)에서
표가 계속 커진다. 되짚는 비용은 벨트당 30~60번의 굴림이고 그 정도는 싸다.

## 플레이어는 이 계보에 없다

배경 계보는 **플레이어가 없는 세계**를 그린다. 플레이어가 벨트를 감고 있으면 그
기간의 챔피언은 플레이어이고, 그건 `CareerRun.titles_held`가 이미 안다 — 두 곳이 같은
사실을 들고 있으면 어긋난다. 여기서는 "내가 아니었다면 누구였을까"만 답한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from typing import Final

from wwe_game.domain.constants import roster
from wwe_game.domain.constants.champions import OPENING_CHAMPIONS
from wwe_game.domain.constants.roster import RivalTier
from wwe_game.domain.constants.teams import KOREAN_TEAM_NAMES
from wwe_game.domain.services import seeded_roll
from wwe_game.domain.services.seeded_roll import SeededRoll
from wwe_game.domain.value_objects.title import TITLES, Brand, Title, TitleTier

TIER_OF: Final[dict[TitleTier, RivalTier]] = {
    TitleTier.WORLD: RivalTier.UPPER_CARD,
    TitleTier.SECONDARY: RivalTier.MID_CARD,
    TitleTier.TAG: RivalTier.MID_CARD,
}
"""벨트 계층 → 그 벨트를 감을 만한 선수 등급.

태그 벨트를 중간급에 두는 이유: 태그 챔피언을 정상급에서 뽑으면 월드 챔피언과 같은
사람이 겹쳐 나온다.
"""

HOLDERS_OF: Final[dict[TitleTier, int]] = {
    TitleTier.WORLD: 1,
    TitleTier.SECONDARY: 1,
    TitleTier.TAG: 2,
}
"""그 벨트를 **몇 명이 드는가** (§3-D57).

태그 벨트를 한 사람이 들고 있었다 — 계보가 이름 하나만 뽑았기 때문이고, 그래서 카드에도
"A vs B"로 1대1 태그 타이틀전이 섰다. 평가에서 가장 큰 왜곡으로 꼽힌 자리다.

**팀 연대기(§3-D30)를 쓰지 않는다.** 0주차 팀들은 이름만 있고 구성원이 비어 있어
(`Team(label, (), 0)`) 성별도 브랜드도 알 수 없다. 계보가 그걸 들면 여성부 벨트를 남성부
팀이 감는다. 그래서 여기서는 **같은 디비전·브랜드·등급의 둘**을 뽑아 짝으로 세운다.
"""

UNDERDOG_SHARE: Final = 0.18
"""**아래 칸에서 챔피언이 나오는 비율** (§3-D95, 2026-08-19 사용자 요청).

*"가끔씩 미드카드가 어퍼카드 챔피언십을 노리고, 로우카드가 미드카드 챔피언십을 노리는
등 이런 일들이 있었으면 해."*

`roster.REACH_UP_CHANCE`와 같은 값이다 — 대립에서 넘보는 빈도와 벨트에서 넘보는 빈도가
달라야 할 이유가 없다. 다만 **여기서는 한 칸만** 내려간다: 두 칸을 열면 로우카드가 월드
챔피언이 되고, 그게 사용자가 *"비정상적"*이라고 부른 그 장면이다.
"""

PARTNER_JOIN: Final = " & "
"""두 사람을 한 챔피언으로 부르는 이음말. `Team.label`이 이름 없는 팀에 쓰는 것과 같다."""

REIGN_WEEKS: Final[dict[TitleTier, tuple[int, int]]] = {
    TitleTier.WORLD: (12, 32),
    TitleTier.SECONDARY: (6, 17),
    TitleTier.TAG: (6, 17),
}
"""계층별 **평상시** 재위 기간(주). 드물게 `LONG_REIGN_WEEKS`로 넘어간다.

**월드를 (26,78)에서 좁혔다** (2026-08-13, 현실 대조). 옛 주석은 "실제 평균에 맞춘
값"이라고 했는데, 그 평균은 로만 레인즈의 1,316일 같은 이상치가 끌어올린 것이다.
중앙값으로 보면 최근 월드 벨트 재위는 250~300일이다(세스 341일 · 군터 270일 ·
코디 280일 · 프리스트 126일). 실측 중앙이 329일이라 20%쯤 길었다.

| | 옛값 (26,78) | 지금 (20,56) |
|---|---|---|
| 재위 중앙 | 329일 | **약 265일** |
| 벨트당 연 교체 | 1.1회 | **약 1.4회** |

2선·태그는 건드리지 않았다 — 실측 189일·182일로 현실 그대로였다.

짧게 두면 30년 커리어에 챔피언이 너무 많이 지나가 "누구의 벨트인가"가 흐려진다 —
이 모듈을 만든 이유가 그것이라, 현실 중앙값 위쪽 끝에 맞췄다.
"""


LONG_REIGN_CHANCE: Final = 0.05
LONG_REIGN_WEEKS: Final[dict[TitleTier, tuple[int, int]]] = {
    TitleTier.WORLD: (40, 70),
    TitleTier.SECONDARY: (30, 56),
    TitleTier.TAG: (30, 56),
}
"""**스무 번에 한 번은 길게 간다** (2026-08-13 사용자 지시).

균등 분포 하나로는 사용자가 말한 두 가지를 동시에 만족할 수 없다 — "평균 5~6개월"과
"1년 넘게 갈 수도 있지만 희박하게". 균등이면 상한이 곧 최댓값이라, 1년을 넘기려면
상한을 52주 위로 올려야 하고 그러면 평균이 따라 올라간다.

그래서 밴드를 둘로 나눴다. 대부분은 평상시 밴드에서 나오고, 스무 번에 한 번 이쪽으로
간다 — 실제로도 장기 재위는 그런 모양이다(로만 1,316일 · 군터 IC 666일이 예외이지
평균이 아니다).

결과: **1선 평균 5.4개월 · 2선 이하 3.0개월**, 1년을 넘기는 재위는 1선 3% · 2선 이하 1%.
"""

INJURY_CHANCE: Final = 0.05
"""재위가 **부상으로** 끊길 확률 (2026-08-12 사용자 요청 · 2026-08-13 반으로).

플레이어만 다치는 세계는 이상하다 — §3-D40이 "길게 빠지는 챔피언은 자리를 비운다"를
플레이어에게 이미 적용했고, 배경 챔피언에게도 같은 일이 일어나야 한다.

**0.10에서 내렸다** (현실 대조). 실측에서 재위의 9.8%가 경기가 아니라 공석으로
끝났는데, 실제로 벨트가 반납되는 일은 그보다 훨씬 드물다 — 역사적으로 1~2% 수준이다.
다만 최근으로 올수록 부상·장기 결장으로 비우는 일이 늘어난 것도 사실이라, 역사값까지
내리지 않고 그 사이인 **5%**로 잡았다. 커리어 한 판에 부상 공석이 한 번쯤 나온다.

공석 자체는 살려 둬야 한다 — §3-D52의 공석 결정전이 그것을 읽는다.
"""


class ReignEnd(StrEnum):
    """재위가 어떻게 끝났는지 (§3-D52·D58)."""

    LOST = "lost"
    """경기에서 졌다. 다음 챔피언이 그를 이긴 것이다."""
    VACATED = "vacated"
    """링 밖의 일로 비웠다 — 은퇴·부상·콜업, 또는 스테이블이 둘을 못 채운다."""
    MEMBER_LEFT = "member_left"
    """팀에서 한 사람이 빠졌다. 스테이블이 있으면 이어받고, 없으면 공석이 된다."""


@dataclass(frozen=True)
class Reign:
    """재위 한 번. **어떻게 끝났는지**를 함께 든다 (§3-D52의 공석 결정전이 그걸 읽는다)."""

    holder: str
    start: int
    ends: int
    vacated: bool = False
    """경기가 아니라 **링 밖의 일**로 끝났는지 — 은퇴 또는 부상.

    졌으면 다음 챔피언이 그를 이긴 것이고, 비웠으면 남은 사람들이 빈자리를 두고 붙는다.
    카드가 이 한 칸으로 두 그림을 나눈다.
    """
    inherited: bool = False
    """**스테이블이 이어받은 재위인지** (§3-D58). 경기로 넘어온 것이 아니라 파트너만
    바뀐 것이라, 카드는 이 밤에 타이틀전을 세우지 않는다."""


@lru_cache(maxsize=8192)
def champion_at(seed: int, week: int, title: Title, *, exclude: str = "") -> str | None:
    """그 주차에 이 벨트를 감고 있는 사람. 명부가 비면 None.

    **캐시한다.** 순수 함수이고(§3-D4) 한 화면이 같은 (시드·주차·벨트)를 여러 번 묻는다 —
    리포트가 벨트 목록과 카드에서, 드래프트가 챔피언 보호에서 각각 부른다. 캐시가 없으면
    그때마다 30년 재위를 다시 걷는다(실측 1.00초 → 0.06초).
    """
    last = _walk(seed, week, title, exclude)
    if last is None or last.ends <= week:
        # **끝난 재위는 주인이 아니다** (§3-D95에서 발견). 연대기가 그 주차 앞에서
        # 멈추는 경우가 있다 — 뽑을 사람이 없거나 옛 주인이 링을 떠났을 때다. 그때
        # 마지막 재위를 그대로 답하면 **은퇴한 챔피언**이 생긴다.
        return None
    return last.holder


def inherited_between(
    seed: int, since: int, until: int, title: Title, *, exclude: str = ""
) -> bool:
    """그 구간에서 **스테이블이 벨트를 이어받았는지** (§3-D58).

    이어받기는 경기가 아니다 — 파트너만 바뀌었으므로 그 밤에 타이틀전을 세우면 안 된다.
    """
    for reign in _reigns(seed, until, title, exclude):
        if reign.inherited and since < reign.start <= until:
            return True
    return False


def vacated_between(
    seed: int, since: int, until: int, title: Title, *, exclude: str = ""
) -> bool:
    """그 구간에서 재위가 **링 밖의 일로** 끝났는지 (§3-D52).

    구간으로 묻는 이유: 계보는 아무 주차에나 바뀌지만 화면은 대회 밤에만 열린다. 지난
    대회와 이번 대회 사이에 벨트가 비었다면, 그 자리를 채우는 경기가 **이번 밤의 일**이다.
    """
    for reign in _reigns(seed, until, title, exclude):
        if reign.vacated and since < reign.ends <= until:
            return True
    return False


def reigns_upto(
    seed: int, week: int, title: Title, *, exclude: str = ""
) -> tuple[Reign, ...]:
    """그 주차까지의 재위 연대기 (§3-D65).

    벨트가 언제 누구에게 넘어갔는지를 **인박스가 읽는다** — 지금까지 그 사실은 카드를
    펼친 사람만 볼 수 있었고, RAW 남성부만 30년에 146번 바뀌는데 뉴스에는 한 줄도
    없었다. 계보는 이미 다 알고 있었다.
    """
    return tuple(_reigns(seed, week, title, exclude))


def _walk(seed: int, week: int, title: Title, exclude: str) -> Reign | None:
    """그 주차를 품는 재위."""
    found: Reign | None = None
    for reign in _reigns(seed, week, title, exclude):
        found = reign
    return found


def _reigns(seed: int, upto: int, title: Title, exclude: str) -> list[Reign]:
    """0주차부터 그 주차까지의 재위 연대기.

    `exclude`는 플레이어의 링네임이다. 실존 선수를 바탕으로 만든 커리어는(§3-D10-1)
    **자기 이름이 명부에 그대로 있을 수 있고**, 그러면 자기 벨트에 도전하게 된다.

    **벨트가 걸린 브랜드에서만 뽑는다** (§3-D53). NXT 벨트를 메인 로스터가 감고 있으면
    그 벨트가 무엇인지가 사라진다. 브랜드 통합 벨트(여성부 태그팀)는 걸러지지 않는다 —
    두 브랜드 중 어느 쪽도 그 벨트의 집이라 좁힐 근거가 없다.
    """
    spec = TITLES[title]
    home = next(iter(spec.brands)) if len(spec.brands) == 1 else None
    tier = (
        TIER_OF[spec.tier] if home is None else roster.tier_in(home, TIER_OF[spec.tier])
    )
    holders = HOLDERS_OF[spec.tier]
    channel = f"{seeded_roll.TITLE_SCENE}:{title.value}"

    cursor = 0
    holder: str | None = None
    inherit: tuple[str, str] | None = None
    reigns: list[Reign] = []
    while True:
        roll = SeededRoll(seed, cursor, channel)
        held = frozenset(members_of(holder or ""))

        def _pool(
            want: RivalTier, at: int = cursor, taken: frozenset[str] = held
        ) -> tuple[str, ...]:
            # 기본값으로 묶는다 — 루프 변수를 그대로 닫으면 나중 회차의 값이 새어 든다.
            return tuple(
                n
                for n in roster.pool_for(spec.gender, want, at, home, seed)
                if n not in taken and n != exclude
            )

        # **가끔은 아래에서 올라온 사람이 벨트를 든다** (§3-D95, 2026-08-19 사용자
        # 요청) — 미드카드가 월드 벨트를, 로우카드가 2선 벨트를 노리는 밤이다.
        # 위상을 아예 안 보면 사용자가 짚은 *"비정상적인 챔피언"*으로 돌아가므로,
        # 넘보는 것은 **한 칸**이고 그것도 다섯에 한 번쯤이다.
        below = RivalTier(max(RivalTier.LOW_CARD, tier - 1))
        reaching = below if below is not tier and roll.chance(UNDERDOG_SHARE) else tier
        pool = _pool(reaching)
        # **빈 칸으로 벨트를 비우지 않는다.** 그 칸에 사람이 없으면 위아래를 차례로
        # 본다 — 벨트에 주인이 없는 세계가 §3-D38이 막으려던 바로 그 상태다.
        for fallback in (tier, below, RivalTier(min(RivalTier.UPPER_CARD, tier + 1))):
            if _pick_holders(pool, holders, roll, spec.tier, seed) is not None:
                break
            pool = _pool(fallback)
        else:
            # **태그 벨트는 짝이 없으면 못 든다**(§3-D58). 위상을 다 훑고도 짝이 안
            # 나오면 그 브랜드·디비전 전체에서 짝을 찾는다 — 벨트를 비우는 것보다
            # 위상을 한 번 접는 편이 낫다.
            pool = tuple(
                dict.fromkeys(name for want in RivalTier for name in _pool(want))
            )
        inherited = False
        if inherit is not None:
            # **스테이블이 벨트를 이어받는다** (§3-D58) — 남은 사람 옆에 같은
            # 스테이블의 동성 선수가 선다. 경기로 넘어간 것이 아니다.
            stayer, stable = inherit
            mates = _stable_mates(pool, stable, exclude=(stayer,), seed=seed)
            if mates:
                holder = PARTNER_JOIN.join((stayer, roll.pick(mates)))
                inherited = True
            else:
                inherit = None
        if not inherited:
            picked = _opening_holder(title, cursor, exclude) or _pick_holders(
                pool, holders, roll, spec.tier, seed
            )
            if picked is not None:
                holder = picked
            elif not _all_active(holder, cursor, seed):
                # **링을 떠난 사람에게 벨트를 다시 들리지 않는다** (§3-D95에서 발견).
                # 새로 뽑지 못했을 때 옛 주인을 그대로 들고 가던 자리인데, 그 주인이
                # 이미 은퇴했으면 "은퇴한 챔피언"이 된다 — §3-D38이 막으려던 상태다.
                return reigns
        if holder is None:
            return reigns
        length, why = _reign_of(
            holder, cursor, _rolled_length(spec.tier, roll), roll, home, seed
        )
        reigns.append(
            Reign(
                holder=holder,
                start=cursor,
                ends=cursor + length,
                vacated=why is ReignEnd.VACATED,
                inherited=inherited,
            )
        )
        if cursor + length > upto:
            return reigns
        cursor += length
        inherit = _inheritor(holder, cursor, why, spec.tier, seed)


def _opening_holder(title: Title, cursor: int, exclude: str) -> str | None:
    """0주차의 주인 (§3-D94, 2026-08-19 사용자 명단). 그 밖의 주차는 `None`이다.

    **첫 재위만 못 박는다.** 사용자가 준 것은 *지금* 누가 들고 있는가이고, 그 뒤의
    계보까지 정해 두면 그건 계보가 아니라 각본이다 — 2년차부터는 그대로 굴린다.

    **내 이름과 겹치면 굴림으로 돌아간다.** §3-D10-1이 실존 선수를 바탕으로 삼게
    해 두었으므로 플레이어가 챔피언과 같은 이름을 쓸 수 있는데, 그러면 계보가 내
    벨트를 남에게 준 것처럼 그린다.
    """
    if cursor != 0:
        return None
    opening = OPENING_CHAMPIONS.get(title)
    if opening is None or exclude and exclude in opening.split(PARTNER_JOIN):
        return None
    return opening


def _all_active(holder: str | None, week: int, seed: int) -> bool:
    """그 주차에 **전원 현역인가.** 아무도 안 뽑혔을 때 옛 주인을 이어도 되는지의 조건이다."""
    if not holder:
        return False
    for name in members_of(holder):
        member = roster.member_of(name, seed)
        if member is not None and not member.is_active_at(week):
            return False
    return True


def _rolled_length(tier: TitleTier, roll: SeededRoll) -> int:
    """이번 재위가 몇 주짜리인지. **긴 재위 밴드를 먼저 굴린다** (§3-D74)."""
    band = LONG_REIGN_WEEKS if roll.chance(LONG_REIGN_CHANCE) else REIGN_WEEKS
    low, high = band[tier]
    return roll.between(low, high)


def _pick_holders(
    pool: tuple[str, ...], count: int, roll: SeededRoll, tier: TitleTier, seed: int = 0
) -> str | None:
    """챔피언 한 명 또는 한 팀. 명단이 모자라면 None.

    **태그 벨트의 짝은 아무나 짜지 못한다** (§3-D58, 2026-08-12 사용자 결정):
    스테이블 소속은 **같은 스테이블 안에서만** 짝을 짜고, 독립 선수는 **스테이블이 없는
    사람들끼리만** 짠다. 스테이블 밖과 손을 잡으면 그 스테이블이 무엇인지가 사라진다.
    """
    if len(pool) < count:
        return None
    if count == 1:
        return roll.pick(pool)

    groups: dict[str, list[str]] = {}
    for name in pool:
        member = roster.member_of(name, seed)
        groups.setdefault(roster.stable_at(member, seed) if member else "", []).append(
            name
        )
    fit = tuple(sorted(key for key, names in groups.items() if len(names) >= count))
    if not fit:
        return None
    chosen = groups[roll.pick(fit)]
    picked: list[str] = []
    for _ in range(count):
        rest = tuple(n for n in chosen if n not in picked)
        picked.append(roll.pick(rest))
    return PARTNER_JOIN.join(picked)


def _stable_mates(
    pool: tuple[str, ...], stable: str, *, exclude: tuple[str, ...], seed: int = 0
) -> tuple[str, ...]:
    """그 명단 안에서 같은 스테이블 사람들 (§3-D58). 독립(`""`)도 한 무리로 본다."""
    return tuple(
        name
        for name in pool
        if name not in exclude
        and (member := roster.member_of(name, seed)) is not None
        and roster.stable_at(member, seed) == stable
    )


def _inheritor(
    holder: str, week: int, why: ReignEnd, tier: TitleTier, seed: int = 0
) -> tuple[str, str] | None:
    """이어받을 자리가 있는지 (§3-D58).

    **한 사람이 빠졌고 남은 사람에게 스테이블이 있으면** 그 스테이블이 벨트를 잇는다.
    빠진 이유가 링 밖의 일(은퇴·부상·콜업)일 때만이다 — 경기로 진 벨트는 이긴 쪽의
    것이지 물려줄 것이 아니다.
    """
    if why is not ReignEnd.MEMBER_LEFT or HOLDERS_OF[tier] < 2:
        return None
    staying = [
        name
        for name in members_of(holder)
        # **시드를 넘긴다** — 가상 선수의 이름은 판마다 다르다(§3-D59). 빠뜨리면
        # 0번 판의 명부에서 찾아 못 찾고, 남은 사람이 조용히 목록에서 빠진다.
        if (member := roster.member_of(name, seed)) is not None
        and member.is_active_at(week)
    ]
    if len(staying) == len(members_of(holder)) and staying:
        # 부상은 명부에 안 남는다(굴림이다) — 그때는 **앞사람이 빠진 것**으로 본다.
        staying = staying[1:]
    if len(staying) != 1:
        return None
    member = roster.member_of(staying[0], seed)
    stable = roster.stable_at(member, seed) if member is not None else ""
    if not stable:
        # **독립 선수는 이어받을 스테이블이 없다.** 그 벨트는 공석이 된다.
        return None
    return staying[0], stable


def members_of(holder: str) -> tuple[str, ...]:
    """챔피언 이름 → 사람들. 태그 벨트는 둘이다 (§3-D57)."""
    return tuple(holder.split(PARTNER_JOIN)) if holder else ()


def holder_label(holder: str, seed: int = 0) -> str:
    """화면에 나갈 이름 (§3-D62). **같은 스테이블 둘이면 팀 이름이다.**

    §3-D57이 태그 벨트를 둘에게 준 뒤로 화면에는 "킷 윌슨 & 엘튼 프린스"가 찍혔다 —
    그 둘의 이름은 **프리티 데들리**다. 명부가 스테이블을 알게 되면서(§3-D58) 그 이름을
    부를 수 있게 됐고, 한글 표기는 §3-D30이 이미 갖고 있었다.

    독립 선수 둘은 팀이 아니므로 "A & B" 그대로다 — 이름 없는 팀을 `Team.label`이
    구성원으로 부르는 것과 같은 규약이다.

    `|`가 든 표기(LWO · OTM)는 **앞의 약칭**을 쓴다. 벨트 옆에 붙는 자리라 좁다.
    """
    people = members_of(holder)
    if len(people) < 2:
        return holder
    stables = {
        roster.stable_at(member, seed)
        for name in people
        if (member := roster.member_of(name, seed)) is not None
    }
    if len(stables) != 1:
        return holder
    stable = next(iter(stables))
    if not stable:
        return holder
    return KOREAN_TEAM_NAMES.get(stable, stable).split("|")[0].strip()


def _reign_of(
    holder: str,
    cursor: int,
    rolled: int,
    roll: SeededRoll,
    home: Brand | None,
    seed: int,
) -> tuple[int, ReignEnd]:
    """(재위 길이, 어떻게 끝났는지).

    **은퇴 주차를 넘기지 않는다.** 이걸 안 하면 링을 떠난 사람이 벨트를 들고 있다 —
    명부에 시간 축을 넣은 이유가(§3-D13-1) 그 자리에서 무너진다. 브랜드로 명단이
    좁아지자(§3-D53) 실제로 여성부 월드 챔피언이 은퇴한 채 벨트를 감고 있었다.

    은퇴가 아니어도 **부상으로 내려놓을 수 있다**(2026-08-12 사용자 요청). 둘 다 결과는
    같다 — 벨트가 비고, 그 자리는 경기로 채워진다(§3-D52).

    **콜업도 같다.** 육성 브랜드의 벨트를 감은 채 메인 로스터로 올라갈 수는 없다
    (§3-D53) — 올라가는 주차에 그 벨트를 두고 간다.
    """
    people = members_of(holder)
    ends: list[int] = []
    for name in people:
        member = roster.member_of(name, seed)
        if member is None:
            continue
        if member.retire_week is not None:
            ends.append(member.retire_week)
        if home is Brand.NXT:
            leaving = roster.call_up_week(member, seed)
            if leaving is not None:
                ends.append(leaving)

    # **한 사람만 빠져도 팀은 그 벨트를 그대로 들 수 없다** — 둘이 들던 것을 하나가
    # 들 수는 없다. 스테이블이 있으면 이어받고(§3-D58), 없으면 공석이 된다.
    leave = min(ends) if ends else None
    solo = len(people) < 2
    if leave is not None and cursor + rolled >= leave:
        return max(
            1, leave - cursor
        ), ReignEnd.VACATED if solo else ReignEnd.MEMBER_LEFT
    if roll.chance(INJURY_CHANCE):
        # 재위 중간에 다친다 — 끝나기 직전에 비우면 그냥 짧은 재위와 구별되지 않는다.
        return max(1, rolled // 2), (ReignEnd.VACATED if solo else ReignEnd.MEMBER_LEFT)
    return rolled, ReignEnd.LOST
