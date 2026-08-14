"""그 밤의 카드 — 나 말고도 그날 링에 오른 사람들 (하네스 §3-D52).

리포트(§3-D45)는 그 밤을 한 장으로 보여주겠다고 만들었는데, 정작 담긴 것은 **벨트
목록**뿐이었다. 대회 이름 아래에 챔피언 셋이 적히고 끝이라, "그날 카드가 어땠지"에
답하지 못했다 — 내 경기 한 줄 말고는 그 밤에 아무 일도 없었다.

## 저장하지 않는다

`title_scene`(§3-D38) · `rivalry_scene`(§3-D44)과 같은 방식이다. 시드와 주차에서 매번
되짚는다. 카드를 세이브에 담으면 30년치 대회 720개의 경기 4천 줄이 세이브에 붙고,
진행 한 번이 세이브를 통째로 다시 쓰는 구조(§3-D6)에서 그건 그대로 비용이 된다.

## 벨트 계보를 **다시 굴리지 않는다**

이 모듈의 핵심 규약이다. 타이틀전의 결과는 여기서 정하지 않고 `title_scene`에 묻는다 —
그 주차의 챔피언이 앞 주차와 다르면 **그날 밤 벨트가 넘어간 것**이고, 같으면 방어다.
따로 굴리면 리포트 안에서 "오늘 X가 벨트를 뺏었다"와 "그날의 벨트: Y" 두 줄이 서로를
부정한다. 같은 사실을 두 곳이 들고 있으면 반드시 어긋난다(§3-D38이 이미 겪은 것).

## 내 경기는 여기 없다

카드는 **배경의 경기만** 만든다. 내 경기는 바로 위 로그 줄에 있고, 화면이 그것을
따로 그린다(§3-D51에서 리포트가 내 기록을 되풀이하지 않기로 한 것과 같은 이유).
그래서 나와 그날 내 상대는 명부에서 빼고 뽑는다 — 빼지 않으면 **내 상대가 같은 밤에
두 경기를 뛴다.**
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final

from wwe_game.domain.constants import roster
from wwe_game.domain.constants.career_clock import WEEKS_PER_YEAR
from wwe_game.domain.constants.ple_calendar import calendar_for
from wwe_game.domain.constants.roster import RivalTier
from wwe_game.domain.services import match_rating, rivalry_scene, title_scene
from wwe_game.domain.services.rivalry_scene import RivalryBeat
from wwe_game.domain.services.seeded_roll import SeededRoll
from wwe_game.domain.value_objects.match_kind import (
    STIPULATION_ODDS,
    MatchKind,
    format_of,
)
from wwe_game.domain.value_objects.title import TITLES, Brand, Title, titles_of
from wwe_game.domain.value_objects.wrestler_identity import Gender

CHANNEL: Final = "show_card"
"""**새 채널이다.** 기존 채널을 나눠 쓰면 카드를 한 줄 더 뽑는 순간 그 뒤의 재위·대립이
통째로 밀려 저장된 세이브가 전부 다른 커리어가 된다(`seeded_roll` 모듈 설명)."""

CARD_SIZE: Final[dict[str, int]] = {"major": 6, "ple": 5, "special": 4, "weekly": 4}
"""그 밤에 서는 경기 수 — **밤의 크기가 곧 카드의 크기다** (§3-D55·D60).

처음엔 타이틀전 + 채움 두셋으로 잡아 실측 평균이 4.2경기였는데, 실제 PLE는 일곱에서
아홉이고 무엇보다 **레슬매니아가 평범한 밤과 같은 크기로 섰다.** 목표 총량으로 바꿔
대형 대회가 실제로 커지게 했다.

열을 넘기지는 않는다 — 리포트는 로그 한 줄을 펼친 자리라 그보다 길면 일정 탭이 그 한
밤으로 덮인다(§3-D34가 럼블 59줄에서 겪은 것).

주간 방송이 넷인 이유는 그것이 **매주 서는 밤**이기 때문이다 — 대회와 같은 크기로 두면
1560주가 전부 대회가 되고, §3-D45가 "그건 로그다"라고 한 그 자리로 돌아간다.

**실제 크기에 맞췄다** (2026-08-12 사용자: "보통 PLE는 5~6경기"). 처음엔 대형 여덟으로
잡았는데 그러면 이틀 대회가 열여섯 줄이 됐다.
"""

TWO_NIGHT_CARD: Final[tuple[int, int]] = (12, 14)
"""이틀에 걸쳐 여는 밤의 경기 수 (2026-08-12 사용자: "2일차 경기는 12~14경기").

하루치의 곱절이 아니라 따로 잡는다 — 이틀이어도 같은 카드를 두 번 세우는 것이 아니라
한 카드를 이틀에 나눠 세우는 것이라, 곱절보다 조금 적다.
"""

ONE_ON_ONE_STIPULATIONS: Final[tuple[tuple[MatchKind, int], ...]] = tuple(
    (kind, weight) for kind, weight in STIPULATION_ODDS if format_of(kind).field == 2
)
"""배경 경기가 걸 수 있는 형식 — **둘이 붙는 것만** (§3-D55).

카드의 배경 경기는 1대1이라 트리플 스렛·페이탈 포 웨이·래더를 붙이면 이름 둘만 적힌
4인 경기가 된다. 실제로 그렇게 나왔다("브론슨 리드 vs 크루즈 델 토로 [페이탈 포 웨이]").
인원이 맞는 형식만 남긴다 — 여럿이 붙는 밤은 참가자를 그만큼 세울 수 있을 때의 일이다.
"""

STIPULATION_CHANCE: Final[dict[bool, float]] = {True: 0.28, False: 0.12}
"""배경 경기가 **특수 경기**일 확률 — 타이틀전이면 높다 (§3-D55).

내 경기는 21종 형식을 갖는데(§3-D32) 배경은 전부 싱글로 읽혔다. 같은 세계에서 나만
철창에 들어가는 셈이다. 다만 흔해지면 안 된다: 매 경기가 스티플레이션이면 그건 그냥
규칙이 없는 세계다.
"""

DEFENSE_CHANCE: Final[dict[str, float]] = {
    "major": 0.55,
    "ple": 0.55,
    "special": 0.35,
    "weekly": 0.08,
}
"""벨트가 안 넘어간 밤에 그래도 방어전이 열릴 확률.

1.0으로 두면 모든 대회에서 모든 벨트가 방어돼 카드가 늘 똑같아진다. 실제로도 벨트는
매 대회 걸리지 않는다 — 안 걸린 밤은 그 벨트 이야기가 쉬어 가는 밤이다.

**주간 방송은 훨씬 낮다** (§3-D60). TV에서 벨트가 걸리는 밤은 드물고, 잦으면 대회가
무엇 때문에 있는지가 사라진다.
"""


@dataclass(frozen=True)
class CardMatch:
    """카드 한 경기. **문장이 아니라 구조로 준다** — 문구는 화면이 만든다(§3-D34)."""

    left: str
    right: str
    winner: str
    """`left`·`right` 중 하나. 무승부는 만들지 않는다 — 배경 경기의 무승부는
    이야기가 아니라 공백이라, 화면에 한 줄을 쓸 값어치가 없다."""
    title: str | None = None
    """걸린 벨트의 표시 이름. 타이틀전이 아니면 None."""
    stars: float = 0.0
    """그 경기의 별점 (§3-D56). 0.25 단위, 0~5."""
    match_label: str | None = None
    """경기 형식 (§3-D55). **싱글이면 None이다** — 화면이 "싱글 매치"를 줄마다 쓰지
    않게 한다. 내 로그 줄이 특수 경기에만 형식을 붙이는 것과 같은 규약이다."""
    changed_hands: bool = False
    """그날 밤 벨트에 새 주인이 생겼는지. `title`이 있을 때만 뜻이 있다."""
    feud: bool = False
    """쌓인 대립의 결착인지 (§3-D66). 별점만 읽는다 — 화면에는 안 쓴다."""
    vacant: bool = False
    """**빈 벨트를 두고 붙은 경기인지** (2026-08-12 사용자 결정).

    앞 챔피언이 링을 떠나면 벨트는 그와 함께 사라지는 것이 아니라 공석이 된다. 그 자리는
    누가 그냥 물려받는 것이 아니라 **경기로 채워진다** — 떠난 사람을 링에 세울 수는 없다.
    """


def card_for(
    seed: int,
    week: int,
    gender: Gender,
    brand: Brand,
    *,
    stage: str = "ple",
    nights: int = 1,
    player: str = "",
    busy: tuple[str, ...] = (),
    skip_titles: frozenset[Title] = frozenset(),
) -> tuple[CardMatch, ...]:
    """그 밤의 배경 카드. 오프너부터 순서대로.

    `stage`는 그 밤의 크기다 — `major` · `ple` · `special` · `weekly` (§3-D60).

    `gender`는 **내 디비전**이다 — 카드는 두 디비전을 다 세우되(§3-D55) 나와 내 상대,
    내가 건드린 벨트를 빼는 일은 내 쪽에만 해당한다.

    `busy`는 그날 이미 링에 올랐지만 화면이 따로 그리는 사람들이다 — 내 상대. `player`는
    나이고, 계보에 물을 때도 빼야 해서 따로 받는다(`title_scene.champion_at`의 규약).

    `skip_titles`는 **이 카드가 건드리면 안 되는 벨트**다 — 내가 감고 있거나 그날 내가
    도전한 벨트. 빼지 않으면 "그날의 벨트: 나"와 "카드: 챔피언 X 방어 성공"이 한 화면에서
    서로를 부정한다.

    순수 함수라 같은 시드·주차는 언제 물어도 같은 카드를 만든다(§3-D4).
    """
    roll = SeededRoll(seed, week, CHANNEL)
    taken = [name for name in (player, *busy) if name]
    matches: list[CardMatch] = []
    # **내 디비전이 먼저다.** 카드가 목표 수에서 잘릴 때 남의 디비전이 먼저 밀린다 —
    # 내 밤의 리포트라 그쪽이 맞다.
    divisions = (gender, _other(gender))

    for division in divisions:
        for title in titles_of(brand, division):
            if division is gender and title in skip_titles:
                continue
            bout = _title_bout(
                seed, week, title, brand, division, stage, roll, player, tuple(taken)
            )
            if bout is None:
                continue
            # **타이틀전의 양쪽은 계보에서 온다** — 명단에서 뽑는 것이 아니라 `taken`을
            # 거치지 않는다. 계보는 벨트마다 따로 걸으므로 한 사람이 두 벨트를 감을 수
            # 있고, 그러면 그가 같은 밤에 두 번 링에 선다. 그 벨트는 이 밤을 쉬어 간다.
            people = [
                *title_scene.members_of(bout.left),
                *title_scene.members_of(bout.right),
            ]
            if any(name in taken for name in people):
                continue
            matches.append(bout)
            taken.extend(people)

    for division in divisions:
        for pair in _feud_pairs(seed, week, division, brand, player, tuple(taken)):
            matches.append(_settle(pair, brand, roll, feud=True))
            taken.extend(pair)

    # 목표 수까지 채운다. 디비전을 번갈아 집어 한쪽만 늘어나지 않게 한다.
    # **이틀이면 따로 잡는다** (§3-D71). 레슬매니아가 하루짜리와 같은 크기면 이틀이라는
    # 사실이 화면 어디에도 안 남는다.
    target = roll.between(*TWO_NIGHT_CARD) if nights > 1 else CARD_SIZE[stage]
    dry: set[Gender] = set()
    while len(matches) < target and len(dry) < len(divisions):
        division = divisions[len(matches) % len(divisions)]
        if division in dry:
            division = _other(division)
        pair = _pick_pair(seed, week, division, brand, tuple(taken), roll)
        if pair is None:
            dry.add(division)
            continue
        matches.append(_settle(pair, brand, roll))
        taken.extend(pair)

    # 오프너가 앞, 타이틀전이 뒤다. 카드는 위로 갈수록 커진다.
    #
    # **팀 이름은 맨 마지막에 붙인다** (§3-D62). 그 전까지는 사람 이름으로 다뤄야
    # 한다 — 같은 밤에 두 번 서지 않는지, 그 브랜드 사람인지, 별점의 등급은 무엇인지가
    # 전부 사람 단위의 물음이다.
    return tuple(
        _named(_rate(seed, week, m, stage=stage), seed) for m in reversed(matches)
    )


def _named(match: CardMatch, seed: int) -> CardMatch:
    """카드 한 줄의 양쪽을 화면에 나갈 이름으로 (§3-D62)."""
    left = title_scene.holder_label(match.left, seed)
    right = title_scene.holder_label(match.right, seed)
    winner = left if match.winner == match.left else right
    return replace(match, left=left, right=right, winner=winner)


TIER_RING: Final[dict[RivalTier, int]] = {
    RivalTier.PROSPECT: 55,
    RivalTier.MIDCARD: 70,
    RivalTier.MAIN_EVENT: 85,
}
"""배경 선수의 경기력 대역 (§3-D56). 명부는 스탯을 들지 않으므로 **등급이 곧 실력**이다 —
별점에만 쓰이는 값이고 승패 판정에는 닿지 않는다."""


def _rate(
    seed: int,
    week: int,
    match: CardMatch,
    *,
    stage: str,
) -> CardMatch:
    """그 경기에 별점을 붙인다 (§3-D56). **판정이 끝난 뒤에 매긴다.**"""
    tiers = [
        roster.tier_at(member, week)
        for label in (match.left, match.right)
        for name in title_scene.members_of(label)
        if (member := roster.member_of(name, seed)) is not None
    ] or [RivalTier.MIDCARD]
    stars = match_rating.rate(
        seed,
        week,
        in_ring=sum(TIER_RING[t] for t in tiers) // len(tiers),
        rival_tier=max(tiers),
        stage=None if stage == "weekly" else stage,
        has_title=match.title is not None,
        has_stipulation=match.match_label is not None,
        has_feud=match.feud,
        salt=f"{match.left}:{match.right}",
    )
    return replace(match, stars=stars)


def _other(gender: Gender) -> Gender:
    return Gender.FEMALE if gender is Gender.MALE else Gender.MALE


def _stipulation(roll: SeededRoll, *, for_title: bool) -> str | None:
    """그 경기의 형식. **싱글이면 None** (§3-D55).

    가중치는 내 경기가 쓰는 표(`STIPULATION_ODDS`)에서 **둘이 붙는 것만** 걸러 쓴다 —
    배경이 다른 표를 쓰면 같은 세계에서 두 종류의 프로레슬링이 열린다.
    """
    if not roll.chance(STIPULATION_CHANCE[for_title]):
        return None
    total = sum(weight for _, weight in ONE_ON_ONE_STIPULATIONS)
    cut = roll.between(1, total)
    for kind, weight in ONE_ON_ONE_STIPULATIONS:
        cut -= weight
        if cut <= 0:
            return format_of(kind).label
    return None


def _title_bout(
    seed: int,
    week: int,
    title: Title,
    brand: Brand,
    division: Gender,
    stage: str,
    roll: SeededRoll,
    player: str,
    taken: tuple[str, ...],
) -> CardMatch | None:
    """그 벨트의 그날 밤. **계보에 묻고, 굴리지 않는다.**

    앞 주차와 챔피언이 다르면 그날 넘어간 것이다 — 도전자를 새로 뽑지 않고 **새
    챔피언 본인**을 세운다. 그래야 "그날의 벨트"에 적힌 이름과 카드가 같은 말을 한다.
    """
    holder = title_scene.champion_at(seed, week, title, exclude=player)
    if holder is None:
        return None
    # **브랜드 통합 벨트는 챔피언이 선 밤에만 걸린다** (§3-D55). 여성부 태그팀은 두
    # 브랜드에 걸쳐 있어(§3-D38) 계보가 브랜드를 안 가린다 — 그대로 두면 RAW 챔피언이
    # 스맥다운 카드에 선다. **팀이면 전원이 그 브랜드에 있어야 한다**(§3-D57): 둘이
    # 갈라져 있으면 그 벨트는 이 밤을 쉬어 간다.
    for name in title_scene.members_of(holder):
        champion = roster.member_of(name, seed)
        if champion is not None and roster.brand_at(champion, week, seed) is not brand:
            return None
    before = title_scene.champion_at(
        seed, _last_show(brand, week, seed), title, exclude=player
    )
    display = TITLES[title].display_name

    if before is not None and before != holder:
        since = _last_show(brand, week, seed)
        if title_scene.inherited_between(seed, since, week, title, exclude=player):
            # **스테이블이 이어받았다** (§3-D58) — 경기가 아니라 파트너가 바뀐 것이다.
            # 그 밤에 타이틀전을 세우면 있지도 않은 경기를 적는 셈이 된다.
            return None
        vacated = title_scene.vacated_between(seed, since, week, title, exclude=player)
        if not vacated and _still_there(before, week, brand, seed):
            return CardMatch(
                left=before,
                right=holder,
                winner=holder,
                title=display,
                changed_hands=True,
            )
        # **앞 챔피언이 링을 떠났거나 다쳐서 반납했다.** 벨트는 그와 함께 사라지지 않고
        # 비어 있을 뿐이라, 남은 사람들이 그 자리를 두고 붙는다 — 링에 못 서는 사람을
        # 다시 세울 수는 없다 (2026-08-12 사용자 결정).
        rival = _pick_side(
            seed,
            week,
            title,
            division,
            brand,
            (*taken, *title_scene.members_of(holder)),
            roll,
        )
        if rival is None:
            return None
        return CardMatch(
            left=holder,
            right=rival,
            winner=holder,
            title=display,
            changed_hands=True,
            vacant=True,
            match_label=_stipulation(roll, for_title=True),
        )
    if not roll.chance(DEFENSE_CHANCE[stage]):
        return None
    challenger = _pick_side(
        seed,
        week,
        title,
        division,
        brand,
        (*taken, *title_scene.members_of(holder)),
        roll,
    )
    if challenger is None:
        return None
    return CardMatch(
        left=holder,
        right=challenger,
        winner=holder,
        title=display,
        match_label=_stipulation(roll, for_title=True),
    )


def _pick_side(
    seed: int,
    week: int,
    title: Title,
    division: Gender,
    brand: Brand,
    taken: tuple[str, ...],
    roll: SeededRoll,
) -> str | None:
    """타이틀전의 도전 쪽. **태그 벨트면 둘을 뽑아 짝으로 세운다** (§3-D57)."""
    tier = roster.tier_in(brand, title_scene.TIER_OF[TITLES[title].tier])
    picked: list[str] = []
    for _ in range(title_scene.HOLDERS_OF[TITLES[title].tier]):
        name = _pick_one(seed, week, division, brand, (*taken, *picked), tier, roll)
        if name is None:
            return None
        picked.append(name)
    return title_scene.PARTNER_JOIN.join(picked)


def _feud_pairs(
    seed: int,
    week: int,
    gender: Gender,
    brand: Brand,
    player: str,
    taken: tuple[str, ...],
) -> tuple[tuple[str, str], ...]:
    """그 주차에 살아 있는 배경 대립 (§3-D44).

    **연대기를 다시 만들지 않고 읽는다.** 시작 사건이 있고 끝 사건이 아직 없는 짝이
    곧 살아 있는 대립이다 — 대립이 도는 중이면 그 둘은 그날 카드에서 붙는다.
    """
    started: list[tuple[str, str]] = []
    for item in rivalry_scene.chronicle(
        seed, week, gender, exclude=player, brand=brand
    ):
        if item.beat is RivalryBeat.STARTED:
            started.append(item.names)
        elif item.names in started:
            started.remove(item.names)
    # **그 밤의 브랜드를 다시 본다.** 대립은 시작한 주차의 명단에서 뽑히는데(§3-D44)
    # 그 뒤에 한쪽이 콜업되거나 트레이드되면(§3-D53·D63) 짝이 두 브랜드로 갈린다 —
    # 그대로 세우면 남의 브랜드 선수가 이 카드에 선다.
    return tuple(
        pair
        for pair in started
        if pair[0] not in taken
        and pair[1] not in taken
        and all(_stands_on(name, week, brand, seed) for name in pair)
    )


def _stands_on(name: str, week: int, brand: Brand, seed: int) -> bool:
    """그 주차에 그 브랜드에 선 사람인지."""
    member = roster.member_of(name, seed)
    return (
        member is not None
        and member.is_active_at(week)
        and roster.brand_at(member, week, seed) is brand
    )


def _last_show(brand: Brand, week: int, seed: int) -> int:
    """그 브랜드의 **직전 대회 주차**. 없으면 0(커리어 시작 전)이다.

    앞 주차(`week - 1`)와 견주면 안 된다 — 계보는 아무 주차에나 바뀔 수 있고(§3-D38),
    그러면 벨트가 화요일에 넘어가고 대회 카드에는 "방어전"만 남는다. **벨트는 대회에서
    바뀐다**가 이 게임이 보여줘야 하는 그림이라, 지난 대회 이후의 변화를 그 밤에 몰아
    보여준다.
    """
    calendar = calendar_for(brand, seed)
    for back in range(week - 1, max(-1, week - WEEKS_PER_YEAR - 1), -1):
        if back > 0 and calendar.is_show_week(back):
            return back
    return 0


def _still_there(label: str, week: int, brand: Brand, seed: int = 0) -> bool:
    """그 주차에 **그 브랜드 링에** 아직 있는지. 팀이면 전원이 있어야 한다 (§3-D57).

    은퇴만 보면 안 된다 — 콜업이나 트레이드로 브랜드를 떠난 사람도 이 밤에는 설 수
    없다(§3-D53·D63). 실제로 NXT 카드에 콜업된 앞 챔피언이 섰다. 명부 밖 이름
    (플레이어)은 없는 것으로 본다.
    """
    people = title_scene.members_of(label)
    return bool(people) and all(_stands_on(name, week, brand, seed) for name in people)


def _settle(
    pair: tuple[str, str], brand: Brand, roll: SeededRoll, *, feud: bool = False
) -> CardMatch:
    left, right = pair
    return CardMatch(
        left=left,
        right=right,
        winner=roll.pick((left, right)),
        feud=feud,
        match_label=_stipulation(roll, for_title=False),
    )


def _pick_pair(
    seed: int,
    week: int,
    gender: Gender,
    brand: Brand,
    taken: tuple[str, ...],
    roll: SeededRoll,
) -> tuple[str, str] | None:
    """카드를 채우는 한 경기. 그 브랜드의 아랫단에서 뽑는다 (§3-D53)."""
    tier = roster.tier_in(brand, RivalTier.MIDCARD)
    first = _pick_one(seed, week, gender, brand, taken, tier, roll)
    if first is None:
        return None
    second = _pick_one(seed, week, gender, brand, (*taken, first), tier, roll)
    if second is None:
        return None
    return first, second


def _pick_one(
    seed: int,
    week: int,
    gender: Gender,
    brand: Brand,
    taken: tuple[str, ...],
    tier: RivalTier,
    roll: SeededRoll,
) -> str | None:
    pool = tuple(
        n for n in roster.pool_for(gender, tier, week, brand, seed) if n not in taken
    )
    return roll.pick(pool) if pool else None
