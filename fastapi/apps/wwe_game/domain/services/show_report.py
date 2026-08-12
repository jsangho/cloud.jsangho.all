"""그 밤의 리포트 — 대회 하나를 한 장으로 (하네스 §3-D45).

뉴스(§3-D31)와 다른 것이다.

| | 뉴스 | 리포트 |
|---|---|---|
| 담는 것 | 30년에서 **남을 만한 사건** | 그 밤에 **있었던 일 전부** |
| 단위 | 커리어 | 한 주차 |
| 묻는 것 | "무슨 일이 있었더라" | "그날 카드가 어땠지" |

**새 규칙이 없다.** 이미 만든 것들을 모을 뿐이다 — 내 주차 기록, 배경 챔피언
계보(§3-D38), 배경 대립(§3-D44). 그래서 저장할 것도 없다: 리포트는 값이 아니라
**보는 방식**이다.
"""

from __future__ import annotations

from dataclasses import dataclass

from wwe_game.domain.constants.ple_calendar import PleShow, calendar_for
from wwe_game.domain.entities.career_run import CareerRun
from wwe_game.domain.services import rivalry_scene, show_card, title_scene
from wwe_game.domain.value_objects.title import TITLES, Title, titles_of
from wwe_game.domain.value_objects.week_report import WeekReport

AROUND_WEEKS = 4
"""배경 사건을 앞뒤 몇 주까지 끌어올지.

대회는 그 주 하나의 일이 아니라 **몇 주에 걸쳐 쌓인 것의 결말**이다. 그 주차만 보면
리포트에 배경이 거의 안 뜬다 — 배경 대립은 30년에 열다섯 번뿐이다(§3-D44).
"""


@dataclass(frozen=True)
class TitleHolder:
    title: str
    holder: str
    mine: bool
    """내가 감고 있는 벨트인지. 계보는 **플레이어가 없는 세계**를 그리므로(§3-D38)
    여기서 겹쳐 준다."""


@dataclass(frozen=True)
class ShowReport:
    week: int
    show: str
    """대회 이름. 주간 방송이면 브랜드 이름이 그 자리에 온다."""
    is_major: bool
    result: str | None
    opponent: str | None
    match_label: str | None
    title_at_stake: str | None
    narration: str
    champions: tuple[TitleHolder, ...]
    around: tuple[str, ...]
    """그 무렵 배경에서 일어난 일. **내 일이 아니어서 뉴스에는 안 뜬 것들도 포함한다.**"""
    card: tuple[show_card.CardMatch, ...] = ()
    """그날 밤의 다른 경기들 (§3-D52). **내 경기는 없다** — 화면이 따로 그린다."""
    stars: float = 0.0
    """그 밤의 평점 — 카드에 선 경기들의 평균 (§3-D56). 카드가 비면 0이다.

    **내 경기는 안 들어간다.** 서버가 그 주차의 내 경기력을 모르는 경로가 있고(체험판),
    한쪽에서만 섞이면 같은 밤이 두 값을 갖는다.
    """


def build(run: CareerRun, report: WeekReport, narration: str) -> ShowReport:
    """그 주차의 리포트. 경기가 없는 주차도 만든다 — 빈 카드가 곧 그 밤의 기록이다."""
    player = str(run.identity.name)
    card = _card(
        run,
        report.week,
        _stage_of(report.show),
        busy=(report.opponent,) if report.opponent else (),
        stakes=(report.title_at_stake,) if report.title_at_stake else (),
    )
    show = report.show.name if report.show is not None else run.brand.value.upper()
    return ShowReport(
        week=report.week,
        show=show,
        is_major=report.is_major_show,
        result=report.result.value if report.result else None,
        opponent=report.opponent,
        match_label=report.match_kind.value if report.match_kind else None,
        title_at_stake=(
            TITLES[report.title_at_stake].display_name
            if report.title_at_stake
            else None
        ),
        narration=narration,
        champions=_champions(run, report.week, player),
        around=_around(run, report.week, player),
        card=card,
        stars=_night_stars(card),
    )


def build_night(
    run: CareerRun,
    week: int,
    *,
    busy: tuple[str, ...] = (),
    stakes: tuple[Title, ...] = (),
) -> ShowReport:
    """**로그 없이** 세우는 리포트 — 체험판의 것이다 (§3-D8 · §3-D51).

    체험판 세이브에는 주차 로그가 없다. 그런데 화면이 리포트에서 실제로 그리는 것은
    그 밤의 **배경**뿐이다 — 대회 이름, 그날의 벨트, 그 무렵의 사건, 그날의 카드.
    내 경기 기록(승패·상대·경기 형식)은 이미 로그 화면의 그 줄에 있고, 리포트는 그것을
    되풀이하지 않는다.

    그래서 여기서는 배경만 세우고 내 경기 자리는 비운다. **비운 것은 모른다는 뜻이 아니라
    이 자리에서 말할 것이 아니라는 뜻이다.** 로그를 가진 로그인 플레이는 `build()`가
    그 줄까지 채워 준다.

    `busy`·`stakes`는 로그 대신 **화면이 알려 주는 그 줄의 사실**이다 — 그날 내 상대와
    내가 도전한 벨트. 카드가 그 둘을 다시 쓰지 않게 하려고 받는다(§3-D52). 없으면 카드가
    조금 어긋날 뿐 리포트는 선다.
    """
    calendar = calendar_for(run.brand)
    # **주간 방송에는 대회 이름이 없다** — 브랜드가 그 밤의 이름이다 (§3-D60).
    show = calendar.show_for(week) if calendar.is_show_week(week) else None
    player = str(run.identity.name)
    stage = _stage_of(show)
    card = _card(run, week, stage, busy=busy, stakes=stakes)
    return ShowReport(
        week=week,
        show=show.name if show is not None else run.brand.value.upper(),
        is_major=show is not None and show.is_major,
        result=None,
        opponent=None,
        match_label=None,
        title_at_stake=None,
        narration="",
        champions=_champions(run, week, player),
        around=_around(run, week, player),
        card=card,
        stars=_night_stars(card),
    )


def _night_stars(card: tuple[show_card.CardMatch, ...]) -> float:
    """그 밤의 평점 — 카드의 평균을 0.25 눈금으로 접는다 (§3-D56)."""
    if not card:
        return 0.0
    return round(sum(m.stars for m in card) / len(card) / 0.25) * 0.25


def _stage_of(show: PleShow | None) -> str:
    """그 밤의 크기 (§3-D60). 카드 수·별점·타이틀전 확률이 이걸 읽는다."""
    if show is None:
        return "weekly"
    if show.is_major:
        return "major"
    return "special" if show.is_special else "ple"


def _card(
    run: CareerRun,
    week: int,
    stage: str,
    *,
    busy: tuple[str, ...],
    stakes: tuple[Title, ...],
) -> tuple[show_card.CardMatch, ...]:
    """그날 밤의 다른 경기들 (§3-D52).

    **내가 감고 있는 벨트와 그날 내가 도전한 벨트는 빼고 짠다.** 그 둘을 빼지 않으면
    같은 리포트 안에서 "그날의 벨트: 나"와 "카드: 챔피언 X 방어"가 서로를 부정한다.
    """
    return show_card.card_for(
        run.seed,
        week,
        run.identity.gender,
        run.brand,
        stage=stage,
        player=str(run.identity.name),
        busy=busy,
        skip_titles=frozenset(run.titles_held) | frozenset(stakes),
    )


def _champions(run: CareerRun, week: int, player: str) -> tuple[TitleHolder, ...]:
    """그 주차에 이 브랜드의 벨트를 누가 감고 있었나.

    **내가 든 벨트는 내 이름으로 덮는다.** 계보는 플레이어가 없는 세계를 그리므로,
    겹쳐 주지 않으면 내가 챔피언인데 리포트에는 남이 적힌다.
    """
    holders: list[TitleHolder] = []
    for title in titles_of(run.brand, run.identity.gender):
        mine = title in run.titles_held
        holder = (
            player
            if mine
            else title_scene.holder_label(
                title_scene.champion_at(run.seed, week, title, exclude=player) or "",
                run.seed,
            )
        )
        if holder is None:
            continue
        holders.append(
            TitleHolder(title=TITLES[title].display_name, holder=holder, mine=mine)
        )
    return tuple(holders)


def _around(run: CareerRun, week: int, player: str) -> tuple[str, ...]:
    """그 무렵의 배경 사건. 앞뒤 `AROUND_WEEKS` 주를 본다.

    **내 브랜드 안에서만 본다** (§3-D53). 그날 그 자리에 있던 사람들의 이야기라야
    "그 무렵"이 뜻을 갖는다 — 다른 브랜드 소식은 그 밤과 아무 상관이 없다.
    """
    scene = rivalry_scene.chronicle(
        run.seed,
        week + AROUND_WEEKS,
        run.identity.gender,
        exclude=player,
        brand=run.brand,
    )
    return tuple(
        item.headline for item in scene if abs(item.week - week) <= AROUND_WEEKS
    )


def is_reportable(run: CareerRun, week: int) -> bool:
    """리포트를 만들 만한 주차인지 — **경기가 서는 밤이면 연다** (§3-D60).

    §3-D45는 "대회 주차만"으로 닫았다. 주간 방송까지 열면 1560주 전부가 리포트가 되고
    그건 로그와 같아진다는 이유였다. 사용자 요청으로 그 문을 연다 — 다만 **밤의 크기가
    다르다**: 주간 방송은 카드가 넷이고 벨트가 잘 안 걸린다(`show_card.CARD_SIZE`).

    0주차는 아직 아무것도 없었던 자리라 연다고 할 것이 없다.
    """
    return week > 0
