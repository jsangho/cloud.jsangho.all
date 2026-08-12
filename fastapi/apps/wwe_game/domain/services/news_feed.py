"""내 세계선의 뉴스 — 일어난 일과 군중의 반응 (하네스 §3-D31).

주차 로그는 "그 주에 나에게 무슨 일이 있었나"를 한 줄씩 쌓는다. 뉴스 피드는 그 위에서
**남을 만한 사건만 골라** 시간순으로 세운다 (2026-08-10 사용자 지시 10번).

## 로그와 무엇이 다른가

| | 커리어 로그 | 뉴스 피드 |
|---|---|---|
| 담는 것 | **모든** 주차 | 남을 만한 사건만 |
| 범위 | 나에게 일어난 일 | 나 + **팀 세계에서 일어난 일**(§3-D30) |
| 붙는 것 | 서술 한 줄 | 헤드라인 + **군중 반응** |

`weekly` 한 판이 1560줄이라 로그를 그대로 펼치면 읽을 수가 없다. 대관·부상·콜업처럼
**되돌아볼 때 기억나는 것**만 남긴다.

## 군중 반응은 사건과 성향이 함께 정한다

같은 대관이라도 확실한 선역과 확실한 악역에게 돌아오는 소리가 다르다. `alignment`가
여기서 두 번째 쓰임을 얻는다 — 인기도 배수(§3-D25) 말고 **소리의 결**을 정한다.

**성향 0은 갈린 반응이다.** 응원할지 야유할지 관중도 모르는 상태이고, 그 어정쩡함이
그대로 화면에 나온다.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from wwe_game.domain.constants import career_rules as rules
from wwe_game.domain.services.rivalry_scene import SceneNews
from wwe_game.domain.services.roster_scene import RosterBeat, RosterNews
from wwe_game.domain.services.team_engine import TeamNews
from wwe_game.domain.value_objects.title import TITLES
from wwe_game.domain.value_objects.week_report import (
    CallUpReason,
    OutcomeKind,
    WeekReport,
)
from wwe_game.domain.value_objects.wrestler_stats import (
    FACE_THRESHOLD,
    HEEL_THRESHOLD,
    WrestlerStats,
)


class NewsKind(StrEnum):
    """뉴스 한 줄의 성격. 화면이 색과 아이콘을 여기서 고른다."""

    TITLE_WON = "title_won"
    TITLE_LOST = "title_lost"
    INJURY = "injury"
    CALL_UP = "call_up"
    BIG_WIN = "big_win"
    CURSED = "cursed"
    SCENE = "scene"
    """배경 세계의 대립 (§3-D44). **나와 무관해도 뉴스다.**"""
    CROWN = "crown"
    """킹 앤 퀸 오브 더 링 우승 — 세 번을 이어 이겼다 (§3-D33)."""
    TURN = "turn"
    """성향이 반대편으로 넘어갔다 — 힐턴·베이비페이스턴 (§3-D39)."""
    TEAM = "team"
    DEBUT = "debut"
    """배경 선수가 링에 처음 섰다 (§3-D61)."""
    CALL_UP_SCENE = "call_up_scene"
    """배경 선수가 메인 로스터로 올라왔다 (§3-D61). 내 콜업(`CALL_UP`)과 나눠 둔다 —
    화면이 "내 일"과 "남의 일"을 다른 색으로 읽는다."""
    RETIRE = "retire"
    """배경 선수가 링을 떠났다 (§3-D61)."""


class CrowdMood(StrEnum):
    """군중이 낸 소리."""

    ROAR = "roar"
    """환호 — 선역의 성취."""
    JEER = "jeer"
    """야유 — 악역의 성취. **관심이 없는 것과 다르다.**"""
    SPLIT = "split"
    """갈린 반응 — 응원할지 야유할지 정하지 못한 상태."""
    HUSH = "hush"
    """침묵 — 부상과 패배가 부르는 소리."""
    CHANT = "chant"
    """구호 — 이름이 불린다. 인기도가 높을 때만 나온다."""


CHANT_POPULARITY = 70
"""이 인기도 위에서만 관중이 이름을 부른다. 아래에서는 부를 이름을 모른다."""

MOOD_LINES: dict[CrowdMood, tuple[str, ...]] = {
    CrowdMood.ROAR: (
        "아레나가 통째로 일어섰다",
        "함성이 중계 마이크를 먹었다",
        "관중석이 흔들렸다",
    ),
    CrowdMood.JEER: (
        "야유가 쏟아졌고, 그게 곧 값이었다",
        "관중은 끝까지 반대쪽을 응원했다",
        "야유 소리가 테마곡보다 컸다",
    ),
    CrowdMood.SPLIT: (
        "환호와 야유가 반씩 갈렸다",
        "관중석이 두 갈래로 나뉘어 소리를 냈다",
        "응원할지 야유할지 관중도 정하지 못했다",
    ),
    CrowdMood.HUSH: (
        "아레나가 조용해졌다",
        "박수 몇 번이 전부였다",
        "중계가 한동안 말을 잇지 못했다",
    ),
    CrowdMood.CHANT: (
        "관중이 이름을 연호했다",
        "구호가 경기장을 한 바퀴 돌았다",
        "이름을 부르는 소리가 끊기지 않았다",
    ),
}
"""반응마다 세 문장. 로그와 달리 뉴스는 드물게 뜨므로 셋이면 겹치지 않는다."""


@dataclass(frozen=True)
class NewsItem:
    """뉴스 한 줄."""

    week: int
    kind: NewsKind
    headline: str
    mood: CrowdMood
    crowd_line: str

    @property
    def year(self) -> int:
        return week_to_year(self.week)


def week_to_year(week: int) -> int:
    """1년차부터 센다. 화면이 연도별로 묶는 데 쓴다."""
    return week // 52 + 1


def mood_for(kind: NewsKind, stats: WrestlerStats) -> CrowdMood:
    """사건과 성향이 함께 정하는 반응.

    **나쁜 소식에는 성향을 묻지 않는다** — 다치거나 저주로 진 밤에 악역이라고 해서
    야유가 나오지는 않는다. 그때 나오는 소리는 침묵 하나다.
    """
    if kind in (NewsKind.INJURY, NewsKind.CURSED, NewsKind.TITLE_LOST):
        return CrowdMood.HUSH
    if kind is NewsKind.TEAM:
        return CrowdMood.SPLIT
    if stats.alignment <= HEEL_THRESHOLD:
        return CrowdMood.JEER
    if stats.popularity >= CHANT_POPULARITY and stats.alignment >= FACE_THRESHOLD:
        return CrowdMood.CHANT
    if stats.alignment >= FACE_THRESHOLD:
        return CrowdMood.ROAR
    return CrowdMood.SPLIT


def _crowd_line(mood: CrowdMood, week: int) -> str:
    """주차로 문장을 고른다 — 굴림을 쓰지 않아 세이브 없이도 재현된다(§3-D4)."""
    lines = MOOD_LINES[mood]
    return lines[week % len(lines)]


def from_report(
    report: WeekReport, stats: WrestlerStats, player: str
) -> NewsItem | None:
    """주차 리포트에서 **남을 만한 사건 하나**. 평범한 주차는 None이다."""
    kind, headline = _headline_of(report, player)
    if kind is None:
        return None
    mood = mood_for(kind, stats)
    return NewsItem(
        week=report.week,
        kind=kind,
        headline=headline,
        mood=mood,
        crowd_line=_crowd_line(mood, report.week),
    )


def _headline_of(report: WeekReport, player: str) -> tuple[NewsKind | None, str]:
    """우선순위는 나레이터(`beat_of`)와 같은 순서다 — 두 화면이 같은 주차를 다르게
    기억하면 플레이어가 둘 중 무엇을 믿어야 할지 모른다."""
    title = report.title_at_stake
    name = TITLES[title].display_name if title is not None else ""
    if report.call_up is CallUpReason.EMERGENCY:
        return NewsKind.CALL_UP, f"{player}, 대타로 메인 로스터에 올라섰다."
    if report.call_up is CallUpReason.EARNED:
        return NewsKind.CALL_UP, f"{player}, 마침내 메인 로스터로 콜업됐다."
    # **누구에게서 빼앗았고 누구에게 내줬는지가 벨트의 이야기다** (§3-D38).
    # 상대 이름이 없던 시절에는 대관 열 번이 전부 같은 한 줄이었다.
    rival = report.opponent
    if (
        report.tournament_round >= rules.TOURNAMENT_ROUNDS
        and report.result is OutcomeKind.WIN
    ):
        # 벨트보다 앞에 둔다 — 결승 밤에 벨트가 걸리는 일은 없고, 왕관이 그날의 사건이다.
        return NewsKind.CROWN, f"{player}, 왕관을 썼다 — 세 밤을 이어 이겼다."
    if title is not None and report.result is OutcomeKind.WIN:
        if report.title_defended:
            against = f" — {rival}의 도전을 막았다" if rival else ""
            return NewsKind.TITLE_WON, f"{player}, {name} 방어에 성공했다{against}."
        took = f"{rival}에게서 " if rival else ""
        return NewsKind.TITLE_WON, f"{player}, {took}{name}을 가져왔다."
    if report.title_defended:
        lost_to = f" {rival}에게" if rival else ""
        return NewsKind.TITLE_LOST, f"{player},{lost_to} {name}을 내줬다."
    if report.vacated:
        # **부상보다 앞이다.** 벨트를 비운 밤의 머리기사는 부상이 아니라 빈 자리다.
        names = " · ".join(TITLES[t].display_name for t in report.vacated)
        return NewsKind.TITLE_LOST, f"{player}, 부상으로 {names}을 반납했다."
    if report.injury is not None:
        return NewsKind.INJURY, f"{player}, 경기 중 부상으로 이탈했다."
    if report.cursed:
        return NewsKind.CURSED, f"{player}, 이길 경기를 이해할 수 없게 놓쳤다."
    # 드래프트는 **열렸다는 사실만** 리포트에 남는다(§`WeekReport.draft_night`). 실제로
    # 소속이 바뀌었는지는 알 수 없어서, 뉴스로 세우면 30년 내내 같은 한 줄이 열두 번
    # 반복된다. 로그가 이미 말해 주는 것을 뉴스가 또 말할 이유가 없다.
    if report.is_major_show and report.result is OutcomeKind.WIN:
        show = report.show.name if report.show is not None else "대회"
        return NewsKind.BIG_WIN, f"{player}, {show} 무대에서 이겼다."
    return None, ""


def from_team_news(news: TeamNews, stats: WrestlerStats) -> NewsItem:
    """팀 세계의 사건. **나와 무관해도 뉴스다** — 세계선이 흐르고 있다는 신호다."""
    mood = mood_for(NewsKind.TEAM, stats)
    return NewsItem(
        week=news.week,
        kind=NewsKind.TEAM,
        headline=news.headline,
        mood=mood,
        crowd_line=_crowd_line(mood, news.week),
    )


def from_scene_news(news: SceneNews, stats: WrestlerStats) -> NewsItem:
    """배경 대립 한 줄 (§3-D44). 팀 소식과 같은 자리다 — 세계선이 흐른다는 신호."""
    mood = mood_for(NewsKind.SCENE, stats)
    return NewsItem(
        week=news.week,
        kind=NewsKind.SCENE,
        headline=news.headline,
        mood=mood,
        crowd_line=_crowd_line(mood, news.week),
    )


_ROSTER_KINDS: dict[RosterBeat, NewsKind] = {
    RosterBeat.DEBUT: NewsKind.DEBUT,
    RosterBeat.CALL_UP: NewsKind.CALL_UP_SCENE,
    RosterBeat.RETIRE: NewsKind.RETIRE,
}


def from_roster_news(news: RosterNews, stats: WrestlerStats) -> NewsItem:
    """명부의 들고 남 한 줄 (§3-D61). 배경이라 내 일 뒤에 붙는다."""
    kind = _ROSTER_KINDS[news.beat]
    mood = mood_for(kind, stats)
    return NewsItem(
        week=news.week,
        kind=kind,
        headline=news.headline,
        mood=mood,
        crowd_line=_crowd_line(mood, news.week),
    )


def compile_feed(
    entries: tuple[tuple[WeekReport, WrestlerStats], ...],
    team_news: tuple[TeamNews, ...],
    player: str,
    scene_news: tuple[SceneNews, ...] = (),
    roster_news: tuple[RosterNews, ...] = (),
) -> tuple[NewsItem, ...]:
    """두 갈래를 하나의 시간순 피드로 합친다.

    **주차마다 그때의 스탯을 함께 받는다.** 마지막 스탯 하나로 전부 계산하면 서른 해치
    반응이 같은 소리가 된다 — 힐턴을 하기 전의 대관에도 야유가 붙는다.

    **같은 주차면 내 일이 먼저다.** 팀 소식은 배경이고, 그 주의 머리기사는 내 커리어다.
    """
    items = [
        item
        for report, stats in entries
        if (item := from_report(report, stats, player)) is not None
    ]
    items += _turns(entries, player)
    last = entries[-1][1] if entries else WrestlerStats()
    items += [from_team_news(n, last) for n in team_news]
    items += [from_scene_news(n, last) for n in scene_news]
    items += [from_roster_news(n, last) for n in roster_news]
    # **같은 주차면 내 일이 먼저다.** 배경(팀·대립·명부)은 그 뒤에 붙는다.
    background = {
        NewsKind.TEAM,
        NewsKind.SCENE,
        NewsKind.DEBUT,
        NewsKind.CALL_UP_SCENE,
        NewsKind.RETIRE,
    }
    return tuple(sorted(items, key=lambda i: (i.week, i.kind in background)))


def _turns(
    entries: tuple[tuple[WeekReport, WrestlerStats], ...], player: str
) -> list[NewsItem]:
    """성향이 반대편으로 넘어간 주차 (§3-D39).

    **턴은 숫자가 아니라 사건이다.** 성향은 카드 169개가 조금씩 움직여 왔지만, 그 값이
    0을 넘어가는 순간에는 아무 일도 일어나지 않았다 — 어느 밤에 등을 돌렸는지가
    화면 어디에도 없었다.

    **한쪽에서 반대쪽으로 갈 때만 센다.** 중립 구간(-19~19)을 드나드는 것은 턴이 아니라
    관중이 갈린 것이고, 그걸 세면 한 커리어에 턴이 수십 번 난다. 처음으로 한쪽에
    서는 것도 턴이 아니다 — 뒤집을 앞면이 없었다.
    """
    items: list[NewsItem] = []
    side = 0
    for report, stats in entries:
        now = 1 if stats.is_face else -1 if stats.is_heel else side
        if side != 0 and now != side:
            heel = now < 0
            items.append(
                NewsItem(
                    week=report.week,
                    kind=NewsKind.TURN,
                    headline=(
                        f"{player}, 등을 돌렸다."
                        if heel
                        else f"{player}, 관중 쪽으로 돌아왔다."
                    ),
                    mood=CrowdMood.JEER if heel else CrowdMood.ROAR,
                    crowd_line=_crowd_line(
                        CrowdMood.JEER if heel else CrowdMood.ROAR, report.week
                    ),
                )
            )
        side = now
    return items
