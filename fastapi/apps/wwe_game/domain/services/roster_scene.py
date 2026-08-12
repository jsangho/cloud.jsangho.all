"""명부에 사람이 들고 난다 — 데뷔와 은퇴 (하네스 §3-D61).

명부에는 시간 축이 있고(§3-D13-1) 30년이면 오늘의 얼굴이 **전부** 사라진다. 그런데
그 사실이 화면 어디에도 없었다 — 로만 레인즈가 어느 밤에 링을 떠났는지 인박스에 한 줄도
안 뜨고, 어느 해에 사라졌는지는 명단이 비어야 알 수 있었다.

## 저장하지 않는다

`title_scene`(§3-D38) · `rivalry_scene`(§3-D44)과 같은 자리다. 명부가 이미 아는 사실
(`debut_week` · `retire_week`)을 읽을 뿐이라 굴림조차 없다 — **이 모듈에는 난수가 없다.**

## 분량은 화면이 정한다 (2026-08-12 사용자 결정)

처음엔 §3-D44를 따라 좁혔다 — 배경 대립을 0.055에서 0.008로 내린 그 판단이다. 0주차
스타의 은퇴(10건)와 실존 선수의 늦은 데뷔(8건)만 남기면 30년에 열여덟 줄이었다.

사용자가 다르게 정했다: **"많아도 상관없어, 안 볼 사람은 안 보기 체크해서 안 보게 하면
돼."** 그래서 세 갈래를 전부 흘리고, 걸러 내는 일은 인박스의 종류 필터가 한다 — 규칙으로
숨기는 것과 사용자가 접는 것은 다르다.

| 넣는 것 | 30년 분량 (RAW 남성부) |
|---|---|
| 데뷔 — 그 브랜드에 처음 선 사람 | 15건 |
| 콜업 — 육성에서 올라왔다 | 46건 |
| 은퇴 — 정상급이 링을 떠났다 | 67건 |

**등급이 낮은 사람의 은퇴는 여전히 뺀다.** 그건 필터의 문제가 아니라 기사가 아닌 것이고,
넣으면 명부 388명의 퇴장이 전부 흐른다.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from wwe_game.domain.constants import roster
from wwe_game.domain.constants.roster import RivalTier, RosterMember
from wwe_game.domain.value_objects.josa import josa_for
from wwe_game.domain.value_objects.title import Brand
from wwe_game.domain.value_objects.wrestler_identity import Gender


class RosterBeat(StrEnum):
    DEBUT = "debut"
    CALL_UP = "call_up"
    RETIRE = "retire"


@dataclass(frozen=True)
class RosterNews:
    """명부에서 일어난 일 하나. 뉴스 피드가 그대로 읽는다 (§3-D31)."""

    week: int
    beat: RosterBeat
    name: str
    headline: str


def chronicle(
    upto_week: int, gender: Gender, brand: Brand, seed: int = 0
) -> tuple[RosterNews, ...]:
    """0주부터 그 주차까지 명부의 들고 남.

    **내 브랜드·디비전만 본다** (§3-D53). 다른 브랜드에서 누가 떠났는지는 그 밤과 아무
    상관이 없고, 그것까지 세면 다시 인박스가 남의 이야기로 덮인다.

    순수 함수다 — 굴림이 없으므로 같은 명부는 언제 물어도 같은 연대기를 만든다.
    """
    news: list[RosterNews] = []
    for member in roster.ROSTER:
        if member.gender is not gender:
            continue
        if _debuts(member, upto_week, brand, seed):
            name = roster.name_at(member, member.debut_week, seed)
            news.append(
                RosterNews(
                    week=member.debut_week,
                    beat=RosterBeat.DEBUT,
                    name=name,
                    headline=f"{name}{josa_for(name, '가')} 링에 처음 섰다.",
                )
            )
        called = _called_up(member, upto_week, brand, seed)
        if called is not None:
            name = roster.name_at(member, called, seed)
            news.append(
                RosterNews(
                    week=called,
                    beat=RosterBeat.CALL_UP,
                    name=name,
                    headline=f"{name}{josa_for(name, '가')} 메인 로스터로 올라왔다.",
                )
            )
        if _retires(member, upto_week, brand, seed):
            week = member.retire_week or 0
            name = roster.name_at(member, week - 1, seed)
            news.append(
                RosterNews(
                    week=week,
                    beat=RosterBeat.RETIRE,
                    name=name,
                    headline=f"{name}{josa_for(name, '가')} 링을 떠났다.",
                )
            )
    return tuple(sorted(news, key=lambda item: item.week))


def _debuts(member: RosterMember, upto: int, brand: Brand, seed: int) -> bool:
    """그 브랜드에 처음 선 주차. **0주차 명부는 데뷔가 아니라 시작이다.**"""
    if not 0 < member.debut_week <= upto:
        return False
    return roster.brand_at(member, member.debut_week, seed) is brand


def _called_up(member: RosterMember, upto: int, brand: Brand, seed: int) -> int | None:
    """육성에서 올라온 주차 (§3-D53의 콜업). 처음부터 메인이면 None.

    **도착한 브랜드에서만 기사가 된다** — 떠난 쪽에서 보면 그건 데뷔의 반대편이고,
    양쪽에 다 흘리면 한 사람의 이동이 두 줄이 된다.
    """
    week = roster.call_up_week(member)
    if week is None or not 0 < week <= upto:
        return None
    return week if roster.brand_at(member, week, seed) is brand else None


def _retires(member: RosterMember, upto: int, brand: Brand, seed: int) -> bool:
    """**정상급이 링을 떠날 때** 기사가 된다.

    등급이 낮은 사람의 퇴장까지 세면 명부 388명이 전부 흐른다 — 그건 뉴스가 아니라
    명단이다. 떠나는 시점의 등급으로 본다(§3-D13-1의 승급이 반영된 값이다).
    """
    week = member.retire_week
    if week is None or not 0 < week <= upto:
        return False
    if roster.tier_at(member, week - 1) is not RivalTier.MAIN_EVENT:
        return False
    return roster.brand_at(member, week - 1, seed) is brand
