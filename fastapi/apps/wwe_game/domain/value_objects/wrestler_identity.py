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


class PlayStyle(StrEnum):
    TECHNICIAN = "technician"
    POWERHOUSE = "powerhouse"
    HIGH_FLYER = "high_flyer"
    BRAWLER = "brawler"
    SHOWMAN = "showman"


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

    def age_at(self, week: int) -> int:
        """20세에서 시작해 52주마다 한 살. 1560주에 정확히 50세가 된다 (§11-9)."""
        if week < 0:
            raise ValueError(f"주차는 음수일 수 없습니다: {week}")
        return START_AGE + week // WEEKS_PER_YEAR
