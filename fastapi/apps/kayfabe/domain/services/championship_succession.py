"""끝난 타이틀 매치로 현 챔피언을 갱신하는 **순수 함수**.

## 왜 필요한가

`current_championship_catalog`는 사람이 손으로 적은 표이고 `CHAMPIONSHIP_AS_OF`에
기준일이 박혀 있다. 대회가 열릴 때마다 사람이 고치지 않으면 보드가 조용히 낡는다 —
2026-09-28 실측에서 실제로 그랬다. 기준일 `2026-07-12` 이후 SummerSlam(8/1)이 열렸고
화면은 그 전 상태를 보여 주고 있었다:

    WWE Intercontinental   화면 Penta(3/02)          실제 Chad Gable(8/1)
    WWE United States      화면 Trick Williams(4/19)  실제 Baron Corbin(8/1)

경기 결과는 이미 DB에 있었다. 없던 것은 **결과에서 챔피언을 끌어내는 규칙**뿐이다.

## 이 함수가 보는 것과 보지 않는 것

카탈로그를 **기준선**으로 삼고, 기준일 뒤에 끝난 타이틀 매치만 얹는다. 기준일 이전
경기는 이미 카탈로그에 반영돼 있으므로 다시 적용하면 안 된다.

## 관문 — 왜 이름을 정확히 맞추는가

**경기 제목이 벨트 이름과 글자 그대로 같아야 한다.** 부분 일치를 허용하면 바로
뚫린다. 2026-08-01 SummerSlam에 이런 경기가 실제로 있다:

    Undisputed WWE Championship — No.1 Contender   승자 Kevin Owens

벨트 이름을 *포함*하지만 타이틀이 걸리지 않은 도전자 결정전이다. `in` 검사나
`title_match_classifier.extract_belt_name`(접미사를 떼어 낸다)을 쓰면 **케빈 오웬스가
챔피언이 된다.** 그래서 이 모듈은 그 함수를 쓰지 않는다.

같은 이유로 보드에 없는 벨트(`AAA Reina de Reinas Championship`,
`Interim WWE Women's Championship — Ladder Match`)는 그냥 지나친다 — 우리 보드가
말하는 벨트가 아니다.

## 방어는 재위가 아니다

승자가 현 챔피언이면 **`won_at`을 건드리지 않는다.** 성공적인 방어는 새 재위가
아니고, 날짜를 갈아 끼우면 "언제부터 챔피언인가"가 거짓이 된다. Roman Reigns가
4/19에 따고 8/1에 방어한 경우 보드는 여전히 4/19여야 한다.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

#: 팀 이름과 구성원을 가르는 구분자. 카드가 `Lucha Brothers — Penta & Rey Fénix`처럼
#: 둘을 함께 적는 일이 있다. em dash 앞뒤 공백까지 포함해 정확히 본다.
_TEAM_SPLIT = re.compile(r"\s+—\s+")

#: 구성원을 가르는 구분자. `Bron Breakker & Austin Theory`.
_MEMBER_SPLIT = re.compile(r"\s+(?:&|and)\s+", re.IGNORECASE)

_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class TitleReign:
    """보드 한 줄 — 어느 벨트를 누가 언제부터 들고 있나."""

    belt_name: str
    champions: tuple[str, ...]
    team_name: str | None = None
    #: `YYYY-MM-DD`. 재위 시작일이지 마지막 방어일이 아니다.
    won_at: str = ""
    won_event: str | None = None


@dataclass(frozen=True)
class FinishedTitleMatch:
    """끝난 경기 하나. **제목을 가공하지 않고 원문 그대로 받는다.**

    가공은 부르는 쪽에서 하면 안 된다 — 접미사를 떼는 순간 도전자 결정전이 타이틀
    매치로 둔갑한다(위 독스트링).
    """

    #: 경기 제목 원문.
    match_title: str
    match_key: str
    #: `winner_pick`이 가리키는 **카드 선택지의 이름**. `winner_name`이 아니다 —
    #: 그 칸은 비어 있는 행이 실제로 있다(WrestleMania 여성 태그전).
    winner: str
    event_label: str
    #: 대회 시작일 `YYYY-MM-DD`. 이틀짜리 대회도 시작일로 센다 — 경기가 몇째 날인지
    #: 카드가 말해 주지 않는다.
    event_date: str


class SkipReason(StrEnum):
    """챔피언십처럼 보이는데 반영하지 않은 이유. 사람이 보라고 남긴다."""

    NOT_A_TITLE_MATCH = "not_a_title_match"
    """MITB 래더·로얄럼블처럼 타이틀이 걸리지 않은 경기."""

    BELT_NOT_ON_BOARD = "belt_not_on_board"
    """우리 보드에 없는 벨트 — AAA 타이틀, 잠정 타이틀 등."""

    NO_WINNER = "no_winner"
    """승자가 없다. 무승부이거나 결과가 아직 기록되지 않았다."""


@dataclass(frozen=True)
class Skipped:
    match_title: str
    match_key: str
    reason: SkipReason


@dataclass(frozen=True)
class Change:
    """실제로 바뀐 것 하나. 로그와 보고에 쓴다."""

    belt_name: str
    before: tuple[str, ...]
    after: tuple[str, ...]
    at: str
    event_label: str
    #: 태그 벨트인데 구성원을 못 알아냈나 — 사람이 카탈로그를 보강해야 하는 자리다.
    members_unknown: bool = False


@dataclass(frozen=True)
class SuccessionResult:
    reigns: tuple[TitleReign, ...]
    #: 적용한 마지막 대회 날짜. 아무것도 안 바뀌었으면 기준일 그대로다.
    as_of: str
    changes: tuple[Change, ...] = ()
    skipped: tuple[Skipped, ...] = ()


def apply_results(
    baseline: Sequence[TitleReign],
    matches: Sequence[FinishedTitleMatch],
    *,
    baseline_as_of: str,
    is_title_match,
) -> SuccessionResult:
    """기준선 위에 끝난 타이틀 매치를 얹는다.

    `is_title_match(title, match_key) -> bool`을 주입받는 이유는 그 판정이
    `app.services.title_match_classifier`에 있고 도메인이 app을 import할 수 없기
    때문이다. 계약은 "타이틀이 걸린 경기인가" 하나다.

    **순서가 판정을 바꾼다.** 벨트별로 가장 늦은 경기가 이기므로 날짜순으로 훑는다.
    같은 날 같은 벨트가 두 번 걸리는 일은 없지만, 있더라도 `match_key`로 순서가
    정해져 결과가 흔들리지 않는다.
    """
    by_belt = {_normalized(reign.belt_name): reign for reign in baseline}
    changes: list[Change] = []
    skipped: list[Skipped] = []
    as_of = baseline_as_of

    for match in sorted(matches, key=lambda m: (m.event_date, m.match_key)):
        if match.event_date <= baseline_as_of:
            # 기준일 이전은 이미 카탈로그에 들어 있다. 다시 얹으면 방어를 재위로
            # 바꾸거나 이미 반영된 변경을 되풀이한다.
            continue

        if not is_title_match(match.match_title, match.match_key):
            if _looks_like_championship(match.match_title):
                skipped.append(
                    Skipped(
                        match.match_title, match.match_key, SkipReason.NOT_A_TITLE_MATCH
                    )
                )
            continue

        key = _normalized(match.match_title)
        current = by_belt.get(key)
        if current is None:
            skipped.append(
                Skipped(
                    match.match_title, match.match_key, SkipReason.BELT_NOT_ON_BOARD
                )
            )
            continue

        if not match.winner.strip():
            skipped.append(
                Skipped(match.match_title, match.match_key, SkipReason.NO_WINNER)
            )
            continue

        as_of = max(as_of, match.event_date)

        if _is_retention(match.winner, current):
            # 방어다. 재위는 이어지므로 아무것도 바꾸지 않는다.
            continue

        team_name, champions = _parse_winner(match.winner)
        by_belt[key] = TitleReign(
            belt_name=current.belt_name,
            champions=champions,
            team_name=team_name,
            won_at=match.event_date,
            won_event=match.event_label,
        )
        changes.append(
            Change(
                belt_name=current.belt_name,
                before=current.champions,
                after=champions,
                at=match.event_date,
                event_label=match.event_label,
                # 기존 재위가 둘 이상이었는데 새 승자가 하나면 팀명만 받은 것이다.
                members_unknown=len(current.champions) > 1 and len(champions) == 1,
            )
        )

    # **기준선의 순서를 지킨다.** 보드는 브랜드·벨트 순서가 화면 배치라, 바뀐 줄이
    # 뒤로 밀리면 사람이 읽던 자리가 달라진다.
    reigns = tuple(by_belt[_normalized(r.belt_name)] for r in baseline)
    return SuccessionResult(
        reigns=reigns, as_of=as_of, changes=tuple(changes), skipped=tuple(skipped)
    )


def _is_retention(winner: str, reign: TitleReign) -> bool:
    """승자가 지금 그 벨트를 든 쪽인가.

    셋 중 하나면 방어다 — 팀 이름이 같거나, 구성원 집합이 같거나, 단독 챔피언의
    이름이 같거나. **팀 이름을 함께 보는 이유**는 카드가 구성원 대신 팀명만 적는
    일이 있기 때문이다(`The Vanity Project`). 이름만 대조하면 방어가 재위로 둔갑해
    `won_at`이 갈아 끼워진다.
    """
    team_name, champions = _parse_winner(winner)

    if (
        reign.team_name
        and team_name
        and _normalized(team_name) == _normalized(reign.team_name)
    ):
        return True
    if reign.team_name and len(champions) == 1:
        if _normalized(champions[0]) == _normalized(reign.team_name):
            return True

    current = {_normalized(name) for name in reign.champions}
    return current == {_normalized(name) for name in champions}


def _parse_winner(winner: str) -> tuple[str | None, tuple[str, ...]]:
    """카드 선택지 이름 → (팀 이름, 구성원).

        "Lucha Brothers — Penta & Rey Fénix"  → ("Lucha Brothers", ("Penta", "Rey Fénix"))
        "Bron Breakker & Austin Theory"        → (None, ("Bron Breakker", "Austin Theory"))
        "The Vanity Project"                   → (None, ("The Vanity Project",))
        "CM Punk"                              → (None, ("CM Punk",))

    **셋째 줄이 한계다.** 팀명만 적힌 카드에서는 구성원을 알 길이 없어 그대로 둔다.
    지어내지 않는 대신 `Change.members_unknown`으로 알려, 사람이 카탈로그를 보강할
    수 있게 한다.
    """
    text = _collapsed(winner)
    parts = _TEAM_SPLIT.split(text, maxsplit=1)
    if len(parts) == 2 and parts[0] and parts[1]:
        return parts[0], _members(parts[1])
    return None, _members(text)


def _members(text: str) -> tuple[str, ...]:
    names = [name.strip() for name in _MEMBER_SPLIT.split(text)]
    return tuple(name for name in names if name)


def _looks_like_championship(title: str) -> bool:
    return "championship" in title.casefold() or "챔피언십" in title


def _collapsed(text: str) -> str:
    return _WHITESPACE.sub(" ", text).strip()


def _normalized(text: str) -> str:
    """대조용 정규화 — **공백과 대소문자만** 흡수한다.

    구두점이나 접미사를 건드리지 않는다. `— No.1 Contender`가 다른 이름으로 남아야
    이 모듈의 관문이 성립한다.
    """
    return _collapsed(text).casefold()
