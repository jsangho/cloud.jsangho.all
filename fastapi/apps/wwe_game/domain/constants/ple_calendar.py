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

from dataclasses import dataclass
from enum import StrEnum

from wwe_game.domain.constants.career_clock import WEEKS_PER_YEAR
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
    tier: ShowTier
    week_offset: int = 0
    """그 달 한가운데에서 몇 주 밀 것인지.

    **한 달에 대회와 특별 방송이 함께 설 수 있어야 한다**(SNME). 달만으로 자리를 잡으면
    3월에 킹 앤 퀸과 SNME를 같이 둘 수 없다.
    """

    @property
    def is_major(self) -> bool:
        return self.tier is ShowTier.MAJOR

    @property
    def is_special(self) -> bool:
        return self.tier is ShowTier.SPECIAL

    @property
    def week_of_year(self) -> int:
        return WEEK_OF_MONTH[self.month] + self.week_offset


def _week_of_year(week: int) -> int:
    """1~52. 커리어 주차는 계속 늘어나므로 해마다 접는다."""
    return (week - 1) % WEEKS_PER_YEAR + 1


@dataclass(frozen=True)
class ShowCalendar:
    """한 브랜드의 대회 달력. **달을 키로 든다** — 간격은 그 결과일 뿐이다."""

    shows: tuple[PleShow, ...]

    def __post_init__(self) -> None:
        weeks = [show.week_of_year for show in self.shows]
        if len(set(weeks)) != len(weeks):
            raise ValueError(f"같은 주차에 무대가 둘입니다: {sorted(weeks)}")
        outside = [w for w in weeks if not 1 <= w <= WEEKS_PER_YEAR]
        if outside:
            raise ValueError(f"연중 주차를 벗어났습니다: {sorted(outside)}")

    def _by_week(self) -> dict[int, PleShow]:
        return {show.week_of_year: show for show in self.shows}

    def is_show_week(self, week: int) -> bool:
        return week > 0 and _week_of_year(week) in self._by_week()

    def show_for(self, week: int) -> PleShow:
        """그 주차의 대회. **PLE 주차에만 의미가 있다.**"""
        show = self._by_week().get(_week_of_year(week)) if week > 0 else None
        if show is None:
            raise ValueError(f"{week}주차는 이 브랜드의 대회 주차가 아닙니다")
        return show

    @property
    def per_year(self) -> int:
        return len(self.shows)


_MAJOR, _STD, _SPECIAL = ShowTier.MAJOR, ShowTier.STANDARD, ShowTier.SPECIAL

MAIN_CALENDAR = ShowCalendar(
    shows=(
        PleShow("로열럼블", 1, _MAJOR),
        PleShow("엘리미네이션 챔버", 2, _STD),
        PleShow("킹 앤 퀸 오브 더 링", 3, _STD),
        PleShow("레슬매니아", 4, _MAJOR),
        PleShow("백래시", 5, _STD),
        PleShow("머니 인 더 뱅크", 6, _STD),
        PleShow("배드 블러드", 7, _STD),
        PleShow("서머슬램", 8, _MAJOR),
        PleShow("나이트 오브 챔피언스", 9, _STD),
        PleShow("크라운 주얼", 10, _STD),
        PleShow("서바이버 시리즈", 11, _MAJOR),
        # ── 분기별 특별 방송 (§3-D21-2) ──
        PleShow("새터데이 나이트 메인 이벤트", 3, _SPECIAL, week_offset=2),
        PleShow("새터데이 나이트 메인 이벤트", 6, _SPECIAL, week_offset=2),
        PleShow("새터데이 나이트 메인 이벤트", 9, _SPECIAL, week_offset=2),
        PleShow("새터데이 나이트 메인 이벤트", 12, _SPECIAL, week_offset=2),
    ),
)
"""메인 로스터 — 1월부터 11월까지 달마다 한 번. **12월은 쉰다**(2026-08-07 사용자 결정).

목록도 사용자가 고른다 — 클래시 앳 더 캐슬·헬 인 어 셀은 뺐다.

달을 실제 시기에 맞췄다: 로열럼블 1월 · 레슬매니아 4월 · 서머슬램 8월 · 서바이버 11월.

**분기별 특별 방송(SNME)이 3·6·9·12월 하순에 함께 선다**(2026-08-07 사용자 요청).
같은 달의 대회와 2주를 띄워 겹치지 않고, **12월에는 이것만 있다** — 대회는 쉬어도
방송은 돈다.
**대형이 고르게 흩어져 있지 않다** — 간격이 일정하면 "다음 큰 대회까지 몇 달"이 늘 같아
계획이 무의미해진다.
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


def calendar_for(brand: Brand) -> ShowCalendar:
    return CALENDARS[brand]


# 브랜드마다 달력이 있어야 한다. 빠뜨리면 그 브랜드는 대회가 영영 안 열린다.
_missing = set(Brand) - set(CALENDARS)
if _missing:  # pragma: no cover - 임포트 시 구조 검증
    raise RuntimeError(f"달력이 없는 브랜드: {sorted(b.value for b in _missing)}")

for _cal in CALENDARS.values():  # pragma: no cover - 임포트 시 구조 검증
    _months = {show.month for show in _cal.shows}
    if not _months <= set(range(1, MONTHS_PER_YEAR + 1)):
        raise RuntimeError(f"달 범위를 벗어난 대회가 있습니다: {sorted(_months)}")
    _ple_months = {s.month for s in _cal.shows if not s.is_special}
    if QUIET_MONTH in _ple_months:
        raise RuntimeError(f"{QUIET_MONTH}월에는 대회를 두지 않습니다")
