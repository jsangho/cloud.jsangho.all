"""생성 화면에서 정해진 뒤 바뀌지 않는 것 (하네스 §3-D10).

이름·성별·국가·플레이스타일 네 가지. **나이는 여기 없다** — 20세 고정이라 입력이 아니고,
`age_at(week)`로 주차에서 파생된다.

성별은 이벤트 조건에 쓰지 않는다(§3-D11). 갈리는 것은 타이틀 이름과 라이벌 풀이지
사건이 아니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from wwe_game.domain.constants.career_clock import START_AGE, WEEKS_PER_YEAR
from wwe_game.domain.constants.countries import Country, Region, region_of
from wwe_game.domain.exceptions import InvalidRingNameError

NAME_MIN_LEN = 2
NAME_MAX_LEN = 20


class Gender(StrEnum):
    MALE = "male"
    FEMALE = "female"


class StyleFamily(StrEnum):
    """이벤트 조건이 보는 스타일 묶음 (§3-D27).

    스타일이 21종이라 값마다 전용 카드 5장(§3-D11)을 주면 지역 카드처럼 덱이 터진다.
    국가(20+)를 권역(5+1)으로 묶은 것과 같은 해법이다 — **고르는 것은 21종, 사건이
    붙는 것은 6종.**
    """

    GRAPPLE = "grapple"
    POWER = "power"
    AERIAL = "aerial"
    STRIKE = "strike"
    SHOW = "show"
    FREE = "free"


class PlayStyle(StrEnum):
    """경기 유형 21종 (2026-08-10 사용자 로스터 CSV의 `style` 값).

    다섯에서 스물하나로 늘었다. 로스터 178명이 실제로 쓰는 값이 21종이었고, 다섯으로
    뭉치면 군터(하드 히팅)와 브록 레스너(파워하우스)가 같은 칸에 들어간다.
    """

    # 그래플 계열
    TECHNICIAN = "technician"
    SUBMISSIONS = "submissions"
    SHOOTER = "shooter"
    UWF = "uwf"
    # 파워 계열
    POWERHOUSE = "powerhouse"
    GIANT = "giant"
    MONSTER = "monster"
    # 공중 계열
    HIGH_FLYER = "high_flyer"
    LUCHA_LIBRE = "lucha_libre"
    STUNTMAN = "stuntman"
    # 타격 계열
    BRAWLER = "brawler"
    HARD_HITTING = "hard_hitting"
    STRONG_STYLE = "strong_style"
    KINGS_ROAD = "kings_road"
    # 쇼 계열
    SHOWMAN = "showman"
    HEEL_STYLE = "heel_style"
    OLD_SCHOOL = "old_school"
    SHOWGIRL = "showgirl"
    # 자유 계열
    HARDCORE = "hardcore"
    ALL_ROUNDER = "all_rounder"
    UNDERDOG = "underdog"


_FAMILY_MEMBERS: tuple[tuple[StyleFamily, tuple[PlayStyle, ...]], ...] = (
    (
        StyleFamily.GRAPPLE,
        (
            PlayStyle.TECHNICIAN,
            PlayStyle.SUBMISSIONS,
            PlayStyle.SHOOTER,
            PlayStyle.UWF,
        ),
    ),
    (
        StyleFamily.POWER,
        (PlayStyle.POWERHOUSE, PlayStyle.GIANT, PlayStyle.MONSTER),
    ),
    (
        StyleFamily.AERIAL,
        (PlayStyle.HIGH_FLYER, PlayStyle.LUCHA_LIBRE, PlayStyle.STUNTMAN),
    ),
    (
        StyleFamily.STRIKE,
        (
            PlayStyle.BRAWLER,
            PlayStyle.HARD_HITTING,
            PlayStyle.STRONG_STYLE,
            PlayStyle.KINGS_ROAD,
        ),
    ),
    (
        StyleFamily.SHOW,
        (
            PlayStyle.SHOWMAN,
            PlayStyle.HEEL_STYLE,
            PlayStyle.OLD_SCHOOL,
            PlayStyle.SHOWGIRL,
        ),
    ),
    (
        StyleFamily.FREE,
        (PlayStyle.HARDCORE, PlayStyle.ALL_ROUNDER, PlayStyle.UNDERDOG),
    ),
)
"""계열 → 소속 스타일. **21종이 빠짐없이 한 번씩** 들어간다 (아래에서 검증한다)."""

FAMILY_OF: dict[PlayStyle, StyleFamily] = {
    style: family for family, styles in _FAMILY_MEMBERS for style in styles
}

if set(FAMILY_OF) != set(PlayStyle):  # pragma: no cover - 임포트 시 구조 검증
    missing = sorted(set(PlayStyle) - set(FAMILY_OF))
    raise RuntimeError(f"계열이 없는 플레이스타일: {missing}")


def family_of(style: PlayStyle) -> StyleFamily:
    """스타일이 속한 계열. 국가 → 권역(`region_of`)과 같은 자리다."""
    return FAMILY_OF[style]


@dataclass(frozen=True)
class RingName:
    """링 네임. 앞뒤 공백을 자른 뒤 2~20자 (하네스 §3-D12).

    검증을 라우터가 아니라 값 객체에 두는 이유는, 이 이름이 서술 템플릿의 `{player}`
    슬롯으로 들어가기 때문이다 — 들어오는 입구가 하나여야 한다.

    중복은 허용한다. 게임 내부 이름이라 유일할 이유가 없다.
    """

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise InvalidRingNameError("이름은 문자열이어야 합니다.")
        stripped = self.value.strip()
        if any(ch.isprintable() is False for ch in stripped):
            # 개행·탭·제어문자가 섞이면 서술 한 줄이 두 줄로 깨진다.
            raise InvalidRingNameError("이름에 제어문자를 넣을 수 없습니다.")
        if not NAME_MIN_LEN <= len(stripped) <= NAME_MAX_LEN:
            raise InvalidRingNameError(
                f"이름은 {NAME_MIN_LEN}~{NAME_MAX_LEN}자로 입력해 주세요."
            )
        object.__setattr__(self, "value", stripped)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class WrestlerIdentity:
    name: RingName
    gender: Gender
    country: Country
    play_style: PlayStyle

    @property
    def region(self) -> Region:
        """이벤트 조건이 보는 값. 국가를 고르면 자동으로 정해진다 (§3-D14)."""
        return region_of(self.country)

    @property
    def style_family(self) -> StyleFamily:
        """이벤트 조건이 보는 값. 스타일을 고르면 자동으로 정해진다 (§3-D27)."""
        return family_of(self.play_style)

    def age_at(self, week: int) -> int:
        """20세에서 시작해 52주마다 한 살. 1560주에 정확히 50세가 된다 (§11-9)."""
        if week < 0:
            raise ValueError(f"주차는 음수일 수 없습니다: {week}")
        return START_AGE + week // WEEKS_PER_YEAR
