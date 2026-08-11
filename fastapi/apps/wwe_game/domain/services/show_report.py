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

from wwe_game.domain.constants.ple_calendar import calendar_for
from wwe_game.domain.entities.career_run import CareerRun
from wwe_game.domain.services import rivalry_scene, title_scene
from wwe_game.domain.value_objects.title import TITLES, titles_of
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


def build(run: CareerRun, report: WeekReport, narration: str) -> ShowReport:
    """그 주차의 리포트. 경기가 없는 주차도 만든다 — 빈 카드가 곧 그 밤의 기록이다."""
    player = str(run.identity.name)
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
            else title_scene.champion_at(run.seed, week, title, exclude=player)
        )
        if holder is None:
            continue
        holders.append(
            TitleHolder(title=TITLES[title].display_name, holder=holder, mine=mine)
        )
    return tuple(holders)


def _around(run: CareerRun, week: int, player: str) -> tuple[str, ...]:
    """그 무렵의 배경 사건. 앞뒤 `AROUND_WEEKS` 주를 본다."""
    scene = rivalry_scene.chronicle(
        run.seed, week + AROUND_WEEKS, run.identity.gender, exclude=player
    )
    return tuple(
        item.headline for item in scene if abs(item.week - week) <= AROUND_WEEKS
    )


def is_reportable(run: CareerRun, week: int) -> bool:
    """리포트를 만들 만한 주차인지 — **대회와 특별 방송만**.

    주간 방송까지 열면 1560주 전부가 리포트가 되고, 그건 로그와 같은 것이다.
    """
    calendar = calendar_for(run.brand)
    return calendar.is_show_week(week)
