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

from dataclasses import dataclass
from typing import Final

from wwe_game.domain.constants import roster
from wwe_game.domain.constants.career_clock import WEEKS_PER_YEAR
from wwe_game.domain.constants.ple_calendar import calendar_for
from wwe_game.domain.constants.roster import RivalTier
from wwe_game.domain.services import rivalry_scene, title_scene
from wwe_game.domain.services.rivalry_scene import RivalryBeat
from wwe_game.domain.services.seeded_roll import SeededRoll
from wwe_game.domain.value_objects.title import TITLES, Brand, Title, titles_of
from wwe_game.domain.value_objects.wrestler_identity import Gender

CHANNEL: Final = "show_card"
"""**새 채널이다.** 기존 채널을 나눠 쓰면 카드를 한 줄 더 뽑는 순간 그 뒤의 재위·대립이
통째로 밀려 저장된 세이브가 전부 다른 커리어가 된다(`seeded_roll` 모듈 설명)."""

FILLER_MATCHES: Final[dict[bool, int]] = {True: 3, False: 2}
"""타이틀전 말고 더 채울 경기 수 — 대형 대회면 셋, 아니면 둘.

레슬매니아를 여덟 경기로 채우고 싶은 유혹이 있지만, 리포트는 로그 한 줄을 펼친
자리라 열 줄이 넘어가면 일정 탭이 그 한 밤으로 덮인다(§3-D34가 럼블 59줄에서 겪은 것).
"""

DEFENSE_CHANCE: Final = 0.55
"""벨트가 안 넘어간 밤에 그래도 방어전이 열릴 확률.

1.0으로 두면 모든 대회에서 모든 벨트가 방어돼 카드가 늘 똑같아진다. 실제로도 벨트는
매 대회 걸리지 않는다 — 안 걸린 밤은 그 벨트 이야기가 쉬어 가는 밤이다.
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
    changed_hands: bool = False
    """그날 밤 벨트에 새 주인이 생겼는지. `title`이 있을 때만 뜻이 있다."""
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
    is_major: bool,
    player: str = "",
    busy: tuple[str, ...] = (),
    skip_titles: frozenset[Title] = frozenset(),
) -> tuple[CardMatch, ...]:
    """그 밤의 배경 카드. 오프너부터 순서대로.

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

    for title in titles_of(brand, gender):
        if title in skip_titles:
            continue
        bout = _title_bout(seed, week, title, brand, roll, player, tuple(taken))
        if bout is None:
            continue
        # **타이틀전의 양쪽은 계보에서 온다** — 명단에서 뽑는 것이 아니라 `taken`을
        # 거치지 않는다. 계보는 벨트마다 따로 걸으므로 한 사람이 두 벨트를 감을 수 있고,
        # 그러면 그가 같은 밤에 두 번 링에 선다. 그 벨트는 이 밤을 쉬어 간다.
        if bout.left in taken or bout.right in taken:
            continue
        matches.append(bout)
        taken.extend((bout.left, bout.right))

    for pair in _feud_pairs(seed, week, gender, brand, player, tuple(taken)):
        matches.append(_settle(pair, roll))
        taken.extend(pair)

    for _ in range(FILLER_MATCHES[is_major]):
        pair = _pick_pair(seed, week, gender, brand, tuple(taken), roll)
        if pair is None:
            break
        matches.append(_settle(pair, roll))
        taken.extend(pair)

    # 오프너가 앞, 타이틀전이 뒤다. 카드는 위로 갈수록 커진다.
    return tuple(reversed(matches))


def _title_bout(
    seed: int,
    week: int,
    title: Title,
    brand: Brand,
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
    before = title_scene.champion_at(
        seed, _last_show(brand, week), title, exclude=player
    )
    display = TITLES[title].display_name

    if before is not None and before != holder:
        vacated = title_scene.vacated_between(
            seed, _last_show(brand, week), week, title, exclude=player
        )
        if not vacated and _still_there(before, week):
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
        rival = _pick_one(
            seed,
            week,
            TITLES[title].gender,
            brand,
            (*taken, holder),
            roster.tier_in(brand, title_scene.TIER_OF[TITLES[title].tier]),
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
        )
    if not roll.chance(DEFENSE_CHANCE):
        return None
    challenger = _pick_one(
        seed,
        week,
        TITLES[title].gender,
        brand,
        (*taken, holder),
        roster.tier_in(brand, title_scene.TIER_OF[TITLES[title].tier]),
        roll,
    )
    if challenger is None:
        return None
    return CardMatch(left=holder, right=challenger, winner=holder, title=display)


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
    return tuple(
        pair for pair in started if pair[0] not in taken and pair[1] not in taken
    )


def _last_show(brand: Brand, week: int) -> int:
    """그 브랜드의 **직전 대회 주차**. 없으면 0(커리어 시작 전)이다.

    앞 주차(`week - 1`)와 견주면 안 된다 — 계보는 아무 주차에나 바뀔 수 있고(§3-D38),
    그러면 벨트가 화요일에 넘어가고 대회 카드에는 "방어전"만 남는다. **벨트는 대회에서
    바뀐다**가 이 게임이 보여줘야 하는 그림이라, 지난 대회 이후의 변화를 그 밤에 몰아
    보여준다.
    """
    calendar = calendar_for(brand)
    for back in range(week - 1, max(-1, week - WEEKS_PER_YEAR - 1), -1):
        if back > 0 and calendar.is_show_week(back):
            return back
    return 0


def _still_there(name: str, week: int) -> bool:
    """그 주차에 아직 링에 있는 사람인지. 명부 밖 이름(플레이어)은 없는 것으로 본다."""
    member = roster.member_of(name)
    return member is not None and member.is_active_at(week)


def _settle(pair: tuple[str, str], roll: SeededRoll) -> CardMatch:
    left, right = pair
    return CardMatch(left=left, right=right, winner=roll.pick((left, right)))


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
