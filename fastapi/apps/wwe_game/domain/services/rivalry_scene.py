"""배경 세계의 대립 — 나 말고도 사람이 산다 (하네스 §3-D44).

인박스는 "세계선의 사건"을 표방하는데(§3-D31), 지금까지 거기 흐르는 것은 **내 일과 팀
소식뿐**이었다. 벨트는 §3-D38로 주인이 생겼지만 그 챔피언은 아무와도 싸우지 않았다 —
내가 도전하러 갈 때만 존재하는 사람이었다.

## 팀 연대기와 같은 방식이다

시드에서 되짚고 저장하지 않는다(§3-D30 `team_engine.chronicle`). **살아 있는 대립
목록을 들고 걷는 것**도 같다: 그렇게 하지 않으면 시작된 적 없는 대립이 끝나고, 시작된
대립은 영원히 안 끝난다 — 팀 연대기가 2026-08-10에 겪은 버그가 정확히 그것이었다.

## 내 대립과 섞지 않는다

플레이어의 대립은 `CareerRun.rivalries`가 들고 있고 열기·단계까지 굴린다(§2-D4).
여기는 **헤드라인만** 만든다. 배경의 대립에 상태기계를 붙이면 명부 388명분의 열기를
매주 굴리게 되고, 그 계산은 화면에 한 줄로 나오는 것에 비해 너무 비싸다.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from wwe_game.domain.constants import roster
from wwe_game.domain.constants.roster import RivalTier
from wwe_game.domain.services.seeded_roll import SeededRoll
from wwe_game.domain.value_objects.josa import josa_for
from wwe_game.domain.value_objects.wrestler_identity import Gender

CHANNEL: Final = "rivalry_scene"

START_CHANCE: Final = 0.008
"""주당 새 대립이 배경에서 시작될 확률. 30년이면 열다섯 번쯤 열린다.

**0.055로 시작했다가 내렸다.** 그 값이면 30년에 배경 뉴스가 174줄인데, **내 뉴스는
커리어당 28줄**이다 — 인박스를 열면 남의 이야기가 3분의 2였다. 이 모듈의 설명이
경고한 바로 그 상황을 만든 값이었다.

배경은 양념이다: 지금은 전체 피드의 3분의 1쯤이고, 그 정도면 "세계선이 흐른다"는
신호는 주되 내 커리어를 덮지 않는다.
"""

MIN_WEEKS: Final = 6
MAX_WEEKS: Final = 34
"""대립이 사는 기간. 짧으면 뉴스가 소음이 되고, 길면 세계가 멈춰 있다."""

MAX_ACTIVE: Final = 3
"""동시에 도는 배경 대립 수. 넷 이상이면 인박스가 남의 이야기로 덮인다."""

BETRAYAL_CHANCE: Final = 0.30
"""결착 대신 배신으로 끝날 확률. 프로레슬링에서 이야기는 자주 그렇게 꺾인다."""


class RivalryBeat(StrEnum):
    STARTED = "started"
    BETRAYED = "betrayed"
    SETTLED = "settled"


@dataclass(frozen=True)
class SceneNews:
    """배경에서 일어난 대립 사건 하나. 뉴스 피드가 그대로 읽는다 (§3-D31)."""

    week: int
    beat: RivalryBeat
    names: tuple[str, str]
    headline: str


@dataclass(frozen=True)
class _Feud:
    names: tuple[str, str]
    started: int
    ends: int


def chronicle(
    seed: int, upto_week: int, gender: Gender, *, exclude: str = ""
) -> tuple[SceneNews, ...]:
    """0주부터 그 주차까지 배경 대립의 연대기.

    `exclude`는 플레이어의 링네임이다 — 실존 선수를 바탕으로 만든 커리어는 자기
    이름이 명부에 있어(§3-D10-1), 빼지 않으면 **내가 배경에서 나와 싸운다.**

    순수 함수다 — 같은 시드는 언제 돌려도 같은 연대기를 만든다(§3-D4).
    """
    active: list[_Feud] = []
    news: list[SceneNews] = []
    for week in range(1, upto_week + 1):
        roll = SeededRoll(seed, week, CHANNEL)
        for feud in tuple(active):
            if week < feud.ends:
                continue
            active.remove(feud)
            news.append(_ending(week, feud, roll))
        if len(active) < MAX_ACTIVE and roll.chance(START_CHANCE):
            pair = _pick_pair(week, gender, exclude, roll)
            if pair is not None:
                fresh = _Feud(pair, week, week + roll.between(MIN_WEEKS, MAX_WEEKS))
                active.append(fresh)
                news.append(
                    SceneNews(
                        week=week,
                        beat=RivalryBeat.STARTED,
                        names=pair,
                        headline=(
                            f"{pair[0]}{josa_for(pair[0], '와')} "
                            f"{pair[1]}{josa_for(pair[1], '가')} 부딪쳤다."
                        ),
                    )
                )
    return tuple(news)


def _ending(week: int, feud: _Feud, roll: SeededRoll) -> SceneNews:
    first, second = feud.names
    if roll.chance(BETRAYAL_CHANCE):
        return SceneNews(
            week=week,
            beat=RivalryBeat.BETRAYED,
            names=feud.names,
            headline=(f"{second}{josa_for(second, '가')} {first}의 등에 칼을 꽂았다."),
        )
    return SceneNews(
        week=week,
        beat=RivalryBeat.SETTLED,
        names=feud.names,
        headline=(f"{first}{josa_for(first, '와')} {second}의 대립이 매듭지어졌다."),
    )


def _pick_pair(
    week: int, gender: Gender, exclude: str, roll: SeededRoll
) -> tuple[str, str] | None:
    """정상급 둘. **중견들의 대립은 헤드라인이 아니다.**

    등급을 섞어 뽑았더니 인박스에 육성 브랜드 이름들이 올라왔다 — 세계가 도는 신호로는
    맞지만 뉴스로는 아니다. 실제로도 남의 대립이 기사가 되는 것은 그 자리가 정상일 때다.
    """
    pool = tuple(
        n for n in roster.pool_for(gender, RivalTier.MAIN_EVENT, week) if n != exclude
    )
    if len(pool) < 2:
        return None
    first = roll.pick(pool)
    second = roll.pick(tuple(n for n in pool if n != first))
    return first, second
