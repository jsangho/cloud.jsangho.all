"""링 밖의 사람들이 서는 자리 (하네스 §3-D93).

명부는 `constants/staff.py`(생성물)이고, **누가 언제 나오는지를 정하는 것이 여기다.**

## 판정에 닿지 않는다

이 파일의 어느 함수도 승패·별점·부상·돈을 만들지 않는다. 고르는 것은 **이름**뿐이고,
그 이름이 화면과 기사에 적힌다 — §3-D88(피니셔)·§3-D91(시그니처)이 그은 선과 같다.

## 이름을 굴릴 때는 주차로 굴린다

해설·심판·링 아나운서는 주차마다 돌아간다. 시드와 주차로만 굴리므로 **같은 밤을 다시
열면 같은 사람이 서 있다**(§3-D4). 채널을 따로 두는 이유는 §3-D87과 같다 — 여기서 한
번 더 굴리는 것만으로 그 주의 경기 결과가 밀리면 안 된다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from wwe_game.domain.constants import staff
from wwe_game.domain.constants.career_clock import WEEKS_PER_YEAR
from wwe_game.domain.constants.staff import StaffMember, StaffRole
from wwe_game.domain.services.seeded_roll import SeededRoll

CHANNEL: Final = "staff"
"""링 밖 사람을 고르는 채널. **경기 굴림과 완전히 갈라 둔다.**"""

PRESIDENT: Final = "President"
"""이 직함으로 **시작하는** 사람은 협상 자리에 안 나온다 (2026-08-19 사용자 결정).

*"재계약할 때도 President 말고 나랑 대화하는 거야"* — 회사의 얼굴은 발표를 하고,
계약서를 사이에 두고 마주 앉는 것은 인재 담당 쪽이다.

**부사장까지 걸러 내면 안 된다.** 처음에 `in`으로 찾았더니 *Senior Vice President of
Talent Development*(숀 마이클스)과 *Vice President …*(윌리엄 리갈)이 함께 빠졌고,
그러면 NXT 계약을 육성 총괄이 맡는다는 규칙이 영영 안 걸린다.
"""


@dataclass(frozen=True)
class MatchCrew:
    """그 밤에 링을 둘러싼 사람들 (§3-D93).

    **경기 전 정보창이 이걸 그대로 읽는다** — 누가 중계하고, 누가 세고, 누가 소개하고,
    누구를 옆에 세우고 나왔는가.
    """

    gm: str = ""
    """브랜드 총괄 겸 스토리 총괄. 그 밤의 대진을 짠 사람이다."""
    commentators: tuple[str, ...] = ()
    ring_announcer: str = ""
    """**챔피언십 경기에만 채운다** — 벨트가 걸린 밤에는 소개가 먼저다."""
    referee: str = ""
    player_manager: str = ""
    """내 옆에 서는 사람. 정보창에 `w/`로 붙는다."""
    rival_manager: str = ""


def _roll(seed: int, week: int, salt: str) -> SeededRoll:
    return SeededRoll(seed + len(salt), week, CHANNEL)


def _pick(people: tuple[StaffMember, ...], seed: int, week: int, salt: str) -> str:
    """그 주차의 한 사람. 비어 있으면 빈 문자열이다 — **없는 사람을 지어내지 않는다.**"""
    if not people:
        return ""
    return _roll(seed, week, salt).pick(people).name


def gm_of(brand: str) -> str:
    """그 브랜드의 GM. **굴리지 않는다** — 한 브랜드에 한 명이고 해마다 바뀌지 않는다."""
    found = staff.for_brand(brand, StaffRole.GM)
    return found[0].name if found else ""


def commentators_of(brand: str) -> tuple[str, ...]:
    """중계석. **순서가 고정이다** — 원본에 적힌 차례가 곧 지정석이다."""
    return tuple(m.name for m in staff.for_brand(brand, StaffRole.COMMENTATOR))


def ring_announcer_of(brand: str, week: int, seed: int) -> str:
    return _pick(staff.for_brand(brand, StaffRole.RING_ANNOUNCER), seed, week, "ann")


def interviewer_of(brand: str, week: int, seed: int) -> str:
    """그 주의 백스테이지 인터뷰어 (§3-D93 규칙 5). 기사에 이름이 남는다."""
    return _pick(staff.for_brand(brand, StaffRole.INTERVIEWER), seed, week, "int")


def referee_of(brand: str, week: int, seed: int, *, title_match: bool = False) -> str:
    """그 경기의 심판. **타이틀전에는 시니어가 선다.**

    실제로도 큰 경기에는 경력이 긴 심판이 배정된다 — 데이터가 이미 `Senior`를 들고
    있어서(채드 패튼·찰스 로빈슨·아드리안 버틀러) 규칙을 새로 만들지 않아도 된다.
    """
    people = staff.for_brand(brand, StaffRole.REFEREE)
    if title_match:
        senior = tuple(m for m in people if m.senior)
        if senior:
            return senior[0].name
    return _pick(people, seed, week, "ref")


def manager_of(who: str, stable: str = "") -> str:
    """그 사람 옆에 서는 매니저 (§3-D93 규칙 7).

    **스테이블이 먼저다.** 폴 헤이먼은 개인이 아니라 무리를 끌고 다니고, 원본도
    `The Vision`처럼 무리 이름으로 적혀 있다. 개인 담당(릴 야티 ↔ 트릭 윌리엄스)은
    이름으로 잡는다.
    """
    for manager in staff.managers():
        target = manager.manages
        if not target:
            continue
        if stable and target == stable:
            return manager.name
        if who and target == who:
            return manager.name
    return ""


def crew_for(
    brand: str,
    week: int,
    seed: int,
    *,
    title_match: bool = False,
    player: str = "",
    player_stable: str = "",
    opponent: str = "",
    opponent_stable: str = "",
) -> MatchCrew:
    """그 밤의 링 밖 사람들 한 벌.

    **링 아나운서는 타이틀전에만 채운다** (2026-08-19 사용자 결정): 소개가 붙는 밤이
    특별해야 소개에 뜻이 생긴다. 매주 소개를 세우면 그건 그냥 오프닝이다.
    """
    return MatchCrew(
        gm=gm_of(brand),
        commentators=commentators_of(brand),
        ring_announcer=ring_announcer_of(brand, week, seed) if title_match else "",
        referee=referee_of(brand, week, seed, title_match=title_match),
        player_manager=manager_of(player, player_stable),
        rival_manager=manager_of(opponent, opponent_stable),
    )


def negotiator_for(brand: str, week: int, seed: int) -> StaffMember | None:
    """재계약 자리에 마주 앉는 사람 (§3-D93 규칙 2 · §3-D84).

    **회장은 안 나온다**(`PRESIDENT`). 그리고 NXT 계약은 육성 총괄이 맡는다 — 원본에
    숀 마이클스의 직함이 그렇게 적혀 있다(`Talent Development`).
    """
    people = tuple(m for m in staff.executives() if not m.title.startswith(PRESIDENT))
    if not people:
        return None
    if brand == "nxt":
        developers = tuple(m for m in people if "Talent Development" in m.title)
        if developers:
            return developers[0]
    return _roll(seed, week, "offer").pick(people)


@dataclass(frozen=True)
class Announcement:
    """집행부의 중대 발표 한 줄 (§3-D93 규칙 2).

    **없는 사실을 만들지 않는다.** 발표가 서는 자리는 이미 달력에 있는 날들이고
    (시즌 개막 · 드래프트), 문장은 그날이 무슨 날인지를 말할 뿐이다 — §3-D87이 기사에
    새 사실을 안 더한 것과 같은 규칙이다.
    """

    week: int
    speaker: str
    headline: str


DRAFT_WEEK: Final = 50
"""연말 드래프트 주차 (§3-D54의 `roster.DRAFT_WEEK`와 같은 값).

**여기서 다시 적는 이유**: `roster`를 import하면 명부 전체가 이 서비스에 딸려 온다.
값 하나를 두 곳에 두는 대신 테스트가 둘이 같은지를 잠근다.
"""


def announcements(seed: int, upto_week: int) -> tuple[Announcement, ...]:
    """0주부터 그 주차까지의 중대 발표.

    한 해에 둘이다 — **시즌 개막**과 **드래프트**. 더 자주 세우면 인박스가 발표로 차고,
    그러면 "중대"가 아니게 된다.
    """
    people = staff.executives()
    if not people:
        return ()
    found: list[Announcement] = []
    for year in range(0, upto_week // WEEKS_PER_YEAR + 1):
        opening = year * WEEKS_PER_YEAR + 1
        draft = year * WEEKS_PER_YEAR + DRAFT_WEEK
        if 0 < opening <= upto_week:
            speaker = _roll(seed, opening, "open").pick(people)
            found.append(
                Announcement(
                    week=opening,
                    speaker=speaker.name,
                    headline=(f"{speaker.name}, {year + 1}년차 시즌 개막을 알렸다"),
                )
            )
        if 0 < draft <= upto_week:
            speaker = _roll(seed, draft, "draft").pick(people)
            found.append(
                Announcement(
                    week=draft,
                    speaker=speaker.name,
                    headline=f"{speaker.name}, 올해 드래프트를 예고했다",
                )
            )
    return tuple(found)
