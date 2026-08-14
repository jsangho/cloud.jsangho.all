"""대형 대회 달력 — **달마다 한 번, 12월은 쉰다** (하네스 §3-D21-1).

**13주에 한 번은 현실과 너무 멀었다**(2026-08-07 사용자 요청). 그러면 연 4회이고, 실제
단체는 한 달에 한 번꼴로 큰 대회를 연다.

세 번 고쳐서 지금 모양이 됐고, 그 과정이 곧 설계 근거다.

1. **4주 간격 13개** — 균일해서 다루기 쉬웠지만 연 13회라 목록과 안 맞았다
2. **5주 간격 11개** — 목록은 맞았지만 대회 날짜가 해마다 3주씩 밀렸다
3. **달마다 한 번, 12월 제외** ← 지금. 사용자 결정(2026-08-07)이고 실제 달력과 같다

**고정 간격을 버렸다.** 달마다 한 번이면 간격이 4~5주로 들쭉날쭉하고, 11월과 이듬해
1월 사이는 **8주가 빈다** — 그게 12월 공백이다. 균일한 간격으로는 이 공백을 만들 수 없다.

**NXT는 메인과 달력을 나눈다**(2026-08-07 사용자 요청). 육성 브랜드라 큰 대회가 드물고,
이름도 겹치지 않는다. 스탠드 앤 딜리버는 그곳의 레슬매니아지 메인 로스터의 대회가 아니다.

| | 메인 로스터 | NXT |
|---|---|---|
| 연 횟수 | 11회 (1~11월) | 4회 |
| 대형 | 4회 (로열럼블·레슬매니아·서머슬램·서바이버) | 2회 (스탠드 앤 딜리버·핼러윈 해벅) |

급을 나눈 이유가 곧 이 개정이 성립하는 조건이다.

| | 급 없이 | 급을 나눠 |
|---|---|---|
| 진행 정지 | 커리어당 300번 — 클릭이 세 배로 는다 | **대형에서만** 멈춘다 |
| 타이틀전 | 전부 같은 확률이면 큰 대회가 특별하지 않다 | 대형에서 두 배 |
| 서술 | "대형 대회"라는 한 덩어리 | 이름이 로그에 남는다 |

이름은 실존 대회다 — 벨트·선수와 같은 판단이다(§3-D13). 전개는 허구임을 화면에 밝힌다.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from functools import lru_cache
from typing import Final

from wwe_game.domain.constants import career_rules as rules
from wwe_game.domain.constants.career_clock import WEEKS_PER_YEAR
from wwe_game.domain.constants.countries import Region
from wwe_game.domain.services import seeded_roll
from wwe_game.domain.services.seeded_roll import SeededRoll
from wwe_game.domain.value_objects.title import Brand

MONTHS_PER_YEAR = 12

WEEK_OF_MONTH: dict[int, int] = {
    1: 2,
    2: 6,
    3: 11,
    4: 15,
    5: 20,
    6: 24,
    7: 28,
    8: 32,
    9: 37,
    10: 41,
    11: 46,
    12: 50,
}
"""달 → 그 달 한가운데의 연중 주차. 대회를 여기에 건다.

`(달 − 0.5) × 52 / 12`를 반올림한 값을 **표로 박아 뒀다** — 계산으로 두면 파이썬의
반올림 규칙(짝수 쪽으로 붙는다)에 결과가 걸려, 읽는 사람이 표를 머릿속으로 다시
돌려야 한다. 어차피 열두 줄이다.
"""


class ShowTier(StrEnum):
    """대회의 급. 타이틀전 확률·부상 위험·진행 정지가 여기서 갈린다."""

    MAJOR = "major"
    """커리어의 분기점이 되는 대회. 진행이 여기서만 멈춘다."""
    STANDARD = "standard"
    """큰 경기지만 한 해에 여러 번 온다."""
    SPECIAL = "special"
    """**PLE와 주간 TV 사이**의 특별 방송 (2026-08-07 사용자 요청).

    분기별 토요일 특집이다. 경기는 반드시 있지만 대회는 아니다 — 타이틀전 확률도
    마모도 그 사이에 놓인다. 주차 종류가 `WeekKind.SPECIAL`로 갈리는 유일한 급이다.
    """


MONTH_FIRST_WEEK: tuple[int, ...] = tuple(
    (month * WEEKS_PER_YEAR) // MONTHS_PER_YEAR + 1 for month in range(MONTHS_PER_YEAR)
)
"""각 달이 시작하는 연중 주차 (1월=1 · 2월=5 · 3월=9 … 12월=48).

`WEEK_OF_MONTH`(달 한가운데)의 짝이다. 저쪽은 대회를 걸 자리를 정하고, 이쪽은
**주차를 날짜로 되읽는 데** 쓴다 — 화면이 "91주"가 아니라 "2년차 3월 2주"로
말하려면 필요하다 (2026-08-10 사용자 요청).

**프론트에서 다시 계산하지 않는다.** 달력은 도메인의 것이고, 양쪽이 각자 나누면
반올림 한 번에 대회 날짜와 표시가 어긋난다.
"""


def year_of(week: int) -> int:
    """커리어 주차 → 연차 (1부터). **달력이 해마다 다시 뽑히므로** 자주 쓴다 (§3-D71)."""
    return (max(week, 1) - 1) // WEEKS_PER_YEAR + 1


def date_of(week: int) -> tuple[int, int, int]:
    """연중 주차(1~1560) → (연차, 달, 그 달의 몇째 주). 전부 1부터 센다."""
    if week < 1:
        raise ValueError(f"주차는 1 이상이어야 합니다: {week}")
    year, in_year = divmod(week - 1, WEEKS_PER_YEAR)
    in_year += 1
    month = MONTHS_PER_YEAR
    for index, first in enumerate(MONTH_FIRST_WEEK):
        if in_year < first:
            month = index
            break
    return year + 1, month, in_year - MONTH_FIRST_WEEK[month - 1] + 1


@dataclass(frozen=True)
class PleShow:
    name: str
    month: int
    """그 대회가 서는 달. **0이면 아직 안 정해졌다** — 해마다 다시 뽑는 대회의 선언
    상태이고, `shows_in()`이 그 해의 달을 채워 준다 (§3-D71).
    """
    tier: ShowTier
    week_offset: int = 0
    """그 달 한가운데에서 몇 주 밀 것인지.

    **한 달에 대회와 특별 방송이 함께 설 수 있어야 한다**(SNME). 달만으로 자리를 잡으면
    한 달에 둘을 둘 수 없다.
    """
    logo: str = ""
    """로고 파일 키 (§3-D71). 화면이 `/ple/<key>.png`로 찾는다."""
    nights: int = 1
    """며칠에 걸쳐 여는가 (2026-08-12 사용자 결정).

    **레슬매니아·서머슬램은 이틀이다.** 이틀이면 카드도 두 배로 선다(§3-D55) — 그게
    "그 밤이 크다"를 화면에서 말하는 방식이다.
    """
    week: int = 0
    """연중 주차를 직접 못 박는다. 0이면 달에서 계산한다.

    **특별 방송만 이 자리를 쓴다** (§3-D71): SNME는 달이 아니라 **대회 사이가 가장 먼
    자리**에 서므로, 달과 오프셋으로는 그 자리를 말할 수 없다.
    """
    region: Region | None = None
    """개최 권역. **해외에서 여는 밤만 채워진다**(클래시) — 그 앞뒤 한 주까지 투어가
    그쪽에 머문다 (§3-D71 · §3-D14-1의 예외).
    """
    two_nights_from: int = 0
    """이 연차부터 이틀로 연다. 0이면 `nights` 그대로 (§3-D71).

    **로열럼블은 3년차부터다.** 처음부터 이틀이면 커진 것이 아니라 원래 큰 것이 된다.
    """
    alt: tuple[str, str] | None = None
    """가끔 쓰는 다른 얼굴 — `(이름, 로고)` (§3-D71).

    **서바이버 시리즈뿐이다.** 기본은 워게임즈이고 가끔 전통 제거 매치로 열린다 —
    사용자가 로고를 둘 가져온 이유가 이것이다. 이름이 갈리므로 그 밤의 시그니처
    경기(`SIGNATURE_MATCHES`)도 함께 갈린다.
    """
    alt_odds: float = 0.0
    """다른 얼굴로 열릴 확률. `alt`가 없으면 의미 없다."""
    hosts: tuple[tuple[str, Region], ...] = ()
    """개최지 후보 — `(도시, 권역)`. 해마다 다시 뽑고 이름이 "○○ 인 △△"로 완성된다."""

    @property
    def is_major(self) -> bool:
        return self.tier is ShowTier.MAJOR

    @property
    def is_special(self) -> bool:
        return self.tier is ShowTier.SPECIAL

    @property
    def week_of_year(self) -> int:
        if self.week:
            return self.week
        if not self.month:
            raise ValueError(
                f"{self.name}: 달이 아직 안 정해졌습니다 — 그 해의 달력부터 뽑습니다"
            )
        return WEEK_OF_MONTH[self.month] + self.week_offset


def _week_of_year(week: int) -> int:
    """1~52. 커리어 주차는 계속 늘어나므로 해마다 접는다."""
    return (week - 1) % WEEKS_PER_YEAR + 1


@dataclass(frozen=True)
class ShowCalendar:
    """한 브랜드의 대회 달력. **해마다 다시 뽑힌다** (§3-D71).

    2026-08-12까지는 상수였다 — 30년 내내 6월은 클래시였고, 두 번째 해가 첫 해와 똑같이
    흘렀다. 사용자 결정으로 **여섯만 달이 고정**되고(럼블·챔버·레슬매니아·백래시·
    서머슬램·서바이버) 나머지 넷은 남은 달에서 해마다 다시 뽑힌다.

    **시드를 여기에 둔다.** `is_show_week(week)`·`show_for(week)`에 시드를 넘기게 하면
    호출부 열다섯 곳이 전부 바뀌는데, 주차가 이미 연차를 품고 있으므로 달력이 시드를
    들고 있으면 서명이 그대로다.
    """

    shows: tuple[PleShow, ...]
    """달이 고정된 대회. NXT는 전부 여기 있다."""
    floating: tuple[PleShow, ...] = ()
    """해마다 달을 다시 뽑는 대회. 선언 시점에는 `month=0`이다."""
    float_months: tuple[int, ...] = ()
    """유동 대회가 들어갈 후보 달. **후보가 대회보다 하나 많다** — 그래야 한 달은
    비고, 그 빈 달이 해마다 옮겨 다닌다."""
    special: PleShow | None = None
    """특별 방송의 본. 자리는 그 해의 간격이 정한다."""
    special_count: int = 0
    """한 해에 몇 번 여는가."""
    seed: int = 0
    """그 판의 시드. `calendar_for(brand, seed)`가 채운다."""

    def __post_init__(self) -> None:
        weeks = [show.week_of_year for show in self.shows]
        if len(set(weeks)) != len(weeks):
            raise ValueError(f"같은 주차에 무대가 둘입니다: {sorted(weeks)}")
        outside = [w for w in weeks if not 1 <= w <= WEEKS_PER_YEAR]
        if outside:
            raise ValueError(f"연중 주차를 벗어났습니다: {sorted(outside)}")
        if len(self.float_months) < len(self.floating):
            raise ValueError(
                f"유동 대회 {len(self.floating)}개를 둘 달이 "
                f"{len(self.float_months)}개뿐입니다"
            )

    def shows_in(self, year: int) -> tuple[PleShow, ...]:
        """그 연차의 대회 목록. 주차 순으로 선다."""
        return _layout(self, year)

    def is_show_week(self, week: int) -> bool:
        return week > 0 and _week_of_year(week) in _by_week(self, year_of(week))

    def show_for(self, week: int) -> PleShow:
        """그 주차의 대회. **PLE 주차에만 의미가 있다.**"""
        show = (
            _by_week(self, year_of(week)).get(_week_of_year(week)) if week > 0 else None
        )
        if show is None:
            raise ValueError(f"{week}주차는 이 브랜드의 대회 주차가 아닙니다")
        return show

    def week_of(self, name: str, week: int) -> int | None:
        """그 해에 `name` 대회가 서는 연중 주차. 그 해 달력에 없으면 `None`.

        **달력이 해마다 바뀌므로 이름으로 되짚어야 한다** (§3-D71) — 토너먼트 결승이
        올해 몇 주차인지는 선언이 아니라 그 해의 달력만 안다.
        """
        return next(
            (s.week_of_year for s in self.shows_in(year_of(week)) if s.name == name),
            None,
        )

    def tour_region(self, week: int) -> Region | None:
        """그 주차에 투어가 머무는 권역. 머물지 않으면 `None` (§3-D71).

        **해외에서 여는 밤의 앞뒤 한 주까지다.** 대회 하나만 해외로 두면 그 주만
        건너뛰듯 대륙을 옮겼다가 다음 주에 돌아오는 그림이 된다.
        """
        if week <= 0:
            return None
        in_year = _week_of_year(week)
        for show in self.shows_in(year_of(week)):
            if show.region is None:
                continue
            gap = abs(show.week_of_year - in_year)
            if min(gap, WEEKS_PER_YEAR - gap) <= 1:
                return show.region
        return None

    def per_year(self, year: int = 1) -> int:
        return len(self.shows_in(year))


# ── 그 해의 달력을 뽑는다 (§3-D71) ────────────────────────────


@lru_cache(maxsize=512)
def _layout(calendar: ShowCalendar, year: int) -> tuple[PleShow, ...]:
    """(달력, 연차) → 그 해에 서는 대회들. **한 해에 한 번만 굴린다.**

    순서가 곧 계약이다: 유동 대회의 달 → 대회마다의 그 해 얼굴 → 특별 방송의 자리.
    앞을 건드리면 뒤가 통째로 밀리므로, 규칙을 더할 때는 **뒤에 붙인다**.

    캐시를 두는 이유는 `_last_show`가 한 번 부를 때마다 52주를 되짚기 때문이다 —
    달력이 상수였을 때는 공짜였던 자리다.
    """
    roll = SeededRoll(calendar.seed, year, seeded_roll.CALENDAR)
    shows = list(calendar.shows)
    remaining = list(calendar.float_months)
    for show in calendar.floating:
        month = roll.pick(tuple(remaining))
        remaining.remove(month)
        shows.append(replace(show, month=month))
    shows = [_in_year(show, year, roll) for show in shows]
    shows.extend(_specials(calendar, tuple(shows)))
    return tuple(sorted(shows, key=lambda s: s.week_of_year))


@lru_cache(maxsize=512)
def _by_week(calendar: ShowCalendar, year: int) -> dict[int, PleShow]:
    """그 해의 주차 → 대회. **읽기 전용으로 쓴다** — 캐시가 같은 사전을 돌려준다."""
    return {show.week_of_year: show for show in _layout(calendar, year)}


def _in_year(show: PleShow, year: int, roll: SeededRoll) -> PleShow:
    """그 해의 얼굴로 고친다 — 몇 밤인지 · 어느 얼굴인지 · 어디서 여는지 (§3-D71)."""
    if show.two_nights_from and year >= show.two_nights_from:
        show = replace(show, nights=2)
    if show.alt is not None and roll.chance(show.alt_odds):
        show = replace(show, name=show.alt[0], logo=show.alt[1])
    if show.hosts:
        city, region = roll.pick(show.hosts)
        show = replace(show, name=f"{show.name} 인 {city}", region=region)
    return show


def _specials(calendar: ShowCalendar, shows: tuple[PleShow, ...]) -> list[PleShow]:
    """특별 방송을 **대회 사이가 가장 먼 자리**에 세운다 (§3-D71 · 사용자 결정).

    분기 고정이었을 때는 대회가 촘촘한 달에도 SNME가 끼어들고, 정작 8주가 비는
    연말 공백은 그대로 비어 있었다. 한 자리를 잡을 때마다 그 자리를 채운 것으로
    치고 다시 재는 이유가 그것이다 — 넷을 한꺼번에 고르면 가장 넓은 한 간격에
    전부 몰린다.
    """
    if calendar.special is None or calendar.special_count <= 0:
        return []
    blocked = _qualifier_weeks(shows)
    occupied = sorted(show.week_of_year for show in shows)
    placed: list[PleShow] = []
    for _ in range(calendar.special_count):
        week = _widest_gap_week(occupied, blocked)
        if week is None:  # pragma: no cover - 달력이 52주를 다 채운 경우
            break
        occupied = sorted([*occupied, week])
        placed.append(replace(calendar.special, week=week, month=date_of(week)[1]))
    return placed


def _qualifier_weeks(shows: tuple[PleShow, ...]) -> frozenset[int]:
    """토너먼트 예선 주차 (§3-D33). **특별 방송이 여기 서면 대진이 끊긴다.**

    예선 주차에는 반드시 경기가 있어야 하는데, 특별 방송이 서면 그 주가 통째로
    특별 방송의 것이 되어 올라간 사람이 없는 채로 결승이 온다. 2026-08-12에는 6월
    SNME를 한 주 앞으로 미는 것으로 막았고, 자리가 유동이 된 지금은 규칙으로 막는다.
    """
    final = next((s.week_of_year for s in shows if s.name == NIGHT_OF_CHAMPIONS), None)
    if final is None:
        return frozenset()
    return frozenset(
        (final - back - 1) % WEEKS_PER_YEAR + 1
        for back in range(1, rules.TOURNAMENT_ROUNDS)
    )


def _widest_gap_week(occupied: list[int], blocked: frozenset[int]) -> int | None:
    """가장 넓은 간격의 한가운데. 간격은 **한 해를 돌아서** 잰다.

    연말 공백(11월 → 이듬해 1월, 8주)이 가장 넓은데, 돌지 않고 재면 그 자리가
    아예 안 보인다. 같은 넓이면 앞선 간격이 이긴다 — 시드가 같으면 달력도 같아야 한다.
    """
    best_week, best_span = None, 0
    for index, start in enumerate(occupied):
        end = occupied[(index + 1) % len(occupied)]
        span = (end - start) % WEEKS_PER_YEAR or WEEKS_PER_YEAR
        if span <= best_span:
            continue
        week = _free_week(start, span, blocked)
        if week is not None:
            best_week, best_span = week, span
    return best_week


def _free_week(start: int, span: int, blocked: frozenset[int]) -> int | None:
    """`start` 다음 `span`주 안에서 한가운데에 가장 가까운 빈 주차."""
    middle = span / 2
    for offset in sorted(range(1, span), key=lambda o: (abs(o - middle), o)):
        week = (start + offset - 1) % WEEKS_PER_YEAR + 1
        if week not in blocked:
            return week
    return None


_MAJOR, _STD, _SPECIAL = ShowTier.MAJOR, ShowTier.STANDARD, ShowTier.SPECIAL

WRESTLEMANIA: Final = "레슬매니아"
"""**도전권이 현금화되는 밤** (§3-D36). 럼블·챔버 우승자가 여기서 벨트에 도전한다."""

NIGHT_OF_CHAMPIONS: Final = "나이트 오브 챔피언스"
"""**토너먼트 결승이 서는 밤** (§3-D71, 2026-08-12 사용자 결정).

킹 앤 퀸 오브 더 링이 달력에서 빠지면서 그 결승이 갈 곳을 잃었다. 예선 둘은 그대로 앞
두 주에 서고(§3-D33) 결승만 이 밤으로 옮겼다.
"""

CLASH_SERIES: Final = "클래시"
"""**해외에서 여는 밤** (§3-D71). 이름이 "클래시 인 ○○"로 완성된다 — 그 해의 개최지가
이름의 절반이다. 이 대회 앞뒤 한 주는 투어가 그쪽에 머문다(§3-D14-1의 예외).
"""

SURVIVOR_SERIES: Final = "서바이버 시리즈: 워게임즈"
"""**두 얼굴을 가진 밤** (§3-D71). 기본은 워게임즈다 — 로고도 그래서 둘이다."""

SURVIVOR_SERIES_CLASSIC: Final = "서바이버 시리즈"
"""가끔 돌아오는 옛 얼굴 — **전통 제거 매치**의 밤 (§3-D71).

이름이 갈리는 것이 규칙의 손잡이다: `SIGNATURE_MATCHES`가 이름으로 그 밤의 경기를
고르므로, 얼굴이 바뀌면 링 위의 형식도 함께 바뀐다.
"""

CLASSIC_SURVIVOR_ODDS: Final = 0.25
"""전통 제거 매치로 열릴 확률. **네 해에 한 번쯤**이다.

절반으로 두면 "가끔"이 아니라 번갈아가 되고, 0.1이면 30년에 세 번이라 두 번째 로고를
본 적 없는 커리어가 흔해진다.
"""

CLASH_HOSTS: Final[tuple[tuple[str, Region], ...]] = (
    ("파리", Region.EU),
    ("베를린", Region.EU),
    ("런던", Region.EU),
    ("도쿄", Region.JP),
    ("멕시코시티", Region.LATAM),
    ("시드니", Region.OCE),
    ("서울", Region.KR),
)
"""클래시의 개최지 후보 (§3-D71). **북미가 없다** — 해외에서 여는 것이 이 대회다."""

MITB: Final = "머니 인 더 뱅크"
"""**가방이 걸리는 밤** (§3-D36). 래더 매치는 다른 밤에도 열리지만 가방은 여기서만 나온다.

두 이름을 상수로 두는 이유는 규칙이 문자열로 이 밤들을 짚기 때문이다 — 오타는 조용히
"도전권이 영영 안 쓰이는" 결과가 되고, 그건 아무 데서도 안 터진다. 아래 달력의 이름과
어긋나면 임포트 시점에 걸리도록 검증도 함께 둔다.
"""

RUMBLE_TWO_NIGHTS_FROM: Final = 3
"""로열럼블이 이틀이 되는 연차 (§3-D71 · 사용자 결정).

**커리어의 처음 두 해는 하루다.** 처음부터 이틀이면 대회가 커진 것이 아니라 원래
큰 것이 되고, 그러면 연차가 흐르는 느낌이 하나 사라진다.
"""

MAIN_CALENDAR = ShowCalendar(
    shows=(
        PleShow(
            "로열럼블",
            1,
            _MAJOR,
            logo="1_royal_rumble",
            two_nights_from=RUMBLE_TWO_NIGHTS_FROM,
        ),
        PleShow("엘리미네이션 챔버", 2, _STD, logo="2_elimination_chamber"),
        PleShow(WRESTLEMANIA, 4, _MAJOR, logo="4_wrestlemania", nights=2),
        PleShow("백래시", 5, _STD, logo="5_backlash"),
        PleShow("서머슬램", 8, _MAJOR, logo="8_summerslam", nights=2),
        PleShow(
            SURVIVOR_SERIES,
            11,
            _MAJOR,
            logo="11_survivor_series_war",
            alt=(SURVIVOR_SERIES_CLASSIC, "11_survivor_series_elimi"),
            alt_odds=CLASSIC_SURVIVOR_ODDS,
        ),
    ),
    floating=(
        PleShow(CLASH_SERIES, 0, _STD, logo="6_clash_series", hosts=CLASH_HOSTS),
        PleShow(NIGHT_OF_CHAMPIONS, 0, _STD, logo="7_night_of_champions"),
        PleShow(MITB, 0, _STD, logo="9_money_in_the_bank"),
        PleShow("크라운 주얼", 0, _STD, logo="10_crown_jewel"),
    ),
    float_months=(3, 6, 7, 9, 10),
    special=PleShow("새터데이 나이트 메인 이벤트", 0, _SPECIAL, logo="snme"),
    special_count=4,
)
"""메인 로스터 — 한 해에 대회 열 번과 특별 방송 넷. **12월은 쉰다**(2026-08-07 결정).

목록은 사용자가 고른다. 2026-08-12에 사용자가 가져온 로고 목록에 맞췄다(§3-D71):
킹 앤 퀸 오브 더 링과 배드 블러드를 빼고 **클래시 시리즈**를 넣었다.

**달이 해마다 바뀐다** (§3-D71 · 사용자 결정). 고정은 여섯이고 — 럼블(1) · 챔버(2) ·
레슬매니아(4) · 백래시(5) · 서머슬램(8) · 서바이버(11) — 나머지 넷은 `float_months`
다섯 달에서 해마다 다시 뽑힌다. **후보가 하나 많아서 한 달은 비고**, 그 빈 달도 해마다
옮겨 다닌다. 30년을 같은 달력으로 흘려보내지 않으려는 결정이다.

**대회가 아니라 간격이 특별 방송의 자리를 정한다.** SNME는 그 해 대회 사이가 가장 먼
네 자리에 선다 — 연말 공백(8주)은 그래서 늘 하나를 받는다.
"""

NXT_CALENDAR = ShowCalendar(
    shows=(
        PleShow("벤전스 데이", 2, _STD),
        PleShow("스탠드 앤 딜리버", 4, _MAJOR),
        PleShow("그레이트 아메리칸 배시", 7, _STD),
        PleShow("핼러윈 해벅", 10, _MAJOR),
    ),
)
"""NXT — 연 4회. **육성 브랜드라 큰 무대가 드물다.**

메인의 열한 번을 그대로 주면 NXT 구간(1.5~3.6년, §3-D22)에만 대회가 서른 번 넘게 열려,
정작 올라간 뒤가 심심해진다. 큰 무대가 귀해야 콜업이 사건이 된다.

**12월 대회(데드라인)는 뺐다** — 메인과 같은 규칙을 따른다.
"""

CALENDARS: dict[Brand, ShowCalendar] = {
    Brand.NXT: NXT_CALENDAR,
    Brand.RAW: MAIN_CALENDAR,
    Brand.SMACKDOWN: MAIN_CALENDAR,
}

QUIET_MONTH = 12
"""**대회**가 열리지 않는 달. 연말은 비워 둔다 (2026-08-07 사용자 결정).

특별 방송(SNME)은 예외다 — 대회가 쉬는 달에도 방송은 돈다.
"""


def calendar_for(brand: Brand, seed: int = 0) -> ShowCalendar:
    """그 브랜드의 달력. **시드를 함께 준다** — 달력이 해마다 다시 뽑히기 때문이다.

    시드를 빼면 0번 판의 달력이 나온다. 규칙이 아니라 구조(대회 이름·급)만 볼 때 쓴다.
    """
    calendar = CALENDARS[brand]
    return calendar if seed == calendar.seed else replace(calendar, seed=seed)


# 규칙이 이름으로 짚는 밤들이 실제 달력에 있어야 한다 (§3-D36). 오타는 실패가 아니라
# **아무 일도 안 일어남**으로 나타나므로 여기서 잡는다. 유동 대회도 함께 본다 —
# 나이트 오브 챔피언스는 달만 유동이지 해마다 반드시 선다.
_NAMED = {WRESTLEMANIA, MITB, NIGHT_OF_CHAMPIONS}
_MAIN_NAMES = {show.name for show in MAIN_CALENDAR.shows + MAIN_CALENDAR.floating}
if not _NAMED <= _MAIN_NAMES:  # pragma: no cover - 임포트 시 구조 검증
    raise RuntimeError(
        f"달력에 없는 대회를 규칙이 가리킵니다: {sorted(_NAMED - _MAIN_NAMES)}"
    )

# 브랜드마다 달력이 있어야 한다. 빠뜨리면 그 브랜드는 대회가 영영 안 열린다.
_missing = set(Brand) - set(CALENDARS)
if _missing:  # pragma: no cover - 임포트 시 구조 검증
    raise RuntimeError(f"달력이 없는 브랜드: {sorted(b.value for b in _missing)}")

for _cal in CALENDARS.values():  # pragma: no cover - 임포트 시 구조 검증
    _months = {show.month for show in _cal.shows} | set(_cal.float_months)
    if not _months <= set(range(1, MONTHS_PER_YEAR + 1)):
        raise RuntimeError(f"달 범위를 벗어난 대회가 있습니다: {sorted(_months)}")
    if QUIET_MONTH in _months:
        raise RuntimeError(f"{QUIET_MONTH}월에는 대회를 두지 않습니다")
