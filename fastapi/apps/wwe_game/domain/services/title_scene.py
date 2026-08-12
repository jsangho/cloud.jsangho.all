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
from wwe_game.domain.constants.roster import RivalTier
from wwe_game.domain.services import seeded_roll
from wwe_game.domain.services.seeded_roll import SeededRoll
from wwe_game.domain.value_objects.title import TITLES, Brand, Title, TitleTier

TIER_OF: Final[dict[TitleTier, RivalTier]] = {
    TitleTier.WORLD: RivalTier.MAIN_EVENT,
    TitleTier.SECONDARY: RivalTier.MIDCARD,
    TitleTier.TAG: RivalTier.MIDCARD,
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

PARTNER_JOIN: Final = " & "
"""두 사람을 한 챔피언으로 부르는 이음말. `Team.label`이 이름 없는 팀에 쓰는 것과 같다."""

REIGN_WEEKS: Final[dict[TitleTier, tuple[int, int]]] = {
    TitleTier.WORLD: (26, 78),
    TitleTier.SECONDARY: (13, 45),
    TitleTier.TAG: (13, 40),
}
"""계층별 재위 기간(주). **위로 갈수록 길다.**

월드 벨트가 6개월~1년 반이라는 것은 실제 평균에 맞춘 값이다. 짧게 두면 30년 커리어에
챔피언이 60명 지나가 "누구의 벨트인가"가 다시 흐려진다 — 이 모듈을 만든 이유가 그것이다.
"""


INJURY_CHANCE: Final = 0.10
"""재위가 **부상으로** 끊길 확률 (2026-08-12 사용자 요청).

플레이어만 다치는 세계는 이상하다 — §3-D40이 "길게 빠지는 챔피언은 자리를 비운다"를
플레이어에게 이미 적용했고, 배경 챔피언에게도 같은 일이 일어나야 한다.

열에 하나로 잡은 이유: 30년이면 월드 벨트의 재위가 스무 번 남짓이라, 이 값이면 커리어
한 판에 부상 공석이 두어 번 나온다. 더 올리면 벨트가 링 밖에서 더 자주 바뀐다.
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
    return last.holder if last is not None else None


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
    low, high = REIGN_WEEKS[spec.tier]
    channel = f"{seeded_roll.TITLE_SCENE}:{title.value}"

    cursor = 0
    holder: str | None = None
    inherit: tuple[str, str] | None = None
    reigns: list[Reign] = []
    while True:
        roll = SeededRoll(seed, cursor, channel)
        held = frozenset(members_of(holder or ""))
        pool = tuple(
            n
            for n in roster.pool_for(spec.gender, tier, cursor, home, seed)
            if n not in held and n != exclude
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
            picked = _pick_holders(pool, holders, roll, spec.tier, seed)
            if picked is not None:
                holder = picked
        if holder is None:
            return reigns
        length, why = _reign_of(
            holder, cursor, roll.between(low, high), roll, home, seed
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
        groups.setdefault(member.stable if member else "", []).append(name)
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
        and member.stable == stable
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
        if (member := roster.member_of(name)) is not None and member.is_active_at(week)
    ]
    if len(staying) == len(members_of(holder)) and staying:
        # 부상은 명부에 안 남는다(굴림이다) — 그때는 **앞사람이 빠진 것**으로 본다.
        staying = staying[1:]
    if len(staying) != 1:
        return None
    member = roster.member_of(staying[0], seed)
    if member is None or not member.stable:
        # **독립 선수는 이어받을 스테이블이 없다.** 그 벨트는 공석이 된다.
        return None
    return staying[0], member.stable


def members_of(holder: str) -> tuple[str, ...]:
    """챔피언 이름 → 사람들. 태그 벨트는 둘이다 (§3-D57)."""
    return tuple(holder.split(PARTNER_JOIN)) if holder else ()


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
            leaving = roster.call_up_week(member)
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
